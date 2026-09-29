# Добавить EmbrAIon в проект

Начните внутри существующего репозитория или пустого каталога проекта:

```bash
cd MyProject
embraion init
```

Команда создаёт каноническую конфигурацию проекта:

```text
.embraion/
├── .gitignore
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── deployments.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

У каждого файла есть своя зона ответственности:

- `project.yaml` — identity проекта, framework pin и открытые capability metadata;
- `knowledge.yaml` — ссылки на project knowledge;
- `policy.yaml` — source classes, privacy, review и enforcement policy;
- `deployments.yaml` — повторно используемые model/provider choices проекта, если они нужны;
- `routing.yaml` — опциональные host-specific overrides model/effort/options;
- `validation.yaml` — исполняемые validation profiles проекта;
- `agents.yaml` — project-specific agent declarations;
- `.gitignore` — оставляет `.embraion/state/` и `.embraion/cache/` локальными.

## Проверьте проект

```bash
embraion status
embraion doctor
```

Исправьте ошибки конфигурации до установки host projections.

## Установите AI-клиент, который используете

Codex:

```bash
embraion install --host codex --destination .
```

GitHub Copilot:

```bash
embraion install --host copilot --destination .
```

Claude Code:

```bash
embraion install --host claude-code --destination .
```

Portable bundle:

```bash
embraion install --host portable --destination vendor/embraion
```

В одном репозитории можно установить несколько projections.

Если репозиторий уже владеет host configuration, agents или skills, используйте более безопасный пошаговый процесс из [Подключения существующего репозитория](existing-repository.md), а не перезаписывайте файлы вслепую.

## Настройте проект одним запросом

Откройте репозиторий в AI-хосте и напишите:

> Настрой EmbrAIon для этого проекта.

Канонический Core skill `project-bootstrap` сначала исследует репозиторий, затем связывает существующие knowledge documents, сохраняет policy и настраивает реальные validation commands. Нет необходимости вручную собирать YAML. Core roles обычно достаточно: `agents: []` не отключает их. Routing может остаться `overrides: {}` и host-default.

Bootstrap проверяет результат, сообщает skips, infrastructure limitations и неоднозначности. Он сохраняет намеренные настройки при повторном запуске и не придумывает источники истины или команды. Затем задавайте обычные инженерные задачи. См. [Project Bootstrap](../configuration/bootstrap.md).

## Дальше

- Новый/небольшой репозиторий: [Настройка EmbrAIon](../configuration/index.md)
- Зрелый репозиторий: [Подключение существующего репозитория](existing-repository.md)
- Готовы работать: [Первая задача для AI](first-ai-task.md)
