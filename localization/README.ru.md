<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System от GORYNED" width="100%">
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <strong>Русский</strong> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

# EmbrAIon

**AI-First Engineering System [от GORYNED](https://goryned.com)**

> Where sparks become AI-built products

> Это перевод канонического английского README. Если версии расходятся, источником истины является английская версия.

EmbrAIon — переносимая AI-First Engineering System для организации разработки программного обеспечения с ИИ: с явными ролями, переиспользуемыми навыками, рабочими процессами, маршрутизацией моделей, контролем доступа, валидацией, независимым ревью, безопасностью, обучением системы и настройками конкретного проекта.

EmbrAIon находится выше конкретных языков программирования и фреймворков. Unity/C#-проект, Python-сервис, веб-приложение или любой другой программный репозиторий могут использовать одно и то же ядро и добавлять только свои проектные знания и правила.

## Что делает EmbrAIon

EmbrAIon разделяет инженерную систему на независимые части:

- **Агент (`Agent`)** — кто отвечает за работу: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher или Steward.
- **Навык (`Skill`)** — как выполнять повторяемый тип работы.
- **Правило (`Rule`)** — что обязательно, запрещено или защищено.
- **Рабочий процесс (`Workflow`)** — в каком порядке объединяются capabilities.
- **Маршрутизация (`Routing`)** — какой уровень доступа, класс модели, host и provider могут выполнять задачу.
- **Адаптер (`Adapter`)** — как канонические capabilities представляются в Codex, Copilot, Claude Code, у API-провайдеров или в нейтральном Portable-пакете.
- **Инструмент (`Tool`)** — детерминированная исполняемая логика: валидация, security scan, управление worktrees, синхронизация и диагностика.
- **Поведенческая оценка (`Eval`)** — проверка того, действительно ли AI следует заданному инженерному контракту.

`core/catalog.yaml` — индекс обнаружения capabilities. Вместо загрузки всего framework для каждой задачи EmbrAIon может загружать только те capabilities, чьи triggers соответствуют текущей работе.

## Классы данных

EmbrAIon использует три канонических класса данных:

| Класс | Значение |
| --- | --- |
| `PUBLIC` | Публичная информация, которую можно передавать разрешённым внешним системам |
| `PRIVATE` | Внутренняя или проприетарная информация проекта; внешнее использование требует явно разрешённого route |
| `CONFIDENTIAL` | Самый защищённый уровень; внешняя передача запрещена, если конкретный route явно её не разрешает |

Неизвестная или неоднозначная классификация приводит к fail-closed. Выбор модели никогда не расширяет разрешённый доступ или privacy eligibility.

## Поддерживаемые адаптеры

Сейчас поддерживаются:

- **Codex** — каталог моделей, сопоставление model/effort с route и генерация project agents/config.
- **GitHub Copilot** — рекомендательный каталог моделей и генерация custom-agent projection.
- **Claude Code** — каталог моделей Claude и генерация subagent projection.
- **Portable** — нейтральный к host устанавливаемый пакет capabilities.
- **Providers** — прямые каталоги API-моделей OpenAI, Anthropic, Google и DeepSeek, а также transport metadata.

Core остаётся независимым от конкретных моделей. Актуальные model identities и host selectors находятся только в adapters.

## Установка

### Требования

- Python 3.11+
- Git
- локальный clone этого репозитория

Текущая предстабильная версия CLI устанавливается из исходников.

### 1. Клонировать EmbrAIon

```bash
git clone https://github.com/GORYNED/EmbrAIon.git
cd EmbrAIon
```

### 2. Создать виртуальное окружение

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### 3. Проверить EmbrAIon

```bash
embraion validate
embraion doctor
```

## Подключение EmbrAIon к проекту

Создайте project overlay:

```bash
cd /path/to/your/project
embraion init --name MyProject
```

Появится:

```text
.embraion/
└── project.yaml
```

Project overlay фиксирует версию EmbrAIon и позволяет объявлять project-specific capabilities без изменения Core.

### Установить projection для нужного host

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

Portable-пакет:

```bash
embraion install --host portable --destination ./vendor/embraion
```

Используйте `--force` только тогда, когда намеренно заменяете уже существующую generated projection.

## Как задача проходит через EmbrAIon

Для substantial-задачи поток выглядит примерно так:

```text
Цель пользователя
  ↓
Project overlay + каталог Core
  ↓
Нужные rules / agents / skills / workflows
  ↓
Класс данных + профиль доступа + сложность
  ↓
Адаптер host + route модели
  ↓
Реализация
  ↓
Валидация
  ↓
Независимое ревью
  ↓
Финальная проверка
  ↓
Передача результата / human merge gate
```

Для substantial specification-driven работы рекомендуется Spec Kit как независимый companion. Он помогает со спецификацией и планированием, но не заменяет Core rules, project truth, compatibility contracts или validation evidence.

## CLI

### Framework и проект

```text
embraion init
embraion install
embraion update
embraion sync
embraion validate
embraion doctor
```

### Маршрутизация и runtime state

Разрешить route:

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

Создать bounded dispatch plan:

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path "src/**"
```

Writable dispatch требует явных owned paths и не разрешается из стабильной ветки `main`/`master`. План и privacy-safe routing telemetry записываются в `.embraion/state/`.

Запустить нормализованный session state:

```bash
embraion session start \
  --session-id task-001 \
  --task "Implement feature" \
  --role lead \
  --host codex \
  --access plan
```

Посмотреть или обновить состояние:

```bash
embraion session show
embraion session set --state review --validation passed
```

Сам host adapter выполняет фактический AI execution. EmbrAIon отвечает за канонический routing, сгенерированные определения агентов, границы доступа и ownership, dispatch plans, нормализованное состояние и privacy-safe operational telemetry.

### Безопасность

```bash
embraion security scan --path .
```

Scanner проверяет высокорисковые проблемы конфигурации, например возможные встроенные credentials и policy drift.

### MCP inventory

```bash
embraion mcp inventory
```

Команда создаёт нормализованный privacy-safe inventory в `.embraion/state/`. Имена environment variables могут сохраняться, но secret values намеренно не записываются.

### Worktrees

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree salvage /path/to/worktree
```

`gc` по умолчанию работает как dry run и рассматривает только worktrees, для которых доказано, что они clean, unlocked и безопасны для удаления. Для фактического удаления необходимо явно добавить `--apply`.

### Обучение системы

Записать повторяющееся evidence:

```bash
embraion learning observe \
  --id repeated-review-gap \
  --kind repeated-failure \
  --target-type skill \
  --target-id review \
  --summary "Repeated review gap"
```

Promotion проходит через обязательные gates:

```text
наблюдение → накопление evidence → предложение → одобрение → promotion
```

Promotion никогда не изменяет Core автоматически. Даже одобренный candidate должен пройти обычный reviewed engineering change.

### Поведенческие evals

Запустить eval case:

```bash
embraion eval run \
  --case reviewer-readonly \
  --record path/to/execution-record.json
```

Создать baseline и сравнить результат:

```bash
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

## Генерация adapter projections

Сгенерировать все поддерживаемые projections, не устанавливая их в проект:

```bash
embraion sync --host all --output build/generated --force
```

Generated outputs являются одноразовыми projections. Каноническая policy всегда остаётся в `core/`.

## Структура репозитория

```text
brand/         бренд, тексты и README assets
core/          канонические rules, agents, skills, workflows, routing, knowledge
adapters/      интеграции Codex, Copilot, Claude Code, Portable и providers
tools/         CLI, runtime, learning, security, MCP, worktree, validation, sync
schemas/       machine-readable contracts
templates/     шаблоны project overlay
docs/          каноническая английская документация
localization/  русская и китайская локализации
tests/         детерминированные unit/integration tests
evals/         behavioral cases, baselines, graders, fixtures и reports
examples/      примеры интеграции
```

## Валидация и CI

Каждый push и pull request должен запускать:

- schema и catalog validation;
- проверку parity локализаций;
- unit и integration tests;
- security scan;
- генерацию всех host projections;
- smoke tests поведенческих evals.

Tagged releases создают архивы source, Codex, Copilot, Claude Code и Portable.

## Документация

Каноническая документация: [docs/](../docs/README.md)

Русская документация: [localization/docs/ru/](docs/ru/README.md)

Китайская документация: [localization/docs/zh-CN/](docs/zh-CN/README.md)

## Лицензия и бренд

Исходный код и документация EmbrAIon распространяются по [MIT License](../LICENSE), если для конкретного файла или каталога явно не указано иное.

Названия **EmbrAIon** и **GORYNED**, логотипы, текстовые логотипы, визуальные знаки и файлы в `brand/assets/` **не предоставляются по MIT**. MIT License не предоставляет права на товарные знаки или фирменный стиль. Каноническая политика: [TRADEMARKS.md](../TRADEMARKS.md).

## Текущий статус

EmbrAIon находится в **предстабильной** стадии. Архитектура и первая исполняемая версия CLI уже существуют, но публичный compatibility contract ещё не зафиксирован окончательно.

До первой стабильной версии ещё могут меняться каталоги моделей, generated host projections, покрытие validation, security rules, установка и release packaging.

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>Последнее обновление: 2026-09-23 20:30 UTC</sub>
