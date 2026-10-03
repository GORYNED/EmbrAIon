// Claude Code Mods early-access API. No automatic agent registration or spawn.
const PLUGIN = 'embraion-mods-probe'
const COMMAND = 'embraion-probe'
const EFFORTS = new Set(['low', 'medium', 'high', 'xhigh', 'max'])
// Structural selector check only: availability belongs to the installed host.
// A version segment keeps plain aliases (sonnet, opus, inherit) out.
const VERSIONED_MODEL = /^claude-[a-z0-9]+(?:-[a-z0-9]+)*-\d+(?:-\d+)*$/

function object(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function own(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key)
}

// Validate the small subset this experiment can check. The caller still owns
// classification, privacy, access, policy, and the bounded task prompt.
export function validatePlan(plan) {
  if (!object(plan) || plan.surface !== 'claude-agent' ||
      plan.status !== 'handoff-required' || plan.executed !== false) {
    throw Error('Expected an unexecuted claude-agent handoff plan')
  }
  const definition = plan['scoped-definition']
  const overrides = plan['definition-overrides']
  if (!object(definition) || !object(overrides) || !object(plan.arguments)) {
    throw Error('Missing scoped definition, overrides, or arguments')
  }
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(definition.name) ||
      plan.arguments.subagent_type !== definition.name ||
      typeof definition.description !== 'string' || !definition.description ||
      typeof definition.prompt !== 'string' || !definition.prompt ||
      !Array.isArray(definition.tools) || !definition.tools.length ||
      !definition.tools.every(tool => typeof tool === 'string' && !!tool)) {
    throw Error('Scoped definition does not match the planned native agent type')
  }
  if (!VERSIONED_MODEL.test(definition.model) || definition.model !== overrides.model) {
    throw Error('Probe requires one explicit versioned Claude model selector in the definition and overrides')
  }
  if (!EFFORTS.has(definition.effort) || definition.effort !== overrides.effort) {
    throw Error('Probe requires one explicit matching effort level')
  }
  if (Object.keys(overrides).some(key => key !== 'model' && key !== 'effort') ||
      Object.keys(definition).some(key => !['name', 'description', 'prompt', 'tools', 'model', 'effort'].includes(key)) ||
      own(plan.arguments, 'model') || own(plan.arguments, 'effort')) {
    throw Error('Unsupported or conflicting native fields')
  }
  return definition
}

function stopped(e) {
  return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: null, usage: null }
}

