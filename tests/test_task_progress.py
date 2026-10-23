import os
import tempfile
import time
import unittest

from stamina import task_progress as tp


class TaskProgressTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("STAR_TYPING_TASKS_DIR")
        os.environ["STAR_TYPING_TASKS_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STAR_TYPING_TASKS_DIR", None)
        else:
            os.environ["STAR_TYPING_TASKS_DIR"] = self.old
        self.tmp.cleanup()

    def test_weighted_percent(self):
        tp.plan("a", "Склейка", ["причина:2", "правило:3", "тесты"])
        tp.step("a", "причина")
        self.assertAlmostEqual(tp.active()[0]["percent"], 100 * 2 / 6)
        tp.step("a", 3)
        self.assertAlmostEqual(tp.active()[0]["percent"], 50.0)

    def test_revision_keeps_done(self):
        tp.plan("a", "Т", ["x", "y"])
        tp.step("a", "x")
        tp.plan("a", "", ["x", "y", "z:2"])
        v = tp.active()[0]
        self.assertEqual(v["title"], "Т")
        self.assertAlmostEqual(v["percent"], 25.0)

    def test_finish_and_keep(self):
        tp.plan("a", "Т", ["x"])
        tp.finish("a")
        self.assertEqual(tp.active()[0]["percent"], 100)
        self.assertEqual(tp.active(time.time() + tp.KEEP + 5), [])

    def test_five_rows_and_legacy(self):
        for i in range(5):
            tp.plan(f"t{i}", f"Задача {i}", ["a", "b"])
        rows = tp.active(legacy={"task": "Старый", "steps": ["a", "b"], "done": 1,
                                 "updated": time.time()})
        self.assertEqual(len(rows), 6)
        self.assertIn(50.0, [r["percent"] for r in rows if r["id"] == "progress"])

    def test_stale_and_bad_file(self):
        tp.plan("a", "Т", ["x"])
        self.assertTrue(tp.active(time.time() + tp.STALE + 5)[0]["stale"])
        (tp.tasks_dir() / "bad.json").write_text("{ ой", encoding="utf-8")
        self.assertEqual(len(tp.active()), 1)

    def test_parse_step(self):
        self.assertEqual(tp.parse_step("код: 2,5")["weight"], 2.5)
        self.assertEqual(tp.parse_step("время 10:30")["name"], "время 10")
        self.assertEqual(tp.parse_step({"step": "s", "w": 0})["weight"], 1.0)

    def test_color_continuous(self):
        self.assertEqual(tp.color_for(0), "#d96a5f")
        self.assertEqual(tp.color_for(100), "#6fbf73")
        self.assertEqual(tp.color_for(50), "#e6c45c")
        prev = None
        for p in range(0, 101):
            c = tp.color_for(p)
            rgb = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
            if prev:  # непрерывно: соседние проценты — почти один цвет
                self.assertLessEqual(max(abs(a - b) for a, b in zip(rgb, prev)), 8)
            prev = rgb
        self.assertNotEqual(tp.color_for(37), tp.color_for(38))
        self.assertEqual(tp.color_for(-5), tp.color_for(0))

    def test_cli(self):
        self.assertEqual(tp.main(["plan", "c", "CLI", "a:1", "b:3"]), 0)
        tp.main(["step", "c", "b"])
        self.assertAlmostEqual(tp.active()[0]["percent"], 75.0)
        tp.main(["finish", "c", "failed"])
        self.assertEqual(tp.active()[0]["state"], "failed")


if __name__ == "__main__":
    unittest.main()
