"""Minimal TBK page walker used by the analysis package.

This is intentionally thin. The full reader lives in the runtime/
package; here we only need page names and the script property so the
expander and runner can operate.
"""

import struct
from pathlib import Path

MARKER = bytes([0x80, 0x65, 0x00, 0x05, 0x00, 0x02, 0x02])

def find_pages(data: bytes) -> list[tuple[int, str]]:
    pages = []
    start = 0
    while True:
        i = data.find(MARKER, start)
        if i < 0:
            break
        # Name is a 32-byte field immediately after the marker
        name = data[i + 7 : i + 39].split(b"\x00", 1)[0].decode("latin-1", errors="replace")
        if name.startswith("P"):
            pages.append((i, name))
        start = i + 7
    return pages

def load_tbk(path: str | Path) -> list[tuple[str, str]]:
    data = Path(path).read_bytes()
    # Script extraction is left to the expander; here we only return names.
    return [(name, "") for _, name in find_pages(data)]
