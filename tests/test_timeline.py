import tkinter as tk
import unittest

from stamina.ui.timeline import Timeline


class TimelineTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()

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
