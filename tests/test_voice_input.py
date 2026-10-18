"""Голосовой ввод: логика без микрофона (модель, определение конца фразы, текст).

Сам микрофон и Vosk в тестах не запускаются — проверяется чистая часть,
поэтому тесты идут быстро и работают на любой машине.
"""
from __future__ import annotations

import array
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "voice_input"))

import voice_input as vi  # noqa: E402


def make_model(root: Path, name: str) -> Path:
    (root / name / "am").mkdir(parents=True)
    return root / name


class FindModelTest(unittest.TestCase):
    def test_prefers_language(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_model(root, "vosk-model-small-en-us-0.15")
            ru = make_model(root, "vosk-model-small-ru-0.22")
            self.assertEqual(vi.find_model(root, "ru"), ru)

    def test_bigger_ru_model_wins_when_both_present(self):
        """Из двух русских моделей берётся vosk-model-ru-0.42 (точнее, идёт первой по алфавиту)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            big = make_model(root, "vosk-model-ru-0.42")
            make_model(root, "vosk-model-small-ru-0.22")
            self.assertEqual(vi.find_model(root, "ru"), big)

    def test_falls_back_to_any_model(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            en = make_model(root, "vosk-model-small-en-us-0.15")
            self.assertEqual(vi.find_model(root, "ru"), en)

    def test_missing_or_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(vi.find_model(Path(d) / "нет-такой-папки"))
            self.assertIsNone(vi.find_model(Path(d)))

    def test_ignores_broken_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "vosk-model-small-ru-0.22").mkdir()   # без am/ — модель не рабочая
            self.assertIsNone(vi.find_model(root))


class PhraseSplitterTest(unittest.TestCase):
    def test_stops_after_silence(self):
        s = vi.PhraseSplitter(silence_sec=1.5, max_sec=12.0, idle_sec=6.0)
        self.assertFalse(s.feed("привет", 0.05, 0.25))    # говорим
        done = [s.feed("", 0.0, 0.25) for _ in range(6)]
        self.assertEqual(done, [False] * 5 + [True])      # ровно 1.5 с тишины

    def test_noise_does_not_count_as_silence(self):
        s = vi.PhraseSplitter(silence_sec=1.5, max_sec=12.0, idle_sec=6.0)
        s.feed("привет", 0.05, 0.25)
        for _ in range(5):                                # в комнате шумно, фоновый звук
            self.assertFalse(s.feed("", 0.02, 0.25))

    def test_gives_up_when_nobody_speaks(self):
        s = vi.PhraseSplitter(silence_sec=1.5, max_sec=12.0, idle_sec=6.0)
        done = [s.feed("", 0.0, 0.25) for _ in range(24)]
        self.assertTrue(done[-1])
        self.assertNotIn(True, done[:-1])

    def test_cuts_long_speech(self):
        s = vi.PhraseSplitter(silence_sec=1.5, max_sec=3.0, idle_sec=6.0)
        done = [s.feed("длинная фраза", 0.05, 0.25) for _ in range(12)]
        self.assertTrue(done[-1])
        self.assertNotIn(True, done[:-1])


class TextTest(unittest.TestCase):
    def test_clean_collapses_and_capitalizes(self):
        self.assertEqual(vi.clean("  привет   ассистент \n"), "Привет ассистент")
        self.assertEqual(vi.clean("Asr.py"), "Asr.py")
        self.assertEqual(vi.clean("   "), "")
        self.assertEqual(vi.clean(None), "")

    def test_rms_silence_is_zero(self):
        self.assertEqual(vi.rms_of(array.array("h", [0] * 100).tobytes()), 0.0)

    def test_rms_loud_is_near_one(self):
        loud = vi.rms_of(array.array("h", [32767] * 100).tobytes())
        self.assertGreater(loud, 0.9)

    def test_rms_tolerates_odd_length(self):
        self.assertGreaterEqual(vi.rms_of(b"\x01\x02\x03"), 0.0)

    def test_log_appends(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "voice_log.txt"
            vi.append_log("первая фраза", path)
            vi.append_log("вторая фраза", path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("первая фраза", text)
            self.assertEqual(len(text.strip().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
