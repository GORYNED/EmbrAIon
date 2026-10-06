# Execution и провайдеры

Provider-neutral execution runtime EmbrAIon — **опциональная** возможность проекта.

Он отделён от обычных разговоров Codex/Copilot/Claude. Используйте его, когда проекту нужен versioned bounded request через reviewed provider bindings с нормализованными attempts, failures, health, usage и cost evidence.

## Когда это нужно

`.embraion/execution.yaml`, скорее всего, **не нужен**, если:

- весь reasoning/tool work выполняет сам AI host;
- host-default model selection достаточно;
- репозиторию нужны только knowledge, policy, agents, routing, validation и review.

Executable bindings нужны для контролируемого external/API lane, whose execution contract принадлежит проекту и runtime EmbrAIon.

## Execution path

```text
execution request
    ↓
candidate deployments
    ↓
project eligibility ceilings
    ↓
execution.yaml binding
    ↓
EmbrAIon adapter
    ↓
provider/model
    ↓
normalized attempt result
    ↓
bounded fallback / handoff
```

Request остаётся ограничен исходными data class, role, task class, source IDs, trust level, access mode, owned paths, timeout и candidate list. Fallback может выбрать другой заранее объявленный eligible candidate, но не расширяет ceilings.

## Минимальный binding

```yaml
# .embraion/execution.yaml
schemaVersion: 1

bindings:
  analysis-api:
    adapter: litellm-loopback
    selector: example/example-model
    credentialRef: env:EXAMPLE_API_KEY
    sourceIds:
      - Project
    trustLevels:
      - verified
    taskClasses:
      - substantial
    maxTimeoutSeconds: 300
    expectedProvider: example
    contextBoundary: ProjectContext/v1
```

Соответствующий deployment объявляется отдельно в `.embraion/deployments.yaml`.

Credentials указываются ссылкой, например `env:EXAMPLE_API_KEY`. Secret values не должны находиться в project configuration.

## Что может ограничивать binding

В зависимости от adapter/project:

- adapter и upstream selector;
- credential reference;
- approved source IDs и trust levels;
- task classes и aliases;
- data-class compatibility aliases;
- timeout и option ceilings;
- expected provider;
- context-boundary identity и context byte bound (`maxContextBytes`);
- exact/pattern-based observed model evidence;
- version-tied usage-semantics evidence.

Конкретные provider/model facts принадлежат проекту; generic execution mechanism остаётся в Core.

## Канонические data classes и aliases

Core использует только:

- `PUBLIC`
- `PRIVATE`
- `CONFIDENTIAL`

Зрелый проект может иметь historical vocabulary. Binding может сопоставить Core class project-specific capability label:

```yaml
bindings:
  legacy-api:
    adapter: litellm-loopback
    selector: example/example-model
    sourceIds: [Project]
    trustLevels: [verified]
    dataClassAliases:
      CONFIDENTIAL: PROJECT_SECRET
```

Это **не создаёт четвёртый Core data class**. Request остаётся `CONFIDENTIAL`; alias — compatibility mapping на project execution boundary.

## Attempts, fallback и health

EmbrAIon владеет bounded attempt loop для `embraion execute`.

Runtime:

1. валидирует versioned request;
2. сверяет кандидатов с deployment capabilities и execution binding ceilings;
3. учитывает переданные health observations, а без них — локальный attempt ledger;
4. вызывает только declared adapter/binding;
5. нормализует failure state;
6. записывает attempt без raw credentials или prompt/context bytes, а CLI добавляет его в attempt ledger;
7. делает fallback только когда failure eligible и mutation/termination evidence безопасно.

Billing failures, availability failures, transport failures, timeouts, cancellation и policy denial остаются разными normalized states.

Adapter не должен молча подменять model или создавать unbounded retry за пределами attempt accounting EmbrAIon.

## Handoff vs execution

Deployment может быть routable, но не executable через EmbrAIon.

Если у candidate нет executable binding, runtime может вернуть:

```text
handoff-required
```

Это означает, что execution должен продолжить выбранный host/project, а EmbrAIon не придумывает неподтверждённый transport.

## Transport completion не равно project acceptance

Успешный provider call доказывает только bounded transport result, но не корректность ответа для проекта.

Проект всё ещё может требовать:

- result-shape validation;
- project-specific acceptance;
- deterministic tests;
- independent review;
- human merge approval.

## Запуск

Для API run достаточно project configuration:

```bash
embraion execution preflight --path src/module.py --task-file task.md < request.json
embraion execution envelope --path src/module.py --task-file task.md < request.json > ready.json
embraion execute < ready.json
embraion execution health
```

