"""OpenScript engine.

Runs handler source and returns actions the viewer should perform.
The same runner serves .tbk/.sbk (decoded source) and .fbk/.fsk (authored source).

Handled:
  go to page "P" [of book "B"]
  send NAME
  NAME = EXPR
  put EXPR into NAME
  set PROP of TARGET to EXPR
  get EXPR
  increment / decrement NAME
  if / else / end if (nested)
  step NAME from A to B
  name of this book / name of this page
  system declarations (ignored)
  stops at the first standalone end, so trailing decode garbage is dropped
"""

from __future__ import annotations

import re
from .model import RuntimeState


_GOTO = re.compile(
    r'go\s+to\s+page\s+"([^"]+)"(?:\s+of\s+book\s+"([^"]+)")?',
    re.IGNORECASE,
)
_SEND = re.compile(r'send\s+(\w+)', re.IGNORECASE)
_PUT = re.compile(r'put\s+(.+?)\s+into\s+(\w+)', re.IGNORECASE)
_SET = re.compile(r'set\s+(.+?)\s+to\s+(.+)', re.IGNORECASE)
_GET = re.compile(r'get\s+(.+)', re.IGNORECASE)
_STEP = re.compile(
    r'step\s+(\w+)\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+by\s+(.+))?$',
    re.IGNORECASE,
)
_INC = re.compile(r'(increment|decrement)\s+(\w+)', re.IGNORECASE)
_ASSIGN = re.compile(r'(\w+)\s*=\s*(.+)')
_NAME_OF = re.compile(r'name\s+of\s+this\s+(book|page)', re.IGNORECASE)


def run_handler(state: RuntimeState, source: str) -> list[dict]:
    """Execute a handler source against the current state."""
    actions: list[dict] = []
    if not source:
        return actions
    lines = _lines(source)
    _run_block(state, lines, 0, len(lines), actions)
    return actions


def _lines(source: str) -> list[str]:
    """Normalize and stop at the first standalone end."""
    out = []
    for raw in source.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        low = line.lower()
        if low.startswith("to handle"):
            continue
        if low == "end" or low == "end handler":
            break
        out.append(line)
    return out


def _run_block(state: RuntimeState, lines: list[str], start: int, end: int, actions: list[dict]) -> int:
    """Run lines[start:end]. Returns the index after the block consumed."""
    i = start
    while i < end:
        line = lines[i]
        low = line.lower()

        if low.startswith("if ") and low.endswith(" then"):
            cond = line[3:low.rfind(" then")].strip()
            body_start = i + 1
            else_at, end_at = _split_if(lines, body_start, end)
            if _truth(_eval(cond, state)):
                i = _run_block(state, lines, body_start, else_at if else_at >= 0 else end_at, actions)
            elif else_at >= 0:
                i = _run_block(state, lines, else_at + 1, end_at, actions)
            else:
                i = end_at
            continue

        m = _GOTO.search(line)
        if m:
            actions.append({"kind": "goto", "page": m.group(1), "book": m.group(2)})
            i += 1
            continue
        m = _SEND.search(line)
        if m:
            actions.append({"kind": "send", "name": m.group(1)})
            i += 1
            continue
        m = _PUT.search(line)
        if m:
            state.variables[m.group(2)] = _eval(m.group(1), state)
            i += 1
            continue
        m = _SET.search(line)
        if m:
            actions.append({"kind": "set", "prop": m.group(1), "value": m.group(2)})
            i += 1
            continue
        m = _GET.search(line)
        if m:
            actions.append({"kind": "get", "expr": m.group(1)})
            i += 1
            continue
        m = _INC.search(line)
        if m:
            name = m.group(2)
            cur = state.variables.get(name, 0)
            try:
                cur = int(cur)
            except (TypeError, ValueError):
                cur = 0
            state.variables[name] = cur + (1 if m.group(1).lower() == "increment" else -1)
            i += 1
            continue
        m = _ASSIGN.match(line)
        if m:
            state.variables[m.group(1)] = _eval(m.group(2), state)
            i += 1
            continue
        m = _NAME_OF.search(line)
        if m:
            kind = m.group(1).lower()
            if kind == "book":
                actions.append({"kind": "name", "of": "book", "value": state.book.title})
            else:
                actions.append({"kind": "name", "of": "page", "value": state.page.id if state.page else ""})
            i += 1
            continue
        # unknown line — note and skip
        state.note(f"skip: {line}")
        i += 1
    return i


def _split_if(lines: list[str], start: int, end: int) -> tuple[int, int]:
    depth = 0
    else_at = -1
    for i in range(start, end):
        low = lines[i].lower()
        if low.startswith("if ") and low.endswith(" then"):
            depth += 1
        elif low == "end if" or low == "end":
            if depth == 0:
                return else_at, i
            depth -= 1
        elif low == "else" and depth == 0 and else_at < 0:
            else_at = i
    return else_at, end


def _eval(expr: str, state: RuntimeState):
    expr = expr.strip()
    if expr.lower() == "true":
        return True
    if expr.lower() == "false":
        return False
    if expr.isdigit() or (expr.startswith("-") and expr[1:].isdigit()):
        return int(expr)
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return expr[1:-1]
    if expr in state.variables:
        return state.variables[expr]
    return expr


def _truth(v) -> bool:
    if v is None or v is False or v == 0 or v == "":
        return False
    return True


def goto(state: RuntimeState, page_id: str) -> bool:
    for i, p in enumerate(state.book.pages):
        if p.id.lower() == page_id.lower():
            state.index = i
            state.note(f"goto {p.id}")
            return True
    state.note(f"missing page {page_id}")
    return False


def open_book(state: RuntimeState, book_name: str, page_id: str) -> bool:
    """Open another book found near the current one and go to page_id."""
    from ..formats.tbk.loader import load, find_book
    found = find_book(book_name, state.book.path)
    if not found:
        state.note(f"missing book {book_name}")
        return False
    state.book = load(found)
    state.index = 0
    state.note(f"open {found.name}")
    if page_id:
        return goto(state, page_id)
    return True


def follow(state: RuntimeState, actions: list[dict]) -> bool:
    """Apply the first navigation action. Returns True if the page changed."""
    for act in actions:
        if act.get("kind") == "goto":
            page = act.get("page")
            book = act.get("book")
            if book:
                return open_book(state, book, page or "")
            if page and goto(state, page):
                return True
        if act.get("kind") == "send":
            name = (act.get("name") or "").lower()
            if name == "next":
                if state.index + 1 < len(state.book.pages):
                    state.index += 1
                    return True
            if name in ("previous", "back"):
                if state.index > 0:
                    state.index -= 1
                    return True
    return False
