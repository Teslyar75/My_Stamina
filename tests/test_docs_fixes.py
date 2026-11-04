"""Документы: исправления — колесо на Linux, список без прыжков, отмена картинок,
логическая ширина снимков (формат 2), временные файлы, окна в стиле темы."""
import io
import json
import os
import tempfile
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from stamina import docs, pilots, theme, wheel_router


def _png(w=300, h=120):
    from PIL import Image
    return Image.new("RGB", (w, h), (200, 40, 40))


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
    def test_legacy_widths_become_logical(self):
        p = docs.docs_dir() / "old.stdoc"
        meta = {"format": 1, "title": "t", "segments": [{"t": "a"}, {"img": "images/1.png", "w": 600}]}
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("document.json", json.dumps(meta))
            z.writestr("images/1.png", b"x")
        with mock.patch.object(theme, "S", 1.5), mock.patch.object(theme, "UI", 1.0):
            d = docs.load(p)
        self.assertEqual(d.segments[1]["w"], 400)
        docs.save(d)
        with zipfile.ZipFile(p) as z:
            self.assertEqual(json.loads(z.read("document.json"))["format"], docs.FORMAT)
        with mock.patch.object(theme, "S", 1.5):
            self.assertEqual(docs.load(p).segments[1]["w"], 400)   # формат 2 — не пересчитываем

    def test_cleanup_temp(self):
        (docs.temp_dir("view") / "a.png").write_bytes(b"x")
        (docs.temp_dir("send") / "b.docx").write_bytes(b"x")
        legacy = docs.docs_dir() / ".view"
        legacy.mkdir()
        (legacy / "c.png").write_bytes(b"x")
        keep = docs.docs_dir() / "doc.stdoc"
        keep.write_bytes(b"x")
        self.assertEqual(docs.cleanup_temp(), 3)
        self.assertFalse((docs.docs_dir() / docs.TMP_DIR).exists())
        self.assertFalse(legacy.exists())
        self.assertTrue(keep.exists())


class _Screen(_Root):
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
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        super().tearDown()


class TestWheel(_Screen):
    def test_bind_scroll_all_sequences(self):
        t = tk.Text(self.root)
        seen = []
        handler = wheel_router.bind_scroll(t, seen.append)
        for seq in wheel_router.WHEEL:
            self.assertTrue(t.bind(seq))
        self.assertEqual(handler(mock.Mock(num=5, delta=0)), "break")
        handler(mock.Mock(num=4, delta=0))
        handler(mock.Mock(num=0, delta=-120))
        self.assertEqual(seen, [1, -1, 1])

    def test_help_view_scrolls_on_x11_buttons(self):
        hv = self.scr.help_view
        texts = [w for w in hv.winfo_children() if isinstance(w, tk.Text)] or \
                [w for f in hv.winfo_children() for w in f.winfo_children() if isinstance(w, tk.Text)]
        self.assertTrue(texts)
        self.assertTrue(texts[0].bind("<Button-4>") and texts[0].bind("<Button-5>"))


