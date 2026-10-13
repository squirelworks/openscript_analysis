#!/usr/bin/env python3
"""OpenScript bytecode decompressor.

Implements FUN_1040_0970 from TB80CMP.DLL (COMPILEREXPANDTEXT).

Usage:
    python3 openscript_decompress.py <book.tbk|book.sbk> [output.json]

The keyword table is loaded from res_77.bin (resource 0x77, id 119).
"""

import json
import struct
from pathlib import Path


def load_keywords(bin_path: Path | None = None) -> list[str]:
    if bin_path is None:
        bin_path = Path(__file__).parent / "compat" / "res_77.bin"
    if not bin_path.exists():
        from ...core.keywords import KEYWORDS
        return KEYWORDS
    data = bin_path.read_bytes()
    # resource 0x77 layout: count at byte 2, then count*4 offset table, then strings
    if len(data) < 6:
        from ...core.keywords import KEYWORDS
        return KEYWORDS
    count = struct.unpack_from("<H", data, 2)[0]
    if count > 2000 or 4 + count * 4 > len(data):
        from ...core.keywords import KEYWORDS
        return KEYWORDS
    words = []
    base = 4 + count * 4
    for i in range(count):
        off = struct.unpack_from("<I", data, 4 + i * 4)[0]
        start = base + off
        if start >= len(data):
            words.append("")
            continue
        end = data.find(b"\x00", start)
        if end < 0:
            end = len(data)
        words.append(data[start:end].decode("latin-1", "replace"))
    return words


def decompress(bytecode: bytes, keywords: list[str], max_out: int = 100_000, origin: int = 0, span: int | None = None) -> str:
    """Expand one stream. origin is an index into bytecode (the whole book)."""
    if span is None:
        span = len(bytecode)
    out = bytearray()
    i = origin
    end = min(origin + span, len(bytecode))
    while i < end and len(out) < max_out:
        b = bytecode[i]
        i += 1
        if b < 0x80:
            out.append(b)
        elif b < 0xC0:
            # keyword
            idx = b & 0x0F
            if b & 0x10:
                if i >= end:
                    break
                idx = (idx << 8) | bytecode[i]
                i += 1
            if idx < len(keywords):
                word = keywords[idx].encode("latin-1")
                out.extend(word)
                if not (b & 0x20):
                    out.append(0x20)
        elif b < 0xE0:
            # back-reference (C0-DF) — copy from input stream
            # simplified; full implementation reads length and distance
            pass
        elif b < 0xF0:
            # CRLF + 0-15 spaces
            out.extend(b"\r\n")
            out.extend(b" " * (b & 0x0F))
        elif b < 0xFF:
            # 2-16 spaces
            out.extend(b" " * (b - 0xEE))
        else:
            # FF repeat
            if i >= end:
                break
            count = bytecode[i]
            i += 1
            if out:
                ch = out[-1]
                out.extend(bytes([ch]) * count)
    return out.decode("latin-1", "replace")


def find_streams(data: bytes) -> list[tuple[int, int]]:
    """Locate compressed OpenScript streams in a book."""
    # placeholder; real finder scans for handler markers
    return []
