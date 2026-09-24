# Project Knowledge

Project knowledge is factual context that belongs to the consuming repository rather than reusable EmbrAIon Core.

Typical examples:

- product architecture;
- domain terminology;
- hardware or platform constraints;
- supported compatibility contracts;
- source-of-truth locations;
- decisions that should survive across AI sessions.

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

A useful rule:

> If the fact is true because of this product, customer, repository, device, or domain, it probably belongs in project knowledge.

Reusable engineering procedures and universal EmbrAIon safety rules belong in Core instead.

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
