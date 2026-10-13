"""Load a book.

.tbk and .sbk are decoded with expand, using the whole file so a
back-reference can land in an earlier handler. .fbk, .fsk, and .json
already hold source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .formats import detect
from .model import Book, Page
from .expand import expand, load_keywords
from .polish import polish
from .engine import run_page
from .tbk import find_pages

def _handlers_from_tbk(data: bytes, keywords: list[str]) -> dict[str, str]:
    """Return {page_name: script_source} by expanding every handler blob."""
    # Very light: look for the script property marker and expand the following bytes.
    # The real expander lives in expand.py; here we only locate the blobs.
    scripts: dict[str, str] = {}
    pages = find_pages(data)
    for off, name in pages:
        # Script is stored as a property inside the page record. We search a
        # short window after the page marker for a plausible handler start.
        window = data[off:off+0x2000]
        # Look for the compressed "to handle" pattern or a plain ASCII start.
        m = re.search(rb"to handle ", window)
        if m:
            # Plain text already present (some exports)
            end = window.find(b"\x00", m.start())
            raw = window[m.start():end if end > 0 else m.start()+512]
            scripts[name] = polish(raw.decode("latin-1", errors="replace"))
        else:
            # Fall back to expanding the whole window; the expander is tolerant.
            src = expand(window, keywords)
            if "to handle" in src.lower():
                scripts[name] = polish(src)
    return scripts

def load_book(path: str | Path) -> Book:
    p = Path(path)
    kind = detect(p)
    if kind == "json":
        raw = json.loads(p.read_text())
        pages = [Page(name=pg.get("name",""), script=pg.get("script","")) for pg in raw.get("pages", [])]
        return Book(name=raw.get("name", p.stem), pages=pages)
    if kind in ("fbk", "fsk"):
        data = p.read_bytes()
        # FBK1/FSK1 + flags + JSON (optionally zlib)
        flags = data[4]
        payload = data[5:]
        if flags & 1:
            import zlib
            payload = zlib.decompress(payload)
        raw = json.loads(payload.decode("utf-8"))
        pages = [Page(name=pg.get("name",""), script=pg.get("script","")) for pg in raw.get("pages", [])]
        return Book(name=raw.get("name", p.stem), pages=pages)
    # default: .tbk / .sbk
    data = p.read_bytes()
    keywords = load_keywords()
    scripts = _handlers_from_tbk(data, keywords)
    pages = []
    for off, name in find_pages(data):
        src = scripts.get(name, "")
        page = Page(name=name, script=src)
        page.actions = run_page(src)
        pages.append(page)
    return Book(name=p.stem, pages=pages)
