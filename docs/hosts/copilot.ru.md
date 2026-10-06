# GitHub Copilot

## Project Bootstrap

Проецируемый канонический Core skill `project-bootstrap` поддерживает «Настрой EmbrAIon для этого проекта». Установите component `skills` и используйте его в активной сессии; trust, permissions и загрузка skills определяются хостом. Lead изучает истину репозитория, сохраняет настройки, находит реальную validation и оставляет routing необязательным. См. [Project Bootstrap](../configuration/bootstrap.md).

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
    ├── orchestration/
    ├── project-bootstrap/
    ├── review/
    ├── routing-configuration/
    └── ...
```

Generated files — projections. Project policy, knowledge, validation, agents и optional routing overrides остаются canonical в `.embraion/`.

## Delivery semantics

Generated Copilot agent profiles включают repository instructions через `include-custom-instructions: true`. Это важно, когда Copilot вызывает profile как custom subagent: repository instruction files не наследуются custom subagents по умолчанию.

Host всё ещё может глобально отключить repository instructions, а host-level settings имеют приоритет над projection.

Generated `tools` — allowlist инструментов, доступных на активной Copilot surface. EmbrAIon может запрашивать aliases `read`, `search`, `edit`, `execute`, но не обещает, что host реально предоставляет каждый alias в каждом custom-subagent context.

Component `skills` также записывает `.github/instructions/embraion-core.instructions.md` с `applyTo: "**"`, поэтому все правила Core прикладываются к каждому запросу как repository instruction file.

Skills в `.github/skills/` проецируются как root/session procedural capabilities. Adapter не обещает автоматическое inheritance этих skills каждым custom subagent, пока GitHub не предоставляет такой contract и EmbrAIon явно его не конфигурирует.

## Routing

Применяйте [канонический assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) перед каждым новым или повторно используемым заданием. Core определяет classification, resolution, reuse, evidence и cross-host handoff со свежими privacy/access checks; [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/copilot/orchestration.md) определяет механизмы конкретного host. Concrete deployment choices принадлежат `.embraion/`; generated specialist profiles остаются model-neutral.

CLI поддерживает definition `model`, ordered `models`, `modelPolicy` и `reasoningEffort`, а также per-call settings, если они есть в установленной схеме `task`/`session.startSubagent`. Precedence: call, `settings.subagents`, definition, parent; `models` имеет приоритет над `model`. Обязательная model требует поддерживаемой policy `required`; `preferred` и Auto могут наследовать parent. VS Code поддерживает per-call model и definition model string/array, но может отклонить более дорогой tier, чем у parent. Для `reasoning-effort` нужно подтверждение installed version/schema; CLI field names не взаимозаменяемы. Для cloud/general agents подтверждена `model`, но не CLI-only controls.

Обязательные settings нельзя молча заменить, ограничить cap или унаследовать. Неизвестная surface, schema или options — capability limitation, требующая разрешения по Core. Документация проверена 2026-09-29; ссылки на официальные источники находятся в native adapter. Проверяйте installed schema, precedence и effective settings при invocation. Подготовка маршрута ещё не означает execution.

```bash
embraion route --host copilot --route-class substantial --data PRIVATE
```

Opt-in planner `embraion dispatch --native-surface` поддерживает `copilot-cli`, `copilot-vscode`, or `copilot-cloud`; `--task-class` выбирает настроенный assignment route. `native-plan` содержит `status`, `arguments`, `definition-overrides`, `requirements`, `limitations` и `executed: false`. `prepared` означает static translation; `handoff-required` требует native loading/session step, а `capability-limitation` блокирует invocation до разрешения проблемы. Проверка active schema, effective configuration и eligibility всё ещё необходима.

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
