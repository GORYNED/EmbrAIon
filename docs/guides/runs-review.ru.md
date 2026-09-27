# Runs и review

Structured run evidence полезно, когда проекту недостаточно conversational history — например для substantial changes, auditability, validation attachment или enforced review.

Для обычных lightweight tasks это опционально.

## Что записывает run

Structured run может хранить:

- task и role;
- выбранные host и route class;
- data class и access mode;
- owned paths;
- selected context identity;
- changed paths;
- attached validation evidence;
- review result;
- outcome и residual risk.

Knowledge content не копируется в run record. Context и validation прикрепляются через persisted identities/evidence, а не вводятся заново как неподтверждённые claims.

## Начать run

```bash
embraion run start   --run-id task-001   --task "Implement feature"   --role worker   --host codex   --route-class substantial   --data PRIVATE   --access write   --owned-path "src/**"   --substantial
```

Run фиксирует task contract: role, host, routing class, data class, access, owned paths и substantial-work intent.

## Прикрепить реальную validation

```bash
embraion validation run affected --run-id task-001
```

Validation evidence прикрепляется по ID вместо ручного повторения claim человеком или AI.

## Записать review и completion

После independent review:

```bash
embraion run complete task-001   --changed-path src/example.py   --validation affected=passed   --review passed   --outcome completed
```

Writable completion сверяет changed paths с owned scope и protected-path policy. Substantial writable work также должна удовлетворять applicable review contract.

## Что означает review

Полезный review должен быть независим от implementation step и проверять evidence, соответствующее риску изменения.

Для substantial work обычно проверяются:

- behavior и regressions;
- architecture/compatibility boundaries;
- protected/generated/external source handling;
- validation coverage;
- security/privacy implications;
- residual risk.

## Связь с GitHub enforcement

Когда `.embraion/policy.yaml` требует review, `embraion enforcement check` может использовать structured run evidence через `--run-id`, а explicitly installed GitHub Actions surface — текущие PR approvals.

См. [Enforcement](enforcement.md).
