"""Simple page/handler model used by the runner."""

from dataclasses import dataclass, field
from typing import Any

@dataclass
class Action:
    kind: str
    target: str = ""
    value: Any = None

@dataclass
class Page:
    name: str
    script: str = ""
    actions: list[Action] = field(default_factory=list)

@dataclass
class Book:
    name: str
    pages: list[Page] = field(default_factory=list)
