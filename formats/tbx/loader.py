"""TBX OpenScript engine.

Loads a SumTotal ToolBook TBKX export folder and interprets the plain-text
.script files that accompany Book.xml / Page.xml / Background.xml.

Page keys are the XML Name attribute (P1040, P430, ...), not the folder name.
Backgrounds are loaded the same way. Page.Objects are walked for kind, Name,
Bounds, Vertices, and parent Group. Bitmap references are recorded.
Export-only pages (P440, P2920 in the 9e954d01 corpus) are flagged.

Runner covers the subset that appears in the Nida lessons:
  go to page / of book, send, assignment, get/set, put,
  if/else/end if (nested), conditions/when, increment, step, forward.
Handler lookup is case-insensitive.

report() and coverage() emit the jump graph and construct counts.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Pages present in the TBX export of 9e954d01 but not in the raw TBK.
EXPORT_ONLY = {"P440", "P2920"}


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


@dataclass
class TbxObject:
    kind: str
    name: str = ""
    bounds: str = ""
    vertices: str = ""
    parent: str = ""
    fill: str = ""
    script_file: str | None = None


@dataclass
class TbxPage:
    id_number: str
    name: str
    background: str = ""
    script_file: str | None = None
    objects: list[TbxObject] = field(default_factory=list)
    export_only: bool = False


@dataclass
class TbxBook:
    path: str
    title: str = ""
    pages: dict[str, TbxPage] = field(default_factory=dict)
    backgrounds: dict[str, TbxPage] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    bitmaps: dict[str, str] = field(default_factory=dict)  # id -> Source file


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
        root_el = tree.getroot()
        book.title = root_el.get("Caption") or root_el.get("Title") or ""
        for el in root_el.iter():
            if _local(el.tag) == "Bitmap":
                bid = el.get("IdNumber") or el.get("Id") or ""
                src = el.get("Source") or ""
                if bid and src:
                    book.bitmaps[bid] = src
    for page_xml in root.rglob("Page.xml"):
        page = _load_page(page_xml)
        if page:
            book.pages[page.name] = page
    for bg_xml in root.rglob("Background.xml"):
        bg = _load_page(bg_xml)
        if bg:
            book.backgrounds[bg.name] = bg
    for script in root.rglob("*.script"):
        book.scripts[script.name] = script.read_text(encoding="utf-8", errors="replace")
    return book


def _load_page(xml_path: Path) -> TbxPage | None:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    el = tree.getroot()
    name = el.get("Name") or xml_path.parent.name
    page = TbxPage(
        id_number=el.get("IdNumber") or "",
        name=name,
        background=el.get("Background") or "",
        script_file=el.get("Script") or None,
        export_only=name in EXPORT_ONLY,
    )
    objs = el.find(".//{urn:sumtotalsystems:toolbook.tbkx}Page.Objects")
    if objs is None:
        objs = el.find(".//{urn:sumtotalsystems:toolbook.tbkx}Background.Objects")
    if objs is not None:
        page.objects = _walk_objects(objs, parent="")
    return page


def _walk_objects(el: ET.Element, parent: str) -> list[TbxObject]:
    out: list[TbxObject] = []
    for child in el:
        tag = _local(child.tag)
        if tag in ("Page.Objects", "Background.Objects", "Group.Objects", "UserProperties"):
            continue
        name = child.get("Name") or ""
        obj = TbxObject(
            kind=tag,
            name=name,
            bounds=child.get("Bounds") or "",
            vertices=child.get("Vertices") or "",
            parent=parent,
            fill=child.get("FillColor") or "",
            script_file=child.get("Script") or None,
        )
        out.append(obj)
        # recurse into groups
        for sub in child:
            if _local(sub.tag) in ("Group.Objects", "Objects"):
                out.extend(_walk_objects(sub, parent=name or tag))
    return out


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
        if low.startswith("to handle") or low.startswith("system "):
            continue
        if low in ("end", "end handler", "end if", "end conditions"):
            out.append(line)  # keep structural ends for the runner
            if low in ("end", "end handler"):
                break
            continue
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
                actions.append({
                    "kind": "goto",
                    "page": m.group(1),
                    "book": book_m.group(1) if book_m else None,
                })
            i += 1
            continue
        if low.startswith("send "):
            actions.append({"kind": "send", "name": line.split(None, 1)[1].lower()})
            i += 1
            continue
        if low.startswith("forward"):
            actions.append({"kind": "forward"})
            i += 1
            continue
        if low.startswith("get "):
            actions.append({"kind": "get", "expr": line[4:].strip()})
            i += 1
            continue
        if low.startswith("set "):
            actions.append({"kind": "set", "expr": line[4:].strip()})
            i += 1
            continue
        if low.startswith("increment "):
            name = line.split(None, 1)[1].strip()
            actions.append({"kind": "increment", "name": name})
            i += 1
            continue
        if low.startswith("step "):
            actions.append({"kind": "step", "expr": line[5:].strip()})
            i += 1
            continue
        if low.startswith("if "):
            i = _run_if(state, lines, i, end, actions)
            continue
        if low.startswith("conditions"):
            i = _run_conditions(state, lines, i, end, actions)
            continue
        if " = " in line and not low.startswith("if "):
            name, expr = line.split("=", 1)
            state.variables[name.strip()] = expr.strip()
            i += 1
            continue
        state.note(f"skip: {line}")
        i += 1
    return i


def _run_if(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    """Handle if / else / end if. Condition is recorded, not evaluated."""
    actions.append({"kind": "if", "cond": lines[start][3:].strip()})
    i = start + 1
    depth = 1
    while i < end and depth > 0:
        low = lines[i].lower()
        if low.startswith("if "):
            depth += 1
        elif low == "end if":
            depth -= 1
            if depth == 0:
                i += 1
                break
        elif low == "else" and depth == 1:
            actions.append({"kind": "else"})
            i += 1
            continue
        else:
            i = _run_block(state, lines, i, i + 1, actions)
            continue
        i += 1
    actions.append({"kind": "end if"})
    return i


def _run_conditions(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    actions.append({"kind": "conditions"})
    i = start + 1
    while i < end:
        low = lines[i].lower()
        if low == "end conditions":
            actions.append({"kind": "end conditions"})
            return i + 1
        if low.startswith("when "):
            actions.append({"kind": "when", "cond": lines[i][5:].strip()})
            i += 1
            continue
        i = _run_block(state, lines, i, i + 1, actions)
    return i


def report(book: TbxBook) -> dict:
    """Jump graph and handler counts from a loaded book."""
    handlers: Counter = Counter()
    gotos: Counter = Counter()
    books: Counter = Counter()
    for name, src in book.scripts.items():
        for m in re.finditer(r"to handle (\w+)", src, re.I):
            handlers[m.group(1).lower()] += 1
        for m in re.finditer(r'go to page "([^"]+)"(?: of book "([^"]+)")?', src, re.I):
            gotos[m.group(1)] += 1
            if m.group(2):
                books[m.group(2)] += 1
    return {
        "pages": len(book.pages),
        "backgrounds": len(book.backgrounds),
        "bitmaps": len(book.bitmaps),
        "handlers": handlers.most_common(),
        "goto_targets": gotos.most_common(20),
        "external_books": dict(books),
        "export_only": [p.name for p in book.pages.values() if p.export_only],
    }


def coverage(book: TbxBook) -> dict:
    """Construct counts across all scripts. Useful as a regression check."""
    counts: Counter = Counter()
    pats = {
        "if": r"\bif\b",
        "else": r"\belse\b",
        "conditions": r"\bconditions\b",
        "when": r"\bwhen\b",
        "step": r"\bstep\b",
        "increment": r"\bincrement\b",
        "set": r"\bset\b",
        "get": r"\bget\b",
        "forward": r"\bforward\b",
        "put": r"\bput\b",
    }
    for src in book.scripts.values():
        low = src.lower()
        for name, pat in pats.items():
            counts[name] += len(re.findall(pat, low))
    return dict(counts.most_common())


def main():
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--page")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    args = ap.parse_args()
    book = load_tbx(args.folder)
    if args.list:
        for name in sorted(book.pages):
            flag = " *" if book.pages[name].export_only else ""
            print(f"{name}{flag}")
        return
    if args.report:
        print(json.dumps(report(book), indent=2))
        return
    if args.coverage:
        print(json.dumps(coverage(book), indent=2))
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
        print("Use --page P900, --list, --report, or --coverage")


if __name__ == "__main__":
    main()
