# GitHub Copilot

The GitHub Copilot adapter projects EmbrAIon roles and skills into Copilot-native project files.

Core agent access is projected through Copilot-native `tools` allowlists. Read-only agents request the `read`/`search` aliases; workspace-write agents additionally request `edit`/`execute`. These aliases filter tools that the active Copilot surface actually provides, so a requested capability such as repository content search is not a guarantee that every custom-subagent surface exposes a matching tool. GitHub or organization policy may further restrict access but EmbrAIon does not widen it.

Generated Copilot agents set `include-custom-instructions: true`. When Copilot runs them as custom subagents, this opts them into repository instructions such as `.github/copilot-instructions.md`, `AGENTS.md`, and `CLAUDE.md`. A host-level `--no-custom-instructions` choice still takes precedence.

Projected skills are root/session procedural capabilities. EmbrAIon does not assume that Copilot custom subagents automatically inherit root-loaded skills or expose the same callable skill loader.

EmbrAIon does not maintain a Copilot model catalog. Copilot keeps ownership of its available models and default/automatic selection. Optional project routing overrides may pass arbitrary Copilot-understood model selectors and settings without making them part of EmbrAIon Core.

Canonical role, complexity, access, privacy, validation, and workflow policy remains in Core.

<sub>Last updated: 2026-09-25 19:32 UTC</sub>
