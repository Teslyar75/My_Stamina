"""Слайдшоу простоя: обрезка длинного имени волны по пикселям."""
import unittest

from stamina.idle import start_index
from stamina.idle.overlay import ELLIPSIS, Slideshow, fit_text


class FitTextTest(unittest.TestCase):
    @staticmethod
    def _measure(text: str) -> int:
        return len(text) * 10

    def test_short_text_is_unchanged(self):
        self.assertEqual(fit_text("Маяк", self._measure, 100), "Маяк")

    def test_long_text_is_cut_by_width(self):
        text = "Очень длинное имя волны"
        out = fit_text(text, self._measure, 80)
        self.assertTrue(out.endswith(ELLIPSIS))
        self.assertLessEqual(self._measure(out), 80)
        self.assertTrue(text.startswith(out[:-1]))

    def test_whitespace_is_collapsed(self):
        self.assertEqual(fit_text("  Маяк   FM  ", self._measure, 100), "Маяк FM")

    def test_too_narrow_for_ellipsis(self):
        self.assertEqual(fit_text("Маяк", self._measure, 5), "")

    def test_empty_text(self):
        self.assertEqual(fit_text("", self._measure, 100), "")
        self.assertEqual(fit_text("Маяк", self._measure, 0), "")


class _FakeCanvas:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def delete(self, *_a, **_kw) -> None:
        pass

    def create_rectangle(self, *_a, **_kw) -> None:
        pass

    def create_text(self, _x, _y, text="", **_kw) -> None:
        self.texts.append(text)


class PlateTest(unittest.TestCase):
    def test_long_wave_name_fits_the_plate(self):
        ss = object.__new__(Slideshow)
        ss.cv = _FakeCanvas()
        ss._size = lambda: (500, 500)
        ss._measure_text = lambda text, _font: len(text) * 8
        ss.stations = [{"name": "Очень длинное имя волны " * 6, "genre": "jazz"}]
        ss.st_i = 0
        ss._muted = False
        ss._target = 40

        ss._plate()

        line1 = ss.cv.texts[0]
        self.assertIn(ELLIPSIS, line1)
        self.assertLessEqual(ss._measure_text(line1, None), 420 - 24)


class StartIndexTest(unittest.TestCase):
    """Слайдшоу продолжает волну с радиорубки, а не первую попавшуюся."""

    def test_current_uuid_wins(self):
        items = [{"uuid": "a", "name": "A"}, {"uuid": "b", "name": "B"}]
        self.assertEqual(start_index(items, {"uuid": "b", "name": "B"}), 1)

    def test_name_matches_when_uuid_differs(self):
        items = [{"uuid": "a", "name": "Радио Джаз"}, {"uuid": "b", "name": "Рок"}]
        self.assertEqual(start_index(items, {"uuid": "zzz", "name": "рок"}), 1)

    def test_unknown_station_falls_back_to_first(self):
        items = [{"uuid": "a", "name": "A"}]
        self.assertEqual(start_index(items, {"uuid": "x", "name": "X"}), 0)
        self.assertEqual(start_index(items, None), 0)
        self.assertEqual(start_index([], {"uuid": "a"}), 0)


class _FakePlayer:
    def __init__(self) -> None:
        self.volume = 40

    def set_volume(self, vol: int) -> None:
        self.volume = vol


class _FakeEngine:
    def __init__(self) -> None:
        self.player = _FakePlayer()
        self.volume = 40
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class StopRadioTest(unittest.TestCase):
    @staticmethod
    def _show(was_playing: bool, idle_after: str = "stop") -> Slideshow:
        ss = object.__new__(Slideshow)
        ss._radio_started = True
        ss._was_playing = was_playing
        ss._radio_full = 40
        ss.cfg = {"idle_after": idle_after}
        return ss

    def _run(self, ss, eng):
        from unittest import mock
        with mock.patch("stamina.radio.get_engine", return_value=eng):
            ss._stop_radio()
        return eng

    def test_radio_that_played_before_keeps_playing(self):
        eng = self._run(self._show(True), _FakeEngine())
        self.assertFalse(eng.stopped, "волна с радиорубки не должна глохнуть")

    def test_slideshow_own_radio_stops_when_asked(self):
        eng = self._run(self._show(False, "stop"), _FakeEngine())
        self.assertTrue(eng.stopped)

    def test_slideshow_own_radio_kept_when_asked(self):
        eng = self._run(self._show(False, "keep"), _FakeEngine())
        self.assertFalse(eng.stopped)


if __name__ == "__main__":
    unittest.main()
