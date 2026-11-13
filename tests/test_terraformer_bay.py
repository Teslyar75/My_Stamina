"""Отсек «ТЕРРАФОРМЕР»: каталог, замки CEFR, сохранение выбора и жизненный цикл."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from stamina import pilots, theme
from stamina.english.progress import Progress
from stamina.terraformer_bay import (
    KEY,
    LINES,
    TerraformerBayScreen,
    need_hint,
    robot_need,
    robot_open,
    save_choice,
    saved_choice,
)
from stamina.terraformer_models import robot


class TerraformerRulesTest(unittest.TestCase):
    """Без Tk: временный Progress и временный корень пилотов."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        pilots.reset_root(self.root)
        self.pilot = pilots.create("Tester")
        pilots.activate(self.pilot["id"])
        self.progress = Progress(self.root / "english.json")

    def tearDown(self) -> None:
        pilots.reset_root()
        self.tmp.cleanup()

    def test_catalog_has_two_lines(self) -> None:
        self.assertEqual(len(LINES["cefr"]), 8)
        self.assertEqual(len(LINES["freq"]), 4)
        self.assertEqual([robot(r).name for r in LINES["cefr"]],
                         ["A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"])
        self.assertEqual([robot(r).name for r in LINES["freq"]],
                         ["S-1000", "S-3000", "S-10K", "S-20K"])

    def test_fresh_pilot_opens_a1_only(self) -> None:
        self.assertTrue(robot_open(self.progress, "a1"))
        self.assertFalse(robot_open(self.progress, "a2"))
        # частотная лестница: открыт только первый набор, дальше — по прохождению
        self.assertTrue(robot_open(self.progress, "s1000"))
        for rid in LINES["freq"][1:]:
            self.assertFalse(robot_open(self.progress, rid), rid)

    def test_locked_hint_has_previous_level_and_threshold(self) -> None:
        prev, pct, now = robot_need(self.progress, "a2")
        self.assertEqual(prev, "A1")
        self.assertGreater(pct, 0)
        self.assertEqual(now, 0)
        hint = need_hint(self.progress, "a2")
        self.assertIn("A1", hint)
        self.assertIn(f"{pct}%", hint)
        self.assertIn("0%", hint)

    def test_captain_sees_everything(self) -> None:
        from stamina import roles
        roles._FORCE_FILE_STORE = True
        roles.write_access_cache(self.pilot["id"], ok=True, login="dev")
        pilots.activate(self.pilot["id"])
        for rid in LINES["cefr"] + LINES["freq"]:
            self.assertTrue(robot_open(self.progress, rid), rid)
        self.assertEqual(need_hint(self.progress, "c2"), "")

    def test_choice_roundtrip_and_closed_rejected(self) -> None:
        self.assertTrue(save_choice(self.progress, "cefr", "a1"))
        self.assertEqual(saved_choice(self.progress, "cefr"), "a1")
        self.assertFalse(save_choice(self.progress, "cefr", "a2"))
        self.assertEqual(saved_choice(self.progress, "cefr"), "a1")
        again = Progress(self.root / "english.json")
        self.assertEqual(saved_choice(again, "cefr"), "a1")
        self.assertTrue(save_choice(again, "freq", "s1000"))


class TerraformerBayScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1024x600")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "root", None) is not None:
            try:
                cls.root.destroy()
            except tk.TclError:
                pass

    def setUp(self) -> None:
        if getattr(self, "root", None) is None:
            self.skipTest("нет дисплея")
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        pilots.reset_root(self.data)
        p = pilots.create("Tester")
        pilots.activate(p["id"])

        class _App:
            current = KEY
        self.app = _App()
        self.scr = TerraformerBayScreen(self.root, self.app)
        self.scr.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.scr.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.scr.destroy()
        except tk.TclError:
            pass
        self.root.update()
        pilots.reset_root()
        self.tmp.cleanup()

    def test_arrows_switch_and_choice_is_saved(self) -> None:
        # event_generate("<Left/Right>") ненадёжен в Windows CI и длинных
        # прогонах: фокус окна часто не успевает встать, и клавиша не доходит
        # до обработчика. Сами _on_left/_on_right синхронны, выбор сохраняется
        # сразу. Проверяем, что привязки стоят, и вызываем обработчики напрямую.
        self.assertEqual(self.scr.current_robot().id, "a1")
        self.assertTrue(self.scr.canvas.bind("<Right>"))
        self.assertTrue(self.scr.canvas.bind("<Left>"))
        self.assertTrue(self.scr.bind("<Right>"))
        self.assertTrue(self.scr.bind("<Left>"))
        self.scr._on_right()
        self.root.update()
        self.assertEqual(self.scr.current_robot().id, "a2")
        self.scr._on_left()
        self.root.update()
        self.assertEqual(self.scr.current_robot().id, "a1")
        self.assertTrue(self.scr.choose())
        self.assertEqual(saved_choice(self.scr.progress, "cefr"), "a1")

    def test_line_switch_changes_catalog(self) -> None:
        self.scr.set_line("freq")
        self.root.update()
        self.assertEqual(len(self.scr._line_ids()), 4)
        self.assertEqual(self.scr.current_robot().name, "S-1000")
        self.scr.set_line("cefr")
        self.root.update()
        self.assertEqual(len(self.scr._line_ids()), 8)

    def test_locked_robot_is_disabled_and_drawn_with_lock(self) -> None:
        self.scr.step(1)
        self.root.update()
        self.assertEqual(self.scr.current_robot().id, "a2")
        self.assertFalse(self.scr.choose_btn._enabled)
        self.assertFalse(self.scr.choose())
        self.assertEqual(saved_choice(self.scr.progress, "cefr"), None)
        self.assertTrue(self.scr.canvas.find_withtag("tf_lock"))
        self.assertIn("A1", self.scr.hint_lbl.cget("text"))

    def test_stop_cancels_viewer_jobs(self) -> None:
        self.scr.start()
        self.scr.stop()
        self.assertIsNone(self.scr._viewer._job)
        self.assertIsNone(self.scr._viewer._full_job)
        self.scr.stop()

    def test_layout_fits_without_scrollbars(self) -> None:
        def walk(w):
            yield w
            for child in w.winfo_children():
                yield from walk(child)
        self.assertFalse(any(isinstance(w, (tk.Scrollbar,)) for w in walk(self.scr)))
        self.assertGreater(self.scr.canvas.winfo_width(), 100)
        self.assertGreater(self.scr.canvas.winfo_height(), 100)
        self.assertTrue(self.scr.choose_btn.winfo_ismapped())
        self.assertTrue(self.scr.btn_prev.winfo_ismapped())
        self.assertTrue(self.scr.btn_next.winfo_ismapped())


if __name__ == "__main__":
    unittest.main()


class FreqLadderTest(unittest.TestCase):
    """Следующий частотный набор открывается после освоения предыдущего."""

    def test_next_set_opens_after_previous_is_done(self) -> None:
        from unittest import mock
        from stamina import terraformer_bay as tb
        prog = object()
        with mock.patch.object(tb.access, "is_captain", return_value=False), \
             mock.patch.object(tb.access, "unlock_pct", return_value=80), \
             mock.patch.object(tb, "_freq_slugs", return_value=[f"w{i}" for i in range(10)]), \
             mock.patch.object(tb, "_done", side_effect=lambda p, s: int(s[1:]) < 7):
            self.assertFalse(tb.robot_open(prog, "s3000"))
            prev, pct, now = tb.robot_need(prog, "s3000")
            self.assertEqual((pct, now), (80, 70))
        with mock.patch.object(tb.access, "is_captain", return_value=False), \
             mock.patch.object(tb.access, "unlock_pct", return_value=80), \
             mock.patch.object(tb, "_freq_slugs", return_value=[f"w{i}" for i in range(10)]), \
             mock.patch.object(tb, "_done", side_effect=lambda p, s: int(s[1:]) < 8):
            self.assertTrue(tb.robot_open(prog, "s3000"))
            self.assertIsNone(tb.robot_need(prog, "s3000"))

    def test_captain_has_everything(self) -> None:
        from unittest import mock
        from stamina import terraformer_bay as tb
        with mock.patch.object(tb.access, "is_captain", return_value=True):
            for rid in tb.LINES["freq"]:
                self.assertTrue(tb.robot_open(object(), rid), rid)
