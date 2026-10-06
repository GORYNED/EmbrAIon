---
name: skill-authoring
description: Design or revise a reusable skill when observed task failures justify a bounded procedure, then compare it with a live baseline.
---

# Skill Authoring

Load for a proposed new skill, changed trigger, or behavioral rewrite of an existing skill. Skip for a local task instruction, a pure documentation correction, or a project fact that belongs in a Project Contract Slot or custom knowledge binding.

1. Name the recurring task, affected users, observed failure, and evidence source. Check nearby skills, rules, roles, workflows, and the catalog for overlap. Explain the distinct procedure and why a narrower edit to an existing capability is insufficient.
2. Write a short entry point with an explicit positive trigger and a near-miss exclusion. Keep detailed examples or references beside it only when progressive disclosure improves use. Preserve one canonical owner for policy, role responsibility, orchestration, project facts, and routing; link to those owners instead of copying them.
3. Create English and Russian positive and near-negative task prompts that differ by intent, not just keywords. Include composition cases with adjacent skills and cases where the candidate must stay unloaded. Keep evaluation prompts separate from the skill text.
4. Compare the live baseline with the candidate on the same representative tasks and environment. Repeat variable cases; inspect selection, actual task output, policy compliance, and regressions. Record the baseline and candidate artifacts, checks, failures, and uncertainty. A schema pass or a test that mirrors the wording of the skill is not evidence of improved behavior.
5. Revise only for observed failures and re-run affected cases. Avoid tuning to one prompt or making triggers so broad that every task loads the skill. Promote through the existing learning and review process when applicable.

Output: the scope and overlap decision, trigger/exclusion examples in both languages, links to reproducible baseline/candidate evidence, behavioral differences, known gaps, and the proposed catalog entry. Use the canonical project source, privacy, access, review, and routing contracts for every run.
