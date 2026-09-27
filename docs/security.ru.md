# Безопасность

EmbrAIon рассматривает execution permissions, data classification, provider eligibility, external integrations, generated configuration, credentials и mutation rights как enforceable engineering constraints.

Security policy находится в Core rules и project policy. Host/provider adapters реализуют mechanics, а deterministic tools проверяют configuration, external integrations и persisted evidence.

## Fail-closed behavior

Framework должен fail-closed, когда:

- task нельзя безопасно классифицировать;
- provider/execution path запрещён для данных;
- integration имеет неизвестный или неожиданно широкий access;
- secret попал в persisted configuration;
- generated configuration drift'ит от approved source;
- writable action превышает access profile или owned paths;
- protected project sources были бы изменены без требуемого path.

Security finding — evidence, а не разрешение ослабить controlling policy.

## Runtime redaction и environment

Runtime state применяет credential redaction до persistence.

Для child processes, запущенных EmbrAIon-owned adapters, framework строит minimal allowlisted environment вместо передачи всего host environment. Captured output redacted до сохранения evidence.

Host-native agents внешнего AI client остаются под environment/credential controls самого host. EmbrAIon не утверждает, что переопределяет host-owned security boundaries.

## External integrations

MCP и другая external server/tool configuration инвентаризируется отдельно от Core policy. Inventory хранит privacy-safe metadata и drift, а не secret values.

```bash
embraion security scan --path . --fail-on high
embraion mcp inventory
```

## Канонические data classes и compatibility aliases

Core policy использует только `PUBLIC`, `PRIVATE` и `CONFIDENTIAL`.

Проект может сохранить historical vocabulary на **execution boundary** через explicit `dataClassAliases` в `.embraion/execution.yaml`. Mapping `CONFIDENTIAL` к legacy label проекта не создаёт новый Core class и не ослабляет privacy policy.

Aliases существуют для compatibility, а не для создания слабых classifications.

## Project policy и enforcement

Project-owned source classes, privacy defaults, review rules и enforcement settings живут в `.embraion/policy.yaml`.

Green test/eval не может отменить privacy, protected-source, permission или security failure. Routing также не расширяет эти boundaries.

См. [Policy и protected paths](configuration/policy.md), [Execution и провайдеры](configuration/execution.md) и [Enforcement](guides/enforcement.md).
