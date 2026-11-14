"""Живая линия Ориона: ответ можно выделить и скопировать (код, команды).

Проверяем без всего экрана: методы `_strip_*` берут только виджет и буфер.
"""
import tkinter as tk
import unittest

from stamina.orion_screen import OrionScreen


class StripCopyTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        self.box: list[str] = []
        self.screen = object.__new__(OrionScreen)
        self.screen.strip_orion = tk.Text(self.root, wrap=tk.WORD)
        self.screen._hint = lambda *a, **k: None
        self.screen.clipboard_clear = lambda: self.box.clear()
        self.screen.clipboard_append = lambda text: self.box.append(text)
        for name in ("_strip_set", "_strip_copy", "_strip_copy_all"):
            setattr(self.screen, name, getattr(OrionScreen, name).__get__(self.screen))

    def tearDown(self):
        self.root.destroy()

    def test_set_keeps_full_text_and_readonly(self):
        self.screen._strip_set("ОРИОН: cd D:\\My_New_Stamina")
        self.assertEqual(self.screen.strip_orion.get("1.0", "end-1c"),
                         "ОРИОН: cd D:\\My_New_Stamina")
        self.assertEqual(str(self.screen.strip_orion.cget("state")), "disabled")

    def test_copy_selection(self):
        self.screen._strip_set("код: pip install argostranslate")
        start = self.screen.strip_orion.search("pip", "1.0")
        end = self.screen.strip_orion.search(" argos", start)
        self.screen.strip_orion.tag_add(tk.SEL, start, end)
        self.screen._strip_copy()
        self.assertEqual(self.box, ["pip install"])

    def test_copy_whole_answer(self):
        text = "ОРИОН: первая строка\nвторая строка кода"
        self.screen._strip_set(text)
        self.screen._strip_copy_all()
        self.assertEqual(self.box, [text])

    def test_copy_without_selection_does_nothing(self):
        self.screen._strip_set("просто ответ")
        self.screen._strip_copy()
        self.assertEqual(self.box, [])


if __name__ == "__main__":
    unittest.main()
