# Codex

## Project Bootstrap

Проецируемый канонический Core skill `project-bootstrap` поддерживает «Настрой EmbrAIon для этого проекта». Установите component `skills` и используйте его в активной сессии; trust, permissions и загрузка skills определяются хостом. Lead изучает истину репозитория, сохраняет настройки, находит реальную validation и оставляет routing необязательным. См. [Project Bootstrap](../configuration/bootstrap.md).

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
    ├── project-bootstrap/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Обычные инженерные запросы

Просите результат обычными словами: «Добавь retry при ошибке соединения». Не нужно называть Lead, отдельно просить делегирование или выбирать специалистов. Проекция `config` записывает orchestration guidance в корневой Codex `developer_instructions`, используя [каноническую роль Lead](https://github.com/GORYNED/EmbrAIon/blob/main/core/agents/lead.yaml) и [Codex orchestration adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/codex/orchestration.md).

Lead выполняет тривиальную работу напрямую и сам выбирает минимальный полезный набор ролей, если специалисты улучшают результат. Он ограничивает задания, безопасно распараллеливает независимую работу, собирает свежую соразмерную validation и получает независимый read-only review существенной реализации, когда этого требует policy. Lead объединяет результаты и сохраняет окончательное право приёмки. Пустой project `agents: []` не добавляет специалистов, но сохраняет Core roles и Lead orchestration.

Codex должен загрузить project config и доверять ему. Возможности host, permissions, native limits и инструкции более высокого приоритета продолжают действовать. Generated instructions направляют orchestration; static TOML сам по себе не гарантирует делегирование и не обеспечивает исполняемую validation или review.

Component `skills` также содержит canonical `orchestration` skill с generated Core Lead contract. Copilot и Claude Code skill projections включают Core contract и собственное native guidance; Portable включает только canonical contract. Загрузку skill выбирает host. Корневой Codex `developer_instructions` дополнительно передаёт guidance без зависимости от выбора skill.

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

Применяйте [канонический assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) перед каждым новым или повторно используемым заданием. Core определяет classification, resolution, reuse, evidence и cross-host handoff со свежими privacy/access checks; [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/codex/orchestration.md) определяет механизмы конкретного host. Concrete deployment choices принадлежат `.embraion/`; generated specialist profiles остаются model-neutral.

При подтверждённой схеме `collaboration.spawn_agent` передавайте role/model/effort независимо как `agent_type`/`model`/`reasoning_effort`. Явная model или effort требует `fork_turns='none'` либо ограниченной положительной числовой строки; full-history fork не принимает эти overrides. Follow-up/message tools не меняют их. Model/effort в custom role file может переопределить spawn settings: проверяйте загруженное определение и effective settings. Имена tools и поля fork зависят от surface.

Обязательные settings нельзя молча заменить, ограничить cap или унаследовать. Неизвестная surface, schema или options — capability limitation, требующая разрешения по Core. Документация проверена 2026-09-29; ссылки на официальные источники находятся в native adapter. Проверяйте installed schema, precedence и effective settings при invocation. Подготовка маршрута ещё не означает execution.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

Opt-in planner `embraion dispatch --native-surface` поддерживает `codex-native`; `--task-class` выбирает настроенный assignment route. `native-plan` содержит `status`, `arguments`, `definition-overrides`, `requirements`, `limitations` и `executed: false`. `prepared` означает static translation; `handoff-required` требует native loading/session step, а `capability-limitation` блокирует invocation до разрешения проблемы. Проверка active schema, effective configuration и eligibility всё ещё необходима.

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
