"""A field keeps its own script. The group's click is not written into it."""

from __future__ import annotations

import unittest

from openscript_analysis.formats.tbk.store import keep_group_click

JUMP = 'to handle buttonClick\n  go to page "P310" of book "nida81.tbk"\nend\n'
MOUSE = 'to handle mouseenter\n  send mouseenter to button "selection1"\nend\n'


class GroupClickTests(unittest.TestCase):
    def test_a_field_keeps_its_mouse_script(self):
        field = {"kind": "text", "name": "Selection1", "script": MOUSE}
        button = {"kind": "button", "name": "selection1", "script": ""}
        keep_group_click([button, field], JUMP)
        self.assertNotIn("buttonclick", field["script"].lower())
        self.assertEqual(field["group_script"], JUMP)
        self.assertIn("buttonclick", button["script"].lower())
        self.assertNotIn("group_script", button)


if __name__ == "__main__":
    unittest.main()
