"""Markdown в документах: разбор, экспорт .md/.docx, письмо, кнопки и справка редактора."""
import os
import tempfile
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.dom import minidom

from stamina import docs, mailer, mdlite, pilots


class TestMdlite(unittest.TestCase):
    def test_runs(self):
        rs = mdlite.runs("a **b** *c* `x*y*` [t](http://u) <u>z</u> snake_case_x")
        self.assertIn(("b", frozenset({"b"}), ""), rs)
        self.assertIn(("c", frozenset({"i"}), ""), rs)
        self.assertIn(("x*y*", frozenset({"code"}), ""), rs)      # внутри кода разметки нет
        self.assertIn(("t", frozenset({"link"}), "http://u"), rs)
        self.assertIn(("z", frozenset({"u"}), ""), rs)
        self.assertTrue(rs[-1][0].endswith("snake_case_x"))       # _ внутри слова — не курсив

    def test_blocks(self):
        kinds = [k for k, _ in mdlite.paragraphs("# A\n## B\n- c\n1. d\n> e\nf")]
        self.assertEqual(kinds, ["h1", "h2", "li", "li", "quote", "p"])
        self.assertEqual(mdlite.plain("# A\n**b** и *c*"), "A\nb и c")
        self.assertIn("<h1>A</h1>", mdlite.to_html("# A"))


class _Root(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"STAMINA_PILOT_DIR": ""})
        self._env.start()
        os.environ.pop("STAMINA_PILOT_DIR", None)
        pilots.reset_root(Path(self._tmp.name))
        self.out = Path(self._tmp.name)

    def tearDown(self):
        pilots.reset_root()
        self._env.stop()
        self._tmp.cleanup()


class TestExports(_Root):
    def _doc(self):
        d = docs.Document("Тест", [{"t": "# Глава\n**жирный** и *курсив* [сайт](https://x.org)\n- пункт\n> цитата\n"}])
        try:
            import io
            from PIL import Image
            b = io.BytesIO()
            Image.new("RGB", (40, 20), "red").save(b, "PNG")
            d.segments.append({"img": d.add_image(b.getvalue()), "w": 40})
            d.segments.append({"t": "\nконец"})
        except ImportError:
            pass
        return d

    def test_docx_is_valid_ooxml(self):
        p = docs.export_docx(self._doc(), self.out / "a.docx")
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            for n in names:
                if n.endswith((".xml", ".rels")):
                    minidom.parseString(z.read(n))
            xml = z.read("word/document.xml").decode("utf-8")
        self.assertIn("word/document.xml", names)
        self.assertIn('w:val="Heading1"', xml)
        self.assertIn("<w:b/>", xml)
        self.assertIn("жирный", xml)
        self.assertNotIn("**", xml)

    def test_md_roundtrip(self):
        d = self._doc()
        p = docs.export_md(d, self.out / "a.md")
        self.assertTrue(p.read_text(encoding="utf-8").startswith("# Тест\n\n# Глава"))
        back = docs.import_md(p)
        self.assertEqual(back.title, "Тест")
        self.assertIn("**жирный**", back.text)
        self.assertEqual(len(back.images), len(d.images))

    def test_mailto_fallback(self):
        f = self.out / "x.docx"
        f.write_bytes(b"x")
        with mock.patch.dict(os.environ, {"STAR_TYPING_NO_MAPI": "1"}), \
                mock.patch.object(mailer.webbrowser, "open") as op, mock.patch.object(mailer, "reveal") as rv:
            self.assertEqual(mailer.send_file(f, "Тема", "Текст"), "mailto")
        self.assertTrue(op.call_args[0][0].startswith("mailto:?subject="))
        rv.assert_called_once()


class TestEditor(_Root):
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

    def test_bold_toggle_and_highlight(self):
        t = self.scr.text
        t.insert("1.0", "слово")
        t.tag_add("sel", "1.0", "1.5")
        self.scr.do_action("b")
        self.assertEqual(t.get("1.0", "end-1c"), "**слово**")
        self.assertIn("md_b", t.tag_names("1.3"))
        self.assertIn("md_mark", t.tag_names("1.0"))
        self.scr.do_action("b")                                # повторно — снять
        self.assertEqual(t.get("1.0", "end-1c"), "слово")

    def test_heading_list_and_enter(self):
        t = self.scr.text
        t.insert("1.0", "пункт")
        t.mark_set("insert", "1.end")
        self.scr.do_action("li")
        self.assertEqual(t.get("1.0", "end-1c"), "- пункт")
        t.mark_set("insert", "1.end")
        self.scr._on_return()
        self.assertEqual(t.get("1.0", "end-1c"), "- пункт\n- ")
        self.scr.do_action("h1")
        self.assertEqual(t.get("2.0", "2.end"), "# ")

    def test_replace_all(self):
        t = self.scr.text
        t.insert("1.0", "кот и кот")
        self.scr.find_var.set("кот")
        self.scr.repl_var.set("пёс")
        self.assertEqual(self.scr.replace_all(), 2)
        self.assertEqual(t.get("1.0", "end-1c"), "пёс и пёс")

    def test_help_replaces_list_and_keeps_focus(self):
        s = self.scr
        s.pack(fill="both", expand=True)
        self.root.deiconify()
        self.root.update()
        s.toggle_help()
        self.root.update()
        self.assertEqual(s.help_view.winfo_manager(), "pack")
        self.assertEqual(s.list_view.winfo_manager(), "")
        self.assertIn("Ctrl+B", s.help_text.get("1.0", "end"))
        self.assertIn("**", s.help_text.get("1.0", "end"))
        self.assertEqual(s.text.focus_lastfor(), s.text)  # не зависит от фокуса ОС
        s.toggle_help()
        self.root.update()
        self.assertEqual(s.list_view.winfo_manager(), "pack")
        self.assertEqual(s.help_view.winfo_manager(), "")

    def test_ctrl_keys_layout_independent(self):
        t = self.scr.text
        t.insert("1.0", "x")
        t.tag_add("sel", "1.0", "1.1")
        ev = mock.Mock(keycode=73, keysym="Cyrillic_sha", state=0x4)  # Ctrl+I на кириллице
        with mock.patch("stamina.docs_format.WIN", True):
            self.assertEqual(self.scr._on_ctrl_key(ev), "break")
        self.assertEqual(t.get("1.0", "end-1c"), "*x*")
        ev = mock.Mock(keycode=67, keysym="c", state=0x4)              # Ctrl+C — не наше
        with mock.patch("stamina.docs_format.WIN", True):
            self.assertIsNone(self.scr._on_ctrl_key(ev))


if __name__ == "__main__":
    unittest.main()
