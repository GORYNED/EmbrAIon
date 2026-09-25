# GitHub Copilot

The GitHub Copilot adapter projects EmbrAIon roles and skills into Copilot-native project files.

Core agent access is projected through Copilot-native `tools` allowlists. Read-only agents receive read/search tools; workspace-write agents receive read/search/edit/execute tools. GitHub or organization policy may further restrict access but EmbrAIon does not widen it.

EmbrAIon does not maintain a Copilot model catalog. Copilot keeps ownership of its available models and default/automatic selection. Optional project routing overrides may pass arbitrary Copilot-understood model selectors and settings without making them part of EmbrAIon Core.

Canonical role, complexity, access, privacy, validation, and workflow policy remains in Core.

<sub>Last updated: 2026-09-25 17:51 UTC</sub>
