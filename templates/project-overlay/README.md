# Project Overlay Template

Copy the `.embraion/` directory into a consuming repository and replace example values with project-specific paths and capabilities.

Project overlays may add domain agents, source classifications, compatibility contracts, validation impact rules, and stricter policy. They must not weaken Core hard rules.

The template includes disabled task housekeeping in `.embraion/project.yaml`. Explicitly
enable `housekeeping.on-task-start` and `housekeeping.remote-branches` only after reviewing
the [Core worktree workflow](../../core/workflows/worktree.md). Unregistered user or legacy
branches remain preserved; configuration cannot relax agent-ownership or recovery gates.

Spec Kit is recommended as an optional external capability for substantial specification-driven work; do not copy Spec Kit internals into the overlay unless the project intentionally manages its own upstream integration.

<sub>Last updated: 2026-10-04 01:28 UTC</sub>
