"""Очередь чтения вслух: разбивка на фразы, управление, события (на моковом движке)."""

import itertools
import unittest

from stamina.voice.reader_tts import ReaderQueue, speech_ready, split_segments


class MockEngine:
    """Движок-заглушка: помнит, что ему сказали, и умеет «договорить» фразу."""

    name = "mock"

    def __init__(self) -> None:
        self.said: list[tuple] = []
        self.events: list[tuple] = []
        self.stopped = 0
        self.last_error = ""
        self._ids = itertools.count(1)

    def speak(self, text: str, rate: int = 0, lang: str = "", voice: str = "") -> int:
        sid = next(self._ids)
        self.said.append((sid, text, rate, lang, voice))
        return sid

    def poll(self) -> list[tuple]:
        out, self.events = self.events, []
        return out

    def stop(self) -> None:
        self.stopped += 1

    def finish(self) -> None:
        """Эмулировать DONE текущей фразы."""
        sid = self.said[-1][0]
        self.events.append(("done", sid, "120"))


class DeadEngine(MockEngine):
    def speak(self, text: str, rate: int = 0, lang: str = "", voice: str = "") -> int:
        self.last_error = "нет голоса"
        return 0


class SplitSegmentsTests(unittest.TestCase):
    SRC = ("Он открыл дверь и вошёл. Свеча горела на столе, освещая свитки.\n\n"
           "— Ты опоздал, — сказал хозяин дома.")

    def test_offsets_match_text(self):
        segs = split_segments(self.SRC)
        self.assertEqual(len(segs), 3)
        for i, s in enumerate(segs):
            self.assertEqual(s.index, i)
            self.assertEqual(self.SRC[s.start:s.end], s.text)
            self.assertTrue(s.text.strip() == s.text)

    def test_paragraph_break_is_a_boundary(self):
        segs = split_segments("Первая строка абзаца кончается тут без точки\n\nВторой абзац начинается заново")
        self.assertEqual(len(segs), 2)
        self.assertNotIn("\n", segs[0].text)

    def test_short_fragments_are_glued(self):
        segs = split_segments("— Да. — Нет. Он долго молчал и смотрел в окно на мокрый город.")
        self.assertEqual(len(segs), 1)

    def test_long_sentence_is_cut(self):
        long_src = "Он говорил долго, " + ("и всё никак не мог остановиться, " * 20) + "пока не устал."
        segs = split_segments(long_src)
        self.assertGreater(len(segs), 1)
        for s in segs:
            self.assertLessEqual(s.length, 320)
            self.assertEqual(long_src[s.start:s.end], s.text)

    def test_empty_text(self):
        self.assertEqual(split_segments(""), [])
        self.assertEqual(split_segments("   \n\n  "), [])

    def test_speech_ready(self):
        self.assertEqual(speech_ready("  — Он сказал[12] это.  "), "Он сказал это.")
        self.assertEqual(speech_ready("Строка\u00a0с\u2009узкими  пробелами"), "Строка с узкими пробелами")


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.eng = MockEngine()
        self.text = "Первое предложение книги. Второе предложение книги. Третье предложение книги."
        self.q = ReaderQueue(self.eng, self.text, duck_radio=False)

    def test_three_segments(self):
        self.assertEqual(len(self.q.segments), 3)
        self.assertEqual(self.q.state, "idle")
        self.assertEqual(self.q.progress(), (0, len(self.text)))

    def test_play_sends_first_and_reports(self):
        self.q.play()
        self.assertEqual(self.q.state, "playing")
        self.assertEqual(len(self.eng.said), 1)
        self.assertEqual(self.eng.said[0][1], "Первое предложение книги.")
        ev = self.q.poll()
        self.assertEqual(ev[0][0], "segment")
        self.assertEqual(ev[0][1].text, "Первое предложение книги.")

    def test_next_segment_after_done(self):
        self.q.play()
        self.q.poll()
        self.eng.finish()
        ev = self.q.poll()
        self.assertEqual([e[0] for e in ev], ["segment"])
        self.assertEqual(ev[0][1].index, 1)
        self.assertEqual(len(self.eng.said), 2)
        self.assertEqual(self.eng.said[1][1], "Второе предложение книги.")

    def test_finishes_at_the_end(self):
        self.q.play()
        for _ in range(3):
            self.q.poll()
            self.eng.finish()
        ev = self.q.poll()
        self.assertIn("finished", [e[0] for e in ev])
        self.assertEqual(self.q.state, "idle")

    def test_pause_and_resume(self):
        self.q.play()
        self.q.poll()
        self.q.pause()
        self.assertEqual(self.q.state, "paused")
        self.assertEqual(self.eng.stopped, 1)
        self.q.resume()
        self.assertEqual(self.q.state, "playing")
        self.assertEqual(len(self.eng.said), 2)
        self.assertEqual(self.eng.said[1][1], self.eng.said[0][1])      # та же фраза заново

    def test_step_forward_and_back(self):
        self.q.play()
        self.q.poll()
        self.q.step(1)
        self.assertEqual(self.q.current.index, 1)
        self.q.step(-5)
        self.assertEqual(self.q.current.index, 0)
        self.q.step(99)
        self.assertEqual(self.q.current.index, 2)

    def test_jump_to_char_and_play_from(self):
        char = self.q.segments[2].start + 3
        self.assertEqual(self.q.index_of_char(char), 2)
        self.q.jump_to(char)
        self.assertEqual(self.q.current_char, self.q.segments[2].start)

    def test_rate_and_lang_reach_engine(self):
        self.q.set_rate(4)
        self.q.set_lang("ru")
        self.q.play()
        sid, text, rate, lang, voice = self.eng.said[0]
        self.assertEqual((rate, lang), (4, "ru"))

    def test_chosen_voice_reaches_engine(self):
        """Пилот выбрал голос в читалке — фраза уходит именно им."""
        self.q.set_voice("Microsoft Pavel")
        self.q.play()
        self.assertEqual(self.eng.said[0][4], "Microsoft Pavel")

    def test_voice_can_be_cleared_back_to_language(self):
        self.q.set_voice("Microsoft Pavel")
        self.q.set_voice("")
        self.q.play()
        self.assertEqual(self.eng.said[0][4], "")

    def test_dead_engine_reports_error(self):
        q = ReaderQueue(DeadEngine(), self.text, duck_radio=False)
        q.play()
        ev = q.poll()
        self.assertEqual(ev[0][0], "error")
        self.assertEqual(q.state, "idle")

    def test_stop_resets_state_keeps_position(self):
        self.q.play()
        self.q.step(1)
        idx = self.q.current.index
        self.q.stop()
        self.assertEqual(self.q.state, "idle")
        self.assertEqual(self.q.current.index, idx)

    def test_load_with_start(self):
        self.q.load(self.text, start=self.q.segments[1].start)
        self.assertEqual(self.q.current.index, 1)
        self.assertEqual(self.q.state, "idle")


if __name__ == "__main__":
    unittest.main()
