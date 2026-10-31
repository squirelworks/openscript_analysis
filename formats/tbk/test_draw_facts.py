"""Stroke, paint order, and hotword spans."""

from __future__ import annotations

import os
import struct
import unittest
from pathlib import Path

from openscript_analysis.formats.tbk.store import _Store, _handle_words, read_store, stroke_width


class StrokeTests(unittest.TestCase):
    def test_the_style_byte_names_the_width(self):
        self.assertEqual(stroke_width(4), 1)
        self.assertEqual(stroke_width(5), 2)
        self.assertEqual(stroke_width(6), 3)
        self.assertEqual(stroke_width(9), 8)

    def test_none_is_no_stroke_and_dotted_is_one_pixel(self):
        self.assertEqual(stroke_width(1), 0)
        self.assertEqual(stroke_width(2), 1)

    def test_a_style_not_read_yet_stays_one_pixel(self):
        for style in (0, 3, 7, 8, 10, 255):
            self.assertEqual(stroke_width(style), 1)

    def test_a_rectangle_stores_the_width(self):
        buf = bytearray(0x200)
        struct.pack_into("<H", buf, 0x100 - 2, 0x8)
        buf[0x100 + 0x1F] = 1
        buf[0x100 + 0x22] = 9
        seg = {"base": 0, "filepos": 0, "size": len(buf), "segid": 1}
        out = _Named(bytes(buf))._emit(seg, 0x100, None)
        self.assertEqual(out[0]["stroke"], 8)

    def test_a_button_does_not_read_its_caption_word_as_a_stroke(self):
        buf = bytearray(0x200)
        struct.pack_into("<H", buf, 0x100 - 2, 0x9)
        buf[0x100 + 0x1F] = 1
        buf[0x100 + 0x22] = 9
        seg = {"base": 0, "filepos": 0, "size": len(buf), "segid": 1}
        out = _Named(bytes(buf))._emit(seg, 0x100, None)
        self.assertNotIn("stroke", out[0])


class _Named(_Store):
    def __init__(self, data: bytes) -> None:
        self.d = data
        self.pictures = False

    def _object_name(self, seg, rec):
        return ""

    def _script(self, seg, rec, decode, a, b):
        return ""

    def _caption(self, seg, rec):
        return ""

    def _trailer(self, segid):
        return None


class OrderTests(unittest.TestCase):
    def test_the_handle_is_the_near_words(self):
        trailer = {"heaps": {1: bytes.fromhex("5a02da029c00e400f603")}, "slots": [(0, 0, 0, 0), (1, 0, 0, 0)]}
        self.assertEqual(_handle_words(trailer, 1, 5), (0x25A, 0x2DA, 0x9C, 0xE4, 0x3F6))
        self.assertEqual(_handle_words(trailer, 4, 5), ())

    def test_the_list_paints_back_to_front(self):
        store = _Listed((0x41, 0x18))
        seg = {"base": 0, "segid": 1, "filepos": 0, "size": 0}
        self.assertEqual(store._layered(seg, 0x14, [0x18, 0x41]), [0x41, 0x18])

    def test_a_list_that_names_something_else_is_ignored(self):
        store = _Listed((0x01, 0x02))
        seg = {"base": 0, "segid": 1, "filepos": 0, "size": 0}
        self.assertEqual(store._layered(seg, 0x14, [0x18, 0x41]), [0x18, 0x41])

    def test_two_rectangles_follow_the_list(self):
        buf = bytearray(0x100)
        _rect(buf, 0x18)
        _rect(buf, 0x41)
        _layer(buf, 0x6A, 0x14, (0x41, 0x18))
        store = _Trailer(bytes(buf), _words(1, (0x41, 0x18)))
        seg = {"base": 0, "filepos": 0, "size": len(buf), "segid": 1}
        self.assertEqual(store._children(seg, 0x14), [0x41, 0x18])


class _Listed(_Store):
    def __init__(self, listed) -> None:
        self.d = b""
        self.listed = listed

    def _layer_nears(self, seg, parent):
        return self.listed


class _Trailer(_Store):
    def __init__(self, data: bytes, trailer: dict) -> None:
        self.d = data
        self.pictures = False
        self.trailer = trailer

    def _trailer(self, segid):
        return self.trailer


def _rect(buf: bytearray, at: int) -> None:
    struct.pack_into("<HH", buf, at - 4, at + 41, 0x8)
    struct.pack_into("<H", buf, at + 4, 0x14)


def _layer(buf: bytearray, at: int, parent: int, nears: tuple[int, ...]) -> None:
    struct.pack_into("<HH", buf, at - 4, at + 15, 0x06)
    struct.pack_into("<H", buf, at + 2, len(nears))
    struct.pack_into("<H", buf, at + 8, parent)
    struct.pack_into("<H", buf, at + 0x0C, 1)


def _words(handle: int, nears: tuple[int, ...]) -> dict:
    blob = b"".join(struct.pack("<H", near) for near in nears)
    slots = [(0, 0, 0, 0)] * handle + [(1, 0, 0, 0)]
    return {"heaps": {1: blob}, "slots": slots}


def _lesson():
    path = os.environ.get("OPENSCRIPT_TBK")
    if path and os.path.isfile(path):
        return Path(path)
    return None


@unittest.skipUnless(_lesson(), "set OPENSCRIPT_TBK to Logic Families")
class LessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from openscript_analysis.formats.tbk.expand import decompress, load_keywords

        keywords = load_keywords()

        def decode(source: bytes) -> str:
            return decompress(source, keywords)

        cls.pages = read_store(_lesson().read_bytes(), decode, pictures=False)["pages"]

    def test_p300_frame_is_behind_the_selection(self):
        page = next(item for item in self.pages if item["id"] == "P300")
        names = [obj.get("name") or "" for obj in page["objects"] if obj.get("layer") == "page"]
        self.assertLess(names.index("MenuFrame"), names.index("selection1"))

    def test_the_five_hotwords(self):
        found = []
        for page in self.pages:
            for obj in page["objects"]:
                text = (obj.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
                for hot in obj.get("hotwords") or []:
                    found.append((page["id"], text[hot["start"]:hot["end"]], hot["script"].lower()))
        self.assertEqual(
            [(page, word) for page, word, _script in found],
            [
                ("P1080", "tolerance"),
                ("P1082", "tolerance"),
                ("P1200", "propagation delay"),
                ("P1207", "propagation delay"),
                ("P2070", "impedance"),
            ],
        )
        self.assertIn("p1085", found[0][2])
        self.assertIn("p1205", found[2][2])
        self.assertIn("p2075", found[4][2])

    def test_a_hidden_mark_is_eight_pixels_and_a_polygon_can_have_none(self):
        marks = [
            obj
            for page in self.pages
            for obj in page["objects"]
            if obj.get("name") == "Correct" and obj.get("stroke") == 8
        ]
        bare = [obj for page in self.pages for obj in page["objects"] if obj.get("stroke") == 0]
        self.assertEqual(len(marks), 20)
        self.assertGreaterEqual(len(bare), 5)
        self.assertTrue(all("stroke" not in obj for page in self.pages for obj in page["objects"] if obj["kind"] == "text"))


if __name__ == "__main__":
    unittest.main()
