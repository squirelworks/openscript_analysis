"""CLI entry: python3 -m openscript_analysis.tbk.openscript_analysis book.tbk out.json"""

import json
import sys
from pathlib import Path

from .loader import load_book

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python3 -m openscript_analysis.tbk.openscript_analysis book.tbk [out.json]", file=sys.stderr)
        return 2
    book = load_book(sys.argv[1])
    out = {
        "name": book.name,
        "pages": [
            {
                "name": p.name,
                "script": p.script,
                "actions": [{"kind": a.kind, "target": a.target, "value": a.value} for a in p.actions],
            }
            for p in book.pages
        ],
    }
    text = json.dumps(out, indent=2)
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(text)
    else:
        print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
