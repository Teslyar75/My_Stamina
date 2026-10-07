"""Тесты логики набора, миссий и разбиения текста для переводчика."""

import random
import unittest

from stamina import missions
from stamina.engine import DONE, ERROR, IDLE_CAP, OK, TypingEngine
from stamina.layouts import key_for_char
from stamina.text_processing import adapt_for_typing
from stamina.translator import Segments


class EngineTests(unittest.TestCase):
    def test_correct_and_error(self):
        e = TypingEngine("ab")
        self.assertEqual(e.press("x", 0.0), ERROR)
        self.assertEqual(e.index, 0)
        self.assertEqual(e.press("A", 0.2), OK)          # регистр не важен
        self.assertEqual(e.press("b", 0.4), DONE)
        self.assertEqual(e.errors, 1)
        self.assertEqual(e.typed, 3)
        self.assertAlmostEqual(e.accuracy, 200 / 3)

    def test_idle_time_is_capped(self):
        e = TypingEngine("abc")
        e.press("a", 0.0)
        e.press("b", 100.0)                              # отошли на 100 секунд
        self.assertAlmostEqual(e.elapsed(100.0), IDLE_CAP)

    def test_pause_stops_time(self):
        e = TypingEngine("abcd")
        e.press("a", 0.0)
        e.press("b", 1.0)
        e.pause(1.5)
        self.assertAlmostEqual(e.elapsed(50.0), 1.5)
        e.resume()
        e.press("c", 60.0)                               # первый после паузы — без интервала
        self.assertAlmostEqual(e.elapsed(60.0), 1.5)

    def test_resume_keeps_progress(self):
        e = TypingEngine("hello", index=3, typed=4, errors=1, elapsed=10.0)
        self.assertEqual(e.current, "l")
        self.assertEqual(e.segment(0.0)["chars"], 0)


class MissionTests(unittest.TestCase):
    def test_texts_use_only_mission_keys(self):
        rng = random.Random(3)
        for m in missions.MISSIONS:
            text = missions.generate_mission_text(m, rng)
            self.assertTrue(set(text) <= set(m["keys"] + " "), m["id"])
            self.assertGreater(len(text), 150)

    def test_stars(self):
        self.assertEqual(missions.stars_for(90, 500, 100), 0)
        self.assertEqual(missions.stars_for(93, 50, 100), 1)
        self.assertEqual(missions.stars_for(96, 100, 100), 2)
        self.assertEqual(missions.stars_for(99, 130, 100), 3)

    def test_ranks(self):
        self.assertEqual(missions.rank_for(0)[0], "Кадет")
        self.assertEqual(missions.rank_for(12000)[0], "Адмирал флота")

    def test_cyrillic_keys(self):
        self.assertEqual(key_for_char("ф"), "a")
        self.assertEqual(key_for_char("Ё"), "`")
        self.assertEqual(key_for_char(" "), "space")


class SegmentTests(unittest.TestCase):
    RAW = ("It was a bright cold day in April, and the clocks were striking thirteen. "
           "Winston Smith slipped quickly through the glass doors! Ok?")

    def test_sentences_from_original(self):
        adapted = adapt_for_typing(self.RAW)
        s = Segments(adapted, self.RAW)
        self.assertTrue(s.from_original)
        self.assertEqual(len(s), 2)                      # «Ok?» приклеен к предыдущему
        self.assertTrue(s.sources[0].startswith("It was"))
        self.assertEqual(s.index_at(0), 0)
        self.assertEqual(s.index_at(len(adapted) - 1), 1)

    def test_fallback_chunks(self):
        adapted = adapt_for_typing(self.RAW)
        s = Segments(adapted)
        self.assertFalse(s.from_original)
        self.assertGreaterEqual(len(s), 2)


if __name__ == "__main__":
    unittest.main()
