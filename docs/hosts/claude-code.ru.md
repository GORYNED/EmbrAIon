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
    ├── orchestration/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Routing

Применяйте [канонический assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) перед каждым новым или повторно используемым заданием. Core определяет classification, resolution, reuse, evidence и cross-host handoff со свежими privacy/access checks; [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/claude-code/orchestration.md) определяет механизмы конкретного host. Concrete deployment choices принадлежат `.embraion/`; generated specialist profiles остаются model-neutral.

Проверяйте схему текущего `Agent` или старого `Task` для per-call `model`. Native definitions `.claude/agents/*.md` или `--agents` JSON поддерживают `model` и `effort`; per-call Agent effort не подтверждена. Явная effort требует загруженного и выбранного assignment-specific native definition либо поддерживаемого handoff с проверенными settings. Обычный model precedence: invocation, definition, `CLAUDE_CODE_SUBAGENT_MODEL`, parent; force-mode environment settings могут его переопределить. Allowlists, fork inheritance, `CLAUDE_CODE_EFFORT_LEVEL` и model-specific effort caps могут изменить результат.

Обязательные settings нельзя молча заменить, ограничить cap или унаследовать. Неизвестная surface, schema или options — capability limitation, требующая разрешения по Core. Документация проверена 2026-09-29; ссылки на официальные источники находятся в native adapter. Проверяйте installed schema, precedence и effective settings при invocation. Подготовка маршрута ещё не означает execution.

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

Opt-in planner `embraion dispatch --native-surface` поддерживает `claude-agent`; `--task-class` выбирает настроенный assignment route. `native-plan` содержит `status`, `arguments`, `definition-overrides`, `requirements`, `limitations` и `executed: false`. `prepared` означает static translation; `handoff-required` требует native loading/session step, а `capability-limitation` блокирует invocation до разрешения проблемы. Проверка active schema, effective configuration и eligibility всё ещё необходима.

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
