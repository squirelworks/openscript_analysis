"""The rest face of a push button, and the checked face of a radio button."""

from __future__ import annotations

import unittest

from openscript_analysis.formats.tbk.store import rest_face


class RestFaceTests(unittest.TestCase):
    def test_begin_is_the_only_push_button_whose_slots_are_swapped(self):
        # P10004 selection1 stores 163 in the up slot and 161 in the checked slot.
        self.assertEqual(rest_face(1, 163, 161), 161)
        # Every other push button in the lesson stores the raised face first.
        self.assertEqual(rest_face(1, 161, 163), 161)
        # A quiz letter is style 9. The checked slot is the answer key.
        self.assertEqual(rest_face(9, 116, 118), 116)
        self.assertEqual(rest_face(9, 119, 121), 119)


if __name__ == "__main__":
    unittest.main()
