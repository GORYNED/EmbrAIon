# Claude Code

The Claude Code adapter projects EmbrAIon roles and skills into Claude Code agent files.

Core agent access is projected through Claude Code-native `tools` allowlists. Read-only agents receive `Read`, `Grep`, and `Glob`; workspace-write agents additionally receive `Write`, `Edit`, and `Bash`. Claude Code or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Claude Code model catalog. Claude Code keeps ownership of its available models and default selection. Optional project routing overrides may pass arbitrary Claude Code-understood model selectors and settings without making them framework-level truth.

Canonical role, complexity, access, privacy, validation, and workflow policy remains in Core.

<sub>Last updated: 2026-09-25 17:51 UTC</sub>
