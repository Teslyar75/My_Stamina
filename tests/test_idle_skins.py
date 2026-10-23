"""Заставка простоя (слайд-шоу + радио) — во всех семи скинах, с офлайн-набором ≥ 40 фото."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from stamina.idle import images

ROOT = Path(__file__).resolve().parents[1]
SKINS = ("spaceship", "steampunk", "bathyscaphe", "neon_city", "old_england", "scriptorium", "zen_garden")
FREE = ("CC0", "CC BY", "CC BY-SA", "Public domain", "No restrictions")


def _theme(skin: str) -> dict:
    return json.loads((ROOT / "stamina" / "themes" / f"{skin}.json").read_text(encoding="utf-8"))


class IdleSkinsTest(unittest.TestCase):
    def test_every_skin_has_slideshow_and_radio(self):
        for skin in SKINS:
            with self.subTest(skin=skin):
                t = _theme(skin)
                self.assertGreaterEqual(len(t["slideshow"]["topics"]), 15)
                self.assertTrue(t["radio"]["tags"])

    def test_offline_pool_is_big_and_exists(self):
        for skin in SKINS:
            with self.subTest(skin=skin):
                items = images.skin_fallback(skin)
                self.assertGreaterEqual(len(items), 40)
                self.assertTrue(all(Path(i["path"]).is_file() and i["source"] == "skin" for i in items))

    def test_every_offline_photo_is_credited_with_free_license(self):
        attr = (ROOT / "stamina" / "assets" / "idle_photos" / "ATTRIBUTION.md").read_text(encoding="utf-8")
        for skin in SKINS:
            folder = ROOT / "stamina" / "assets" / "idle_photos" / skin
            rows = json.loads((folder / "credits.json").read_text(encoding="utf-8"))
            listed = {r["file"] for r in rows}
            for p in folder.glob("*.jpg"):
                with self.subTest(file=p.name, skin=skin):
                    self.assertIn(f"idle_photos/{skin}/{p.name}", listed)
                    self.assertIn(f"`{skin}/{p.name}`", attr)
            for r in rows:
                with self.subTest(file=r["file"]):
                    self.assertTrue(r["license"].startswith(FREE), r["license"])
                    self.assertTrue(r["author"])
                    self.assertTrue(r["page"].startswith("https://commons.wikimedia.org/"))
