# Runtime и разрешение версий

EmbrAIon разделяет **версию глобального launcher** и **release framework, закреплённый за каждым проектом**.

## Один launcher, несколько project pins

Проект хранит framework contract в:

```text
.embraion/project.yaml
```

Начиная с v0.14 project pin может включать точную identity опубликованного wheel и его проверенный SHA-256 digest:

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: 0.16.0
  artifact:
    schema: 1
    source: github-release
    release: v0.16.0
    asset: embraion-0.16.0-py3-none-any.whl
    digest: sha256:<64-lowercase-hex>
```

Artifact lock принадлежит самому framework. Consumer CI больше не нужен отдельный URL wheel, вручную захардкоженная переменная checksum или собственный parser checksum.

Старые manifests, где есть только version, остаются валидными. Следующий успешный `embraion update` автоматически обновит их и создаст lock; ручная миграция не требуется.

Обычные команды находят ближайший проект и разрешают его pin:

![Runtime и разрешение версий](../assets/diagrams/en/07-runtime-version-resolution.svg){ loading=lazy }

Если pin отличается от версии launcher, EmbrAIon устанавливает точно закреплённую distribution в изолированный cache:

```text
~/.embraion/versions/<version>/
```

Для проектов с lock runtime resolver скачивает точный asset из canonical GitHub Release, проверяет SHA-256 **до** установки через pip и записывает artifact identity в runtime marker. Cached runtime можно повторно использовать только когда его artifact identity и digest совпадают с project lock.

Поэтому разные репозитории на одной машине могут оставаться на разных release-версиях EmbrAIon.

В Windows длинный `EMBRAION_CACHE_HOME` может привести к превышению распространённого ограничения в 260 символов для путей внутри wheel. При установке закреплённого релиза `framework install` проверяет эти пути до создания или замены runtime и сообщает, что нужно сделать. Задайте короткий каталог для `EMBRAION_CACHE_HOME`, например `C:\EmbrAIonCache`, и повторите установку. Уже пригодный cached runtime используется без переустановки.

## Update, verify, install

Сначала обновите global launcher, затем проект:

```bash
pipx upgrade embraion
cd MyProject
embraion update
```

`embraion update` ориентируется на установленную версию launcher. До изменения project pin команда разрешает canonical GitHub Release, требует ровно один ожидаемый wheel asset, требует server-side GitHub digest формата `sha256:`, проверяет release tag / имя asset / URL и валидирует candidate project configuration.

Запись manifest является commit point обновления: `framework.version` и `framework.artifact` заменяются вместе одной атомарной записью YAML. Отсутствующий release, отсутствующий artifact, некорректный digest или несовместимая конфигурация приводят к fail-closed до изменения pin.

Проверить закреплённый release artifact без установки:

```bash
embraion framework verify
```

Установить точный release с проверенным digest в изолированный runtime cache:

```bash
embraion framework install
```

Обе команды берут artifact identity только из project pin/lock. Consumer-owned checksum logic им не нужна.

## Consumer CI

Workflow GitHub Actions может использовать переиспользуемый setup action вместо собственного шага установки и чтения pin:

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0  # история для --base-ref
  - uses: GORYNED/EmbrAIon/actions/setup@v<release>
    with:
      python-version: "3.13"  # необязательно, значение по умолчанию
      project-path: .         # необязательно, папка в корне проекта или ниже
  - uses: GORYNED/EmbrAIon/actions/check@v<release>
```

