"""ToolBook 8 object store.

The book image starts at the ``03 4A 42 4F`` header. A handle is
``segment id << 16 | near offset``. The segment's file bytes begin
six bytes after that offset's zero, so a near pointer ``p`` is at
``file position + p - 6``.

Checked against 9e954d01.tbk: 131 pages, every background reference,
field text through the trailer handle, and class ``0x10`` outlines.
"""

from __future__ import annotations

import struct
from typing import Callable

_SIZES = {
    0x8: 41, 0x9: 43, 0xA: 61, 0xB: 49, 0xC: 41, 0xD: 45, 0xE: 53,
    0xF: 53, 0x10: 53, 0x11: 61, 0x13: 55, 0x14: 55, 0x15: 89, 0x19: 89,
}
_CLASSES = {
    0x8: "rect",
    0x9: "button",
    0xA: "text",
    0xC: "ellipse",
    0xD: "rect",
    0xE: "line",
    0xF: "polygon",
    0x10: "polygon",
    0x13: "line",
}


def read_store(data: bytes, decode: Callable[[bytes], str] | None = None) -> dict:
    """One ``.tbk`` or ``.sbk`` image to pages in stored order.

    Coordinates stay in page units. ``decode`` turns a tokenized
    script into source. Without it the script is left empty.
    """
    store = _Store(data)
    return {"pages": store.pages(decode), "size": store.book_size()}


