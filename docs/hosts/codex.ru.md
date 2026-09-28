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
    ├── orchestration/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Обычные инженерные запросы

Просите результат обычными словами: «Добавь retry при ошибке соединения». Не нужно называть Lead, отдельно просить делегирование или выбирать специалистов. Проекция `config` записывает orchestration guidance в корневой Codex `developer_instructions`, используя [каноническую роль Lead](https://github.com/GORYNED/EmbrAIon/blob/main/core/agents/lead.yaml) и [Codex orchestration adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/codex/orchestration.md).

Lead выполняет тривиальную работу напрямую и сам выбирает минимальный полезный набор ролей, если специалисты улучшают результат. Он ограничивает задания, безопасно распараллеливает независимую работу, собирает свежую соразмерную validation и получает независимый read-only review существенной реализации, когда этого требует policy. Lead объединяет результаты и сохраняет окончательное право приёмки. Пустой project `agents: []` не добавляет специалистов, но сохраняет Core roles и Lead orchestration.

Codex должен загрузить project config и доверять ему. Возможности host, permissions, native limits и инструкции более высокого приоритета продолжают действовать. Generated instructions направляют orchestration; static TOML сам по себе не гарантирует делегирование и не обеспечивает исполняемую validation или review.

Component `skills` также содержит canonical `orchestration` skill с generated Core Lead contract. Copilot, Claude Code и Portable projections получают тот же skill-level guidance; загрузку skill выбирает host. Корневой Codex `developer_instructions` дополнительно передаёт guidance без зависимости от выбора skill.

## Ownership config

Whole-file replacement остаётся default для component `config`:

```bash
embraion install --host codex --destination . --component config
```

Зрелый репозиторий может позволить EmbrAIon управлять orchestration subsection и обязательными `[agents]` settings, сохраняя project-owned Codex config вроде MCP servers или дополнительных agent defaults:

```bash
embraion projection diff   --host codex   --destination .   --component config   --config-mode merge

embraion install   --host codex   --destination .   --component config   --config-mode merge
```

Merge mode разбирает TOML через `tomlkit` и сохраняет пользовательскую конфигурацию. В разобранной корневой строке `developer_instructions` он создаёт или обновляет только subsection между `# >>> EmbrAIon managed: orchestration` и `# <<< EmbrAIon managed: orchestration`. Пользовательский текст вне subsection сохраняется. В `[agents]` он управляет `enabled = true` и `max_concurrent_threads_per_session = 3` с существующими comment markers, сохраняя остальные options, tables, comments и пользовательские `default_subagent_model` / `default_subagent_reasoning_effort`. Invalid TOML, malformed, duplicate или ambiguous managed markers приводят к fail-closed даже с `--force`; whole-file `replace` используйте только при явно намеренной замене.

Для managed-настроек agents нужна одна явная таблица `[agents]`. Inline, dotted-only или out-of-order представления без этой границы ownership отклоняются без изменений; перед merge mode нормализуйте таблицу.

## Routing

Codex остаётся authoritative для доступных моделей и automatic/default selection. Без project override EmbrAIon разрешает routing как `host-default`.

Optional Codex model, effort и host-specific settings принадлежат только `overrides.codex` в `.embraion/routing.yaml`.

Перед каждым native spawn Lead классифицирует конкретное задание и запрашивает project resolver с role, route class, data class и access mode либо configured task class. Явные resolved model/effort он передаёт через поддерживаемые spawn parameters. Generated specialist files не содержат model/effort: role-file overrides имели бы приоритет над явным spawn choice. Результат `host-default` использует Codex subagent defaults или inheritance, включая сохранённые пользовательские defaults. Static TOML не может запрашивать routing перед каждым spawn; если host не умеет применить обязательный выбор, Lead сообщает об ограничении и разрешает его до dispatch. Роль не означает фиксированную модель или расширенный access.

Настройки и precedence host описаны в официальных [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference) и [subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

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
