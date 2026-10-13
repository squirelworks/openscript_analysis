"""Format detection for .tbk/.sbk and .fbk/.fsk envelopes."""

from pathlib import Path

def is_tbk(data: bytes) -> bool:
    return data[0xC00:0xC08] == b"JBO\x03\x01\x00\x00\x08" or b"ZZZTBKBOOKLOC" in data[:0x200]

def is_fbk(data: bytes) -> bool:
    return data[:4] in (b"FBK1", b"FSK1")

def detect(path: str | Path) -> str:
    p = Path(path)
    data = p.read_bytes()[:0x1000]
    if is_fbk(data):
        return "fbk"
    if is_tbk(data):
        return "tbk"
    if data[:1] == b"{" or data[:5] == b"{\"id":
        return "json"
    return "unknown"
