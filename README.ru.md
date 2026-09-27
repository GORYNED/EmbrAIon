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
embraion doctor
```

После этого откройте репозиторий в своём AI-клиенте и пишите обычную задачу.

Канонический сайт документации: **https://embraion.goryned.com/**

---

<sub>Последнее обновление: 2026-09-27 10:20 UTC</sub>
