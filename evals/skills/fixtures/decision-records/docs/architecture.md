# Architecture

- `src/inventory/settings.py` loads and saves settings in `settings.json` ([ADR 0001](decisions/0001-store-settings-in-json.md)).
- `src/inventory/network.py` talks to the warehouse API and imports `ui` to show error dialogs.
- `src/inventory/ui.py` renders screens and dialogs.
