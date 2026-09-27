# Codex

## Что это

Codex adapter проецирует host configuration EmbrAIon, Core/project agents и reusable skills в native-файлы Codex.

## Установка

```bash
embraion install --host codex --destination .
```

## Generated structure

```text
.codex/
├── config.toml
└── agents/
    ├── analyst.toml
    ├── architect.toml
    ├── reviewer.toml
    └── ...

.agents/
└── skills/
    ├── implementation/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Ownership config

Whole-file replacement остаётся default для component `config`:

```bash
embraion install --host codex --destination . --component config
```

Зрелый репозиторий может позволить EmbrAIon управлять только обязательными `[agents]` settings, сохраняя project-owned Codex config вроде MCP servers или дополнительных agent defaults:

```bash
embraion projection diff   --host codex   --destination .   --component config   --config-mode merge

embraion install   --host codex   --destination .   --component config   --config-mode merge
```

Merge mode записывает отмеченный EmbrAIon-managed block внутри `[agents]`, сохраняет остальные `[agents]` keys и non-managed TOML tables и fail-closed при invalid TOML или ambiguous managed markers. `--force` не обходит unsafe merge; whole-file `replace` используйте только при явно намеренной замене.

## Routing

Codex остаётся authoritative для доступных моделей и automatic/default selection. Без project override EmbrAIon разрешает routing как `host-default`.

Optional Codex model, effort и host-specific settings принадлежат только `overrides.codex` в `.embraion/routing.yaml`.

Проверить resolution без вызова модели:

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

## Selective adoption

Codex поддерживает components `config`, `agents` и `skills`. Зрелые репозитории могут выбрать только нужные:

```bash
embraion install --host codex --destination . --component skills
embraion install --host codex --destination . --component agents --component skills
```

Preview:

```bash
embraion projection diff --host codex --destination .
```

## Verify

```bash
embraion doctor
embraion status
embraion projection verify --host codex --destination .
```

`projection verify` — fail-closed CI form projection comparison: non-zero, если любой selected generated file нужно создать/обновить, есть conflict или obsolete managed output.

Для partial-owned config используйте тот же mode:

```bash
embraion projection verify   --host codex   --destination .   --component config   --config-mode merge
```

`status` показывает detected host projections. `projection diff` — explanatory preview, `projection verify` — strict gate.

## Дальнейшая настройка

См. [Разговорную настройку](../configuration/ai-hosts.md) и [Подключение существующего репозитория](../getting-started/existing-repository.md).
