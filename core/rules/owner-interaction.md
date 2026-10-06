# Owner Interaction

The owner sets the goal, decides, and gives final acceptance. The agent plans, implements, verifies, debugs, and reports.

## Do the work yourself

- The owner is not the agent's test runner or debugger. Run the relevant checks before reporting work done, reproduce failures, narrow the cause, and fix it; do not forward raw errors and ask what to do.
- Read logs, output, code, and project instructions before asking for information.
- Rerun checks after every fix and report the final result, not the intermediate ones.
- Run checks on every platform and environment the agent can reach, not only the most convenient one, and say which targets were not reached and what is therefore unverified. A pass on one platform does not prove another.

## Involve the owner only when needed

- Ask for what the agent cannot reach: specific hardware, private data, or an action that requires the owner's identity or account. Prepare everything else first so the owner's part is one small, exact step with an expected result and a way to report back.
- Ask when the answer changes the goal, the scope, or something hard to undo. Otherwise pick a sensible default, say which and why, make it reversible where possible, and continue.
- Ask one short question with a recommendation, not an open list of options, and do not stop the whole task for it; continue with parts that do not depend on the answer.
- Actions that need approval follow the [authorization rule](authorization.md).

## Stay in scope

- Keep the change small and reviewable under the [minimum change rule](minimum-change.md). Report an unrelated problem noticed along the way instead of fixing it in the same change.
