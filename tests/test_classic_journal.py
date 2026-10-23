"""Классический Бортжурнал: прокрутка до календаря активности и автосинхронизация Monkeytype."""
import os
import tempfile
import time
import tkinter as tk
import types
import unittest
from pathlib import Path


class ClassicJournalTest(unittest.TestCase):
    def setUp(self):
        from stamina import monkeytype, pilots
        monkeytype._sync.update(last=0.0, until=0.0, busy=False)
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        os.environ["APPDATA"] = self._tmp
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")

    def tearDown(self):
        from stamina import pilots
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        pilots.reset_root()

    def pump(self, s=0.5):
        t = time.time()
        while time.time() - t < s:
            self.app.update()

    def test_activity_map_reachable_at_720p(self):
        from stamina import portal_stats
        portal_stats.add_result({"ts": time.time(), "mode": "words", "mode2": 10, "wpm": 60, "raw": 62,
                                 "acc": 97, "consistency": 70, "time": 10})
        a = self.app
        a.geometry("1280x720+0+0")
        self.pump(1.0)              # стартовый экран (мостик) открывается отложенно
        a.show("log")
        log = a.screens["log"]
        self.pump(1.0)
        log.mt_panel._redraw()
        self.pump(0.5)
        self.assertTrue(log._bar_on)
        cv = log.mt_panel.cv
        self.assertTrue(cv.find_withtag("hm"))
        for _ in range(80):
            log._wheel(types.SimpleNamespace(widget=cv, num=5, delta=0))
        self.pump(0.3)
        self.assertGreater(log.scroll.yview()[0], 0.0)
        bottom = cv.winfo_rooty() + cv.bbox("hm")[3]
        self.assertLessEqual(bottom, log.scroll.winfo_rooty() + log.scroll.winfo_height())

    def test_manual_refresh_bypasses_interval_not_backoff(self):
        from stamina import monkeytype
        calls = []

        def fetch(url, headers=None):
            calls.append(url)
            return 200, {"data": {"name": "pilot", "personalBests": {}, "xp": 10}}
        p = Path(self._tmp) / "mt.json"
        self.assertTrue(monkeytype.auto_sync("pilot", fetch=fetch, path=p, threaded=False))
        self.assertFalse(monkeytype.auto_sync("pilot", fetch=fetch, path=p, threaded=False))
        self.assertTrue(monkeytype.auto_sync("pilot", fetch=fetch, path=p, threaded=False, force=True))
        monkeytype._sync["until"] = time.time() + 600
        self.assertFalse(monkeytype.auto_sync("pilot", fetch=fetch, path=p, threaded=False, force=True))
        self.assertGreater(monkeytype.backoff_left(), 500)
        self.assertFalse(monkeytype._sync["busy"])

    def test_error_resets_busy_and_reports(self):
        from stamina import monkeytype
        errs = []

        def bad(url, headers=None):
            raise OSError("boom")
        monkeytype.auto_sync("pilot", fetch=bad, path=Path(self._tmp) / "m.json", threaded=False,
                             force=True, on_error=errs.append)
        self.assertFalse(monkeytype._sync["busy"])
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()
