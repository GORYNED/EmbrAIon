# Portable

The Portable adapter packages canonical EmbrAIon capabilities into a host-neutral installable bundle.

It is not another AI host. It exists so the same canonical Core can be packaged without tying the bundle to Codex, Copilot, Claude Code, or a specific provider.

Responsibilities:

- include discoverable skills;
- include shared knowledge and routing metadata;
- expose capability metadata;
- preserve one canonical source of truth in Core;
- remain suitable as an interchange/installable bundle.

The bundle includes the [canonical orchestration contract](../../core/skills/orchestration/SKILL.md), without a native dispatch adapter. A consuming integration must prove its execution capabilities, apply resolved settings, and satisfy the Core handoff checks. Portable has no spawn tool or model runtime.

Generated Portable output is a projection, never the canonical policy source.

The opt-in `embraion dispatch --native-surface` planner supports `portable` for this adapter and accepts `--task-class` for configured assignment routing. Its `native-plan` contains `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. A `prepared` result is static translation; `handoff-required` needs a supported native loading/session step, and `capability-limitation` prevents invocation until resolved. None proves native execution. Unsupported native options block planning until their application is established. Portable always reports a capability limitation and supplies no runtime arguments.

<sub>Last updated: 2026-09-29 01:14 UTC</sub>
