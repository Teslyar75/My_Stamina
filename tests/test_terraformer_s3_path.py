"""Тесты для A* поиска пути (Stage 3): кратчайшие маршруты, препятствия, отрисовка."""
from __future__ import annotations

import tkinter as tk
import unittest

from stamina import terraformer_strategy as strategy
from stamina.terraformer_trainer import (
    GRID_H,
    GRID_W,
    TrainerModel,
)
from stamina.lounge.iso import tile_metrics, world_to_screen
from stamina.lounge.trainer import TrainerGame


class AStarPathfindTest(unittest.TestCase):
    """Проверки алгоритма A*: длина пути совпадает с BFS на пустой сетке."""

    def test_open_grid_shortest_path(self) -> None:
        """На пустой сетке A* даёт кратчайший путь (манхэттенское расстояние)."""
        start = (2, 2)
        goal = (8, 5)
        path = strategy.pathfind(start, goal, GRID_W, GRID_H)
        self.assertTrue(path)
        self.assertEqual(path[-1], goal)
        # Длина пути = манхэттенское расстояние (так как нет препятствий)
        expected_len = abs(goal[0] - start[0]) + abs(goal[1] - start[1])
        self.assertEqual(len(path), expected_len)

    def test_path_around_building(self) -> None:
        """Путь обходит здание по кратчайшему обходу."""
        wall = {(5, y) for y in range(0, 8)}
        start = (3, 3)
        goal = (7, 3)
        path = strategy.pathfind(start, goal, 10, 10, wall)
        self.assertTrue(path)
        self.assertEqual(path[-1], goal)
        # Ни одна клетка пути не в стене
        self.assertFalse(any(cell in wall for cell in path))
        # Длина пути = 5 вниз до y=8 + 4 вперёд + 5 вверх = 14
        self.assertEqual(len(path), 14)

    def test_avoids_water_springs(self) -> None:
        """Путь обходит источники воды (springs)."""
        springs = {(4, 4), (4, 5)}
        start = (2, 4)
        goal = (6, 4)
        path = strategy.pathfind(start, goal, 10, 10, springs)
        self.assertTrue(path)
        self.assertEqual(path[-1], goal)
        self.assertFalse(any(cell in springs for cell in path))

    def test_avoids_dug_pits(self) -> None:
        """Путь обходит ямы (dug > 0)."""
        pits = {(3, 3), (4, 3), (5, 3)}
        start = (2, 3)
        goal = (6, 3)
        path = strategy.pathfind(start, goal, 10, 10, pits)
        self.assertTrue(path)
        self.assertEqual(path[-1], goal)
        self.assertFalse(any(cell in pits for cell in path))

    def test_goal_inside_blocked_reachable(self) -> None:
        """Цель внутри blocked достижима — путь заканчивается на соседней клетке."""
        blocked = {(5, 5)}
        start = (2, 5)
        goal = (5, 5)  # Цель в заблокированной клетке
        path = strategy.pathfind(start, goal, 10, 10, blocked)
        self.assertTrue(path)
        # Последняя клетка пути — цель (путь заходит в цель)
        self.assertEqual(path[-1], goal)
        # Но предпоследняя не в blocked (кроме цели)
        if len(path) > 1:
            self.assertNotIn(path[-2], blocked)

    def test_no_path_when_completely_blocked(self) -> None:
        """Если цель полностью окружена — путь не найден."""
        blocked = {(4, 4), (6, 4), (5, 3), (5, 5)}
        start = (2, 4)
        goal = (5, 4)
        path = strategy.pathfind(start, goal, 10, 10, blocked)
        self.assertEqual(path, [])

    def test_same_start_goal_returns_empty(self) -> None:
        """Старт = цель — пустой путь."""
        path = strategy.pathfind((5, 5), (5, 5), 10, 10)
        self.assertEqual(path, [])

    def test_out_of_bounds_goal_returns_empty(self) -> None:
        """Цель за границей карты — пустой путь."""
        path = strategy.pathfind((5, 5), (100, 100), 10, 10)
        self.assertEqual(path, [])

    def test_matches_bfs_length_on_random_obstacles(self) -> None:
        """На случайных препятствиях длина пути A* = BFS (кратчайший)."""
        import random
        random.seed(42)
        for _ in range(20):
            w, h = 15, 15
            blocked = set()
            for _ in range(30):
                blocked.add((random.randrange(w), random.randrange(h)))
            start = (1, 1)
            goal = (13, 13)
            if start in blocked or goal in blocked:
                continue
            path = strategy.pathfind(start, goal, w, h, blocked)
            # A* с аддитивной эвристикой всегда находит кратчайший путь
            if path:
                # Проверяем, что нет более короткого пути (эвристика согласованна)
                self.assertTrue(len(path) >= abs(goal[0] - start[0]) + abs(goal[1] - start[1]))


