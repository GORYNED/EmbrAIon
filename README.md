<p align="center">
  <img src="brand/assets/readme/hero-dark.png" alt="EmbrAIon — AI-First Engineering System by GORYNED" width="100%">
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.ru.md">Русский</a>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

**EmbrAIon keeps the rules for AI-assisted engineering with the repository — project knowledge, protected paths, routing, validation, review, and evidence — instead of scattering them across prompts and AI-client settings.**

Use the same project contract with Codex, GitHub Copilot, Claude Code, or a host-neutral Portable bundle.

## Why use it?

Use EmbrAIon when:

- important project rules no longer fit in one prompt;
- several AI clients need to follow the same repository contract;
- protected paths and validation need deterministic checks rather than prose alone;
- architecture knowledge and policy must survive model/session changes;
- model selection, review, and evidence should be reusable project settings instead of ad hoc choices.

> **Mental model:** EmbrAIon is the operating system for AI-assisted engineering; `.embraion/` is the Settings for this repository.

EmbrAIon does **not** replace the AI client, intercept every prompt, or run inside the finished product.

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
```

Then open the repository in your AI client and work normally:

> Fix the retry flow and add regression coverage.

Use `copilot` or `claude-code` instead of `codex` when that is your host.

Want to experiment first? Use the [Five-Minute Sandbox](docs/getting-started/playground.md).

## Before / after

```text
Before
prompts + AGENTS.md + host settings + CI + tribal knowledge
                         ↓
                      drift

After
                 .embraion/
                     ↓
      one repository-owned project contract
                     ↓
      host projections + validation + review
```

## Documentation

Canonical site: **https://embraion.goryned.com/**

Recommended onboarding:

1. [Why EmbrAIon?](docs/getting-started/what-is-embraion.md)
2. [EmbrAIon in 60 Seconds](docs/getting-started/in-60-seconds.md)
3. [Five-Minute Sandbox](docs/getting-started/playground.md)
4. [Installation](docs/getting-started/installation.md)
5. [Your First AI Task](docs/getting-started/first-ai-task.md)
6. [How It Works](docs/getting-started/how-it-works.md)

For engineers, see [Engineering Model Deep Dive](docs/reference/engineering-model.md).

## Examples

- [Minimal](examples/minimal/) — smallest complete project overlay.
- [Python](examples/python/) — ordinary Python app + EmbrAIon engineering layer.
- [Unity](examples/unity/) — Unity 6 project with EmbrAIon outside the game runtime.

## Status

EmbrAIon is pre-1.0. Projects pin exact published framework versions so upgrades remain intentional.

## License and brand

Source code and documentation are licensed under the [MIT License](LICENSE) except where explicitly stated otherwise. The **EmbrAIon** and **GORYNED** names, logos, wordmarks, visual marks, and files under `brand/assets/` are governed separately by [TRADEMARKS.md](TRADEMARKS.md).

---

<sub>Last updated: 2026-09-27 10:20 UTC</sub>