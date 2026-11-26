"""Тесты изометрической проекции (stamina.lounge.iso)."""
from __future__ import annotations

import unittest

from stamina.terraformer_trainer import Camera
from stamina.lounge import iso


class IsoConstantsTest(unittest.TestCase):
    def test_zoom_constants_match_camera(self) -> None:
        self.assertEqual(iso.ZOOM_MIN, 0.5)
        self.assertEqual(iso.ZOOM_MAX, 3.0)
        self.assertEqual(iso.ZOOM_STEP, 1.25)


class ProjectionRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_world_to_screen_to_world_identity(self) -> None:
        """world -> screen -> world (gz=0) должен возвращать исходные координаты."""
        for gx, gy in [(0, 0), (10, 5), (25, 30), (99, 99), (50, 50)]:
            sx, sy = iso.world_to_screen(gx, gy, 0, self.m)
            gx2, gy2 = iso.screen_to_world(sx, sy, self.m)
            self.assertAlmostEqual(gx, gx2, places=6, msg=f"gx {gx} -> {gx2}")
            self.assertAlmostEqual(gy, gy2, places=6, msg=f"gy {gy} -> {gy2}")

    def test_tile_polygon_corners_order(self) -> None:
        """tile_polygon возвращает 8 координат в порядке: top, right, bottom, left."""
        poly = iso.tile_polygon(10, 10, 0, self.m)
        self.assertEqual(len(poly), 8)
        x0, y0, x1, y1, x2, y2, x3, y3 = poly
        # top выше bottom
        self.assertLess(y0, y2)
        # left левее right
        self.assertLess(x3, x1)


class PickTileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_pick_tile_inside_map(self) -> None:
        """pick_tile должен попадать в клетку под курсором."""
        gx, gy = 10, 15
        sx, sy = iso.world_to_screen(gx, gy, 0, self.m)
        picked = iso.pick_tile(sx, sy, self.m, 100, 100)
        self.assertEqual(picked, (gx, gy))

    def test_pick_tile_uses_floor_not_int(self) -> None:
        """Для отрицательных координат math.floor работает правильно, int — нет."""
        # Симулируем точку, которая попадает в клетку (-1, -1) в мировых координатах
        gx, gy = -1, -1
        sx, sy = iso.world_to_screen(gx, gy, 0, self.m)
        # pick_tile с boundary check должен вернуть None (вне карты)
        picked = iso.pick_tile(sx, sy, self.m, 100, 100)
        self.assertIsNone(picked)

    def test_pick_tile_outside_map_returns_none(self) -> None:
        picked = iso.pick_tile(-1000, -1000, self.m, 100, 100)
        self.assertIsNone(picked)
        picked = iso.pick_tile(10000, 10000, self.m, 100, 100)
        self.assertIsNone(picked)


class ZoomAtTest(unittest.TestCase):
    def test_zoom_in_then_out_returns_to_original(self) -> None:
        cam = Camera(100, 100)
        cam.cx, cam.cy = 50.0, 50.0
        zoom = 1.0
        w, h = 800, 600
        sx, sy = w / 2, h / 2  # центр экрана

        # zoom in
        zoom = iso.zoom_at(-1, sx, sy, w, h, cam, zoom)
        self.assertAlmostEqual(zoom, 1.25, places=6)

        # zoom out
        zoom = iso.zoom_at(1, sx, sy, w, h, cam, zoom)
        self.assertAlmostEqual(zoom, 1.0, places=6)

    def test_zoom_clamped_to_bounds(self) -> None:
        cam = Camera(100, 100)
        cam.cx, cam.cy = 50.0, 50.0
        w, h = 800, 600
        sx, sy = w / 2, h / 2

        zoom = iso.ZOOM_MAX
        zoom = iso.zoom_at(-1, sx, sy, w, h, cam, zoom)
        self.assertEqual(zoom, iso.ZOOM_MAX)

        zoom = iso.ZOOM_MIN
        zoom = iso.zoom_at(1, sx, sy, w, h, cam, zoom)
        self.assertEqual(zoom, iso.ZOOM_MIN)

    def test_zoom_at_keeps_world_point_under_cursor(self) -> None:
        """При зуме вокруг курсора世界点 должен оставаться под курсором."""
        cam = Camera(100, 100)
        cam.cx, cam.cy = 50.0, 50.0
        zoom = 1.0
        w, h = 800, 600
        sx, sy = 400, 300  # центр

        # Мировая точка под курсором до зума
        m = iso.tile_metrics(zoom, w, h, cam)
        wx_before, wy_before = iso.screen_to_world(sx, sy, m)

        zoom = iso.zoom_at(-1, sx, sy, w, h, cam, zoom)

        # Та же мировая точка должна быть под курсором после зума
        m2 = iso.tile_metrics(zoom, w, h, cam)
        wx_after, wy_after = iso.screen_to_world(sx, sy, m2)

        self.assertAlmostEqual(wx_before, wx_after, places=4)
        self.assertAlmostEqual(wy_before, wy_after, places=4)


class VisibleCellBoundsTest(unittest.TestCase):
    def test_bounds_cover_viewport(self) -> None:
        cam = Camera(100, 100)
        cam.cx, cam.cy = 50.0, 50.0
        zoom = 1.0
        w, h = 800, 600
        m = iso.tile_metrics(zoom, w, h, cam)

        min_gx, min_gy, max_gx, max_gy = iso.visible_cell_bounds(m, 100, 100, w, h)

        # Границы должны быть внутри карты
        self.assertGreaterEqual(min_gx, 0)
        self.assertGreaterEqual(min_gy, 0)
        self.assertLessEqual(max_gx, 99)
        self.assertLessEqual(max_gy, 99)

        # Область должна быть непустой
        self.assertLessEqual(min_gx, max_gx)
        self.assertLessEqual(min_gy, max_gy)

    def test_bounds_clamped_to_map_edges(self) -> None:
        cam = Camera(100, 100)
        cam.cx, cam.cy = 5.0, 5.0  # близко к краю
        zoom = 1.0
        w, h = 800, 600
        m = iso.tile_metrics(zoom, w, h, cam)

        min_gx, min_gy, max_gx, max_gy = iso.visible_cell_bounds(m, 100, 100, w, h)

        self.assertEqual(min_gx, 0)
        self.assertEqual(min_gy, 0)


class IsoIntegrationTest(unittest.TestCase):
    """Интеграционные тесты: проверяем, что trainer использует iso правильно."""

    def test_trainer_has_iso_view_property(self) -> None:
        from stamina.lounge.trainer import TrainerGame
        # Проверяем, что класс имеет свойство iso_view
        self.assertTrue(hasattr(TrainerGame, "iso_view"))
        # Проверяем, что это property
        self.assertIsInstance(getattr(TrainerGame, "iso_view", None), property)


if __name__ == "__main__":
    unittest.main()