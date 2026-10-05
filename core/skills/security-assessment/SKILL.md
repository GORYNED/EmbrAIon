---
name: security-assessment
description: Assess reachable threats across relevant trust boundaries with evidence, scoped mitigations, and explicit residual risk.
---

# Security Assessment

## Activation contract

Load when the requested change or assessment involves a relevant trust boundary, untrusted input reaching a dangerous operation, a privileged operation, or an access-control change. A filename or HTTP API in a diff alone is insufficient. Skip unrelated formatting, inert data, and ordinary local logic without a relevant threat flow. Existing security and integration hard rules apply independently of this skill. Stop when in-scope reachable flows have supported findings or a bounded no-finding conclusion, with missing evidence and residual risk stated. Return compact findings or a no-material-findings result and its coverage boundary.

## Procedure

1. Identify the in-scope asset, allowed sources, actor capability, and entry point. Inventory an external integration only when one is involved; never collect secret values.
2. Trace the entry point across its trust boundary to a reachable dangerous or privileged operation. Evaluate authorization, validation, containment, and existing controls for the relevant actor on that path. A theoretical sink without reachability does not establish an exploitable finding; a control after a completed return is ineffective on that path.
3. For each finding record: asset, entry point, trust boundary, reachable dangerous operation, existing control, evidence, mitigation, and residual risk. Explain realistic attacker actions, preconditions, and priority based on supported impact and exploitation conditions; do not assign a universal CVSS score.
4. Propose the smallest mitigation preserving the accepted contract and a reproducible permitted check that can falsify it. Distinguish source, isolated-test, and runtime proof. Do not execute candidate code without required isolation, use real credentials, or perform destructive or external exploitation to manufacture evidence.
5. Distinguish the presence of a trust boundary from a supported violation. For a guarded negative assessment, record the effective control, conditions and coverage without inventing a vulnerability. Missing runtime evidence proves neither exploitation nor safety.
6. Respect the requested output contract. Keep findings, evidence and residual risk distinct; a structured answer grants no additional reports, permissions or actions. Report prerequisites and unverified conditions; do not weaken hard policy, expand access or infer authority from the role.
