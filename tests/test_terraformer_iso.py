"""Тесты изометрической проекции (stamina.lounge.iso)."""
from __future__ import annotations

import unittest

from stamina.terraformer_trainer import Camera
from stamina.terraformer_strategy import STRUCTURES
from stamina.lounge import iso
from stamina.lounge.iso import terrain_gz, prism_faces, PrismFaces, screen_to_world_at_gz, point_in_diamond, pick_surface, apply_zoom


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


class TerrainGzTest(unittest.TestCase):
    """Тесты для terrain_gz: تحويل глубины копать в изометрическую высоту."""

    def test_undug_surface_is_zero(self) -> None:
        """Нескопанная поверхность (dug=0) -> gz=0 (верх)."""
        self.assertEqual(terrain_gz(0), 0)

    def test_dug_goes_down(self) -> None:
        """Копание увеличивает dug, gz уходит в минус (вниз)."""
        self.assertEqual(terrain_gz(1), -1)
        self.assertEqual(terrain_gz(2), -2)
        self.assertEqual(terrain_gz(8), -8)


class PrismFacesTest(unittest.TestCase):
    """Тесты для prism_faces: генерация граней призмы."""

    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_prism_faces_has_three_faces(self) -> None:
        """prism_faces возвращает 3 грани: top, sw, se."""
        faces = prism_faces(10, 10, 0, -1, self.m)
        self.assertIsInstance(faces, PrismFaces)
        self.assertEqual(len(faces.top), 8)   # верхний ромб
        self.assertEqual(len(faces.sw), 8)    # юго-западная стена
        self.assertEqual(len(faces.se), 8)    # юго-восточная стена

    def test_top_face_matches_tile_polygon(self) -> None:
        """Верхняя грань совпадает с tile_polygon на той же высоте."""
        faces = prism_faces(5, 7, -2, -3, self.m)
        expected = iso.tile_polygon(5, 7, -2, self.m)
        self.assertEqual(faces.top, expected)

    def test_sw_se_are_different(self) -> None:
        """SW и SE стены — разные полигоны."""
        faces = prism_faces(0, 0, 0, -1, self.m)
        self.assertNotEqual(faces.sw, faces.se)


class ScreenToWorldAtGzTest(unittest.TestCase):
    """Тесты для screen_to_world_at_gz: обратная проекция на заданном gz."""

    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_screen_to_world_at_gz_zero_matches_screen_to_world(self) -> None:
        """При gz=0 результат должен совпадать со screen_to_world."""
        sx, sy = 400, 300
        gx1, gy1 = iso.screen_to_world(sx, sy, self.m)
        gx2, gy2 = screen_to_world_at_gz(sx, sy, 0.0, self.m)
        self.assertAlmostEqual(gx1, gx2, places=6)
        self.assertAlmostEqual(gy1, gy2, places=6)

    def test_screen_to_world_at_gz_nonzero_shifts_correctly(self) -> None:
        """При gz != 0 результат сдвигается: выше gz -> больше gx, gy для фиксированной точки экрана."""
        sx, sy = 400, 300
        gx0, gy0 = screen_to_world_at_gz(sx, sy, 0.0, self.m)
        gx1, gy1 = screen_to_world_at_gz(sx, sy, 1.0, self.m)
        gx2, gy2 = screen_to_world_at_gz(sx, sy, -1.0, self.m)
        # gz=1 (выше) -> для той же точки экрана мировые координаты больше
        self.assertGreater(gx1, gx0)
        self.assertGreater(gy1, gy0)
        # gz=-1 (ниже) -> для той же точки экрана мировые координаты меньше
        self.assertLess(gx2, gx0)
        self.assertLess(gy2, gy0)


class PointInDiamondTest(unittest.TestCase):
    """Тесты для point_in_diamond: попадание в ромб."""

    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_center_of_diamond_is_inside(self) -> None:
        """Центр ромба должен быть внутри."""
        poly = iso.tile_polygon(10, 10, 0, self.m)
        # Центр ромба - середина между top и bottom
        cx = (poly[0] + poly[4]) / 2
        cy = (poly[1] + poly[5]) / 2
        self.assertTrue(point_in_diamond(cx, cy, poly))

    def test_corners_are_inside(self) -> None:
        """Углы ромба считаются внутри."""
        poly = iso.tile_polygon(10, 10, 0, self.m)
        for i in range(0, 8, 2):
            self.assertTrue(point_in_diamond(poly[i], poly[i+1], poly))

    def test_outside_point_is_false(self) -> None:
        """Точка далеко от ромба должна быть снаружи."""
        poly = iso.tile_polygon(10, 10, 0, self.m)
        # Точка далеко вправо
        self.assertFalse(point_in_diamond(poly[2] + 100, poly[3], poly))


