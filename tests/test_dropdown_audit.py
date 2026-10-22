"""Real-click audit: alt dropdowns open on click and look/behave the same in every compartment."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# мостик: «ПОЛЁТ ▾» живёт в панели пульта, а не в шапке отсека (задокументированное исключение)
OWN_PLACE = {"bridge"}
X_TOL = 12


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("STAMINA_SLOW_TESTS"),
                     "slow, Windows-only real-click audit")
class DropdownAuditTest(unittest.TestCase):
    def _run(self, skin: str) -> dict:
        with tempfile.TemporaryDirectory() as out:
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "dropdown_audit.py"),
                                "alt", skin, out, "1280x720"], cwd=ROOT, timeout=600,
                               check=False, capture_output=True, text=True, errors="replace")
            js = list(Path(out).glob("*.json"))
            self.assertTrue(js, p.stderr[-2000:])
            return json.loads(js[0].read_text("utf-8"))

    def test_dropdowns_open_and_are_consistent(self):
        for skin in ("spaceship", "steampunk"):
            with self.subTest(skin=skin):
                data = self._run(skin)
                xs = {}
                for r in data["rows"]:
                    self.assertNotIn("error", r, r.get("error"))
                    self.assertLessEqual(r["max_nav"], 6, r["zone"])
                    for d in r["dropdowns"]:
                        if not d.get("kind"):
                            continue
                        msg = f'{skin}/{r["zone"]}: {d.get("text")} {d.get("trace", "")}'
                        self.assertTrue(d["shared"], msg)            # только общий RowCompactor+DropList
                        self.assertTrue(d["popup_ok"], msg)          # щелчок открыл список
                        self.assertTrue(d.get("below"), msg)         # под кнопкой
                        self.assertTrue(d.get("same_monitor"), msg)  # на том же мониторе
                        self.assertTrue(d.get("on_monitor"), msg)
                        self.assertTrue(d.get("on_top"), msg)        # реально виден (не под окном)
                        if d["kind"] == "section" and r["zone"] not in OWN_PLACE:
                            xs[r["zone"]] = d["x_rel"]
                eng = next(r for r in data["rows"] if r["zone"] == "english")
                self.assertTrue(any(d.get("kind") == "section" for d in eng["dropdowns"]))
                # список раздела - в одном и том же месте (левый край шапки) во всех отсеках
                self.assertLessEqual(max(xs.values()) - min(xs.values()), X_TOL, xs)


if __name__ == "__main__":
    unittest.main()
