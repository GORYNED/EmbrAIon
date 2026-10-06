# Claude Code

## Project Bootstrap

Проецируемый канонический Core skill `project-bootstrap` поддерживает «Настрой EmbrAIon для этого проекта». Установите component `skills` и используйте его в активной сессии; trust, permissions и загрузка skills определяются хостом. Lead изучает истину репозитория, сохраняет настройки, находит реальную validation и оставляет routing необязательным. См. [Project Bootstrap](../configuration/bootstrap.md).

## Что это

Claude Code adapter проецирует EmbrAIon Core/project agents и reusable skills в repository-native files Claude Code.

## Установка

```bash
embraion install --host claude-code --destination .
```

## Generated structure

```text
.claude/
├── rules/
│   ├── embraion.md
│   └── embraion-core.md
├── agents/
│   ├── analyst.md
│   ├── architect.md
│   ├── reviewer.md
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

## Routing

Применяйте [канонический assignment routing contract](https://github.com/GORYNED/EmbrAIon/blob/main/core/skills/orchestration/SKILL.md) перед каждым новым или повторно используемым заданием. Core определяет classification, resolution, reuse, evidence и cross-host handoff со свежими privacy/access checks; [native adapter](https://github.com/GORYNED/EmbrAIon/blob/main/adapters/claude-code/orchestration.md) определяет механизмы конкретного host. Concrete deployment choices принадлежат `.embraion/`; generated specialist profiles остаются model-neutral.

Проверьте схему установленного `Agent`/`Task`: его аргумент `model` может принимать только короткие имена, а не полные ID. Планировщик помещает явно выбранные model и/или effort в полное временное описание агента вместе с инструкциями роли и разрешёнными инструментами. Это описание нужно загрузить и выбрать перед запуском. Настройки среды, разрешённые модели, наследование при fork и ограничения effort могут изменить результат — проверяйте фактические настройки.

Обязательные settings нельзя молча заменить, ограничить cap или унаследовать. Неизвестная surface, schema или options — capability limitation, требующая разрешения по Core. Документация проверена 2026-09-29; ссылки на официальные источники находятся в native adapter. Проверяйте installed schema, precedence и effective settings при invocation. Подготовка маршрута ещё не означает execution.

```bash
embraion route --host claude-code --route-class substantial --data PRIVATE
```

Opt-in planner `embraion dispatch --native-surface` поддерживает `claude-agent`; `--task-class` выбирает настроенный assignment route. `native-plan` содержит `status`, `arguments`, `definition-overrides`, `requirements`, `limitations` и `executed: false`. `prepared` означает static translation; `handoff-required` требует native loading/session step, а `capability-limitation` блокирует invocation до разрешения проблемы. Проверка active schema, effective configuration и eligibility всё ещё необходима.

## Selective adoption

Компонент `skills` также управляет `.claude/rules/embraion.md`. Это правило без ограничения по путям: оно просит каждый Thread прочитать orchestration и применимые `AGENTS.md`. Рядом лежит `.claude/rules/embraion-core.md`: все правила Core в одном безусловном файле. Установка сохраняет пользовательский `CLAUDE.md` и чужие skills. Загрузка правила зависит от конкретного режима Claude — её нужно проверить в самом приложении.

Начиная с 0.18.0 имена профилей Claude используют машинные ID, например `reviewer`, вместо названий вроде `Reviewer` или `Video/CV`. Длинные ID получают сокращённое имя с хешем. Пересоздайте профили и используйте полученные имена; заголовки инструкций сохраняют удобные для чтения названия.

Роль маршрутизации и имя агента разделены. Для настроенной роли `independent-review`, которую выполняет стандартный reviewer, используйте `--role independent-review --native-agent reviewer`. Сохраняются ограничения маршрута и инструменты reviewer только для чтения. Явные настройки дают полное `scoped-definition`; его `name` становится `arguments.subagent_type`. Для поддерживаемого загрузчика `--agents` создайте JSON-объект с ключом `name` и остальными полями описания в значении. Текст задания передаётся отдельно при запуске. План остаётся `executed: false`.

Каждый выбранный маршрут `critical` теперь требует непустой `--justification`, в том числе при прямом вызове route и dispatch. Само переименование API не доказывает критический риск: правила проекта должны учитывать реальные последствия. При обновлении старые вызовы `critical` нужно дополнить объяснением.

Claude Code поддерживает стандартные компоненты `agents` и `skills`, а также явно выбранный `scoped-agents`. Обычная установка сохраняет прежний набор компонентов:

```bash
embraion install --host claude-code --destination . --component skills
embraion install --host claude-code --destination . --component agents --component skills
```

## Агенты, подготовленные до старта Thread

Чтобы выбранный маршрут появился в списке агентов приложения, до запуска Thread добавьте `.embraion/claude-native.yaml`. Пример для проекта, в котором маршрут Claude reviewer уже выбирает подходящий deployment:

```yaml
bindings:
  reviewer: reviewer
