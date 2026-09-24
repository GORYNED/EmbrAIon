# Minimal Example

The Minimal example contains only what is necessary to be a complete EmbrAIon consumer:

```text
examples/minimal/
├── .embraion/
│   └── project.yaml
├── knowledge/
│   └── project.md
└── README.md
```

It demonstrates:

- a pinned framework version;
- project identity;
- one project-knowledge file;
- no committed generated host projection.

Try the lifecycle from the example directory:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

[Browse the example on GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/minimal).