Полная request/result schema — в [CLI reference](../reference/cli.md#embraion-execute).

## Context envelopes

`embraion execution envelope` читает request из stdin и печатает его с `payload.inputsByDeployment` для каждого candidate, привязанного к envelope adapter (сейчас `litellm-loopback`) на host запроса. Каждый input — один envelope, привязанный к `contextBoundary` binding и к work item, deployment, model, role, source IDs, access и aliased data class. Он содержит task text, resolved commit и по одной записи на файл: path, SHA-256, size и content.

Builder работает fail closed. Он читает только committed blobs на `--commit` (по умолчанию `HEAD`), никогда working tree, и отклоняет:

- absolute paths, paths с `..`, `:` или control characters, а также paths, отсутствующие в commit;
- symbolic links, submodules, directories, Git LFS pointers, binary и non-UTF-8 files;
- paths, совпадающие с `sources.protected` в `.embraion/policy.yaml`, и всегда `.git/`, `.embraion/state/`, `.embraion/cache/` и `.env` files;
- files с unknown data class или более чувствительные, чем request; class берётся из подходящей записи `.embraion/knowledge.yaml`, иначе из `privacy.default-class`;
- content или task text с credential material (patterns security scan или значение bound credential reference) либо с machine-local absolute path или file URL;
- больше 128 files, file больше `--max-file-bytes` (по умолчанию 262144) или context больше `--max-total-bytes` (по умолчанию 524288) или binding `maxContextBytes`;
- candidates, нарушающие request ceilings или не имеющие `contextBoundary`, и requests, которые уже передают payload input.

Refusal называет path и причину, но не content. `--payload-only` печатает только payload; `--max-output-tokens` задаёт `payload.maxOutputTokens`.

## Readiness без вызова

`embraion execution preflight` проверяет каждый adapter-bound candidate request из stdin: binding полный, request ceilings соблюдены, credential reference разрешается, adapter preflight проходит с payload запроса или, если его нет, с payload из `--path` и `--task-file`. Проверяется только наличие credential; значение не печатается и не сохраняется, provider не вызывается. `--deployment ID` (можно повторять) проверяет bindings и credentials без request. Cross-host и unbound candidates перечисляются как handoff. Команда завершается с кодом 1, если что-то не готово.

## Attempt ledger и health

`embraion execute` добавляет каждый validated attempt в `.embraion/state/execution-attempts.jsonl` под file lock. Запись — тот же redacted attempt object, что и в result, с run и work-item IDs; prompt, context, output и credential values в неё не попадают. При 1 MiB ledger один раз ротируется в `execution-attempts.1.jsonl`. Нечитаемые строки, включая обрезанную последнюю строку после прерванной записи, пропускаются и подсчитываются. Если request не передаёт `healthObservations`, `execute` берёт их из ledger, поэтому повторные operational failures понижают или пропускают deployment в пределах health window. Ошибка записи ledger выводит warning и сохраняет result.

`embraion execution health [--json]` показывает state по каждому deployment, недавние operational failures, cooldown и число нечитаемых строк.

## LiteLLM

Текущий optional loopback adapter использует extra `litellm`:

```bash
pip install "embraion[litellm]"
```

Проекты pin/validate совместимую комбинацию adapter/runtime. EmbrAIon остаётся provider-neutral: concrete selectors, bindings, credential references, source ceilings и evidence принадлежат проекту.

Для LiteLLM `payload.inputsByDeployment` (его строит `embraion execution envelope`) должен содержать bounded input для каждого candidate, привязанного к `litellm-loopback` на execution host запроса, включая external fallback candidates. Cross-host и unbound candidates не требуют external input. Unknown и non-candidate input keys приводят к fail closed. Каждый selected external input проверяется на approved boundary и исходный provenance work item до получения credentials и вызова transport. Core вычисляет adapter candidate scope внутри runtime; caller не может передать его. Существующие валидные optional inputs для handoff candidates остаются допустимыми.

Текущий LiteLLM adapter отклоняет явный `selected.effort` и непустой `selected.options` на preflight, до получения credentials и provider call. Проверенной трансляции этих настроек пока нет; option allowlist сам по себе не подтверждает поддержку transport. Запросы без этих настроек продолжают использовать bounded Responses transport.

Публичный execution result, включая CLI, сообщает об этом известном preflight refusal как `unsupported-capability` со статическим `diagnostic`. Credentials и provider call не вызываются. Произвольные тексты adapter exceptions и diagnostics не раскрываются.

## Связанные страницы

- [Как работает EmbrAIon](../getting-started/how-it-works.md)
- [Deployments проекта](deployments.md)
- [Model routing](../model-routing.md)
- [Pricing и стоимость](pricing.md)
- [Безопасность](../security.md)
