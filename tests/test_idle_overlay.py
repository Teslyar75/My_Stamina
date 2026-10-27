"""Слайдшоу простоя: обрезка длинного имени волны по пикселям."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
