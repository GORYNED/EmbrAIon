# Установка

EmbrAIon использует один глобальный launcher на машине. Каждый проект фиксирует точную версию framework, которую ожидает.

!!! tip "Простыми словами"
    Команда `embraion` устанавливается один раз. Каждый репозиторий хранит собственный version pin, поэтому одна машина может работать с проектами на разных версиях EmbrAIon.

## Требования

- Windows, macOS или Linux
- Python 3.11 или новее
- `pipx` для рекомендуемой изолированной установки CLI
- Git в вашем `PATH`

### Git и GitHub

Git — заявленное предварительное требование EmbrAIon. Проверки проекта, worktree и записи решений читают и меняют состояние Git. Командам worktree нужен Git 2.36 или новее, потому что они читают `git worktree list --porcelain -z`. CLI не проверяет версию Git за вас.

GitHub — поддерживаемая платформа хостинга и поставки. GitHub CLI `gh` с выполненным входом нужен только когда `embraion worktree gc` проверяет влитые pull request. Без него очистка сохраняет ресурсы, которые не может доказать.

Универсальные правила остаются в workflow [worktree](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/worktree.md) и [delivery](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/delivery.md). Их механика Git и GitHub описана в [одном месте](https://github.com/GORYNED/EmbrAIon/blob/main/core/workflows/git.md). Решение записано в [ADR 0001](../architecture/decisions/0001-git-is-a-prerequisite-git-mechanics-live-in-one-place.md).

## Установите launcher

```bash
pipx install embraion
```

Проверьте установку:

```bash
embraion --version
embraion help
```

Если EmbrAIon уже установлен:

```bash
pipx upgrade embraion
```

## Что происходит после `pipx install`?

На этом этапе **ни один репозиторий не изменён**.

Вы установили только launcher-команду.

Репозиторий становится EmbrAIon-проектом по вашему запросу агенту. Агент
проверяет launcher и репозиторий, закрепляет официальный release artifact,
устанавливает runtime проекта и проекцию хоста, затем по возможности проверяет
результат в новой сессии.
Для установки общего ПО на машине может понадобиться ваше разрешение; вводить
команды или править YAML самому не требуется. Если хост ещё не загрузил
`project-bootstrap`, агент сначала должен найти официальные инструкции.
Проверка файлов сама по себе не доказывает загрузку skill хостом.

Для ручной настройки доступна эквивалентная команда:

```bash
cd MyProject
embraion init
embraion update --check
embraion update
embraion framework install
```

Если `update --check` сообщает об устаревшем launcher, обновите его до команды
`update`: pin проекта не меняется автоматически вслед за глобальным обновлением.
Ошибка проверки релиза или runtime означает незавершённую настройку. Затем
устанавливаются нужные host projections и открывается новая сессия хоста.

## Почему одного launcher достаточно

Проект хранит framework version в `.embraion/project.yaml`.

Если pin отличается от версии глобального launcher, EmbrAIon может разрешить точную опубликованную project runtime в изолированный cache:

```text
~/.embraion/versions/<version>/
```

Так разные проекты могут оставаться на разных версиях EmbrAIon без отдельных глобальных CLI.

## Примечания по платформам

### Windows

Используйте Python 3.11+ и `pipx`. После `pipx ensurepath` заново откройте PowerShell, чтобы обновился PATH.

### macOS

`pipx` через Homebrew — удобный вариант, но подойдёт любой управляемый Python 3.11+ environment.

### Linux

Установите Python 3.11+ и `pipx` предпочтительным способом вашего дистрибутива, затем установите `embraion` через `pipx`.

Контракт EmbrAIon переносим между репозиториями; собственные validation commands проекта могут оставаться platform-specific.

После `init` установите host projection, откройте репозиторий в этом хосте и напишите «Настрой EmbrAIon для этого проекта». См. [Project Bootstrap](../configuration/bootstrap.md).

## Дальше

- Хотите нулевой риск? [Попробуйте песочницу](playground.md).
- Готовы к репозиторию? [Добавьте EmbrAIon в проект](first-project.md).