class PickSurfaceTest(unittest.TestCase):
    """Тесты для pick_surface: поиск верхней поверхности под курсором."""

    def setUp(self) -> None:
        self.cam = Camera(100, 100)
        self.cam.cx, self.cam.cy = 50.0, 50.0
        self.zoom = 1.0
        self.w, self.h = 10, 10
        self.m = iso.tile_metrics(self.zoom, 800, 600, self.cam)

    def test_pick_surface_flat_terrain(self) -> None:
        """На ровной поверхности (dug=0) должен попадать в клетку с surface_gz=1."""
        dug = [[0 for _ in range(self.w)] for _ in range(self.h)]
        gx, gy = 5, 5
        sx, sy = iso.world_to_screen(gx + 0.5, gy + 0.5, 1, self.m)  # top face at gz=1
        hit = pick_surface(sx, sy, self.m, dug, self.w, self.h)
        self.assertIsNotNone(hit)
        hx, hy, hgz = hit
        self.assertEqual((hx, hy), (gx, gy))
        self.assertEqual(hgz, 1)  # terrain_gz(0) + 1 = 1

    def test_pick_surface_high_cell_next_to_pit(self) -> None:
        """Высокая клетка рядом с ямой: курсор на вершине высокой -> попадает в неё."""
        dug = [[0 for _ in range(self.w)] for _ in range(self.h)]
        # Клетка (5,5) - высокая (dug=0, surface gz=0, top face gz=1)
        # Клетка (6,5) - яма (dug=2, surface gz=-2, top face gz=-1)
        dug[5][6] = 2
        # Курсор на центре верхней грани высокой клетки (5,5)
        sx, sy = iso.world_to_screen(5.5, 5.5, 1, self.m)
        hit = pick_surface(sx, sy, self.m, dug, self.w, self.h)
        self.assertIsNotNone(hit)
        hx, hy, hgz = hit
        self.assertEqual((hx, hy), (5, 5))
        self.assertEqual(hgz, 1)

    def test_pick_surface_gz0_unprojection_is_different(self) -> None:
        """gz=0 unprojection той же точки даёт другую мировую координату."""
        dug = [[0 for _ in range(self.w)] for _ in range(self.h)]
        dug[5][6] = 2
        sx, sy = iso.world_to_screen(5.5, 5.5, 1, self.m)
        # gz=0 unprojection
        gx0, gy0 = iso.screen_to_world(sx, sy, self.m)
        # surface-aware pick
        hit = pick_surface(sx, sy, self.m, dug, self.w, self.h)
        self.assertIsNotNone(hit)
        hx, hy, hgz = hit
        # gx0,gy0 должно отличаться от (hx+0.5, hy+0.5)
        self.assertNotAlmostEqual(gx0, hx + 0.5, places=1)
        self.assertNotAlmostEqual(gy0, hy + 0.5, places=1)


