# Маршрутизация

Routing EmbrAIon model-agnostic.

Он классифицирует **работу и риск**, а не силу модели, цену, provider или marketing tier. Model availability меняется быстро; project architecture и safety constraints — значительно медленнее.

![Маршрутизация моделей](assets/diagrams/ru/12-model-routing.svg){ loading=lazy }

## Route classes

Канонические route classes:

| Route class | Значение |
| --- | --- |
| `bounded-read` | Узкое read-only discovery или research |
| `bounded-write` | Механическое или жёстко ограниченное writable изменение |
| `ordinary` | Ограниченная обычная инженерная работа |
| `substantial` | Существенная инженерная работа и стандартный review |
| `complex` | Cross-domain, lifecycle, concurrency или сложный review |
| `critical` | Исключительный protected-decision risk |

Это стабильный framework vocabulary. Класс не означает, что одна конкретная модель навсегда является «complex model» или «critical model».

Routing оценивается вместе с независимыми dimensions:

- role;
- data class;
- access mode;
- owned paths;
- project deployment capabilities;
- validation/review requirements.

## Поведение по умолчанию

Без project override routing разрешается как `host-default`. Host отвечает за доступные модели и automatic/default model policy.

```bash
embraion route --host codex --route-class substantial --data PRIVATE
```

Default result не содержит framework-selected model:

```json
{
  "host": "codex",
  "route": "substantial",
  "role": null,
  "resolution": "host-default",
  "model": null,
  "effort": null,
  "options": {},
  "data": "PRIVATE"
}
```

Новые модели могут появляться в host без новой release EmbrAIon.

## Optional project overrides

Проект может объявить reusable choices в `.embraion/deployments.yaml` и сослаться на них из `.embraion/routing.yaml`:

```yaml
# .embraion/deployments.yaml
providers:
  example:
    display-name: Example Provider

deployments:
  complex-main:
    host: codex
    provider: example
    model: any-host-model-selector
    efforts: [medium, high]
    default-effort: high
```

```yaml
# .embraion/routing.yaml
overrides:
  codex:
    routes:
      complex:
        deployment: complex-main
        effort: high
    roles:
      reviewer:
        deployment: complex-main
        options:
          thinking: maximum
```

Registry project-owned, а не Core model catalog. Model/provider strings намеренно open-ended.

Для простых choices поддерживаются direct `model`, `effort`, `options` overrides.

Resolution precedence:

1. role override, если role передана;
2. route override;
3. host default/automatic selection.

Role override merge поверх route override и может заменить только нужные поля.

## Routing не является provider execution

Routing отвечает на вопрос **что выбрать**, но сам не создаёт provider call.

Для host-native work AI host использует resolved project contract и сам выполняет execution.

Для `embraion execute` выбранный deployment должен иметь approved `.embraion/execution.yaml` binding. Runtime выполняет bounded candidate list и eligible fallback в исходных request ceilings.

См. [Как работает EmbrAIon](getting-started/how-it-works.md) и [Execution и провайдеры](configuration/execution.md).

## AI-First configuration

Каждая installed host projection содержит reusable `routing-configuration` skill. Он объясняет AI, что routing overrides принадлежат `.embraion/routing.yaml`, а не generated host files или arbitrary docs.

Ожидаемый UX — conversational:

> Настрой EmbrAIon routing для репозитория, используя реально доступные модели. Оставь host-default там, где explicit choice не нужен. Model, effort и host-specific overrides записывай только в project routing/deployment configuration. Не ослабляй privacy, access, ownership, validation или review policy.

AI должен менять только project-owned configuration и проверять affected routes.

## Что валидирует EmbrAIon

Детерминированно проверяются:

- route-class и data-class names;
- project-override structure;
- role/route precedence;
- deployment existence/enabled state;
- host matching;
- supported effort;
- declared data/role/access/task capabilities;
- access/privacy policy независимо от model identity.

Execution host остаётся authoritative в вопросе, доступен ли opaque selector/options текущему аккаунту.

## Host-specific setup

См. [Разговорную настройку](configuration/ai-hosts.md) для Codex, GitHub Copilot и Claude Code.
