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

Поддерживаемые components host-specific: Codex поддерживает `config`, `agents` и `skills`; GitHub Copilot и Claude Code — `agents` и `skills`; Portable использует `bundle`. Невыбранные components остаются user-owned и исключаются из obsolete-file handling.

Для зрелого Codex repo, который уже владеет `.codex/config.toml`, используйте merge ownership только для required `[agents]` keys EmbrAIon:

```bash
embraion install   --host codex   --component config   --config-mode merge
```

`--config-mode replace` остаётся default. Merge mode сохраняет project-owned `[agents]` keys и другие TOML tables и fail-closed, если файл нельзя безопасно merge.

Projection install и pruning отклоняют вложенные symlinks/junctions в managed paths, включая projection evidence под `.embraion/state`. Сам destination может оставаться alias каталога; targets ограничены его канонической границей.

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

### `embraion policy`

Посмотреть normalized source, validation, review и privacy policy:

```bash
embraion policy show
embraion policy show --json
```

### `embraion update`

Безопасно нормализует project configuration и атомарно синхронизирует framework pin с точным lock опубликованного release artifact.

```bash
embraion update
embraion update --framework-version <published-version>
```

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

### `embraion execute`

Про execution ownership, bindings, aliases, fallback и handoff см. [Execution и провайдеры](../configuration/execution.md).

Команда читает versioned execution request из stdin и выводит JSON result. Executable deployments требуют explicit bindings в `.embraion/execution.yaml`. Для adapter `litellm-loopback` установите optional extra `embraion[litellm]`. Он выполняет один bounded request в short-lived local child, используя только выбранный credential reference. Bindings объявляют exact upstream selector/provider, approved context boundary, source/trust/task ceilings и exact/anchored observed-model evidence. Request передаёт approved input в `payload.inputsByDeployment` для каждого candidate, привязанного к этому adapter на текущем execution host, включая fallback candidates. Cross-host и unbound handoff candidates не требуют adapter input. Отсутствующие required inputs и non-candidate input keys приводят к fail closed; selected input должен соответствовать provenance work item; worker text появляется только в result, но не в attempt evidence. Unbound host deployments возвращают `handoff-required`. Project acceptance остаётся отдельным от transport completion.

Snapshot cost из LiteLLM usage требует отдельно reviewed overlap evidence. Optional binding `usageSemanticsEvidence` содержит project-relative path `.embraion/usage-evidence/*.json` и SHA-256 digest. Checked-in sanitized JSON хранит schema version 1, `transport: litellm-responses`, exact LiteLLM `adapterVersion`, provider, selector, official `sourceUrl`, verification/validity timestamps, explicit input/output `usageSemantics` и representative `sampleUsage`. Adapter принимает evidence только если digest, running LiteLLM version (сейчас 1.77.7), provider, selector, dates и sample shape совпадают. Missing/expired/mismatched evidence оставляет usage semantics unknown, поэтому snapshot-derived cost остаётся unknown; execution при этом не блокируется. Provider-reported exact cost или LiteLLM normalized cost сохраняют собственный приоритет. Записывайте evidence только после review реального normalized Responses usage относительно official billing semantics provider; synthetic fixture не доказывает этот contract.

```bash
embraion execute < request.json
```

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

С `--run-id` active runs получают validation evidence. Для завершённого run gate читает review evidence и хранит новую validation в gate, не изменяя завершённый run. Ошибка новой validation по-прежнему блокирует gate.

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

Learning evidence идентифицируется по run ID: повторы и eval labels внутри одного run считаются один раз. Без run ID отдельный eval ID даёт одно подтверждение; observations без обоих ID считаются один раз на candidate. Повторы сохраняют confidence и состояние candidate. Legacy counts консервативно восстанавливаются по run IDs (или eval IDs, если runs отсутствуют), а не по прежнему счётчику вызовов.

### `embraion eval`

Запустить behavioral evals и сравнить baselines.

```bash
embraion eval run --case reviewer-readonly --record execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

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
