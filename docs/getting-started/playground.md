# Five-Minute Sandbox

You can try EmbrAIon without touching an existing codebase.

This sandbox creates a new empty Git repository, initializes the project contract, installs one host projection, and lets you inspect routing and validation behavior.

## 1. Create a disposable repository

```bash
mkdir embraion-playground
cd embraion-playground
git init
```

## 2. Initialize EmbrAIon

```bash
embraion init --name EmbrAIonPlayground
```

Inspect what was created:

```text
.embraion/
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── deployments.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml
```

Runtime-only `.embraion/state/` and `.embraion/cache/` stay ignored.

## 3. Install one host projection

For Codex:

```bash
embraion install --host codex --destination .
```

Or use:

```bash
embraion install --host copilot --destination .
embraion install --host claude-code --destination .
```

## 4. Inspect the project

```bash
embraion doctor
embraion status
embraion policy show
embraion validation list
```

A fresh project's validation profiles may be empty. If so, running them reports `skipped`, not a false pass.

## 5. Inspect routing without calling a model

```bash
embraion route \
  --host codex \
  --route-class substantial \
  --data PRIVATE
```

With no project override, the result should resolve to `host-default`: EmbrAIon classifies the work, while the host remains responsible for its actual model selection.

## 6. Ask the AI to configure the sandbox

Open the repository with your installed AI client and try a natural-language configuration request:

> Configure EmbrAIon for this project.

Then inspect the canonical diff under `.embraion/`.

Bootstrap must report that an empty repository has no application test workflow; it should preserve unbound optional slots and `skipped` profiles rather than invent checks. See [Project Bootstrap](../configuration/bootstrap.md).

## What this proves

The sandbox lets you see the core lifecycle without risking production code:

```text
init
 ↓
project-owned .embraion/ contract
 ↓
host projection
 ↓
normal AI conversation
 ↓
routing / validation / policy inspection
```

It intentionally does not simulate paid provider calls or complex application validation.

For a checked-in example, use the [Minimal reference project](../examples/minimal.md).

## What next?

If the sandbox made sense, continue with a checked-in example:

- [Minimal](../examples/minimal.md) — the smallest complete current project overlay;
- [Python](../examples/python.md) — ordinary application code and tests;
- [Unity](../examples/unity.md) — Unity 6 with EmbrAIon outside the game runtime.

Then move to [Add EmbrAIon to a Project](first-project.md) or [Adopt an Existing Repository](existing-repository.md).

## Clean up

Delete the `embraion-playground` directory whenever you are finished.
