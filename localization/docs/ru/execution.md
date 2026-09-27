# Execution: выполнение через провайдеров

`embraion execute` — опциональный provider-neutral execution path.

Обычные разговоры с Codex/Copilot/Claude через него не проходят. Он нужен, когда проект хочет детерминированный API/provider lane с явными bindings и bounded fallback.

## Поток

```text
versioned request
  ↓
candidate deployments
  ↓
eligibility ceilings
  ↓
execution.yaml
  ↓
adapter
  ↓
provider/model
  ↓
normalized attempts / failures / usage / cost
```

## Что хранит execution.yaml

Binding может задавать:

- adapter и selector;
- `credentialRef` — только ссылку на secret, не значение;
- source IDs и trust levels;
- task/data aliases;
- timeout/options ceilings;
- expected provider/model evidence;
- usage semantics evidence.

## Data class aliases

Core знает только:

```text
PUBLIC
PRIVATE
CONFIDENTIAL
```

Для legacy vocabulary проект может объявить:

```yaml
dataClassAliases:
  CONFIDENTIAL: PROJECT_SECRET
```

Это **не новый Core data class**. Это compatibility mapping на execution boundary.

## Fallback и health

EmbrAIon сам ведёт bounded attempt loop для `execute`, нормализует failure, учитывает health и может перейти только к заранее разрешённому кандидату, не расширяя исходные privacy/access/source/task ceilings.

Если deployment не имеет executable binding, результат может быть `handoff-required`: выполнение должен продолжить host/project, а не неизвестный transport.

## Completion != acceptance

Успешный provider call ещё не означает, что результат корректен для продукта. Проект может отдельно требовать validation, acceptance, independent review и human merge.
