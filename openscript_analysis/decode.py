"""Decode OpenScript bytecode to source.

decode() is expand(). A back-reference reads the whole book, not the slice
the caller happened to pass. compile() writes bytecode without back-references.
"""

from __future__ import annotations

from .expand import decompress, load_keywords


def decode(bytecode, keywords, origin=0, span=None, max_out=100_000):
    """Expand one stream. origin is an index into bytecode, which is the book."""
    return decompress(bytecode, keywords, max_out=max_out, origin=origin, span=span)


def compile(source: str, keywords: list[str] | None = None) -> bytes:
    """Compile OpenScript source to the bytecode FUN_1040_0970 expands.

    Inverse of decode(). Known opcodes only:

      00-7F   literal
      80-BF   keyword (bit 4 = two-byte index, bit 5 clear = trailing space)
      E0-EF   CRLF plus 0-15 spaces
      F0-FE   2-16 spaces
      FF      repeat

    Back-references (C0-DF) are a compressor. This cut does not emit them.
    The keyword table is the same one the decoder uses.
    """
    if keywords is None:
        from .keywords import KEYWORDS
        keywords = KEYWORDS
    table = {w: i for i, w in enumerate(keywords) if w}
    # longest first so "buttonClick" wins over "button"
    words = sorted(table, key=len, reverse=True)
    out = bytearray()
    i = 0
    n = len(source)
    while i < n:
        # newline
        if source[i] == "\n" or source.startswith("\r\n", i):
            if source.startswith("\r\n", i):
                i += 2
            else:
                i += 1
            spaces = 0
            while i < n and source[i] == " " and spaces < 15:
                spaces += 1
                i += 1
            out.append(0xE0 | spaces)
            continue
        # space run
        if source[i] == " ":
            j = i
            while j < n and source[j] == " ":
                j += 1
            run = j - i
            while run >= 2:
                take = min(run, 16)
                out.append(0xF0 | (take - 2))
                run -= take
            if run:
                out.append(0x20)
            i = j
            continue
        # keyword
        matched = None
        for w in words:
            if source.startswith(w, i):
                after = i + len(w)
                # do not eat a keyword that is a prefix of an identifier
                if after < n and (source[after].isalnum() or source[after] == "_"):
                    continue
                matched = w
                break
        if matched is not None:
            idx = table[matched]
            trailing = (i + len(matched) < n and source[i + len(matched)] == " ")
            if idx < 16:
                b = 0x80 | idx
                if not trailing:
                    b |= 0x20
                out.append(b)
            else:
                b = 0x80 | 0x10 | ((idx >> 8) & 0xF)
                if not trailing:
                    b |= 0x20
                out.append(b)
                out.append(idx & 0xFF)
            i += len(matched)
            if trailing:
                i += 1
            continue
        # literal, with a repeat if the same byte runs
        ch = source[i].encode("latin-1", "replace")[0]
        run = 1
        while i + run < n and source[i + run].encode("latin-1", "replace")[0] == ch and run < 256:
            run += 1
        if run >= 4:
            out.append(0xFF)
            out.append(ch)
            out.append(run - 1)
            i += run
        else:
            out.append(ch)
            i += 1
    return bytes(out)


# Compiled procedures end with opcode 0x27. The constant pool is the
# bytes immediately after that: 1d 66, a uint16, then NUL-terminated
# strings. A two-byte tag sits in front of a linked name. Either byte
# may be the high one: c3 b2 before ASYM_CBTVersion, f0 5d before
# ASYM_AnimationState, 6d f3 before ASYM_AnimationPosition. A bare NUL
# ends the pool. Both objects use this.
_POOL = b"\x27\x1d\x66"


def constant_pool(buf: bytes, at: int) -> list[str]:
    """Read the string pool that starts at a compiled END (27 1d 66)."""
    if buf[at:at + 3] != _POOL:
        return []
    i = at + 5
    end = len(buf)
    out = []
    while i < end:
        if buf[i] == 0:
            break
        if buf[i] >= 0x80 or (i + 1 < end and buf[i + 1] >= 0x80):
            i += 2
            continue
        j = buf.find(b"\x00", i, end)
        if j < 0:
            break
        raw = buf[i:j]
        if any(c < 0x20 for c in raw):
            break
        out.append(raw.decode("latin-1"))
        i = j + 1
    return out


def constant_pools(buf: bytes) -> list[list[str]]:
    """Every constant pool in a page or object blob."""
    found = []
    start = 0
    while True:
        at = buf.find(_POOL, start)
        if at < 0:
            break
        strings = constant_pool(buf, at)
        if strings:
            found.append(strings)
        start = at + 3
    return found