class _Store:
    def __init__(self, data: bytes):
        self.d = data
        self.H = data.find(b"\x03JBO")
        if self.H < 0:
            raise ValueError("not a ToolBook object store")
        self.segs = self._walk()
        self._trailers: dict[int, dict | None] = {}
        self._dirs: dict[int, dict] = {}

    def w(self, off: int) -> int:
        return struct.unpack_from("<H", self.d, off)[0]

    def sw(self, off: int) -> int:
        return struct.unpack_from("<h", self.d, off)[0]

    def dw(self, off: int) -> int:
        return struct.unpack_from("<I", self.d, off)[0]

    def book_size(self) -> tuple[int, int]:
        rec = self._layer(1)
        if rec is None:
            return (9360, 6624)
        return (self.w(rec + 0x20), self.w(rec + 0x1E))

    def pages(self, decode) -> list[dict]:
        layers = {}
        for seg in self.segs.values():
            rec = seg["base"] + 0x14
            if rec + 0x60 > len(self.d):
                continue
            kind = self.w(rec - 2)
            if kind in (4, 5):
                layers[seg["segid"]] = (kind, seg, rec)
        out = []
        for entry in self._page_entries():
            seg = self.segs.get(entry["page"] >> 16)
            if seg is None:
                continue
            rec = seg["base"] + (entry["page"] & 0xFFFF)
            if self.w(rec - 2) != 5:
                continue
            bg = self._background(self.dw(rec + 0x47), layers)
            width, height = self.book_size()
            if bg and (bg["width"] or bg["height"]):
                width, height = bg["width"] or width, bg["height"] or height
            objects = []
            if bg:
                objects.append({
                    "kind": "rect",
                    "bounds": (0, 0, width, height),
                    "fill": bg["fill"],
                    "outline": "",
                    "name": bg["name"],
                    "text": "",
                    "script": "",
                })
                objects.extend(self._layer_objects(bg["seg"], bg["rec"], decode))
            objects.extend(self._layer_objects(seg, rec, decode))
            out.append({
                "id": self._cstr(rec + 6, 32) or entry["name"],
                "size": (width, height),
                "fill": bg["fill"] if bg else "",
                "objects": objects,
            })
        return out

    def _page_entries(self) -> list[dict]:
        book = self._layer(1)
        if book is None:
            return []
        head = self.segs[self._book_seg()]["base"] + self.w(book + 0x10)
        if head + 4 > len(self.d):
            return []
        children = self.w(head + 2)
        found = []
        for child in range(children):
            flags, count, ref = struct.unpack_from("<HHI", self.d, head + 4 + 8 * child)
            del flags
            seg = self.segs.get(ref >> 16)
            if seg is None:
                continue
            rec = seg["base"] + (ref & 0xFFFF)
            total = self.w(rec + 3)
            for i in range(min(count or total, total)):
                _bg, _idn, pref, _zero = struct.unpack_from("<IIIB", self.d, rec + 5 + 13 * i)
                found.append({"page": pref, "name": ""})
        return found

    def _book_seg(self) -> int:
        handle = self.dw(self.H + 8 + 0x10)
        return handle >> 16

    def _layer(self, kind: int) -> int | None:
        for seg in self.segs.values():
            rec = seg["base"] + 0x14
            if rec + 4 <= len(self.d) and self.w(rec - 2) == kind:
                return rec
        return None

    def _background(self, handle: int, layers: dict) -> dict | None:
        segid = handle >> 16
        hit = layers.get(segid)
        if not hit or hit[0] != 4:
            return None
        _kind, seg, rec = hit
        pattern = self.d[rec + 0x4B]
        fill = "" if pattern == 0xFD else _rgb(self.d, rec + 0x5B)
        return {
            "seg": seg,
            "rec": rec,
            "name": self._cstr(rec + 6, 32),
            "fill": fill,
            "width": self.w(rec + 0x5F),
            "height": self.w(rec + 0x61),
        }

    def _layer_objects(self, seg: dict, rec: int, decode) -> list[dict]:
        parent = rec - seg["base"]
        found = []
        for child in self._children(seg, parent):
            found.extend(self._emit(seg, child, decode))
        return found

    def _children(self, seg: dict, parent: int) -> list[int]:
        base = seg["base"]
        end = seg["filepos"] + seg["size"]
        kids = []
        at = base + 0x18
        while at + 0x20 < end:
            kind = self.w(at - 2)
            size = self.w(at - 4) - (at - base)
            if kind in _SIZES and size == _SIZES[kind] and self.w(at + 4) == parent:
                kids.append(at)
                at += size
                continue
            at += 1
        return kids

    def _emit(self, seg: dict, rec: int, decode) -> list[dict]:
        kind = self.w(rec - 2)
        if kind == 0xB:
            out = []
            count = self.w(rec + 0x24)
            ptr = self.w(rec + 0x2E)
            base = seg["base"]
            for i in range(count if 0 < count < 300 else 0):
                child = base + self.w(base + ptr + 10 * i)
                if seg["base"] < child < seg["filepos"] + seg["size"] and self.w(child + 4) == rec - base:
                    out.extend(self._emit(seg, child, decode))
            return out
        if not self.d[rec + 0x1F] & 1:
            return []
        name = _kind(kind)
        bounds = tuple(self.sw(rec + 0x0F + step) for step in (0, 2, 4, 6))
        obj = {
            "kind": name,
            "bounds": bounds,
            "fill": _rgb(self.d, rec + 0x1B) if name != "text" else "",
            "outline": _rgb(self.d, rec + 0x17),
            "name": self._object_name(seg, rec),
            "text": "",
            "script": self._script(seg, rec, decode, 0x0A, 0x0B),
            "points": [],
            "align": self.d[rec + 0x26],
        }
        if self.d[rec + 0x1F] & 0x40:
            obj["fill"] = "#c0c0c0"
            obj["outline"] = "#000000"
        pattern = self.d[rec + 0x25] if kind in (0x8, 0xC, 0xD, 0xF, 0x10) else 0xFE
        if pattern == 0xFD:
            obj["fill"] = ""
        if kind in (0xF, 0x10):
            obj["points"] = self._mapped(seg, rec, 0x30, 0x32, bounds)
        elif kind == 0x13:
            obj["points"] = self._points(seg, rec, 0x2D, 0x2F)
            obj["kind"] = "line"
        elif kind == 0xE:
            obj["points"] = [
                (self.sw(rec + 0x26), self.sw(rec + 0x28)),
                (self.sw(rec + 0x2A), self.sw(rec + 0x2C)),
            ]
        elif kind == 0xA:
            obj["text"] = self._field_text(seg, rec)
            obj["fill"] = obj["outline"] or "#000000"
        elif kind == 0x9:
            obj["text"] = self._caption(seg, rec)
            obj["bmp"] = self._button_bmp(seg, rec)
        if kind == 0xA and not obj["text"] and not obj["name"]:
            return []
        return [obj]

    def _mapped(self, seg, rec, count_at, ptr_at, bounds) -> list[tuple[int, int]]:
        points = self._points(seg, rec, count_at, ptr_at)
        if len(points) < 3:
            return []
        left, top, right, bottom = bounds
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        width = right - left
        height = bottom - top
        placed = []
        for x, y in points:
            px = left if span_x == 0 else left + (x - min(xs)) * width / span_x
            py = top if span_y == 0 else top + (y - min(ys)) * height / span_y
            placed.append((int(round(px)), int(round(py))))
        return placed

    def _points(self, seg, rec, count_at, ptr_at) -> list[tuple[int, int]]:
        count = self.w(rec + count_at)
        ptr = self.w(rec + ptr_at)
        base = seg["base"]
        end = seg["filepos"] + seg["size"]
        if not 0 < count < 500 or not ptr or base + ptr + 4 * count > end:
            return []
        return [(self.sw(base + ptr + 4 * i), self.sw(base + ptr + 4 * i + 2)) for i in range(count)]

    def _field_text(self, seg, rec) -> str:
        trailer = self._trailer(seg["segid"])
        ptr = self.w(rec + 0x24)
        heap = trailer["heaps"].get(0) if trailer else None
        if not heap or ptr + 4 > len(heap):
            return ""
        _runs, text = struct.unpack_from("<HH", heap, ptr)
        return _htext(trailer, text)

    def _caption(self, seg, rec) -> str:
        ptr = self.w(rec + 0x22)
        if not ptr:
            return ""
        base = seg["base"]
        if base + ptr < seg["filepos"] + seg["size"]:
            raw = self._cstr(base + ptr, 80)
            if raw:
                return raw
        trailer = self._trailer(seg["segid"])
        return _hstr(trailer, ptr) or ""

    def _button_bmp(self, seg, rec) -> bytes | None:
        ptr = self.w(rec + 0x28)
        if not ptr:
            return None
        block = seg["base"] + ptr
        if block + 0x16 > seg["filepos"] + seg["size"]:
            return None
        stored = self.w(block + 0x15)
        if stored <= 1:
            return None
        return self._bitmap(stored - 1)

    def _bitmap(self, ident: int) -> bytes | None:
        directory = self._directory(1)
        entry = directory.get(ident)
        if not entry:
            return None
        body = entry["body"]
        if self.d[body + 8] & 1:
            return None
        data_at = entry["base"] + self.w(body + 9)
        if self.d[data_at + 8:data_at + 10] != b"BM":
            return None
        size = self.dw(data_at + 10)
        blob = self.d[data_at + 8:data_at + 8 + size]
        return blob if blob[:2] == b"BM" else None

    def _directory(self, kind: int) -> dict:
        if kind in self._dirs:
            return self._dirs[kind]
        handle = self.dw(self.H + 8 + (kind + 5) * 4)
        found = {}
        seg, body = self._ref(handle)
        if seg is not None:
            count = self.w(body + 2)
            table = self.w(body + 0x0E)
            base = seg["base"]
            for i in range(count):
                _word0, off, segid, ident = struct.unpack_from("<HHHH", self.d, base + table + i * 8)
                owner, obj = self._ref((segid << 16) | off)
                if owner is not None:
                    found[ident] = {"body": obj, "base": owner["base"]}
        self._dirs[kind] = found
        return found

    def _script(self, seg, rec, decode, mode_at, word_at) -> str:
        if decode is None or (self.d[rec + mode_at] & 3) != 0:
            return ""
        ptr = self.w(rec + word_at)
        trailer = self._trailer(seg["segid"])
        heap = trailer["heaps"].get(0) if trailer else None
        if not heap or ptr + 4 > len(heap):
            return ""
        first = struct.unpack_from("<H", heap, ptr)[0]
        second_at = ptr + 2 + first
        if second_at + 2 > len(heap):
            return ""
        length = struct.unpack_from("<H", heap, second_at)[0]
        source = heap[second_at + 2:second_at + 2 + length]
        try:
            return decode(source)
        except Exception:
            return ""

    def _object_name(self, seg, rec) -> str:
        trailer = self._trailer(seg["segid"])
        return _hstr(trailer, self.w(rec + 6)) or ""

    def _ref(self, handle: int):
        seg = self.segs.get(handle >> 16)
        if seg is None:
            return None, None
        return seg, seg["base"] + (handle & 0xFFFF)

    def _cstr(self, off: int, limit: int) -> str:
        raw = self.d[off:off + limit]
        end = raw.find(b"\x00")
        if end >= 0:
            raw = raw[:end]
        return raw.decode("latin-1", "replace")

    def _trailer(self, segid: int) -> dict | None:
        if segid in self._trailers:
            return self._trailers[segid]
        seg = self.segs[segid]
        parsed = None
        if seg["flags"] & 0x4000:
            parsed = _parse_trailer(self.d, seg)
        self._trailers[segid] = parsed
        return parsed

    def _walk(self) -> dict:
        out = {}

        def node(pos, level, prefix):
            if level < 3:
                for n in range(16):
                    child = self.dw(pos + n * 0x14)
                    if child:
                        node(child, level + 1, prefix | (n << (4 * level)))
                return
            for n in range(16):
                slot = pos + n * 0x18
                filepos = self.dw(slot)
                flags = self.w(slot + 8)
                size = self.w(slot + 0xC)
                key = prefix | (n << 12)
                if filepos and filepos + 4 <= len(self.d) and self.w(filepos) == key and self.w(filepos + 2) == size - 2:
                    out[key] = {
                        "segid": key,
                        "filepos": filepos,
                        "size": size,
                        "flags": flags,
                        "base": filepos - 6,
                    }

        node(self.dw(self.H + 0x10E), 0, 0)
        return out


