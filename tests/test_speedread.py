"""Тесты отсека «СКОРОЧТЕНИЕ»: RSVP-ядро, разгон, тест понимания, прогресс, тренажёры."""

import tempfile
import unittest
from pathlib import Path

from stamina.speedread import rsvp
from stamina.speedread.exercises import gorbov_sequence, schulte_norm, stars_for
from stamina.speedread.quiz import make_quiz
from stamina.speedread.store import SpeedStore

SAMPLE = ("Chapter 1\n\nThe ship left orbit at dawn. Pilots checked every gauge, then the engines "
          "roared; nobody spoke.\n\nIn 2026 the crew counted «extraordinarily» long words.\n\n"
          "Chapter 2\n\nA new day began.")


class OrpTests(unittest.TestCase):
    def test_offsets_by_length(self):
        self.assertEqual([rsvp.orp_offset(n) for n in (1, 2, 5, 6, 9, 10, 13, 14, 20)],
                         [0, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_orp_skips_leading_punctuation(self):
        # «hello» — ядро 'hello' (5 букв) → смещение 1 от начала ядра
        self.assertEqual(rsvp.orp_index("«hello»"), 2)
        self.assertEqual(rsvp.orp_index("a"), 0)


class TokenizeTests(unittest.TestCase):
    def setUp(self):
        self.words = rsvp.tokenize(SAMPLE)

    def test_positions_map_back_to_text(self):
        for w in self.words:
            self.assertEqual(SAMPLE[w.start:w.end], w.text)

    def test_sentence_and_paragraph_flags(self):
        dawn = next(w for w in self.words if w.text == "dawn.")
        self.assertTrue(dawn.sent_end)
        spoke = next(w for w in self.words if w.text == "spoke.")
        self.assertTrue(spoke.para_end)

    def test_frames_do_not_cross_sentence_end(self):
        i = next(k for k, w in enumerate(self.words) if w.text == "at")
        frame = rsvp.frame_at(self.words, i, 5)
        self.assertEqual(self.words[frame[-1]].text, "dawn.")

    def test_frame_respects_max_chars(self):
        frame = rsvp.frame_at(self.words, 0, 5, max_chars=8)
        self.assertLessEqual(len(rsvp.frame_text(self.words, frame)[0]), 12)

    def test_multipliers(self):
        idx = {w.text: k for k, w in enumerate(self.words)}
        self.assertEqual(rsvp.multiplier(self.words, [idx["dawn."]]), 2.2)
        self.assertEqual(rsvp.multiplier(self.words, [idx["spoke."]]), 3.0)
        self.assertEqual(rsvp.multiplier(self.words, [idx["roared;"]]), 1.5)
        self.assertEqual(rsvp.multiplier(self.words, [idx["2026"]]), 1.4)
        self.assertEqual(rsvp.multiplier(self.words, [idx["ship"]]), 1.0)
        self.assertEqual(rsvp.multiplier(self.words, [idx["dawn."]], punct=False), 1.0)

    def test_frame_ms(self):
        idx = {w.text: k for k, w in enumerate(self.words)}
        self.assertAlmostEqual(rsvp.frame_ms(self.words, [idx["ship"]], 600), 100.0)

    def test_navigation(self):
        i = next(k for k, w in enumerate(self.words) if w.text == "engines")
        s = rsvp.sentence_start(self.words, i)
        self.assertEqual(self.words[s].text, "Pilots")
        self.assertEqual(self.words[rsvp.prev_sentence(self.words, s)].text, "The")
        j = next(k for k, w in enumerate(self.words) if w.text == "began.")
        self.assertEqual(self.words[rsvp.chapter_start(self.words, j)].text, "Chapter")
        self.assertGreater(rsvp.chapter_start(self.words, j), 5)


class RampTests(unittest.TestCase):
    def test_smooth(self):
        r = rsvp.Ramp(300, 600, 10, 30)
        r.tick(95)
        self.assertEqual(r.wpm, 330)

    def test_caps_at_target(self):
        r = rsvp.Ramp(590, 600, 10, 30)
        r.tick(600)
        self.assertEqual(r.wpm, 600)
        self.assertFalse(r.ramping)

    def test_steps(self):
        r = rsvp.Ramp(300, 600, mode="steps")
        r.tick(10, words=1100)
        self.assertEqual(r.wpm, 400)

    def test_two_decreases_make_plateau(self):
        r = rsvp.Ramp(400, 600, 10, 30)
        r.tick(5)
        r.manual(-25)
        r.tick(5)
        r.manual(-25)
        self.assertFalse(r.ramping)
        r.tick(100)
        self.assertEqual(r.wpm, 350)
        r.tick(60)
        self.assertTrue(r.ramping or r.wpm > 350)


class QuizTests(unittest.TestCase):
    def test_quiz_items_are_consistent(self):
        text = " ".join(f"Sentence number {i} mentions planet{i} and orbit{i}." for i in range(60))
        words = rsvp.tokenize(text)
        items = make_quiz(words, 0, len(words), "en")
        self.assertGreaterEqual(len(items), 4)
        for q in items:
            self.assertIn("question", q)
            self.assertLess(q["answer"], len(q["options"]))

    def test_short_passage_has_no_quiz(self):
        self.assertEqual(make_quiz(rsvp.tokenize("too short text here."), 0, 4, "en"), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SpeedStore(Path(self.tmp.name) / "speedread.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_xp_and_eff_wpm(self):
        xp = self.store.add_session({"text": "t", "title": "T", "words": 1000, "secs": 120,
                                     "avg_wpm": 500, "max_wpm": 600, "comp": 0.9})
        rec = self.store.last_sessions(1)[0]
        self.assertEqual(rec["eff_wpm"], 450)
        self.assertEqual(rec["stars"], 3)
        self.assertEqual(xp, round(1000 / 50 * 0.81) + 45)
        again = SpeedStore(self.store.path)
        self.assertEqual(again.best_wpm(), 500)
        self.assertEqual(again.streak(), 1)

    def test_exercise_records_and_daily_xp_cap(self):
        xp1, rec1 = self.store.add_exercise("E-SHL", "5x5", 40.0, 2)
        self.assertEqual((xp1, rec1), (30, False))
        xp2, rec2 = self.store.add_exercise("E-SHL", "5x5", 30.0, 3)
        self.assertTrue(rec2)
        self.assertEqual(xp2, 10 + 30 + 25)
        for _ in range(3):
            self.store.add_exercise("E-SHL", "5x5", 50.0, 1)
        self.assertEqual(self.store.add_exercise("E-SHL", "5x5", 50.0, 1)[0], 0)
        self.assertEqual(self.store.data["exercises"]["E-SHL"]["5x5"]["best"], 30.0)


class ExerciseRulesTests(unittest.TestCase):
    def test_gorbov_order(self):
        seq = gorbov_sequence(5)
        self.assertEqual(len(seq), 25)
        self.assertEqual(seq[:4], [("b", 1), ("r", 12), ("b", 2), ("r", 11)])
        self.assertEqual(seq[-1], ("b", 13))

    def test_schulte_norms_and_stars(self):
        self.assertEqual(schulte_norm(5), (35, 50, 70))
        self.assertEqual(stars_for(30, schulte_norm(5)), 3)
        self.assertEqual(stars_for(80, schulte_norm(5)), 0)
        self.assertEqual(stars_for(30, (34, 24, 14), lower_is_better=False), 2)


if __name__ == "__main__":
    unittest.main()
