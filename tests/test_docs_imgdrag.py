"""Документы: размер картинки перетаскиванием угла."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from stamina import pilots

try:
    from PIL import Image
except Exception:  # noqa: BLE001
    Image = None


@unittest.skipIf(Image is None, "нет Pillow")
class TestImageDrag(unittest.TestCase):
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
        self.root.geometry("900x700")
        from stamina.docs_screen import DocsScreen
        self.scr = DocsScreen(self.root, mock.Mock(store=None))
        self.scr.pack(fill=tk.BOTH, expand=True)
        self.scr.new_doc()
        self.scr.insert_image(Image.new("RGB", (200, 100), "red"))
        self.name = next(iter(self.scr._widths))
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self._env.stop()
        self._tmp.cleanup()

    def _corner(self):
        t = self.scr.text
        for key, _v, idx in t.dump("1.0", "end", image=True):
            if key == "image":
                x, y, w, h = t.bbox(idx)
                return x + w - 3, y + h - 3
        raise AssertionError("нет картинки")

    def test_corner_detected_only_near_corner(self):
        x, y = self._corner()
        self.assertEqual(self.scr.image_corner_at(x, y)[0], self.name)
        self.assertIsNone(self.scr.image_corner_at(x - 60, y - 40))

    def test_drag_resizes_and_one_undo(self):
        old = self.scr._widths[self.name]
        x, y = self._corner()
        ev = lambda dx: mock.Mock(x=x + dx, y=y)  # noqa: E731
        self.assertEqual(self.scr._grip_press(ev(0)), "break")
        self.scr._grip_drag(ev(20))
        self.scr._grip_drag(ev(-80))
        self.scr._grip_release(ev(-80))
        new = self.scr._widths[self.name]
        self.assertLess(new, old)
        self.assertEqual(self.scr.segments()[0]["w"], new)
        self.scr.undo.undo()
        self.assertEqual(self.scr._widths[self.name], old)

    def test_drag_clamped(self):
        x, y = self._corner()
        self.scr._grip_press(mock.Mock(x=x, y=y))
        self.scr._grip_release(mock.Mock(x=x - 5000, y=y))
        self.assertEqual(self.scr._widths[self.name], self.scr.MIN_IMG_W)

    def test_press_elsewhere_passes_through(self):
        self.assertIsNone(self.scr._grip_press(mock.Mock(x=1, y=1)))


if __name__ == "__main__":
    unittest.main()
