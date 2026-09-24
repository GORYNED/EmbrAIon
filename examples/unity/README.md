# Unity / C# Reference Project

This is a small public Unity 6 reference project for EmbrAIon.

It demonstrates a realistic repository shape without using any private application code:

- a Unity project version file;
- a package manifest;
- a conventional `Assets/Scripts/` source layout;
- an assembly definition;
- pure C# state logic;
- a Unity-facing `MonoBehaviour` controller;
- a runnable `Assets/Scenes/SampleScene.unity`;
- a tiny runtime UI showing the current value with Increment and Reset actions;
- project and architecture knowledge;
- a pinned EmbrAIon project overlay.

The architecture deliberately keeps `CounterState` independent of `UnityEngine`. `CounterController` owns the Unity lifecycle boundary, while `CounterSampleView` owns the sample presentation.

To try it in Unity:

1. Open this directory as a Unity project.
2. Open `Assets/Scenes/SampleScene.unity`.
3. Press Play.
4. Use **Increment** and **Reset** while watching the displayed value.

The sample UI uses Unity IMGUI intentionally so the reference project stays dependency-free. EmbrAIon CI validates the scene/script links structurally and exercises the consuming-project lifecycle; the Unity Editor itself is not launched in CI at this stage.

From this directory:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

<sub>Last updated: 2026-09-24 00:10 UTC</sub>