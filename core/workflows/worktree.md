# Worktree

Independent writable tasks should use isolated task worktrees when the host repository supports them.

Cleanup is fail-closed: preserve dirty, locked, active, divergent, ambiguous, or unproven worktrees. Never use a stable main checkout as an unsafe fallback runtime.

Repository-specific requirements such as Git LFS hydration remain project or tool configuration, not universal Core policy.
