# Настройка через запрос

Не нужно знать файлы `.embraion/`, их ключи и команды `embraion`. Попросите AI-клиента простыми словами, на любом языке, и он заполнит нужный файл.

При первой настройке агент также проверяет наличие launcher и проектного контракта,
устанавливает launcher при наличии разрешения, инициализирует репозиторий и
устанавливает проекцию для нужного хоста. Для установки общего ПО на машине
может понадобиться ваше разрешение, но команды выполняет агент. Загрузку новых
skills проверяют в новой сессии хоста. Повтор неизменённого запроса не должен
менять проект.

> Настрой EmbrAIon для этого проекта.
>
> Защити папку `vendor/`.
>
> Объяви наш MCP-сервер.
>
> Разреши тебе мержить после зелёных проверок.
>
> Требуй запись решения при изменении зависимостей.

## Как агент обрабатывает запрос

1. Он сопоставляет ваши слова с одной записью матрицы настройки. Матрица поставляется с навыком `project-bootstrap` как `references/configuration-matrix.yaml`.
2. Он загружает навык и рецепт, которые назвала эта запись: `project-bootstrap`, `routing-configuration` или `architecture-decision`.
3. Сначала он читает репозиторий и текущий файл `.embraion/`. Он спрашивает только то, что нельзя узнать из репозитория, по одному короткому вопросу.
4. Он меняет только поля этой записи и сохраняет всё остальное.
5. Он запускает проверки из записи и сообщает по каждой: пройдена, не пройдена или не запускалась.

Ручное редактирование и команды `embraion` остаются доступными. Эта страница показывает путь от запроса к результату.

## Настройки, которые решаете только вы

Строки с ● расширяют доступ или ослабляют защиту: уборка, которая удаляет ветки, классы приватности, правила ревью, enforcement, режим merge, потолки политики, execution-привязки, интеграции, внешние возможности, политику записи зарегистрированных источников, проектных агентов (их доступ) и изменения validation, которые делают проверки необязательными или более узкими. Агент меняет их, только если ваш запрос это говорит. Иначе он сначала спрашивает.

`merge.mode: owner-permission` не даёт постоянного разрешения на merge. Агент может смержить pull request, только если вы разрешили именно этот pull request, обязательные проверки прошли на его финальном head, а независимый ревьюер подтвердил этот head. Auto-merge остаётся выключенным.

## Карта запросов

