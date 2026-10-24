"""A written store has to open in the same reader a real book uses."""

import unittest
from pathlib import Path

from openscript_analysis.formats.tbk.store import _without_owned, read_store
from openscript_analysis.formats.tbk.storewrite import splice_text, write_store


class StoreWriteTest(unittest.TestCase):
    def test_pages_text_and_margins_come_back(self):
        path = Path("/tmp/storewrite-one.tbk")
        write_store(path, {"pages": [
            {"id": "P0", "text": "Hello from the store"},
            {"id": "P10", "text": "Second page"},
        ]})
        book = read_store(path.read_bytes())
        self.assertEqual([page["id"] for page in book["pages"]], ["P0", "P10"])
        field = book["pages"][0]["objects"][-1]
        self.assertEqual(field["text"], "Hello from the store")
        self.assertEqual(field["indentFirst"], 360)
        self.assertEqual(field["indentLeft"], 360)
        self.assertEqual(field["indentRight"], 310)
        self.assertEqual(field["tab"], 720)
        self.assertEqual(field["marginL"], 360)
        self.assertEqual(field["marginR"], 310)
        self.assertEqual(book["pages"][0]["fill"], "#0000bf")

    def test_an_object_handler_is_not_the_page_handler(self):
        text = "to handle buttonClick\n  go to page \"P400\"\nend\nto handle buttonClick\n  send next\nend"
        kept = _without_owned(text, ['to handle buttonClick\n  go to page "P400"\nend'])
        self.assertIn("send next", kept)
        self.assertNotIn("P400", kept)

    def test_twenty_pages_cross_the_directory_nibble(self):
        path = Path("/tmp/storewrite-many.tbk")
        write_store(path, {"pages": [{"id": f"P{i}", "text": f"line {i}"} for i in range(20)]})
        book = read_store(path.read_bytes())
        self.assertEqual(book["pages"][-1]["objects"][-1]["text"], "line 19")

    def test_splice_refuses_a_different_length(self):
        with self.assertRaises(ValueError):
            splice_text(b"abcd", "ab", "a")


if __name__ == "__main__":
    unittest.main()
