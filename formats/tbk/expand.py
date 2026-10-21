#!/usr/bin/env python3
"""OpenScript bytecode decompressor.

Implements FUN_1040_0970 from TB80CMP.DLL (COMPILEREXPANDTEXT).

The keyword resource is formats/tbk/compat/res_77.bin (NE resource 0x77).
It is not in the tree. load_keywords() reads it when it is present and
otherwise uses the id-indexed list in core/keywords.py.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path


def load_keywords(bin_path: Path | None = None) -> list[str]:
    """Load resource 0x77.

    Byte 0 is the count (994). Byte 2 starts count pairs of {id, offset}.
    The id-indexed offset table starts at byte 2 plus count times 4.
    Each entry there is a word offset of a NUL-terminated string.
    """
    if bin_path is None:
        bin_path = Path(__file__).parent / "compat" / "res_77.bin"
    if not bin_path.exists():
        from ...core.keywords import KEYWORDS
        return list(KEYWORDS)
    data = bin_path.read_bytes()
    if len(data) < 4:
        from ...core.keywords import KEYWORDS
        return list(KEYWORDS)
    count = struct.unpack_from("<H", data, 0)[0]
    table = 2 + count * 4
    if count > 2000 or table + count * 2 > len(data):
        from ...core.keywords import KEYWORDS
        return list(KEYWORDS)
    words = []
    for i in range(count):
        off = struct.unpack_from("<H", data, table + i * 2)[0]
        if off >= len(data):
            words.append("")
            continue
        end = data.find(b"\x00", off)
        if end < 0:
            words.append("")
            continue
        words.append(data[off:end].decode("latin-1", "replace"))
    return words


def decompress(bytecode: bytes, keywords: list[str], max_out: int = 100_000, origin: int = 0, span: int | None = None) -> str:
    """Expand one stream. origin is an index into bytecode, which is the book.

    A back-reference is an index into that same book. It often lands before
    origin. Slicing the book first turns those copies into "?".

    Follows FUN_1040_0970:
      00-7F   literal, and 00 ends the stream
      80-BF   keyword (bit 4 = two-byte index, bit 5 clear = trailing space)
      C0-DF   back-reference into the input stream
      E0-EF   CRLF plus 0-15 spaces
      F0-FE   2-16 spaces
      FF      repeat the next byte (count + 1) times
    """
    blob = bytecode
    out = bytearray()
    pos = origin
    end = len(blob) if span is None else min(len(blob), origin + span)
    if pos < end and blob[pos] == 0xF8:
        pos += 1

    while pos < end and len(out) < max_out:
        b = blob[pos]
        pos += 1

        if b < 0x80:
            if b == 0:
                break
            out.append(b)
            continue

        if (b & 0xF0) == 0xF0:
            if b == 0xFF:
                if pos + 1 >= end:
                    break
                ch = blob[pos]
                count = blob[pos + 1] + 1
                pos += 2
                _emit(out, [ch] * count, max_out)
            else:
                _emit(out, [0x20] * ((b & 0xF) + 2), max_out)
            continue

        if (b & 0xF0) == 0xE0:
            _emit(out, [0x0D, 0x0A] + [0x20] * (b & 0xF), max_out)
            continue

        if (b & 0x40) == 0:
            index = b & 0xF
            if b & 0x10:
                if pos >= end:
                    break
                index = (index << 8) | blob[pos]
                pos += 1
            chunk = bytearray()
            if index < len(keywords):
                chunk.extend(keywords[index].encode("latin-1"))
            if (b & 0x20) == 0:
                chunk.append(0x20)
            _emit(out, chunk, max_out)
            continue

        if (b & 0x10) == 0:
            if pos >= end:
                break
            length = (b & 0xF) + 3
            src = pos + (-4 - blob[pos])
            pos += 1
        else:
            if pos + 1 >= end:
                break
            length = (b & 0xF) + 4
            off = struct.unpack_from("<H", blob, pos)[0]
            src = pos + (-1 - off)
            pos += 2

        copied = bytearray()
        for i in range(length):
            at = src + i
            if 0 <= at < len(blob):
                copied.append(blob[at])
            else:
                copied.append(ord("?"))
        _emit(out, copied, max_out)

    return out.decode("latin-1", errors="replace")


def _emit(out: bytearray, data, max_out: int) -> None:
    room = max_out - len(out)
    if room <= 0:
        return
    if len(data) > room:
        out.extend(data[:room])
        return
    out.extend(data)


def find_streams(data: bytes, keywords: list[str] | None = None) -> list[tuple[int, int]]:
    """Starts of OpenScript handlers in a book, as (offset, end).

    A lesson stores the words ``to handle`` in the clear and compresses the
    body. A system book compresses the words as well. ``end`` is the next
    handler, or the end of this stream. A back-reference still reads the
    whole book.
    """
    if keywords is None:
        keywords = load_keywords()
    starts = _handler_starts(data, keywords)
    out = []
    for i, off in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else len(data)
        out.append((off, nxt))
    return out


def read_handlers(data: bytes, keywords: list[str] | None = None) -> list[dict]:
    """Each handler the scan found: offset, end, kind, name, source."""
    if keywords is None:
        keywords = load_keywords()
    found = []
    for off, end in find_streams(data, keywords):
        span = max(1, min(end - off, 8000))
        text = decompress(data, keywords, max_out=100_000, origin=off, span=span)
        source = _one_handler(text)
        kind, name = _header(source)
        if not name:
            continue
        found.append({
            "offset": off,
            "end": end,
            "kind": kind,
            "name": name,
            "source": source,
        })
    return found


_HEADER = re.compile(
    r"(?is)^[ \t]*to[ \t]+(handle|get|set)[ \t]+([A-Za-z_][A-Za-z0-9_]*)"
)
_NEXT = re.compile(
    r"(?im)^[ \t]*to[ \t]+(?:handle|get|set)[ \t]+[A-Za-z_]"
)


# Words the opcode stream emits when a window is not a handler. Real
# handler names such as enterPage are keywords too, so this list stays short.
_GLUE = {
    "to", "handle", "get", "set", "end", "if", "of", "put", "send",
    "is", "into", "text", "this", "and", "or", "when", "from", "step",
}


def _handler_starts(data: bytes, keywords: list[str]) -> list[int]:
    starts = []
    pos = 0
    while True:
        pos = data.find(b"\x80", pos)
        if pos < 0:
            break
        if _opens_handler(data, keywords, pos):
            starts.append(pos)
        pos += 1
    for match in re.finditer(
        rb"(?i)to[ \t]+(?:handle|get|set)[ \t]+([A-Za-z_][A-Za-z0-9_]*)",
        data,
    ):
        name = match.group(1).decode("latin-1")
        if name.lower() in _GLUE:
            continue
        at = match.start()
        if any(off <= at < nxt for off, nxt in _pairs(starts, len(data))):
            continue
        starts.append(at)
    starts = sorted(set(starts))
    kept = []
    for off in starts:
        if kept and off < kept[-1] + 4:
            continue
        kept.append(off)
    return kept


def _pairs(starts: list[int], end: int):
    for i, off in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else end
        yield off, nxt


def _opens_handler(data: bytes, keywords: list[str], origin: int) -> bool:
    text = decompress(data, keywords, max_out=120, origin=origin, span=160)
    return _header_line(text) is not None


def _header_line(text: str):
    """The first line, when it is a handler header and the name is not glue."""
    line = text.lstrip("\r\n").split("\r", 1)[0].split("\n", 1)[0]
    match = re.match(
        r"(?i)^to[ \t]+(handle|get|set)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
        line,
    )
    if not match or match.group(2).lower() in _GLUE:
        return None
    # A real header is its own line. Opcode noise has no line break after it.
    rest = text.lstrip("\r\n")
    if not re.match(r"(?s)^[^\r\n]*[\r\n]", rest):
        return None
    return match.group(1).lower(), match.group(2)


def _one_handler(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    match = _NEXT.search(text, 1)
    if match:
        text = text[:match.start()]
    return text.strip() + "\n"


def _header(source: str) -> tuple[str, str]:
    match = _HEADER.match(source)
    if not match:
        return "", ""
    return match.group(1).lower(), match.group(2)

