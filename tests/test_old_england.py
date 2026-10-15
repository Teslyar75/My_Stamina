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
