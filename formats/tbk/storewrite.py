"""Write a ToolBook object store, and patch text inside one.

The opener does not read a stream of page markers. It reads the directory
at header +0x10E, then a segment whose first word is its own id. Field
text is a trailer handle, not a ``Text`` property. This writer emits that
container: one background, one field per page, no pictures and no scripts.
A script ToolBook runs is TB80CMP bytecode. Copying source text in would
not run.

``splice_text`` is the other half. It replaces one string with another of
the same length inside a book the program already opens. The directory,
the segments and the scripts stay as they were.
"""

from __future__ import annotations

import struct
from pathlib import Path

STUB = 0xC00
HEADER = 0x120
BOOK = 0x1100
BACKGROUND = 0x2100
ARRAY = 0x3100


def write_store(path: str | Path, book: dict) -> Path:
    """Write ``path``. ``book["pages"]`` supplies the id and the field text."""
    path = Path(path)
    pages = [_page(item, index) for index, item in enumerate(book.get("pages") or [{"id": "P0", "text": ""}])]
    if not pages:
        pages = [_page({"id": "P0", "text": ""}, 0)]
    segments = _segments(pages, _colour(book.get("fill") or "#0000bf"))
    raw = _assemble(segments)
    path.write_bytes(raw)
    return path


def splice_text(data: bytes, old: str, new: str) -> bytes:
    """Replace ``old`` with ``new`` in a book that already opens.

    The two strings must be the same length. A shorter string would have
    to move the trailer, and the length word is not the only thing that
    would change.
    """
    before = old.encode("latin-1")
    after = new.encode("latin-1")
    if len(before) != len(after):
        raise ValueError("the new text has to be the same length as the text it replaces")
    at = data.find(before)
    if at < 0:
        raise ValueError("that text is not in the file")
    if data.find(before, at + 1) >= 0:
        raise ValueError("that text occurs more than once")
    out = bytearray(data)
    out[at:at + len(after)] = after
    return bytes(out)


def _page(item: dict, index: int) -> dict:
    text = item.get("text") or ""
    if isinstance(text, list):
        text = "\n".join(str(part) for part in text)
    return {
        "id": str(item.get("id") or f"P{index}"),
        "text": str(text),
        "sid": _page_id(index),
    }


