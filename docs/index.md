# EmbrAIon

![EmbrAIon — Where sparks become AI-built products](assets/hero-dark.png)

<div class="embraion-lead" markdown>

**EmbrAIon** is a portable **AI-First Engineering System** for making AI-assisted software development structured, reusable, reviewable, and trustworthy.

It does not replace your application runtime. It sits around the engineering process: roles, skills, project knowledge, routing, permissions, validation, and host-specific projections. It is model-agnostic: the AI host owns model availability, while a project may optionally override model selection in `.embraion/routing.yaml`.

</div>

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } **Start in minutes**

    ---

    Install one launcher, initialize a project, and install the host projection you use.

    [Get started](getting-started/installation.md)

-   :material-brain:{ .lg .middle } **One canonical Core**

    ---

    Keep reusable engineering policy upstream while project-specific truth stays with each consuming repository.

    [Understand the model](concepts/index.md)

-   :material-connection:{ .lg .middle } **Multiple AI hosts**

    ---

    Project the same Core into Codex, GitHub Copilot, Claude Code, or a host-neutral Portable bundle.

    [Explore hosts](hosts/index.md)

-   :material-check-decagram-outline:{ .lg .middle } **Evidence, not assumptions**

    ---

    Deterministic validation, behavioral evals, security checks, reference E2E, and release gates make changes observable.

    [See validation](validation.md)

</div>

## The basic idea

A software project keeps its normal source code and runtime:

```text
Application / Library / Game
          ↑
      your code
```

EmbrAIon adds an engineering layer around that repository:

<div class="embraion-architecture-diagram">
<svg viewBox="0 0 760 430" role="img" aria-labelledby="architecture-title architecture-desc">
  <title id="architecture-title">EmbrAIon engineering layer architecture</title>
  <desc id="architecture-desc">EmbrAIon Core projects into Codex, Copilot, and Claude Code. Those hosts operate on a consuming project, which produces the product runtime.</desc>

  <g class="diagram-lines" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M380 58 V95" />
    <path d="M170 95 H590" />
    <path d="M170 95 V130" />
    <path d="M380 95 V130" />
    <path d="M590 95 V130" />

    <path d="M170 205 V245" />
    <path d="M380 205 V245" />
    <path d="M590 205 V245" />
    <path d="M170 245 H590" />
    <path d="M380 245 V285" />

    <path d="M380 335 V375" />
  </g>

  <g class="diagram-arrows" fill="currentColor">
    <path d="M170 130 l-7 -10 h14 z" />
    <path d="M380 130 l-7 -10 h14 z" />
    <path d="M590 130 l-7 -10 h14 z" />
    <path d="M380 285 l-7 -10 h14 z" />
    <path d="M380 375 l-7 -10 h14 z" />
  </g>

  <g class="diagram-labels" fill="currentColor" text-anchor="middle">
    <text x="380" y="42">EmbrAIon Core</text>

    <text x="170" y="175">Codex</text>
    <text x="380" y="175">Copilot</text>
    <text x="590" y="175">Claude Code</text>

    <text x="380" y="325">Consuming project</text>
    <text x="380" y="420">Product runtime</text>
  </g>
</svg>
</div>

The final application does not need an EmbrAIon runtime dependency. EmbrAIon is used to organize how humans and AI agents engineer the project.

## Quick start

```bash
pipx install embraion

cd MyProject
embraion init
embraion install --host codex --destination .
embraion doctor
embraion status
```

The project now has a pinned EmbrAIon version plus a generated host projection.

If you want to override model selection, ask the AI in that project to configure EmbrAIon routing. The installed `routing-configuration` skill directs it to `.embraion/routing.yaml` → `overrides`; otherwise the host keeps its own default/automatic model policy.

## What EmbrAIon owns

| Area | Purpose |
| --- | --- |
| Core | Canonical reusable rules, roles, skills, workflows, routing, and knowledge |
| Project overlay | Project identity, version pin, domain knowledge, and local capabilities |
| Routing config | Optional project model/effort/options overrides in `.embraion/routing.yaml` |
| Adapters | Codex, Copilot, Claude Code, Portable, and transport projections without a global model catalog |
| Tools | Validation, security, worktrees, sessions, learning, evals, install/sync |
| Evidence | Unit/integration tests, reference E2E, behavioral evals, release gates |

## See it in a real project

The repository ships with executable reference projects:

- [Minimal](examples/minimal.md) — the smallest complete EmbrAIon consumer.
- [Python](examples/python.md) — ordinary application code and tests wrapped by EmbrAIon.
- [Unity](examples/unity.md) — a runnable Unity 6 example showing that EmbrAIon lives around the project, not inside the game runtime.

## Status

EmbrAIon is pre-1.0. Patch releases are intended to remain migration-free; minor releases may evolve public framework contracts while release notes and project pinning preserve intentional upgrades.

[Start with installation](getting-started/installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/GORYNED/EmbrAIon){ .md-button }
