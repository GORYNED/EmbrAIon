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

## Model routing опционален

EmbrAIon model-agnostic. Если default/automatic model choice AI-клиента подходит, ничего настраивать не нужно.

Если проекту нужен явный routing, попросите AI-клиент записывать только подтверждённые selectors в `.embraion/routing.yaml`. Не ослабляйте privacy, access, protected-source, validation или review policy ради совместимости с моделью.

## Добавьте project knowledge

Факты проекта должны жить вместе с репозиторием. Например:

```text
knowledge/
├── project.md
└── architecture.md
```

Сошлитесь на них из `.embraion/knowledge.yaml`. См. [Знания проекта](../configuration/knowledge.md).

## Добавьте реальную validation как можно раньше

Стандартные validation profiles пустые. До того как считать validation evidence, добавьте реальные команды репозитория в `.embraion/validation.yaml`.

См. [Настройку валидации](../configuration/validation.md).

## Дальше

- Новый/небольшой репозиторий: [Настройка EmbrAIon](../configuration/index.md)
- Зрелый репозиторий: [Подключение существующего репозитория](existing-repository.md)
- Готовы работать: [Первая задача для AI](first-ai-task.md)
