# Справочник CLI

Запустите:

```bash
embraion help
```

чтобы увидеть каталог команд launcher, или:

```bash
embraion help <command>
```

для справки по конкретной команде.

## Проект и setup

### `embraion init`

Создать modular project configuration `.embraion/`.

```bash
embraion init
embraion init --name MyProject
```

### `embraion bootstrap`

Необязательный deterministic discovery и консервативное применение для инициализированного проекта. Обычный entry point пользователя — ordinary-language skill [Project Bootstrap](../configuration/bootstrap.md).

```bash
embraion bootstrap plan --output .embraion/state/bootstrap-plan.json
embraion bootstrap apply --plan .embraion/state/bootstrap-plan.json
```

`plan` сообщает evidence, proposed knowledge/policy/validation changes и limitations. Перед применением прочитайте оригинальные источники: имя документа не доказывает authority, CI commands требуют проверки локального контекста и безопасности. `--path` выбирает инициализированный проект. Output должен находиться в локальном `.embraion/state/` или вне репозитория.

`apply` принимает только неизменённый проверенный план, совпадающий с текущими discovery, source hashes, configuration и project root. Он заполняет unbound slots/empty profiles и консервативно пустые canonical sources; populated settings и более строгие ограничения сохраняются. Он не настраивает routing/agents, не создаёт docs, не устанавливает зависимости, не запускает команды и не заявляет validation pass. Семантическая коррекция выполняется bounded project edits с последующим новым планом. Lead отвечает за дальнейшую verification.

### `embraion install`

Установить одну host projection.

```bash
embraion install --host codex --destination .
```

Hosts: `codex`, `copilot`, `claude-code`, `portable`.

Preview без записи:

```bash
embraion install --host codex --destination . --dry-run
```

Installed projections отслеживают generated-file hashes. Последующие installs отличают безопасные updates от local conflicts вместо слепой перезаписи файлов.

Существующие repos могут явно выбирать projection components:

```bash
embraion install --host codex --destination . --component skills
embraion install --host codex --destination . --component agents --component skills
```

Поддерживаемые components host-specific: Codex поддерживает `config`, `agents` и `skills`; GitHub Copilot — `agents` и `skills`; Claude Code — `agents`, `skills` и необязательный `scoped-agents`; Portable использует `bundle`. Невыбранные components остаются user-owned и исключаются из obsolete-file handling.

Для зрелого Codex repo, который уже владеет `.codex/config.toml`, используйте merge ownership только для required `[agents]` keys EmbrAIon:

```bash
embraion install   --host codex   --component config   --config-mode merge
```

`--config-mode replace` остаётся default. Merge mode сохраняет project-owned `[agents]` keys и другие TOML tables и fail-closed, если файл нельзя безопасно merge.

Projection install и pruning отклоняют вложенные symlinks/junctions в managed paths, включая projection evidence под `.embraion/state`. Сам destination может быть alias каталога. Запись использует эксклюзивно созданный уникальный temporary file и заменяет directory entry: внешний hardlink inode и существующие `.tmp` aliases не изменяются. Pruning повторно проверяет ownership hash перед удалением и сохраняет более поздние пользовательские правки.

### `embraion projection`

Preview ownership-aware изменений projection:

```bash
embraion projection diff --host codex --destination .
embraion projection diff --host codex --destination . --component skills
embraion projection diff --host codex --destination . --json
```

Проверить installed projection как strict CI gate:

```bash
embraion projection verify --host codex --destination .
embraion projection verify --host copilot --component agents --component skills
```

`projection verify` завершается с кодом 0 только когда каждый selected projection file уже canonical и нет create/update/conflict/obsolete managed output. При partial Codex config ownership передавайте `--config-mode merge` и в `projection diff`, и в `projection verify`.

