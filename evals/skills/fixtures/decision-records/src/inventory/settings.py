import json
from pathlib import Path

PATH = Path("settings.json")


def load() -> dict:
    cfg = json.loads(PATH.read_text(encoding="utf-8"))
    return cfg


def save(values: dict) -> None:
    PATH.write_text(json.dumps(values, indent=2), encoding="utf-8")
