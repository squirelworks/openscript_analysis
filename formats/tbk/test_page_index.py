"""The page index is a run of six-byte entries, one per page table."""

from __future__ import annotations

import struct
import unittest

from openscript_analysis.formats.tbk.store import page_table_refs


def index(entries):
    return struct.pack("<HHH", 0x20, len(entries), 0x0100) + b"".join(
        struct.pack("<HI", count, ref) for count, ref in entries
    )


class PageIndexTests(unittest.TestCase):
    def test_every_table_is_read_at_six_bytes_a_step(self):
        entries = [(151, 0x00120031), (150, 0x00130031), (0, 0x00140031), (42, 0x00150031)]
        data = b"\x00" * 10 + index(entries) + b"\xff" * 8
        self.assertEqual(page_table_refs(data, 10), entries)

    def test_one_table_is_unchanged(self):
        self.assertEqual(page_table_refs(index([(131, 0x00020010)]), 0), [(131, 0x00020010)])

    def test_an_index_cut_short_stops_at_the_last_whole_entry(self):
        data = index([(5, 0x00010001), (6, 0x00020002), (7, 0x00030003)])[:-2]
        self.assertEqual(page_table_refs(data, 0), [(5, 0x00010001), (6, 0x00020002)])
        self.assertEqual(page_table_refs(b"\x20\x00", 0), [])


if __name__ == "__main__":
    unittest.main()
