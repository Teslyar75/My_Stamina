"""ALT UI: вид интерфейса «Пульт-кабина» (stamina/alt_ui.py)."""
import json
import tkinter as tk
import unittest
from pathlib import Path

from stamina import alt_ui, nav, storage

ROOT = Path(__file__).resolve().parents[1]
# Скины со своим профилем ALT UI: id скина -> стиль рамки (профиль = id скина).
NEW_SKINS: dict[str, str] = {"zen_garden": "brush", "scriptorium": "illumin", "old_england": "engraved", "neon_city": "neon", "bathyscaphe": "porthole"}


class TestAltSettings(unittest.TestCase):
    def test_default_is_classic(self):
        self.assertEqual(storage.DEFAULT_SETTINGS["ui_layout"], "classic")
        self.assertEqual(alt_ui.layout_of({}), "classic")
        self.assertEqual(alt_ui.layout_of({"ui_layout": "мусор"}), "classic")
        self.assertEqual(alt_ui.layout_of({"ui_layout": "alt"}), "alt")

    def test_profiles(self):
        self.assertEqual(alt_ui.profile_id("spaceship", {}), "starship")
        self.assertEqual(alt_ui.profile_id("steampunk", {}), "steampunk")
        self.assertEqual(alt_ui.profile_id("no_such_skin", {}), "generic")
        self.assertEqual(alt_ui.profile_id(None, {"id": "x", "alt_ui": {"profile": "steampunk"}}), "steampunk")
        for tid, prof in (("spaceship", "starship"), ("steampunk", "steampunk")):
            data = json.loads((ROOT / "stamina" / "themes" / f"{tid}.json").read_text(encoding="utf-8"))
            self.assertEqual(alt_ui.profile_id(None, data), prof)

    def test_every_zone_has_glyph_and_compartment(self):
        for prof in alt_ui.PROFILES:
            for z in nav.ZONE_ORDER:
                self.assertNotEqual(alt_ui.glyph(prof, z), "•", (prof, z))
        for prof in ("starship", "steampunk"):
            self.assertEqual(set(alt_ui.COMPARTMENTS[prof]), set(nav.ZONE_ORDER))

    def test_frame_styles(self):
        self.assertEqual(alt_ui.frame_style("starship", {}), "hud")
        self.assertEqual(alt_ui.frame_style("steampunk", {}), "brass")
        self.assertEqual(alt_ui.frame_style("generic", {}), "plain")
        self.assertEqual(alt_ui.frame_style("generic", {"alt_ui": {"frame": "brass"}}), "brass")

    def test_i18n_keys(self):
        for lang in ("ru", "uk", "en", "de"):
            d = json.loads((ROOT / "stamina" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
            for prof in alt_ui.COMPARTMENTS.values():
                for title, _ in prof.values():
                    self.assertIn(title, d, (lang, title))


class TestAltWidgets(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_draw_all_profiles(self):
        for prof in alt_ui.PROFILES:
            b = alt_ui.AltNavButton(self.root, "МОСТИК", profile=prof, glyph_char=alt_ui.glyph(prof, "bridge"),
                                    width=170, height=38)
            b.place(x=0, y=0, width=170, height=38)
            b._draw(); b.set_active(True); b._draw(); b.set_narrow(True); b._draw()
            fr = alt_ui.wrap(self.root, prof, title="T")
            for side, cv in fr._edges.items():
                cv._size = None
                ev = type("E", (), {"width": 300, "height": 12} if side in ("top", "bottom") else {"width": 12, "height": 300})
                fr._on_edge(side, ev)
                self.assertTrue(cv.find_all() or prof == "generic", (prof, side))
            ban = alt_ui.CompartmentBanner(self.root, prof, transition=False)
            ban._size = (900, 64)
            for z in nav.ZONE_ORDER:
                ban.set_zone(z)
            alt_ui.GaugeCanvas(self.root, prof)._on_size(type("E", (), {"width": 150, "height": 150}))

    def test_composer_row_is_not_compacted(self):
        row = tk.Frame(self.root, bg="#000000")
        row._alt_nocompact = True
        for i in range(5):
            alt_ui.HudButton(row, f"B{i}", height=30).pack(side=tk.LEFT)
        alt_ui.compact(row, "starship")
        self.assertFalse(hasattr(row, "_alt_row"))

    def test_airlock_finishes(self):
        ban = alt_ui.CompartmentBanner(self.root, "starship")
        ban._size = (600, 64)
        ban.set_zone("bridge")
        ban.set_zone("radio")
        import time
        t0 = time.time()
        while ban._job is not None and time.time() - t0 < 3:
            self.root.update()
        self.assertIsNone(ban._job)
        self.assertEqual(ban.find_withtag("door"), ())


class TestAltWallpapers(unittest.TestCase):
    def test_every_compartment_has_wallpaper(self):
        for prof in ("starship", "steampunk"):
            for z in nav.ZONE_ORDER:
                self.assertIsNotNone(alt_ui.wallpaper_path(prof, z), (prof, z))
        self.assertIsNone(alt_ui.wallpaper_path("generic", "bridge"))

    def test_cover_and_dim(self):
        im = alt_ui._wall_image("steampunk", "radio", 640, 300, 0.5)
        if im is None:
            self.skipTest("нет Pillow")
        self.assertEqual(im.size, (640, 300))
        self.assertIsNone(alt_ui._wall_image("generic", "radio", 640, 300, 0.5))

    def test_widget_fallback(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        try:
            body = tk.Frame(root, bg="#000000")
            wp = alt_ui.Wallpaper(body, "generic")
            wp.size = (300, 200); wp.set_zone("bridge"); wp._paint()
            self.assertIsNone(wp.photo)
            wp2 = alt_ui.Wallpaper(body, "starship")
            wp2.size = (300, 200); wp2.zone = "orion"; wp2._paint()
            self.assertTrue(wp2.available)
        finally:
            root.destroy()

class TestSkinAltProfiles(unittest.TestCase):
    """Каждый скин со своим профилем: своя рамка и обои-слайдшоу в каждом отсеке."""

    def test_profile_and_frame(self):
        for skin, style in NEW_SKINS.items():
            self.assertTrue((ROOT / "stamina" / "themes" / f"{skin}.json").is_file(), skin)
            self.assertEqual(alt_ui.profile_id(skin, {}), skin)
            self.assertEqual(alt_ui.frame_style(skin, {}), style)
            self.assertIn(style, alt_ui.FRAME_STYLES)
            self.assertTrue(hasattr(alt_ui.SkinFrame, f"_edge_{style}"), style)
            self.assertTrue(hasattr(alt_ui.OrnamentBand, f"_draw_{skin}"), skin)
            self.assertTrue(hasattr(alt_ui.AltNavButton, f"_nav_{skin}"), skin)

    def test_every_zone_has_wallpapers(self):
        attr = (ROOT / "stamina" / "assets" / "alt_wallpapers" / "ATTRIBUTION.md").read_text(encoding="utf-8")
        for skin in NEW_SKINS:
            for z in nav.ZONE_ORDER:
                ps = alt_ui.wallpaper_paths(skin, z)
                self.assertGreaterEqual(len(ps), 2, (skin, z))   # слайдшоу: несколько кадров
                for p in ps:
                    self.assertIn(f"`{skin}/{p.name}`", attr, p)


if __name__ == "__main__":
    unittest.main()
