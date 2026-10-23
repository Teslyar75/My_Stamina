"""Плавающая панель радио alt_ui: строится во всех профилях, логика — движок радио."""
import os
import tkinter as tk
import unittest
from unittest import mock

from stamina import alt_ui
from stamina.radio import altpanel


class FakeEng:
    def __init__(self):
        self.playing, self.track, self.volume = False, "", 50
        self.station, self.data, self.calls, self.subs = None, {"favorites": [1]}, [], []
    def bind_ui(self, app): pass
    def subscribe(self, cb): self.subs.append(cb)
    def unsubscribe(self, cb): self.subs.remove(cb)
    def toggle(self): self.calls.append("toggle")
    def stop(self): self.calls.append("stop")
    def next_favorite(self): self.calls.append("next")
    def prev_favorite(self): self.calls.append("prev")
    def set_volume(self, v): self.calls.append(("vol", v)); self.volume = v


class App:
    class store:
        settings = {}
        @staticmethod
        def save_settings(): pass
    screens = {}


class TestAltRadioPanel(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.geometry("800x500")
        self.host = tk.Frame(self.root); self.host.pack(fill=tk.BOTH, expand=True)

    def tearDown(self):
        self.root.destroy()

    def make(self, prof):
        eng = FakeEng()
        with mock.patch.object(altpanel, "get_engine", return_value=eng):
            p = altpanel.AltRadioPanel(App, self.host, prof)
        return p, eng

    def test_all_profiles_style_and_visibility(self):
        for prof in alt_ui.PROFILES:
            with self.subTest(prof=prof):
                p, eng = self.make(prof)
                self.assertIsNone(p.mode())
                eng.playing, eng.station = True, {"name": "Jazz FM"}
                for cb in eng.subs: cb()
                self.assertEqual(p.mode(), "full")
                self.assertIn("Jazz FM", p.lbl.cget("text"))
                p.fold(); self.assertEqual(p.mode(), "tab")
                p._enter(); self.assertEqual(p.mode(), "full")
                p._hover_off(); self.assertEqual(p.mode(), "tab")
                p.unfold(); self.assertEqual(p.mode(), "full")
                p.destroy(); self.assertEqual(eng.subs, [])

    def test_buttons_call_engine(self):
        p, eng = self.make("steampunk")
        for b in (p.btn_play, p.btn_prev, p.btn_next, p.btn_stop):
            b.command()
        p.step(+8); p.step(-100)
        self.assertEqual(eng.calls, ["toggle", "prev", "next", "stop", ("vol", 58), ("vol", 0)])
        p.destroy()

    def test_every_profile_has_style(self):
        for prof in alt_ui.PROFILES:
            self.assertIn(prof, altpanel.STYLE)


if __name__ == "__main__":
    unittest.main()
