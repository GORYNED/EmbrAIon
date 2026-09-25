# Project Knowledge

Project knowledge is factual context that belongs to the consuming repository rather than reusable EmbrAIon Core.

Typical examples:

- product architecture;
- domain terminology;
- hardware or platform constraints;
- supported compatibility contracts;
- source-of-truth locations;
- decisions that should survive across AI sessions.

## Core vs project knowledge

Keep reusable engineering behavior in Core and product-specific truth in the project.

| EmbrAIon Core | Project repository |
| --- | --- |
| roles | product facts |
| reusable skills | domain rules |
| model-agnostic routing | architecture |
| hard gates | compatibility and source-of-truth details |

A practical rule is:

> If a fact is true because of this product, customer, repository, device, or domain, it probably belongs in project knowledge.

Reusable engineering procedures and universal EmbrAIon safety rules belong in Core instead.

## Project Contract Slots

EmbrAIon provides seven canonical semantic slots for project-specific truth:

| Slot | Project-owned meaning |
| --- | --- |
| `constitution` | durable project governance and engineering principles |
| `architecture` | architecture, ownership boundaries, and dependency direction |
| `source-authority` | canonical sources, source-of-truth, vendor/protected ownership |
| `compatibility` | compatibility, migration, versioning, and schema constraints |
| `persistence` | persisted identities, serialization, storage, and recovery semantics |
| `engineering-workflow` | project-specific execution gates and delivery workflow |
| `specification` | requirements/specification system and artifact lifecycle |

The slots are built into EmbrAIon; the project supplies only its own file references.

Starting with EmbrAIon v0.10.0, the top-level `slots` key in `.embraion/knowledge.yaml` is framework-reserved for this contract. This is an intentional pre-1.0 breaking cleanup; do not use `slots` as an arbitrary custom knowledge ID.

```yaml
slots:
  constitution: .specify/memory/constitution.md
  architecture: docs/architecture/current.md
  source-authority: docs/references/project-sources.md
  compatibility: docs/compatibility.md
  persistence: docs/persistence.md
  engineering-workflow: .agents/skills/engineering-workflow/SKILL.md
  specification: .specify/integration.md
```

Unconfigured slots remain `null`. Projects do not need to invent placeholder documents just to fill every slot.

Each slot has framework-owned default task triggers. A structured binding may override `data-class`, `trust`, `roles`, or `triggers` exactly like an ordinary knowledge entry. Passing `triggers: []` intentionally makes the configured slot eligible without a task-term filter.

Inspect bindings with:

```bash
embraion context slots
```

Force a relevant configured slot into a context selection without depending on trigger matching:

```bash
embraion context build \
  --task "Review a persistence migration" \
  --role reviewer \
  --slot persistence \
  --data PRIVATE
```

Project/domain-specific knowledge that does not fit a reusable semantic slot remains an ordinary custom entry or scoped project instruction. The slot catalog is intentionally small so EmbrAIon stays generic.

## Keep knowledge in ordinary project files

A common layout is:

```text
knowledge/
├── project.md
├── architecture.md
└── compatibility.md
```

`.embraion/knowledge.yaml` references those files; it does not duplicate their contents.

Shortest form:

```yaml
project: knowledge/project.md
architecture: knowledge/architecture.md
```

Structured form:

```yaml
architecture:
  path: knowledge/architecture.md
  data-class: PRIVATE
  trust: project
  roles:
    - architect
    - lead
  triggers:
    - architecture
```

## When to create a knowledge file

Create project knowledge when a fact should remain available across AI sessions and belongs to the repository rather than to one transient task.

Do not put executable validation commands in knowledge files. Those belong in `.embraion/validation.yaml`. Knowledge can document why a compatibility or architecture constraint exists; validation defines the commands that prove it still holds.

## Context selection

Structured entries can declare:

- `data-class` — `PUBLIC`, `PRIVATE`, or `CONFIDENTIAL`;
- `trust` — `project`, `external`, or `generated`;
- `roles` — which roles are eligible to receive the knowledge;
- `triggers` — task terms that make the knowledge relevant.

Build a context selection record with:

```bash
embraion context build \
  --task "Review architecture boundaries" \
  --role architect \
  --data PRIVATE \
  --max-chars 20000
```

The runtime state stores provenance and hashes, not a second copy of the knowledge content.

## Verify

```bash
embraion doctor
```

EmbrAIon validates declared knowledge references.

For the complete schema, see [Project Configuration Files](project-files.md).