def _parse_trailer(data: bytes, seg: dict) -> dict | None:
    off = seg["filepos"] + seg["size"]
    if off + 4 > len(data) or struct.unpack_from("<H", data, off)[0] != 1:
        return None
    count = struct.unpack_from("<H", data, off + 2)[0]
    pos = off + 4
    headers = []
    for _i in range(count):
        headers.append(struct.unpack_from("<HHIHH", data, pos))
        pos += 12
    heaps = {0: b"\x00" * 6 + data[seg["filepos"]:seg["filepos"] + seg["size"]]}
    for i, (_a, pre, length, _x, _y) in enumerate(headers):
        blob = data[pos:pos + length]
        pos += length
        if length:
            heaps[i + 1] = b"\x00" * pre + blob
    if pos + 4 > len(data) or struct.unpack_from("<H", data, pos)[0] != 1:
        return None
    n1 = struct.unpack_from("<H", data, pos + 2)[0]
    pos += 4 + 4 * n1
    n2 = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    slots = [struct.unpack_from("<HHHH", data, pos + 8 * i) for i in range(n2)]
    return {"heaps": heaps, "slots": slots}


def _item(trailer: dict | None, handle: int):
    if not trailer or handle in (0, 0xFFFF) or handle >= len(trailer["slots"]):
        return None
    heap, off, _a, _b = trailer["slots"][handle]
    blob = trailer["heaps"].get(heap)
    if blob is None or off >= len(blob):
        return None
    end = struct.unpack_from("<H", blob, off - 6)[0] if off >= 6 else off + 64
    if end <= off or end > len(blob):
        end = min(len(blob), off + 64)
    return blob[off:end]


def _hstr(trailer, handle) -> str:
    raw = _item(trailer, handle)
    if not raw:
        return ""
    return raw.split(b"\x00", 1)[0].decode("latin-1", "replace")


def _htext(trailer, handle) -> str:
    raw = _item(trailer, handle)
    if not raw or len(raw) < 4:
        return ""
    _cap, length = struct.unpack_from("<HH", raw, 0)
    if length > len(raw) - 4:
        return ""
    return raw[4:4 + length].decode("latin-1", "replace")


def _rgb(data: bytes, off: int) -> str:
    return "#%02x%02x%02x" % (data[off], data[off + 1], data[off + 2])


def _kind(number: int) -> str:
    return _CLASSES.get(number, "rect")
