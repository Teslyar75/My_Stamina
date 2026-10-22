"""Real-click audit: the alt «ОБЗОР ▾» dropdown opens and stays mapped."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("STAMINA_SLOW_TESTS"),
                     "slow, Windows-only real-click audit")
class DropdownAuditTest(unittest.TestCase):
    def test_english_dropdown_opens(self):
        for skin in ("spaceship", "steampunk"):
            with self.subTest(skin=skin), tempfile.TemporaryDirectory() as out:
                subprocess.run([sys.executable, str(ROOT / "tools" / "dropdown_audit.py"),
                                "alt", skin, out, "1280x720"], cwd=ROOT, timeout=600,
                               check=False, capture_output=True)
                data = json.loads(next(Path(out).glob("*.json")).read_text("utf-8"))
                rows = {r["zone"]: r for r in data["rows"]}
                eng = rows["english"]
                self.assertLessEqual(eng["max_nav"], 6)
                vis = [d for d in eng["dropdowns"] if d["more_visible"]]
                self.assertTrue(vis)
                for d in vis:
                    self.assertTrue(d["popup_ok"], d.get("trace"))
                    self.assertIn("INIT", d.get("trace", ""))


if __name__ == "__main__":
    unittest.main()
