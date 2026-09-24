# Minimal Example

The Minimal reference project demonstrates the smallest **complete current** EmbrAIon configuration shape.

```text
examples/minimal/
├── .embraion/
│   ├── .gitignore
│   ├── project.yaml
│   ├── knowledge.yaml
│   ├── policy.yaml
│   ├── routing.yaml
│   ├── validation.yaml
│   └── agents.yaml
├── knowledge/
│   └── project.md
└── README.md
```

It demonstrates:

- an exact framework pin;
- project identity;
- project knowledge;
- focused policy/routing/validation/agent configuration files;
- no committed generated host projection.

Try the lifecycle from the example directory:

```bash
embraion status
embraion doctor
embraion validation list
embraion install --host codex --destination .
```

[Browse the example on GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/minimal).
