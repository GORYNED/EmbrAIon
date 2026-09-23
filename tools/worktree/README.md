# Worktree

This directory owns safe reusable Git worktree automation.

The generic contract is evidence-driven and fail-closed: preserve dirty, locked, active, divergent, ambiguous, or unproven state; isolate writable tasks; never fall back to stable main for unsafe execution.

Project-specific Git LFS hydration or Unity preflight logic is supplied by project overlays or optional tool extensions.

<sub>Last updated: 2026-09-23 18:11 UTC</sub>
