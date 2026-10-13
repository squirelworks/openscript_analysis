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
        from ...core.keywords import KEYWORDS
        keywords = KEYWORDS
    table = {w: i for i, w in enumerate(keywords) if w}
    words = sorted(table, key=len, reverse=True)
    out = bytearray()
    i = 0
    n = len(source)
    while i < n:
        # longest keyword match
        matched = False
        for w in words:
            if source.startswith(w, i):
                idx = table[w]
                if idx < 16:
                    out.append(0x80 | idx)
                else:
                    out.append(0x90 | (idx >> 8))
                    out.append(idx & 0xFF)
                i += len(w)
                matched = True
                break
        if matched:
            continue
        ch = source[i]
        if ch == "\n":
            out.append(0xE0)
        elif ch == " ":
            # count spaces
            j = i
            while j < n and source[j] == " ":
                j += 1
            count = j - i
            if count <= 15:
                out.append(0xE0 + count)
            else:
                out.append(0xF0 + min(count - 2, 14))
            i = j
            continue
        else:
            out.append(ord(ch) & 0x7F)
        i += 1
    return bytes(out)


def constant_pools(data: bytes) -> list[str]:
    """Placeholder for constant pool extraction."""
    return []
