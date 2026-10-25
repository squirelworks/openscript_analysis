"""An object whose visible bit is clear is read, and says so. It is not dropped."""

from __future__ import annotations

import struct
import unittest

from openscript_analysis.formats.tbk.store import _Store


class _Bytes(_Store):
    def __init__(self, data: bytes) -> None:
        self.d = data
        self.pictures = False

    def _object_name(self, seg, rec):
        return {0x100: "shown", 0x140: "TryAgain"}.get(rec, "")

    def _script(self, seg, rec, decode, a, b):
        return ""


def _rect(buf: bytearray, rec: int, flags: int) -> None:
    struct.pack_into("<H", buf, rec - 2, 0x8)
    buf[rec + 0x1F] = flags


class HiddenObjectTests(unittest.TestCase):
    def _emit(self, flags: int) -> list[dict]:
        buf = bytearray(0x400)
        _rect(buf, 0x100, flags)
        seg = {"base": 0, "filepos": 0, "size": len(buf), "segid": 1}
        return _Bytes(bytes(buf))._emit(seg, 0x100, None)

    def test_a_visible_rectangle_has_no_hidden_key(self):
        out = self._emit(1)
        self.assertEqual(len(out), 1)
        self.assertNotIn("hidden", out[0])

    def test_a_hidden_rectangle_is_read_and_marked(self):
        out = self._emit(0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "shown")
        self.assertIs(out[0]["hidden"], True)


if __name__ == "__main__":
    unittest.main()
