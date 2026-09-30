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
- context-boundary identity;
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
3. учитывает health observations;
4. вызывает только declared adapter/binding;
5. нормализует failure state;
6. записывает attempt без raw credentials или prompt/context bytes;
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

```bash
embraion execute < request.json
```

Полная request/result schema — в [CLI reference](../reference/cli.md#embraion-execute).

## LiteLLM

Текущий optional loopback adapter использует extra `litellm`:

```bash
pip install "embraion[litellm]"
```

Проекты pin/validate совместимую комбинацию adapter/runtime. EmbrAIon остаётся provider-neutral: concrete selectors, bindings, credential references, source ceilings и evidence принадлежат проекту.

Для LiteLLM `payload.inputsByDeployment` должен содержать bounded input для каждого candidate, привязанного к `litellm-loopback` на execution host запроса, включая external fallback candidates. Cross-host и unbound candidates не требуют external input. Unknown и non-candidate input keys приводят к fail closed. Каждый selected external input проверяется на approved boundary и исходный provenance work item до получения credentials и вызова transport. Core вычисляет adapter candidate scope внутри runtime; caller не может передать его. Существующие валидные optional inputs для handoff candidates остаются допустимыми.

Текущий LiteLLM adapter отклоняет явный `selected.effort` и непустой `selected.options` на preflight, до получения credentials и provider call. Проверенной трансляции этих настроек пока нет; option allowlist сам по себе не подтверждает поддержку transport. Запросы без этих настроек продолжают использовать bounded Responses transport.

Публичный execution result, включая CLI, сообщает об этом известном preflight refusal как `unsupported-capability` со статическим `diagnostic`. Credentials и provider call не вызываются. Произвольные тексты adapter exceptions и diagnostics не раскрываются.

## Связанные страницы

- [Как работает EmbrAIon](../getting-started/how-it-works.md)
- [Deployments проекта](deployments.md)
- [Model routing](../model-routing.md)
- [Pricing и стоимость](pricing.md)
- [Безопасность](../security.md)
