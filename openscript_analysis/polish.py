#!/usr/bin/env python3
"""Polish decompressed OpenScript text.

Normalizes the output of openscript_decompress.py:
  - \\r\\n  -> \\n
  - keeps \\t as tab
  - strips trailing whitespace on each line
  - optionally drops lines that are mostly '?' (failed back-references)

Usage:
    python3 openscript_polish.py <handlers.json> [output.json]
    python3 openscript_polish.py <handlers.json> --text [output.txt]
"""

import json
import sys
from pathlib import Path


def polish(text: str, drop_noisy: bool = False) -> str:
    """Normalize one handler body."""
    # CRLF -> LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        if drop_noisy and line.count("?") > 8:
            continue
        lines.append(line)
    # collapse excessive blank lines
    out = []
    blank = 0
    for line in lines:
        if line == "":
            blank += 1
            if blank <= 2:
                out.append(line)
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).strip() + "\n"


def main():
    if len(sys.argv) < 2:
        print("usage: openscript_polish.py <handlers.json> [--text] [output]", file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1])
    as_text = "--text" in sys.argv
    args = [a for a in sys.argv[2:] if a != "--text"]
    out = Path(args[0]) if args else src.with_name(src.stem + "_polished" + (".txt" if as_text else ".json"))

    handlers = json.loads(src.read_text(encoding="utf-8"))
    polished = []
    for h in handlers:
        body = polish(h.get("text", ""), drop_noisy=False)
        polished.append({
            "offset": h.get("offset"),
            "name": h.get("name", "").split("\n")[0][:100],
            "text": body,
        })

    if as_text:
        parts = []
        for h in polished:
            parts.append(f"-- {h['offset']}  {h['name']}\n{h['text']}")
        out.write_text("\n".join(parts), encoding="utf-8")
    else:
        out.write_text(json.dumps(polished, indent=2), encoding="utf-8")

    print(f"polished {len(polished)} handlers -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