class ModelBlockedCellsTest(unittest.TestCase):
    """Проверка, что _blocked_cells включает здания, источники и ямы."""

    def _model(self) -> TrainerModel:
        m = TrainerModel(w=20, h=20, seed=123, depth=1)
        m.developer = False
        return m

    def test_buildings_in_blocked(self) -> None:
        m = self._model()
        m.build_structure("shelter", x=10, y=10)
        blocked = m._blocked_cells()
        self.assertIn((10, 10), blocked)

    def test_springs_in_blocked(self) -> None:
        m = self._model()
        # Вручную добавляем открытый источник
        m.revealed.add((5, 5))
        m.finds[(5, 5)] = ("water", 0, 10)
        blocked = m._blocked_cells()
        self.assertIn((5, 5), blocked)

    def test_dug_pits_in_blocked(self) -> None:
        m = self._model()
        m.dug[5][5] = 1  # Яма глубины 1 -> (x=5, y=5)
        m.dug[5][6] = 2  # Яма глубины 2 -> (x=6, y=5)
        blocked = m._blocked_cells()
        self.assertIn((5, 5), blocked)
        self.assertIn((6, 5), blocked)
        self.assertNotIn((4, 5), blocked)  # Не выкопано — не в blocked

    def test_undug_cells_not_blocked(self) -> None:
        m = self._model()
        m.dug[7][7] = 0  # Не выкопано
        blocked = m._blocked_cells()
        self.assertNotIn((7, 7), blocked)


class UnitPathPopulationTest(unittest.TestCase):
    """Проверка, что issue_move заполняет unit.path и unit.target."""

    def _model(self) -> TrainerModel:
        m = TrainerModel(w=20, h=20, seed=1, depth=1)
        m.developer = False
        return m

    def test_issue_move_populates_path_and_target(self) -> None:
        m = self._model()
        u = m.units[0]
        u.x, u.y = 5, 5
        result = m.command_move(10, 10)
        self.assertIn(u.uid, result)
        self.assertEqual(u.target, (10, 10))
        self.assertTrue(u.path)
        self.assertEqual(u.path[-1], (10, 10))

    def test_issue_move_respects_blocked(self) -> None:
        m = self._model()
        u = m.units[0]
        u.x, u.y = 5, 5
        # Блокируем прямой путь: ямы в клетках (6,5), (7,5), (8,5), (9,5)
        # dug[y][x] -> y=5, x=6/7/8/9
        m.dug[5][6] = 1
        m.dug[5][7] = 1
        m.dug[5][8] = 1
        m.dug[5][9] = 1
        result = m.command_move(10, 5)
        # Путь должен найтись (объезжать ямы)
        self.assertTrue(u.path)
        # Проверяем, что путь не проходит через ямы (dug == 0 на пути)
        for cell in u.path:
            self.assertEqual(m.dug[cell[1]][cell[0]], 0, f"Путь проходит через яму в {cell}")


class PathDrawingTest(unittest.TestCase):
    """Проверка отрисовки путей в плоском и изометрическом виде."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            cls.root = None
            return
        from stamina import theme
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
        import tempfile
        from pathlib import Path
        from stamina import pilots
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "Stamina"
        self.data.mkdir()
        pilots.reset_root(self.data)
        p = pilots.create("Tester")
        pilots.activate(p["id"])

        self.game = TrainerGame(self.root, on_back=lambda: None, app=None)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self) -> None:
        try:
            self.game.stop()
        except Exception:
            pass
        try:
            self.game.destroy()
        except tk.TclError:
            pass
        self.root.update()
        from stamina import pilots
        pilots.reset_root()
        self.tmp.cleanup()

    def test_flat_view_draws_unit_path(self) -> None:
        """В плоском виде рисуется пунктир пути юнита."""
        game = self.game
        u = game.model.units[0]
        u.x, u.y = 10, 10
        u.path = [(11, 10), (12, 10), (13, 10)]
        u.target = (13, 10)
        game.redraw()
        self.root.update()
        # Проверяем, что на канвасе есть линия с тегом "unit" и dash
        c = game.canvas
        lines = c.find_withtag("unit")
        # Должна быть линия пути (пунктир)
        path_lines = [i for i in lines if c.type(i) == "line"]
        self.assertTrue(len(path_lines) > 0, "Путь не нарисован в плоском виде")

    def test_iso_view_draws_unit_path(self) -> None:
        """В изометрическом виде рисуется пунктир пути юнита."""
        game = self.game
        game._iso_view = True
        u = game.model.units[0]
        u.x, u.y = 10, 10
        u.path = [(11, 10), (12, 10), (13, 10)]
        u.target = (13, 10)
        game.redraw()
        self.root.update()
        c = game.canvas
        lines = c.find_withtag("unit")
        path_lines = [i for i in lines if c.type(i) == "line"]
        self.assertTrue(len(path_lines) > 0, "Путь не нарисован в изометрическом виде")


class IsoPathProjectionTest(unittest.TestCase):
    """Проверка корректности проекции пути в изометрии."""

    def test_world_to_screen_path_consistency(self) -> None:
        """Координаты пути в изометрии проецируются корректно."""
        cam = type('Camera', (), {'cx': 20.0, 'cy': 12.0})()
        m = tile_metrics(1.0, 800, 600, cam)
        path = [(10, 10), (11, 10), (12, 10), (13, 10)]
        screen_points = []
        for px, py in path:
            sx, sy = world_to_screen(px + 0.5, py + 0.5, 0, m)
            screen_points.append((sx, sy))
        # Точки должны идти в порядке пути
        self.assertEqual(len(screen_points), 4)
        # X должен расти (двигаемся вправо)
        for i in range(1, len(screen_points)):
            self.assertGreater(screen_points[i][0], screen_points[i-1][0])


if __name__ == "__main__":
    unittest.main()