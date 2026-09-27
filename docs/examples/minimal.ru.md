# Minimal example

Minimal reference project показывает минимальную **полную текущую** форму EmbrAIon configuration.

```text
examples/minimal/
├── .embraion/
│   ├── .gitignore
│   ├── project.yaml
│   ├── knowledge.yaml
│   ├── policy.yaml
│   ├── deployments.yaml
│   ├── routing.yaml
│   ├── validation.yaml
│   └── agents.yaml
├── knowledge/
│   └── project.md
└── README.md
```

Он показывает:

- точный framework pin;
- project identity;
- project knowledge;
- отдельные policy/deployment/routing/validation/agent files;
- отсутствие committed generated host projection.

Попробуйте lifecycle из каталога example:

```bash
embraion status
embraion doctor
embraion validation list
embraion install --host codex --destination .
```

[Открыть пример на GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/minimal).
