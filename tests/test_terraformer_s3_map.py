"""Этап 3 терраформера: большая карта, панорама камеры и миникарта."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from stamina import pilots, theme
from stamina import terraformer_strategy as strategy
from stamina.terraformer_trainer import (
    GRID_H,
    GRID_W,
    Camera,
    TrainerModel,
    minimap_click_to_world,
    minimap_rect,
    point_in_rect,
    world_to_minimap,
)


class MapSizeTest(unittest.TestCase):
    def test_table_matches_plan(self) -> None:
        expected = {
            "A1": (64, 40),
            "A2": (72, 44),
            "B1.1": (80, 48),
            "B1.2": (84, 52),
            "B2.1": (88, 52),
            "B2.2": (92, 56),
            "C1": (96, 56),
            "C2": (100, 60),
        }
        for level, size in expected.items():
            self.assertEqual(strategy.map_size(level), size, level)

    def test_c2_is_100_by_60(self) -> None:
        self.assertEqual(strategy.map_size("C2"), (100, 60))

    def test_sizes_are_non_decreasing(self) -> None:
        sizes = [strategy.map_size(name) for name in strategy.LEVELS]
        for (pw, ph), (nw, nh) in zip(sizes, sizes[1:]):
            self.assertGreaterEqual(nw, pw)
            self.assertGreaterEqual(nh, ph)

    def test_unknown_level_falls_back_to_a1(self) -> None:
        self.assertEqual(strategy.map_size("nope"), strategy.map_size("A1"))
        self.assertEqual(strategy.map_size(None), strategy.map_size("A1"))


class StartModelTest(unittest.TestCase):
    def test_default_model_stays_40_by_24(self) -> None:
        m = TrainerModel(seed=1)
        self.assertEqual((m.w, m.h), (GRID_W, GRID_H))
        self.assertEqual((GRID_W, GRID_H), (40, 24))

    def test_explicit_size_is_kept(self) -> None:
        m = TrainerModel(50, 30, seed=2)
        self.assertEqual((m.w, m.h), (50, 30))

    def test_for_level_uses_map_size(self) -> None:
        for level in strategy.LEVELS:
            m = TrainerModel.for_level(level, seed=3)
            self.assertEqual((m.w, m.h), strategy.map_size(level), level)

    def test_for_level_c2(self) -> None:
        m = TrainerModel.for_level("C2", seed=4)
        self.assertEqual((m.w, m.h), (100, 60))
        self.assertEqual(len(m.dug), 60)
        self.assertEqual(len(m.dug[0]), 100)


class CameraPanTest(unittest.TestCase):
    def test_pan_clamps_inside_map(self) -> None:
        cam = Camera(64, 40)
        cam.pan(1000, 1000)
        self.assertLessEqual(cam.cx, 64)
        self.assertLessEqual(cam.cy, 40)
        self.assertFalse(cam.follow)
        cam.pan(-2000, -2000)
        self.assertGreaterEqual(cam.cx, 0)
        self.assertGreaterEqual(cam.cy, 0)

    def test_center_on_clamps_and_disables_follow(self) -> None:
        cam = Camera(64, 40)
        cam.center_on(-10, 999)
        self.assertEqual(cam.cx, 0.0)
        self.assertEqual(cam.cy, 40.0)
        self.assertFalse(cam.follow)

    def test_edge_pan_direction(self) -> None:
        from stamina.lounge.trainer import TrainerGame
        self.assertEqual(TrainerGame.edge_pan_direction(0, 300, 800, 600), (-1, 0))
        self.assertEqual(TrainerGame.edge_pan_direction(799, 300, 800, 600), (1, 0))
        self.assertEqual(TrainerGame.edge_pan_direction(400, 0, 800, 600), (0, -1))
        self.assertEqual(TrainerGame.edge_pan_direction(400, 599, 800, 600), (0, 1))
        self.assertEqual(TrainerGame.edge_pan_direction(400, 300, 800, 600), (0, 0))


class MinimapGeometryTest(unittest.TestCase):
    def test_rect_keeps_aspect_and_stays_inside(self) -> None:
        rect = minimap_rect(1000, 600, 100, 60, margin=10, bottom=34,
                            max_w=190, max_h=150)
        x0, y0, x1, y1 = rect
        self.assertLessEqual(x1, 1000)
        self.assertLessEqual(y1, 600)
        self.assertGreater(x0, 0)
        self.assertGreater(y0, 0)
        self.assertAlmostEqual((x1 - x0) / (y1 - y0), 100 / 60, places=2)

    def test_click_to_world_corners_and_center(self) -> None:
        rect = (0, 0, 100, 50)
        self.assertEqual(minimap_click_to_world(0, 0, rect, 100, 50), (0.0, 0.0))
        self.assertEqual(minimap_click_to_world(100, 50, rect, 100, 50), (100.0, 50.0))
        self.assertEqual(minimap_click_to_world(50, 25, rect, 100, 50), (50.0, 25.0))

    def test_click_outside_clamps_to_edges(self) -> None:
        rect = (10, 10, 110, 60)
        self.assertEqual(minimap_click_to_world(-50, -50, rect, 100, 50), (0.0, 0.0))
        self.assertEqual(minimap_click_to_world(500, 500, rect, 100, 50), (100.0, 50.0))

    def test_world_to_minimap_round_trip(self) -> None:
        rect = (20, 30, 220, 150)
        for gx, gy in ((0, 0), (25.5, 12.5), (100, 60)):
            sx, sy = world_to_minimap(gx, gy, rect, 100, 60)
            bx, by = minimap_click_to_world(sx, sy, rect, 100, 60)
            self.assertAlmostEqual(bx, gx, places=6)
            self.assertAlmostEqual(by, gy, places=6)

    def test_point_in_rect(self) -> None:
        self.assertTrue(point_in_rect(5, 5, (0, 0, 10, 10)))
        self.assertFalse(point_in_rect(15, 5, (0, 0, 10, 10)))
        self.assertFalse(point_in_rect(5, 5, None))


class _Event:
    def __init__(self, keysym: str = "", keycode: int = 0, state: int = 0,
                 x: int = 0, y: int = 0) -> None:
        self.keysym = keysym
        self.keycode = keycode
        self.state = state
        self.x = x
        self.y = y


class TrainerMapUiTest(unittest.TestCase):
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
        self.data = Path(self.tmp.name) / "Stamina"
        self.data.mkdir()
        pilots.reset_root(self.data)
        pilots.activate(pilots.create("Tester")["id"])
        from stamina.lounge.trainer import TrainerGame
        self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.game.canvas.config(width=960, height=540)
        self.root.update_idletasks()
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

    def test_new_game_uses_level_map_size(self) -> None:
        expected = strategy.map_size(self.game.model.standing.current_level)
        self.assertEqual((self.game.model.w, self.game.model.h), expected)

    def test_reset_starts_level_sized_map(self) -> None:
        self.game.model = TrainerModel(seed=9)
        self.game.camera = Camera(self.game.model.w, self.game.model.h)
        self.game.reset()
        expected = strategy.map_size(self.game.model.standing.current_level)
        self.assertEqual((self.game.model.w, self.game.model.h), expected)

    def test_arrow_keys_move_selected_unit_not_pan_camera(self) -> None:
        game = self.game
        game.camera.center_on(game.model.w / 2, game.model.h / 2)
        game.camera.follow = True
        before_cx = game.camera.cx
        before_unit_x = game.model.main_unit.x

        game.on_key(_Event("Right", 39))
        self.assertEqual(game.camera.cx, before_cx)
        game.model.tick_units()
        self.assertEqual(game.model.main_unit.x, before_unit_x + 1)

        before_cx = game.camera.cx
        before_unit_x = game.model.main_unit.x
        game.on_key(_Event("Left", 37))
        self.assertEqual(game.camera.cx, before_cx)
        game.model.tick_units()
        self.assertEqual(game.model.main_unit.x, before_unit_x - 1)

    def test_wasd_still_moves_the_unit(self) -> None:
        game = self.game
        before = list(game.model.robot)
        game.on_key(_Event("d", 68))
        self.assertEqual(game.model.robot[0], before[0] + 1)

    def test_edge_pan_moves_camera_and_clamps(self) -> None:
        game = self.game
        w = max(game.canvas.winfo_width(), 10)
        h = max(game.canvas.winfo_height(), 10)
        game.camera.center_on(game.model.w / 2, game.model.h / 2)

        game._last_mouse = (0, h // 2)
        dx, dy = game.edge_pan_step(w, h)
        self.assertEqual((dx, dy), (-1, 0))
        self.assertLess(game.camera.cx, game.model.w / 2)
        self.assertFalse(game.camera.follow)

        game._last_mouse = (w - 1, h // 2)
        dx, dy = game.edge_pan_step(w, h)
        self.assertEqual((dx, dy), (1, 0))

        game.camera.cx = 0
        game._last_mouse = (0, h // 2)
        game.edge_pan_step(w, h)
        self.assertGreaterEqual(game.camera.cx, 0)

        game.camera.cx = game.model.w
        game._last_mouse = (w - 1, h // 2)
        game.edge_pan_step(w, h)
        self.assertLessEqual(game.camera.cx, game.model.w)

    def test_minimap_is_drawn_and_click_jumps_camera(self) -> None:
        game = self.game
        game.camera.center_on(game.model.w / 2, game.model.h / 2)
        game.redraw()
        rect = game._minimap_rect
        self.assertIsNotNone(rect)
        x0, y0, x1, y1 = rect
        # клик у правого края миникарты — камера уходит к правой части карты
        sx, sy = x1 - 2, (y0 + y1) / 2
        game._on_lmb_down(_Event(x=sx, y=sy))
        game._on_lmb_up(_Event(x=sx, y=sy))
        self.assertGreater(game.camera.cx, game.model.w / 2)
        self.assertFalse(game.camera.follow)

    def test_minimap_drag_moves_camera(self) -> None:
        game = self.game
        game.camera.center_on(game.model.w / 2, game.model.h / 2)
        game.redraw()
        x0, y0, x1, y1 = game._minimap_rect
        start = (x1 - 2, (y0 + y1) / 2)
        game._on_lmb_down(_Event(x=start[0], y=start[1]))
        game._on_lmb_drag(_Event(x=x0 + 2, y=(y0 + y1) / 2))
        game._on_lmb_up(_Event(x=x0 + 2, y=(y0 + y1) / 2))
        self.assertLess(game.camera.cx, game.model.w / 2)

    def test_minimap_works_in_iso_view(self) -> None:
        game = self.game
        game.on_key(_Event("i", 73))
        self.assertTrue(game.iso_view)
        game.camera.center_on(game.model.w / 2, game.model.h / 2)
        game.redraw()
        rect = game._minimap_rect
        self.assertIsNotNone(rect)
        x0, y0, x1, y1 = rect
        game._on_lmb_down(_Event(x=x1 - 2, y=(y0 + y1) / 2))
        game._on_lmb_up(_Event(x=x1 - 2, y=(y0 + y1) / 2))
        self.assertGreater(game.camera.cx, game.model.w / 2)

    def test_minimap_not_clickable_when_overlay_open(self) -> None:
        game = self.game
        game.redraw()
        rect = game._minimap_rect
        self.assertIsNotNone(rect)
        game.overlay = "missions"
        game.redraw()
        self.assertIsNone(game._minimap_rect)
        x0, y0, x1, y1 = rect
        cx_before = game.camera.cx
        game._on_lmb_down(_Event(x=x1 - 2, y=(y0 + y1) / 2))
        self.assertEqual(game.camera.cx, cx_before)
        game.overlay = None


if __name__ == "__main__":
    unittest.main()
