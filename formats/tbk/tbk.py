"""Minimal ToolBook II 8.1 course-book loader.

Self-contained so Foolbook does not depend on an external runtime package.
A lesson is a Click2learn shell: 0xC00-byte stub, then the book at
ZZZTBKBOOKLOC (file 0xC00, magic 0x22222222). Pages are the 80 65 records.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

MARK = bytes.fromhex("80650005000202")
BOOK_MAGIC = 0x22222222
STUB = 0xC00


def cstr(buf: bytes, off: int, n: int) -> str:
    end = buf.find(b"\x00", off, off + n)
    if end < 0:
        end = off + n
    return buf[off:end].decode("latin-1", "replace")


@dataclass
class Page:
    id: str
    offset: int
    raw: bytes = b""


@dataclass
class Book:
    path: str
    pages: list[Page] = field(default_factory=list)


def load(path: str | Path) -> Book:
    data = Path(path).read_bytes()
    if len(data) < STUB + 8 or int.from_bytes(data[STUB:STUB+4], "little") != BOOK_MAGIC:
        raise ValueError("not a ToolBook book")
    book = Book(path=str(path))
    i = 0
    while True:
        i = data.find(MARK, i)
        if i < 0:
            break
        name = cstr(data, i + 7, 32)
        if name.startswith("P"):
            book.pages.append(Page(id=name, offset=i))
        i += 1
    return book
