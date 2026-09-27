# Runtime и разрешение версий

EmbrAIon разделяет **версию глобального launcher** и **версию framework, закреплённую за каждым проектом**.

## Один launcher, несколько project pins

Проект записывает точную release-версию framework в:

```text
.embraion/project.yaml
```

```yaml
framework:
  repository: GORYNED/EmbrAIon
  version: <published-version>
```

Обычные команды находят ближайший проект и разрешают его pin:

![Runtime и разрешение версий](../assets/diagrams/en/07-runtime-version-resolution.svg){ loading=lazy }

Если pin отличается от версии launcher, EmbrAIon может установить точно эту опубликованную distribution в изолированный cache:

```text
~/.embraion/versions/<version>/
```

Поэтому разные репозитории на одной машине могут оставаться на разных release-версиях EmbrAIon.

## Проверить разрешённую версию

```bash
embraion status
embraion status --json
```

Status показывает launcher, project pin, resolved runtime, состояние cache и обнаруженные host projections.

## Управление cache

```bash
embraion cache list
```

Предварительный просмотр очистки:

```bash
embraion cache prune --older-than 90
```

Применить очистку осознанно:

```bash
embraion cache prune --older-than 90 --apply
```

Активный launcher и resolved runtime текущего проекта защищены от очистки по возрасту.

## Обновление проекта

Безопасная последовательность:

```bash
pipx upgrade embraion
cd MyProject
embraion update
embraion doctor
```

`embraion update` принадлежит launcher. Безопасная нормализация конфигурации ориентируется **только на установленную версию launcher**, чтобы текущий runtime не пытался угадать schema/defaults другого release.

Команда может добавить совместимые отсутствующие defaults и обновить project pin, сохраняя значения проекта. Перед записью она валидирует все candidate canonical-файлы `.embraion/`.

Host projections не обновляются молча.

## Переход на другую конкретную release

Сначала установите нужную версию launcher, затем запустите `embraion update` из проекта. Так нормализация конфигурации остаётся в том же release contract, который будет записан.

## Development override

`EMBRAION_HOME` выбирает явный checkout framework для разработки самого EmbrAIon. Автоматическое разрешение версий можно намеренно отключить через `EMBRAION_DISABLE_VERSION_RESOLUTION=1`.
