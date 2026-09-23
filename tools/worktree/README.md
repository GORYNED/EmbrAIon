# Worktree

EmbrAIon provides conservative worktree operations:

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree salvage /path/to/worktree
```

GC is dry-run by default. A candidate must be clean, unlocked, not the active/main worktree, and directly proven integrated into the configured base.

Ambiguous or squash-only integration is preserved rather than guessed. Salvage stores patches and copies untracked files before manual recovery work.

<sub>Last updated: 2026-09-23 20:05 UTC</sub>
