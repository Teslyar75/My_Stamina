"""Движок скинов: загрузка JSON, смена палитры, список тем."""

from __future__ import annotations

import unittest

from stamina import theme


class ThemeSkinsTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)

    def test_list_contains_all_skins(self) -> None:
        ids = {t["id"] for t in theme.list_themes()}
        for need in ("spaceship", "bathyscaphe", "steampunk", "scriptorium", "neon_city", "zen_garden"):
            self.assertIn(need, ids)

    def test_spaceship_matches_legacy_palette(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)
        self.assertEqual(theme.BG.upper(), "#03060C")
        self.assertEqual(theme.AMBER.upper(), "#FFB000")
        self.assertEqual(theme.CYAN.upper(), "#00E5FF")
        self.assertEqual(theme.theme_id(), "spaceship")

    def test_bathyscaphe_recolors_tokens(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)
        old_bg = theme.BG
        theme.load_theme("bathyscaphe", apply_ui=False)
        self.assertEqual(theme.theme_id(), "bathyscaphe")
        self.assertEqual(theme.BG.upper(), "#021219")
        self.assertNotEqual(theme.BG, old_bg)
        self.assertEqual(theme.c("accent").upper(), theme.AMBER.upper())

    def test_c_helper(self) -> None:
        theme.load_theme("neon_city", apply_ui=False)
        self.assertEqual(theme.c("error").upper(), "#FF3355")
        self.assertEqual(theme.c("ok").upper(), theme.GREEN.upper())

    def test_display_name_ru(self) -> None:
        theme.load_theme("steampunk", apply_ui=False)
        self.assertIn("Стимпанк", theme.theme_display_name(lang="ru"))


if __name__ == "__main__":
    unittest.main()
