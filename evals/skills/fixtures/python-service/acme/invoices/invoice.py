"""Invoice data."""

from dataclasses import dataclass


@dataclass
class Invoice:
    number: str
