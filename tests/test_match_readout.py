"""Итог проверки речи: длинная заметка не должна обрезаться снизу.

Жалоба пилота (30.10): под шкалой «СОВПАДЕНИЕ: 12%» видны половинки букв —
список пропущенных слов переносился на вторую строку, а высота панели была
фиксированной (86 px).
"""
import tkinter as tk
import unittest

from stamina.english.ui import MatchReadout

MARKS_LONG = [("we", False), ("have", False), ("all", False), ("the", True),
              ("time", False), ("in", False), ("world", False)]


class MatchReadoutFitTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        # узкая панель: длинная заметка переносится при любом шрифте (в т.ч. X11 без Xft)
        self.root.geometry("360x700+40+40")
        self.host = tk.Frame(self.root, width=360)
        self.host.pack(fill=tk.X)
        self.mr = MatchReadout(self.host, height=86)
        self.mr.pack(fill=tk.X)
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _text_bottom(self) -> int:
        boxes = [self.mr.bbox(i) for i in self.mr.find_all()
                 if self.mr.type(i) == "text"]
        boxes = [b for b in boxes if b]
        return max((b[3] for b in boxes), default=0)

    def test_long_note_grows_and_fits(self):
        self.mr.set(12, marks=MARKS_LONG, heard="the", target_missed=True)
        self.root.update()
        self.assertGreater(self.mr.winfo_reqheight(), 86)          # панель выросла
        self.assertLessEqual(self._text_bottom(), self.mr.winfo_height())  # и текст внутри

    def test_short_note_keeps_base_height(self):
        self.mr.set(95, marks=[("time", True)], heard="time")
        self.root.update()
        self.assertEqual(self.mr.winfo_reqheight(), 86)

    def test_clear_returns_base_height(self):
        self.mr.set(12, marks=MARKS_LONG, heard="the", target_missed=True)
        self.root.update()
        grown = self.mr.winfo_reqheight()
        self.mr.clear()
        self.root.update()
        self.assertGreater(grown, 86)
        self.assertEqual(self.mr.winfo_reqheight(), 86)


class WrapTextTest(unittest.TestCase):
    def test_wraps_by_measured_width(self):
        from stamina.english.ui import wrap_text
        self.assertEqual(wrap_text("aa bb cc", len, 5), ["aa bb", "cc"])
        self.assertEqual(wrap_text("short", len, 50), ["short"])
        self.assertEqual(wrap_text("verylongword x", len, 4), ["verylongword", "x"])


if __name__ == "__main__":
    unittest.main()