class TestUndoImages(_Screen):
    def _images(self):
        return [v for k, v, _i in self.scr.text.dump("1.0", "end", image=True) if k == "image"]

    def test_undo_redo_image_insert_and_delete(self):
        t = self.scr.text
        t.insert("1.0", "до снимка")
        t.edit_separator()
        t.mark_set("insert", "end")
        self.scr.insert_image(_png())
        self.assertEqual(len(self._images()), 1)
        t.edit_undo()
        self.assertEqual(self._images(), [])
        self.assertEqual(t.get("1.0", "end-1c"), "до снимка")       # текст не тронут
        t.edit_redo()
        self.assertEqual(len(self._images()), 1)
        t.delete("1.0", "end")
        self.assertEqual(self._images(), [])
        t.edit_undo()
        self.assertEqual(len(self._images()), 1)
        self.assertTrue(t.get("1.0", "end-1c").startswith("до снимка"))

    def test_resize_is_undoable(self):
        self.scr.insert_image(_png(800, 200))
        name = docs.Document  # noqa: F841
        img = self.scr._img_name(self._images()[0])
        w0 = self.scr._widths[img]
        self.scr._resize(img, 25)
        self.assertNotEqual(self.scr._widths[img], w0)
        self.scr.text.edit_undo()
        self.assertEqual(self.scr._widths[img], w0)
        self.scr.text.edit_redo()
        self.assertEqual(self.scr._widths[img], max(self.scr.MIN_IMG_W, round(self.scr._natural_width(800) / 4)))

    def test_width_is_logical(self):
        with mock.patch.object(theme, "S", 2.0):
            self.scr.insert_image(_png(800, 200))
            img = self.scr._img_name(self._images()[0])
            self.assertEqual(self.scr._widths[img], 400)            # 800 экранных px при 200%
            self.scr.save_now()
            seg = [s for s in docs.load(self.scr.doc.path).segments if "img" in s][0]
            self.assertEqual(seg["w"], 400)

    def test_typing_groups_words(self):
        t = self.scr.text
        for ch in "раз два":
            t.insert("insert", ch)
        t.edit_undo()
        self.assertEqual(t.get("1.0", "end-1c"), "раз")


class TestListAndDialogs(_Screen):
    def test_autosave_keeps_order(self):
        for title in ("первый", "второй", "третий"):
            self.scr.new_doc()
            self.scr.title_var.set(title)
            self.scr.save_now()
        self.scr.refresh()
        order = [it["title"] for it in self.scr._items]
        self.assertEqual(order[0], "третий")
        self.scr._show_doc(docs.load(self.scr._items[2]["path"]))   # «первый»
        self.scr.text.insert("1.0", "правка")
        self.scr.save_now()
        self.assertEqual([it["title"] for it in self.scr._items], order)   # не прыгнул наверх
        self.scr.refresh()
        self.assertEqual(self.scr._items[0]["title"], "первый")          # при входе — свежие сверху

    def test_remove_uses_themed_confirm(self):
        self.scr.title_var.set("удалить")
        self.scr.save_now()
        path = self.scr.doc.path
        with mock.patch("stamina.docs_screen.confirm", return_value=False) as c:
            self.scr._remove()
        c.assert_called_once()
        self.assertTrue(Path(path).exists())
        with mock.patch("stamina.docs_screen.confirm", return_value=True):
            self.scr._remove()
        self.assertFalse(Path(path).exists())

    def test_confirm_dialog_theme(self):
        from stamina.docs_dialogs import ConfirmDialog
        d = ConfirmDialog(self.root, "T", "M", "OK", danger=True)
        self.assertEqual(d.cget("bg"), theme.BG)
        d.ok()
        self.assertTrue(d.result)

    def test_preview_follows_theme(self):
        from stamina.docs_preview import DocPreview
        self.scr.text.insert("1.0", "# Заголовок\n**жирный**")
        self.scr.save_now()
        p = DocPreview(self.root, self.scr.doc, self.scr._widths)
        try:
            self.assertEqual(p.txt.cget("bg"), theme.BG2)
            self.assertEqual(p.txt.cget("fg"), theme.TEXT)
            self.assertTrue(p.txt.bind("<Button-4>"))
            self.assertNotIn("Georgia", str(p.txt.tag_cget("h1", "font")))
        finally:
            p.destroy()

    def test_open_image_uses_temp_dir(self):
        self.scr.insert_image(_png())
        img = [v for k, v, _i in self.scr.text.dump("1.0", "end", image=True) if k == "image"][0]
        with mock.patch("stamina.compose.open_image") as op:
            self.scr._open_image(self.scr._img_name(img))
        p = Path(op.call_args[0][1])
        self.assertEqual(p.parent, docs.docs_dir() / docs.TMP_DIR / "view")
        docs.cleanup_temp()
        self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
