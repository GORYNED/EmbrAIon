# Разговорная настройка проекта

Не обязательно вручную редактировать каждый файл в `.embraion/`. AI-клиент, уже работающий в репозитории, может помочь настроить project-owned settings EmbrAIon.

Эта страница про **изменение project contract через естественный язык**. Установка hosts, расположение generated files и host-specific ownership rules описаны в [AI-хостах](../hosts/index.md).

> EmbrAIon не перехватывает ваш prompt. Установленная host projection объясняет AI-клиенту, где находится каноническая конфигурация EmbrAIon и какие reusable roles/skills доступны.

## Обычная инженерная работа vs конфигурация

Обычная задача:

> Исправь retry behavior при ошибке соединения.

должна использовать существующий project contract.

Запрос на конфигурацию:

> Настрой routing так, чтобы bounded work использовала недорогие модели, complex architecture — более сильный reasoning, а critical route оставался только для исключительного риска.

должен намеренно изменить канонический project contract.

Host не должен переписывать `.embraion/` только потому, что вы попросили обычное продуктовое изменение.

## Канонический ownership

| Намерение пользователя | Канонический файл |
| --- | --- |
| Изменить identity проекта или capabilities metadata | `.embraion/project.yaml` |
| Зарегистрировать architecture/domain knowledge | `.embraion/knowledge.yaml` |
| Пометить protected/canonical/generated/external paths | `.embraion/policy.yaml` |
| Зарегистрировать reusable model/provider choices | `.embraion/deployments.yaml` |
| Изменить model routing | `.embraion/routing.yaml` |
| Добавить project validation commands | `.embraion/validation.yaml` |
| Объявить project-specific agents | `.embraion/agents.yaml` |
| Настроить optional provider execution bindings | `.embraion/execution.yaml` |
| Настроить optional pricing sources | `.embraion/pricing.yaml` |

Generated host files — это projections, а не второй configuration authority.

![Каноническая конфигурация и AI host projections](../assets/diagrams/en/10-ai-host-projections.svg){ loading=lazy }

## Project Bootstrap

> Настрой EmbrAIon для этого проекта.

Короткий запрос загружает каноническую Core процедуру `project-bootstrap`. Lead находит существующую истину репозитория, сохраняет настройки, конфигурирует полезные knowledge/policy/validation, оставляет agents минимальными и routing необязательным, затем проверяет результат. См. [Project Bootstrap](bootstrap.md): discovery, ограничения создания документов, повторная настройка и limitations.

Для явного tuning:

> Настрой EmbrAIon полностью для этого проекта, включая routing с моделями и reasoning settings, реально доступными моему AI-хосту.

## Запрос на routing

> Настрой EmbrAIon routing для этого репозитория с моделями и reasoning settings, реально доступными этому хосту. Оставь host-default там, где явный routing не добавляет пользы, сохрани safety policy проекта и проверь полученные routes.

## Запрос на knowledge

> Зарегистрируй текущие architecture и compatibility documents как EmbrAIon project knowledge. Используй Project Contract Slots там, где они соответствуют существующему source of truth. Не дублируй содержимое документов в YAML.

## Запрос на policy

> Проверь source ownership этого репозитория. Пометь first-party source как canonical, generated artifacts как generated, vendor-managed code как external или protected в зависимости от ownership, и сохрани все более строгие существующие ограничения.

## Запрос на validation

> Добавь deterministic project validation commands в подходящие EmbrAIon profiles. Fast должен быть дешёвым, affected — подходить для обычных изменений, full — оставаться широким project gate. Не считай пустой profile pass.

## Запрос на project agent

> Добавь project-specific read-only specialist для этого domain только если существующих Core roles недостаточно. По возможности наследуй совместимую Core role и не расширяй её access boundary.

## Host-specific setup

Используйте отдельные страницы:

- [Codex](../hosts/codex.md)
- [GitHub Copilot](../hosts/copilot.md)
- [Claude Code](../hosts/claude-code.md)
- [Portable bundle](../hosts/portable.md)
