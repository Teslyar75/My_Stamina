"""Пометки правой кнопкой: запись, хранение, блок для агента."""
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stamina import marks, pilots


class MarksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        pilots.reset_root(Path(self.tmp.name))

    def tearDown(self):
        pilots.reset_root(None)
        self.tmp.cleanup()

    def test_empty(self):
        self.assertEqual(marks.load(), [])
        self.assertEqual(marks.recent(), [])
        self.assertEqual(marks.context_block(), "")
        self.assertEqual(marks.last_id(), 0)

    def test_add_and_describe(self):
        mark = marks.add(312, 640, "МОСТИК", "", "HudButton «ПЕЧАТЬ»", root=(1920, 1080))
        self.assertEqual(mark["x"], 312)
        self.assertAlmostEqual(mark["nx"], 312 / 1920, places=4)
        self.assertEqual(mark["root"], [1920, 1080])
        text = marks.describe(mark)
        self.assertIn("МОСТИК", text)
        self.assertIn("ПЕЧАТЬ", text)
        self.assertIn("312, 640", text)

    def test_describe_with_subtab(self):
        mark = marks.add(10, 20, "ОРИОН", "чат", "Text", root=(800, 600))
        self.assertIn("ОРИОН / чат", marks.describe(mark))

    def test_persisted(self):
        marks.add(1, 2, "МОСТИК", root=(800, 600))
        marks.add(3, 4, "МИССИИ", root=(800, 600))
        self.assertEqual(len(marks.load()), 2)
        self.assertEqual(marks.recent(1)[0]["x"], 3)

    def test_since_returns_only_new(self):
        old = marks.add(1, 1, "МОСТИК", root=(800, 600))
        new = marks.add(2, 2, "МИССИИ", root=(800, 600))
        got = marks.since(old["id"])
        self.assertEqual([m["id"] for m in got], [new["id"]])

    def test_context_block_lists_points(self):
        marks.add(5, 6, "МОСТИК", "", "HudButton «ПЕЧАТЬ»", root=(1920, 1080))
        block = marks.context_block()
        self.assertIn("ПРАВАЯ КНОПКА МЫШИ", block.upper())
        self.assertIn("1920x1080", block)
        self.assertIn("5,6", block.replace(" ", ""))

    def test_context_block_note(self):
        marks.add(5, 6, "МОСТИК", note="кнопка не влезает", root=(800, 600))
        self.assertIn("кнопка не влезает", marks.context_block())

    def test_place_line_matches_agent_block(self):
        mark = marks.add(5, 6, "МОСТИК", "чат", "HudButton", root=(800, 600))
        line = marks.place_line(mark)
        self.assertIn("МОСТИК / чат / HudButton", line)
        self.assertIn("окно 800x600, точка 5,6", line)
        self.assertIn(line, marks.context_block())

    def test_limit_keeps_last(self):
        for i in range(marks.LIMIT + 5):
            marks.add(i, i, "МОСТИК", root=(800, 600))
        items = marks.load()
        self.assertEqual(len(items), marks.LIMIT)
        self.assertEqual(items[-1]["x"], marks.LIMIT + 4)

    def test_clear(self):
        marks.add(1, 1, "МОСТИК", root=(800, 600))
        marks.clear()
        self.assertEqual(marks.load(), [])

    def test_broken_file_is_empty_list(self):
        path = marks.marks_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{oops", encoding="utf-8")
        self.assertEqual(marks.load(), [])

    def test_zone_without_root(self):
        mark = marks.add(1, 2, "ОТДЫХ")
        self.assertEqual(mark["nx"], 0.0)
        self.assertEqual(mark["root"], [0, 0])


if __name__ == "__main__":
    unittest.main()



def test_mark_copies_location_to_clipboard_but_not_from_text_fields():
    import tkinter as tk
    from stamina import clipboard
    from stamina.cockpit import Cockpit
    root = tk.Tk()
    root.withdraw()
    try:
        if not clipboard.set_text("probe", root):
            import pytest
            pytest.skip("system clipboard unavailable in this session")
        assert Cockpit._copy_mark(root, "МОСТИК / x=10 y=20") is True
        assert clipboard.get_text(root) == "МОСТИК / x=10 y=20"
        clipboard.set_text("keep", root)
        assert Cockpit._copy_mark(root, "other", tk.Entry(root)) is False
        assert clipboard.get_text(root) == "keep"
    finally:
        root.destroy()
