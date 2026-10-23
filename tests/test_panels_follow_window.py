"""Плашки радио: перетаскивание, позиция относительно окна; диалоги едут за окном."""
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

from stamina import monitors
from stamina.radio import altpanel, drag, minibark


class TestFrac(unittest.TestCase):
    def test_roundtrip_and_clamp(self):
        pos = drag.to_frac(400, 100, 200, 100, 1000, 600)
        self.assertEqual(pos, (0.5, 0.2))
        self.assertEqual(drag.from_frac(pos, 200, 100, 1000, 600), (400, 100))
        # окно сузили — плашка остаётся видимой
        self.assertEqual(drag.from_frac((1.0, 1.0), 200, 100, 500, 300), (300, 200))
        self.assertEqual(drag.to_frac(-50, 9999, 200, 100, 1000, 600), (0.0, 1.0))
        self.assertEqual(drag.load({"k": [2, -1]}, "k"), (1.0, 0.0))
        self.assertIsNone(drag.load({"k": None}, "k"))
        self.assertIsNone(drag.load({}, "k"))

    def test_parse_xy(self):
        self.assertEqual(monitors.parse_xy("300x200+-1500+20"), (-1500, 20))


class FakeEng:
    def __init__(self):
        self.playing, self.track, self.volume = True, "", 50
        self.station, self.data, self.subs = {"name": "Jazz"}, {}, []
    def bind_ui(self, app): pass
    def subscribe(self, cb): self.subs.append(cb)
    def unsubscribe(self, cb): self.subs.remove(cb)
    toggle = stop = next_favorite = prev_favorite = lambda self: None
    def set_volume(self, v): self.volume = v


def ev(w, x, y):
    return SimpleNamespace(x_root=x, y_root=y, widget=w)


class UiBase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.geometry("900x600+0+0")
        self.settings = {}
        self.app = SimpleNamespace(store=SimpleNamespace(settings=self.settings, save_settings=lambda: None),
                                   screens={})
        self.eng = FakeEng()

    def tearDown(self):
        self.root.destroy()

    def drag_by(self, d, handle, dx, dy):
        self.root.update()
        d._press(ev(handle, 100, 100))
        d._motion(ev(handle, 100 + dx, 100 + dy))
        d._release(ev(handle, 100 + dx, 100 + dy))
        self.root.update()


class TestAltPanelDrag(UiBase):
    def test_drag_persist_reset(self):
        host = tk.Frame(self.root, width=900, height=600)
        host.pack(fill=tk.BOTH, expand=True)
        self.root.update()
        with mock.patch.object(altpanel, "get_engine", return_value=self.eng):
            p = altpanel.AltRadioPanel(self.app, host, "old_england")
        self.root.update()
        self.drag_by(p.drag, p.grip, -400, -200)
        pos = self.settings[altpanel.POS_KEY]
        self.assertTrue(0 <= pos[0] < 0.8 and 0 <= pos[1] < 0.5, pos)
        self.assertEqual(p.frame.place_info()["anchor"], "nw")
        # новая панель (перезапуск) — на сохранённом месте
        with mock.patch.object(altpanel, "get_engine", return_value=FakeEng()):
            p2 = altpanel.AltRadioPanel(self.app, host, "starship")
        self.assertEqual(p2.drag.pos, tuple(pos))
        p2.destroy()
        p.drag._reset()
        self.assertIsNone(self.settings[altpanel.POS_KEY])
        self.root.update()
        self.assertEqual(p.frame.place_info()["anchor"], "e")
        p.destroy()


class TestMiniBarDrag(UiBase):
    def test_detach_and_dock(self):
        row = tk.Frame(self.root, height=30)
        row.pack(fill=tk.X)
        tk.Frame(self.root, height=500).pack(fill=tk.BOTH, expand=True)
        with mock.patch.object(minibark, "get_engine", return_value=self.eng):
            bar = minibark.RadioMiniBar(row, self.app)
        self.root.update()
        self.assertEqual(bar.winfo_manager(), "pack")
        self.drag_by(bar.drag, bar.grip, -300, 250)
        self.assertEqual(bar.winfo_manager(), "place")
        self.assertIsNotNone(self.settings[minibark.POS_KEY])
        bar.drag._reset()
        self.root.update()
        self.assertEqual(bar.winfo_manager(), "pack")
        bar.destroy()

    def test_alt_mode_not_draggable(self):
        row = tk.Frame(self.root)
        with mock.patch.object(minibark, "get_engine", return_value=self.eng):
            bar = minibark.RadioMiniBar(row, self.app, draggable=False)
        self.assertIsNone(bar.drag)
        bar.destroy()


class TestFollow(UiBase):
    def test_dialog_moves_with_root_and_clamps(self):
        monitors.set_provider(lambda x, y, n: (0, 0, 3000, 1000) if x >= 0 else (-1920, 0, 0, 1080))
        try:
            dlg = tk.Toplevel(self.root)
            dlg.geometry("200x100+300+300")
            self.root.update()
            gx, gy = monitors.parse_xy(dlg.geometry())
            monitors.move_children(self.root, 100, 50)
            self.root.update()
            self.assertEqual(monitors.parse_xy(dlg.geometry()), (gx + 100, gy + 50))
            monitors.move_children(self.root, 10000, 0)   # прижат к монитору окна
            self.root.update()
            self.assertLessEqual(monitors.parse_xy(dlg.geometry())[0], 3000 - 200)
        finally:
            monitors.set_provider(None)

    def test_droplist_closed(self):
        closed = []
        dlg = tk.Toplevel(self.root)
        dlg.overrideredirect(True)
        dlg.close = lambda: closed.append(1)
        dlg.geometry("50x50+10+10")
        self.root.update()
        monitors.move_children(self.root, 5, 5)
        self.assertEqual(closed, [1])


if __name__ == "__main__":
    unittest.main()
