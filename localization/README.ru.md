<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System от GORYNED" width="100%">
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <strong>Русский</strong> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.hi.md">हिन्दी</a>
</p>

# EmbrAIon

**AI-First Engineering System [от GORYNED](https://goryned.com)**

> Where sparks become AI-built products

EmbrAIon даёт программному репозиторию переиспользуемую **операционную модель AI-разработки**.

Вместо того чтобы хранить знания проекта, роли ИИ, model routing, protected paths, тестовые команды, review rules и host-specific prompt-файлы в разных местах, EmbrAIon собирает их в один проектный контракт, который могут использовать Codex, GitHub Copilot, Claude Code и другие интеграции.

EmbrAIon **не работает внутри готового приложения** и **не перехватывает каждый prompt**. Unity-игра, Python-сервис, сайт или библиотека остаются обычным проектом. EmbrAIon организует процесс инженерной работы человека и ИИ вокруг репозитория.

## За 60 секунд

EmbrAIon хранит правила AI-разработки **вместе с репозиторием**: что AI должен знать, какие пути защищены, какие проверки запускать и как устроен routing.

Для первого полезного результата достаточно трёх вещей:

- `knowledge.yaml` — что AI должен знать;
- `policy.yaml` — какие правила и границы соблюдать;
- `validation.yaml` — чем доказать, что изменение работает.

После этого вы открываете проект в Codex/Copilot/Claude и пишете обычную задачу. Остальные возможности — custom agents, deployments, provider execution, pricing, enforcement — можно подключать позже.

## Выберите путь

- **Простой:** sandbox → установка → knowledge/policy/validation → обычные задачи.
- **Инженерный:** ownership → projections → routing → execution → evidence/enforcement.

## Зачем он нужен

AI coding хорошо работает, пока задача маленькая и все правила помещаются в один разговор. В реальном проекте ИИ должен стабильно учитывать:

- архитектуру и project truth;
- protected/private sources;
- разные роли и project-specific специалистов;
- model/provider choices;
- validation и independent review;
- generated host files;
- правила, которые должны переживать новые сессии и смену AI-клиента.

Без системы это быстро превращается в набор разрозненных prompt'ов, инструкций, CI-скриптов и ручных договорённостей.

> **Ментальная модель:** EmbrAIon — операционная система AI-разработки, а `.embraion/` — Settings конкретного проекта.

## Почему не просто AGENTS.md или инструкции конкретного AI-клиента

Host-native instructions полезны и могут оставаться в проекте. Но сами по себе они в основном являются текстовыми инструкциями одного host surface.

EmbrAIon добавляет общий repository-owned contract: одни и те же project knowledge/policy/routing/validation правила могут проецироваться в разные AI hosts, а validation и enforcement являются реальными исполняемыми проверками, а не только текстом для модели.

То есть EmbrAIon не «заменяет prompt-файл», а делает host-native инструкции частью более широкого инженерного контракта.

## Core и проект

**EmbrAIon Core владеет механизмами:**

- generic roles и skills;
- routing/execution/fallback/health contracts;
- validation/review/security/evidence mechanics;
- host projections.

**Проект владеет фактами и настройками:**

- identity и точным framework pin;
- knowledge и architecture;
- protected paths, privacy/review/enforcement policy;
- deployments и routing preferences;
- validation commands;
- project-specific agents;
- optional execution bindings и pricing sources.

## Как выглядит проект

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

Опционально для provider-neutral runtime:

```text
execution.yaml
pricing.yaml
pricing.snapshot.json
usage-evidence/
```

Generated `.codex/**`, `.github/agents/**`, `.github/skills/**`, `.claude/**` — это projections, а не второй source of truth.

## Обычная работа остаётся обычной

После установки projection пользователь может просто написать:

> Исправь reconnect при потере соединения и добавь regression test.

AI host получает prompt напрямую и использует проектный контракт EmbrAIon.

Настройки тоже можно задавать человеческим языком:

> Настрой routing: bounded work держи дешёвым, complex отправляй на более сильный deployment, critical оставь для исключительного риска.

AI должен записать это в канонические `.embraion/` файлы, а не создавать ещё одну routing-таблицу где-то ещё.

## Быстрый старт

Если не хочется сразу трогать рабочий проект, создайте пустую папку с `git init` и выполните команды в [песочнице Five-Minute Sandbox](../docs/getting-started/playground.md) — это безопасный способ изучить `.embraion/`, projections, routing и validation.

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

Для других клиентов используйте `copilot` или `claude-code`.

## Как это работает

```text
Вы формулируете задачу
        ↓
Codex / Copilot / Claude Code
        ↓
host-native projections
        +
project .embraion/
        ↓
roles / knowledge / routing / policy / validation
        ↓
engineering work
        ↓
validation → review → evidence → human merge
```

Для обычной host-native работы host сам выполняет reasoning/tools.

Для опционального API/provider lane можно использовать `embraion execute`, где EmbrAIon уже детерминированно владеет bounded attempts, normalized failures/health и eligible fallback по утверждённым project bindings.

## Execution и Pricing

Четыре понятия отвечают на разные вопросы:

| Понятие | Вопрос |
| --- | --- |
| Deployment | **Что** можно использовать |
| Routing | **Когда** это выбирать |
| Execution | **Как** это безопасно вызвать |
| Pricing | **Как** получить и интерпретировать стоимость |

Provider execution настраивается отдельным `.embraion/execution.yaml`; credentials хранятся как references, а не значения секретов.

Pricing обновляется только явно через `embraion pricing refresh`. EmbrAIon валидирует официальный источник и локальный snapshot; failed refresh не уничтожает last-known-good данные, а неизвестная стоимость остаётся `unknown`, а не превращается в ноль.

## Routing

EmbrAIon использует стабильные классы работы:

- `bounded-read`
- `bounded-write`
- `ordinary`
- `substantial`
- `complex`
- `critical`

Они описывают работу и риск, а не конкретную модель. По умолчанию модель выбирает host. Проект может явно настроить deployment/routing.

## Validation и enforcement

Проект объявляет реальные команды в `.embraion/validation.yaml`:

```bash
embraion validation run affected
```

Enforcement включается только явно:

```bash
embraion enforcement install \
  --surface github-actions \
  --validation-profile affected
```

EmbrAIon не устанавливает merge gate или hooks молча.

## Обновление

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
```

Глобальный launcher и project pin разделены: каждый проект может оставаться на своей точной опубликованной версии.

## Документация

Каноническая документация: **https://embraion.goryned.com/**

Русский набор ключевых страниц: [localization/docs/ru/](docs/ru/README.md)

Полная текущая документация на английском: [docs/](../docs/index.md)

## Статус

EmbrAIon находится в pre-1.0 стадии. Patch-релизы предназначены для совместимых исправлений и улучшений; minor-релизы могут развивать публичные framework contracts. Проекты фиксируют точную опубликованную версию, поэтому обновления остаются намеренными.

## Лицензия и бренд

Исходный код и документация лицензируются по [MIT License](../LICENSE), если явно не указано иное. Имена и визуальные материалы **EmbrAIon** и **GORYNED** регулируются отдельно через [TRADEMARKS.md](../TRADEMARKS.md).

---

<sub>Последнее обновление: 2026-09-27 02:20 UTC</sub>