# Локализация

Английская документация — **оригинальная, каноническая и release-authoritative** версия EmbrAIon.

Русский — единственный поддерживаемый перевод. Публичный сайт документации собирает оба языка из одной структуры навигации и показывает переключатель языка.

## Policy

- **English (`en`)** — оригинальный source и canonical contract.
- **Русский (`ru`)** — полный поддерживаемый перевод каждой public documentation page.
- Другие публичные языки документации не поддерживаются.

Technical identifiers не переводятся, если перевод сделал бы commands или configuration неоднозначными. Например: `.embraion/routing.yaml`, `bounded-write`, `CONFIDENTIAL`, `embraion validation run`.

## Структура файлов

Сайт использует suffix structure `mkdocs-static-i18n`:

```text
docs/
├── index.md
├── index.ru.md
├── configuration/
│   ├── policy.md
│   └── policy.ru.md
└── ...
```

English files используют обычные `.md` names. Russian translations используют `.ru.md`.

## Полнота

У каждой canonical English Markdown page в `docs/` должна быть matching Russian `.ru.md` page.

Build использует `fallback_to_default: false`, а repository validation проверяет parity, поэтому отсутствующая русская страница не подменяется английской молча.

## Workflow contribution

1. Сначала обновляйте English source.
2. В том же PR обновляйте matching Russian translation.
3. Сохраняйте точными technical identifiers, commands, paths, schema keys и host names.
4. Запускайте strict documentation build и `embraion validate`.
5. Review'ьте обе language versions перед merge.

Если смысл English и Russian расходится, authoritative остаются English source и machine-readable framework contracts.
