"""Тренажёр терраформера A1: логика поля, камера, чертёж и Tk-дым."""
from __future__ import annotations

import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from stamina import pilots, theme
from stamina.terraformer_trainer import (
    BASE_CELL,
    HOLD_CAP,
    LAYERS,
    SITE,
    ZOOM_MAX,
    ZOOM_MIN,
    Camera,
    TrainerModel,
    load_blueprint,
    save_blueprint,
)


def _dig_until_soil_full(model: TrainerModel) -> None:
    for y in range(model.h):
        for x in range(model.w):
            if model.holds["soil"] >= HOLD_CAP:
                return
            if model.on_site(x, y) or model.dug[y][x]:
                continue
            model.robot = [x, y]
            if model.dig() != "ok":
                raise AssertionError("не удалось набрать грунт")


class TrainerModelTest(unittest.TestCase):
    def test_move_clamps_at_edges(self) -> None:
        m = TrainerModel()
        m.robot = [0, 0]
        self.assertFalse(m.move(-1, 0))
        self.assertEqual(m.robot, [0, 0])
        self.assertEqual(m.facing, (-1, 0))
        m.robot = [m.w - 1, m.h - 1]
        self.assertFalse(m.move(1, 1))
        self.assertEqual(m.robot, [m.w - 1, m.h - 1])
        m.robot = [5, 5]
        self.assertTrue(m.move(1, 0))
        self.assertEqual(m.robot, [6, 5])

    def test_dig_takes_soil_then_depth_blocks(self) -> None:
        m = TrainerModel(depth=1)
        m.robot = [10, 10]
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.holds["soil"], 1)
        self.assertEqual(m.dug[10][10], 1)
        self.assertEqual(m.dig(), "too_deep")

    def test_depth_two_takes_clay(self) -> None:
        m = TrainerModel(depth=2)
        m.robot = [10, 10]
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.dig(), "ok")
        self.assertEqual(m.holds["soil"], 1)
        self.assertEqual(m.holds["clay"], 1)
        self.assertEqual(m.dug[10][10], 2)
        self.assertEqual(m.dig(), "too_deep")

    def test_site_is_not_diggable(self) -> None:
        m = TrainerModel()
        sx, sy = SITE[0], SITE[1]
        m.robot = [sx, sy]
        self.assertTrue(m.on_site(sx, sy))
        self.assertEqual(m.dig(), "site")
        self.assertEqual(m.holds["soil"], 0)

    def test_hold_full_and_robot_still_moves(self) -> None:
        m = TrainerModel()
        _dig_until_soil_full(m)
        self.assertTrue(m.hold_full("soil"))
        x, y = 0, 0
        while m.on_site(x, y) or m.dug[y][x]:
            x += 1
        m.robot = [x, y]
        self.assertEqual(m.dig(), "hold_full")
        self.assertEqual(m.holds["soil"], HOLD_CAP)
        before = list(m.robot)
        m.move(1, 0)
        self.assertNotEqual(m.robot, before)

    def test_unload_needs_full_hold_then_places_block(self) -> None:
        m = TrainerModel()
        self.assertEqual(m.unload(), "not_full")
        _dig_until_soil_full(m)
        self.assertEqual(m.unload(), "ok")
        self.assertEqual(m.progress(), (1, len(m.site_cells())))
        self.assertEqual(m.holds["soil"], 0)
        self.assertEqual(m.blocks, [m.site_cells()[0]])

    def test_twelve_unloads_complete_foundation(self) -> None:
        m = TrainerModel()
        for i in range(12):
            _dig_until_soil_full(m)
            result = m.unload()
            if i < 11:
                self.assertEqual(result, "ok")
            else:
                self.assertEqual(result, "complete")
        self.assertTrue(m.walls_open)
        self.assertEqual(m.progress(), (12, 12))
        _dig_until_soil_full(m)
        self.assertEqual(m.unload(), "done")

    def test_switch_hold_cycles(self) -> None:
        m = TrainerModel()
        self.assertEqual(m.active_hold, LAYERS[0])
        self.assertEqual(m.switch_hold(), LAYERS[1])
        self.assertEqual(m.switch_hold(), LAYERS[2])
        self.assertEqual(m.switch_hold(), LAYERS[0])

    def test_layer_left(self) -> None:
        m = TrainerModel(depth=2)
        self.assertEqual(m.layer_left(10, 10), 2)
        m.robot = [10, 10]
        m.dig()
        self.assertEqual(m.layer_left(10, 10), 1)
        m.dig()
        self.assertEqual(m.layer_left(10, 10), 0)


