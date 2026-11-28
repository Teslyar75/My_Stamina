import tkinter as tk
import unittest

from stamina import monitors
from stamina.theme import px
from stamina.ui.timeline import Timeline


class TimelineTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.geometry("900x500+40+40")
        self.root.deiconify()            # popup-тесты меряют экранные координаты
        self.root.update()

    def tearDown(self):
        monitors.set_provider(None)
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_set_items_and_active(self):
        tl = Timeline(self.root, orientation="horizontal", command=lambda *_: None)
        tl.pack()
        tl.set_items([{"id": "a", "label": "A"}, {"id": "b", "label": "B", "children": [{"id": "b1", "label": "B1"}]}])
        self.assertEqual([i.id for i in tl.items()], ["a", "b"])
        tl.set_active("b")
        self.assertEqual(tl.active_id(), "b")
        self.root.update_idletasks()
        tl.redraw()
        self.assertTrue(tl._item_boxes)

    def test_activate_command(self):
        seen = []
        tl = Timeline(self.root, orientation="vertical", command=lambda iid, it: seen.append((iid, it.label)))
        tl.set_items([{"id": "x", "label": "X"}])
        tl.activate(tl.items()[0])
        self.assertEqual(seen, [("x", "X")])

    def test_popup_for_children(self):
        tl = Timeline(self.root, orientation="horizontal")
        tl.pack()
        tl.set_items([{"id": "z", "label": "Zone", "children": [{"id": "c1", "label": "Child"}]}])
        self.root.update_idletasks()
        tl.redraw()
        tl._show_popup(tl.items()[0])
        self.root.update_idletasks()
        self.assertIsNotNone(tl._popup)
        self.assertEqual(len(tl._popup_buttons), 1)
        tl.close_popup()
        self.assertIsNone(tl._popup)

    def test_command_receives_popup_flag(self):
        seen = []
        tl = Timeline(self.root, orientation="horizontal",
                      command=lambda iid, item, from_popup: seen.append(from_popup))
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.activate(tl.items()[0], from_popup=False)
        tl.activate(tl.items()[0], from_popup=True)
        self.assertEqual(seen, [False, True])

    def _surface(self, orientation):
        canvas = tk.Canvas(self.root, width=900, height=500, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.root.update_idletasks()
        if orientation == "horizontal":
            box = (0, 0, 870, 46)
        else:
            box = (870, 0, 30, 454)
        return canvas, box

    def test_surface_dashes_share_slideshow_canvas(self):
        canvas, box = self._surface("horizontal")
        seen = []
        tl = Timeline(self.root, orientation="horizontal", surface=canvas,
                      region=lambda: box, tag="ribbon_top", command=lambda iid, item: seen.append(iid))
        tl.set_items([{"id": "a", "label": "A"}, {"id": "b", "label": "B"}])
        canvas.create_image(0, 0, tags=("slide",))
        tl.redraw()

        self.assertEqual(tl.canvas, canvas)
        self.assertTrue(canvas.find_withtag("ribbon_top"))
        self.assertTrue(canvas.find_withtag("timeline"))
        self.assertTrue(canvas.find_withtag("dash"))
        canvas.tag_raise("slide")
        tl.lift()
        order = canvas.find_all()
        self.assertLess(max(order.index(i) for i in canvas.find_withtag("slide")),
                        min(order.index(i) for i in canvas.find_withtag("ribbon_top")))

        e = tk.Event()
        e.x, e.y = 10, 23
        tl._on_surface_click(e)
        self.assertEqual(seen, ["a"])

    def test_vertical_popup_sits_left_of_dash_with_small_gap(self):
        canvas, box = self._surface("vertical")
        tl = Timeline(self.root, orientation="vertical", surface=canvas,
                      region=lambda: box, tag="ribbon_side", dash_width=px(30))
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.redraw()
        self.root.update_idletasks()

        item = tl.items()[0]
        tl._show_popup(item)
        self.root.update_idletasks()
        x0, _y0, _x1, _y1 = tl._full_tick_screen_box(item)
        popup = tl._popup
        gap = x0 - (popup.winfo_rootx() + popup.winfo_width())
        self.assertLessEqual(abs(gap - px(10)), 12)  # DPI tolerance
        self.assertGreaterEqual(gap, 0)
        self.assertLessEqual(gap, 30)

    def test_horizontal_popup_sits_below_dash_with_small_gap(self):
        canvas, box = self._surface("horizontal")
        tl = Timeline(self.root, orientation="horizontal", surface=canvas,
                      region=lambda: box, tag="ribbon_top")
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.redraw()
        self.root.update_idletasks()

        item = tl.items()[0]
        tl._show_popup(item)
        self.root.update_idletasks()
        _x0, _y0, _x1, y1 = tl._full_tick_screen_box(item)
        popup = tl._popup
        gap = popup.winfo_rooty() - y1
        self.assertLessEqual(abs(gap - px(10)), 12)
        self.assertGreaterEqual(gap, 0)
        self.assertLessEqual(gap, 30)

    def test_popup_stays_open_in_gap_and_closes_far_away(self):
        canvas, box = self._surface("vertical")
        tl = Timeline(self.root, orientation="vertical", surface=canvas,
                      region=lambda: box, tag="ribbon_side", dash_width=px(30))
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.redraw()
        self.root.update_idletasks()
        item = tl.items()[0]
        tl._show_popup(item)
        self.root.update_idletasks()

        x0, _y0, _x1, _y1 = tl._dash_screen_box(item)
        popup = tl._popup
        gap_x = (popup.winfo_rootx() + popup.winfo_width() + x0) // 2
        gap_y = popup.winfo_rooty() + 5
        tl.winfo_pointerxy = lambda: (gap_x, gap_y)
        tl._maybe_close_popup()
        self.assertIsNotNone(tl._popup)

        tl.winfo_pointerxy = lambda: (5, 480)
        tl._maybe_close_popup()
        self.assertIsNone(tl._popup)

    @staticmethod
    def _motion(x, y):
        e = tk.Event()
        e.x, e.y = x, y
        return e

    @staticmethod
    def _line(tl, item_id):
        for i in tl.canvas.find_withtag(item_id):
            if tl.canvas.type(i) == "line":
                return i
        return None

    def _settle(self, tl):
        if tl._anim_job is not None:
            self.root.after_cancel(tl._anim_job)
            tl._anim_job = None
        for _ in range(10):
            tl._animate_hover()

    def test_both_ribbons_grow_toward_popup_and_get_brighter(self):
        for orientation, box, point, direction in (
            ("horizontal", (0, 0, 870, 46), (14, 20), "down"),
            ("vertical", (870, 0, 30, 454), (15, 14), "left"),
        ):
            with self.subTest(orientation=orientation):
                canvas, _ = self._surface(orientation)
                tl = Timeline(self.root, orientation=orientation, surface=canvas,
                              region=lambda b=box: b, tag=f"ribbon_{orientation}")
                tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
                tl.redraw()
                item = tl.items()[0]
                line = self._line(tl, item.id)
                self.assertIsNotNone(line)
                before = list(tl.canvas.coords(line))
                before_color = tl.canvas.itemcget(line, "fill")

                tl._on_motion(self._motion(*point))
                self._settle(tl)
                line = self._line(tl, item.id)   # redraw создаёт новые item id
                after = list(tl.canvas.coords(line))
                after_color = tl.canvas.itemcget(line, "fill")
                if direction == "down":
                    self.assertAlmostEqual(after[1], before[1])
                    self.assertGreaterEqual(after[3] - after[1], (before[3] - before[1]) * 2)
                else:
                    self.assertAlmostEqual(after[2], before[2])
                    self.assertGreaterEqual(before[2] - after[0], (before[2] - before[0]) * 2)
                self.assertNotEqual(before_color, after_color)

                # Меню стоит у ПОЛНОСТЬЮ выросшей чёрточки с первого кадра и
                # не едет за ней — кнопка не дёргается перед глазами.
                self.root.update_idletasks()
                tx0, ty0, tx1, ty1 = tl._full_tick_screen_box(item)
                popup = tl._popup
                self.assertIsNotNone(popup)
                if direction == "down":
                    self.assertLessEqual(abs(popup.winfo_rooty() - ty1 - px(10)), 12)
                else:
                    self.assertLessEqual(abs(tx0 - popup.winfo_rootx() - popup.winfo_width() - px(10)), 12)
                self.assertLessEqual(tx1 - tx0 if direction == "left" else ty1 - ty0, px(40))

    def test_popup_does_not_jump_while_dash_grows(self):
        for orientation, box, point in (("horizontal", (0, 0, 870, 46), (14, 20)),
                                        ("vertical", (870, 0, 30, 454), (15, 14))):
            with self.subTest(orientation=orientation):
                canvas, _ = self._surface(orientation)
                tl = Timeline(self.root, orientation=orientation, surface=canvas,
                              region=lambda b=box: b, tag=f"ribbon_{orientation}")
                tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
                tl.redraw()
                item = tl.items()[0]
                tl._on_motion(self._motion(*point))
                self.root.update_idletasks()
                start = (tl._popup.winfo_rootx(), tl._popup.winfo_rooty())
                if tl._anim_job is not None:
                    self.root.after_cancel(tl._anim_job)
                    tl._anim_job = None
                for _ in range(10):
                    tl._animate_hover()
                self.root.update_idletasks()
                end = (tl._popup.winfo_rootx(), tl._popup.winfo_rooty())
                self.assertEqual(start, end)

    def test_popup_survives_whole_path_from_dash_to_button(self):
        canvas, box = self._surface("vertical")
        tl = Timeline(self.root, orientation="vertical", surface=canvas,
                      region=lambda: box, tag="ribbon_side", dash_width=px(30))
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.redraw()
        item = tl.items()[0]
        tl._on_motion(self._motion(15, 14))
        self._settle(tl)
        self.root.update_idletasks()
        tx0, ty0, tx1, ty1 = tl._tick_screen_box(item)
        popup = tl._popup
        px0, py0 = popup.winfo_rootx(), popup.winfo_rooty()
        px1, py1 = px0 + popup.winfo_width(), py0 + popup.winfo_height()
        for x, y in ((tx1, ty0), ((tx0 + px1) // 2, (ty0 + py0) // 2),
                     (px1 - px(12), py0 + px(8)), (px0 + px(20), py1 - px(8))):
            tl.winfo_pointerxy = lambda p=(x, y): p
            tl._maybe_close_popup()
            self.assertIsNotNone(tl._popup, (x, y))
        tl.winfo_pointerxy = lambda: (px0 - px(120), py0 + 5)
        tl._maybe_close_popup()
        self.assertIsNone(tl._popup)

    def test_popup_stays_on_second_monitor_with_negative_coords(self):
        canvas, box = self._surface("vertical")
        tl = Timeline(self.root, orientation="vertical", surface=canvas,
                      region=lambda: box, tag="ribbon_side", dash_width=px(30))
        tl.set_items([{"id": "a", "label": "A", "children": [{"id": "a1", "label": "A1"}]}])
        tl.redraw()
        monitors.set_provider(lambda x, y, n: (-2560, 0, 0, 1400) if x < 0 else (0, 0, 2560, 1400))
        fake_root_x, fake_root_y = -2500, 20
        canvas.winfo_rootx = lambda: fake_root_x
        canvas.winfo_rooty = lambda: fake_root_y
        self.root.winfo_rootx = lambda: fake_root_x
        self.root.winfo_rooty = lambda: fake_root_y
        self.root.update_idletasks()

        item = tl.items()[0]
        tl._on_motion(self._motion(15, 14))
        self._settle(tl)
        tx0, _ty0, _tx1, _ty1 = tl._full_tick_screen_box(item)
        info = tl._popup.place_info()
        popup_x = fake_root_x + float(info["x"])
        pw = max(px(180), tl._popup.winfo_reqwidth())
        self.assertGreaterEqual(popup_x, -2560)
        self.assertLessEqual(popup_x + pw, 0)
        self.assertLessEqual(abs(tx0 - popup_x - pw - px(10)), 12)


if __name__ == "__main__":
    unittest.main()
