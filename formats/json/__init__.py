"""Plain JSON lesson shell loader (stub)."""

from pathlib import Path
import json

def load(path: str | Path):
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data
