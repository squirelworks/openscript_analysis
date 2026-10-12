"""Foolbook formats.

.fbk is the Foolbook book format. It is the standard.
.fsk is the Foolbook system-book format. It is the standard.
.json is the working copy.

.fbk and .fsk are not renamed JSON. They are a small binary envelope:

    4 bytes  magic   FBK1 or FSK1
    1 byte   flags   bit 0 set means the payload is zlib-compressed
    rest     payload JSON bytes, compressed or not

The engine reads all three. .tbk and .sbk remain the backward-compatible path.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path


FBK = "fbk"
FSK = "fsk"
FORMAT_VERSION = 1
MAGIC = {FBK: b"FBK1", FSK: b"FSK1"}
FLAG_COMPRESSED = 0x01


def is_book(path: Path) -> bool:
    return path.suffix.lower() in (".fbk", ".json")


def is_system(path: Path) -> bool:
    return path.suffix.lower() == ".fsk"


def kind_of(path: Path) -> str:
    return FSK if path.suffix.lower() == ".fsk" else FBK


def pack(data: dict, kind: str = FBK, compress: bool = True) -> bytes:
    """Build an .fbk or .fsk byte string."""
    magic = MAGIC.get(kind, MAGIC[FBK])
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    flags = 0
    if compress:
        payload = zlib.compress(payload, 9)
        flags |= FLAG_COMPRESSED
    return magic + bytes([flags]) + payload


def unpack(blob: bytes) -> dict:
    """Read an .fbk/.fsk envelope. Plain JSON is accepted so older files still open."""
    if blob[:1] in (b"{", b"["):
        return json.loads(blob.decode("utf-8"))
    if len(blob) < 5 or blob[:4] not in MAGIC.values():
        raise ValueError("not an .fbk or .fsk")
    flags = blob[4]
    payload = blob[5:]
    if flags & FLAG_COMPRESSED:
        payload = zlib.decompress(payload)
    return json.loads(payload.decode("utf-8"))


