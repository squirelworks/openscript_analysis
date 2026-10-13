"""Load a book.

.tbk and .sbk are decoded with expand, using the whole file so a
back-reference can land in an earlier handler. .fbk, .fsk, and .json
already hold source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ...core.formats import unpack
from ...core.model import Book, Handler, Page


_BIN_OVERRIDE: Path | None = None
_KEEP_DECODED = False


def set_keyword_bin(path: str | Path | None) -> None:
    global _BIN_OVERRIDE
    _BIN_OVERRIDE = Path(path) if path else None


def set_keep_decoded(keep: bool) -> None:
    global _KEEP_DECODED
    _KEEP_DECODED = bool(keep)


def find_book(name: str, near: str | Path | None = None) -> Path | None:
    """Locate a book by name near the current file."""
    if near:
        base = Path(near).parent
        for cand in (base / name, base / f"{name}.tbk", base / f"{name}.sbk"):
            if cand.exists():
                return cand
    return None


def load(path: str | Path) -> Book:
    """Load a .tbk / .sbk / .fbk / .fsk / .json into the core Book model."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".fbk", ".fsk", ".json"):
        data = unpack(p.read_bytes()) if suffix != ".json" else json.loads(p.read_text())
        book = Book(path=str(p), title=data.get("title", ""))
        for raw in data.get("pages", []):
            page = Page(id=raw.get("id", ""))
            page.text = raw.get("text", [])
            page.handlers = [Handler(name=h.get("name", ""), source=h.get("source", "")) for h in raw.get("handlers", [])]
            book.pages.append(page)
        return book
    # .tbk / .sbk
    from .tbk import load as load_raw
    raw_book = load_raw(p)
    book = Book(path=str(p))
    for rp in raw_book.pages:
        page = Page(id=rp.id)
        book.pages.append(page)
    return book
