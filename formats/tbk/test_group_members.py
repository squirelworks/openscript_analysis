"""A group is a record of kind 0xB. Its children say which group they belong to."""

from __future__ import annotations

import struct
import unittest

from openscript_analysis.formats.tbk.store import _Store, tag_groups


class _Bytes(_Store):
    """A store holding only the bytes of one group and its two children."""

    def __init__(self, data: bytes) -> None:
        self.d = data
        self.pictures = False

    def _object_name(self, seg, rec):
        return {0x40: "Review 1", 0xA0: "inner"}.get(rec, "")

    def _script(self, seg, rec, decode, a, b):
        return ""


def _record(buf: bytearray, rec: int, kind: int, parent: int, flags: int = 1) -> None:
    struct.pack_into("<H", buf, rec - 2, kind)
    struct.pack_into("<H", buf, rec + 4, parent)
    buf[rec + 0x1F] = flags


class GroupMembersTests(unittest.TestCase):
    def _store(self) -> tuple[_Bytes, dict]:
        buf = bytearray(0x400)
        group, child_a, child_b = 0x40, 0x100, 0x140
        _record(buf, group, 0xB, 0)
        _record(buf, child_a, 0x8, group)
        _record(buf, child_b, 0x8, group)
        struct.pack_into("<H", buf, group + 0x24, 2)
        struct.pack_into("<H", buf, group + 0x2E, 0x300)
        struct.pack_into("<H", buf, 0x300, child_a)
        struct.pack_into("<H", buf, 0x30A, child_b)
        seg = {"base": 0, "filepos": 0, "size": len(buf), "segid": 1}
        return _Bytes(bytes(buf)), seg

    def test_each_child_names_its_group(self):
        store, seg = self._store()
        out = store._emit(seg, 0x40, None)
        self.assertEqual(len(out), 2)
        self.assertEqual([o["groups"] for o in out], [["Review 1"], ["Review 1"]])

    def test_a_hidden_group_hides_its_children(self):
        store, seg = self._store()
        buf = bytearray(store.d)
        buf[0x40 + 0x1F] = 0x20
        out = _Bytes(bytes(buf))._emit(seg, 0x40, None)
        self.assertEqual([o.get("hidden") for o in out], [True, True])

    def test_a_visible_group_leaves_its_children_alone(self):
        store, seg = self._store()
        out = store._emit(seg, 0x40, None)
        self.assertEqual([o.get("hidden") for o in out], [None, None])

    def test_an_outer_group_is_added_after_the_inner_one(self):
        objs = [{"kind": "rect"}]
        tag_groups(objs, "inner")
        tag_groups(objs, "outer")
        self.assertEqual(objs[0]["groups"], ["inner", "outer"])

    def test_an_object_in_no_group_has_no_groups_key(self):
        self.assertNotIn("groups", {"kind": "rect"})


if __name__ == "__main__":
    unittest.main()
