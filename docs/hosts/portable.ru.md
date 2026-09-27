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

Portable несёт host-neutral routing capability data, но не является execution host. Integration, consuming bundle, отвечает за model availability и execution.

Project-owned routing overrides остаются в `.embraion/routing.yaml` и не превращают Portable в model registry.

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
