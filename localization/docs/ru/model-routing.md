# Routing (Маршрутизация)

Routing в EmbrAIon классифицирует **работу и риск**, а не «мощность модели».

## Route classes

| Класс | Значение |
| --- | --- |
| `bounded-read` | узкое read-only исследование |
| `bounded-write` | механическое или жёстко ограниченное изменение |
| `ordinary` | обычная ограниченная инженерная работа |
| `substantial` | существенная работа и стандартный review |
| `complex` | cross-domain, lifecycle, concurrency или сложный review |
| `critical` | исключительный protected-decision risk |

Эти классы стабильны даже когда модели меняются.

## Host-default

Если проект ничего не переопределил, route разрешается как `host-default`: Codex/Copilot/Claude выбирает модель своей обычной политикой.

## Project override

Проект может зарегистрировать deployment в `.embraion/deployments.yaml` и сослаться на него из `.embraion/routing.yaml`.

```yaml
overrides:
  codex:
    routes:
      complex:
        deployment: complex-main
        effort: high
```

Role override имеет более высокий приоритет, чем route override.

## Routing не является вызовом провайдера

Routing отвечает: **что выбрать**.

Для host-native работы фактическое выполнение делает host.

Для `embraion execute` выбранный deployment должен иметь отдельный approved binding в `.embraion/execution.yaml`.

## Разговорная настройка

Пользователь может сказать AI:

> Настрой routing проекта: bounded оставь дешёвым, complex отправляй на сильный deployment, critical только для исключительных случаев.

AI должен изменить канонические `.embraion/` файлы, а не создавать ещё одну routing-таблицу в Markdown.
