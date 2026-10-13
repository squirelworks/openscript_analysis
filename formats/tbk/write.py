"""Write a best-effort .tbk or .sbk shell.

Foolbook's reader can open it. ToolBook has not been shown to.
The caller passes the OpenScript compiler. This module does not keep one.
"""

from __future__ import annotations

import struct
from pathlib import Path


MARK = bytes.fromhex("80650005000202")
STUB = 0xC00
LOCATOR = 0x9EC
BOOK_OFF = 0xC00
MAGIC = 0x22222222
PAGE_PROPS = bytes.fromhex("140000110000760068002001000100000000")
BOOK_TREE = bytes.fromhex(
    "1400001100000000"
    "1400001000000000"
    "140000700000000000000000000000000000000000000000"
    "14000090140000b000000000"
    "140000d00000000000000000"
    "140000f00000000000000000"
)


def write_tbk(path: str | Path, book: dict, compile_script) -> Path:
    """Write a .tbk shell. A path ending in .sbk is the same shell."""
    path = Path(path)
    stub = bytearray(STUB)
    stub[0:2] = b"MZ"
    struct.pack_into("<II", stub, LOCATOR, BOOK_OFF, MAGIC)
    stream = bytearray(bytes.fromhex("034a424f01000008") + b"\x00" * 16)
    stream += BOOK_TREE
    for n, page in enumerate(book.get("pages") or [], start=1):
        text = "\n".join(page.get("text") or page.get("paragraphs") or [])
        script = compile_script(_script_for(page))
        stream += _record(page.get("id") or f"P{n}", n, text, script)
    path.write_bytes(bytes(stub) + bytes(stream))
    return path


def write_sbk(path: str | Path, book: dict, compile_script) -> Path:
    path = Path(path)
    if path.suffix.lower() != ".sbk":
        path = path.with_suffix(".sbk")
    return write_tbk(path, book, compile_script)


def _script_for(page: dict) -> str:
    if page.get("script"):
        return str(page["script"])
    for handler in page.get("handlers") or []:
        source = handler.get("source") or ""
        if source.strip():
            return source
    lines = ["to handle buttonClick"]
    if page.get("quiz") and page["quiz"].get("next"):
        lines.append(f'  go to page "{page["quiz"]["next"]}"')
    else:
        for item in page.get("items") or []:
            target = item.get("page") or ""
            if target:
                lines.append(f"  -- {item.get('label') or ''}")
                lines.append(f'  go to page "{target}"')
    if len(lines) == 1:
        lines.append("  -- end of course")
    lines.append("end")
    return "\n".join(lines) + "\n"


def _record(name: str, oid: int, text: str, script: bytes) -> bytes:
    name_b = (name.encode("ascii", "replace")[:31] + b"\x00").ljust(32, b"\x00")
    body = text.replace("\n", "\r\n")
    if not body.startswith("\r\n"):
        body = "\r\n" + body
    raw = body.encode("latin-1", "replace")
    field = b"Text\x00\x00" + b"\x00" * 8 + struct.pack("<H", len(raw)) + raw
    return MARK + struct.pack("<I", oid) + name_b + PAGE_PROPS + field + b"\x00" + script + b"\x00"
