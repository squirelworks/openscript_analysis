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
                _run_block(state, lines, body_start, else_at, actions)
            elif else_at < end_at:
                _run_block(state, lines, else_at + 1, end_at, actions)
            i = end_at + 1
            continue

        if low.startswith("step "):
            m = _STEP.match(line)
            if m:
                name, a, b, by = m.group(1), m.group(2), m.group(3), m.group(4)
                body_start = i + 1
                end_at = _find_end_step(lines, body_start, end)
                _run_step(state, name, a, b, by, lines, body_start, end_at, actions)
                i = end_at + 1
                continue

        if low.startswith("system "):
            i += 1
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
        m = _PUT.match(line)
        if m:
            value = _eval(m.group(1), state)
            state.variables[m.group(2)] = value
            actions.append({"kind": "set", "name": m.group(2), "value": value})
            i += 1
            continue
        m = _SET.match(line)
        if m:
            value = _eval(m.group(2), state)
            actions.append({"kind": "setprop", "target": m.group(1).strip(), "value": value})
            i += 1
            continue
        m = _GET.match(line)
        if m:
            value = _eval(m.group(1), state)
            actions.append({"kind": "get", "expr": m.group(1).strip(), "value": value})
            i += 1
            continue
        m = _INC.match(line)
        if m:
            name = m.group(2)
            cur = state.variables.get(name, 0)
            try:
                cur = int(cur)
            except (TypeError, ValueError):
                cur = 0
            cur = cur + 1 if m.group(1).lower() == "increment" else cur - 1
            state.variables[name] = cur
            actions.append({"kind": "set", "name": name, "value": cur})
            i += 1
            continue
        m = _ASSIGN.match(line)
        if m and not low.startswith("if "):
            name, expr = m.group(1), m.group(2).strip().rstrip(".")
            value = _eval(expr, state)
            state.variables[name] = value
            actions.append({"kind": "set", "name": name, "value": value})
            i += 1
            continue

        actions.append({"kind": "note", "text": line})
        i += 1
    return i


def _split_if(lines: list[str], start: int, end: int) -> tuple[int, int]:
    """Return (else_index_or_end, end_if_index) for the if that opened before start."""
    depth = 1
    else_at = end
    for i in range(start, end):
        low = lines[i].lower()
        if low.startswith("if ") and low.endswith(" then"):
            depth += 1
        elif low.startswith("else") and depth == 1 and else_at == end:
            else_at = i
        elif low.startswith("end if"):
            depth -= 1
            if depth == 0:
                return (else_at if else_at < i else i), i
    return end, end


def _find_end_step(lines: list[str], start: int, end: int) -> int:
    depth = 1
    for i in range(start, end):
        low = lines[i].lower()
        if low.startswith("step "):
            depth += 1
        elif low.startswith("end step"):
            depth -= 1
            if depth == 0:
                return i
    return end


def _run_step(state, name, a, b, by, lines, start, end, actions):
    try:
        lo = int(_eval(a, state))
        hi = int(_eval(b, state))
        step = int(_eval(by, state)) if by else 1
    except (TypeError, ValueError):
        actions.append({"kind": "note", "text": f"step {name} not numeric"})
        return
    if step == 0:
        return
    cur = lo
    guard = 0
    while (cur <= hi if step > 0 else cur >= hi) and guard < 10000:
        state.variables[name] = cur
        _run_block(state, lines, start, end, actions)
        cur += step
        guard += 1


def _eval(expr: str, state: RuntimeState):
    """Evaluate a small OpenScript expression."""
    expr = expr.strip().rstrip(".")
    if not expr:
        return ""
    low = expr.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null":
        return None
    m = _NAME_OF.fullmatch(expr)
    if m:
        if m.group(1).lower() == "book":
            return state.book.title or state.book.path
        page = state.page
        return page.id if page else ""
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return expr[1:-1]
    if re.fullmatch(r"-?\d+", expr):
        return int(expr)
    # and / or
    if " and " in low:
        i = low.index(" and ")
        return _truth(_eval(expr[:i], state)) and _truth(_eval(expr[i + 5:], state))
    if " or " in low:
        i = low.index(" or ")
        return _truth(_eval(expr[:i], state)) or _truth(_eval(expr[i + 4:], state))
    if low.startswith("not "):
        return not _truth(_eval(expr[4:], state))
    # comparisons, longest operator first
    padded = f" {expr} "
    for op in (" <> ", " != ", " <= ", " >= ", " < ", " > ", " = "):
        idx = padded.find(op)
        if idx >= 0:
            left = padded[:idx].strip()
            right = padded[idx + len(op):].strip()
            return _cmp(op.strip(), _eval(left, state), _eval(right, state))
    if expr in state.variables:
        return state.variables[expr]
    return expr


def _cmp(op: str, a, b) -> bool:
    if op in ("=",):
        return a == b
    if op in ("<>", "!="):
        return a != b
    try:
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "<=":
            return a <= b
        if op == ">=":
            return a >= b
    except TypeError:
        return False
    return False


def _truth(value) -> bool:
    if isinstance(value, str):
        return value.lower() not in ("", "false", "0")
    return bool(value)


def goto(state: RuntimeState, page_id: str) -> bool:
    idx = state.book.index_of(page_id)
    if idx < 0:
        # case-insensitive fallback; real books mix P1292 and p1292
        for i, p in enumerate(state.book.pages):
            if p.id.lower() == page_id.lower():
                state.index = i
                state.note(f"goto {p.id}")
                return True
        state.note(f"missing page {page_id}")
        return False
    state.index = idx
    state.note(f"goto {page_id}")
    return True


def open_book(state: RuntimeState, book_name: str, page_id: str) -> bool:
    """Open another book found near the current one and go to page_id."""
    from .loader import load, find_book
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
                if _follow_label(state, "next"):
                    return True
                if state.index + 1 < len(state.book.pages):
                    state.index += 1
                    return True
            if name in ("previous", "back"):
                if _follow_label(state, "back"):
                    return True
                if state.index > 0:
                    state.index -= 1
                    return True
    return False


def _follow_label(state: RuntimeState, label: str) -> bool:
    page = state.page
    if not page:
        return False
    for item in page.items or []:
        if (item.get("label") or "").lower() == label and item.get("page"):
            return goto(state, item["page"])
    return False


def run_page_handlers(state: RuntimeState, kind: str = "enterpage") -> list[dict]:
    """Run handlers of the given kind on the current page."""
    page = state.page
    if not page:
        return []
    actions: list[dict] = []
    for h in page.handlers or []:
        if h.name.lower() != kind.lower():
            continue
        actions.extend(run_handler(state, h.source))
    return actions
