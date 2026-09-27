# Архитектура

## Слои

1. **Core** — переиспользуемые правила, роли, skills, workflows, routing/execution contracts.
2. **Adapters** — интеграция с AI hosts и transport/provider surfaces.
3. **Tools** — CLI, validation, security, worktree, evidence, execution, pricing и диагностика.
4. **Project Overlay** — проектные факты и настройки в `.embraion/`.
5. **External capabilities** — необязательные внешние системы и интеграции.
6. **Evidence** — тесты, validation records, reviews, evals и отчёты.

## Механизмы vs факты проекта

| EmbrAIon Core | Проект |
| --- | --- |
| Core roles и skills | архитектура и domain knowledge |
| route/execution contracts | deployments и routing preferences |
| generic privacy/security mechanics | protected paths и project policy |
| validation/review mechanics | реальные команды validation |
| host projections | project-specific agents |
| generic execution/fallback/health | execution bindings, credential references, pricing sources |

Проект может делать правила строже, но не должен молча ослаблять hard gates Core.

## Prompt не проходит через обязательный proxy

Обычный поток:

```text
пользователь
  ↓
Codex / Copilot / Claude Code
  ↓
host-native EmbrAIon projections
+
.embraion/ проекта
  ↓
работа
  ↓
validation → review → evidence → human merge
```

EmbrAIon не стоит перед host как обязательный перехватчик prompt.

## Instruction vs deterministic enforcement

| Surface | Что это |
| --- | --- |
| agents / skills projections | инструкции AI host |
| `route` | детерминированное разрешение routing contract |
| `dispatch` | bounded execution plan |
| host-native работа | выполняет AI host |
| `execute` | реальное provider-neutral выполнение |
| `validation run` | реальные project commands |
| `enforcement check` | детерминированный gate |

Это различие важно: текстовая инструкция не равна исполняемому security boundary.

## Model ownership

Core классифицирует работу по стабильным route classes. EmbrAIon не хранит глобальный каталог актуальных моделей.

По умолчанию конкретную модель выбирает host. Проект может явно настроить deployment/routing, не расширяя privacy/access/review границы.
