"""Пульт набора: многострочность, прокрутка, Enter/Shift+Enter, приём подсказок."""

from __future__ import annotations

import time
import tkinter as tk
import unittest
from types import SimpleNamespace

from stamina.prompt_box import PromptBox
from stamina.suggest import dictionary_from, Suggester

COLORS = {"bg": "#101418", "fg": "#E6E6E6", "line": "#223040", "hint": "#8899AA"}


class PromptBoxTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        self.sent = []
        self.drafts = []
        self.d = dictionary_from(["проверь тесты", "проверь тесты и покажи отчёт",
                                  "проверка связи", "проверить отчёт", "привет корабль"])
        self.box = PromptBox(self.root, on_send=lambda: self.sent.append(self.box.get()),
                             colors=COLORS, suggester=Suggester(self.d),
                             on_draft=self.drafts.append, draft_delay=0.01)
        self.box.pack()
        self.root.update()

    def tearDown(self):
        self.box.destroy()
        self.root.destroy()

    def _event(self, sequence, **kw):
        """Событие клавиши: как придёт от Tk (state — модификаторы)."""
        return SimpleNamespace(state=kw.get("state", 0), keysym=sequence, widget=self.box.text)

    def _key(self, sequence, **kw):
        """Нажать клавишу в пульте (скрытое окно без фокуса события не получает)."""
        event = self._event(sequence, **kw)
        if sequence in ("<Return>", "<KP_Enter>"):
            return self.box._on_return(event)
        if sequence == "<Tab>":
            return self.box._on_tab(event)
        raise AssertionError(sequence)

    def _type(self, text):
        self.box.text.insert(tk.INSERT, text)
        self.box._after_change()
        self.root.update()

    # -- базовое поле ------------------------------------------------------
    def test_three_rows_by_default(self):
        self.assertEqual(int(self.box.text.cget("height")), 3)

    def test_wraps_words(self):
        self.assertEqual(self.box.text.cget("wrap"), "word")

    def test_has_scrollbar(self):
        self.assertTrue(self.box.bar.winfo_exists())

    def test_grows_with_text(self):
        self._type("раз\nдва\nтри\nчетыре")
        self.assertGreaterEqual(int(self.box.text.cget("height")), 5)

    def test_growth_is_capped(self):
        self._type("\n".join(f"строка {i}" for i in range(40)))
        self.assertLessEqual(int(self.box.text.cget("height")), 8)

    def test_shrinks_back(self):
        self._type("\n".join(f"строка {i}" for i in range(20)))
        self.box.clear()
        self.root.update()
        self.assertEqual(int(self.box.text.cget("height")), 3)

    def test_scrollbar_hidden_when_text_fits(self):
        self.root.update()
        self.assertFalse(self.box.bar.winfo_ismapped())

    # -- содержимое --------------------------------------------------------
    def test_get_set_clear(self):
        self.box.set("привет")
        self.assertEqual(self.box.get(), "привет")
        self.box._drop_ghost()                 # призрак виден в виджете, но не в тексте
        self.assertEqual(self.box.get(), self.box.text.get("1.0", "end-1c"))
        self.box.clear()
        self.assertEqual(self.box.get(), "")

    def test_set_replaces_old_text(self):
        self.box.set("первый")
        self.box.set("второй")
        self.assertEqual(self.box.get(), "второй")

    def test_insert_text_appends_with_space(self):
        self.box.set("набрал")
        self.box.insert_text("голосом")
        self.assertEqual(self.box.get(), "набрал голосом")

    def test_insert_text_empty_is_noop(self):
        self.box.set("набрал")
        self.box.insert_text("")
        self.assertEqual(self.box.get(), "набрал")

    def test_cursor_visible_after_insert(self):
        self.box.set("строка")
        self.box.insert_text("ещё")
        self.root.update()
        self.assertEqual(self.box.text.index(tk.INSERT), self.box.text.index("end-1c"))

    # -- призрак в строке (как в Cursor) ------------------------------------
    def test_ghost_appears_after_typing(self):
        self._type("прив")
        self.assertEqual(self.box.ghost(), "ет")

    def test_ghost_is_drawn_in_widget(self):
        self._type("прив")
        self.assertIn("привет", self.box.text.get("1.0", "end-1c"))

    def test_get_excludes_ghost(self):
        self._type("прив")
        self.assertEqual(self.box.get(), "прив")

    def test_ghost_sits_after_cursor(self):
        self._type("прив")
        self.assertEqual(self.box.text.index(tk.INSERT), "1.4")
        spans = tuple(str(x) for x in self.box.text.tag_ranges("ghost"))
        self.assertEqual(spans, ("1.4", "1.6"))

    def test_ghost_is_phrase_when_word_complete(self):
        self._type("проверь")
        self.assertEqual(self.box.ghost(), " тесты")

    def test_typed_letter_does_not_land_inside_ghost(self):
        self._type("прив")
        self.box._on_keypress()
        self.box.text.insert(tk.INSERT, "е")
        self.box._after_change()
        self.assertIn(self.box.get(), ("приве", "привет"))

    def test_tab_materializes_ghost(self):
        self._type("прив")
        self.assertTrue(self.box.accept_hint())
        self.assertEqual(self.box.get(), "привет")
        self.assertEqual(self.box.ghost(), "")

    def test_ghost_not_in_sent_text(self):
        self._type("прив")
        self._key("<Return>")
        self.assertEqual(self.sent, ["прив"])

    def test_escape_removes_ghost(self):
        self._type("прив")
        self.box._on_escape()
        self.assertEqual(self.box.ghost(), "")
        self.assertEqual(self.box.get(), "прив")

    def test_no_ghost_without_hints(self):
        self._type("щщщ")
        self.assertEqual(self.box.ghost(), "")

    def test_ghost_gone_after_clear(self):
        self._type("прив")
        self.box.clear()
        self.assertEqual(self.box.ghost(), "")
        self.assertEqual(self.box.text.get("1.0", "end-1c"), "")

    def test_ghost_gone_when_disabled(self):
        self._type("прив")
        self.box.set_enabled(False)
        self.assertEqual(self.box.ghost(), "")

    def test_paste_replaces_ghost(self):
        self._type("прив")
        self.box.paste("!")
        self.assertEqual(self.box.get(), "прив!")

    def test_voice_text_keeps_ghost_out(self):
        self._type("прив")
        self.box.insert_text("корабль")
        self.assertEqual(self.box.text.get("1.0", "end-1c"), self.box.get())

    # -- отправка ----------------------------------------------------------
    def test_return_is_bound(self):
        self.assertTrue(self.box.text.bind("<Return>"))
        self.assertTrue(self.box.text.bind("<KP_Enter>"))
        self.assertTrue(self.box.text.bind("<Tab>"))

    def test_enter_sends(self):
        self.box.set("готово")
        self.assertEqual(self._key("<Return>"), "break")
        self.assertEqual(self.sent, ["готово"])

    def test_shift_enter_makes_newline(self):
        self.box.set("первая")
        self._key("<Return>", state=0x0001)
        self.assertEqual(self.sent, [])
        self.assertIn("\n", self.box.get())

    def test_kp_enter_sends(self):
        self.box.set("число")
        self._key("<KP_Enter>")
        self.assertEqual(self.sent, ["число"])

    def test_multiline_text_is_sent_whole(self):
        self.box.set("первая\nвторая")
        self._key("<Return>")
        self.assertEqual(self.sent, ["первая\nвторая"])

    # -- подсказки ---------------------------------------------------------
    def test_tab_accepts_word_tail(self):
        self._type("прив")
        self.assertTrue(self.box.accept_hint())
        self.assertEqual(self.box.get(), "привет")

    def test_tab_without_hints_non_break(self):
        self._type("щщщ")
        self.assertFalse(self.box.accept_hint())

    def test_tab_break_only_when_hint_taken(self):
        self._type("прив")
        self.assertEqual(self.box._on_tab(), "break")
        self.box.clear()
        self._type("щщщ")
        self.assertIsNone(self.box._on_tab())

    def test_hint_line_is_shown(self):
        self._type("прив")
        self.assertIn("Tab:", self.box.hint.cget("text"))

    def test_phrase_hint_continues_text(self):
        self._type("проверь")
        self.assertTrue(self.box.accept_hint())
        self.assertTrue(self.box.get().startswith("проверь "))

    def test_second_tab_gives_next_variant(self):
        self._type("пров")
        self.box.accept_hint()
        first = self.box.get()
        self.box.accept_hint()
        second = self.box.get()
        self.assertNotEqual(second, first)
        self.assertIn(second, ("проверь", "проверка", "проверить"))
        self.box.accept_hint()
        self.assertNotEqual(self.box.get(), second)

    def test_cycle_never_glues_tails(self):
        self._type("пров")
        for _ in range(5):
            self.box.accept_hint()
        self.assertIn(self.box.get(), ("проверь", "проверка", "проверить"))

    def test_escape_refuses_hint(self):
        self._type("прив")
        self.assertEqual(self.box._on_escape(), "break")
        self.assertEqual(self.box.hint.cget("text"), "")

    def test_typing_after_accept_recomputes(self):
        self._type("прив")
        self.box.accept_hint()
        self.assertEqual(self.box.get(), "привет")
        self._type("X")
        self.assertIsNone(self.box._cycle)

    def test_no_suggester_no_hints(self):
        self.box.set_suggester(None)
        self._type("прив")
        self.assertEqual(self.box.hints(), [])
        self.assertEqual(self.box.hint.cget("text"), "")

    def test_hints_cleared_when_word_finished(self):
        self._type("привет ")
        self.assertEqual(self.box.hints(), [])

    # -- черновик ----------------------------------------------------------
    def test_draft_is_reported(self):
        self._type("пишу")
        deadline = time.time() + 1.0
        while not self.drafts and time.time() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.drafts[-1], "пишу")

    def test_draft_is_stripped(self):
        self._type("  пишу  ")
        self.assertEqual(self.box.draft(), "пишу")

    def test_no_draft_for_empty_text(self):
        self._type("пишу")
        self.box.clear()
        deadline = time.time() + 0.3
        while time.time() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertNotIn("", self.drafts)

    # -- включение/выключение ----------------------------------------------
    def test_disable_blocks_hints_and_get(self):
        self.box.set("текст")
        self.box.set_enabled(False)
        self.assertEqual(self.box.state(), "disabled")
        self.assertEqual(self.box.hints(), [])

    def test_enable_again(self):
        self.box.set_enabled(False)
        self.box.set_enabled(True)
        self.assertEqual(self.box.state(), "normal")

    def test_apostrophe_and_dash_are_part_of_word(self):
        self._type("что-то")
        self.assertEqual(self.box.get().split()[0], "что-то")


if __name__ == "__main__":
    unittest.main()
