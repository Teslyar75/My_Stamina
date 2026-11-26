"""Стратегический слой терраформера: уровни, отряд, задания, туман, червь, стройка."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from stamina import pilots, theme
from stamina import terraformer_strategy as strategy
from stamina.terraformer_trainer import (
    GRID_H,
    GRID_W,
    HOLD_CAP,
    Camera,
    TrainerModel,
)


class LevelsTest(unittest.TestCase):
    def test_cefr_ladder(self) -> None:
        self.assertEqual(strategy.LEVELS,
                         ("A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"))
        self.assertEqual(strategy.level_index("B1.2"), 3)
        self.assertEqual(strategy.level_name(99), "C2")
        self.assertEqual(strategy.level_index("unknown"), 0)

    def test_heights_grow_with_level(self) -> None:
        heights = [strategy.max_height(name) for name in strategy.LEVELS]
        self.assertEqual(heights, sorted(heights))
        self.assertEqual(strategy.max_height("A1"), 1)
        self.assertEqual(strategy.max_height("C2"), 8)
        self.assertEqual(strategy.level_for_height(3), "B1.2")
        self.assertEqual(strategy.level_for_height(8), "C2")

    def test_standing_unlocks_next_level_above_80(self) -> None:
        st = strategy.standing({"A1": 90})
        self.assertEqual(st.pct("A1"), 90)
        self.assertTrue(st.unlocked("A2"))
        self.assertFalse(st.unlocked("B1.1"))
        self.assertIn("A2", st.allowed_levels())

    def test_second_unit_after_half_level(self) -> None:
        st = strategy.standing({"A1": 60})
        self.assertTrue(st.second_unit)
        self.assertFalse(st.next_unit)
        st = strategy.standing({"A1": 20})
        self.assertFalse(st.second_unit)

    def test_developer_gets_every_level(self) -> None:
        with patch.object(strategy, "is_developer", return_value=True):
            st = strategy.standing({})
        self.assertTrue(st.developer)
        self.assertEqual(st.allowed_levels(), strategy.LEVELS)
        self.assertTrue(st.unlocked("C2"))

    def test_level_titles(self) -> None:
        expected = {
            "A1": "Высадка",
            "A2": "Лагерь",
            "B1.1": "Посёлок",
            "B1.2": "Станция",
            "B2.1": "Город",
            "B2.2": "Агломерация",
            "C1": "Колония",
            "C2": "Цивилизация",
        }
        for name, russian in expected.items():
            self.assertEqual(strategy.LEVEL_TITLE[name], f"{name} · {russian}")
            state = strategy.LevelState(name, strategy.level_index(name))
            self.assertEqual(state.title, f"{name} · {russian}")


class MissionsTest(unittest.TestCase):
    def test_catalog_has_three_per_level(self) -> None:
        book = strategy.MissionBook()
        self.assertEqual(len(book.missions), len(strategy.LEVELS) * 3)
        for name in strategy.LEVELS:
            self.assertEqual(len(book.by_level(name)), 3)

    def test_evaluate_marks_done_and_pushes_alert(self) -> None:
        book = strategy.MissionBook()
        fresh = book.evaluate({"finds": 1})
        self.assertTrue(any(m.id == "a1-find" for m in fresh))
        self.assertTrue(book.by_level("A1")[1].done)
        self.assertTrue(any(a.kind == "mission" for a in book.alerts))
        self.assertEqual(book.stats_pct()["A1"], 33)

    def test_done_missions_survive_round_trip(self) -> None:
        book = strategy.MissionBook()
        book.evaluate({"finds": 1})
        restored = strategy.MissionBook.from_dict(book.to_dict())
        self.assertTrue(restored.by_level("A1")[1].done)
        self.assertEqual(restored.done_count("A1"), 1)


class UnitsTest(unittest.TestCase):
    def _model(self) -> TrainerModel:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=7, depth=1)
        m.developer = False
        return m

    def test_selection_rect_and_order(self) -> None:
        m = self._model()
        m.units[0].x, m.units[0].y = 12, 12
        u2 = m.add_unit("A1", 5, 5)
        picked = m.select_rect(4, 4, 6, 6)
        self.assertEqual([u.uid for u in picked], [u2.uid])
        result = m.command_move(8, 8)
        self.assertIn(u2.uid, result)
        self.assertEqual(u2.target, (8, 8))
        self.assertTrue(u2.path)

    def test_select_all(self) -> None:
        m = self._model()
        m.add_unit("A1", 5, 5)
        self.assertEqual(len(m.select_all()), 2)
        self.assertEqual(len(m.selected), 2)

    def test_pathfind_goes_around_wall(self) -> None:
        wall = {(3, y) for y in range(0, 8)}
        path = strategy.pathfind((1, 3), (5, 3), 10, 10, wall)
        self.assertTrue(path)
        self.assertEqual(path[-1], (5, 3))
        self.assertFalse(any(cell in wall for cell in path))

    def test_formation_targets_are_unique(self) -> None:
        units = [strategy.Unit(f"u{i}", "A1", i, 0) for i in range(4)]
        targets = strategy.formation_targets(units, 10, 10)
        self.assertEqual(len(set(targets.values())), 4)


class FogAndExpansionTest(unittest.TestCase):
    def test_fog_starts_small_and_grows(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=3, depth=1)
        self.assertLess(len(m.explored), m.w * m.h)
        self.assertTrue(m.is_visible(m.main_unit.x, m.main_unit.y))
        before = len(m.explored)
        m.main_unit.x = min(m.w - 1, m.main_unit.x + 10)
        m._update_explored()
        self.assertGreater(len(m.explored), before)

    def test_map_expands_and_shifts_world(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=4, depth=1)
        m.units[0].x, m.units[0].y = 2, 2
        m.robot = [2, 2]
        old_site = m.site
        self.assertTrue(m.expand_around(2, 2, pad=4))
        self.assertEqual(m.w, GRID_W + 4)
        self.assertEqual(m.h, GRID_H + 4)
        self.assertEqual((m.units[0].x, m.units[0].y), (6, 6))
        self.assertEqual(m.robot, [6, 6])
        self.assertEqual(m.site, (old_site[0] + 4, old_site[1] + 4, old_site[2], old_site[3]))
        for (x, y) in m.finds:
            self.assertTrue(0 <= x < m.w and 0 <= y < m.h)

    def test_edge_find_is_deterministic(self) -> None:
        self.assertEqual(strategy.find_for_cell(5, 30, 40), strategy.find_for_cell(5, 30, 40))


class WormTest(unittest.TestCase):
    def test_trail_and_safe_cells(self) -> None:
        worm = strategy.Sandworm(5, 5)
        deposits = {(6, 5)}
        safe = {(4, 5)}
        cell, spice = strategy.worm_step(worm, 20, 20, 1, deposits, safe)
        self.assertTrue(worm.trail)
        self.assertNotIn((6, 5), {(worm.x, worm.y)})
        self.assertIsInstance(spice, bool)
        self.assertTrue(cell is None or cell not in safe)

    def test_worm_never_hits_safe_foundation(self) -> None:
        worm = strategy.Sandworm(5, 5)
        safe = {(x, y) for x in range(20) for y in range(20)}
        for _ in range(10):
            cell, _ = strategy.worm_step(worm, 20, 20, 2, set(), safe)
            self.assertIsNone(cell)


class StructuresTest(unittest.TestCase):
    def test_availability_by_level(self) -> None:
        self.assertTrue(strategy.structure_available("shelter", "A1"))
        self.assertFalse(strategy.structure_available("greenhouse", "A1"))
        self.assertTrue(strategy.structure_available("greenhouse", "A2"))
        self.assertFalse(strategy.structure_available("core", "C1"))
        self.assertTrue(strategy.structure_available("core", "C2"))
        self.assertTrue(strategy.structure_available("core", "A1", developer=True))

    def test_build_checks_level_and_credits(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=8, depth=1)
        m.developer = False
        m.credits = 1000
        ok, msg = m.build_structure("greenhouse")
        self.assertFalse(ok)
        self.assertIn("A2", msg)
        ok, _ = m.build_structure("shelter")
        self.assertTrue(ok)
        self.assertEqual(m.max_build_height, 1)

    def test_income_needs_connection(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=9, depth=1)
        m.developer = False
        m.credits = 1000
        # далеко от базы и других зданий — связи нет, дохода нет
        self.assertTrue(m.build_structure("shelter", x=20, y=15)[0])
        self.assertEqual(m.tick_income(), 0)
        self.assertFalse(m.buildings[0].connected)
        # рядом появилось второе здание — коммуникация есть, доход идёт
        self.assertTrue(m.build_structure("shelter", x=21, y=15)[0])
        self.assertEqual(m.tick_income(), 2)
        self.assertEqual(m.connected, 2)

    def test_community_snapshot_strips_terrain(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=10, depth=1)
        snap = strategy.community_snapshot(m, "Tester")
        self.assertEqual(snap["kind"], "terraformer_community")
        self.assertNotIn("dug", snap)
        self.assertNotIn("revealed", snap)
        self.assertEqual(snap["levels"], list(strategy.LEVELS))


class ModelStrategyTest(unittest.TestCase):
    def test_hold_cap_is_five(self) -> None:
        self.assertEqual(HOLD_CAP, 5)

    def test_developer_sync_gives_all_eight_units(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=11, depth=1)
        m.developer = True
        m.sync_units()
        self.assertEqual({u.level for u in m.units}, set(strategy.LEVELS))
        self.assertEqual(len(m.units), 8)

    def test_blueprint_keeps_strategy_state(self) -> None:
        m = TrainerModel(w=GRID_W, h=GRID_H, seed=12, depth=1)
        m.add_unit("A1", 4, 4)
        m.credits = 77
        m.mission_book.evaluate({"finds": 1})
        restored = TrainerModel.from_blueprint(m.to_blueprint())
        self.assertEqual(restored.credits, 77)
        self.assertEqual(len(restored.units), len(m.units))
        self.assertEqual(restored.selected, m.selected)
        self.assertTrue(restored.mission_book.by_level("A1")[1].done)
        self.assertEqual(restored.explored, m.explored)


class CameraZoomTest(unittest.TestCase):
    def test_zoom_keeps_point_under_cursor(self) -> None:
        cam = Camera(40, 24)
        cam.reset(20, 12)
        sx, sy = 300, 200
        before = cam.to_cell(sx, sy, 800, 600)
        cam.zoom_at(-1, sx, sy, 800, 600)
        after = cam.to_cell(sx, sy, 800, 600)
        self.assertGreater(cam.zoom, 1.0)
        self.assertLessEqual(abs(after[0] - before[0]), 1)
        self.assertLessEqual(abs(after[1] - before[1]), 1)


class _Event:
    def __init__(self, x: float = 0, y: float = 0, keysym: str = "",
                 keycode: int = 0, state: int = 0) -> None:
        self.x = x
        self.y = y
        self.keysym = keysym
        self.keycode = keycode
        self.state = state


class TrainerStrategyUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1100x700")

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
        self.data = Path(self.tmp.name) / "Stamina"
        self.data.mkdir()
        pilots.reset_root(self.data)
        p = pilots.create("Tester")
        pilots.activate(p["id"])
        from stamina.lounge.trainer import TrainerGame

        self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.game.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.game.destroy()
        except tk.TclError:
            pass
        self.root.update()
        pilots.reset_root()
        self.tmp.cleanup()

    def _texts(self) -> list[str]:
        c = self.game.canvas
        return [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]

    def _screen(self, x: int, y: int) -> tuple[float, float]:
        w = max(self.game.canvas.winfo_width(), 10)
        h = max(self.game.canvas.winfo_height(), 10)
        return self.game.camera.to_screen(x, y, w, h)

    def test_missions_overlay_draws_levels_and_checkmarks(self) -> None:
        self.game.toggle_missions()
        self.root.update()
        texts = self._texts()
        self.assertTrue(any("ЗАДАНИЯ · ТРЕВОГИ" in t for t in texts))
        self.assertTrue(any("УРОВНИ" in t for t in texts))
        self.assertTrue(any("A1" in t and "0/3" in t for t in texts))
        self.game.toggle_missions()

    def test_structures_overlay_shows_height_and_level(self) -> None:
        self.game.toggle_structures()
        self.root.update()
        texts = self._texts()
        self.assertTrue(any("СТРОЙКА · ЗДАНИЯ" in t for t in texts))
        self.assertTrue(any("h1" in t and "Укрытие" in t for t in texts))
        self.assertTrue(any("C2" in t for t in texts))
        self.game.toggle_structures()

    def test_lmb_click_selects_unit_or_clears(self) -> None:
        game = self.game
        u2 = game.model.add_unit("A1", 5, 5)
        game.redraw()
        # LMB click on a unit selects it
        sx, sy = self._screen(5, 5)
        click = _Event(sx, sy)
        game._on_lmb_down(click)
        game._on_lmb_up(click)
        self.assertIn(u2.uid, game.model.selected)

        # LMB click on empty ground clears selection
        game.model.clear_selection()
        game.redraw()
        # use a cell where no unit exists
        empty_x, empty_y = 8, 8
        self.assertIsNone(game.model.unit_at(empty_x, empty_y))
        sx3, sy3 = self._screen(empty_x, empty_y)
        click2 = _Event(sx3 + 2, sy3 + 2)
        game._on_lmb_down(click2)
        game._on_lmb_up(click2)
        self.assertEqual(game.model.selected, set())

    def test_rmb_click_gives_order_without_selecting(self) -> None:
        game = self.game
        u2 = game.model.add_unit("A1", 5, 5)
        game.model.selected = {u2.uid}
        game.redraw()
        # RMB click on empty cell issues command_move without changing selection
        tx, ty = 8, 8
        sx, sy = self._screen(tx, ty)
        click = _Event(sx + 2, sy + 2)
        game._on_rmb_down(click)
        game._on_rmb_up(click)
        self.assertEqual(u2.target, (tx, ty))
        self.assertTrue(u2.path)
        # selection should remain as was (not changed to the target unit)
        self.assertEqual(game.model.selected, {u2.uid})

    def test_lmb_drag_box_selects(self) -> None:
        game = self.game
        u2 = game.model.add_unit("A1", 5, 5)
        u3 = game.model.add_unit("A1", 10, 10)
        game.redraw()
        # LMB down at cell just before both units, drag past 6px to cell just after both
        sx_start, sy_start = self._screen(4, 4)
        sx_end, sy_end = self._screen(11, 11)
        down = _Event(sx_start, sy_start)
        game._on_lmb_down(down)
        game._on_lmb_drag(_Event(sx_end, sy_end))
        game._on_lmb_up(_Event(sx_end, sy_end))
        # both units should be selected
        self.assertIn(u2.uid, game.model.selected)
        self.assertIn(u3.uid, game.model.selected)

    def test_ctrl_wheel_zooms_at_cursor(self) -> None:
        game = self.game
        game.overlay = None
        w = game.canvas.winfo_width()
        h = game.canvas.winfo_height()
        x, y = w // 2 + 120, h // 2 - 60
        before = game.camera.to_cell(x, y, w, h)
        zoom_before = game.camera.zoom
        game.on_wheel(-1, True, False, x, y)
        after = game.camera.to_cell(x, y, w, h)
        self.assertGreater(game.camera.zoom, zoom_before)
        self.assertLessEqual(abs(after[0] - before[0]), 1)
        self.assertLessEqual(abs(after[1] - before[1]), 1)

    def test_middle_drag_pans_map(self) -> None:
        game = self.game
        before = game.camera.cx
        game._on_mmb_down(_Event(300, 300))
        game._on_mmb_drag(_Event(380, 300))
        self.assertNotEqual(game.camera.cx, before)
        game._on_mmb_up(_Event(380, 300))

    def test_help_stage_covers_all_eight_levels(self) -> None:
        with patch("stamina.terraformer_trainer.get_language_level", return_value=7):
            self.assertEqual(self.game.help_level_id(), "stage_7")
        with patch("stamina.terraformer_trainer.get_language_level", return_value=2):
            self.assertEqual(self.game.help_level_id(), "stage_2")


class DevFlagTest(unittest.TestCase):
    def test_dev_flag_in_dev_is_true(self) -> None:
        self.assertTrue(strategy.dev_flag_in(["--dev"]))

    def test_dev_flag_in_empty_is_false(self) -> None:
        self.assertFalse(strategy.dev_flag_in([]))

    def test_is_dev_env_with_1(self) -> None:
        import os
        os.environ["STAR_TYPING_DEV"] = "1"
        try:
            self.assertTrue(strategy.is_dev_env())
        finally:
            os.environ.pop("STAR_TYPING_DEV", None)

    def test_is_developer_with_env(self) -> None:
        import os
        from stamina import pilots
        prev = os.environ.get("STAR_TYPING_DEV")
        strategy.set_developer_mode(False)
        try:
            os.environ["STAR_TYPING_DEV"] = "1"
            with patch.object(pilots, "is_captain", return_value=False):
                self.assertTrue(strategy.is_developer())
        finally:
            if prev is None:
                os.environ.pop("STAR_TYPING_DEV", None)
            else:
                os.environ["STAR_TYPING_DEV"] = prev
            strategy.set_developer_mode(False)

    def test_dev_flag_consistency_with_set_developer_mode(self) -> None:
        import os
        from stamina import pilots
        prev = os.environ.get("STAR_TYPING_DEV")
        strategy.set_developer_mode(False)
        try:
            if "STAR_TYPING_DEV" in os.environ:
                os.environ.pop("STAR_TYPING_DEV")
            with patch.object(pilots, "is_captain", return_value=False):
                strategy.set_developer_mode(True)
                self.assertTrue(strategy.is_developer())
                strategy.set_developer_mode(False)
                self.assertFalse(strategy.is_developer())
        finally:
            if prev is None:
                os.environ.pop("STAR_TYPING_DEV", None)
            else:
                os.environ["STAR_TYPING_DEV"] = prev
            strategy.set_developer_mode(False)


if __name__ == "__main__":
    unittest.main()
