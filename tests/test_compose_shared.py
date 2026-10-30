"""Общий компоновщик и помощник хоткеев: Орион пользуется ими, а не своими копиями."""
import inspect
import tkinter as tk
import unittest

from stamina import compose, hotkeys
from stamina.english import speech_std


class ComposeSharedTest(unittest.TestCase):
    def test_orion_uses_shared_compose(self):
        from stamina import orion_screen
        src = inspect.getsource(orion_screen)
        self.assertIn("compose.ShotTray", src)
        self.assertNotIn("filedialog.askopenfilenames", src)
        self.assertIs(orion_screen.OrionScreen.IMAGE_TYPES, compose.IMAGE_TYPES)

    def test_image_paths_filter(self):
        got = compose.image_paths(["a.PNG", "b.txt", "c.jpeg"])
        self.assertEqual([p.name for p in got], ["a.PNG", "c.jpeg"])

    def test_typing_in_is_shared(self):
        self.assertIs(speech_std.typing_in, hotkeys.typing_in)

    def test_letter_key_respects_typing(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        root.withdraw()
        try:
            ent, lab = tk.Entry(root), tk.Label(root)
            ev = type("E", (), {})
            e1, e2 = ev(), ev()
            e1.keysym, e1.widget = "M", ent
            e2.keysym, e2.widget = "M", lab
            self.assertFalse(hotkeys.letter_key(e1, ("m",)))
            self.assertTrue(hotkeys.letter_key(e2, ("m",)))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