class CameraTest(unittest.TestCase):
    def test_zoom_clamps(self) -> None:
        cam = Camera(40, 24)
        self.assertAlmostEqual(cam.cell_px(), BASE_CELL)
        for _ in range(50):
            cam.zoom_in()
        self.assertEqual(cam.zoom, ZOOM_MAX)
        for _ in range(50):
            cam.zoom_out()
        self.assertEqual(cam.zoom, ZOOM_MIN)

    def test_reset_and_track(self) -> None:
        cam = Camera(40, 24)
        cam.pan(10, 10)
        self.assertFalse(cam.follow)
        cam.reset(5, 6)
        self.assertTrue(cam.follow)
        self.assertEqual(cam.zoom, 1.0)
        self.assertAlmostEqual(cam.cx, 5.5)
        self.assertAlmostEqual(cam.cy, 6.5)
        cam.track(8, 9)
        self.assertAlmostEqual(cam.cx, 8.5)
        self.assertAlmostEqual(cam.cy, 9.5)

    def test_pan_disables_follow_and_clamps(self) -> None:
        cam = Camera(40, 24)
        cam.pan(-1000, -1000)
        self.assertFalse(cam.follow)
        self.assertGreaterEqual(cam.cx, 0)
        self.assertGreaterEqual(cam.cy, 0)
        cam.pan(10000, 10000)
        self.assertLessEqual(cam.cx, 40)
        self.assertLessEqual(cam.cy, 24)

    def test_to_screen_center(self) -> None:
        cam = Camera(40, 24)
        cam.reset(10, 10)
        px, py = cam.to_screen(10, 10, 800, 600)
        self.assertAlmostEqual(px, 400 - BASE_CELL / 2)
        self.assertAlmostEqual(py, 300 - BASE_CELL / 2)


class BlueprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Stamina"
        self.root.mkdir()
        pilots.reset_root(self.root)
        self.pilot = pilots.create("Tester")
        pilots.activate(self.pilot["id"])

    def tearDown(self) -> None:
        pilots.reset_root()
        self.tmp.cleanup()

    def test_round_trip(self) -> None:
        m = TrainerModel()
        m.robot = [7, 7]
        m.dig()
        _dig_until_soil_full(m)
        m.unload()
        self.assertTrue(save_blueprint(m))
        loaded = load_blueprint()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.to_blueprint(), m.to_blueprint())

    def test_garbage_from_blueprint_is_fresh(self) -> None:
        fresh = TrainerModel.from_blueprint({"kind": "wrong"})
        self.assertEqual(fresh.w, TrainerModel().w)
        self.assertEqual(fresh.h, TrainerModel().h)
        fresh = TrainerModel.from_blueprint({"kind": "terraformer_trainer", "w": "x"})
        self.assertEqual(fresh.dug, [[0] * fresh.w for _ in range(fresh.h)])
        fresh = TrainerModel.from_blueprint("garbage")  # type: ignore[arg-type]
        self.assertEqual(fresh.w, TrainerModel().w)

    def test_load_missing_and_garbage(self) -> None:
        self.assertIsNone(load_blueprint())
        path = Path(self.tmp.name) / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(load_blueprint(path))
        path.write_text(json.dumps({"kind": "other"}), encoding="utf-8")
        self.assertIsNone(load_blueprint(path))


class TrainerTkTest(unittest.TestCase):
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
        p = pilots.create("Tester")
        pilots.activate(p["id"])

        from stamina.lounge.screen import GAMES
        from stamina.lounge.trainer import TrainerGame

        self.assertIn("trainer", [g["id"] for g in GAMES])
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

    class _Event:
        def __init__(self, keysym: str, keycode: int = 0, state: int = 0) -> None:
            self.keysym = keysym
            self.keycode = keycode
            self.state = state

    def _canvas_texts(self) -> list[str]:
        c = self.game.canvas
        return [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]

    def test_handlers_move_dig_and_keys(self) -> None:
        before = list(self.game.model.robot)
        self.game.do_move(-1, 0)
        self.root.update()
        self.assertNotEqual(self.game.model.robot, before)

        self.game.model.robot = [10, 10]
        self.assertEqual(self.game.do_dig(), "ok")
        self.assertEqual(self.game.model.holds["soil"], 1)

        self.assertEqual(self.game.do_unload(), "not_full")

        self.assertIn("Учебная смена", "\n".join(self._canvas_texts()))

    def test_on_key_and_wheel(self) -> None:
        before = list(self.game.model.robot)
        self.game.on_key(self._Event("d", 68))
        self.root.update()
        self.assertEqual(self.game.model.robot[0], before[0] + 1)

        # русская раскладка: неизвестный keysym, знакомый keycode
        before = list(self.game.model.robot)
        self.game.on_key(self._Event("в", 65))
        self.root.update()
        self.assertEqual(self.game.model.robot[0], before[0] - 1)

        zoom = self.game.camera.zoom
        self.game.on_wheel(-1, True, False)
        self.assertGreater(self.game.camera.zoom, zoom)
        self.game.on_wheel(1, True, False)
        self.assertAlmostEqual(self.game.camera.zoom, zoom)


if __name__ == "__main__":
    unittest.main()
