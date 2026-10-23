"""«Поверх всех окон»: включено по умолчанию, переключается, держит свои окна сверху."""
import tkinter as tk
import unittest
from unittest import mock

from stamina import ontop, storage


class OnTopTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"нет дисплея: {exc}")
        self.root.geometry("200x100+0+0")
        self.root.update()

    def tearDown(self):
        ontop.apply(self.root, False)
        self.root.destroy()

    def test_default_on(self):
        self.assertIs(storage.DEFAULT_SETTINGS["topmost"], True)

    def test_apply_on_off(self):
        # Без оконного менеджера (xvfb) X11 не хранит -topmost — проверяем, что мы его просим
        top = tk.Toplevel(self.root)
        top.update()
        self.root.attributes = mock.Mock()
        top.attributes = mock.Mock()
        ontop.apply(self.root, True)
        self.assertTrue(ontop.enabled(self.root))
        self.root.attributes.assert_called_with("-topmost", True)
        top.attributes.assert_called_with("-topmost", True)
        self.assertIsNotNone(self.root._ontop_job)    # периодический подъём запущен
        ontop.apply(self.root, False)
        self.assertFalse(ontop.enabled(self.root))
        self.root.attributes.assert_called_with("-topmost", False)
        top.attributes.assert_called_with("-topmost", False)
        self.assertIsNone(self.root._ontop_job)

    def test_tick_reschedules_and_stops(self):
        ontop.apply(self.root, True)
        ontop._tick(self.root)
        self.assertIsNotNone(self.root._ontop_job)
        self.root._ontop_on = False
        ontop._tick(self.root)
        self.assertIsNone(self.root._ontop_job)

    def test_hotkeys_free_of_plain_ctrl_t(self):
        # Ctrl+T в Tk Text переставляет буквы — берём Ctrl+Shift+T
        self.assertNotIn("<Control-t>", ontop.HOTKEYS)


if __name__ == "__main__":
    unittest.main()
