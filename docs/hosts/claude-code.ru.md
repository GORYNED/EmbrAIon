# Claude Code

## Что это

Claude Code adapter проецирует EmbrAIon Core/project agents и reusable skills в repository-native files Claude Code.

## Установка

```bash
embraion install --host claude-code --destination .
```

## Generated structure

```text
.claude/
├── agents/
│   ├── analyst.md
│   ├── architect.md
│   ├── reviewer.md
│   └── ...
└── skills/
    ├── implementation/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Routing

Claude Code authoritative для доступных моделей и default selection. EmbrAIon не содержит Claude Code model catalog.

Optional selectors/options принадлежат только `overrides.claude-code` в `.embraion/routing.yaml`.

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

## Selective adoption

Claude Code поддерживает `agents` и `skills` independently:

```bash
embraion install --host claude-code --destination . --component skills
embraion install --host claude-code --destination . --component agents --component skills
```

Preview:

```bash
embraion projection diff --host claude-code --destination .
```

## Verify

```bash
embraion doctor
embraion status
```

Если `.claude/` уже содержит project-owned configuration, сначала используйте `projection diff`.

## Дальнейшая настройка

См. [Разговорную настройку](../configuration/ai-hosts.md) и [Подключение существующего репозитория](../getting-started/existing-repository.md).
