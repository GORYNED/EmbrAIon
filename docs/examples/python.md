# Python Example

The Python example shows that EmbrAIon is an engineering layer rather than an application dependency.

```text
examples/python/
├── .embraion/
├── knowledge/
├── src/reference_app/
├── tests/
├── pyproject.toml
└── README.md
```

The application has ordinary Python code and its own deterministic tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"
```

EmbrAIon independently manages project knowledge, version pinning, diagnostics, and host projections:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

The application can continue to run without EmbrAIon being a runtime dependency.

[Browse the example on GitHub](https://github.com/GORYNED/EmbrAIon/tree/main/examples/python).