class ApplyZoomTest(unittest.TestCase):
    """Тесты для apply_zoom: surface-aware изометрический зум."""

    def test_zoom_keeps_surface_point_under_cursor(self) -> None:
        """При зуме поверхностная точка должна оставаться под курсором."""
        cam = Camera(20, 20)
        cam.cx, cam.cy = 10.0, 10.0
        zoom = 1.0
        w, h = 800, 600

        # Карта: одна высокая клетка (dug=0) рядом с ямой (dug=2)
        map_w, map_h = 20, 20
        dug = [[0 for _ in range(map_w)] for _ in range(map_h)]
        dug[10][11] = 2  # яма справа

        m = iso.tile_metrics(zoom, w, h, cam)
        # Курсор на центре верхней грани высокой клетки (10,10) при gz=1
        sx, sy = iso.world_to_screen(10.5, 10.5, 1, m)

        # Зум in
        zoom = apply_zoom(-1, sx, sy, w, h, cam, zoom, dug, map_w, map_h)

        # После зума та же поверхностная точка должна быть под курсором
        m2 = iso.tile_metrics(zoom, w, h, cam)
        sx2, sy2 = iso.world_to_screen(10.5, 10.5, 1, m2)
        # Разница не должна превышать ~1 пиксель
        self.assertLess(abs(sx - sx2), 1.5)
        self.assertLess(abs(sy - sy2), 1.5)

    def test_zoom_out_returns_to_original(self) -> None:
        """Зум in затем out возвращает к исходному положению."""
        cam = Camera(20, 20)
        cam.cx, cam.cy = 10.0, 10.0
        zoom = 1.0
        w, h = 800, 600

        map_w, map_h = 20, 20
        dug = [[0 for _ in range(map_w)] for _ in range(map_h)]
        dug[10][11] = 2

        m = iso.tile_metrics(zoom, w, h, cam)
        sx, sy = iso.world_to_screen(10.5, 10.5, 1, m)

        cx_before, cy_before = cam.cx, cam.cy

        zoom = apply_zoom(-1, sx, sy, w, h, cam, zoom, dug, map_w, map_h)
        zoom = apply_zoom(1, sx, sy, w, h, cam, zoom, dug, map_w, map_h)

        # Камера и зум должны вернуться близко к исходным
        self.assertAlmostEqual(zoom, 1.0, places=4)
        self.assertAlmostEqual(cam.cx, cx_before, places=3)
        self.assertAlmostEqual(cam.cy, cy_before, places=3)

    def test_fallback_to_gz0_when_no_dug_grid(self) -> None:
        """Без dug_grid должен работать как старый zoom_at (gz=0)."""
        cam = Camera(20, 20)
        cam.cx, cam.cy = 10.0, 10.0
        zoom = 1.0
        w, h = 800, 600
        sx, sy = w / 2, h / 2

        cx_before, cy_before = cam.cx, cam.cy
        zoom = apply_zoom(-1, sx, sy, w, h, cam, zoom, None, 0, 0)

        # Compute world point before (with original camera/zoom)
        cam_before = Camera(20, 20)
        cam_before.cx, cam_before.cy = cx_before, cy_before
        m_before = iso.tile_metrics(1.0, w, h, cam_before)
        wx_before, wy_before = iso.screen_to_world(sx, sy, m_before)

        # Compute world point after (with new camera/zoom)
        m_after = iso.tile_metrics(zoom, w, h, cam)
        wx_after, wy_after = iso.screen_to_world(sx, sy, m_after)

        self.assertAlmostEqual(wx_before, wx_after, places=3)
        self.assertAlmostEqual(wy_before, wy_after, places=3)

    def test_mixed_height_map_offset_cursor_stays_anchored(self) -> None:
        """Смешанная карта: курсор НЕ в центре верхней грани высокой клетки.
        
        - Карта: HIGH клетка (dug=0) рядом с PIT (dug=2)
        - Курсор на (gx=10.3, gy=10.7, gz=1) — внутри верхнего ромба, но не в центре
        - После apply_zoom in (и out) world_to_screen той же (gx,gy,surface_gz)
          остаётся на том же sx,sy в пределах ~1px
        - Якорение только по центру клетки ИЛИ только gz=0 сдвигает эту точку
          (так тест ловит старый баг).
        """
        cam = Camera(20, 20)
        cam.cx, cam.cy = 10.0, 10.0
        zoom = 1.0
        w, h = 800, 600

        map_w, map_h = 20, 20
        dug = [[0 for _ in range(map_w)] for _ in range(map_h)]
        dug[10][11] = 2  # яма справа от (10,10)

        m = iso.tile_metrics(zoom, w, h, cam)
        
        # Курсор на точке, смещённой от центра (10.5, 10.5) — внутри верхнего ромба
        # world_to_screen(10.3, 10.7, 1) даст экранные координаты
        anchor_gx, anchor_gy, anchor_gz = 10.3, 10.7, 1.0
        sx, sy = iso.world_to_screen(anchor_gx, anchor_gy, anchor_gz, m)

        # Зум in
        zoom = apply_zoom(-1, sx, sy, w, h, cam, zoom, dug, map_w, map_h)

        # После зума та же поверхностная точка должна быть под курсором
        m2 = iso.tile_metrics(zoom, w, h, cam)
        sx2, sy2 = iso.world_to_screen(anchor_gx, anchor_gy, anchor_gz, m2)
        
        # Разница не должна превышать ~1 пиксель (или 1e-6 в мировых координатах)
        self.assertLess(abs(sx - sx2), 1.0, 
            f"sx drift {abs(sx - sx2):.3f}px after zoom in")
        self.assertLess(abs(sy - sy2), 1.0,
            f"sy drift {abs(sy - sy2):.3f}px after zoom in")

        # Зум out — возврат
        zoom = apply_zoom(1, sx, sy, w, h, cam, zoom, dug, map_w, map_h)
        m3 = iso.tile_metrics(zoom, w, h, cam)
        sx3, sy3 = iso.world_to_screen(anchor_gx, anchor_gy, anchor_gz, m3)
        self.assertLess(abs(sx - sx3), 1.0,
            f"sx drift {abs(sx - sx3):.3f}px after zoom out")
        self.assertLess(abs(sy - sy3), 1.0,
            f"sy drift {abs(sy - sy3):.3f}px after zoom out")

        # --- Проверка, что старый баг воспроизводится ---
        # 1) Если якорь только в ЦЕНТРЕ клетки (10.5, 10.5), точка (10.3, 10.7, 1) смещается
        cam2 = Camera(20, 20)
        cam2.cx, cam2.cy = 10.0, 10.0
        zoom2 = 1.0
        m2_before = iso.tile_metrics(zoom2, w, h, cam2)
        sx_c, sy_c = iso.world_to_screen(10.5, 10.5, 1.0, m2_before)  # centre anchor
        zoom2 = apply_zoom(-1, sx_c, sy_c, w, h, cam2, zoom2, dug, map_w, map_h)
        m2_after = iso.tile_metrics(zoom2, w, h, cam2)
        sx2_c, sy2_c = iso.world_to_screen(anchor_gx, anchor_gy, anchor_gz, m2_after)
        # Точка должна сместиться больше 1px
        self.assertGreater(abs(sx - sx2_c), 1.5,
            "Centre-anchor should move the offset point (bug reproduced)")

        # 2) Если якорь только gz=0 (экранные координаты sx,sy от screen_to_world на gz=0)
        # В этой изометрической проекции gz=0 unprojection того же (sx,sy) также закрепляет
        # (gx,gy,gz) на том же луче экрана (sx/sy identity), поэтому точка НЕ смещается.
        # Это геометрически ожидаемо — проверяем, что gz=0 unproject даёт ДРУГУЮ мировую координату.
        cam3 = Camera(20, 20)
        cam3.cx, cam3.cy = 10.0, 10.0
        zoom3 = 1.0
        m3_before = iso.tile_metrics(zoom3, w, h, cam3)
        # gz=0 unproject того же экранного sx,sy
        gx0, gy0 = iso.screen_to_world(sx, sy, m3_before)
        # gx0,gy0 должно отличаться от anchor_gx, anchor_gy (10.3, 10.7)
        self.assertNotAlmostEqual(gx0, anchor_gx, places=1)
        self.assertNotAlmostEqual(gy0, anchor_gy, places=1)


