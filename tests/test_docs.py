"""Модуль «ДОКУМЕНТЫ»: формат .stdoc, список, экспорт, экран."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import docs, nav, pilots


class _Root(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"STAMINA_PILOT_DIR": ""})
        self._env.start()
        os.environ.pop("STAMINA_PILOT_DIR", None)
        pilots.reset_root(Path(self._tmp.name))

    def tearDown(self):
        pilots.reset_root()
        self._env.stop()
        self._tmp.cleanup()


class TestStdoc(_Root):
    def test_roundtrip_with_image(self):
        d = docs.Document("Отчёт", [{"t": "Привет\n"}])
        name = d.add_image(b"\x89PNG fake")
        d.segments.append({"img": name, "w": 200})
        d.segments.append({"t": "\nконец"})
        p = docs.save(d)
        self.assertEqual(p.suffix, ".stdoc")
        self.assertEqual(p.parent, docs.docs_dir())
        back = docs.load(p)
        self.assertEqual(back.title, "Отчёт")
        self.assertEqual(back.segments, d.segments)
        self.assertEqual(back.images[name], b"\x89PNG fake")
        self.assertFalse(list(p.parent.glob("*.tmp")))

    def test_list_and_trash(self):
        a = docs.save(docs.Document("", [{"t": "первая строка\nвторая"}]))
        lst = docs.list_docs()
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["title"], "первая строка")
        docs.remove_to_trash(a)
        self.assertEqual(docs.list_docs(), [])
        self.assertTrue((a.parent / ".trash" / a.name).is_file())

    def test_export(self):
        d = docs.Document("T<1>", [{"t": "a & b\nc"}])
        out = Path(self._tmp.name)
        self.assertIn("<p>a &amp; b</p>", docs.export_html(d, out / "x.html").read_text(encoding="utf-8"))
        self.assertEqual(docs.export_txt(d, out / "x.txt").read_text(encoding="utf-8"), "T<1>\n\na & b\nc")

    def test_zone_registered(self):
        self.assertIn("docs", nav.ZONE_ORDER)
        from stamina import docs_hook, page_help
        self.assertEqual(docs_hook.KEY, "docs")
        self.assertIn("docs", page_help.PAGES)


class TestDocsScreen(_Root):
    def setUp(self):
        super().setUp()
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def test_type_autosave_reload(self):
        from stamina.docs_screen import DocsScreen
        app = mock.Mock(store=None)
        scr = DocsScreen(self.root, app)
        scr.save_now()
        self.assertEqual(docs.list_docs(), [])           # пустой новый документ не плодим
        scr.new_doc()
        scr.title_var.set("План")
        scr.text.insert("1.0", "строка")
        scr.insert_dictation("сказано")
        scr.save_now()
        lst = docs.list_docs()
        self.assertEqual(len(lst), 1)
        self.assertEqual(docs.load(lst[0]["path"]).text, "строка сказано")
        scr2 = DocsScreen(self.root, app)
        scr2.listbox.selection_set(0)
        scr2._on_pick()
        self.assertEqual(scr2.text.get("1.0", "end-1c"), "строка сказано")
        self.assertEqual(scr2.title_var.get(), "План")


class TestPdf(_Root):
    def test_pdf_cyrillic_and_image(self):
        if not docs.pdf_available() or docs.find_font() is None:
            self.skipTest("нет fpdf2 или шрифта")
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("нет Pillow")
        d = docs.Document("Отчёт", [{"t": "Привет, мир! Héllo\n"}])
        n = d.add_image(docs.image_bytes(Image.new("RGB", (300, 120), "red")))
        d.segments += [{"img": n, "w": 150}, {"t": "\nконец"}]
        out = docs.export_pdf(d, Path(self._tmp.name) / "x.pdf")
        self.assertTrue(out.read_bytes().startswith(b"%PDF"))
