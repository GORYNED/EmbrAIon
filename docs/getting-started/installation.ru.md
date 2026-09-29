# Установка

EmbrAIon использует один глобальный launcher на машине. Каждый проект фиксирует точную версию framework, которую ожидает.

!!! tip "Простыми словами"
    Команда `embraion` устанавливается один раз. Каждый репозиторий хранит собственный version pin, поэтому одна машина может работать с проектами на разных версиях EmbrAIon.

## Требования

- Windows, macOS или Linux
- Python 3.11 или новее
- `pipx` для рекомендуемой изолированной установки CLI

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

Репозиторий становится EmbrAIon-проектом только после явного:

```bash
cd MyProject
embraion init
```

Затем отдельно устанавливаются нужные host projections.

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
