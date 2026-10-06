# Completion report

`.embraion/report.yaml` — необязательный контракт проекта для итогового отчёта по существенной работе. EmbrAIon не выбирает секции за вас: он выводит объявленный вами контракт, встраивает его в проецируемый skill `orchestration` и проверяет текст отчёта.

```yaml
schema-version: 1
sections: [Changed, Architecture, Validation, Risks, Workers]
workers:
  section: Workers
  task-status: [completed, cancelled, incomplete]
  columns: [Status, Worker, Role, Billing, Access, Data, Runs, Cost, Routing, Validation]
pull-request:
  section: Changed
guidance:
  - Name the provider, task, access, and selection reason before each external worker attempt.
```

- `sections` — секции верхнего уровня итогового отчёта в обязательном порядке. Каждая встречается ровно один раз как Markdown-заголовок или строка только из жирного текста.
- `workers` (необязательно) требует одну таблицу с точно такими колонками внутри `workers.section`, перед которой стоит строка `Task status: <значение>` из `task-status`. Ячейки не должны содержать абсолютные пути машины, значения, похожие на учётные данные, блоки кода и диффы.
- `pull-request` (необязательно) заставляет `--pull-request` требовать полный URL pull request в этой секции.
- Строки `guidance` дословно попадают в шаблон и skill. Они не проверяются.

## Шаблон и проверка

```bash
embraion report template
embraion report validate report.md --pull-request
embraion report validate update.md --kind intermediate
```

Отчёт `final` должен соответствовать контракту. Промежуточное сообщение `intermediate` не должно содержать таблицу или секцию Workers. Блоки кода при разборе игнорируются, поэтому цитируемые примеры не учитываются.

Проверка структурная. Она не определяет, правдиво ли содержимое, и не заменяет review.

## Projection

Если `.embraion/report.yaml` существует, `embraion install --component skills` добавляет раздел *Project completion report contract* в проецируемый skill `orchestration` для каждого host. После изменения контракта `embraion projection verify` покажет устаревшую projection.

<sub>Last updated: 2026-10-06 01:40 UTC</sub>
