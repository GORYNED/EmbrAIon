# Claude Mods capability probe

This optional plugin tests whether a current Claude Code Mods build can load an EmbrAIon `claude-agent` scoped definition and expose native model and effort evidence. It is an experiment, not an installed production hook or a router. Loading the plugin only adds `/embraion-probe`; it does not register or spawn an agent by itself.

The probe accepts an unexecuted `native-plan` with `status: handoff-required`, a `scoped-definition`, and matching `arguments.subagent_type`. It requires a versioned `claude-...` model selector and an explicit effort level in both the definition and overrides. It rejects plain aliases, inheritance, missing effort, extra native fields, and mismatches. Its selector check does not assert model availability in the installed host. It reads one local JSON file only when asked, and reports metadata without prompt, result, or file contents.

With a Claude Code build that enables function hooks, from this repository run:

```text
claude --plugin-dir adapters/claude-code/mods-probe
```

In that interactive session, run `/embraion-probe load <local-plan.json>`, using a single local path without spaces. The JSON file contains the `native-plan` object itself. The command returns the plugin-qualified type, for example `embraion-mods-probe:embraion-worker-abc123`; Claude's Mods registration namespaces the plan's unqualified `arguments.subagent_type`. Then explicitly ask Claude to invoke its native `Agent` tool with that qualified `subagent_type` and a bounded task prompt. Run `/embraion-probe status` afterward. A separate new session is needed to probe another plan.

`status` distinguishes registration, spawn start, the model and effort observed in the `turn.step` request, and any responding model reported in usage for the same agent ID. Its `routeEvidence` stays `unverified` without an observed step; it reports a `mismatch` on conflicting evidence. `step-request-observed` and `response-model-corroborated-effort-request-observed` describe the evidence available, not a final assertion about effective effort. A wrong model override or fork is denied before the target spawn. If a targeted step is identified and presents a different model or effort, the hook stops it before calling the model. Claude Code or another plugin may still reject or alter a registration or spawn. A mismatch learned after a start or response cannot undo that work; the probe blocks later identified steps and reports the mismatch.

The published Mods declaration notes that a plugin's own `$.agent.spawn` can bypass its own hooks. This probe deliberately has no such call. It observes native model-origin Agent invocations. It does not establish project privacy classification, effective file permissions, tool availability, or a successful completed assignment. Those remain required checks under EmbrAIon's routing contract. Claude Mods is early access, and this plugin must be tested against the installed build before relying on its status.

Local mock checks (Node 18 or newer): `node adapters/claude-code/mods-probe/hooks/register.test.mjs`. In a live build, use `claude plugin test adapters/claude-code/mods-probe` if supported and inspect the installed `/plugin-types` declaration. The source was prepared against Anthropic's published `mods/types/claude-code.d.ts` from Claude Code 2.1.277 and the published Mods guide; this workspace has no `claude` executable, so live loading and execution remain unverified.

<sub>Last updated: 2026-10-03 01:04 UTC</sub>
