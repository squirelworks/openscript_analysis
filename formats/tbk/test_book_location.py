"""A book is found where ZZZTBKBOOKLOC says, not at a fixed 0xC00.

The shells here are built in the test. No ToolBook bytes are stored.
``INSTRUCTOR_BOOKS`` names a local folder of ToolBook Instructor 8 books.
When it is set, ``blank.tbk`` from that folder must open too. Its book
starts at 0xE00.
"""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path

from openscript_analysis.formats.tbk.tbk import BOOK_MAGIC, load

STORE = b"\x03JBO\x01\x00\x00\x08"


def shell(at: int, name: str = "ZZZTBKBOOKLOC", magic: int = BOOK_MAGIC) -> bytes:
    """A PE stub with one RCDATA resource NAME = (at, magic), then a book at AT."""
    pe, rsrc_rva, rsrc_raw = 0x80, 0x1000, 0x400
    out = bytearray(at)
    out[0:2] = b"MZ"
    struct.pack_into("<I", out, 0x3C, pe)
    out[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", out, pe + 4, 0x14C, 1, 0, 0, 0, 0xE0, 0)
    opt = pe + 24
    struct.pack_into("<H", out, opt, 0x10B)
    struct.pack_into("<II", out, opt + 96 + 2 * 8, rsrc_rva, 0x200)
    sec = opt + 0xE0
    struct.pack_into("<8sIIII", out, sec, b".rsrc", 0x200, rsrc_rva, 0x200, rsrc_raw)

    # type 10 -> name -> language 1033 -> data entry
    struct.pack_into("<IIHHHH", out, rsrc_raw, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", out, rsrc_raw + 16, 10, 0x80000000 | 0x18)
    struct.pack_into("<IIHHHH", out, rsrc_raw + 0x18, 0, 0, 0, 0, 1, 0)
    struct.pack_into("<II", out, rsrc_raw + 0x28, 0x80000000 | 0x60, 0x80000000 | 0x30)
    struct.pack_into("<IIHHHH", out, rsrc_raw + 0x30, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", out, rsrc_raw + 0x40, 1033, 0x48)
    struct.pack_into("<IIII", out, rsrc_raw + 0x48, rsrc_rva + 0x90, 8, 0, 0)
    label = name.encode("utf-16-le")
    struct.pack_into("<H", out, rsrc_raw + 0x60, len(name))
    out[rsrc_raw + 0x62:rsrc_raw + 0x62 + len(label)] = label
    struct.pack_into("<II", out, rsrc_raw + 0x90, at, magic)
    return bytes(out) + STORE + b"\x00" * 24


class BookLocationTests(unittest.TestCase):
    def _load(self, data: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.tbk"
            path.write_bytes(data)
            return load(path)

    def test_a_book_at_0xc00_opens(self):
        book = self._load(shell(0xC00))
        self.assertEqual(book.offset, 0xC00)

    def test_a_book_at_0xe00_opens(self):
        book = self._load(shell(0xE00))
        self.assertEqual(book.offset, 0xE00)

    def test_the_resource_magic_is_not_the_book(self):
        with self.assertRaises(ValueError):
            self._load(shell(0xE00, magic=0x11111111))

    def test_another_resource_name_is_not_the_book(self):
        with self.assertRaises(ValueError):
            self._load(shell(0xE00, name="ZZZTBKFLAGSXX"))

    def test_the_old_marker_at_0xc00_still_opens(self):
        data = b"\x00" * 0xC00 + struct.pack("<I", BOOK_MAGIC) + b"\x00" * 8
        self.assertEqual(getattr(self._load(data), "offset", 0xC00), 0xC00)

    def test_other_bytes_are_refused(self):
        with self.assertRaises(ValueError):
            self._load(b"FBK1\x00{}" + b"\x00" * 0x1000)


class InstructorBookTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("INSTRUCTOR_BOOKS"), "INSTRUCTOR_BOOKS is not set")
    def test_blank_tbk_opens(self):
        path = Path(os.environ["INSTRUCTOR_BOOKS"]) / "blank.tbk"
        if not path.exists():
            self.skipTest(f"{path} is not here")
        self.assertEqual(load(path).offset, 0xE00)


if __name__ == "__main__":
    unittest.main()
