"""Конец фразы при голосовом вводе: заминка не должна рвать запись.

Проверяются оба разделителя фраз — корабельный (`stamina/voice/stt.py`) и утилиты
диктовки (`tools/voice_input/voice_input.py`): логика одна, поведение должно совпадать.
Микрофон и Vosk в тестах не запускаются.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "voice_input"))

import voice_input as vi  # noqa: E402

from stamina.voice import stt  # noqa: E402

STEP = 0.25


class PauseTestBase:
    """Общие проверки для обоих разделителей: `splitter` задаётся в наследнике."""

    def make(self, **kw):
        raise NotImplementedError

    def speech(self, s, sec=1.0):
        """Пилот говорит: частичный текст + уверенная громкость."""
        done = [s.feed("привет как дела", 0.05, STEP) for _ in range(int(sec / STEP))]
        self.assertNotIn(True, done)
        return s

    def silence(self, s, sec):
        return [s.feed("", 0.0, STEP) for _ in range(int(round(sec / STEP)))]

    def test_hesitation_does_not_close_phrase(self):
        s = self.speech(self.make(silence_sec=2.5))
        self.assertNotIn(True, self.silence(s, 2.0))      # задумался на две секунды
        self.assertTrue(s.feed("и ещё", 0.05, STEP) is False)
        self.assertEqual(s.silence, 0.0)                  # заговорил — счётчик сброшен
        self.assertFalse(s.paused)

    def test_closes_after_configured_silence(self):
        s = self.make(silence_sec=2.5)
        self.speech(s)
        done = self.silence(s, 3.0)
        self.assertIn(True, done)
        self.assertEqual(done.index(True), 9)             # ровно 2,5 с тишины
        self.assertEqual(s.reason, "silence")

    def test_soft_pause_warns_before_closing(self):
        s = self.make(silence_sec=2.5, soft_sec=0.7)
        self.speech(s)
        self.silence(s, 0.5)
        self.assertFalse(s.paused)
        self.silence(s, 0.5)
        self.assertTrue(s.paused)                         # «…пауза 1,0 с — говорите»

    def test_hold_never_closes_on_silence(self):
        s = self.make(silence_sec=0.0)
        self.speech(s)
        self.assertNotIn(True, self.silence(s, 60.0))     # режим «держать до СТОП»
        self.assertEqual(s.reason, "")

    def test_time_limit(self):
        s = self.make(silence_sec=2.5, max_sec=2.0)
        done = [s.feed("говорю", 0.05, STEP) for _ in range(12)]
        self.assertIn(True, done)
        self.assertEqual(s.reason, "max")

    def test_idle_when_nobody_speaks(self):
        s = self.make(idle_sec=2.0)
        done = self.silence(s, 3.0)
        self.assertIn(True, done)
        self.assertEqual(s.reason, "idle")

    def test_live_start_is_not_the_end(self):
        """Vosk закрыл кусок сам — фраза продолжается, счётчик тишины сброшен."""
        s = self.make(silence_sec=2.5)
        self.speech(s, 0.5)
        s.silence = 2.4
        s.live_start()
        self.assertEqual(s.silence, 0.0)
        self.assertTrue(s.heard)
        self.assertFalse(s.paused)


class StaminaSplitterTest(PauseTestBase, unittest.TestCase):
    def make(self, **kw):
        return stt.PhraseSplitter(**kw)

    def test_listener_defaults_are_generous(self):
        listener = stt.Listener()
        self.assertEqual(listener.silence_sec, 2.5)
        self.assertEqual(listener.max_sec, 120.0)
        self.assertEqual(listener.idle_sec, 12.0)
        self.assertEqual(listener.soft_sec, 0.7)
        self.assertEqual(listener.reason, "")


class VoiceInputSplitterTest(PauseTestBase, unittest.TestCase):
    def make(self, **kw):
        return vi.PhraseSplitter(**kw)

    def test_reason_words_are_human(self):
        s = self.make(silence_sec=2.5)
        self.speech(s)
        self.silence(s, 3.0)
        self.assertEqual(vi.stop_reason(s), "тишина 2.5 с")


class NoiseGateTest(unittest.TestCase):
    def test_empty_gives_base(self):
        self.assertEqual(stt.noise_gate([]), 0.003)
        self.assertEqual(vi.noise_gate([]), 0.003)

    def test_quiet_room_keeps_base(self):
        self.assertEqual(stt.noise_gate([0.0001, 0.0002]), 0.003)

    def test_noisy_room_raises_gate(self):
        self.assertAlmostEqual(stt.noise_gate([0.004, 0.01]), 0.01)

    def test_gate_is_capped(self):
        self.assertEqual(stt.noise_gate([0.5]), 0.02)
        self.assertEqual(vi.noise_gate([0.5]), 0.02)

    def test_speech_does_not_lower_the_floor(self):
        """Самый тихий блок — фон: громкая речь рядом порог не занижает."""
        self.assertAlmostEqual(stt.noise_gate([0.02, 0.004, 0.02]), 0.01)


class MicHelpersTest(unittest.TestCase):
    def test_clock(self):
        from stamina.voice.mic import clock
        self.assertEqual(clock(0), "00:00")
        self.assertEqual(clock(7.4), "00:07")
        self.assertEqual(clock(72), "01:12")

    def test_level_bar_grows_with_voice(self):
        from stamina.voice.mic import level_bar
        self.assertEqual(level_bar(0.0), "")
        self.assertLess(len(level_bar(0.01)), len(level_bar(0.05)))
        self.assertEqual(len(level_bar(9.9)), 14)


if __name__ == "__main__":
    unittest.main()
