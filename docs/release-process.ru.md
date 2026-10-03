# Процесс релиза

EmbrAIon использует versioned framework releases, публикуемые из validated release commits.

## Contract

- GitHub `main` — upstream source of truth.
- Stable releases используют immutable `vX.Y.Z` tags.
- Python distributions публикуются в PyPI через Trusted Publishing.
- GitHub Releases включают source, Codex, Copilot, Claude Code и Portable artifacts.
- Новые проекты bootstrap из published framework version.
- Существующие проекты pin'ят version в `.embraion/project.yaml`.
- Global launcher разрешает exact published pins в isolated per-version runtimes.
- Project upgrades всегда намеренные и выполняются через `embraion update`.

## Release gate

До разрешённого релизного слияния завершите self-review автора, обязательные тесты/CI и цикл независимого Reviewer внутри хоста. После всех исправлений reviewer явно подтверждает полный текущий SHA исходного HEAD PR. Последующее изменение требует повторного подтверждения. Разрешения пользователя на merge и release остаются отдельными gates; Copilot Review не требуется. Итоговый squash-коммит получает новый SHA и запускает проверки ниже.

Release commit использует точное сообщение:

```text
release: vX.Y.Z
```

До создания tag CI проверяет:

- Linux, Windows и macOS compatibility;
- minimum и selected latest Python versions;
- framework validation;
- unit/integration tests;
- project resolver E2E;
- packaged reference-project E2E;
- security scanning;
- behavioral eval smoke;
- Core assignment routing и capability-aware regression coverage для Codex, Copilot, Claude Code и Portable;
- generation of host projections;
- strict documentation build.

Только после успешных checks workflow создаёт immutable release tag и запускает tagged build.

Tagged build снова проверяет version/tag contract, строит distributions/release archives, создаёт GitHub Release и публикует Python distributions в PyPI.

Assignment-routing eval fixtures проверяют grading и regression behavior, но не подтверждают live native execution. Evidence различает prepared arguments, capability limitations, handoffs и действительно применённые settings.

## Совместимость pre-1.0

Patch releases предназначены для совместимых fixes/improvements. Minor releases могут намеренно развивать framework contracts. Project pinning сохраняет upgrades explicit.

## Изменения необязательных capabilities

Необязательные inventory, правила структуры и связи knowledge-maintenance версии 0.20 добавляются без изменения поведения существующих overlays. Перед публикацией проверяйте схемы, пути выбранного bundle, ресурсы установленного wheel и все host projections. Проводите настоящую оценку skill при доступном авторизованном native host; явно сообщайте сбои host и недоступные evidence. Детерминированные fixtures и fake-host tests не заменяют live behavioral evidence и не обосновывают заявления об улучшении. Релиз не устанавливает provider login или credentials.
