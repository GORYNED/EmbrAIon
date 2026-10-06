# Human Merge

The project's merge mode decides who merges a pull request. A project declares one mode; without a declaration the mode is `human-only`.

- `human-only`: agents stop after producing a reviewable pull request and completion evidence. A human merges.
- `owner-permission`: an agent may merge a pull request only when the owner has explicitly permitted merging that pull request, the required checks have passed on its final head, and the independent reviewer has confirmed that exact head. When any condition is missing, the agent stops as in `human-only`.

In every mode, automation never enables auto-merge and never bypasses the merge decision.