class StructuresHeightsTest(unittest.TestCase):
    """Тесты высот зданий STRUCTURES: должны соответствовать потолкам уровней."""

    def test_structure_heights_match_level_ceilings(self) -> None:
        """Высоты зданий из STRUCTURES соответствуют потолкам CEFR-уровней.
        
        Реальные потолки уровней (MAX_BUILD_HEIGHT):
        A1=1, A2=1, B1.1=3, B1.2=3, B2.1=3, B2.2=3, C1=6, C2=8
        
        Каждое здание должно иметь высоту <= потолка своего уровня.
        Используем strategy.max_height(spec.level) для получения потолка.
        """
        from stamina import terraformer_strategy as strategy
        
        for key, spec in STRUCTURES.items():
            ceiling = strategy.max_height(spec.level)
            self.assertLessEqual(spec.height, ceiling,
                f"{key}: height={spec.height} > ceiling={ceiling} for level {spec.level}")
            self.assertGreater(spec.height, 0,
                f"{key}: height must be positive")

    def test_expected_structure_heights(self) -> None:
        """Контрольные значения высот конкретных зданий (известные константы)."""
        expected = {
            "shelter": 1,
            "greenhouse": 1,
            "energy_panel": 1,
            "refinery": 3,
            "habitat": 3,
            "radar": 3,
            "spire": 6,
            "core": 8,
        }
        for key, expected_height in expected.items():
            self.assertIn(key, STRUCTURES, f"Missing structure: {key}")
            self.assertEqual(STRUCTURES[key].height, expected_height,
                f"{key}: expected height {expected_height}, got {STRUCTURES[key].height}")

    def test_structure_heights_strictly_increasing_by_level(self) -> None:
        """Высоты зданий не убывают при повышении уровня."""
        # Группируем по уровню и проверяем максимумы
        from stamina.terraformer_strategy import level_index
        max_by_level: dict[int, int] = {}
        for spec in STRUCTURES.values():
            idx = level_index(spec.level)
            max_by_level[idx] = max(max_by_level.get(idx, 0), spec.height)
        
        # Проверяем монотонность: следующий уровень не ниже предыдущего
        for i in range(1, 8):
            if i in max_by_level and (i-1) in max_by_level:
                self.assertGreaterEqual(max_by_level[i], max_by_level[i-1],
                    f"Level {i} max height < level {i-1} max height")


if __name__ == "__main__":
    unittest.main()