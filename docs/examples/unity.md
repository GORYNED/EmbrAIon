# Unity Usage Example

The Unity example is a small runnable Unity 6 project.

When `Assets/Scenes/SampleScene.unity` enters Play Mode, it displays a simple counter:

```text
EmbrAIon Unity Reference

Value: 0

[ Increment ]
[ Reset ]
```

The counter is intentionally simple. The example is demonstrating the boundary between an ordinary Unity application and the EmbrAIon engineering layer.

## Application architecture

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

`CounterState` does not depend on `UnityEngine`. `CounterController` coordinates Unity lifecycle and state. `CounterSampleView` owns the sample UI.

The project itself is a normal Unity project with `Assets/`, `Packages/`, and `ProjectSettings/`.

## EmbrAIon layer

Alongside Unity files, the project has:

```text
.embraion/project.yaml
knowledge/
├── project.md
└── architecture.md
```

This is where the project declares its EmbrAIon pin and local engineering knowledge.

Installing a host projection:

```bash
embraion install --host codex --destination .
```

adds Codex-facing engineering configuration without changing the Unity runtime architecture.

## What the example proves

EmbrAIon is used while engineering the project. It does not sit between Unity and the finished application runtime.

[Browse the Unity Usage Example on GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/unity).
