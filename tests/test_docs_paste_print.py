"""Документы: вставка с оформлением (HTML → Markdown) и печать Ctrl+P."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import clip_html, docs, pilots


class TestHtmlToMarkdown(unittest.TestCase):
    def test_inline_and_blocks(self):
        md = clip_html.to_markdown(
            '<h1>Заголовок</h1><p>Текст <b>жирный</b>, <em>курсив</em>, <u>подчёркнутый</u>, '
            '<a href="https://x.org">ссылка</a>, <code>код</code>.</p>'
            '<h3>Мелкий</h3><ul><li>один</li><li>два</li></ul><ol><li>а</li><li>б</li></ol>'
            '<blockquote>цитата</blockquote><script>alert(1)</script><style>p{}</style>')
        self.assertEqual(md.split("\n"), [
            "# Заголовок", "",
            "Текст **жирный**, *курсив*, <u>подчёркнутый</u>, [ссылка](https://x.org), `код`.", "",
            "## Мелкий", "", "- один", "- два", "", "1. а", "2. б", "", "> цитата"])

    def test_word_spans_and_tables(self):
        md = clip_html.to_markdown(
            '<p><span style="font-weight: bold">Ж</span> <span style="font-style:italic">К</span> '
            '<span style="text-decoration: underline">П</span></p>'
            '<table><tr><th>Имя</th><th>Кол-во</th></tr><tr><td>яблоки</td><td>3</td></tr></table>')
        self.assertIn("**Ж** *К* <u>П</u>", md)
        self.assertIn("| Имя | Кол-во |\n|---|---|\n| яблоки | 3 |", md)

    def test_whitespace_and_empty_tags(self):
        self.assertEqual(clip_html.to_markdown("<p>a<b></b>  b\n c <b>d </b>e</p>"), "a b c **d** e")
        self.assertEqual(clip_html.to_markdown("строка<br>вторая"), "строка\nвторая")
        self.assertEqual(clip_html.to_markdown('<a name="x">якорь</a>'), "якорь")

    def test_cf_html(self):
        frag = "<b>Привет</b>"
        head = "Version:0.9\r\nStartHTML:{a:010d}\r\nEndHTML:{b:010d}\r\nStartFragment:{c:010d}\r\nEndFragment:{d:010d}\r\n"
        pre = "<html><body><!--StartFragment-->"
        dummy = head.format(a=0, b=0, c=0, d=0)
        start = len(dummy.encode()) + len(pre.encode())
        end = start + len(frag.encode())
        raw = (head.format(a=len(dummy.encode()), b=end + 30, c=start, d=end) + pre + frag
               + "<!--EndFragment--></body></html>").encode() + b"\0"
        self.assertEqual(clip_html.cf_html_fragment(raw), frag)
        self.assertEqual(clip_html.cf_html_fragment("x<!--StartFragment--><i>a</i><!--EndFragment-->"), "<i>a</i>")

    def test_unix_sources(self):
        def run(cmd, **kw):
            out = b"TARGETS\ntext/html\nUTF8_STRING\n" if "TARGETS" in cmd else b"<b>x</b>"
            return mock.Mock(returncode=0, stdout=out)
        with mock.patch.object(clip_html.sys, "platform", "linux"), \
                mock.patch.dict(os.environ, {"DISPLAY": ":0", "WAYLAND_DISPLAY": ""}), \
                mock.patch.object(clip_html.shutil, "which", side_effect=lambda n: "/usr/bin/" + n if n == "xclip" else None), \
                mock.patch.object(clip_html.subprocess, "run", side_effect=run):
            self.assertEqual(clip_html.clipboard_markdown(), "**x**")

    def test_no_tools_no_html(self):
        with mock.patch.object(clip_html.sys, "platform", "linux"), \
                mock.patch.object(clip_html.shutil, "which", return_value=None):
            self.assertIsNone(clip_html.clipboard_html())
        with mock.patch.object(clip_html.sys, "platform", "linux"), \
                mock.patch.dict(os.environ, {"DISPLAY": ":0", "WAYLAND_DISPLAY": ""}), \
                mock.patch.object(clip_html.shutil, "which", return_value="/usr/bin/xclip"), \
                mock.patch.object(clip_html.subprocess, "run", side_effect=OSError("boom")):
            self.assertIsNone(clip_html.clipboard_html())


class TestScreen(unittest.TestCase):
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

    def tearDown(self):
        self.root.destroy()
        self._env.stop()
        self._tmp.cleanup()

    def test_rich_paste_and_undo(self):
        t = self.scr.text
        t.insert("1.0", "до ")
        t.edit_separator()
        self.root.clipboard_clear()
        self.root.clipboard_append("Жирный и список")
        with mock.patch("stamina.docs_screen.compose.clipboard_image", return_value=None), \
                mock.patch.object(clip_html, "clipboard_html", return_value="<b>Жирный</b><ul><li>пункт</li></ul>"):
            self.assertEqual(self.scr._on_paste(), "break")
        self.assertEqual(t.get("1.0", "end-1c"), "до **Жирный**\n\n- пункт")
        self.assertIn("md_b", t.tag_names("1.6"))
        t.edit_undo()
        self.assertEqual(t.get("1.0", "end-1c"), "до ")

    def test_plain_paste_when_no_markup(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("просто")
        with mock.patch("stamina.docs_screen.compose.clipboard_image", return_value=None), \
                mock.patch.object(clip_html, "clipboard_html", return_value="<span>просто</span>"):
            self.assertIsNone(self.scr._on_paste())             # стандартная вставка Tk

    def test_ctrl_shift_v_plain(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("**как есть**")
        t = self.scr.text
        t.insert("1.0", "старое")
        t.tag_add("sel", "1.0", "end-1c")
        self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="V", state=0x5))
        self.assertEqual(t.get("1.0", "end-1c"), "**как есть**")

    def test_print_pdf_in_temp(self):
        self.scr.title_var.set("Печать")
        self.scr.text.insert("1.0", "строка")
        with mock.patch.object(docs, "pdf_available", return_value=True), \
                mock.patch.object(docs, "export_pdf", side_effect=lambda d, p: (Path(p).write_bytes(b"%PDF"), Path(p))[1]), \
                mock.patch("stamina.docs_screen.shots.open_file", return_value=True) as op:
            self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="p", state=0x4))
        p = Path(op.call_args[0][0])
        self.assertEqual(p.parent, docs.docs_dir() / docs.TMP_DIR / "print")
        self.assertEqual(p.suffix, ".pdf")

    def test_print_html_fallback(self):
        self.scr.text.insert("1.0", "строка")
        with mock.patch.object(docs, "pdf_available", return_value=False), \
                mock.patch("webbrowser.open", return_value=True) as op:
            self.scr.print_doc()
        uri = op.call_args[0][0]
        self.assertTrue(uri.startswith("file:") and uri.endswith(".html"))

    def test_ctrl_shift_p_left_to_cockpit(self):
        with mock.patch.object(self.scr, "print_doc") as pd:
            self.assertIsNone(self.scr._on_ctrl_key(mock.Mock(keycode=0, keysym="P", state=0x5)))
        pd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