Action `check` выполняет `embraion framework install` для pin с lock, а затем `embraion check`, поэтому в workflow нет флагов проекта: режимы organization check, порог security и область сканирования берутся из секции `check` в `.embraion/policy.yaml` (см. [Параметры check](../configuration/policy.md#check-options)). Входы: `project-path` (по умолчанию `.`, корень проекта или папка ниже него), `base-ref`, `upload-evidence` (по умолчанию `false`) и `evidence-retention-days` (по умолчанию `14`). С `upload-evidence: "true"` action загружает `.embraion/state/validation/` корня проекта, который он находит так же, как `embraion check`, как workflow artifact с уникальным для запуска именем, в том числе когда проверка падает. В этой папке лежит evidence validation profiles, которые запускает `check.validation-profiles`. Папка скрытая, поэтому action загружает скрытые файлы. Если ни один профиль не запускался, шаг загрузки выдаёт предупреждение, что файлов нет. **Artifact содержит полный вывод команд профилей**, поэтому всё, что эти команды печатают, сохраняется вместе с запуском; для чувствительного вывода не включайте `upload-evidence` и уменьшите `evidence-retention-days`. Поиск artifact никогда не роняет action. Без `base-ref` pull request сравнивается с `origin/<base branch>`, а push использует проверенный предыдущий commit из события. У initial push, недоступного предыдущего commit и переписанной истории нет пригодного base; action падает только тогда, когда выбранная сравнительная проверка требует base. Checkout должен получить нужную историю. Action ожидает, что EmbrAIon уже установлен setup action, и входа `python-version` не имеет. `embraion check` запускает все проверки, которые выбирает конфигурация проекта; см. [справочник CLI](cli.md#embraion-check).

Action настраивает Python, читает `.embraion/project.yaml` тем же кодом, что и `embraion framework pin`, и устанавливает ровно закреплённую release. При artifact lock он скачивает canonical release wheel и проверяет SHA-256 до установки через pip; без lock устанавливает `embraion==<version>`. Затем проверяется установленная версия. Отсутствующий или неточный pin, несовпадающий lock или несовпадение digest завершают шаг с ошибкой. Outputs: `version` и `digest` (пустой без lock).

Ref action выбирает только код начальной установки. Устанавливаемая release всегда берётся из project pin, поэтому `embraion update` действует без правки workflow; ref стоит менять только ради нового поведения самого action. Чтение pin выполняется кодом release action в изолированном окружении только с PyYAML, а текст проекта не может выполнить workflow commands в логе. Шаги используют `bash` и рассчитаны на Linux и macOS runners; Windows runners не поддерживаются. Команды в проекте с lock по-прежнему выполняются из runtime cache, привязанного к digest, как описано выше.

Другие CI-системы могут следовать тому же контракту: `embraion framework pin` печатает строки `version=` и `digest=` и завершается с ошибкой при неточном pin. `embraion enforcement install` генерирует workflow с этим action.

## Проверить разрешённую версию

```bash
embraion status
embraion status --json
```

Status показывает launcher, project pin, resolved runtime, состояние cache, а также наличие artifact lock и его digest.

## Управление cache

```bash
embraion cache list
```

Предварительный просмотр очистки:

```bash
embraion cache prune --older-than 90
```

Применить очистку осознанно:

```bash
embraion cache prune --older-than 90 --apply
```

Активный launcher и resolved runtime текущего проекта защищены от очистки по возрасту.

## Переход на другую конкретную release

Сначала установите нужную версию launcher, затем запустите `embraion update` из проекта. Нормализация конфигурации и генерация artifact lock принадлежат тому же release contract, который будет записан.

## Development override

`EMBRAION_HOME` выбирает явный checkout framework для разработки самого EmbrAIon. Автоматическое разрешение версий можно намеренно отключить через `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.

Переменные resolver `EMBRAION_VERSION_RESOLVED`, `EMBRAION_RESOLVED_VERSION`, `EMBRAION_RESOLVED_PROJECT` и установленный им `EMBRAION_HOME` действуют только в делегированном интерпретаторе. Validation и другие независимые дочерние команды получают очищенное окружение и разрешают собственный project. Явный development override пользователя сохраняется. Установка, проверка и запуск cached runtime также исключают `PYTHONPATH`, чтобы импорты из checkout не подменяли locked distribution.

Репозиторий framework сам является EmbrAIon project. Его pin и artifact lock остаются на последнем опубликованном стабильном релизе, пока source развивается. В checkout используйте `python tools/source.py <command>` для source CLI и `python tools/source.py test unit` или `test integration` для source tests. Runner выбирает код и данные checkout, удаляет унаследованное состояние resolver и использует локальную `.venv`, если она существует; иначе текущий Python должен иметь зависимости framework. Source CLI сохраняет project overlay и routing репозитория. Validation profiles и source CI используют этот entry point; проверки installed package вне checkout продолжают использовать packaged CLI.

Обе команды тестов принимают `--jobs N` или `--jobs auto` (число CPU, не больше 4). Если jobs больше одного, модули тестов запускаются в отдельных рабочих процессах, которые берут модули из общей очереди, начиная с самых больших файлов. У каждого процесса свой временный каталог (`TMPDIR`, `TEMP` и `TMP`). Команда печатает сводку по каждому процессу и общий итог, сохраняет вывод ошибок и завершается с ненулевым кодом, если упал любой процесс или число выполненных тестов не совпало с числом найденных. Без `--jobs`, с `--jobs 1` и с `--jobs auto` на машине с одним CPU тесты идут в одном процессе, как раньше. Рабочий процесс, завершившийся с ненулевым кодом, считается упавшим, даже если он записал результат. Модули, которые нельзя запускать рядом с параллельными процессами, можно назвать в `SEQUENTIAL_MODULES` в `tools/parallel_tests.py`; тогда они идут в родительском процессе после параллельной фазы. Сейчас unit-список содержит `test_core`, `test_sources`, `test_policy_ceilings`, `test_config_checks` и `test_derived_generated`: они сканируют checkout, пока другие модули создают временные build-файлы. Также в нём `test_worktree_housekeeping`: удаление Git worktree на Windows падало в параллельном запуске, а модуль из 57 тестов завершился изолированно с одним skip. Runner выполняет эти модули после параллельной фазы.

Аудит изоляции параллельного runner: чтение кода и поиск общего состояния в тестах. Тесты не используют фиксированные порты (серверы привязываются к порту 0). Тесты, которые пишут в `build/`, используют уникальные временные каталоги или `mkdir(exist_ok=True)`. Тесты, которые создают проекты или checkout, используют временные каталоги. CLI-тесты, запускающие `embraion` как подпроцесс, задают `EMBRAION_CACHE_HOME` во временный каталог или отключают разрешение версий и не трогают runtime cache пользователя. Код, который читает `~/.codex`, `~/.claude` или `~/.agents/skills`, только читает. Один тест пишет в общее состояние: `test_clean_project_bootstrap_and_update` в `tests/integration/test_reference_projects.py` вызывает `update_project` в процессе теста. Это устанавливает runtime для pin 0.8.1 в настоящий runtime cache (`~/.embraion/versions/`, меняется через `EMBRAION_CACHE_HOME`) и наполняет кэш pip. Это единственный модуль с таким поведением, а наборы unit и integration идут один за другим, поэтому два процесса не пишут туда одновременно. Новый тест, который пишет в runtime cache, домашний каталог пользователя, фиксированный путь или фиксированный порт, должен задать собственное место или быть назван в `SEQUENTIAL_MODULES`.
