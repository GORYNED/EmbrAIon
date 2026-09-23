# Python Reference Project

This example shows EmbrAIon beside an ordinary Python package and its own deterministic unit tests.

The application deliberately stays tiny: `reference_app.labels.normalize_label` normalizes a user-facing label while rejecting empty input.

Run the application tests from this directory:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"
```

Inspect the EmbrAIon project:

```bash
embraion status
embraion doctor
embraion install --host codex --destination .
```

The Python package is product code. EmbrAIon remains an engineering-system layer around that code rather than a runtime dependency of the application.

<sub>Last updated: 2026-09-23 23:55 UTC</sub>
