# Portable bundle

## Что это

Portable — **host-neutral capability bundle**, а не отдельный AI-клиент и не generic model/provider.

Он нужен, когда другой integration должен получить discoverable capabilities EmbrAIon без Codex-, Copilot- или Claude-specific files.

CLI host identifier остаётся `portable`.

## Установка

```bash
embraion install --host portable --destination vendor/embraion
```

## Generated structure

```text
vendor/embraion/
└── embraion/
    ├── plugin.json
    ├── catalog.yaml
    ├── skills/
    ├── knowledge/
    └── routing/
```

Generated files — projections. Каноническая project configuration остаётся в `.embraion/`.

## Для чего Portable

Portable подходит, когда:

- custom integration умеет потреблять host-neutral capability catalog;
- инструменту нужны EmbrAIon skills/knowledge/routing metadata без притворства Codex/Copilot/Claude Code;
- репозиторию нужен neutral bundle как integration boundary.

Portable **не означает**:

- portable installation CLI EmbrAIon;
- “bring your own model” сам по себе;
- provider-neutral API execution engine.

Для provider execution см. [Execution и провайдеры](../configuration/execution.md).

## Routing

Portable передаёт [канонический assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md), но не содержит native dispatch adapter, spawn tool или model runtime. Consuming integration отвечает за проверку возможностей execution host, применение resolved settings и evidence исполнения. Cross-host handoff требует свежих privacy/access checks по Core. Concrete deployment choices остаются в `.embraion/`.

Opt-in planner `embraion dispatch --native-surface` поддерживает `portable`; `--task-class` выбирает настроенный assignment route. `native-plan` содержит `status`, `arguments`, `definition-overrides`, `requirements`, `limitations` и `executed: false`. `prepared` означает static translation; `handoff-required` требует native loading/session step, а `capability-limitation` блокирует invocation до разрешения проблемы. Проверка active schema, effective configuration и eligibility всё ещё необходима. Portable всегда возвращает capability limitation без runtime arguments.

## Selective adoption

Portable представлен одним component `bundle`.

Preview:

```bash
embraion projection diff --host portable --destination vendor/embraion --component bundle
```

Intentional install:

```bash
embraion install --host portable --destination vendor/embraion --component bundle
```

## Verify

```bash
embraion doctor
embraion status
```

Перед reinstall используйте `embraion projection diff --host portable --destination vendor/embraion`.

## Дальнейшая настройка

См. [Файлы конфигурации проекта](../configuration/project-files.md) и [AI-хосты](index.md).
