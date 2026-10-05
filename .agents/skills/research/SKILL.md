---
name: research
description: Investigate a bounded question using allowed sources, explicit evidence, and clear separation between fact and inference.
---

# Research

Use for a bounded factual question or an engineering decision with unresolved evidence. An ordinary factual question needs source-backed findings, not an implementation reuse comparison.

## Procedure

1. Freeze the question and allowed source scope.
2. Apply privacy and access policy before retrieval.
3. For an engineering implementation decision, first inspect relevant repository code, project contracts, consumers, tests, and installed dependencies within the allowed source scope. Compare compatible reuse, a bounded extension, and a new implementation against required behavior and ownership; a matching name alone does not establish fit. For other questions, prefer authoritative primary sources. Use external primary sources when material facts remain unresolved or current external facts require verification.
4. Record source-backed facts separately from inference.
5. Surface uncertainty, contradictions, and missing evidence. Narrow the next search to facts that could change the decision instead of repeatedly loading broad context.
6. Stop when evidence supports the next authorized step and remaining uncertainty cannot change it. Return concise findings, limits, and the recommended next step; for an implementation decision, state the evidence-based adopt, extend, or build choice.

## Guardrails

- Do not mutate repository or external state.
- Do not expand to unrelated research.
- Do not present inference as verified fact.
- Do not expose protected context to an ineligible source or provider.
