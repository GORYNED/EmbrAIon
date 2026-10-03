# EmbrAIon engineering entry point

For an engineering request, read `.claude/skills/orchestration/SKILL.md` before choosing the work plan. It contains the canonical Lead contract and Claude adapter guidance. Load other skills only when relevant. Concrete routing decisions belong to `.embraion/`; this rule does not define model choices.

Read the repository's `AGENTS.md` and applicable nested `AGENTS.md` files before working in their scope. Preserve any existing `CLAUDE.md` imports and project instructions. Do not assume Claude discovers `AGENTS.md` automatically.

At the start of a new Thread, after resuming, or when the assignment changes, establish the working directory, applicable instructions, project configuration, and current execution surface again. A Project overview, another Thread, or a previous agent's settings do not establish this Thread's routing state. Resolve every delegated assignment through the loaded orchestration contract before dispatch, including review and follow-up assignments.

Compare this worktree's framework pin and Git commit with the intended task baseline; a globally updated launcher does not update an old worktree. If `.embraion/claude-native.yaml` is present, inspect `embraion claude-native status` and prefer the exact startup-projected scoped type returned by dispatch. Confirm it is loaded in this Thread, invoke it without a model override, and retain available native evidence. Missing or stale profiles require a projection refresh and a new Thread or supported loader; another process's CLI authentication is not the current desktop session's authentication.

Keep evidence separate: files installed, instructions read, route resolved, native definition loaded, and effective model/effort verified. An installed projection or prepared dispatch proves neither loading nor execution. If the current surface cannot load or apply the required selection, report the limitation and follow the canonical handoff policy.
