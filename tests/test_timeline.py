import tkinter as tk
import unittest

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
        x0, _y0, _x1, _y1 = tl._dash_screen_box(item)
        popup = tl._popup
        gap = x0 - (popup.winfo_rootx() + popup.winfo_width())
        self.assertLessEqual(abs(gap - px(4)), 12)  # DPI tolerance
        self.assertGreaterEqual(gap, 0)
        self.assertLessEqual(gap, 24)

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
        _x0, _y0, _x1, y1 = tl._dash_screen_box(item)
        popup = tl._popup
        gap = popup.winfo_rooty() - y1
        self.assertLessEqual(abs(gap - px(4)), 12)
        self.assertGreaterEqual(gap, 0)
        self.assertLessEqual(gap, 24)

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


if __name__ == "__main__":
    unittest.main()
