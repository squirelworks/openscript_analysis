"""Load a book.

.tbk and .sbk are decoded with expand, using the whole file so a
back-reference can land in an earlier handler. .fbk, .fsk, and .json
already hold source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .formats import unpack
from .model import Book, Handler, Page


_BIN_OVERRIDE: Path | None = None
_KEEP_DECODED = False


def set_keyword_bin(path: str | Path | None) -> None:
    global _BIN_OVERRIDE
    _BIN_OVERRIDE = Path(path) if path else None


def set_keep_decoded(keep: bool) -> None:
    global _KEEP_DECODED
    _KEEP_DECODED = bool(keep)


def find_book(name: str, near: str | Path) -> Path | None:
    stem = Path(name).stem
    near = Path(near)
    here = near.parent if near.is_file() else near
    below = here.parent
    root = Path(__file__).resolve().parents[1]
    dirs = [below, here, root / "core"]
    suffixes = (".fsk", ".sbk", ".fbk", ".tbk", ".json")
    for d in dirs:
        for suf in suffixes:
            candidate = d / f"{stem}{suf}"
            if candidate.exists():
                return candidate
    return None


def load(path: str | Path) -> Book:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return _book_from_dict(path, json.loads(path.read_text(encoding="utf-8")))
    if path.suffix.lower() in (".fbk", ".fsk"):
        return _book_from_dict(path, unpack(path.read_bytes()))
    return _load_tbk(path)


def _book_from_dict(path: Path, data: dict) -> Book:
    pages = []
    for raw in data.get("pages") or []:
        handlers = []
        if raw.get("script"):
            handlers.append(Handler(name="script", source=raw["script"]))
        pages.append(Page(
            id=raw.get("id") or raw.get("name") or "",
            text=list(raw.get("text") or []),
            items=list(raw.get("items") or []),
            jumps=list(raw.get("jumps") or []),
            quiz=raw.get("quiz"),
            handlers=handlers,
            raw=raw,
        ))
    return Book(
        path=str(path),
        title=data.get("title") or path.stem,
        pages=pages,
        shells=list(data.get("shells") or []),
    )


def _load_tbk(path: Path) -> Book:
    try:
        from . import tbk as rtbk
        from .decode import constant_pools, decode
        from .expand import find_streams

        keywords = _keywords()
        data = path.read_bytes()
        raw = rtbk.load(path)
        pages = []
        any_handler = False
        for p in raw.pages:
            text = []
            for f in getattr(p, "fields", []) or []:
                t = getattr(f, "text", None)
                if t:
                    text.append(t)
            for para in getattr(p, "paragraphs", []) or []:
                if para and para not in text:
                    text.append(para)
            handlers = _handlers_from_blob(data, p.offset, p.blob, keywords, decode)
            any_handler = any_handler or bool(handlers)
            items = _items_from_handlers(handlers)
            extra = {"offset": p.offset}
            pools = constant_pools(p.blob)
            if pools:
                extra["pools"] = pools
            pages.append(Page(
                id=p.name,
                text=text,
                items=items,
                jumps=list(getattr(p, "quoted_jumps", None) or []),
                handlers=handlers,
                raw=extra,
            ))
        if not any_handler:
            pages.append(_script_page(data, keywords, find_streams))
        if _KEEP_DECODED:
            _write_decoded(path, pages)
        return Book(path=str(path), title=path.stem, pages=pages)
    except Exception as exc:
        book = Book(path=str(path), title=path.stem)
        book.pages.append(Page(
            id="(unloadable)",
            text=[f"Could not parse {path.name}: {exc}"],
        ))
        return book


def _script_page(data: bytes, keywords, find_streams) -> Page:
    """System books compress the handler name too, so the page scan finds nothing."""
    handlers = []
    for item in find_streams(data, keywords):
        text = item.get("text") or ""
        name = text.lstrip().split("\n", 1)[0][:80]
        handlers.append(Handler(name=name, source=text, offset=int(item["offset"], 16)))
    return Page(id="scripts", handlers=handlers, raw={"scanned": True})


def _write_decoded(path: Path, pages: list) -> None:
    from datetime import datetime
    root = Path(__file__).resolve().parents[1]
    dest_dir = root / "_debug" / "decoded"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "book": path.name,
        "decoded": stamp,
        "pages": [
            {
                "id": p.id,
                "handlers": [
                    {"name": h.name, "offset": h.offset, "source": h.source}
                    for h in (p.handlers or [])
                ],
            }
            for p in pages
            if p.handlers
        ],
    }
    out = dest_dir / f"{path.stem}-{stamp}.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")


def _keywords():
    if _BIN_OVERRIDE is not None:
        from .expand import load_keywords
        if not _BIN_OVERRIDE.exists():
            raise FileNotFoundError(f"keyword bin not found: {_BIN_OVERRIDE}")
        return load_keywords(_BIN_OVERRIDE)
    try:
        from .keywords import KEYWORDS
        if KEYWORDS:
            return KEYWORDS
    except ImportError:
        pass
    here = Path(__file__).resolve().parent
    bin_path = here / "compat" / "res_77.bin"
    if bin_path.exists():
        from .expand import load_keywords
        return load_keywords(bin_path)
    return []


def _handlers_from_blob(data: bytes, page_off: int, blob: bytes, keywords, decode) -> list:
    """Plain-text 'to handle' names, expanded against the whole file."""
    found = []
    if not blob or not keywords:
        return found
    for match in re.finditer(rb"(?i)to handle [A-Za-z][A-Za-z0-9]*", blob):
        origin = page_off + match.start()
        try:
            source = decode(data, keywords, origin=origin, span=4000)
        except Exception:
            source = ""
        if not source:
            continue
        kind = match.group().split()[-1].decode("latin1")
        found.append(Handler(name=kind, source=source, offset=origin))
    return found


def _items_from_handlers(handlers: list) -> list:
    items = []
    goto = re.compile(r'go\s+to\s+page\s+"([^"]+)"(?:\s+of\s+book\s+"([^"]+)")?', re.IGNORECASE)
    for h in handlers:
        if h.name.lower() != "buttonclick":
            continue
        src = h.source or ""
        low = src.lower()
        cut = low.find("\nend")
        if cut > 0:
            src = src[:cut]
            low = src.lower()
        m = goto.search(src)
        target = m.group(1) if m else ""
        other = m.group(2) if m else None
        if "go to next page" in low or (not target and "send next" in low):
            label = "Next"
        elif "go to previous" in low or "send previous" in low:
            label = "Back"
        elif other:
            label = f"{target}@{other}"
        elif target:
            label = target
        else:
            continue
        items.append({"label": label, "page": target, "book": other})
    return items