| Запись | Пример запроса | Заполняет | Решение владельца | Чем проверяется |
| --- | --- | --- | --- | --- |
| `set-up` | Настрой EmbrAIon для этого проекта | набор: `bind-knowledge`, `protect-paths`, `project-validation`, `project-agents`, `project-identity` |  | `embraion doctor`<br>`embraion validate --strict`<br>`embraion check` |
| `bind-knowledge` | Зарегистрируй документ с архитектурой | `knowledge.yaml`: slots, свои записи |  | `embraion context slots`<br>`embraion validate --strict` |
| `project-validation` | Добавь нашу команду тестов в проверки | `validation.yaml`: profiles |  | `embraion validation list`<br>`embraion validation run fast` |
| `validation-guards` | Падай, если тесты меняют рабочее дерево | `validation.yaml`: profiles | ● | `embraion validation list`<br>`embraion validation run <profile>` |
| `plan-validation` | Запускай только проверки, относящиеся к изменённым файлам | `validation.yaml`: areas, impact, full-reasons, default-area | ● | `embraion validation list`<br>`embraion validation explain <profile> --base-ref <base>` |
| `project-agents` | Добавь специалиста только для чтения по нашему API | `agents.yaml`: agents | ● | `embraion projection diff --host <installed-host> --destination .`<br>`embraion install --host <installed-host> --destination .` |
| `project-identity` | Переименуй проект в EmbrAIon | `project.yaml`: project, capabilities |  | `embraion status`<br>`embraion validate --strict` |
| `update-framework` | Обнови EmbrAIon до последнего релиза | `project.yaml`: framework |  | `embraion update --check`<br>`embraion doctor`<br>`embraion status` |
| `task-housekeeping` | Автоматически чисти старые ветки и рабочие деревья агентов | `project.yaml`: housekeeping | ● | `embraion worktree gc` |
| `declare-sources` | Зарегистрируй наши репозитории и укажи, какие можно изменять | `sources.yaml`: schema-version, sources | ● | `embraion sources list`<br>`embraion sources status`<br>`embraion validate --strict` |
| `hydrate-lfs-worktrees` | Подтягивай файлы Git LFS в новых рабочих деревьях | `project.yaml`: worktree |  | `embraion policy show` |
| `add-pr-template` | Добавь шаблон pull request | создаёт `.github/pull_request_template.md` |  | `embraion pr-template` |
| `protect-paths` | Защити эти папки | `policy.yaml`: sources |  | `embraion policy show`<br>`embraion check` |
| `classify-privacy` | Считай этот источник конфиденциальным | `policy.yaml`: privacy | ● | `embraion policy show`<br>`embraion policy check` |
| `set-review-rule` | Требуй ревью для существенных изменений | `policy.yaml`: review | ● | `embraion policy show` |
| `enable-enforcement` | Проверяй правила в CI | `policy.yaml`: enforcement | ● | `embraion enforcement status`<br>`embraion policy show`<br>`embraion enforcement check --base-ref <base>` |
| `set-merge-mode` | Разреши тебе мержить после зелёных проверок | `policy.yaml`: merge | ● | `embraion policy show`<br>`embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |
| `set-policy-ceilings` | Никогда не отправляй конфиденциальные данные этому провайдеру | `policy.yaml`: ceilings | ● | `embraion policy check`<br>`embraion route --validate` |
| `configure-check` | Сделай одну команду со всеми проверками проекта для CI | `policy.yaml`: check |  | `embraion check`<br>`embraion policy show` |
| `configure-projection-checks` | Проверяй установленные файлы агентов в CI | `policy.yaml`: projection |  | `embraion projection verify --host <installed-host> --destination .`<br>`embraion check` |
| `configure-routing` | Настрой роутинг | `routing.yaml`: overrides, task-classes, candidate-groups; `deployments.yaml`: providers, deployments |  | `embraion route --validate`<br>`embraion deployment list`<br>`embraion route --host <host> --route-class <class> --data PRIVATE`<br>`embraion route --audit-authority`<br>`embraion policy check` |
| `declare-execution-binding` | Разреши EmbrAIon вызывать этого провайдера через ключ API из окружения | `execution.yaml`: schemaVersion, bindings | ● | `embraion execution preflight --deployment <deployment-id>`<br>`embraion policy check` |
| `declare-pricing` | Считай стоимость вызовов провайдера | `pricing.yaml`: schemaVersion, sources |  | `embraion pricing status` |
| `declare-integration` | Объяви наш MCP-сервер | `integrations.yaml`: schema-version, servers | ● | `embraion security scan --path . --fail-on high`<br>`embraion doctor` |
| `declare-external-capability` | Запиши, что этот плагин установлен у команды | `external-capabilities.yaml`: schema-version, capabilities | ● | `embraion capabilities --path . --host <installed-host>` |
| `bind-decisions` | Требуй запись решения при изменении зависимостей | `decisions.yaml`: index, template, triggers, extra-triggers; `knowledge.yaml`: slots.decisions |  | `embraion decisions check --require-config --path . --base-ref <base>`<br>`embraion context slots`<br>`embraion check --base-ref <base>` |
| `limit-code-structure` | Требуй имена файлов строчными буквами в docs | `organization.yaml`: exclude, namespaces, assemblies, unity_meta, filenames |  | `embraion organization check --require-config --path .` |
| `track-doc-sources` | Предупреждай, когда документ об архитектуре устарел относительно кода | `knowledge-maintenance.yaml`: documents |  | `embraion knowledge audit --path .` |
| `shape-final-report` | Используй такие разделы в итоговых отчётах | `report.yaml`: schema-version, sections, workers, pull-request, guidance |  | `embraion report template`<br>`embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |
| `claude-native-agents` | Сделай маршрут ревьюера доступным как нативного агента Claude | `claude-native.yaml`: bindings, assignments, read-policy |  | `embraion claude-native status` |
| `project-skill` | Добавь проектный навык для нашего процесса релиза | `.embraion/skills/`: `<name>/SKILL.md` |  | `embraion install --host <installed-host> --destination .`<br>`embraion projection verify --host <installed-host> --destination .` |

`embraion validate --strict` и `embraion doctor` проверяют имена ключей, а не полную форму файла. Команды из последнего столбца загружают файл и проверяют его форму целиком, поэтому агент всегда их запускает. После изменения, которое копируется в файлы хоста (режим merge, контракт отчёта, агенты, проектные навыки, нативные агенты Claude), агент также запускает `embraion install --host <host> --destination .` и `embraion projection verify` для каждого установленного хоста.

## Что запросом не настраивается

- `project.yaml` `framework`: меняется только через `embraion update`; см. [Безопасное обновление](../getting-started/updating.md).
- `.embraion/pricing.snapshot.json`: создаётся командой `embraion pricing refresh`.
- `.embraion/state/` и `.embraion/.gitignore`: локальное состояние выполнения.

## Как карта остаётся полной

Матрица лежит в файле данных рядом с навыком. Unit-тест читает схемы, перечисляет каждый файл `.embraion/` и каждый ключ верхнего уровня и раздела и падает, если у ключа нет записи в матрице. Поэтому новый ключ обязан получить запись, рецепт и строку здесь.

Связанные страницы: [Начальная настройка проекта](bootstrap.md), [Разговорная настройка](ai-hosts.md), [Файлы проекта](project-files.md).
