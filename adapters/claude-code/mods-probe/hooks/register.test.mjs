import assert from 'node:assert/strict'
import { test } from 'node:test'
import { register, validatePlan } from './register.js'

const definition = {
  name: 'embraion-worker-test', description: 'One scoped task', prompt: 'Work carefully.',
  tools: ['Read', 'Grep'], model: 'claude-sonnet-4-5-20250929', effort: 'high',
}
const plan = () => ({
  surface: 'claude-agent', status: 'handoff-required', executed: false,
  arguments: { subagent_type: definition.name },
  'definition-overrides': { model: definition.model, effort: definition.effort },
  'scoped-definition': { ...definition },
})

function harness() {
  const hooks = new Map()
  const calls = { registered: [], spawnNext: 0, stepNext: 0 }
  const engine = {
    command: { register: async spec => { calls.registered.push(spec); return { command: spec.name } } },
    fs: { read: async () => JSON.stringify(plan()) },
    agent: {
      register: async spec => ({ agent: `embraion-mods-probe:${spec.name}` }),
      list: async () => [{ id: 'agent-1', type: `embraion-mods-probe:${definition.name}` }],
    },
  }
  register((name, matcher, handler) => hooks.set(name, handler ?? matcher))
  const command = async args => hooks.get('command.run')(engine, { args })
  const spawn = async (input, result = { agentId: 'agent-1', model: definition.model }) => hooks.get('agent.spawn')(engine, input, async () => {
    calls.spawnNext++
    return result
  })
  const step = async (input, responseModel = null) => {
    const stream = hooks.get('turn.step')(engine, input, async function* () {
      calls.stepNext++
      yield { kind: 'text', text: 'hidden response' }
      return { turnId: input.turnId, index: input.index, answer: 'hidden response', toolUses: [], stopReason: 'end_turn',
        usage: responseModel ? { model: responseModel } : null }
    })
    const chunks = []
    let item = await stream.next()
    while (!item.done) { chunks.push(item.value); item = await stream.next() }
    return { chunks, result: item.value }
  }
  return { hooks, calls, engine, command, spawn, step }
}

test('accepts only an exact scoped definition with explicit full model and effort', () => {
  assert.equal(validatePlan(plan()).name, definition.name)
  const unknownFamily = plan()
  unknownFamily['scoped-definition'].model = 'claude-fable-5-1'
  unknownFamily['definition-overrides'].model = 'claude-fable-5-1'
  assert.equal(validatePlan(unknownFamily).model, 'claude-fable-5-1')
  for (const mutate of [
    p => { p.arguments.subagent_type = 'other' },
    p => { p.executed = true },
    p => { p['definition-overrides'].model = 'other' },
    p => { p['scoped-definition'].model = 'sonnet' },
    p => { delete p['scoped-definition'].effort },
  ]) {
    const bad = plan()
    mutate(bad)
    assert.throws(() => validatePlan(bad))
  }
})

test('registration is opt-in and does not itself spawn or claim execution', async () => {
  const h = harness()
  await h.hooks.get('session.start')(h.engine, {}, async () => ({ cwd: '/work' }))
  assert.equal(h.calls.registered.length, 1)
  assert.equal(h.calls.spawnNext, 0)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence, 'unverified')
  assert.match((await h.command('load plan.json')).text, /Registered embraion-mods-probe:/)
  assert.equal(h.calls.spawnNext, 0)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence, 'unverified')
})

test('rejects a different model before spawn and missing effort before the model step', async () => {
  const h = harness()
  await h.command('load plan.json')
  const target = `embraion-mods-probe:${definition.name}`
  const denied = await h.spawn({ subagentType: target, model: 'claude-other', fork: false })
  assert.match(denied.deny, /exact model/)
  assert.equal(h.calls.spawnNext, 0)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence, 'mismatch')
  await h.spawn({ subagentType: target, fork: false })
  const blocked = await h.step({ agentId: 'agent-1', model: definition.model, turnId: 'turn-1', index: 0, messageCount: 1 })
  assert.equal(blocked.chunks.length, 0)
  assert.equal(h.calls.stepNext, 0)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence, 'mismatch')
})

test('exact observed model and effort are linked to the started native agent', async () => {
  const h = harness()
  await h.command('load plan.json')
  await h.spawn({ subagentType: `embraion-mods-probe:${definition.name}`, fork: false })
  const outcome = await h.step({ agentId: 'agent-1', model: definition.model,
    effort: definition.effort, turnId: 'turn-1', index: 0, messageCount: 1 })
  assert.equal(outcome.chunks.length, 1)
  assert.equal(h.calls.stepNext, 1)
  const status = JSON.parse((await h.command('status')).text)
  assert.equal(status.routeEvidence, 'step-request-observed')
  assert.doesNotMatch(JSON.stringify(status), /Work carefully|hidden response/)
})

test('started ID remains identifiable without a list row and response model corroborates', async () => {
  const h = harness()
  await h.command('load plan.json')
  await h.spawn({ subagentType: `embraion-mods-probe:${definition.name}`, fork: false })
  h.engine.agent.list = async () => []
  await h.step({ agentId: 'agent-1', model: definition.model,
    effort: definition.effort, turnId: 'turn-1', index: 0, messageCount: 1 }, definition.model)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence,
    'response-model-corroborated-effort-request-observed')
})

test('post-start model mismatch blocks later steps for the known agent ID', async () => {
  const h = harness()
  await h.command('load plan.json')
  await h.spawn({ subagentType: `embraion-mods-probe:${definition.name}`, fork: false },
    { agentId: 'agent-1', model: 'claude-other-5-1' })
  h.engine.agent.list = async () => []
  const blocked = await h.step({ agentId: 'agent-1', model: definition.model,
    effort: definition.effort, turnId: 'turn-1', index: 1, messageCount: 1 })
  assert.equal(blocked.chunks.length, 0)
  assert.equal(h.calls.stepNext, 0)
  assert.equal(JSON.parse((await h.command('status')).text).routeEvidence, 'mismatch')
})
