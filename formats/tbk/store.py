"""ToolBook 8 object store.

The book image starts at the ``03 4A 42 4F`` header. A handle is
``segment id << 16 | near offset``. The segment's file bytes begin
six bytes after that offset's zero, so a near pointer ``p`` is at
``file position + p - 6``.

Checked against 9e954d01.tbk: 131 pages, every background reference,
field text through the trailer handle, and class ``0x10`` outlines.
A button face is chosen from ``+0x26``. A bitmap with the stored-in-file
bit comes from the table at header ``+0x104``.
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
    0x11: "arc",
    0x13: "line",
}


def keep_group_click(children: list[dict], script: str) -> None:
    """Leave a group's buttonClick off a child that has its own script.

    The button under a menu picture has no script, so the group's handler
    is the button's. A field that already handles the mouse keeps that
    script. The jump is stored beside it for the click, not inside it.
    """
    if not script or "buttonclick" not in script.lower():
        return
    for obj in children:
        own = obj.get("script") or ""
        if "buttonclick" in own.lower():
            continue
        if own.strip():
            obj["group_script"] = script
        else:
            obj["script"] = script


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
                    "layer": "background",
                })
                objects.extend(self._layer_objects(bg["seg"], bg["rec"], decode, "background"))
            objects.extend(self._layer_objects(seg, rec, decode, "page"))
            out.append({
                "id": self._cstr(rec + 6, 32) or entry["name"],
                "size": (width, height),
                "fill": bg["fill"] if bg else "",
                "script": self._script(seg, rec, decode, 0x0A, 0x0B) or self._inline_script(seg, decode),
                "background_script": (
                    self._script(bg["seg"], bg["rec"], decode, 0x0A, 0x0B) or self._inline_script(bg["seg"], decode)
                ) if bg else "",
                "props": self._props(seg),
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

    def _layer_objects(self, seg: dict, rec: int, decode, layer: str = "page") -> list[dict]:
        parent = rec - seg["base"]
        found = []
        for child in self._children(seg, parent):
            found.extend(self._emit(seg, child, decode))
        for obj in found:
            obj["layer"] = layer
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
            # The click belongs to the group. A child with no script of its
            # own is the thing under the pointer, so it keeps that handler.
            # A child that already has a script keeps its own. The group's
            # handler is remembered beside it and is not written into it.
            keep_group_click(out, self._script(seg, rec, decode, 0x0A, 0x0B))
            return out
        if not self.d[rec + 0x1F] & 1:
            return []
        name = _kind(kind)
        bounds = tuple(self.sw(rec + 0x0F + step) for step in (0, 2, 4, 6))
        obj = {
            "kind": name,
            "bounds": bounds,
            "fill": _rgb(self.d, rec + 0x1B),
            "outline": _rgb(self.d, rec + 0x17),
            "name": self._object_name(seg, rec),
            "text": "",
            "script": self._script(seg, rec, decode, 0x0A, 0x0B),
            "points": [],
            "align": self.d[rec + 0x26],
            "direct": bool(self.d[rec + 0x1F] & 0x20),
        }
        if self.d[rec + 0x1F] & 0x40:
            obj["fill"] = "#c0c0c0"
            obj["outline"] = "#000000"
        pattern = self.d[rec + 0x25] if kind in (0x8, 0xC, 0xD, 0xF, 0x10) else 0xFE
        if pattern == 0xFD:
            obj["fill"] = ""
        if kind in (0xF, 0x10):
            obj["points"] = self._mapped(seg, rec, 0x30, 0x32, bounds)
        elif kind == 0x11:
            # No pattern byte. Two local endpoints start at +0x25. The ellipse
            # they sit on is center +0x2D/+0x2F, radii +0x31/+0x33. That local
            # rectangle maps onto the bounds. Checked against the TBX vertices.
            cx, cy = self.sw(rec + 0x2D), self.sw(rec + 0x2F)
            rx, ry = self.sw(rec + 0x31), self.sw(rec + 0x33)
            local = (cx - rx, cy - ry, cx + rx, cy + ry)
            obj["ends"] = [
                self._into(bounds, local, self.sw(rec + 0x25), self.sw(rec + 0x27)),
                self._into(bounds, local, self.sw(rec + 0x29), self.sw(rec + 0x2B)),
            ]
        elif kind == 0x13:
            obj["points"] = self._mapped(seg, rec, 0x2D, 0x2F, bounds)
            obj["kind"] = "line"
        elif kind == 0xE:
            obj["points"] = [
                (self.sw(rec + 0x26), self.sw(rec + 0x28)),
                (self.sw(rec + 0x2A), self.sw(rec + 0x2C)),
            ]
        elif kind == 0xA:
            text, face = self._field_style(seg, rec)
            obj["text"] = text
            if not face:
                face = self._face(self.w(rec + 0x22))
            if face:
                obj["font"] = face
            obj["border"] = self.d[rec + 0x36]
            # Paragraph dialog, checked on the P400 body field: first line,
            # other lines, from the right, then the tab spacing. The tab is
            # not an inset. 720 in that word is the tab on every one of these.
            first, left, right, tab = (self.w(rec + off) for off in (0x28, 0x2A, 0x2C, 0x2E))
            obj["indentFirst"] = first
            obj["indentLeft"] = left
            obj["indentRight"] = right
            obj["tab"] = tab
            if left or first:
                obj["marginL"] = left or first
            if right:
                obj["marginR"] = right
            # Bit 1 is transparent. The border byte is none, rectangle,
            # scrolling, shadowed, raised, inset.
            if self.d[rec + 0x1F] & 0x02 or self.d[rec + 0x25] == 0xFD:
                obj["fill"] = ""
        elif kind == 0x9:
            obj["text"] = self._caption(seg, rec)
            obj["bmp"] = self._button_bmp(seg, rec)
            obj["transparent"] = bool(self.d[rec + 0x1F] & 0x02)
        elif kind == 0x15:
            # A paint object. The dword at +0x51 is a near pointer to the
            # BITMAPINFOHEADER, and the pixels follow it in the segment.
            obj["bmp"] = self._paint_bmp(seg, rec)
        if kind == 0xA and not obj["text"] and not obj["name"] and obj.get("border", 1) == 1:
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

    def _into(self, bounds, local, x, y) -> tuple[int, int]:
        left, top, right, bottom = bounds
        ll, lt, lr, lb = local
        span_x = lr - ll
        span_y = lb - lt
        px = left if span_x == 0 else left + (x - ll) * (right - left) / span_x
        py = top if span_y == 0 else top + (y - lt) * (bottom - top) / span_y
        return int(round(px)), int(round(py))

    def _points(self, seg, rec, count_at, ptr_at) -> list[tuple[int, int]]:
        count = self.w(rec + count_at)
        ptr = self.w(rec + ptr_at)
        base = seg["base"]
        end = seg["filepos"] + seg["size"]
        if not 0 < count < 500 or not ptr or base + ptr + 4 * count > end:
            return []
        return [(self.sw(base + ptr + 4 * i), self.sw(base + ptr + 4 * i + 2)) for i in range(count)]

    def _field_text(self, seg, rec) -> str:
        text, _face = self._field_style(seg, rec)
        return text

    def _field_style(self, seg, rec) -> tuple[str, str]:
        trailer = self._trailer(seg["segid"])
        ptr = self.w(rec + 0x24)
        heap = trailer["heaps"].get(0) if trailer else None
        if not heap or ptr + 4 > len(heap):
            return "", ""
        runs_handle, text_handle = struct.unpack_from("<HH", heap, ptr)
        text = _htext(trailer, text_handle)
        raw = _item_span(trailer, runs_handle, 480)
        runs = []
        if len(raw) >= 6:
            pos = 4
            previous = -1
            while pos + 6 <= len(raw) and len(runs) < 64:
                start = struct.unpack_from("<H", raw, pos)[0]
                font = struct.unpack_from("<I", raw, pos + 2)[0]
                name = self._face(font)
                if not name or start < previous:
                    break
                runs.append((start, name))
                previous = start
                pos += 11
        return apply_faces(text, runs)

    def _face(self, ptr: int) -> str:
        """A style run stores a near pointer to the face name in the book."""
        if not ptr:
            return ""
        seg = self.segs.get(self._book_seg())
        if seg is None:
            return ""
        off = seg["base"] + (ptr & 0xFFFF)
        if off < 0 or off >= len(self.d):
            return ""
        end = self.d.find(b"\x00", off, off + 40)
        if end <= off:
            return ""
        raw = self.d[off:end]
        if not raw or any(char < 32 or char > 126 for char in raw):
            return ""
        return raw.decode("latin-1")

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
        end = seg["filepos"] + seg["size"]
        if block + 0x16 > end:
            return None
        # FUN_1230_18d2. Bit 0x01 is enabled, 0x04 is pressed, 0x10 is checked.
        flags = self.d[rec + 0x26]
        kind = self.d[rec + 0x27] & 0x7F
        up = self.w(block + 0x15)
        down = self.w(block + 0x27) if block + 0x29 <= end else 0
        disabled = self.w(block + 0x39) if block + 0x3B <= end else 0
        checked = self.w(block + 0x4B) if block + 0x4D <= end else 0
        if (flags & 0x01) == 0 and disabled:
            stored = disabled
        elif flags & 0x04 and down:
            stored = down
        elif flags & 0x10 and checked and kind in (5, 6, 8, 9):
            stored = checked
        else:
            stored = up
        if stored <= 1:
            return None
        return self._bitmap(stored - 1)

    def _bitmap(self, ident: int) -> bytes | None:
        entry = self._directory(1).get(ident)
        if not entry:
            return None
        body = entry["body"]
        if self.d[body + 8] & 1:
            return self._stored_bitmap(self.w(body + 9))
        return self._bmp_at(entry["base"] + self.w(body + 9))

    def _stored_bitmap(self, index: int) -> bytes | None:
        """Bit 0 of the resource: the bytes are a row of the table at header +0x104.

        The table is twelve bytes of head, then twelve-byte rows. The word
        at resource +0x09 is a 1-based row number. The row's third dword is
        the file offset of the same 8-byte prefix the inline bitmaps use.
        """
        if index < 1:
            return None
        table = self.dw(self.H + 0x104)
        if table <= 0 or table + 12 > len(self.d):
            return None
        count = self.w(table + 10)
        if index > count:
            return None
        row = table + 12 + (index - 1) * 12
        if row + 12 > len(self.d):
            return None
        _size, _unused, offset = struct.unpack_from("<III", self.d, row)
        return self._bmp_at(offset)

    def _bmp_at(self, data_at: int) -> bytes | None:
        if data_at < 0 or data_at + 14 > len(self.d):
            return None
        if self.d[data_at + 8:data_at + 10] != b"BM":
            return None
        size = self.dw(data_at + 10)
        end = data_at + 8 + size
        if size < 14 or end > len(self.d):
            return None
        return self.d[data_at + 8:end]

    def _paint_bmp(self, seg: dict, rec: int) -> bytes | None:
        ptr = self.dw(rec + 0x51)
        if not ptr:
            return None
        info = seg["base"] + ptr
        if info < 0 or info + 40 > len(self.d) or self.dw(info) < 40:
            return None
        header = self.dw(info)
        width, height = struct.unpack_from("<ii", self.d, info + 4)
        planes = self.w(info + 12)
        bpp = self.w(info + 14)
        compression = self.dw(info + 16)
        pixels = abs(height)
        if planes != 1 or compression != 0 or width <= 0 or pixels == 0:
            return None
        if width > 4000 or pixels > 4000 or bpp not in (1, 4, 8, 24, 32):
            return None
        used = self.dw(info + 32)
        colors = used if bpp > 8 else (used or (1 << bpp))
        stride = ((width * bpp + 31) // 32) * 4
        image = self.dw(info + 20) or stride * pixels
        if image < stride * pixels:
            image = stride * pixels
        palette = colors * 4
        if info + header + palette > len(self.d):
            return None
        end = seg["filepos"] + seg["size"]
        inline = info + header + palette
        if inline + image <= end:
            bits = self.d[inline:inline + image]
        else:
            bits = self._paint_bits(image)
            if not bits:
                return None
        dib = self.d[info:info + header + palette] + bits
        offbits = 14 + header + palette
        head = struct.pack("<2sIHHI", b"BM", 14 + len(dib), 0, 0, offbits)
        return head + dib

    def _paint_bits(self, image: int) -> bytes | None:
        """Pixels that do not fit in the segment are a row of the table at +0x104.

        The row's first dword is the byte count and the third is the file offset.
        """
        table = self.dw(self.H + 0x104)
        if table <= 0 or table + 12 > len(self.d):
            return None
        count = self.w(table + 10)
        found = None
        for i in range(count):
            row = table + 12 + i * 12
            if row + 12 > len(self.d):
                break
            size, _unused, offset = struct.unpack_from("<III", self.d, row)
            if size != image or offset < 0 or offset + image > len(self.d):
                continue
            if found is not None:
                return None
            found = offset
        if found is None:
            return None
        return self.d[found:found + image]

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

    def _inline_script(self, seg: dict, decode) -> str:
        """A background keeps its handler in the segment, not at +0x0B.

        Logo is plain ``To handle Buttonclick``. The Test background is
        tokenized, and that is the script that runs the quiz buttons.
        """
        cached = seg.get("_script")
        if cached is not None:
            return cached
        if decode is None:
            seg["_script"] = ""
            return ""
        start = seg["filepos"]
        end = start + seg["size"]
        pieces = []
        at = start
        while at < end:
            j = self.d.find(b"To \x81", at, end)
            if j < 0:
                break
            try:
                text = decode(self.d[j:end])
            except Exception:
                text = ""
            if text and text not in pieces:
                pieces.append(text)
            at = j + 3
        blob = self.d[start:end]
        try:
            from openscript_analysis.formats.tbk.expand import load_keywords, read_handlers
            for handler in read_handlers(blob, load_keywords()):
                text = handler.get("source") or ""
                if text and text not in pieces:
                    pieces.append(text)
        except Exception:
            pass
        found = "\n".join(pieces)
        seg["_script"] = found
        return found

    def _props(self, seg: dict) -> dict:
        """User properties kept beside the page, such as the quiz answer.

        The value sits in front of the name: a type word, a length, then the
        bytes. Answer, QuestionNo and TestNo are how a quiz page is graded.
        """
        start = seg["filepos"]
        stop = start + seg["size"] + 2048
        later = [other["filepos"] for other in self.segs.values() if other["filepos"] > start]
        if later:
            stop = min(stop, min(later))
        blob = self.d[start:stop]
        found = {}
        for name in (b"Answer", b"QuestionNo", b"TestNo", b"HelpPage"):
            at = 0
            while True:
                i = blob.find(name + b"\x00", at)
                if i < 0:
                    break
                value = _prop_before(blob[max(0, i - 48):i])
                if value is not None:
                    found[name.decode()] = value
                    break
                at = i + 1
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


def _item_span(trailer, handle: int, count: int) -> bytes:
    """Bytes at a handle, not cut at the stored size.

    A style run's size word is 1, and the runs continue past it.
    """
    if not trailer or handle in (0, 0xFFFF) or handle >= len(trailer["slots"]):
        return b""
    heap, off, _a, _b = trailer["slots"][handle]
    blob = trailer["heaps"].get(heap)
    if blob is None or off >= len(blob):
        return b""
    return blob[off:off + count]


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


# The face name is a near pointer in the book segment. Wingdings has no
# file of its own here, so the one glyph this book uses is drawn as a bullet.
_WINGDINGS = {
    "l": "\u25cf",
    "m": "\u25cb",
    "n": "\u25a0",
    "o": "\u25a1",
    "w": "\u2022",
}


def apply_faces(text: str, runs: list[tuple[int, str]]) -> tuple[str, str]:
    """Replace a symbol face with a character the window can draw.

    ``runs`` are ``(start, face)`` in character order. The face returned
    is the one the words use, not the bullet.
    """
    if not text or not runs:
        return text, ""
    faces = [""] * len(text)
    for start, name in runs:
        if start < 0:
            continue
        for index in range(start, len(text)):
            faces[index] = name
    out = []
    for index, char in enumerate(text):
        face = faces[index]
        if face.lower() == "wingdings":
            out.append(_WINGDINGS.get(char, char))
        else:
            out.append(char)
    words = next((name for _start, name in runs if name.lower() != "wingdings"), "")
    return "".join(out), words or runs[0][1]


def _prop_before(window: bytes) -> str | None:
    for marker in (b"\x09\x00", b"\x04\x00"):
        at = window.rfind(marker)
        if at < 0 or at + 4 > len(window):
            continue
        length = int.from_bytes(window[at + 2:at + 4], "little")
        if not 0 < length <= 32 or at + 4 + length > len(window):
            continue
        value = window[at + 4:at + 4 + length]
        if all(32 <= byte < 127 for byte in value):
            return value.decode("latin-1")
    return None


def _rgb(data: bytes, off: int) -> str:
    return "#%02x%02x%02x" % (data[off], data[off + 1], data[off + 2])


def _kind(number: int) -> str:
    return _CLASSES.get(number, "rect")
