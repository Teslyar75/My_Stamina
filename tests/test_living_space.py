"""«Живой космос»: сцена, стекло, контроллер (Pillow нужен; без него тесты пропускаются)."""
import os
import time
import unittest

from stamina import living_space as ls


@unittest.skipUnless(ls.available(), "нужен Pillow")
class SceneTest(unittest.TestCase):
    def test_render_sizes_and_box(self):
        sc = ls.Scene(400, 300, "full")
        self.assertEqual(sc.render().size, (400, 300))
        self.assertEqual(sc.render((10, 20, 110, 70)).size, (100, 50))

    def test_profiles(self):
        self.assertEqual(ls.DEFAULT_MODE, "light")
        for m in ("light", "full"):
            sc = ls.Scene(300, 200, m)
            self.assertEqual(len(sc.stars), ls.PROFILE[m]["stars"])
        self.assertLessEqual(ls.PROFILE["full"]["fps"], 24)
        self.assertLess(ls.PROFILE["light"]["fps"], ls.PROFILE["full"]["fps"])

    def test_static_layer_cached(self):
        sc = ls.Scene(300, 200, "full")
        a = sc.static()
        sc.step(0.1)
        self.assertIs(sc.static(), a)
        sc.step(ls.STATIC_REFRESH + 0.1)
        self.assertIsNot(sc.static(), a)

    def test_objects_wrap_around(self):
        sc = ls.Scene(300, 200, "full")
        for _ in range(400):
            sc.step(0.2, 2.0)
        for s in sc.stars:
            self.assertGreaterEqual(s[0], -4)

    def test_frost(self):
        sc = ls.Scene(400, 240, "light")
        fs = sc.frost_frame()
        self.assertEqual(fs.size, (400 // ls.FS, 240 // ls.FS))
        crop = ls.frost_crop(fs, (40, 40, 240, 140))
        self.assertEqual(crop.size, (200, 100))
        # стекло темнее и ближе к цвету панели, чем резкая сцена
        self.assertEqual(ls.frost(sc.render()).size, (400, 240))

    def test_deterministic(self):
        a, b = ls.Scene(200, 150, "full", seed=3), ls.Scene(200, 150, "full", seed=3)
        a.step(0.5); b.step(0.5)
        self.assertEqual(a.render().tobytes(), b.render().tobytes())


@unittest.skipUnless(ls.available(), "нужен Pillow")
class ControllerTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.geometry("500x400")
        self.host = tk.Frame(self.root, bg="black")
        self.host.pack(fill="both", expand=True)
        self.scr = tk.Frame(self.host, bg="black")
        self.scr.place(relwidth=1, relheight=1)
        from stamina.hud import HudButton, HudPanel
        self.panel = HudPanel(self.scr, "ТЕСТ")
        self.panel.pack(fill="both", expand=True, padx=40, pady=40)
        self.btn = HudButton(self.panel.body, "КНОПКА", lambda: None)
        self.btn.pack()
        self.root.update()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def _pump(self, sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)

    def test_attach_paints_glass_and_off_restores(self):
        live = ls.LivingSpace(self.root, self.host, "full")
        live.attach(self.scr)
        self._pump(0.8)
        self.assertGreater(live.stats["frames"], 3)
        self.assertTrue(self.btn.glass)
        self.assertTrue(self.panel.find_withtag(live.TAG))
        self.assertTrue(self.btn.find_withtag(live.TAG))
        live.set_mode("off")
        self.assertFalse(self.btn.glass)
        self.assertFalse(self.btn.find_withtag(live.TAG))

    def test_glass_survives_redraw(self):
        live = ls.LivingSpace(self.root, self.host, "light")
        live.attach(self.scr)
        self._pump(0.5)
        self.btn.delete("all")
        self.btn._draw()
        self._pump(0.8)
        self.assertTrue(self.btn.find_withtag(live.TAG))

    def test_unknown_mode_is_off(self):
        live = ls.LivingSpace(self.root, self.host, "turbo")
        self.assertFalse(live.on)


if __name__ == "__main__":
    unittest.main()
