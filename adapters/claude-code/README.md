# Claude Code

The Claude Code adapter projects EmbrAIon roles and skills into Claude Code agent files.

Core agent access is projected through Claude Code-native `tools` allowlists. Read-only agents receive `Read`, `Grep`, and `Glob`; workspace-write agents additionally receive `Write`, `Edit`, and `Bash`. Claude Code or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Claude Code model catalog. Claude Code keeps ownership of its available models and default selection. Optional project routing overrides may pass arbitrary Claude Code-understood model selectors and settings without making them framework-level truth.

The orchestration skill projection combines the [canonical assignment routing contract](../../core/skills/orchestration/SKILL.md) with [this host's native guidance](orchestration.md). Native capabilities and precedence depend on the active surface and installed schema; prepared settings must be applied and verified at invocation. Reusable role profiles remain model-neutral.

Canonical role, complexity, access, privacy, validation, and workflow policy remains in Core.

The opt-in `embraion dispatch --native-surface` planner supports `claude-agent` for this adapter and accepts `--task-class` for configured assignment routing. Its `native-plan` contains `status`, `arguments`, `definition-overrides`, `requirements`, `limitations`, and `executed: false`. A `prepared` result is static translation; `handoff-required` needs a supported native loading/session step, and `capability-limitation` prevents invocation until resolved. None proves native execution. Unsupported native options block planning until their application is established.

<sub>Last updated: 2026-09-29 01:14 UTC</sub>
