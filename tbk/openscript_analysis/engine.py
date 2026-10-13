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
  conditions / when / else / end conditions
  step NAME from A to B
  name of this book / name of this page
  system declarations (ignored)
  forward / break

Stops at the first standalone end so decode garbage is dropped.
"""

from __future__ import annotations

import re
from typing import Any

from .model import Action

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
_END = re.compile(r'^\s*end\s*$', re.I)

def run_handler(src: str, ctx: dict[str, Any] | None = None) -> list[Action]:
    """Execute a single handler and return the action list."""
    if not src:
        return []
    actions: list[Action] = []
    lines = src.splitlines()
    i = 0
    depth = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("--"):
            continue
        if _END.match(line) and depth == 0:
            break
        if m := _GOTO.search(line):
            actions.append(Action("goto", m.group(1), m.group(2) or ""))
            continue
        if m := _SEND.search(line):
            actions.append(Action("send", m.group(1)))
            continue
        if m := _ASSIGN.match(line):
            actions.append(Action("assign", m.group(1), m.group(2).strip()))
            continue
        if m := _PUT.search(line):
            actions.append(Action("put", m.group(2), m.group(1).strip()))
            continue
        if m := _SET.search(line):
            actions.append(Action("set", m.group(1), (m.group(2).strip(), m.group(3).strip())))
            continue
        if m := _GET.search(line):
            actions.append(Action("get", m.group(1).strip()))
            continue
        if m := _INC.search(line):
            actions.append(Action(m.group(1).lower(), m.group(2)))
            continue
        if _IF.match(line):
            depth += 1
            actions.append(Action("if", line))
            continue
        if _ELSE.match(line):
            actions.append(Action("else"))
            continue
        if _ENDIF.match(line):
            depth = max(0, depth - 1)
            actions.append(Action("end if"))
            continue
        if _COND.match(line):
            depth += 1
            actions.append(Action("conditions"))
            continue
        if m := _WHEN.match(line):
            actions.append(Action("when", m.group(1).strip()))
            continue
        if _ENDCOND.match(line):
            depth = max(0, depth - 1)
            actions.append(Action("end conditions"))
            continue
        if m := _STEP.match(line):
            actions.append(Action("step", m.group(1), (m.group(2).strip(), m.group(3).strip())))
            continue
        if m := _NAMEOF.search(line):
            actions.append(Action("nameof", m.group(1).lower()))
            continue
        # fall-through: keep the line as a note so nothing is silently dropped
        actions.append(Action("note", line))
    return actions

def run_page(script: str, ctx: dict[str, Any] | None = None) -> list[Action]:
    """Run every handler in a page script."""
    if not script:
        return []
    # Split on "to handle" so each handler is independent
    parts = re.split(r'(?=to\s+handle\s+)', script, flags=re.I)
    actions: list[Action] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        actions.extend(run_handler(part, ctx))
    return actions
