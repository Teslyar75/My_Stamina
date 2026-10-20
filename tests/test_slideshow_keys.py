"""Стрелки в слайдшоу: волна вправо/влево, выход — только Esc и правая кнопка мыши."""
import unittest

from stamina.idle.overlay import IdleController, Slideshow


class _Event:
    def __init__(self, keysym: str, etype: str = "2"):
        self.keysym = keysym
        self.type = etype


def _show(stations):
    show = Slideshow.__new__(Slideshow)
    show.stations = stations
    show.st_i = 0
    show._muted = False
    show.calls = []
    show.switch_station = lambda n: show.calls.append(("switch", n))
    show.change_volume = lambda n: show.calls.append(("vol", n))
    show.toggle_mute = lambda: show.calls.append(("mute", 0))
    show.close = lambda: show.calls.append(("close", 0))
    return show


class SlideshowKeysTest(unittest.TestCase):
    def test_right_switches_wave(self):
        show = _show([{"name": "A"}, {"name": "B"}])
        self.assertEqual(show._key(_Event("Right")), "break")
        self.assertEqual(show.calls, [("switch", 1)])

    def test_left_switches_back(self):
        show = _show([{"name": "A"}])
        show._key(_Event("Left"))
        self.assertEqual(show.calls, [("switch", -1)])

    def test_arrows_do_not_close_without_stations(self):
        show = _show([])
        for key in ("Right", "Left", "Up", "Down"):
            self.assertEqual(show._key(_Event(key)), "break")
        self.assertEqual(show.calls, [])

    def test_volume_and_mute(self):
        show = _show([{"name": "A"}])
        show._key(_Event("Up"))
        show._key(_Event("Down"))
        show._key(_Event("m"))
        self.assertEqual(show.calls, [("vol", 10), ("vol", -10), ("mute", 0)])

    def test_escape_closes(self):
        show = _show([{"name": "A"}])
        show._key(_Event("Escape"))
        self.assertIn(("close", 0), show.calls)

    def test_random_letter_does_not_close(self):
        show = _show([{"name": "A"}])
        show._key(_Event("f"))
        self.assertEqual(show.calls, [])

    def test_key_release_ignored(self):
        show = _show([{"name": "A"}])
        show._key(_Event("Right", etype="3"))
        self.assertEqual(show.calls, [])


class IdleTouchTest(unittest.TestCase):
    def test_touch_does_not_close_show(self):
        ctl = IdleController.__new__(IdleController)
        ctl.last = 0.0
        shown = []
        ctl.show = type("S", (), {"close": lambda self: shown.append(True)})()
        ctl.touch()
        self.assertEqual(shown, [])
        self.assertGreater(ctl.last, 0)


if __name__ == "__main__":
    unittest.main()
