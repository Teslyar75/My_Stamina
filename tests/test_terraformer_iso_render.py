"""Iso-отрисовка: порядок слоёв, точный пик и камера (п. 1, 3, 5)."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from stamina import pilots, theme
from stamina.lounge import iso
from stamina.terraformer_trainer import BuildingBlueprint, Camera


class _Event:
    def __init__(self, keysym: str = "", keycode: int = 0, state: int = 0,
                 x: float = 0, y: float = 0) -> None:
        self.keysym = keysym
        self.keycode = keycode
        self.state = state
        self.x = x
        self.y = y


class IsoPickGeometryTest(unittest.TestCase):
    """Точный screen→cell на разных высоте и зуме (без Tk)."""

    def test_pick_top_face_center_at_various_depths_and_zoom(self) -> None:
        cam = Camera(12, 12)
        cam.cx, cam.cy = 6.0, 6.0
        for depth in (0, 1, 3, 6):
            # Одинаковая глубина вокруг: верхняя грань клетки действительно видна.
            dug = [[depth] * 12 for _ in range(12)]
            gz = iso.terrain_gz(depth) + 1
            for zoom in (0.5, 1.0, 2.0, 3.0):
                m = iso.tile_metrics(zoom, 800, 600, cam)
                for x in (2, 5, 8, 10):
                    sx, sy = iso.world_to_screen(x + 0.5, 6.5, gz, m)
                    hit = iso.pick_surface(sx, sy, m, dug, 12, 12)
                    self.assertEqual(hit[:2], (x, 6), (zoom, x, depth))
                    self.assertEqual(hit[2], gz, (zoom, x, depth))

    def test_pick_follows_visible_surface_when_pit_is_covered(self) -> None:
        """Верх ямы совпадает с гранью ближней клетки — пик берёт ближнюю."""
        dug = [[0] * 12 for _ in range(12)]
        dug[6][5] = 1
        cam = Camera(12, 12)
        cam.cx, cam.cy = 6.0, 6.0
        m = iso.tile_metrics(1.0, 800, 600, cam)
        sx, sy = iso.world_to_screen(5.5, 6.5, iso.terrain_gz(1) + 1, m)
        self.assertEqual(iso.pick_surface(sx, sy, m, dug, 12, 12)[:2], (6, 7))

    def test_pick_corner_stays_in_cell(self) -> None:
        dug = [[2] * 20 for _ in range(20)]
        cam = Camera(20, 20)
        cam.cx, cam.cy = 10.0, 10.0
        m = iso.tile_metrics(1.5, 900, 650, cam)
        gz = iso.terrain_gz(2)
        poly = iso.tile_polygon(10, 10, gz, m)
        cx = (poly[0] + poly[4]) / 2
        cy = (poly[1] + poly[5]) / 2
        for k in range(4):
            j = (k + 1) % 4
            # Точка внутри ромба, ближе к середине ребра (не на самой границе).
            edge_x = (poly[2 * k] + poly[2 * j]) / 2
            edge_y = (poly[2 * k + 1] + poly[2 * j + 1]) / 2
            sx = cx + 0.6 * (edge_x - cx)
            sy = cy + 0.6 * (edge_y - cy)
            self.assertEqual(iso.pick_surface(sx, sy, m, dug, 20, 20)[:2], (10, 10))

    def test_draw_order_key_uses_depth_height_and_layer(self) -> None:
        far = iso.draw_order_key(3, 4, 0, 3)
        near = iso.draw_order_key(6, 6, 0, 3)
        self.assertLess(far, near)
        ground = iso.draw_order_key(5, 5, 0, 0)
        unit = iso.draw_order_key(5, 5, 0, 3)
        building = iso.draw_order_key(5, 5, 0, 5)
        self.assertLess(ground, unit)
        self.assertLess(unit, building)
        low = iso.draw_order_key(4, 4, -2, 0)
        high = iso.draw_order_key(4, 4, 1, 0)
        self.assertLess(low, high)


class IsoCameraGeometryTest(unittest.TestCase):
    """Камера не уводит за край карты (п. 5)."""

    def test_clamp_iso_keeps_screen_inside_map(self) -> None:
        cam = Camera(40, 24)
        hw, hh = 32.0, 19.84
        w, h = 900, 650
        span = (w / (2 * hw) + h / (2 * hh)) / 2
        self.assertGreater(2 * span, 24)       # по высоте карта целиком на экране
        cam.cx, cam.cy = 10_000.0, -10_000.0
        cam.clamp_iso(hw, hh, w, h)
        self.assertAlmostEqual(cam.cx, 40.0 - span)
        self.assertAlmostEqual(cam.cy, 12.0)   # центр карты, а не пустота сверху
        cam.cx, cam.cy = -10_000.0, 10_000.0
        cam.clamp_iso(hw, hh, w, h)
        self.assertAlmostEqual(cam.cx, span)
        self.assertAlmostEqual(cam.cy, 12.0)

    def test_clamp_iso_centers_small_map(self) -> None:
        cam = Camera(6, 4)
        cam.cx, cam.cy = 100.0, -100.0
        cam.clamp_iso(40.0, 24.0, 900, 650)
        self.assertEqual((cam.cx, cam.cy), (3.0, 2.0))


class IsoRenderGuiTest(unittest.TestCase):
    """Порядок рисования, клик по юниту и переход I на живом холсте."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        theme.init(cls.root)
        cls.root.geometry("1000x700")
        cls.root.update()

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

    def _redraw(self) -> None:
        try:
            self.game.redraw()
        except tk.TclError as exc:
            if "image" in str(exc):
                self.skipTest(f"текстуры недоступны в тесте: {exc}")
            raise

    def _toggle(self) -> None:
        try:
            self.game.on_key(_Event("i", 73))
        except tk.TclError as exc:
            if "image" in str(exc):
                self.skipTest(f"текстуры недоступны в тесте: {exc}")
            raise

    def _items(self, tag: str, cell: tuple[int, int]) -> list[int]:
        c = self.game.canvas
        cell_tag = f"iso_cell_{cell[0]}_{cell[1]}"
        return [i for i in c.find_withtag(tag) if cell_tag in c.gettags(i)]

    def test_unit_is_drawn_before_near_building(self) -> None:
        """Юнит в дальней клетке перекрывается зданием из ближней."""
        game = self.game
        model = game.model
        model.developer = True
        model.units = [model.main_unit]
        far = (30, 18)
        near = (31, 19)
        model.units[0].x, model.units[0].y = far
        building = BuildingBlueprint("shelter", near)
        building.height = 3
        building.built = True
        building.connected = False
        model.buildings = [building]
        model.explored.update((far, near))
        model.visited.update((far, near))

        self._toggle()
        game._center_iso_cell(*far)
        self._redraw()

        order = {i: n for n, i in enumerate(game.canvas.find_all())}
        unit_items = self._items("unit", far)
        building_items = self._items("building", near)
        self.assertTrue(unit_items, "юнит должен быть нарисован")
        self.assertTrue(building_items, "здание должно быть нарисовано")
        self.assertLess(max(order[i] for i in unit_items),
                        min(order[i] for i in building_items))

    def test_building_in_same_cell_covers_unit(self) -> None:
        """В одной клетке юнит рисуется раньше здания."""
        game = self.game
        model = game.model
        model.developer = True
        model.units = [model.main_unit]
        cell = (30, 18)
        model.units[0].x, model.units[0].y = cell
        building = BuildingBlueprint("shelter", cell)
        building.height = 2
        building.built = True
        building.connected = False
        model.buildings = [building]
        model.explored.add(cell)
        model.visited.add(cell)

        self._toggle()
        game._center_iso_cell(*cell)
        self._redraw()

        order = {i: n for n, i in enumerate(game.canvas.find_all())}
        unit_items = self._items("unit", cell)
        building_items = self._items("building", cell)
        self.assertTrue(unit_items)
        self.assertTrue(building_items)
        self.assertLess(max(order[i] for i in unit_items),
                        min(order[i] for i in building_items))

    def test_click_selects_unit_on_uneven_terrain_at_any_zoom(self) -> None:
        """Клик по центру верхней грани выбирает юнита и на яме, и при зуме."""
        game = self.game
        model = game.model
        model.developer = True
        model.units = [model.main_unit]
        unit = model.main_unit
        cell = (32, 20)
        unit.x, unit.y = cell
        # Яма с ровными краями: её верхняя грань не перекрыта соседями.
        for gy in range(cell[1] - 4, cell[1] + 5):
            for gx in range(cell[0] - 4, cell[0] + 5):
                model.dug[gy][gx] = 2
        model.explored.add(cell)
        model.visited.add(cell)

        self._toggle()
        w = max(game.canvas.winfo_width(), 10)
        h = max(game.canvas.winfo_height(), 10)
        for zoom in (0.5, 1.0, 1.8):
            game._iso_zoom = zoom
            game._center_iso_cell(*cell)
            game._clamp_camera(w, h)
            m = game._iso_metrics(w, h)
            gz = iso.terrain_gz(model.dug[cell[1]][cell[0]]) + 1
            sx, sy = iso.world_to_screen(cell[0] + 0.5, cell[1] + 0.5, gz, m)
            self.assertEqual(game._cell_from_screen(sx, sy, w, h), cell, zoom)
            model.clear_selection()
            event = _Event(x=sx, y=sy)
            game._on_lmb_down(event)
            game._on_lmb_up(event)
            self.assertEqual(model.active_uid, unit.uid, zoom)
            self.assertIn(unit, model.selected_units(), zoom)

    def test_iso_toggle_keeps_center_cell_and_pan_stays_in_bounds(self) -> None:
        """I туда-обратно держит клетку в центре, панорама не выходит за карту."""
        game = self.game
        w = max(game.canvas.winfo_width(), 10)
        h = max(game.canvas.winfo_height(), 10)
        game.camera.center_on(32.5, 20.5)
        before = game._cell_from_screen(w / 2, h / 2, w, h)
        self.assertEqual(before, (32, 20))

        self._toggle()
        self.assertTrue(game.iso_view)
        self.assertEqual(game._cell_from_screen(w / 2, h / 2, w, h), before)
        self._redraw()

        m = game._iso_metrics(w, h)
        span = (w / (2 * m.hw) + h / (2 * m.hh)) / 2
        limits = []
        for size in (game.model.w, game.model.h):
            limits.append((span, size - span) if 2 * span <= size else (size / 2, size / 2))
        game.pan_camera(1, 1, step=10_000)
        for value, (low, high) in zip((game.camera.cx, game.camera.cy), limits):
            self.assertGreaterEqual(value, low - 1e-6)
            self.assertLessEqual(value, high + 1e-6)

        game._center_iso_cell(*before)
        game._clamp_camera(w, h)
        self._toggle()
        self.assertFalse(game.iso_view)
        self.assertEqual(game._cell_from_screen(w / 2, h / 2, w, h), before)


if __name__ == "__main__":
    unittest.main()
