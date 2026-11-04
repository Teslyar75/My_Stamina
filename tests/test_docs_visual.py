"""Документы: маркеры Markdown спрятаны вне строки с курсором."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import pilots


class TestVisual(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"STAMINA_PILOT_DIR": ""})
        self._env.start()
        os.environ.pop("STAMINA_PILOT_DIR", None)
        pilots.reset_root(Path(self._tmp.name))
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        from stamina.docs_screen import DocsScreen
        self.scr = DocsScreen(self.root, mock.Mock(store=None))
        self.scr.new_doc()
        t = self.t = self.scr.text
        t.insert("1.0", "# Заголовок\n**жирный** и *курсив*\n- пункт")
        t.mark_set("insert", "1.3")
        self.scr.highlight()

    def tearDown(self):
        self.root.destroy()
        self._env.stop()
        self._tmp.cleanup()

    def hidden(self, ln):
        t = self.t
        return "".join(t.get(f"{ln}.{k}") for k in range(len(t.get(f"{ln}.0", f"{ln}.end")))
                       if "md_hide" in t.tag_names(f"{ln}.{k}"))

    def test_hidden_except_cursor_line(self):
        self.assertEqual(self.hidden(1), "")
        self.assertEqual(self.hidden(2), "******")
        self.assertEqual(self.hidden(3), "")                   # маркер списка виден
        self.t.mark_set("insert", "2.2")
        self.scr.reveal_cursor_line()
        self.assertEqual(self.hidden(1), "# ")
        self.assertEqual(self.hidden(2), "")

    def test_text_and_saved_markdown_unchanged(self):
        self.assertEqual(self.t.get("1.0", "end-1c"), "# Заголовок\n**жирный** и *курсив*\n- пункт")
        self.assertIn("**жирный**", "".join(s.get("t", "") for s in self.scr.segments()))

    def test_toggle_off_and_on(self):
        self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="M", state=0x5))
        self.assertFalse(self.scr.visual_on())
        self.assertEqual(self.hidden(2), "")
        self.assertFalse(self.scr.fmt_buttons["visual"]._active)
        self.scr.set_visual(True)
        self.assertEqual(self.hidden(2), "******")

    def test_typing_on_other_line_rehides(self):
        self.t.mark_set("insert", "2.end")
        self.scr.reveal_cursor_line()
        self.t.insert("insert", " ещё")
        self.scr.highlight(2, 2)
        self.assertEqual(self.hidden(2), "")
        self.t.mark_set("insert", "3.end")
        self.scr.reveal_cursor_line()
        self.assertEqual(self.hidden(2), "******")

    def test_find_reaches_hidden_markers_and_reveals(self):
        self.scr.find_var.set("**жир")
        self.assertTrue(self.scr.find_next())
        self.assertEqual(self.t.index("insert"), "2.0")
        self.assertEqual(self.hidden(2), "")


if __name__ == "__main__":
    unittest.main()
