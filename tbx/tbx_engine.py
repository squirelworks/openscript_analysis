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

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Action:
    kind: str
    target: str = ""
    value: Any = None


@dataclass
class State:
    book_name: str = ""
    page_name: str = ""
    vars: dict[str, Any] = field(default_factory=dict)
    actions: list[Action] = field(default_factory=list)


_GOTO = re.compile(
    r'go\s+to\s+page\s+"([^"]+)"(?:\s+of\s+book\s+"([^"]+)")?',
    re.I,
)
_SEND = re.compile(r'send\s+(\w+)', re.I)
_ASSIGN = re.compile(r'^\s*(\w+)\s*=\s*(.+)$')
_PUT = re.compile(r'put\s+(.+?)\s+into\s+(\w+)', re.I)
_SET = re.compile(r'set\s+(\w+)\s+of\s+(.+?)\s+to\s+(.+)', re.I)
_GET = re.compile(r'get\s+(.+)', re.I)
_INC = re.compile(r'(increment|decrement)\s+(\w+)', re.I)
_IF = re.compile(r'^\s*if\s+(.+)\s*$', re.I)
_ELSE = re.compile(r'^\s*else\s*$', re.I)
_ENDIF = re.compile(r'^\s*end\s+if\s*$', re.I)
_COND = re.compile(r'^\s*conditions\s*$', re.I)
_WHEN = re.compile(r'^\s*when\s+(.+)\s*$', re.I)
_ENDCOND = re.compile(r'^\s*end\s+conditions\s*$', re.I)
_STEP = re.compile(r'^\s*step\s+(\w+)\s+from\s+(.+?)\s+to\s+(.+?)\s*$', re.I)
_NAMEOF = re.compile(r'name\s+of\s+this\s+(book|page)', re.I)
_SYSTEM = re.compile(r'^\s*system\s+', re.I)
_FORWARD = re.compile(r'^\s*forward\s*$', re.I)
_BREAK = re.compile(r'^\s*break\s*$', re.I)
_END = re.compile(r'^\s*end\s*$', re.I)
_HANDLER = re.compile(r'^\s*to\s+handle\s+(\w+)', re.I)


def run_script(state: State, src: str) -> list[dict[str, Any]]:
    """Interpret a script and append actions to state. Returns the action list."""
    if not src:
        return []
    lines = src.splitlines()
    i = 0
    depth = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if _HANDLER.match(stripped):
            continue
        if _END.match(stripped) and depth == 0:
            break
        if _SYSTEM.match(stripped):
            continue
        if _FORWARD.match(stripped):
            state.actions.append(Action("forward"))
            continue
        if _BREAK.match(stripped):
            state.actions.append(Action("break"))
            continue
        if m := _GOTO.search(stripped):
            state.actions.append(Action("goto", m.group(1), m.group(2) or ""))
            continue
        if m := _SEND.search(stripped):
            state.actions.append(Action("send", m.group(1)))
            continue
        if m := _ASSIGN.match(stripped):
            state.actions.append(Action("assign", m.group(1), m.group(2).strip()))
            continue
        if m := _PUT.search(stripped):
            state.actions.append(Action("put", m.group(2), m.group(1).strip()))
            continue
        if m := _SET.search(stripped):
            state.actions.append(
                Action("set", m.group(1), (m.group(2).strip(), m.group(3).strip()))
            )
            continue
        if m := _GET.search(stripped):
            state.actions.append(Action("get", m.group(1).strip()))
            continue
        if m := _INC.search(stripped):
            state.actions.append(Action(m.group(1).lower(), m.group(2)))
            continue
        if _IF.match(stripped):
            depth += 1
            state.actions.append(Action("if", stripped))
            continue
        if _ELSE.match(stripped):
            state.actions.append(Action("else"))
            continue
        if _ENDIF.match(stripped):
            depth = max(0, depth - 1)
            state.actions.append(Action("end if"))
            continue
        if _COND.match(stripped):
            depth += 1
            state.actions.append(Action("conditions"))
            continue
        if m := _WHEN.match(stripped):
            state.actions.append(Action("when", m.group(1).strip()))
            continue
        if _ENDCOND.match(stripped):
            depth = max(0, depth - 1)
            state.actions.append(Action("end conditions"))
            continue
        if m := _STEP.match(stripped):
            state.actions.append(
                Action("step", m.group(1), (m.group(2).strip(), m.group(3).strip()))
            )
            continue
        if m := _NAMEOF.search(stripped):
            state.actions.append(Action("nameof", m.group(1).lower()))
            continue
        state.actions.append(Action("note", stripped))
    return [{"kind": a.kind, "target": a.target, "value": a.value} for a in state.actions]


def load_tbx(folder: str | Path) -> dict[str, Any]:
    """Load Book.xml / Page.xml / Background.xml and associated .script files."""
    root = Path(folder)
    book_xml = root / "Book.xml"
    if not book_xml.exists():
        raise FileNotFoundError(f"No Book.xml in {root}")
    tree = ET.parse(book_xml)
    book = tree.getroot()
    name = book.get("Name") or book.findtext("Name") or root.name
    pages = []
    for page_xml in sorted(root.glob("Page*.xml")):
        pt = ET.parse(page_xml)
        pr = pt.getroot()
        pid = pr.get("IdNumber") or pr.findtext("IdNumber") or ""
        pname = pr.get("Name") or pr.findtext("Name") or page_xml.stem
        script_path = root / f"{page_xml.stem}.script"
        script = script_path.read_text(encoding="utf-8", errors="replace") if script_path.exists() else ""
        pages.append({"id": pid, "name": pname, "script": script, "file": page_xml.name})
    return {"name": name, "pages": pages, "folder": str(root)}


def main() -> None:
    ap = argparse.ArgumentParser(description="TBX OpenScript engine")
    ap.add_argument("folder", help="Path to the TBKX export folder")
    ap.add_argument("--list", action="store_true", help="List pages")
    ap.add_argument("--page", help="Run the script for a named page (e.g. P900)")
    ap.add_argument("--book", action="store_true", help="Run Book.script")
    ap.add_argument("--script", help="Run an arbitrary .script file")
    args = ap.parse_args()

    book = load_tbx(args.folder)
    state = State(book_name=book["name"])

    if args.list:
        for p in book["pages"]:
            print(f"{p['name']}\t{p['id']}\t{len(p['script'])} chars")
        return

    if args.book:
        book_script = Path(args.folder) / "Book.script"
        if book_script.exists():
            run_script(state, book_script.read_text(encoding="utf-8", errors="replace"))
            print(json.dumps(state.actions, indent=2, default=str))
        else:
            print("No Book.script")
        return

    if args.page:
        match = next((p for p in book["pages"] if p["name"] == args.page), None)
        if not match:
            print(f"Page {args.page} not found")
            return
        state.page_name = match["name"]
        run_script(state, match["script"])
        print(json.dumps([{"kind": a.kind, "target": a.target, "value": a.value} for a in state.actions], indent=2, default=str))
        return

    if args.script:
        src = Path(args.script).read_text(encoding="utf-8", errors="replace")
        if not src:
            print(f"script not found: {args.script}")
            return
        actions = run_script(state, src)
        print(json.dumps(actions, indent=2, default=str))
    else:
        print("Use --page P900 or --script Book.script or --list")


if __name__ == "__main__":
    main()
