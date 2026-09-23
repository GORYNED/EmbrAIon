# Unity Reference Architecture

- Keep deterministic domain state independent of `UnityEngine` where practical.
- Keep Unity lifecycle and serialization concerns in Unity-facing components.
- Keep project-specific engineering knowledge under `knowledge/`.
- EmbrAIon Core remains upstream and must not be copied into project knowledge.
- Generated Codex, Copilot, Claude Code, and Portable projections are disposable outputs.
