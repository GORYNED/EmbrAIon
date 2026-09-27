# Python example

Python example показывает, что EmbrAIon — engineering layer, а не application dependency.

```text
examples/python/
├── .embraion/
├── knowledge/
├── src/reference_app/
├── tests/
├── pyproject.toml
└── README.md
```

У приложения обычный Python code и собственные deterministic tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"
```

EmbrAIon независимо управляет project knowledge, version pinning, diagnostics и host projections:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

Приложение продолжает работать без EmbrAIon как runtime dependency.

[Открыть пример на GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/python).
