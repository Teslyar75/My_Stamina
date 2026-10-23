"""«Параллельная вселенная»: в классике нет ни состояния, ни виджетов, ни таймеров alt.

Плюс быстрые проверки без окна: правило «глубинных окон» (рабочая страница сообщается
методом alt_working и не сворачивается) и предел ширины карточки.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stamina import alt_ui

ROOT = Path(__file__).resolve().parent.parent


class WorkingRuleTest(unittest.TestCase):
    def test_card_width_limits(self):
        self.assertEqual(alt_ui.card_width(1900, 840), 840)
        self.assertEqual(alt_ui.card_width(600, 840), 600)     # узкое окно — всё окно

    def test_working_page_contract(self):
        class Scr:
            def alt_working(self):
                return ("page", 840)
        self.assertEqual(alt_ui.working_page(Scr()), ("page", 840))
        self.assertIsNone(alt_ui.working_page(object()))

    def test_english_declares_work_pages(self):
        from stamina.english.screen import EnglishScreen
        self.assertEqual(set(EnglishScreen.WORK_PAGES), {"review", "practice", "book"})


@unittest.skipUnless(os.environ.get("STAMINA_SLOW_TESTS") and sys.platform == "win32",
                     "сборка кабины: STAMINA_SLOW_TESTS=1 (Windows)")
class ClassicIsolationTest(unittest.TestCase):
    def test_classic_has_no_alt_state(self):
        for skin in ("spaceship", "steampunk"):
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, "c.json")
                subprocess.run([sys.executable, str(ROOT / "tools" / "qa_skin_mix.py"), "cockpit", "classic", skin, out],
                               cwd=ROOT, timeout=240, capture_output=True)
                rep = json.loads(Path(out).read_text(encoding="utf-8"))
                self.assertEqual(rep["alt_attrs"], [], skin)
                self.assertEqual(rep["alt_compactors"], 0, skin)
                self.assertFalse(rep.get("alt_widgets"), skin)


if __name__ == "__main__":
    unittest.main()
