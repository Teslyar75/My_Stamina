"""Документы, группа 6: задачи, маркер, таблицы, оглавление, корзина, версии, шаблоны."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import docs, mdlite, pilots


class TestMdlite(unittest.TestCase):
    def test_task_and_hl(self):
        self.assertIs(mdlite.task_done("- [ ] a"), False)
        self.assertIs(mdlite.task_done("- [x] a"), True)
        self.assertIsNone(mdlite.task_done("- a"))
        h = mdlite.to_html("- [x] готово\n- [ ] нет\n\n==важно==")
        self.assertIn('class="tasks"', h)
        self.assertIn("<mark>важно</mark>", h)

    def test_table_and_toc(self):
        h = mdlite.to_html("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<table", h)
        self.assertIn("<td>2</td>", h)
        self.assertEqual(mdlite.table_cells("| a | b |"), ["a", "b"])
        text = "# A\n## B\n## C\nx"
        self.assertEqual([h[2] for h in mdlite.headings(text)], ["A", "B", "C"])
        self.assertIn("<nav", mdlite.to_html(text, toc=True))
        self.assertNotIn("<nav", mdlite.to_html("# A\nx", toc=True))


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"STAMINA_PILOT_DIR": ""})
        self._env.start()
        os.environ.pop("STAMINA_PILOT_DIR", None)
        pilots.reset_root(Path(self._tmp.name))

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class TestTrashVersions(_Base):
    def test_trash_roundtrip_unique_names(self):
        a = docs.Document("Тот же", [{"t": "1"}])
        docs.save(a)
        pa = Path(a.path)
        t1 = docs.remove_to_trash(pa)
        b = docs.Document("Тот же", [{"t": "2"}])
        docs.save(b)
        pb = Path(b.path)
        t2 = docs.remove_to_trash(pb)
        self.assertNotEqual(t1, t2)
        self.assertEqual(len(docs.list_trash()), 2)
        back = docs.restore_from_trash(t1)
        self.assertTrue(back.exists())
        docs.purge(t2)
        self.assertEqual(docs.list_trash(), [])
        with self.assertRaises(ValueError):
            docs.purge(back)

    def test_versions_throttled_and_kept(self):
        d = docs.Document("V", [{"t": "один"}])
        docs.save(d)
        path = Path(d.path)
        self.assertIsNotNone(docs.snapshot(path, force=True))
        self.assertIsNone(docs.snapshot(path))            # раньше 10 минут — без снимка
        for _ in range(docs.VERSION_KEEP + 3):
            docs.snapshot(path, force=True)
        vs = docs.list_versions(path)
        self.assertEqual(len(vs), docs.VERSION_KEEP)
        self.assertGreaterEqual(vs[0]["when"], vs[-1]["when"])


class TestScreen(_Base):
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
        self.t = self.scr.text

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def test_toggle_task_one_undo(self):
        self.t.insert("1.0", "- [ ] купить")
        self.assertTrue(self.scr.toggle_task_at(1))
        self.assertEqual(self.t.get("1.0", "1.end"), "- [x] купить")
        self.t.edit_undo()
        self.assertEqual(self.t.get("1.0", "1.end"), "- [ ] купить")
        self.t.insert("2.0", "\nобычная")
        self.assertFalse(self.scr.toggle_task_at(2))

    def test_insert_table(self):
        self.t.insert("1.0", "текст")
        self.t.mark_set("insert", "1.2")
        self.scr.insert_table()
        lines = self.t.get("1.0", "end-1c").split("\n")
        self.assertEqual(lines[0], "текст")
        self.assertTrue(mdlite.TABLE_ROW.match(lines[1]))
        self.assertTrue(mdlite.TABLE_SEP.match(lines[2]))

    def test_goto_heading(self):
        self.t.insert("1.0", "# A\nx\n## B\ny")
        self.scr.goto_line(3)
        self.assertEqual(self.t.index("insert"), "3.0")

    def test_compact_moves_rare_buttons(self):
        from stamina.docs_format import COMPACT_HIDE
        self.scr.set_compact(True)
        self.assertTrue(self.scr.fmt_more._flow_shown)
        self.assertTrue(all(not self.scr.fmt_buttons[a]._flow_shown for a in COMPACT_HIDE))
        self.scr.set_compact(False)
        self.assertFalse(self.scr.fmt_more._flow_shown)

    def test_template(self):
        from stamina import docs_templates
        for tid, *_ in docs_templates.templates():
            self.scr.new_from_template(tid)
            self.assertTrue(self.t.get("1.0", "end-1c").strip())

    def test_trash_dialog_restore(self):
        d = docs.Document("Корз", [{"t": "abc"}])
        docs.save(d)
        tp = docs.remove_to_trash(d.path)
        with mock.patch("stamina.docs_dialogs.pick", return_value=("restore", tp)):
            self.scr.trash_dialog()
        self.assertEqual(self.scr.doc.title, "Корз")
        self.assertEqual(docs.list_trash(), [])

    def test_restore_version(self):
        self.scr.title_entry.insert(0, "Вер")
        self.t.insert("1.0", "старый")
        self.scr.save_now()
        path = Path(self.scr.doc.path)
        docs.snapshot(path, force=True)
        self.t.delete("1.0", "end")
        self.t.insert("1.0", "новый")
        self.scr.save_now()
        old = docs.load(docs.list_versions(path)[-1]["path"])
        self.scr.restore_version(old)
        self.assertIn("старый", self.scr.doc.text)
        self.assertTrue(any("новый" in docs.load(v["path"]).text for v in docs.list_versions(path)))
