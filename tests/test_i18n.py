"""Язык интерфейса: перевод с фолбэком, сохранение выбора, целостность json."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from stamina import i18n

PH = re.compile(r"\{[^{}]*\}")


class I18nTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("ru")

    def test_default_ru_in_tests(self):
        self.assertEqual(i18n.language(), "ru")
        self.assertEqual(i18n.t("МОСТИК"), "МОСТИК")

    def test_translate_and_fallback(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("МОСТИК"), "BRIDGE")
        self.assertEqual(i18n.t("нет такой фразы"), "нет такой фразы")
        i18n.set_language("xx")
        self.assertEqual(i18n.language(), "ru")

    def test_save_language(self):
        from stamina import pilots
        with tempfile.TemporaryDirectory() as d:
            try:
                pilots.reset_root(Path(d))
                self.assertEqual(i18n.saved_language(), "")
                i18n.save_language("uk")
                self.assertEqual(i18n.saved_language(), "uk")
                with self.assertRaises(ValueError):
                    i18n.save_language("xx")
            finally:
                pilots.reset_root()

    def test_json_files(self):
        ru = json.loads((i18n.DIR / "ru.json").read_text(encoding="utf-8"))
        for lang in i18n.LANGS:
            if lang == "ru":
                continue
            tr = json.loads((i18n.DIR / f"{lang}.json").read_text(encoding="utf-8"))
            self.assertGreater(len(tr), len(ru) * 0.95, lang)
            for k, v in tr.items():
                self.assertIn(k, ru, lang)
                self.assertEqual(sorted(PH.findall(v)), sorted(PH.findall(k)), (lang, k))
                if "{0" in k:
                    try:
                        v.format(*range(9))
                    except (KeyError, IndexError, ValueError):
                        # Ключ сам не format-строка (например regex .{0,40}) — не проверяем.
                        try:
                            k.format(*range(9))
                        except (KeyError, IndexError, ValueError):
                            pass
                        else:
                            raise

    def test_check_tool(self):
        import subprocess
        import sys
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run([sys.executable, str(root / "tools" / "i18n_check.py")], capture_output=True,
                             text=True, encoding="utf-8", cwd=root)
        self.assertIn("ru.json", out.stdout)
        self.assertNotIn("нет в ru.json", out.stdout)


if __name__ == "__main__":
    unittest.main()
