# Unity example

Unity reference — небольшой runnable Unity 6 project, показывающий, что EmbrAIon является engineering layer вокруг обычного Unity-репозитория.

В Play Mode `Assets/Scenes/SampleScene.unity` показывает простой counter. Application architecture остаётся обычной Unity/C#:

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

## Структура репозитория

Рядом с `Assets/`, `Packages/` и `ProjectSettings/` используется полный текущий project config:

```text
.embraion/
├── .gitignore
├── project.yaml
├── knowledge.yaml
├── policy.yaml
├── deployments.yaml
├── routing.yaml
├── validation.yaml
└── agents.yaml

knowledge/
├── project.md
└── architecture.md
```

`.embraion/` объявляет framework pin и project engineering contract. `knowledge/` содержит Unity-specific project truth.

## Установка AI-client projection

```bash
embraion install --host codex --destination .
```

Это добавляет Codex-facing engineering files, не меняя Unity runtime architecture.

## Что доказывает пример

EmbrAIon используется во время инженерной работы над проектом. Он не находится между Unity и runtime готового приложения.

То же разделение Core/project/host применимо к большим Unity repos: project architecture принадлежит проекту, reusable engineering behavior — EmbrAIon, generated AI-client files остаются projections.

[Открыть Unity example на GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/unity).
