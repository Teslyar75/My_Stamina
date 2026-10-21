"""Стрелки в пульте: история сообщений не должна съедать набранный черновик."""
import tkinter as tk
import unittest

from stamina.prompt_box import PromptBox, hud_colors


class HistoryDraftTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        self.box = PromptBox(self.root, on_send=lambda: None, colors=hud_colors())
        self.box.pack()
        self.box.set_history(["первое сообщение", "второе сообщение"])

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _draft(self, text: str) -> None:
        self.box.clear()
        self.box.text.insert("1.0", text)
        self.box.text.mark_set(tk.INSERT, "1.0")

    def test_draft_returns_after_full_history_round(self):
        self._draft("мой черновик, ещё не отправлен")
        self.assertTrue(self.box._history_step(-1))
        self.assertEqual(self.box.get(), "второе сообщение")
        self.assertTrue(self.box._history_step(-1))
        self.assertEqual(self.box.get(), "первое сообщение")
        self.assertTrue(self.box._history_step(1))
        self.assertEqual(self.box.get(), "второе сообщение")
        self.assertTrue(self.box._history_step(1))
        self.assertEqual(self.box.get(), "мой черновик, ещё не отправлен")
        self.assertFalse(self.box._browsing)

    def test_up_from_empty_field_does_not_stash_garbage(self):
        self.assertTrue(self.box._history_step(-1))
        self.assertEqual(self.box.get(), "второе сообщение")
        self.assertTrue(self.box._history_step(1))
        self.assertEqual(self.box.get(), "")

    def test_typing_drops_history_mode(self):
        self._draft("черновик")
        self.assertTrue(self.box._history_step(-1))
        self.box._on_keypress()
        self.assertFalse(self.box._browsing)
        self.assertFalse(self.box._stashed)
        self.assertEqual(self.box._draft_stash, "")

    def test_up_moves_caret_inside_draft_instead_of_history(self):
        self._draft("длинный черновик в три строки\nвторая строка\nтретья строка")
        self.box.text.mark_set(tk.INSERT, "2.4")
        self.assertFalse(self.box._history_allowed(-1))
        self.assertIsNone(self.box._on_arrow(-1))
        self.assertEqual(self.box.get(), "длинный черновик в три строки\nвторая строка\nтретья строка")

    def test_up_at_end_of_wrapped_line_is_not_history(self):
        self._draft("x" * 300)
        self.box.text.mark_set(tk.INSERT, "1.290")
        self.assertFalse(self.box._history_allowed(-1))

    def test_selection_blocks_history(self):
        self._draft("выделенный черновик")
        self.box.text.tag_add("sel", "1.0", "1.5")
        self.assertFalse(self.box._history_allowed(-1))


if __name__ == "__main__":
    unittest.main()
