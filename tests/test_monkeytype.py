"""Monkeytype: импорт прогресса (только чтение), HTTP подменён."""
import json
import tempfile
import unittest
from pathlib import Path

from stamina import monkeytype as mt

PROFILE = {"name": "pilot", "typingStats": {"completedTests": 100, "startedTests": 120, "timeTyping": 7200},
           "streak": 5, "maxStreak": 9,
           "personalBests": {"time": {"15": [{"wpm": 60.4, "acc": 95}, {"wpm": 70.2, "acc": 97, "language": "english"}]},
                             "words": {"10": [{"wpm": 110, "acc": 100}]}},
           "allTimeLbs": {"time": {"15": {"english": {"rank": 1234, "count": 9999}}}},
           "testActivity": {"testsByDays": [1, 0, 3], "lastDay": 1792713600000}}


class Fake:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        for part, resp in self.routes.items():
            if part in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return 404, {}


class MonkeytypeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "cache.json"

    def test_profile_without_key(self):
        f = Fake({"/users/pilot/profile": (200, {"data": PROFILE})})
        data = mt.refresh("pilot", "", fetch=f, path=self.tmp)
        s = data["summary"]
        self.assertEqual((s["tests"], s["started"], s["hours"], s["streak"]), (100, 120, 2.0, 5))
        pb = {(p["mode"], p["mode2"]): p for p in s["pbs"]}
        self.assertEqual(pb[("time", "15")]["wpm"], 70.2)
        self.assertIsNone(pb[("time", "120")]["wpm"])
        self.assertEqual(s["lbs"][0]["rank"], 1234)
        self.assertEqual(s["activity"][-1], ("2026-10-23", 3))
        self.assertEqual(len(f.calls), 1)
        self.assertNotIn("Authorization", f.calls[0][1])
        self.assertTrue(self.tmp.exists())
        self.assertEqual(mt.load_cache(self.tmp)["summary"]["tests"], 100)

    def test_apekey_results_header(self):
        f = Fake({"/profile": (200, {"data": PROFILE}), "/results": (200, {"data": [{"wpm": 80}, {"wpm": 75.5}]})})
        data = mt.refresh("pilot", "SECRET", fetch=f, path=self.tmp)
        self.assertEqual(data["summary"]["recent"], [80.0, 75.5])
        hdr = [h for u, h in f.calls if "/results" in u][0]
        self.assertEqual(hdr["Authorization"], "ApeKey SECRET")
        # ключ не попадает в кэш
        self.assertNotIn("SECRET", self.tmp.read_text(encoding="utf-8"))

    def test_key_errors_do_not_break_profile(self):
        for code in (470, 471, 472, 479):
            f = Fake({"/profile": (200, {"data": PROFILE}), "/results": (code, {"message": "x"})})
            data = mt.refresh("pilot", "K", fetch=f, path=self.tmp)
            self.assertTrue(data["warning"])
            self.assertEqual(data["summary"]["tests"], 100)

    def test_errors(self):
        with self.assertRaises(mt.MonkeytypeError):
            mt.refresh("", fetch=Fake({}), path=self.tmp)
        with self.assertRaisesRegex(mt.MonkeytypeError, "не найден"):
            mt.refresh("nobody", fetch=Fake({}), path=self.tmp)
        with self.assertRaisesRegex(mt.MonkeytypeError, "офлайн"):
            mt.refresh("pilot", fetch=Fake({"/profile": OSError("down")}), path=self.tmp)
        self.assertIn("Лимит", mt.describe_status(479))

    def test_no_posting(self):
        src = Path(mt.__file__).read_text(encoding="utf-8")
        self.assertNotIn("method=\"POST\"", src)
        self.assertNotIn("data=", src.split("def _default_fetch")[1].split("def ")[0])


if __name__ == "__main__":
    unittest.main()
