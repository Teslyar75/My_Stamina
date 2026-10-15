"""Скин «Старая Англия» (десктоп): голос, звания, звуки, фон; «Звездолёт» не тронут."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from stamina import i18n, missions, theme

ROOT = Path(__file__).resolve().parents[1]
PH = re.compile(r"\{[^}]*\}")


class OldEnglandTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)
        i18n.set_language("ru")

    def test_listed(self) -> None:
        self.assertIn("old_england", {t["id"] for t in theme.list_themes()})

    def test_starship_has_no_voice_and_t_unchanged(self) -> None:
        sp = json.loads((ROOT / "stamina/themes/spaceship.json").read_text(encoding="utf-8"))
        self.assertNotIn("voice", sp)
        for lang in ("ru", "uk", "en", "de"):
            i18n.set_language(lang)
            theme.load_theme("spaceship", apply_ui=False)
            before = {k: i18n.t(k) for k in ("ПИЛОТ", "СТАРТ", "Миссии")}
            theme.load_theme("old_england", apply_ui=False)
            theme.load_theme("spaceship", apply_ui=False)
            self.assertEqual(before, {k: i18n.t(k) for k in before})
            self.assertEqual(theme.skin_rank(missions.RANKS[0][1]), missions.RANKS[0][1])

    def test_voice_same_keys_and_placeholders(self) -> None:
        data = json.loads((ROOT / "stamina/themes/old_england.json").read_text(encoding="utf-8"))
        v = data["voice"]
        keys = set(v["ru"])
        self.assertGreater(len(keys), 100)
        for lang in ("uk", "en", "de"):
            self.assertEqual(set(v[lang]), keys, lang)
            for k in keys:
                self.assertEqual(sorted(PH.findall(v[lang][k])), sorted(PH.findall(k)), (lang, k))

    def test_voice_applies_and_reverts(self) -> None:
        theme.load_theme("old_england", apply_ui=False)
        data = theme.current()
        key = next(iter(data["voice"]["ru"]))
        self.assertEqual(i18n.t(key), data["voice"]["ru"][key])
        theme.load_theme("spaceship", apply_ui=False)
        self.assertNotEqual(i18n.t(key), data["voice"]["ru"][key])

    def test_skin_rank(self) -> None:
        theme.load_theme("old_england", apply_ui=False)
        base = missions.RANKS[0][1]
        self.assertNotEqual(theme.skin_rank(base), base)
        self.assertEqual(theme.skin_rank("нечто"), "нечто")

    def test_sounds_present(self) -> None:
        theme.load_theme("old_england", apply_ui=False)
        d = theme.skin_sound_dir()
        self.assertIsNotNone(d)
        for n in ("click", "error", "start", "bell"):
            self.assertTrue((d / f"{n}.wav").exists(), n)

    def test_london_fog_scene(self) -> None:
        from stamina.backgrounds import engine_for_theme
        from stamina.backgrounds.scenes import ENGINES
        theme.load_theme("old_england", apply_ui=False)
        self.assertEqual(engine_for_theme(), "london_fog")
        self.assertIn("london_fog", ENGINES)


if __name__ == "__main__":
    unittest.main()


class IdleLogicTest(unittest.TestCase):
    def test_is_idle_and_fade(self) -> None:
        from stamina.idle import fade_volume, is_idle
        self.assertFalse(is_idle(0, 10_000, 0))
        self.assertTrue(is_idle(0, 180, 3))
        self.assertFalse(is_idle(0, 179, 3))
        self.assertEqual(fade_volume(0, 6000, 30), 0)
        self.assertEqual(fade_volume(3000, 6000, 30), 15)
        self.assertEqual(fade_volume(9000, 6000, 30), 30)

    def test_pick_station_pinned_first(self) -> None:
        from stamina.idle import pick_station
        st = [{"name": "Jazz 24"}, {"name": "BBC Radio 3 HQ"}]
        self.assertEqual(pick_station(st, ["BBC Radio 3"])["name"], "BBC Radio 3 HQ")
        self.assertEqual(pick_station(st, ["nope"])["name"], "Jazz 24")
        self.assertIsNone(pick_station([], ["x"]))

    def test_settings_defaults_like_web(self) -> None:
        from stamina.idle import IDLE_MINUTES, settings_of
        self.assertEqual(IDLE_MINUTES, (0, 1, 3, 5, 10, 15))
        s = settings_of({"idle_minutes": 7})
        self.assertEqual(s, {"idle_minutes": 5, "idle_radio": True, "idle_after": "stop", "idle_provider": "auto"})

    def test_only_skins_with_slideshow(self) -> None:
        from stamina.idle.overlay import skin_slideshow
        theme.load_theme("spaceship", apply_ui=False)
        self.assertIsNone(skin_slideshow())
        theme.load_theme("old_england", apply_ui=False)
        self.assertTrue(skin_slideshow()["wikimedia"])
        theme.load_theme("spaceship", apply_ui=False)

    def test_fallback_images_offline(self) -> None:
        from stamina.idle.images import skin_fallback
        self.assertTrue(skin_fallback("old_england"))


class FogSceneRenderTest(unittest.TestCase):
    def tearDown(self) -> None:
        theme.load_theme("spaceship", apply_ui=False)

    def test_fog_and_newsprint_cards_render(self) -> None:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("no Pillow")
        from stamina.backgrounds.scenes import LondonFogScene
        theme.load_theme("old_england", apply_ui=False)
        s = LondonFogScene(400, 300, mode="light", theme_id="old_england")
        s.step(0.5)
        im = s.render()
        self.assertEqual(im.size, (400, 300))
        fs = s.frost_static()
        self.assertIsNotNone(fs)
        self.assertGreater(len(fs.getcolors(1 << 20) or []), 50)   # зерно печати — не плоская заливка