/** @type {import('claude-code').Register} */
export const register = on => {
  let scope = null
  let registrationAttempted = false
  let mismatch = false
  const started = new Set()
  const allowed = new Set()
  const responseMatched = new Set()
  const blockedIds = new Set()
  const events = []
  const record = event => {
    if (event.kind === 'spawn-started' || (event.kind === 'spawn-model-mismatch' && event.agentId)) {
      started.add(event.agentId)
    }
    if (event.kind === 'step-allowed') allowed.add(event.agentId)
    if (event.kind === 'response-model-matched') responseMatched.add(event.agentId)
    if ((event.kind === 'spawn-model-mismatch' || event.kind === 'response-model-mismatch') && event.agentId) {
      blockedIds.add(event.agentId)
    }
    if (event.kind === 'registration-mismatch' || event.kind === 'spawn-model-mismatch' ||
        event.kind === 'step-blocked' || event.kind === 'response-model-mismatch') mismatch = true
    events.push(event)
    if (events.length > 20) events.shift()
  }

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({
      name: COMMAND,
      description: 'Opt-in scoped agent registration and native routing evidence',
      argumentHint: 'load <local-plan.json> | status',
    })
    return result
  })

  on('command.run', { command: COMMAND }, async ($, e) => {
    if (e.args.trim() === 'status') {
      return { text: JSON.stringify({
        registeredAgent: scope?.agent ?? null,
        requestedModel: scope?.model ?? null,
        requestedEffort: scope?.effort ?? null,
        events,
        routeEvidence: mismatch ? 'mismatch' : scope !== null && started.size > 0 &&
          [...started].every(id => responseMatched.has(id)) ?
          'response-model-corroborated-effort-request-observed' :
          scope !== null && started.size > 0 && [...started].every(id => allowed.has(id)) ?
          'step-request-observed' : 'unverified',
      }, null, 2) }
    }
    const match = /^load\s+(\S+)$/.exec(e.args.trim())
    if (!match || match[1].includes('://') || match[1].startsWith('\\\\')) {
      return { text: 'Usage: /embraion-probe load <local-plan.json> | status' }
    }
    try {
      const plan = JSON.parse(await $.fs.read(match[1]))
      const definition = validatePlan(plan)
      // Replacing a registered name is legal in the API, but this probe keeps
      // one immutable assignment per session to avoid stale evidence.
      if (registrationAttempted) return { text: 'Registration was already attempted in this session; start a fresh session.' }
      registrationAttempted = true
      const { agent } = await $.agent.register(definition)
      const expected = `${PLUGIN}:${definition.name}`
      if (agent !== expected) {
        record({ kind: 'registration-mismatch', expected, observed: agent })
        return { text: 'Registration returned an unexpected agent type; do not invoke it.' }
      }
      scope = { agent, model: definition.model, effort: definition.effort }
      record({ kind: 'registered', agent })
      return { text: `Registered ${agent}. The plan's unqualified subagent_type maps to this plugin-qualified type. Ask Claude to invoke Agent with subagent_type ${agent} and a bounded prompt, then run /embraion-probe status. Registration is not execution.` }
    } catch (error) {
      // Do not include exception text: parsers and other plugins can put file
      // contents in errors. The plan and prompt never enter probe output.
      return { text: `Probe load refused (${error instanceof SyntaxError ? 'invalid JSON' : 'invalid or unreadable plan'}).` }
    }
  })

  on('agent.spawn', async ($, e, next) => {
    if (!scope || e.subagentType !== scope.agent) return next(e)
    if (e.fork || (e.model !== undefined && e.model !== scope.model)) {
      record({ kind: 'spawn-blocked', reason: 'fork or model override' })
      return { deny: 'EmbrAIon probe: scoped agent requires its exact model and no fork.' }
    }
    const result = await next(e)
    if (result.deny) {
      record({ kind: 'spawn-denied' })
    } else if (result.model !== scope.model || !result.agentId) {
      record({ kind: 'spawn-model-mismatch', agentId: result.agentId ?? null, observedModel: result.model })
    } else {
      record({ kind: 'spawn-started', agentId: result.agentId, model: result.model })
    }
    return result
  })

  on('turn.step', async function* ($, e, next) {
    if (!scope || !e.agentId) return yield* next(e)
    // The list identifies the native loop even if it starts before the
    // agent.spawn result is available to this hook.
    const knownStart = started.has(e.agentId)
    let info
    try {
      info = (await $.agent.list()).find(agent => agent.id === e.agentId)
    } catch {
      // A known start is still identified by the returned agentId. An
      // unidentified loop cannot be claimed as evidence for this assignment.
      if (!knownStart) return yield* next(e)
    }
    if (blockedIds.has(e.agentId)) {
      record({ kind: 'step-blocked', agentId: e.agentId, reason: 'earlier model mismatch', index: e.index })
      return stopped(e)
    }
    if (knownStart && info && info.type !== scope.agent) {
      record({ kind: 'step-blocked', agentId: e.agentId, reason: 'agent identity changed', index: e.index })
      return stopped(e)
    }
    if (!knownStart && info?.type !== scope.agent) return yield* next(e)
    if (e.model !== scope.model || e.effort !== scope.effort) {
      record({ kind: 'step-blocked', agentId: e.agentId, observedModel: e.model,
        observedEffort: e.effort ?? null, index: e.index })
      return stopped(e)
    }
    const result = yield* next(e)
    record({ kind: 'step-allowed', agentId: e.agentId, observedModel: e.model,
      observedEffort: e.effort, index: e.index })
    if (result.usage?.model === scope.model) {
      record({ kind: 'response-model-matched', agentId: e.agentId, responseModel: result.usage.model, index: e.index })
    } else if (result.usage?.model) {
      record({ kind: 'response-model-mismatch', agentId: e.agentId, responseModel: result.usage.model, index: e.index })
    }
    return result
  })
}
