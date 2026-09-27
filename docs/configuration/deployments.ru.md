# Deployments проекта

`.embraion/deployments.yaml` — reusable execution registry конкретного consuming project.

EmbrAIon Core остаётся model-agnostic: он не поставляет актуальный model catalog и не решает, какого vendor/model должен использовать проект. Registry нужен, чтобы проект дал имена конкретным execution choices, которыми уже владеет, и переиспользовал эти имена в routing.

## Базовая конфигурация

```yaml
providers: {}
deployments: {}
```

Пустой registry означает, что routing может использовать host-default selection или direct model overrides.

## Reusable deployments

```yaml
providers:
  example:
    display-name: Example Provider
    homepage: https://example.com

deployments:
  native-main:
    host: codex
    provider: example
    model: example-model-selector
    enabled: true
    efforts: [medium, high]
    default-effort: medium
    billing:
      mode: subscription
      plan: Example Plan
    capabilities:
      data-classes: [PUBLIC, PRIVATE]
      access-modes: [read-only, workspace-write]
      roles: [worker, reviewer]
      task-classes: [substantial, complex]
    options:
      example-option: true
```

Model/provider strings принадлежат проекту. EmbrAIon валидирует структуру и deterministic eligibility, но не утверждает, что selector глобально доступен.

Deployment требует `host` и `model`. Также он может объявлять provider identity, enabled state, supported/default effort, billing metadata, eligibility capabilities, host options и non-secret metadata.

Не помещайте credentials, tokens, API keys или secret environment values в этот файл.

## Routing по deployment id

```yaml
overrides:
  codex:
    routes:
      substantial:
        deployment: native-main
        effort: medium
```

Resolved route сообщает deployment id, provider, model, effort, billing metadata и merged options.

## Fallback chains

```yaml
overrides:
  codex:
    routes:
      substantial:
        deployment: native-main
        fallbacks:
          - deployment: native-backup
            effort: low
```

Fallbacks в `.embraion/routing.yaml` — это **selection plan**. EmbrAIon проверяет, что каждый deployment существует, enabled, принадлежит выбранному host и удовлетворяет объявленным route/data/role/access/effort capabilities.

Project task-class profiles могут объединять host-local selections с явно упорядоченными candidates других hosts. Межхостовой candidate требует handoff и новой privacy/access проверки. Availability fallback не повышает complexity; quality и critical escalation выбираются отдельно и явно.

Дальнейшее зависит от execution lane:

- для **host-native work** AI host фактически запускает выбранный model/tool workflow;
- для **provider-neutral execution** caller может передать bounded candidate set в `embraion execute`; EmbrAIon владеет attempt loop, failure normalization, health-aware ordering и eligible fallback в исходных request ceilings.

Deployment — не transport. Для provider invocation нужен approved binding в `.embraion/execution.yaml`.

## Fail-closed

Deployment route отклоняется, если deployment отсутствует/disabled, относится к другому host, ссылается на undeclared provider, требует unsupported effort, нарушает capabilities или образует duplicate/self fallback.

## Посмотреть registry

```bash
embraion deployment list
embraion deployment list --json
embraion deployment show native-main
embraion deployment show native-main --json
```

См. [Model routing](../model-routing.md), [Execution и провайдеры](execution.md) и [Pricing и стоимость](pricing.md).