Merge mode сохраняет пользовательское содержимое вне managed-блоков, поэтому verify дополнительно сообщает `root-findings` об этом содержимом: ключи верхнего уровня, которые переопределяют модель или effort пользователя либо routed-выбор субагентов (`model`, `model_reasoning_effort`, `agents.default_subagent_*`), ключи вне необязательного списка `allowed-root-keys` и текст корневых `developer_instructions` вне managed orchestration block. По умолчанию это предупреждения. `--strict-root` или `projection.codex.strict-root: true` в [policy](../configuration/policy.ru.md#projection-root-checks) делают их ошибкой проверки:

```bash
embraion projection verify --host codex --component config --config-mode merge --strict-root --json
```

### `embraion policy`

Посмотреть normalized source, validation, review и privacy policy:

```bash
embraion policy show
embraion policy show --json
```

Завершиться с ошибкой, если deployments, execution bindings или routing расширяют [policy ceilings](../configuration/policy.ru.md#policy-ceilings) проекта. `embraion validate` внутри проекта выполняет ту же проверку:

```bash
embraion policy check
embraion policy check --json
```

### `embraion report`

Вывести или проверить контракт итогового отчёта проекта, объявленный в `.embraion/report.yaml` (см. [Completion report](../configuration/report.ru.md)):

```bash
embraion report template
embraion report validate report.md --pull-request
embraion report validate report.md --pull-request-not-created
embraion report validate update.md --kind intermediate
```

`report validate` завершается с ошибкой и перечнем findings с номерами строк, если отчёт нарушает контракт. `-` читает отчёт из stdin. `--pull-request` требует полный URL pull request, а `--pull-request-not-created` вместо него требует compare URL. Эти флаги взаимоисключающие.

### `embraion update`

Безопасно нормализует project configuration и атомарно синхронизирует framework pin с точным lock опубликованного release artifact.

```bash
embraion update
embraion update --framework-version <published-version>
```

Проверить наличие новой опубликованной release, не меняя файлы:

```bash
embraion update --check
embraion update --check --json
```

`--check` читает последнюю stable GitHub Release, проверяет её tag и digest ожидаемого wheel и сообщает статус launcher и project pin (`current`, `outdated`, `ahead` или `not-comparable`), наличие artifact lock в проекте и следующие шаги. Код выхода `0` независимо от наличия обновления; ответ содержится в поле `update-available` JSON-отчёта. Недоступные или некорректные release metadata дают ненулевой код выхода. `--check` нельзя сочетать с `--framework-version`.

Безопасная нормализация конфигурации ориентируется только на установленную версию EmbrAIon launcher. Чтобы перевести проект на другую опубликованную версию, сначала установите или обновите/понизьте launcher до этой версии, затем запустите `embraion update`.

До изменения pin EmbrAIon разрешает canonical GitHub Release и требует ровно один ожидаемый wheel с именем `embraion-<version>-py3-none-any.whl` и валидным server-side GitHub digest формата `sha256:`. Команда проверяет release tag, identity asset, URL, формат digest и всю candidate canonical-конфигурацию `.embraion/`.

Project manifest записывается атомарно сразу с двумя частями:

- `framework.version`
- `framework.artifact.{schema,source,release,asset,digest}`

Отсутствующий release asset, некорректный digest, mismatch version/lock или несовместимая конфигурация приводят к fail-closed. Существующие проекты только с version обновляются автоматически; отсутствующие modular config files создаются из совместимых defaults без ручной миграции. Generated host projections и projection state не меняются.

### `embraion framework`

Используйте framework-owned artifact lock вместо consumer-specific download/checksum logic.

Проверить точный locked release asset без установки:

```bash
embraion framework verify
embraion framework verify --json
```

Установить точный locked wheel в изолированный EmbrAIon runtime cache:

```bash
embraion framework install
embraion framework install --json
```

Обе команды читают `.embraion/project.yaml`, требуют валидный artifact lock, скачивают точный canonical GitHub Release asset и проверяют его SHA-256 до успешного завершения. `framework install` выполняет проверку до вызова pip и записывает identity lock в runtime cache marker. Cached runtimes с другой artifact identity или digest отклоняются.

### `embraion sync`

Создать disposable host projections без установки в проект.

```bash
embraion sync --host all --output build/generated --force
```

## Health и runtime

### `embraion pricing`

Концептуальная модель: [Pricing и стоимость](../configuration/pricing.md).

Посмотреть validated local pricing snapshot без network access:

```bash
embraion pricing status --json
embraion pricing status --fail-on-stale
```

Обновить только approved official sources, объявленные по ID в `.embraion/pricing.yaml`:

```bash
embraion pricing refresh --json
embraion pricing refresh --source openai
```

Refresh валидирует каждый выбранный source и атомарно заменяет snapshot. Failure сохраняет previous snapshot; execution может продолжать offline, а stale/missing rates дают unknown calculated cost. Provider-specific SKU patterns и source URLs остаются в project configuration. CLI не принимает arbitrary URLs.

`embraion pricing calculate` читает JSON request из stdin с `deployment`, nullable `usage`, `usageSemantics` и optional `billing`, `providerExact`, `adapterCost`, `reportedCurrency`, `atUtc`, `batch`, `discount`. Snapshot calculation требует explicit usage semantics: `inclusive` означает, что cached/reasoning counts входят в input/output totals; `disjoint` — что они дополнительные. Для разных input/output conventions можно передать `{"input":"inclusive","output":"disjoint"}`. Команда читает только validated local snapshot; reported exact costs имеют приоритет. Reported cost имеет unknown currency без `reportedCurrency`. Response различает unknown/stale и zero. Scheduled rate нельзя комбинировать с batch/discount rates в одной snapshot entry.

`embraion pricing verify --fixtures <yaml> [--json]` проверяет, что configured rows дают reviewed costs. Файл содержит `schemaVersion: 1` и список `fixtures`; у каждого fixture уникальный `id`, `deployment`, nullable `usage`, optional `usageSemantics`, `atUtc` (в кавычках), `billing`, `batch`, `discount` и `expect` с `state`, `amount` (decimal string в кавычках или null) и optional `currency`. Каждый fixture считается offline тем же calculation, что и `pricing calculate`; amounts сравниваются как exact decimals (`"3.750"` равно `"3.75"`). При любом mismatch команда завершается с кодом 1.

### `embraion execute`

Про execution ownership, bindings, aliases, fallback и handoff см. [Execution и провайдеры](../configuration/execution.md).

Команда читает versioned execution request из stdin и выводит JSON result. Executable deployments требуют explicit bindings в `.embraion/execution.yaml`. Для adapter `litellm-loopback` установите optional extra `embraion[litellm]`. Он выполняет один bounded request в short-lived local child, используя только выбранный credential reference. Bindings объявляют exact upstream selector/provider, approved context boundary, source/trust/task ceilings и exact/anchored observed-model evidence. Request передаёт approved input в `payload.inputsByDeployment` для каждого candidate, привязанного к этому adapter на текущем execution host, включая fallback candidates. Cross-host и unbound handoff candidates не требуют adapter input. Отсутствующие required inputs и non-candidate input keys приводят к fail closed; selected input должен соответствовать provenance work item; worker text появляется только в result, но не в attempt evidence. Unbound host deployments возвращают `handoff-required`. Project acceptance остаётся отдельным от transport completion.

Snapshot cost из LiteLLM usage требует отдельно reviewed overlap evidence. Optional binding `usageSemanticsEvidence` содержит project-relative path `.embraion/usage-evidence/*.json` и SHA-256 digest. Checked-in sanitized JSON хранит schema version 1, `transport: litellm-responses`, exact LiteLLM `adapterVersion`, provider, selector, official `sourceUrl`, verification/validity timestamps, explicit input/output `usageSemantics` и representative `sampleUsage`. Adapter принимает evidence только если digest, running LiteLLM version (сейчас 1.77.7), provider, selector, dates и sample shape совпадают. Missing/expired/mismatched evidence оставляет usage semantics unknown, поэтому snapshot-derived cost остаётся unknown; execution при этом не блокируется. Provider-reported exact cost или LiteLLM normalized cost сохраняют собственный приоритет. Записывайте evidence только после review реального normalized Responses usage относительно official billing semantics provider; synthetic fixture не доказывает этот contract.

Без `healthObservations` в request health берётся из локального attempt ledger. Каждый validated attempt добавляется в `.embraion/state/execution-attempts.jsonl` (только redacted attempt fields; одна ротация при 1 MiB). Ошибка записи ledger выводит warning и сохраняет result.

```bash
embraion execute < request.json
```

### `embraion execution`

Сборка context envelopes, проверка readiness и просмотр attempt health. Правила отказов — в [Execution и провайдеры](../configuration/execution.md#context-envelopes).

```bash
embraion execution envelope --path src/module.py --task-file task.md < request.json > ready.json
embraion execution preflight --path src/module.py --task-file task.md --json < request.json
embraion execution preflight --deployment analysis-api
embraion execution health --json
```

`envelope` читает request из stdin и печатает его с `payload.inputsByDeployment` для каждого adapter-bound candidate. Читается только committed content (`--commit`, по умолчанию `HEAD`); `--path` можно повторять, `--task-file` обязателен, `--max-file-bytes`, `--max-total-bytes`, `--max-output-tokens` и `--payload-only` опциональны. Refusal завершается с кодом 2 и называет path и причину. `preflight` выполняет проверки согласованности request из `execute`, затем проверяет полноту binding, request ceilings, наличие credential и adapter preflight без provider call и без вывода credential, и завершается с кодом 1, если что-то не готово. `health` сводит attempt ledger по deployments.

### `embraion doctor`

Запустить framework/project diagnostics.

```bash
embraion doctor
embraion doctor --json
```

### `embraion status`

Показать launcher version, project pin, resolved runtime, cache и host projections.

```bash
embraion status
embraion status --json
```

### `embraion validate`

Валидировать framework schemas, catalogs, references, localization и другие deterministic contracts.

```bash
embraion validate
embraion validate --json
```

### `embraion validation`

Показать или выполнить project validation profiles из `.embraion/validation.yaml`:

```bash
embraion validation list
embraion validation list --json
embraion validation run fast
embraion validation run affected --json
embraion validation run full --run-id task-001
```

`validation run` выполняет commands из project root, сохраняет redacted evidence в `.embraion/state/validation/` и возвращает non-zero при fail profile. Empty profiles дают `skipped`. `--fail-fast` останавливает после первого failed command; `--timeout SECONDS` задаёт per-command timeout.

Structured validation profiles могут объявлять runtime parameters. Передавайте их повторяемым `--param NAME=VALUE`:

```bash
embraion validation run affected   --param base-ref=origin/main   --param head-ref=HEAD
```

Unknown parameters и missing required parameters fail-closed. Parameters могут проецироваться в command-line argument или environment child validation process согласно `.embraion/validation.yaml`.

`--run-id` прикрепляет profile result к active structured execution record, поэтому validation evidence не нужно вводить вручную повторно.

### `embraion cache`

Посмотреть или очистить isolated project runtimes.

```bash
embraion cache list
embraion cache list --json
embraion cache prune --older-than 90
embraion cache prune --older-than 90 --apply
```

Pruning работает как dry-run, пока не передан `--apply`.

## AI execution

### `embraion deployment`

Посмотреть registry `.embraion/deployments.yaml` consuming project:

```bash
embraion deployment list
embraion deployment list --json
embraion deployment show DEPLOYMENT_ID
embraion deployment show DEPLOYMENT_ID --json
```

Registry project-owned. EmbrAIon валидирует его, но не поставляет global model/provider catalog.

### `embraion route`

Разрешить host-default или project-overridden routing. EmbrAIon не выбирает модель, если проект явно не переопределил route/role.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
embraion route --host codex --route-class substantial --role reviewer --data PRIVATE
embraion route --task-class routine-review --access review
embraion route --task-class routine-review --escalation quality --justification "review evidence"
embraion route --validate
embraion route --audit-authority
```

Result сообщает `resolution: host-default` с `model: null`, когда host выбирает автоматически; `resolution: project-override` для direct project selector; `resolution: project-deployment`, когда routing ссылается на `.embraion/deployments.yaml`. Deployment routes также сообщают resolved provider, billing metadata и ordered fallback plan.

Task-class resolution собирает ordered effective candidates, отделяет availability fallback от explicit escalation и возвращает provenance. Authority audit ищет дубли concrete facts вне `.embraion/**`; проверенные generated projections исключаются.

### `embraion dispatch`

Создать bounded privacy-aware execution plan.

Каждый выбранный маршрут `critical` требует `--justification "конкретный риск"` у `route` и `dispatch`. Прямой запрос execution также требует непустого `justification` при `routeClass: critical`.

`dispatch --native-surface claude-agent` готовит полное временное описание агента с явно выбранными model/effort, но не запускает его. `--native-agent reviewer` выбирает native specialist независимо от `--role` — роли маршрутизации проекта. Загрузку описания и проверку фактических настроек см. в [Claude Code](../hosts/claude-code.md).

```bash
embraion dispatch   --task "Implement feature"   --role worker   --host codex   --route-class bounded-write   --data PRIVATE   --access write   --owned-path "src/**"
```

### `embraion context`

Выбрать project knowledge по task, role, privacy class и character budget:

```bash
embraion context build   --task "Review architecture boundaries"   --role architect   --data PRIVATE   --max-chars 20000
```

Canonical Project Contract Slots можно запросить явно:

```bash
embraion context slots
embraion context slots --json

embraion context build   --task "Review persistence compatibility"   --role reviewer   --slot persistence   --slot compatibility   --data PRIVATE
```

`--slot` repeatable и принимает `constitution`, `architecture`, `source-authority`, `compatibility`, `persistence`, `engineering-workflow`, `specification`. Explicit slot request обходит default task-term trigger, но всё ещё соблюдает project-configured role/privacy restrictions.

Saved record хранит provenance metadata и hashes, а не duplicated knowledge contents.

```bash
embraion context show CONTEXT_ID
```

### `embraion run`

Записать execution evidence:

Для `run start --route-class critical` передайте `--justification "конкретный риск"`. Причина сохраняется в записи маршрута запуска с маскированием секретов.

```bash
embraion run start   --run-id task-001   --task "Implement feature"   --role worker   --host codex   --route-class substantial   --data PRIVATE   --access write   --owned-path "src/**"   --substantial

embraion run complete task-001   --changed-path src/example.py   --validation fast=passed   --review passed   --outcome completed
```

Completed writable runs enforce owned scope, protected project paths и substantial-review policy.

### `embraion session`

Управлять normalized task/session state.

```bash
embraion session start --session-id task-001 --task "Implement feature"
embraion session show
embraion session set --state review --validation passed
```

## Engineering controls

### `embraion capabilities`

Показать необязательные декларации `.embraion/external-capabilities.yaml` и доступные свидетельства для хоста:

```bash
embraion capabilities --path . --host codex --json
embraion capabilities --path . --host codex --observation host-observation.json --json
```

Запись в инвентаре не устанавливает и не загружает возможность хоста. Локально можно проверить файлы управляемого пакета; предоставленные наблюдения хоста остаются сообщениями самого источника и не доказывают выполнение. См. [Внешние возможности](../configuration/capabilities.md).

### `embraion organization`

Проверить изменённые файлы по инкрементальным правилам организации кода:

```bash
embraion organization check --path . --base-ref main --head-ref HEAD --include-worktree --json
embraion organization check --path . --config .embraion/organization.yaml --json
embraion organization check --path . --require-config --json
```

Базовая ссылка отделяет старый долг и не освобождает новый код от правил. Без конфигурации проверка возвращает `skipped`; с `--require-config` она завершается ошибкой. См. [Организация кода](../configuration/organization.md).

### `embraion checkpoint`

Сохранить локальные ссылки для продолжения задачи и позже проверить их актуальность:

```bash
embraion checkpoint create task-42-step-1 --task-id task-42 --phase implementing --acceptance-path docs/task-42.md --path .
embraion checkpoint resume task-42-step-1 --path .
```

`create` также принимает `--decision-id`, `--next-action-id`, `--remaining-path`, `--context-id` и `--run-id`. Обе команды возвращают JSON. При продолжении проверяются pin и хеши знаний проекта, свидетельства и снимок Git, включающий HEAD, индекс и видимые рабочие файлы. Статус `valid`, `stale` или `missing` не даёт одобрения review или разрешения пользователя. См. [Продолжение задачи](../guides/task-continuity.md).

### `embraion knowledge`

Явно создать базовый снимок связей документов и исходных файлов, затем проверить изменения без записи:

```bash
embraion knowledge snapshot --path .
embraion knowledge audit --path .
```

Обе команды возвращают JSON. `snapshot` сохраняет локальные хеши в игнорируемом каталоге; `audit` отмечает изменённые или отсутствующие источники для проверки и не переписывает документы. См. [Поддержка знаний](../guides/knowledge-maintenance.md).

### `embraion enforcement`

Посмотреть project enforcement:

```bash
embraion enforcement status
embraion enforcement status --json
```

Проверить enabled gate относительно Git base ref:

```bash
embraion enforcement check --base-ref origin/main
embraion enforcement check --base-ref origin/main --run-id task-001 --json
```

С `--run-id` active runs получают validation evidence. Завершение run с passed review фиксирует HEAD, index и содержимое, modes и symlink targets tracked/nonignored untracked файлов. Gate требует совпадения снимка до и после validation; новый commit, staging или working edit требуют нового reviewed run. Legacy review без снимка не проходит gate. Нечитаемое состояние, submodules и неоднозначные directory aliases приводят к отказу. Завершённый run не изменяется и не завершается повторно. Все gates, включая external-review, отклоняют изменения Git-снимка во время validation; ignored runtime/build output в него не входит.

Check отклоняет mutations protected sources, требует real pass configured validation profile и проверяет review из execution evidence, когда `require-review` enabled.

Явно установить GitHub Actions CI surface:

```bash
embraion enforcement install   --surface github-actions   --validation-profile affected   --require-review
```

Ни `init`, ни `install`, ни `harness audit` не устанавливают enforcement workflow/native hook молча. Generated workflow возвращает non-zero при policy/validation/review failures. Чтобы gate стал обязательным для merge, настройте **EmbrAIon enforcement** как required status check в branch rules/ruleset.

### `embraion security`

Сканировать likely secrets и policy drift.

```bash
embraion security scan --path . --fail-on high
```

`--all-files` дополнительно проверяет исходники и другие текстовые файлы на private keys, access tokens и machine paths; см. [Security](../security.ru.md).

Redact likely credentials из diagnostic text:

```bash
embraion security redact --text "token=..."
```

### `embraion harness`

Аудит host agent/skill projection surfaces и metadata native hook capability:

```bash
embraion harness audit --host codex
embraion harness audit --host all
```

EmbrAIon сообщает hook availability, но не устанавливает executable project hooks молча.

### `embraion mcp`

Создать privacy-safe MCP inventory.

```bash
embraion mcp inventory
```

### `embraion worktree`

Управлять isolated Git worktrees.

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree gc --apply
embraion worktree salvage /path/to/worktree
```

GC удаляет только worktrees, созданные через `embraion worktree create`, с соответствующей записью ownership в Git-каталоге worktree. Требуются завершённые локальные run/session evidence, чистый интегрированный checkout, отсутствие блокировок и незавершённых Git-операций. Отсутствующее, повреждённое, активное, blocked или иное недоказанное состояние сохраняется. Старые и созданные вручную worktrees не удаляются.

### `embraion learning`

Записать evidence и управлять gated learning candidates.

```bash
embraion learning observe   --id repeated-review-gap   --kind repeated-failure   --target-type skill   --target-id review   --summary "Repeated review gap"

embraion learning propose repeated-review-gap
embraion learning approve repeated-review-gap
embraion learning promote repeated-review-gap
```

Learning evidence идентифицируется по run ID. Eval IDs сохраняют связи с runs: повтор eval без run не добавляет подтверждение, а последующая связь заменяет ранее учтённое eval-only подтверждение. Отдельные runs независимы даже при общей eval label. Непривязанные observations считаются один раз только при отсутствии идентифицированного evidence. Повторы идемпотентны; legacy associations консервативно восстанавливаются и сохраняются. Если новая корреляция опровергает независимость proposal/approval, состояние возвращается в observed/accumulating. Approval и promotion повторно проверяют пороги; promoted нельзя снова propose. Неуказанный target ID отсутствует; promotion-note включён в schema.

### `embraion eval`

Запустить behavioral evals и сравнить baselines.

```bash
embraion eval run --case reviewer-readonly --record execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
embraion eval skills run --suite evals/skills/code-organization.json --host codex --attempts 2 --output build/skill-evals.json --path . --route-class ordinary --data PRIVATE
```

`eval run --record` проверяет предоставленную запись выполнения и не запускает AI-хост. `eval skills run` создаёт новые сессии хоста (`--host codex`, `claude-code` или `portable` с `--host-command`) для базового и проверяемого вариантов навыка с учётом маршрутизации проекта и правил приватности. Необязательные `--model` и `--effort` должны совпадать с разрешёнными настройками проекта при явном маршруте. Отчёт отделяет наблюдаемое поведение от узкого свидетельства чтения файла навыка; ни одно из них само по себе не доказывает причину результата. См. [Живые проверки навыков](../guides/skill-evals.md).

## Help

### `embraion help`

Показать launcher-owned catalog или nested command help.

```bash
embraion help
embraion help cache prune
embraion --help
```

## Exit behavior

Commands используют non-zero exit codes при failed deterministic checks или invalid operations. Machine-readable output доступен там, где документирован `--json`.

## `embraion claude-native`

Настроить защитные hooks и просмотреть справочные данные событий Claude Code:

```bash
embraion install --host claude-code --component scoped-agents
embraion claude-native install-hooks --dry-run
embraion claude-native install-hooks
embraion claude-native status
```

Компонент `scoped-agents` требует `.embraion/claude-native.yaml`; обычная установка Claude по-прежнему включает только `agents` и `skills`. Определения выводятся из проектной маршрутизации. Начните новый Thread после установки и вызывайте точное имя определения, полученное от dispatch. См. [Claude Code](../hosts/claude-code.md).

`install-hooks` сохраняет остальные настройки и hooks в `.claude/settings.json`. `guard` читает JSON события PreToolUse из stdin: проверяет выбранные определения, запрещает подмену настроек и, при включённом read-policy, ограничивает чтение выбранных агентов. Он не ограничивает родительскую сессию, произвольных агентов или Bash. `observe` принимает PostToolUse/SubagentStop и сохраняет только идентификаторы и сообщённый effort в игнорируемом локальном состоянии. Эти две команды предназначены для hooks.

`status` различает установку файлов, записанные события и справочное сравнение `reported-effort`. Источник ввода помечен `evidence-origin: unverified-command-input`; `execution`, фактические `effort` и `model` остаются `unverified`; `callbacks: recorded` означает принятую запись. Тесты с искусственным JSON и локальные записи не доказывают передачу поля приложением, загрузку инструкций, завершение запуска или применение настроек.