def _page_id(index: int) -> int:
    slot = index + 4
    return ((slot % 16) << 12) | ((1 + slot // 16) << 8)


def _colour(value: str) -> bytes:
    raw = value.removeprefix("#")
    if len(raw) != 6:
        return bytes((0, 0, 0xBF))
    return bytes(int(raw[i:i + 2], 16) for i in (0, 2, 4))


def _segments(pages: list[dict], colour: bytes) -> list[dict]:
    array = _array(pages)
    book = _book(len(pages))
    background = _background(colour)
    out = [book, background, array]
    for page in pages:
        body, trailer = _page_segment(page)
        out.append({"id": page["sid"], "body": body, "flags": 0x4000, "trailer": trailer})
    return out


def _book(count: int) -> dict:
    near = 0x50
    body = _blank(BOOK, near)
    _object(body, 0x14, 1, 0x40)
    struct.pack_into("<H", body, _at(0x24), 0x40)
    struct.pack_into("<HH", body, _at(0x14 + 0x1E), 6624, 9360)
    struct.pack_into("<HH", body, _at(0x40), 0x0020, 1)
    struct.pack_into("<HHI", body, _at(0x44), 0x0100, count, ARRAY << 16 | 0x14)
    return {"id": BOOK, "body": body, "flags": 0, "trailer": b""}


def _background(colour: bytes) -> dict:
    near = 0x80
    body = _blank(BACKGROUND, near)
    _object(body, 0x14, 4, 0x78)
    _name(body, 0x14, "Page")
    body[_at(0x14 + 0x4B)] = 0xFE
    body[_at(0x14 + 0x5B):_at(0x14 + 0x5E)] = colour
    return {"id": BACKGROUND, "body": body, "flags": 0, "trailer": b""}


def _array(pages: list[dict]) -> dict:
    rows = len(pages)
    near = 0x14 + 5 + 13 * rows + 4
    body = _blank(ARRAY, near)
    struct.pack_into("<H", body, _at(0x14 + 3), rows)
    for index, page in enumerate(pages):
        struct.pack_into(
            "<IIIB",
            body,
            _at(0x14 + 5 + 13 * index),
            BACKGROUND << 16 | 0x14,
            index + 1,
            page["sid"] << 16 | 0x14,
            0,
        )
    return {"id": ARRAY, "body": body, "flags": 0, "trailer": b""}


def _page_segment(page: dict) -> tuple[bytes, bytes]:
    text_at = 0xB0
    near = text_at + 4
    body = _blank(page["sid"], near)
    _object(body, 0x14, 5, 0x60)
    _name(body, 0x14, page["id"])
    struct.pack_into("<I", body, _at(0x14 + 0x47), BACKGROUND << 16 | 0x14)
    _object(body, 0x64, 0x0A, 0xA1)
    struct.pack_into("<H", body, _at(0x64 + 4), 0x14)
    body[_at(0x64 + 0x0A)] = 1
    struct.pack_into("<hhhh", body, _at(0x64 + 0x0F), 600, 900, 8400, 2400)
    body[_at(0x64 + 0x1F)] = 1
    struct.pack_into("<H", body, _at(0x64 + 0x24), text_at)
    struct.pack_into("<HHHH", body, _at(0x64 + 0x28), 360, 360, 310, 720)
    body[_at(0x64 + 0x36)] = 1
    struct.pack_into("<HH", body, _at(text_at), 0xFFFF, 1)
    return body, _trailer(page["text"].encode("latin-1", "replace"))


def _trailer(text: bytes) -> bytes:
    item = struct.pack("<HH", len(text), len(text)) + text
    end = 6 + len(item)
    blob = struct.pack("<HHH", end, 0, 0) + item
    header = struct.pack("<HHIHH", 0, 0, len(blob), 0, 0)
    slots = struct.pack("<HHHH", 0, 0, 0, 0) + struct.pack("<HHHH", 1, 6, 0, 0)
    return struct.pack("<HH", 1, 1) + header + blob + struct.pack("<HHH", 1, 0, 2) + slots


def _blank(segid: int, near: int) -> bytearray:
    size = near - 6
    body = bytearray(size)
    struct.pack_into("<HH", body, 0, segid, size - 2)
    return body


def _object(body: bytearray, rec: int, kind: int, end: int) -> None:
    struct.pack_into("<HH", body, _at(rec - 4), end, kind)


def _name(body: bytearray, rec: int, name: str) -> None:
    raw = name.encode("latin-1", "replace")[:31] + b"\x00"
    start = _at(rec + 6)
    body[start:start + len(raw)] = raw


def _at(near: int) -> int:
    return near - 6


def _assemble(segments: list[dict]) -> bytes:
    stub = bytearray(STUB)
    stub[0:2] = b"MZ"
    struct.pack_into("<II", stub, 0x9E8, STUB, 0x22222222)
    header = bytearray(HEADER)
    header[0:8] = bytes.fromhex("034a424f01000008")
    struct.pack_into("<I", header, 0x18, BOOK << 16 | 0x14)
    # The property tree that sits in a real 8.x header, through the last
    # record that is not a file offset. Offsets past this point are zero
    # so nothing points into the lesson this header was copied from.
    header[0x20:0x80] = bytes.fromhex(
        "14000010000000001400007000000000"
        "00000000000000000000000000000000"
        "14000090140000b00000000000000000"
        "00000000000000140000d00000000000"
        "00000000000000000000000000000000"
        "140000f0000000000000000000000000"
    )
    file = bytearray(stub) + header
    for seg in segments:
        seg["filepos"] = len(file)
        file += seg["body"]
        file += seg["trailer"]
    root_at, directory = _directory(len(file), segments)
    struct.pack_into("<I", file, STUB + 0x10E, root_at)
    file += directory
    return bytes(file)


def _directory(base: int, segments: list[dict]) -> tuple[int, bytes]:
    """Three levels of 16 children, then the leaf that names each segment.

    The walk uses nibble 0, then 1, then 2. The leaf slot is nibble 3.
    """
    leaves: dict[tuple[int, int, int], dict[int, dict]] = {}
    for seg in segments:
        ident = seg["id"]
        n0 = ident & 0xF
        n1 = (ident >> 4) & 0xF
        n2 = (ident >> 8) & 0xF
        n3 = (ident >> 12) & 0xF
        leaves.setdefault((n0, n1, n2), {})[n3] = seg
    l2_keys = sorted({key[:2] for key in leaves})
    l1_keys = sorted({(key[0],) for key in l2_keys})
    blobs: list[tuple[str, tuple, bytearray]] = [("l0", (), bytearray(16 * 0x14))]
    blobs += [("l1", key, bytearray(16 * 0x14)) for key in l1_keys]
    blobs += [("l2", key, bytearray(16 * 0x14)) for key in l2_keys]
    for key, slots in leaves.items():
        leaf = bytearray(16 * 0x18)
        for n3, seg in slots.items():
            at = n3 * 0x18
            struct.pack_into("<I", leaf, at, seg["filepos"])
            struct.pack_into("<H", leaf, at + 8, seg["flags"])
            struct.pack_into("<H", leaf, at + 0xC, len(seg["body"]))
        blobs.append(("leaf", key, leaf))
    where = {}
    at = base
    for kind, key, blob in blobs:
        where[(kind, key)] = at
        at += len(blob)
    l0 = next(item[2] for item in blobs if item[0] == "l0")
    for (n0,) in l1_keys:
        struct.pack_into("<I", l0, n0 * 0x14, where[("l1", (n0,))])
    for (n0, n1) in l2_keys:
        blob = next(item[2] for item in blobs if item[0] == "l2" and item[1] == (n0, n1))
        parent = next(item[2] for item in blobs if item[0] == "l1" and item[1] == (n0,))
        struct.pack_into("<I", parent, n1 * 0x14, where[("l2", (n0, n1))])
        for (a, b, n2), _slots in leaves.items():
            if (a, b) == (n0, n1):
                struct.pack_into("<I", blob, n2 * 0x14, where[("leaf", (a, b, n2))])
    return where[("l0", ())], b"".join(blob for _kind, _key, blob in blobs)
