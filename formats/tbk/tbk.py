"""Minimal ToolBook II 8.1 course-book loader.

Self-contained so Foolbook does not depend on an external runtime package.
A lesson is a Click2learn shell: a PE stub, then the book. The stub's
RCDATA resource ZZZTBKBOOKLOC holds two longs, the book's file offset and
the magic 0x22222222. The book starts there with 03 4A 42 4F (JBO). The
offset is 0xC00 in most books and 0xE00 in others, so it is read, not
assumed. Pages are the 80 65 records.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

MARK = bytes.fromhex("80650005000202")
BOOK_MAGIC = 0x22222222
STUB = 0xC00
STORE = b"\x03JBO"
RT_RCDATA = 10


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
    offset: int = STUB


def _resource(data: bytes, type_id: int, name: str) -> bytes | None:
    """The bytes of a named resource in a PE file, or None."""
    try:
        if data[:2] != b"MZ":
            return None
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            return None
        sections, optional = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        dirs = opt + (96 if struct.unpack_from("<H", data, opt)[0] == 0x10B else 112)
        rva = struct.unpack_from("<I", data, dirs + 2 * 8)[0]
        table = []
        for i in range(sections):
            _n, vsize, va, rsize, raw = struct.unpack_from("<8sIIII", data, opt + optional + 40 * i)
            table.append((va, max(vsize, rsize), raw))

        def at(addr: int) -> int | None:
            for va, size, raw in table:
                if va <= addr < va + size:
                    return addr - va + raw
            return None

        base = at(rva)
        if base is None:
            return None

        def entries(off: int):
            named, ids = struct.unpack_from("<HH", data, base + off + 12)
            for k in range(named + ids):
                yield struct.unpack_from("<II", data, base + off + 16 + 8 * k)

        def label(key: int):
            if not key & 0x80000000:
                return key
            o = base + (key & 0x7FFFFFFF)
            n = struct.unpack_from("<H", data, o)[0]
            return data[o + 2:o + 2 + 2 * n].decode("utf-16-le")

        for key, ptr in entries(0):
            if label(key) != type_id or not ptr & 0x80000000:
                continue
            for key2, ptr2 in entries(ptr & 0x7FFFFFFF):
                if label(key2) != name or not ptr2 & 0x80000000:
                    continue
                for _lang, leaf in entries(ptr2 & 0x7FFFFFFF):
                    if leaf & 0x80000000:
                        continue
                    drva, size = struct.unpack_from("<II", data, base + leaf)
                    off = at(drva)
                    return None if off is None else data[off:off + size]
    except struct.error:
        return None
    return None


def book_offset(data: bytes) -> int | None:
    """Where the book starts, or None when this is not a ToolBook book.

    ZZZTBKBOOKLOC names it. A file without that resource is still a book
    when the old marker 0x22222222 sits at 0xC00.
    """
    loc = _resource(data, RT_RCDATA, "ZZZTBKBOOKLOC")
    if loc is not None and len(loc) >= 8:
        offset, magic = struct.unpack_from("<II", loc, 0)
        if magic == BOOK_MAGIC and data[offset:offset + 4] == STORE:
            return offset
    if len(data) >= STUB + 8 and int.from_bytes(data[STUB:STUB + 4], "little") == BOOK_MAGIC:
        return STUB
    return None


def load(path: str | Path) -> Book:
    data = Path(path).read_bytes()
    offset = book_offset(data)
    if offset is None:
        raise ValueError("not a ToolBook book")
    book = Book(path=str(path), offset=offset)
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
