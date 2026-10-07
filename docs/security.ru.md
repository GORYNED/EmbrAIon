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

### Объявленные integrations

Проект может объявить ожидаемые MCP servers в опциональном `.embraion/integrations.yaml`, который проверяется по [schema](https://github.com/GORYNED/EmbrAIon/blob/main/schemas/integrations.schema.json). Без этого файла ничего не сравнивается, и scan работает как раньше.

```yaml
schema-version: 1
servers:
  - id: docs
    host: generic
    command: npx
    args: ["-y", "docs-server"]
    transport: stdio
    access: read-only
    env-vars: [DOCS_TOKEN]
```

Каждая запись указывает `id` server и `host`, в чьей configuration он находится: `generic` (`.mcp.json`), `vscode` (`.vscode/mcp.json`), `claude-code` (`.claude/settings.json` и `.claude/settings.local.json`) или `codex` (`.codex/config.toml`). Также она хранит `command`, `args`, `transport`, `access` (`read-only`, `workspace-write` или `external-execution`) и **имена** environment variables в `env-vars`; значения не хранятся никогда. Для URL server `command` не указывается. Host без явного type запускает command server через `stdio`, а URL server через `http`. По умолчанию записи переносимы: machine-absolute path в `command` или `args` считается finding. `portable: false` ставьте только для намеренно machine-local server, например из игнорируемого `.claude/settings.local.json`: он может использовать machine-absolute paths и не считается отсутствующим там, где не настроен, но найденная копия всё равно сравнивается с объявлением. Запись Codex с `enabled = false` только отключает server, поэтому она не сравнивается и не считается неожиданной; объявление для неё считается отсутствующим server. У других hosts нет ключа `enabled` для отдельного server, и их записи сравниваются всегда.

Два опциональных поля, `cwd` (рабочий каталог server) и `required` (`true` или `false`), сравниваются только тогда, когда объявление их задаёт; объявление без них сравнивается как раньше. Эти ключи есть только в configuration Codex, поэтому задавать их могут только записи с `host: codex`; для других hosts такое объявление считается невалидным. Для Codex `cwd` сравнивается со строкой `cwd`, а отсутствующий ключ считается незаданным; `required` сравнивается с булевым `required`, а отсутствующий ключ считается `false`. Расхождение — это finding `integration-mismatch`, где указаны поле, ожидаемое и наблюдаемое значения. Переносимая запись не должна объявлять machine-absolute `cwd`. Server Codex с `enabled = false` по-прежнему пропускается до сравнения этих полей.

Если файл существует, `embraion security scan` и `embraion doctor` сравнивают его с наблюдаемой configuration и сообщают каждое расхождение как high-severity finding `integration-drift`: объявленный, но не настроенный server (`integration-missing`), настроенный, но не объявленный server (`integration-unexpected`), server с другими command, arguments, transport, именами environment variables или объявленными `cwd` и `required` (`integration-mismatch`), непереносимая запись, невалидный файл объявлений или нечитаемая host configuration. Поэтому scan fails closed при `--fail-on high` по умолчанию. Findings никогда не выводят значения arguments, скрывают похожие на credentials значения command, а ошибки schema сообщают только местоположение. `access` — объявленная metadata; host configuration её не содержит, поэтому она не сравнивается.

## Findings сканирования

`embraion security scan` читает текстовые файлы проекта и сообщает каждый finding с категорией и severity:

| Категория | Severity | Что находит |
| --- | --- | --- |
| `private-key` | critical | заголовок PEM private key |
| `api-key` | high | key, secret, token или password с литеральным значением |
| `access-token` | high | token с префиксом provider без ключа перед ним: GitHub classic и fine-grained (`ghp_…`, `github_pat_…`), cloud access key IDs (`AKIA…`), ключи model providers (`sk-…`), Google API keys (`AIza…`) и Slack tokens (`xox…`) |
| `machine-path` | medium | путь к домашнему каталогу, например `/Users/<name>/`, `/home/<name>/` или `C:\Users\<name>\` (также с прямыми слешами или экранированными в JSON обратными) |
| `policy-drift` | medium | устаревшее имя data class, которое не объявлено execution alias |
| `integration-drift` | high | расхождение объявленных и наблюдаемых MCP servers; только при наличии `.embraion/integrations.yaml`, см. [Объявленные integrations](#integrations) |

Тело token должно содержать цифру, поэтому идентификаторы и заполнители в документации с этими префиксами не считаются tokens. Домашние каталоги CI runner, общие каталоги и имена-заполнители вроде `user`, `example` или `<name>` не считаются machine paths. Finding `machine-path` ниже порога по умолчанию `--fail-on high`; чтобы он приводил к ошибке, передайте `--fail-on medium`. `embraion security redact` и redaction evidence заменяют отдельный token с префиксом на `<REDACTED:access-token>`.

По умолчанию сканируются файлы Markdown, YAML, JSON, TOML, обычный текст, Python, PowerShell и shell, а также `.gitignore` и `.editorconfig`, вне служебных папок вроде `.git`, `.venv`, `node_modules` и `Library`. `--all-files` дополнительно читает каждый другой tracked или неигнорируемый untracked файл размером не больше 2 MiB и без байта NUL, например исходники C#, native-код или Unity assets; вне Git — каждый другой файл вне служебных папок. В этих файлах проверяются только `private-key`, `access-token` и `machine-path`: проверка `api-key` по ключевым словам срабатывала бы на обычные присваивания в коде. `--all-files` не добавляет файлы из Git submodules.

С `--all-files` сканирование читает `sources` из `.embraion/policy.yaml` проекта и отключает только проверку `machine-path` для содержимого, которое проект не может изменять. Сопоставление путей такое же, как в остальной policy (`fnmatch` и `**` для любого числа папок, включая ноль):

- другие текстовые файлы в `external` или `generated` по-прежнему проверяются на private keys и access tokens;
- файлы конфигурации и документации в `external` проходят все проверки, кроме `machine-path`, потому что принадлежат поставщику; в `generated` они проходят все проверки, потому что сгенерированную конфигурацию загружают инструменты, а исправляется она повторной генерацией из источника;
- конфигурация EmbrAIon в `.embraion/` и путь, который также совпадает с `canonical` или `protected`, проходят все проверки.

Поэтому секреты никогда не пропускаются. Вывод сообщает число файлов, для которых отключена проверка machine-path (`machine-path-waived-files` с `--json`). Если policy отсутствует, не читается или некорректна, ничего не отключается. Сканирование читает только явные списки `sources`, а не записи, выведенные из локальных ledgers проекций, поэтому результат не зависит от локального состояния. Без `--all-files` policy не используется, поэтому сканирование по умолчанию не меняется.

## Канонические data classes и compatibility aliases

Core policy использует только `PUBLIC`, `PRIVATE` и `CONFIDENTIAL`.

Проект может сохранить historical vocabulary на **execution boundary** через explicit `dataClassAliases` в `.embraion/execution.yaml`. Mapping `CONFIDENTIAL` к legacy label проекта не создаёт новый Core class и не ослабляет privacy policy.

Aliases существуют для compatibility, а не для создания слабых classifications.

## Project policy и enforcement

Project-owned source classes, privacy defaults, review rules и enforcement settings живут в `.embraion/policy.yaml`.

Green test/eval не может отменить privacy, protected-source, permission или security failure. Routing также не расширяет эти boundaries.

См. [Policy и protected paths](configuration/policy.md), [Execution и провайдеры](configuration/execution.md) и [Enforcement](guides/enforcement.md).
