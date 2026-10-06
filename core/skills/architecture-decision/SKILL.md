---
name: architecture-decision
description: Record a durable architecture decision in the project's own decision-record format, or supersede an earlier record. Use when a decision changes dependency direction, ownership, a persisted format, a platform, or a foundational dependency; skip local implementation choices.
---

# Architecture Decision

Load when a task makes or changes a decision that is costly to reverse or easy to misunderstand later: dependency direction, ownership between components or repositories, a persisted format or stable identifier, a time or synchronization contract, a platform, build or deployment strategy, an authoritative validation contract, or a foundational dependency. Skip local implementation choices, renames and documentation fixes; describe those in the change itself.

1. Find the project's decision records before writing: a configured architecture or decision binding, an existing decisions folder, its index, its template, and its numbering and status rules. Follow them exactly. When the project has no decision records and the owner did not ask to start them, put the decision in the change description and propose a location instead of inventing a format.
2. Read the existing records on the same subject. Never rewrite the decision text of an accepted record. To change it, write a new record that says what changes and why, then mark the old record superseded and link the two records both ways in their metadata. Keep the old record in place.
3. Write the new record from the project's template with the next unused number, never reusing one. Cover the context with observed facts separated from assumptions, the decision with its scope and owner, the consequences including costs and follow-up work, and the credible alternatives with the reason each was not chosen. Add verification and rollout or compatibility notes when the template has them. Use the status the project's lifecycle gives a new record; a record is accepted only through the owner or the project's process.
4. In the same change, add the record to the index. Update current-state documentation only for what is already true; a decision whose implementation has not landed does not change current-state text. Link the record from the instructions or documents whose rules depend on it.
5. Report the record path and status, any record it supersedes, and the documents updated.
