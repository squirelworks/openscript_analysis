#!/usr/bin/env python3
"""OpenScript bytecode decompressor.

Implements FUN_1040_0970 from TB80CMP.DLL (resource 0x77 keyword table).
Back-references (0xC0-0xFF) copy from the compressed input stream.
"""

from pathlib import Path

def expand(data: bytes, keywords: list[str]) -> str:
    """Expand a compressed OpenScript handler into source text."""
    if not data:
        return ""
    out = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        i += 1
        if b < 0x80:
            # literal run
            out.append(chr(b))
        elif b < 0xC0:
            # keyword index
            idx = b - 0x80
            if idx < len(keywords):
                out.append(keywords[idx])
            else:
                out.append(f"/*kw{idx}*/")
        else:
            # back-reference into the compressed input
            length = (b & 0x3F) + 3
            if i >= n:
                break
            dist = data[i]
            i += 1
            if dist == 0:
                dist = 256
            start = len(out) - dist
            if start < 0:
                start = 0
            for _ in range(length):
                if start < len(out):
                    out.append(out[start])
                    start += 1
                else:
                    break
    return "".join(out)

def load_keywords(path: str | Path | None = None) -> list[str]:
    """Load the keyword table from res_77.bin or the JSON transcription."""
    if path is None:
        here = Path(__file__).resolve().parent
        path = here / "compat" / "res_77.bin"
    p = Path(path)
    if not p.exists():
        return []
    data = p.read_bytes()
    # Resource layout: word count at offset 2, then count*4 offset table, then strings
    if len(data) < 6:
        return []
    count = int.from_bytes(data[2:4], "little")
    offsets = []
    base = 4
    for k in range(count):
        off = int.from_bytes(data[base + k*4 : base + k*4 + 4], "little")
        offsets.append(off)
    strings = []
    for off in offsets:
        end = data.find(b"\x00", off)
        if end < 0:
            end = len(data)
        strings.append(data[off:end].decode("latin-1", errors="replace"))
    return strings
