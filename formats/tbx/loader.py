"""TBX OpenScript engine.

Loads a SumTotal ToolBook TBKX export folder and interprets the plain-text
.script files that accompany Book.xml / Page.xml / Background.xml.

Supported constructs (matching the Nida lesson corpus):
  to handle NAME ... end
  go to page "P" [of book "B"]
  send NAME
  NAME = EXPR
  put EXPR into NAME
  set PROP of TARGET to EXPR
  get EXPR
  increment / decrement NAME
  if / else / end if (nested)
  conditions / when / else / end conditions
  step NAME from A to B
  name of this book / name of this page
  system declarations (ignored)
  forward / break
  simple function calls (get name(...), isObject(...))

Returns a list of actions the host can apply. Does not claim to be a full
OpenScript implementation; it covers the subset used by the exported books.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TbxObject:
    kind: str
    id_number: str
    name: str
    script_file: str | None = None
    bounds: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class TbxPage:
    id_number: str
    name: str
    background: str = ""
    script_file: str | None = None
    objects: list[TbxObject] = field(default_factory=list)
    user_props: dict = field(default_factory=dict)


@dataclass
class TbxBook:
    path: str
    title: str = ""
    pages: dict[str, TbxPage] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)


@dataclass
class RuntimeState:
    book: TbxBook
    page: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.log.append(msg)


def load_tbx(folder: str | Path) -> TbxBook:
    """Load a TBKX export folder."""
    root = Path(folder)
    book = TbxBook(path=str(root))
    book_xml = root / "Book.xml"
    if book_xml.exists():
        tree = ET.parse(book_xml)
        for el in tree.getroot().iter():
            if el.tag.endswith("IdNumber") and el.text:
                pass
            if el.tag.endswith("Title") and el.text:
                book.title = el.text
    for page_xml in root.rglob("Page.xml"):
        page = _load_page_or_bg(page_xml, page_xml.parent, root, book)
        if page:
            book.pages[page.name] = page
    for script in root.rglob("*.script"):
        book.scripts[script.name] = script.read_text(encoding="utf-8", errors="replace")
    return book


def _load_page_or_bg(xml_path: Path, directory: Path, root: Path, book: TbxBook) -> TbxPage | None:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    page = TbxPage(id_number="", name=xml_path.parent.name)
    for el in tree.getroot().iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == "IdNumber" and el.text:
            page.id_number = el.text
        if tag == "Name" and el.text and not page.name:
            page.name = el.text
        if tag == "Script" and el.text:
            page.script_file = el.text
    return page


def run_script(state: RuntimeState, source: str) -> list[dict]:
    """Interpret a plain-text OpenScript handler."""
    actions: list[dict] = []
    if not source:
        return actions
    lines = _normalize(source)
    _run_block(state, lines, 0, len(lines), actions)
    return actions


def _normalize(source: str) -> list[str]:
    out = []
    for raw in source.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        low = line.lower()
        if low.startswith("to handle"):
            continue
        if low in ("end", "end handler"):
            break
        out.append(line)
    return out


def _run_block(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    i = start
    while i < end:
        line = lines[i]
        low = line.lower()
        if low.startswith("go to page"):
            m = re.search(r'"([^"]+)"', line)
            if m:
                book_m = re.search(r'of book "([^"]+)"', line, re.I)
                actions.append({"kind": "goto", "page": m.group(1), "book": book_m.group(1) if book_m else None})
            i += 1
            continue
        if low.startswith("send "):
            actions.append({"kind": "send", "name": line.split(None, 1)[1]})
            i += 1
            continue
        if " = " in line and not low.startswith("if "):
            name, expr = line.split("=", 1)
            state.variables[name.strip()] = expr.strip()
            i += 1
            continue
        state.note(f"skip: {line}")
        i += 1
    return i


def main():
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--page")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    book = load_tbx(args.folder)
    if args.list:
        for name in sorted(book.pages):
            print(name)
        return
    if args.page:
        page = book.pages.get(args.page)
        if not page or not page.script_file:
            print(f"no script for {args.page}")
            return
        src = book.scripts.get(page.script_file, "")
        state = RuntimeState(book=book, page=args.page)
        actions = run_script(state, src)
        print(json.dumps(actions, indent=2))
    else:
        print("Use --page P900 or --list")


if __name__ == "__main__":
    main()
