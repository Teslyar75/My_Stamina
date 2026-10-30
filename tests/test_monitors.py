"""Выпадашки и диалоги открываются на мониторе окна программы (раскладки — подменные)."""
from __future__ import annotations

import unittest

from stamina import monitors

# основной 1920×1080 (0,0); второй 2560×1440 слева, с отрицательными координатами;
# третий 1280×1024 справа и ниже
LAYOUT = [(0, 0, 1920, 1040), (-2560, -200, 0, 1200), (1920, 300, 3200, 1324)]


def provider(x, y, nearest):
    for r in LAYOUT:
        if r[0] <= x < r[2] and r[1] <= y < r[3]:
            return r
    if not nearest:
        return None
    def d(r):
        cx = min(max(x, r[0]), r[2]); cy = min(max(y, r[1]), r[3])
        return (cx - x) ** 2 + (cy - y) ** 2
    return min(LAYOUT, key=d)


class Anchor:
    def __init__(self, x, y, w=120, h=30):
        self.x, self.y, self.w, self.h = x, y, w, h
    def winfo_rootx(self): return self.x
    def winfo_rooty(self): return self.y
    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_toplevel(self): return self


class MonitorsTest(unittest.TestCase):
    def setUp(self):
        monitors.set_provider(provider)

    def tearDown(self):
        monitors.set_provider(None)

    def test_popup_on_primary(self):
        self.assertEqual(monitors.below_pos(Anchor(100, 100), 200, 300), (100, 130))

    def test_popup_follows_window_to_negative_monitor(self):
        x, y = monitors.below_pos(Anchor(-1500, 400), 200, 300)
        self.assertEqual((x, y), (-1500, 430))   # не прижато к x=0 основного монитора

    def test_flip_up_and_left_inside_anchor_monitor(self):
        a = Anchor(3150, 1290, 40, 30)           # правый нижний угол третьего монитора
        x, y = monitors.below_pos(a, 200, 300)
        self.assertEqual((x, y), (3190 - 200, 1290 - 300))
        l, t, r, b = LAYOUT[2]
        self.assertTrue(l <= x and x + 200 <= r and t <= y and y + 300 <= b)

    def test_flip_near_monitor_edge_with_negative_coords(self):
        a = Anchor(-150, -190, 120, 30)          # правый верх левого монитора
        x, y = monitors.below_pos(a, 300, 200)
        self.assertEqual((x, y), (-30 - 300, -160))
        self.assertLessEqual(x + 300, 0)         # не перепрыгнуло на основной

    def test_center_dialog_on_app_monitor(self):
        class Top(Anchor):
            pass
        top = Top(-2400, 0, 1600, 900)
        geo = monitors.center_geometry(top, 800, 600)
        self.assertEqual(geo, "800x600+-2000+150")
        self.assertEqual(monitors.area_size(top), (2560, 1400))

    def test_saved_geometry_on_second_monitor_is_valid(self):
        self.assertTrue(monitors.on_some_monitor(-1000, 50))
        self.assertFalse(monitors.on_some_monitor(5000, 50))


class DropListRealTest(unittest.TestCase):
    """Настоящий Tk: DropList ставится под якорем в момент открытия, transient к окну."""

    def test_droplist_position_and_transient(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        try:
            from stamina import alt_ui
            root.geometry("600x400+50+50")
            b = tk.Button(root, text="⋯")
            b.place(x=20, y=20)
            root.update()
            monitors.set_provider(lambda x, y, n: (-3000, -500, 4000, 3000))
            root.geometry("+700+300")            # «перетащили» окно
            root.update()
            dl = alt_ui.DropList(b, [("пункт", None, False, True)], lambda _b: None)
            root.update()
            # 7c53b4d: no transient() (Tk 9/Windows hides overrideredirect+transient); -topmost instead
            self.assertEqual(str(dl.transient()), "")
            self.assertTrue(int(dl.attributes("-topmost")))
            self.assertLessEqual(abs(dl.winfo_rootx() - b.winfo_rootx()), 2)
            self.assertLessEqual(abs(dl.winfo_rooty() - (b.winfo_rooty() + b.winfo_height())), 2)
            dl.close()
        finally:
            monitors.set_provider(None)
            root.destroy()


if __name__ == "__main__":
    unittest.main()
