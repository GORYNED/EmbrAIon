# AI-хосты

EmbrAIon хранит один канонический Core и project contract, а затем проецирует нужные части в каждую поддерживаемую интеграцию.

!!! tip "Простыми словами"
    Правила проекта хранятся один раз. EmbrAIon записывает native agent/skill-файлы, которые ожидает используемый AI-клиент.

## Выберите путь

- **Использую один AI host:** установите его projection, остальной project contract храните в `.embraion/`.
- **Поддерживаю несколько hosts или custom integration:** используйте один canonical project contract и устанавливайте нужные projections, включая host-neutral Portable bundle, когда это уместно.

| Интеграция | Типичные generated locations | Что проецирует EmbrAIon |
| --- | --- | --- |
| Codex | `.codex/`, `.agents/skills/` | config, specialist agents, skills |
| GitHub Copilot | `.github/agents/`, `.github/skills/` | custom agents, skills |
| Claude Code | `.claude/agents/`, `.claude/skills/` | agent definitions, skills |
| Portable bundle | `embraion/` внутри выбранного destination | host-neutral capability bundle |

## Установка

```bash
embraion install --host codex --destination .
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

Для host-neutral bundle:

```bash
embraion install --host portable --destination vendor/embraion
```

## Существующая host configuration

Перед записью посмотрите diff:

```bash
embraion projection diff --host codex --destination .
```

Зрелые репозитории могут принять только выбранные components.

## Разговорная настройка проекта

Установка host и изменение project configuration — разные concerns.

Используйте [Разговорную настройку](../configuration/ai-hosts.md), когда хотите, чтобы AI в репозитории обновил knowledge, policy, deployments, routing, validation или project agents.

## Model selection

AI host владеет текущей доступностью моделей и default/automatic selection. EmbrAIon не содержит canonical model catalog.

## Enforcement отдельно

Установка host projection не устанавливает executable merge enforcement молча.
