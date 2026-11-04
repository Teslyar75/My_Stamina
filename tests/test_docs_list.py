"""Документы: поиск и порядок списка, строка состояния, Ctrl+S, нумерованный список."""
import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import docs, pilots


class _Root(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"STAMINA_PILOT_DIR": ""})
        self._env.start()
        os.environ.pop("STAMINA_PILOT_DIR", None)
        pilots.reset_root(Path(self._tmp.name))

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class TestModel(_Root):
    def _mk(self, title, text, created):
        d = docs.Document(title, [{"t": text}], created=created)
        docs.save(d)
        return d

    def test_filter_and_sort(self):
        self._mk("Бета", "про котов", 100)
        self._mk("альфа", "про собак и котов", 300)
        self._mk("Гамма", "ничего", 200)
        items = docs.list_docs()
        self.assertEqual([d["title"] for d in docs.sort_items(items, "title")], ["альфа", "Бета", "Гамма"])
        self.assertEqual([d["title"] for d in docs.sort_items(items, "created")], ["альфа", "Гамма", "Бета"])
        self.assertEqual({d["title"] for d in docs.filter_items(items, "КОТОВ")}, {"альфа", "Бета"})
        self.assertEqual([d["title"] for d in docs.filter_items(items, "котов собак")], ["альфа"])
        self.assertEqual([d["title"] for d in docs.filter_items(items, "гамм")], ["Гамма"])
        self.assertEqual(len(docs.filter_items(items, "  ")), 3)


class TestScreen(_Root):
    def setUp(self):
        super().setUp()
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        from stamina.docs_screen import DocsScreen
        self.scr = DocsScreen(self.root, mock.Mock(store=None))
        self.scr.new_doc()

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def _add(self, title, text=""):
        self.scr.new_doc()
        self.scr.title_var.set(title)
        self.scr.text.insert("1.0", text)
        self.scr.save_now()

    def test_one_line_per_doc_and_search(self):
        self._add("Отчёт", "квартальные цифры")
        self._add("Письмо", "привет")
        self.scr.refresh()
        self.assertEqual(self.scr.listbox.size(), 2)
        self.assertIn("Письмо", self.scr.listbox.get(0))
        self.scr.search_var.set("цифры")
        self.assertEqual(self.scr.listbox.size(), 1)
        self.assertIn("Отчёт", self.scr.listbox.get(0))
        self.scr.listbox.selection_set(0)
        self.scr._on_pick()
        self.assertEqual(self.scr.title_var.get(), "Отчёт")
        self.scr.search_var.set("нет-такого")
        self.assertEqual(self.scr.listbox.size(), 0)
        self.assertTrue(self.scr.empty_hint.winfo_manager())

    def test_sort_title(self):
        self._add("Б")
        self._add("А")
        self._add("В")
        self.scr.set_sort("title")
        self.assertEqual([self.scr.listbox.get(i).split("·")[0].strip() for i in range(3)], ["А", "Б", "В"])
        self.scr.refresh()
        self.assertEqual(self.scr._sort_key(), "title")

    def test_sort_saved_in_settings(self):
        st = {}
        self.scr.app = mock.Mock(store=mock.Mock(settings=st))
        self.scr.set_sort("created")
        self.assertEqual(st["docs_sort"], "created")
        self.scr.app.store.save_settings.assert_called()

    def test_status_counts_and_selection(self):
        t = self.scr.text
        t.insert("1.0", "раз два\nтри")
        self.scr._update_status()
        self.assertIn("3", self.scr.status.cget("text"))
        self.assertIn("10", self.scr.status.cget("text"))            # 11 символов без \n = 10
        t.tag_add("sel", "1.0", "1.3")
        self.scr._update_status()
        txt = self.scr.status.cget("text")
        self.assertIn("1", txt)
        self.assertIn("3", txt)

    def test_saved_hh_mm_and_ctrl_s(self):
        self.scr.title_var.set("x")
        self.scr.save_manual()
        self.assertTrue(Path(self.scr.doc.path).exists())
        self.assertIn(time.strftime("%H:%M"), self.scr.status.cget("text"))
        self.scr._update_status()
        txt = self.scr.status.cget("text")
        self.assertIn(time.strftime("%H:%M"), txt)
        self.assertNotRegex(txt, r"\d\d:\d\d:\d\d")

    def test_ctrl_keys(self):
        ev = mock.Mock(keycode=0, keysym="s", state=0x4)
        with mock.patch.object(self.scr, "save_manual") as sm:
            self.assertEqual(self.scr._on_ctrl_key(ev), "break")
        sm.assert_called_once()
        t = self.scr.text
        t.insert("1.0", "а\nб")
        t.tag_add("sel", "1.0", "2.1")
        self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="ampersand", state=0x5))
        self.assertEqual(t.get("1.0", "end-1c"), "1. а\n2. б")
        t.tag_add("sel", "1.0", "2.end")
        self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="ampersand", state=0x5))
        self.assertEqual(t.get("1.0", "end-1c"), "а\nб")
        t.tag_add("sel", "1.0", "2.end")
        self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="asterisk", state=0x5))
        self.assertEqual(t.get("1.0", "end-1c"), "- а\n- б")
        t.edit_undo()
        self.assertEqual(t.get("1.0", "end-1c"), "а\nб")

    def test_format_button_is_one_undo_step(self):
        t = self.scr.text
        t.insert("1.0", "слово")
        t.edit_separator()
        t.tag_add("sel", "1.0", "1.5")
        self.scr.do_action("b")
        self.assertEqual(t.get("1.0", "end-1c"), "**слово**")
        t.edit_undo()
        self.assertEqual(t.get("1.0", "end-1c"), "слово")

    def test_windows_vk(self):
        from stamina import docs_format
        with mock.patch.object(docs_format, "WIN", True), mock.patch.object(self.scr, "toggle_numbered") as tn:
            self.scr._on_ctrl_key(mock.Mock(keycode=55, keysym="7", state=0x5))
        tn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
