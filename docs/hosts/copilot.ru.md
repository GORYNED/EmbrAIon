# GitHub Copilot

## Что это

GitHub Copilot adapter проецирует EmbrAIon Core/project agents и reusable skills в repository-native locations Copilot.

## Установка

```bash
embraion install --host copilot --destination .
```

## Generated structure

```text
.github/
├── agents/
│   ├── analyst.agent.md
│   ├── architect.agent.md
│   ├── reviewer.agent.md
│   └── ...
└── skills/
    ├── implementation/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Delivery semantics

Generated Copilot agent profiles включают repository instructions через `include-custom-instructions: true`. Это важно, когда Copilot вызывает profile как custom subagent: repository instruction files не наследуются custom subagents по умолчанию.

Host всё ещё может глобально отключить repository instructions, а host-level settings имеют приоритет над projection.

Generated `tools` — allowlist инструментов, доступных на активной Copilot surface. EmbrAIon может запрашивать aliases `read`, `search`, `edit`, `execute`, но не обещает, что host реально предоставляет каждый alias в каждом custom-subagent context.

Skills в `.github/skills/` проецируются как root/session procedural capabilities. Adapter не обещает автоматическое inheritance этих skills каждым custom subagent, пока GitHub не предоставляет такой contract и EmbrAIon явно его не конфигурирует.

## Routing

GitHub Copilot authoritative для моделей/options текущего аккаунта. EmbrAIon не поддерживает Copilot model catalog.

Optional selectors/options принадлежат только `overrides.copilot` в `.embraion/routing.yaml`.

```bash
embraion route --host copilot --route-class substantial --data PRIVATE
```

## Selective adoption

Copilot поддерживает `agents` и `skills` components:

```bash
embraion install --host copilot --destination . --component skills
embraion install --host copilot --destination . --component agents --component skills
```

Preview:

```bash
embraion projection diff --host copilot --destination .
```

## Verify

```bash
embraion doctor
embraion status
```

Перед reinstall в репозиторий, уже владеющий `.github/` AI configuration, используйте `embraion projection diff --host copilot --destination .`.

## Дальнейшая настройка

См. [Разговорную настройку](../configuration/ai-hosts.md) и [Подключение существующего репозитория](../getting-started/existing-repository.md).
