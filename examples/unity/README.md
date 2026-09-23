# Unity / C# Reference Project

This is a small public Unity 6 reference project for EmbrAIon.

It demonstrates a realistic repository shape without using any private application code:

- a Unity project version file;
- a package manifest;
- an assembly definition;
- pure C# state logic;
- a Unity-facing `MonoBehaviour` controller;
- project and architecture knowledge;
- a pinned EmbrAIon project overlay.

The architecture deliberately keeps `CounterState` independent of `UnityEngine`. `CounterController` owns the Unity lifecycle boundary.

EmbrAIon CI validates the project structure and exercises the consuming-project lifecycle. The Unity Editor itself is not launched in this stage; editor/device validation is a separate application-level concern.

From this directory:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

<sub>Last updated: 2026-09-23 23:55 UTC</sub>
