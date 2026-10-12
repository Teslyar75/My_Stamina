"""Фоны скинов: фабрика сцен и контракт LivingSpace."""

from __future__ import annotations

import unittest

from stamina import theme
from stamina.backgrounds import engine_for_theme, make_scene


@unittest.skipUnless(__import__("importlib").util.find_spec("PIL"), "Pillow required")
class SkinBackgroundsTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)

    def test_spaceship_uses_living_space_scene(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)
        self.assertEqual(engine_for_theme(), "living_space")
        from stamina.living_space import Scene
        sc = make_scene(400, 300, "light")
        self.assertIsInstance(sc, Scene)

    def test_each_skin_engine(self) -> None:
        expect = {
            "bathyscaphe": "sonar",
            "steampunk": "gears",
            "scriptorium": "candles",
            "neon_city": "city_rain",
            "zen_garden": "zen",
        }
        for tid, eng in expect.items():
            theme.load_theme(tid, apply_ui=False)
            self.assertEqual(engine_for_theme(), eng, tid)
            sc = make_scene(320, 240, "light")
            self.assertEqual(getattr(sc, "engine", ""), eng)
            sc.step(0.05, 1.0)
            im = sc.render()
            self.assertIsNotNone(im)
            self.assertEqual(im.size, (320, 240))
            frost = sc.frost_frame()
            self.assertIsNotNone(frost)

    def test_sonar_ping(self) -> None:
        theme.load_theme("bathyscaphe", apply_ui=False)
        sc = make_scene(200, 200, "full")
        self.assertTrue(hasattr(sc, "ping"))
        sc.ping()
        sc.step(0.1, 1.2)
        self.assertGreaterEqual(len(sc.pings), 1)


if __name__ == "__main__":
    unittest.main()
