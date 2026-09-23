# Worktree

This directory owns safe reusable Git worktree lifecycle automation.

## Lifecycle

created → active → review → merge-ready → merged → closed

Side states include `blocked`, `stale`, and `salvage`.

The lifecycle is evidence-driven and fail-closed. Automatic cleanup must preserve a worktree when it is dirty, locked, active, divergent, associated with unresolved review, contains unproven commits, or has ambiguous integration state.

## Operations

- **create** — create an isolated writable task workspace;
- **resume** — return a known safe workspace to active work;
- **pause** — preserve state without declaring completion;
- **review** — identify the candidate under review;
- **stale** — mark inactive state requiring inspection;
- **salvage** — preserve recoverable commits or files before cleanup;
- **close** — retire only after integration or explicit abandonment is proven;
- **gc** — remove only worktrees whose safety predicates are satisfied.

Project-specific hydration or platform preflight logic is supplied by project overlays or optional extensions.

`lifecycle.yaml` defines the canonical state transitions.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
