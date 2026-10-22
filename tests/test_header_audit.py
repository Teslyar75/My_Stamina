"""ПРАВИЛА НАВИГАЦИИ alt: «ОБЗОР ▾» сразу справа от заголовка, одинаково везде (медленный)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOL = 3


@unittest.skipUnless(os.environ.get("STAMINA_SLOW_TESTS") == "1" and sys.platform == "win32", "slow GUI audit")
class HeaderRulesTest(unittest.TestCase):
    def test_overview_everywhere(self):
        out = Path(tempfile.mkdtemp())
        for skin in ("spaceship", "steampunk"):
            for size in ("800x700", "1280x720", "1920x1080"):
                subprocess.run([sys.executable, str(ROOT / "tools" / "header_audit.py"), skin, str(out), size],
                               check=True, timeout=600)
                res = json.loads((out / f"header_{skin}_{size}_M.json").read_text("utf-8"))
                ys = []
                for d in res["rows"]:
                    with self.subTest(skin=skin, size=size, zone=d["zone"]):
                        self.assertTrue(d["label_ok"], d["text"])
                        self.assertTrue(d["visible"])
                        self.assertTrue(d["in_window"], d)
                        self.assertLessEqual(abs(d["gap"] - res["gap_px"]), TOL, d)
                        self.assertTrue(d["menu_open"])
                        self.assertEqual(len(d["checked"]), 1, d["entries"])
                        self.assertEqual(d["errors"], [])
                        ys.append(d["y"])
                self.assertLessEqual(max(ys) - min(ys), TOL, ys)


if __name__ == "__main__":
    unittest.main()
