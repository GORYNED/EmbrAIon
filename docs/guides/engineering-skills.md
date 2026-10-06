# Engineering Skills

EmbrAIon's Core includes short, conditional procedures for recurring engineering work. The catalog selects a skill when the task needs its procedure; a skill does not create a role, grant access, select a model, or override a project contract. Project-specific architecture, source authority, compatibility, persistence, and engineering workflow belong in the project's [knowledge slots](../configuration/project-files.md#embraionknowledgeyaml). Core [validation](../validation.md), review, privacy, and routing rules still govern the work.

| Skill | Load for | Usually skip for |
| --- | --- | --- |
| `skill-authoring` | A reusable skill or trigger change supported by observed failures | Local instructions or a documentation correction |
| `compatibility-migration` | Persisted shapes, stable IDs, public APIs, or consumer migrations | Verified private refactoring |
| `test-design` | A behavior, persistence, integration, or regression test strategy | Trivial reversible edits without behavior risk |
| `performance-investigation` | A measurable performance concern or target | Ordinary code changes without a performance question |
| `dependency-upgrade` | A requested or necessary exact-version upgrade | Unrelated feature work |
| `architecture-decision` | A durable decision on dependency direction, ownership, persisted format, platform, or a foundational dependency, recorded in the project's own decision-record format | Local implementation choices, renames, and documentation fixes |

Each procedure yields traceable outputs: the affected contract or risk, evidence sources, actions, fresh checks, and remaining limits. Load adjacent skills only when their separate concerns apply. For example, a dependency upgrade that changes a persisted format may also need `compatibility-migration`; an optimization needs a correctness check as well as comparable measurements. The [capability model](../capability-model.md) keeps skills distinct from agents, rules, and workflows.

`skill-authoring` requires behavioral evidence beyond a valid Markdown file. Compare a live baseline and candidate on English and Russian positive, near-negative, and composition tasks; repeat variable cases and inspect the work produced. Deterministic metadata and link checks protect structure, while behavioral evaluation shows whether the new procedure helps. Avoid broad triggers that load on unrelated work or test prompts that simply repeat the skill text.

These skill sources live under `core/skills/<id>/SKILL.md`. The canonical `core/catalog.yaml` entry is the discovery point for a Core skill. Installed host files are projections of those sources; a changed source only affects a host after the appropriate install or sync step and verification that the host loaded it. Commands and installation behavior depend on the framework version and host capabilities actually present in the project.
