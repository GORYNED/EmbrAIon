# Learning

`tools/learning/` owns privacy-safe continuous learning from engineering outcomes.

The learning system does not modify Core automatically. It records small structured candidates and promotes them only through the reviewed Learning workflow.

## Candidate lifecycle

observed → accumulating → proposed → approved or rejected → promoted

Typical evidence may include:

- repeated successful strategy;
- recurring failure mode;
- repeated manual correction;
- repeated routing mismatch;
- repeated validation or review finding.

Candidate records keep identifiers, counters, confidence, categories, and references to privacy-safe run IDs. They must not contain source code, prompts, diffs, credentials, raw reasoning, or protected implementation content.

`policy.yaml` defines default evidence and promotion gates.

<sub>Last updated: 2026-09-23 19:34 UTC</sub>
