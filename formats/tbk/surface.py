"""Objects a TBK page already has, read before the page is shown.

ToolBook opens the file from the start, keeps the later copy of a
repeated object, and only then paints. Bounds are four twips at a fixed
spot in the widget record. The name and the field text are properties
keyed from that same record. A button's script sits between that
widget and the next one.
"""

from __future__ import annotations

import re
import struct

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_#]*$")
_NAV = {"next", "back", "previous", "ok", "help", "skip", "menu"}


def read_surface(blob: bytes, decode=None) -> dict:
    """One page blob to the objects that remain after the record is replayed.

    ``decode`` turns a ``TO HANDLE`` slice into source. Without it the
    script is left empty. Bounds stay in twips: left, top, right, bottom.
    """
    if not blob:
        return {"objects": [], "answer": ""}
    widgets = _widgets(blob)
    _attach_text(blob, widgets)
    for obj in widgets:
        obj["script"] = _script(blob, obj, widgets, decode)
        obj["kind"] = _kind(obj)
    widgets = _replay(widgets)
    for obj in widgets:
        _fill_nav(obj)
    answer = _user_value(blob, "Answer")
    objects = []
    for obj in widgets:
        objects.append({
            "id": obj["id"],
            "kind": obj["kind"],
            "name": obj["name"],
            "text": obj["text"],
            "bounds": list(obj["bounds"]),
            "fill": obj["fill"],
            "outline": obj["outline"],
            "script": obj["script"],
        })
    return {"objects": objects, "answer": answer}


def _widgets(blob: bytes) -> list[dict]:
    found = []
    spans = []
    i = 0
    while True:
        i = blob.find(b"\x14\x00", i)
        if i < 4:
            if i < 0:
                break
            i += 1
            continue
        if i + 27 > len(blob):
            break
        idn = int.from_bytes(blob[i - 4:i], "little")
        if not 0 < idn < 100_000:
            i += 1
            continue
        left, top, right, bottom = struct.unpack_from("<hhhh", blob, i + 11)
        width, height = right - left, bottom - top
        if not (
            -4000 <= left <= 30000 and -4000 <= top <= 30000
            and 0 < width < 20000 and 0 < height < 15000
        ):
            i += 1
            continue
        start = i - 4
        span = (start, i + 19)
        if any(not (span[1] <= a or span[0] >= b) for a, b in spans):
            i += 1
            continue
        spans.append(span)
        key = int.from_bytes(blob[i + 2:i + 4], "little")
        stroke = blob[i + 19:i + 23]
        fill = blob[i + 23:i + 27]
        found.append({
            "id": idn,
            "key": key,
            "at": start,
            "bounds": (left, top, right, bottom),
            "name": _name(blob, key),
            "text": "",
            "fill": _color(fill),
            "outline": _color(stroke),
            "script": "",
        })
        i += 1
    return found


def _replay(widgets: list[dict]) -> list[dict]:
    """A later copy of an object replaces the earlier one.

    An edit often repeats the bounds and leaves the script on the
    first copy. The script and the text stay when the later copy
    does not carry its own. A 1,275 by 300 twip box at 0,30 is a
    scan hit, not the field, so it must not replace the real box.
    """
    order = []
    latest = {}
    for obj in widgets:
        if obj["id"] not in latest:
            order.append(obj["id"])
            latest[obj["id"]] = obj
            continue
        old = latest[obj["id"]]
        if _stub(obj) and not _stub(old):
            if not old["script"]:
                old["script"] = obj["script"]
            if not old["text"]:
                old["text"] = obj["text"]
            old["kind"] = _kind(old)
            continue
        if not obj["script"]:
            obj["script"] = old["script"]
        if not obj["text"]:
            obj["text"] = old["text"]
        if not obj["name"]:
            obj["name"] = old["name"]
        obj["kind"] = _kind(obj)
        latest[obj["id"]] = obj
    kept = [latest[key] for key in order]
    named = {}
    for obj in kept:
        if _stub(obj):
            continue
        named[(obj.get("name") or "").lower()] = True
    return [obj for obj in kept if not (_stub(obj) and named.get((obj.get("name") or "").lower()))]


def _stub(obj: dict) -> bool:
    """The 0,30 box the scan reads on some pages. It is not a field."""
    left, top, right, bottom = obj["bounds"]
    return (left, top, right - left, bottom - top) == (0, 30, 1275, 300)


def _name(blob: bytes, key: int) -> str:
    found = _names(blob, key)
    return found[0] if found else ""


