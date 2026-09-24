# Unity Usage Example

The Unity reference is a small runnable Unity 6 project showing that EmbrAIon is an engineering layer around a normal Unity repository.

When `Assets/Scenes/SampleScene.unity` enters Play Mode, it displays a simple counter. The application architecture stays ordinary Unity/C#:

```text
CounterState
pure C# state
     ↓
CounterController
MonoBehaviour / lifecycle boundary
     ↓
CounterSampleView
sample presentation
```

## Repository shape

Alongside `Assets/`, `Packages/`, and `ProjectSettings/`, the example uses the full current project configuration:

```text
.embraion/
├── .gitignore
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml

knowledge/
├── project.md
└── architecture.md
```

The `.embraion/` files declare the framework pin and project engineering contract. The `knowledge/` files contain Unity-specific project truth.

## Install an AI-client projection

```bash
embraion install --host codex --destination .
```

This adds Codex-facing engineering files without changing the Unity runtime architecture.

## What the example proves

EmbrAIon is used while engineering the project. It does not sit between Unity and the finished application runtime.

The same Core/project/host split used here applies to larger Unity repositories: project architecture belongs with the project, reusable engineering behavior stays in EmbrAIon, and generated AI-client files remain projections.

[Browse the Unity Usage Example on GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/unity).
