# Агенты проекта

Core уже предоставляет переиспользуемые roles: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher и Steward.

Используйте `.embraion/agents.yaml` только если репозиторию нужен **project-specific specialist** сверх generic roles.

## Пример

```yaml
agents:
  - id: domain-specialist
    title: Domain Specialist
    extends: reviewer
    purpose: Review project-specific domain behavior.
    access: read-only
    responsibilities:
      - focus review on project-specific domain contracts
    restrictions:
      - do not modify project files
    triggers:
      - domain-focused review
    outputs:
      - domain review findings
```

## Обязательные поля

- `id` — уникальный kebab-case project agent ID;
- `purpose` — краткая project-specific responsibility;
- `access` — `read-only` или `workspace-write`;
- `responsibilities` — одна или больше project-specific responsibilities.

## Опциональное наследование

Project agent может `extend` существующую non-Lead Core role.

EmbrAIon добавляет project-specific responsibilities/restrictions/triggers/outputs, но сохраняет inherited access boundary.

Project agent не может:

- shadow Core agent ID;
- extend Core `lead`;
- расширить inherited read-only role до writable access.

## Host projection

При установке проекта project agents генерируются в native host files:

```text
Codex          .codex/agents/<id>.toml
GitHub Copilot .github/agents/<id>.agent.md
Claude Code    .claude/agents/<id>.md
```

`embraion sync` без consuming project остаётся Core-only и не придумывает project specialists.

## Preview перед записью

```bash
embraion projection diff --host codex --destination . --component agents
```

Затем установите намеренно:

```bash
embraion install --host codex --destination . --component agents
```

Полный список полей — в [Файлах конфигурации проекта](project-files.md).
