# Безопасность и поток данных

Эта страница отвечает на практический вопрос: **что может покинуть мой компьютер или репозиторий и в какой момент?**

Нормативные правила безопасности описаны в разделе [Security](security.md).

!!! tip "Простыми словами"
    EmbrAIon не является prompt proxy. Обычные разговоры с Codex/Copilot/Claude идут напрямую через соответствующий AI host. EmbrAIon управляет конфигурацией репозитория и детерминированными local/CI checks; provider calls происходят только через host или через явно настроенный provider-execution path.

## Поток данных в одном месте

| Действие | Что делает EmbrAIon | Граница network/data |
| --- | --- | --- |
| `pipx install embraion` / upgrade | Устанавливает CLI package | Package installer обращается к настроенной package infrastructure. Репозиторий проекта для установки не требуется. |
| `embraion init` | Создаёт принадлежащий проекту контракт `.embraion/` | Не вызывает model provider. |
| `doctor`, `status`, `context`, `policy`, `route` | Читает/валидирует локальную конфигурацию и metadata проекта | Эти команды не требуют model-provider call. `route` разрешает policy, а не обращается к модели. |
| `embraion install --host ...` | Генерирует host-native projection files | Генерация — операция над project/host configuration, а не provider inference call. |
| Обычная работа Codex/Copilot/Claude | AI host читает разрешённый ему repository/context | Именно **AI host** определяет свои network, retention и account policies. EmbrAIon не стоит между вами и host. |
| `embraion validation run ...` | Запускает настроенные команды проекта и записывает redacted evidence | Сам EmbrAIon не вызывает model provider. При этом команда проекта может иметь собственное обычное network behavior. |
| `embraion security scan` / `enforcement check` | Выполняет детерминированные проверки repository/configuration/evidence | Самой проверке EmbrAIon model-provider call не требуется. |
| `embraion execute` | Запускает опциональный bounded provider-neutral execution path | Может отправить разрешённый request/context явно настроенному adapter/provider в пределах project policy и binding ceilings. |
| Project runtime resolution | При необходимости разрешает точную опубликованную версию EmbrAIon, закреплённую проектом | Может скачать опубликованный package EmbrAIon в локальный version cache; это доставка framework, а не загрузка model context. |

## Загружает ли EmbrAIon мой репозиторий в GORYNED?

Обычная работа проекта не требует EmbrAIon-operated prompt proxy или cloud backend, а Core не предназначен для отправки содержимого репозитория в сервис GORYNED/EmbrAIon.

Сеть при этом могут использовать две другие системы:

1. **Ваш AI host** — Codex, Copilot, Claude Code или другая поддерживаемая поверхность работает по собственным product/account data policies.
2. **Явно настроенный execution provider** — `embraion execute` может вызвать объявленный adapter/provider согласно execution contract проекта.

Package installation/runtime resolution также могут обращаться к package infrastructure.

## Есть ли у EmbrAIon telemetry?

Да, но runtime telemetry — это **локальное operational state**, а не удалённый analytics service.

EmbrAIon дописывает privacy-safe runtime events в:

```text
.embraion/state/telemetry.jsonl
```

Локальные events могут содержать operational metadata: timestamps, session/dispatch IDs, role, host, выбранные model/effort, data class, access mode и owned-path count. Перед сохранением значения проходят redaction.

Runtime telemetry намеренно не содержит prompt content, source excerpts, diffs, raw reasoning и credential values. Telemetry writer дописывает данные в локальный state file и не является network sender. `.embraion/state/` — локальное состояние проекта, которое по умолчанию gitignored.

## Что сохраняется?

### Принадлежащая проекту versioned configuration

Репозиторий может коммитить:

- `.embraion/project.yaml`
- `.embraion/knowledge.yaml`
- `.embraion/policy.yaml`
- `.embraion/deployments.yaml`
- `.embraion/routing.yaml`
- `.embraion/validation.yaml`
- `.embraion/agents.yaml`
- опциональные `.embraion/execution.yaml` и `.embraion/pricing.yaml`

Secret values не должны храниться в этих файлах.

### Локальное runtime state

Runtime evidence/state хранится в `.embraion/state/`, caches — в `.embraion/cache/`; project initialization оставляет их локальными через project `.gitignore`.

Validation evidence может содержать redacted stdout/stderr tails, command identity, duration, exit state и evidence IDs.

Для provider-neutral execution attempt records спроектированы так, чтобы не сохранять raw credentials и raw prompt/context bytes.

## Как обрабатываются credentials?

Execution bindings ссылаются на credentials по имени, например:

```yaml
credentialRef: env:EXAMPLE_API_KEY
```

Само secret value не должно попадать в project configuration.

Для child processes, запускаемых EmbrAIon-owned adapters, framework формирует минимальный allowlisted environment и редактирует captured output перед сохранением.

Host-native AI clients остаются под контролем собственных environment/credential механизмов.

## Что означают PUBLIC / PRIVATE / CONFIDENTIAL?

Это Core data classes, ограничивающие eligibility и execution. Routing не может расширить privacy или permission boundaries.

Проект может сопоставить canonical class со старой project vocabulary на execution boundary, но alias не ослабляет исходный class.

## А локальные модели?

EmbrAIon **provider-neutral**, но это не означает автоматическую поддержку любого local model server.

Локальная модель может использоваться только через:

- AI host, который уже умеет с ней работать; или
- execution adapter/binding, который проект намеренно поддерживает и валидирует.

Нельзя считать Ollama, LM Studio или другой local server поддерживаемым только потому, что EmbrAIon model-agnostic.

## Связанные разделы

- [Модель безопасности](security.md)
- [Execution и провайдеры](configuration/execution.md)
- [Policy и защищённые пути](configuration/policy.md)
- [Validation и evidence](validation.md)
- [Enforcement](guides/enforcement.md)
