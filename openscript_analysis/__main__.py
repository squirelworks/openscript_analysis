"""python3 -m openscript_analysis book.tbk [handlers.json]

Expands every compressed handler in the book and writes them as JSON.
"""

import json
import sys
from pathlib import Path

from .expand import find_streams, load_keywords


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python3 -m openscript_analysis <book.tbk|book.sbk> [out.json]", file=sys.stderr)
        return 2
    book = Path(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else book.with_suffix(".handlers.json")
    keywords = load_keywords(Path(__file__).resolve().parent / "compat" / "res_77.bin")
    handlers = find_streams(book.read_bytes(), keywords)
    out.write_text(json.dumps(handlers, indent=2), encoding="utf-8")
    print(f"{len(handlers)} handlers -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
