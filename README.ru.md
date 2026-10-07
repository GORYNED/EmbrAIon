<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System от GORYNED" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <strong>Русский</strong>
</p>

# EmbrAIon

**AI-First Engineering System [от GORYNED](https://goryned.com)**

**EmbrAIon хранит правила AI-разработки вместе с репозиторием — знания проекта, защищённые пути, routing, validation, review и evidence — вместо того, чтобы размазывать их по промптам и настройкам AI-клиентов.**

Один и тот же контракт проекта можно использовать с Codex, GitHub Copilot, Claude Code или host-neutral Portable bundle.

## Когда это нужно

EmbrAIon полезен, когда важные правила проекта уже не помещаются в один prompt, несколько AI-клиентов должны следовать одним правилам, protected paths и validation нужны как реальные проверки, а архитектурные знания должны переживать новые сессии и смену модели.

> **Ментальная модель:** EmbrAIon — операционная система AI-разработки, а `.embraion/` — Settings конкретного репозитория.

## Быстрый старт

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
```

Откройте репозиторий в своём AI-клиенте и напишите:

> Настрой EmbrAIon для этого проекта.

Lead использует канонический Core skill Project Bootstrap: изучает существующие источники истины, связывает knowledge, сохраняет safety policy и находит реальные validation commands. Routing остаётся необязательным. См. [Project Bootstrap](docs/configuration/bootstrap.ru.md).

Затем работайте обычно:

> Исправь retry flow и добавь regression coverage.

Для другого хоста замените `codex` на `copilot` или `claude-code`.

Lead читает контракт проекта, автоматически выбирает специалистов, независимо классифицирует каждое assignment, разрешает routing и применяет настроенные model/effort через поддерживаемые native capabilities. Он собирает пропорциональные validation/review, интегрирует результаты и сохраняет окончательные полномочия.

## Документация

Канонический сайт: **https://embraion.goryned.com/**

Рекомендуемый путь:

1. [Зачем нужен EmbrAIon?](docs/getting-started/what-is-embraion.ru.md)
2. [EmbrAIon за 60 секунд](docs/getting-started/in-60-seconds.ru.md)
3. [Песочница за пять минут](docs/getting-started/playground.ru.md)
4. [Установка](docs/getting-started/installation.ru.md)
5. Выберите путь репозитория:
   - [Добавить EmbrAIon в проект](docs/getting-started/first-project.ru.md) — для нового или простого репозитория.
   - [Подключить существующий репозиторий](docs/getting-started/existing-repository.ru.md) — для зрелого проекта с существующей конфигурацией AI-клиента.
6. [Первая задача для AI](docs/getting-started/first-ai-task.ru.md)
7. [Как это работает](docs/getting-started/how-it-works.ru.md)

Если непонятен термин или нужен прямой ответ, откройте [Глоссарий](docs/glossary.ru.md), [FAQ](docs/faq.ru.md) или [Безопасность и поток данных](docs/security-data-flow.ru.md).

Для подробной инженерной модели см. [Engineering Model Deep Dive](docs/reference/engineering-model.ru.md).

## Новое в 0.30

- Необязательная секция `check` в [policy](docs/configuration/policy.ru.md) объявляет, какие режимы organization check (`full`, `compare` или оба), порог security и область сканирования использует [`embraion check`](docs/reference/cli.ru.md#embraion-check), а переиспользуемый action `actions/check` запускает его после setup action, поэтому [CI проекта](docs/reference/runtime-version-resolution.ru.md) обходится без флагов проекта.

## Новое в 0.29

- [Записи архитектурных решений](docs/configuration/decisions.ru.md) стали частью процесса: необязательный слот `decisions` и `.embraion/decisions.yaml` описывают, какие изменения архитектурные; `embraion decisions check` (его запускает и `embraion check --base-ref`) требует запись или `Decision-Waiver`, а `embraion adr new` создаёт следующую пронумерованную запись.

## Новое в 0.28

- [`embraion check`](docs/reference/cli.ru.md#embraion-check) запускает все проверки, которые выбирает конфигурация проекта, поэтому [CI проекта](docs/reference/runtime-version-resolution.ru.md) обходится одним шагом; `projection.<host>.components` в [policy](docs/configuration/policy.ru.md) объявляют проверяемые проекции.
- Необязательная секция [`privacy.sources`](docs/configuration/policy.ru.md) задаёт data class каждого source ID, и execution requests, называющие source, отклоняются, если их класс ниже.

## Новое в 0.27

- [CI проекта](docs/reference/runtime-version-resolution.ru.md) может устанавливать закреплённый релиз переиспользуемым action `GORYNED/EmbrAIon/actions/setup`, а `embraion framework pin` выводит точный pin; [enforcement](docs/guides/enforcement.ru.md) генерирует workflow с этим action.
- Проекции переносят собственные skills проекта из [`.embraion/skills/`](docs/configuration/project-files.ru.md), triggers и outputs специалистов, ссылки на Core с тегом релиза и опциональный компонент [hooks Claude Code](docs/hosts/claude-code.ru.md); файлы из журналов проекций считаются generated sources.
- [Объявленные integrations](docs/security.ru.md) в `.embraion/integrations.yaml` показывают расхождения между ожидаемыми и фактическими MCP-серверами.
- `embraion validate` проверяет собственные `.embraion/*.yaml` проекта, а `claude-native status --require` превращает состояние проекции Claude Code в проверку CI.
- [Режим merge](docs/configuration/policy.ru.md) `owner-permission` разрешает агенту merge с явного разрешения владельца; [профили валидации](docs/configuration/validation.ru.md) получают тайм-ауты для каждой команды, полные логи и завершение всего дерева процессов.

## Новое в 0.26

- Правила Core проецируются в стартовые инструкции каждого хоста: файлы правил Claude Code и Copilot и управляемые инструкции Codex. Применяет ли их поверхность, проверяется на этой поверхности; см. [Claude Code](docs/hosts/claude-code.ru.md) и [Copilot](docs/hosts/copilot.ru.md).
- [Исполнение через API](docs/configuration/execution.ru.md#context-envelopes) собирает context envelopes из закоммиченных файлов с отказом по умолчанию, записывает каждую попытку в локальный журнал, по которому оценивается состояние кандидатов, и проверяет готовность без вызова провайдера.
- [Организация кода](docs/configuration/organization.ru.md) проверяет имена файлов и может требовать `.meta` для каждого файла в своих корнях Unity, с поиском осиротевших `.meta`.
- [Проверка безопасности](docs/security.ru.md) находит токены с префиксом провайдера и пути к домашним каталогам, а `--all-files` применяет точные проверки и к исходному коду.
- [Policy ceilings](docs/configuration/policy.ru.md#policy-ceilings) ограничивают и host overrides маршрутизации, а [контракт отчёта](docs/configuration/report.ru.md) может требовать сводку Workers и ссылку compare.

## Новое в 0.20

- [Инженерные навыки](docs/guides/engineering-skills.ru.md) и [живые проверки навыков](docs/guides/skill-evals.ru.md) описывают повторяемые процедуры и сравнение в новых сессиях хоста. Проверка готовой записи отличается от живого запуска.
- [Организация кода](docs/configuration/organization.ru.md) проверяет изменённые файлы постепенно; старый долг не освобождает новые нарушения от правил.
- [Контрольные точки](docs/guides/task-continuity.ru.md) и [поддержка знаний](docs/guides/knowledge-maintenance.ru.md) отслеживают актуальность по хешам и явно созданным базовым снимкам. Они не одобряют review и не переписывают документы проекта.
- [Внешние возможности](docs/configuration/capabilities.ru.md) описывают независимо установленные возможности хоста. Декларация не устанавливает плагин и не доказывает загрузку или выполнение хостом.

---

<sub>Последнее обновление: 2026-10-07 03:20 UTC</sub>
