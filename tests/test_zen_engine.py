"""Портал: поведение набора как на сайте-тренажёре и его формулы."""
import unittest

from stamina.zen_engine import PortalTest, kogasa, prepare_words, quote_slice


def typ(t, s, now=0.0, step=0.2):
    for ch in s:
        now += step
        t.type_char(ch, now)
    return now


class EngineTest(unittest.TestCase):
    def test_prepare(self):
        self.assertEqual(prepare_words("Hello, World! 42 it's"), ["hello", "world", "it's"])
        self.assertEqual(prepare_words("Hello, World!", punctuation=True), ["Hello,", "World!"])
        self.assertIn("42", prepare_words("a 42", numbers=True))

    def test_space_skips_and_locks_correct_word(self):
        t = PortalTest(["one", "two", "three"])
        typ(t, "one tw ")
        self.assertEqual(t.wi, 2)
        t.backspace()                           # в «tw» с ошибкой вернуться можно
        self.assertEqual((t.wi, t.inputs[1]), (1, "tw"))
        t.backspace(word=True)
        self.assertEqual(t.inputs[1], "")
        t.backspace()                           # «one» верное — назад нельзя
        self.assertEqual(t.wi, 1)

    def test_extra_and_finish_words(self):
        t = PortalTest(["ab", "cd"])
        typ(t, "abx cd")
        self.assertTrue(t.finished)
        c = t.chars()
        self.assertEqual((c["extra"], c["correct"]), (1, 4))

    def test_formulas(self):
        t = PortalTest(["hello", "world"])
        typ(t, " hello world", step=0.5)        # пробел в начале — ничего, таймер не стартует
        self.assertAlmostEqual(t.elapsed(), 5.0, places=6)   # с первого нажатия
        self.assertAlmostEqual(t.wpm(), 11 / 5 / (5 / 60), places=6)
        self.assertAlmostEqual(t.raw(), 11 / 5 / (5 / 60), places=6)
        self.assertEqual(t.acc(), 100.0)

    def test_time_mode(self):
        t = PortalTest(["a"] * 100, mode="time", limit=15)
        typ(t, "a " * 40, step=0.25)
        self.assertTrue(t.finished)
        self.assertAlmostEqual(t.elapsed(), 15.0)
        self.assertGreater(len(t.samples), 10)
        self.assertGreater(t.consistency(), 90)

    def test_acc_counts_errors(self):
        t = PortalTest(["ab"])
        typ(t, "xb")
        t.backspace(); t.backspace()
        typ(t, "ab")
        self.assertAlmostEqual(t.acc(), 75.0)

    def test_misc(self):
        self.assertAlmostEqual(kogasa(0), 100)
        self.assertEqual(quote_slice("a b c. d e f.", 0, min_words=2), 3)


class MergeTest(unittest.TestCase):
    def test_merge_rules(self):
        import datetime as dt
        from stamina import portal_stats as ps
        today = dt.date(2026, 10, 23)
        ts = dt.datetime(2026, 10, 22, 12).timestamp()
        ours = ps.summarize({"started": 3, "results": [
            {"ts": ts, "mode": "words", "mode2": 10, "wpm": 80, "acc": 95, "time": 10}]}, today=today)
        mt = {"tests": 100, "started": 120, "hours": 1.0, "name": "N",
              "pbs": [{"mode": "words", "mode2": "10", "wpm": 110, "acc": 100},
                      {"mode": "time", "mode2": "15", "wpm": 67, "acc": 92}],
              "activity": [("2026-10-22", 9), ("2026-10-23", 4)]}
        m = ps.merge(ours, mt, today=today)
        pb = {(p["mode"], p["mode2"]): p for p in m["pbs"]}
        self.assertEqual((pb[("words", "10")]["wpm"], pb[("words", "10")]["src"]), (80, "ST"))
        self.assertEqual(pb[("time", "15")]["src"], "MT")
        act = dict(m["activity"])
        self.assertEqual((act["2026-10-22"], act["2026-10-23"]), (1, 4))
        self.assertEqual(m["both"]["2026-10-22"], (1, 9))
        self.assertEqual((m["tests"], m["started"], m["streak"]), (101, 123, 2))
        self.assertAlmostEqual(m["seconds"], 3610)