def _names(blob: bytes, key: int) -> list[str]:
    # 0xFFFF is the filler in a bar's header, not a property key.
    if not 0 < key < 0xFF00:
        return []
    needle = key.to_bytes(2, "little") + b"\x00\x00"
    found = []
    start = 0
    while True:
        j = blob.find(needle, start)
        if j < 0 or j + 4 >= len(blob):
            break
        text = _cstr(blob, j + 4)
        start = j + 1
        if not text or not _NAME.match(text) or text.startswith("ASYM"):
            continue
        if text not in found:
            found.append(text)
    return found


def _attach_text(blob: bytes, widgets: list[dict]) -> None:
    if not widgets:
        return
    owners = sorted(widgets, key=lambda obj: obj["key"])
    for key, raw in _texts(blob):
        owner = None
        for obj in owners:
            if obj["key"] <= key and key - obj["key"] <= 2 and obj["name"].lower() not in _NAV:
                owner = obj
        if owner is None or owner["text"]:
            continue
        owner["text"] = _words(raw)


def _texts(blob: bytes):
    i = 0
    limit = len(blob)
    while i + 10 <= limit:
        if blob[i + 4:i + 6] != b"\x00\x00":
            i += 1
            continue
        key = int.from_bytes(blob[i + 2:i + 4], "little")
        size_a = int.from_bytes(blob[i + 6:i + 8], "little")
        length = int.from_bytes(blob[i + 8:i + 10], "little")
        if key == 0 or not (0 < length <= 2000 and length <= size_a <= 8000):
            i += 1
            continue
        if i + 10 + length > limit:
            i += 1
            continue
        raw = blob[i + 10:i + 10 + length]
        if _textual(raw):
            yield key, raw
            i += 10 + length
            continue
        i += 1


def _script(blob: bytes, obj: dict, widgets: list[dict], decode) -> str:
    later = [other["at"] for other in widgets if other["at"] > obj["at"]]
    end = min(later) if later else len(blob)
    window = blob[obj["at"]:end]
    start = window.find(b"TO HANDLE")
    if start < 0:
        return ""
    stop = window.find(b"END", start)
    if stop < 0 or stop - start > 4000:
        return ""
    raw = window[start:stop + 3]
    if decode is None:
        return ""
    try:
        return decode(raw) or ""
    except Exception:
        return ""


def _kind(obj: dict) -> str:
    if obj["script"]:
        return "button"
    if obj["text"]:
        return "text"
    name = obj["name"]
    if name.lower() in _NAV or (len(name) == 1 and name.isalpha()):
        return "button"
    return "rect"


def _fill_nav(obj: dict) -> None:
    """Next and Back move along the settled page list when the record has no script of its own."""
    if obj.get("script") or obj.get("kind") != "button":
        return
    name = (obj.get("name") or "").lower()
    if name == "next":
        obj["script"] = "send next"
    elif name in ("back", "previous"):
        obj["script"] = "send previous"
    if obj["script"]:
        return "button"
    if obj["text"]:
        return "text"
    name = obj["name"]
    if name.lower() in _NAV or (len(name) == 1 and name.isalpha()):
        return "button"
    return "rect"


def _user_value(blob: bytes, name: str) -> str:
    needle = name.encode("latin1") + b"\x00"
    start = 0
    while True:
        j = blob.find(needle, start)
        if j < 2:
            return ""
        if blob[j - 2:j] != b"\x00\x00":
            start = j + 1
            continue
        region_at = max(0, j - 32)
        region = blob[region_at:j]
        k = region.rfind(b"\x09\x00")
        if k < 0:
            start = j + 1
            continue
        abs_k = region_at + k
        if abs_k + 4 > len(blob):
            return ""
        length = int.from_bytes(blob[abs_k + 2:abs_k + 4], "little")
        if 0 < length < 64 and abs_k + 4 + length <= j:
            raw = blob[abs_k + 4:abs_k + 4 + length]
            if raw and all(32 <= c < 127 for c in raw):
                return raw.decode("ascii")
        start = j + 1


def _words(raw: bytes) -> str:
    text = raw.decode("latin1", "replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        # The face tag is not in the 8.1 field. A Wingdings bullet remains as "w ".
        if line.startswith("w "):
            line = "• " + line[2:]
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _cstr(blob: bytes, off: int) -> str:
    out = []
    for c in blob[off:off + 64]:
        if c == 0:
            break
        if not 32 <= c < 127:
            return ""
        out.append(chr(c))
    return "".join(out)


def _textual(raw: bytes) -> bool:
    if not raw:
        return False
    for c in raw:
        if c in (9, 10, 13):
            continue
        if not 32 <= c < 127:
            return False
    return any(48 <= c <= 57 or 65 <= c <= 90 or 97 <= c <= 122 for c in raw)


def _color(dword: bytes) -> str:
    if len(dword) < 3 or dword[:4] == b"\x00\x00\x00\x00":
        return ""
    b, g, r = dword[0], dword[1], dword[2]
    return f"#{r:02x}{g:02x}{b:02x}"
