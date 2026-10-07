# Знания проекта

Project knowledge — это фактический контекст, который принадлежит конкретному репозиторию, а не переиспользуемому EmbrAIon Core.

Типичные примеры:

- архитектура продукта;
- domain terminology;
- hardware/platform constraints;
- compatibility contracts;
- source-of-truth locations;
- решения, которые должны переживать новые AI-сессии.

## Core vs project knowledge

Переиспользуемое инженерное поведение храните в Core, а product-specific truth — в проекте.

| EmbrAIon Core | Репозиторий проекта |
| --- | --- |
| roles | product facts |
| reusable skills | domain rules |
| model-agnostic routing | architecture |
| hard gates | compatibility и source-of-truth details |

Практическое правило:

> Если факт является правдой именно из-за этого продукта, клиента, репозитория, устройства или domain — скорее всего, это project knowledge.

Reusable engineering procedures и универсальные safety rules EmbrAIon должны оставаться в Core.

## Project Contract Slots

EmbrAIon предоставляет девять канонических semantic slots для project-specific truth:

| Slot | Значение, которым владеет проект |
| --- | --- |
| `constitution` | долгосрочные governance и engineering principles |
| `architecture` | architecture, ownership boundaries, dependency direction |
| `source-authority` | canonical sources, source of truth, vendor/protected ownership |
| `compatibility` | compatibility, migration, versioning и schema constraints |
| `persistence` | persisted identities, serialization, storage и recovery semantics |
| `engineering-workflow` | project-specific execution gates и delivery workflow |
| `specification` | requirements/specification system и artifact lifecycle |
| `decisions` | папка записей об архитектурных решениях; см. [Записи об архитектурных решениях](decisions.md) |
| `deferred-tasks` | список отложенных задач и follow-ups; [правило owner interaction](https://github.com/GORYNED/EmbrAIon/blob/main/core/rules/owner-interaction.md) читает его в начале задачи |

Slots встроены в EmbrAIon; проект предоставляет только ссылки на свои файлы. Исключение — slot `decisions`: он связывает папку, которую `embraion context` не загружает как текст.

Начиная с EmbrAIon v0.10.0 top-level `slots` в `.embraion/knowledge.yaml` зарезервирован framework. Это намеренная pre-1.0 cleanup, а не compatibility shim для произвольного старого knowledge ID с именем `slots`.

```yaml
slots:
  constitution: .specify/memory/constitution.md
  architecture: docs/architecture/current.md
  source-authority: docs/references/project-sources.md
  compatibility: docs/compatibility.md
  persistence: docs/persistence.md
  engineering-workflow: .agents/skills/engineering-workflow/SKILL.md
  specification: .specify/integration.md
  decisions: docs/architecture/decisions
  deferred-tasks: docs/engineering/follow-ups.md
```

Ненастроенные slots остаются `null`. Не нужно создавать пустые документы только ради заполнения списка.

Каждый slot имеет framework-owned default task triggers. Structured binding может переопределить `data-class`, `trust`, `roles` или `triggers` так же, как обычная knowledge entry. `triggers: []` намеренно делает slot eligible без task-term filter.

Посмотреть bindings:

```bash
embraion context slots
```

Принудительно включить relevant slot в context selection:

```bash
embraion context build   --task "Review a persistence migration"   --role reviewer   --slot persistence   --data PRIVATE
```

Domain-specific knowledge, которое не подходит под canonical slot, остаётся обычной custom entry или scoped project instruction. Каталог slots намеренно маленький, чтобы EmbrAIon оставался generic.

## Храните knowledge в обычных файлах проекта

Обычная структура:

```text
knowledge/
├── project.md
├── architecture.md
└── compatibility.md
```

`.embraion/knowledge.yaml` ссылается на эти файлы, а не дублирует их содержимое.

Короткая форма:

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

## Когда создавать knowledge file

Создавайте project knowledge, когда факт должен сохраняться между AI-сессиями и принадлежит репозиторию, а не одной временной задаче.

Не кладите executable validation commands в knowledge files. Они принадлежат `.embraion/validation.yaml`. Knowledge объясняет, почему существует constraint; validation определяет, какой командой доказать, что он соблюдён.

## Context selection

Structured entries могут задавать:

- `data-class` — `PUBLIC`, `PRIVATE` или `CONFIDENTIAL`;
- `trust` — `project`, `external` или `generated`;
- `roles` — какие roles могут получить knowledge;
- `triggers` — task terms, делающие knowledge релевантным.

Построить context selection record:

```bash
embraion context build   --task "Review architecture boundaries"   --role architect   --data PRIVATE   --max-chars 20000
```

Runtime state сохраняет provenance и hashes, а не вторую копию knowledge content.

## Проверка

```bash
embraion doctor
```

EmbrAIon проверяет объявленные knowledge references.

Полная schema описана в [Файлах конфигурации проекта](project-files.md).