assignments:
  - role: reviewer
    route-class: complex
    data-class: PRIVATE
    access: review
read-policy:
  project-only: true
  deny-protected: true
```

`bindings` связывает роль маршрутизации с ID специалиста. `assignments` задаёт только сочетания класса, данных и доступа, которые нужно подготовить. Модель и effort по-прежнему берутся из routing/deployments. Компонент отклоняет неподходящее сочетание или `host-default`, а не придумывает настройки. Подготовка файлов не выбирает маршрут выполнения: для фактического запуска `critical` всё ещё требуется объяснение риска. Если роль называется `independent-review`, явно свяжите её с `reviewer`. Класс задачи выбирает объявленных кандидатов: переопределение роли Claude не превращает API-кандидата в агента приложения.

```bash
embraion framework install
embraion route --validate
embraion install --host claude-code --component scoped-agents
embraion projection verify --host claude-code --component agents --component skills --component scoped-agents
embraion claude-native install-hooks --dry-run
embraion claude-native install-hooks
embraion projection verify --host claude-code --component hooks
embraion claude-native status
```

Установка добавляет отдельные `.claude/agents/embraion--*.md` и метаданные `.claude/embraion-native.json`. Обычный `reviewer.md` остаётся без привязки к модели. Изменённые пользователем файлы и устаревшие изменённые определения сохраняют обычную защиту проекций. `--prune` удаляет только неизменённые устаревшие файлы с подтверждённым владением после проверки изменений. Префикс `embraion--` зарезервирован за этой проекцией: при выбранном `scoped-agents` команды `projection diff` и `projection verify` показывают любой `.claude/agents/embraion--*.md`, который текущая проекция не создала бы, как `obsolete-modified`, даже без локального ownership ledger (например, в чистом clone или CI). Владение такими файлами не подтверждено, поэтому `--prune` их сохраняет; удалите их после проверки.

После установки откройте **новый рабочий Thread** в этой копии проекта. Локальная и облачная копии требуют собственных проверок версии и проекций. Старый worktree сохраняет прежний пин; обновление глобального CLI его не переносит на новую версию. Lead разрешает каждое задание, dispatch находит настроенную связь ролей, затем Lead выбирает точное имя подготовленного агента из загруженного списка без переопределения модели при вызове. Наличие файла не доказывает загрузку. Если определения нет или оно устарело, требуется обновление проекции и новый Thread либо поддерживаемый загрузчик. Отдельный вход в CLI для правильно загруженного Agent не нужен.

## Нативные hooks и подтверждение настроек

`install-hooks` явно добавляет только записи EmbrAIon в `.claude/settings.json`, сохраняя остальные настройки и hooks. Повреждённые настройки и изменённую конфликтующую запись команда не заменяет, даже с `--force`. `install-hooks` устанавливает компонент projection `hooks` (`embraion install --host claude-code --component hooks`), который записывает управляемые записи в журнал projection, поэтому `projection verify --host claude-code --component hooks` сообщает об отсутствующей или изменённой записи как о расхождении. Неизменённая управляемая запись из предыдущей версии заменяется при следующей установке. В каждом режиме приложения нужно проверить разрешение hooks, поддержку хоста и доступность команды `embraion`.

Проверка перед инструментом запрещает запуск настроенной роли через обычный профиль, устаревшее имя подготовленного агента и переопределение модели при вызове. Если задан `read-policy`, чтение и поиск подготовленного агента ограничиваются текущим проектом и исключают защищённые пути или поиск, который может их затронуть. Используются текущие правила проекта; классификация данных не меняется. Проверка не изолирует инструменты родителя, произвольных агентов и shell. Родитель должен отдельно соблюдать правила источников и передавать допустимый ограниченный контекст.

Guard проверяет имя и точное содержимое определения, но не подтверждает свежую классификацию задачи или обоснование critical: перед запуском всё равно нужен канонический dispatch. Явные isolation/resume блокируются, пока перенос определения и настройки возобновлённого агента не подтверждены.

PostToolUse и SubagentStop сохраняют ограниченные ID сессии/агента и необязательное `effort.level` в игнорируемую локальную папку. Это поле допускается ранними описаниями типов Claude Code 2.1.277, но отсутствует в примерах; передачу поля установленной версией приложения нужно проверить на настоящем событии. Публичная команда observer принимает произвольный JSON, поэтому записи помечены `unverified-command-input`. `claude-native status` показывает установку, записанные события и справочное сравнение `reported-effort`; `execution`, фактические `effort` и `model` остаются `unverified`; `callbacks: recorded` означает только принятую запись. Запись сама по себе не доказывает источник события или завершение задачи. Нужны данные ответа или поддерживаемого нативного события; пустой effort при старте и слова агента настройки не подтверждают. Уже состоявшийся вызов модели проверка отменить не может. В журнал не попадают ввод инструментов, запросы, ответы и содержимое транскрипта.

Preview:

```bash
embraion projection diff --host claude-code --destination .
```

## Verify

```bash
embraion doctor
embraion status
embraion harness audit --host claude-code
```

Если `.claude/` уже содержит project-owned configuration, сначала используйте `projection diff`.

`harness audit` показывает необходимые и отсутствующие файлы. `ready` означает только наличие установки: содержимое файлов, загрузка инструкций, фактические настройки и выполнение этой командой не проверяются. У обзора Project, облачного и локального Thread могут различаться рабочие папки, инструкции и возможности. Отправка сообщения другому Thread ещё не доказывает, что его маршрутизация изменилась.

Для каждого доступного режима приложения проверьте новый и продолженный Thread: прочитаны ли правило и инструкции нужной папки; какой маршрут выбран для ограниченного ревью; загружено ли полученное описание агента; какие model/effort реально применились. Отдельно проверьте несовпадение настроек — запуск должен остановиться. Повторите для локального и облачного Thread. Автоматические проверки файлов не заменяют эту проверку в приложении.

Необязательный [Mods probe](https://github.com/GORYNED/EmbrAIon/tree/main/adapters/claude-code/mods-probe) проверяет регистрацию и наблюдаемые настройки в сборках Claude с поддержкой function hooks. `embraion install` его не устанавливает; после регистрации нужен отдельный явный вызов native Agent. Тесты с имитацией API не доказывают загрузку в приложении или фактическое effort.

[Отчёт проверки 0.19.1 на Windows](claude-code-check-0.19.1.md) сохраняет переданные сопровождающим наблюдения из двух локальных сессий Desktop в worktree и ограничения этих свидетельств.

## Дальнейшая настройка

См. [Разговорную настройку](../configuration/ai-hosts.md) и [Подключение существующего репозитория](../getting-started/existing-repository.md).

События hooks с полем `cwd` выбирают это рабочее дерево для проверки политики и записи метаданных, даже если Desktop запускает команду из основной папки. Относительные пути чтения и поиска отсчитываются от каталога события, включая вложенные папки; политика берётся из корня рабочего дерева. Выполняйте `claude-native status` в том же рабочем дереве. Некорректный путь события или несовпадение версии или контрольной суммы пакета рабочего дерева с активным кешированным runtime отклоняются; для старых событий без `cwd` сохраняется выбор по каталогу процесса. Метаданные остаются вспомогательными и не доказывают эффективную модель или effort.
