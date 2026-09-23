# Безопасность

EmbrAIon рассматривает execution permissions, data classification, provider eligibility, external integrations, generated configuration, credentials и mutation rights как enforceable engineering constraints.

Security policy живёт в Core rules и routing. Host/provider adapters реализуют mechanics. `tools/security/` выполняет deterministic inspection, а `tools/mcp/` нормализует inventory внешних servers и drift.

Framework должен fail closed, если:

- задача не может быть безопасно классифицирована;
- provider не разрешён для соответствующих данных;
- integration имеет неизвестный или неожиданно расширенный access;
- secret попал в persisted configuration;
- generated configuration расходится с approved source;
- writable action выходит за access profile.

Security findings являются evidence, а не разрешением ослаблять управляющую policy.
