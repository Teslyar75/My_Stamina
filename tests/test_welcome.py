"""Первый запуск: проверка зависимостей и экран «ДОБРО ПОЖАЛОВАТЬ НА БОРТ»."""
import unittest

from stamina import deps


class DepsTest(unittest.TestCase):
    def test_check_items(self):
        for system in deps.SYSTEMS:
            items = deps.check(system)
            self.assertEqual([i["key"] for i in items], ["python", "pillow", "tts", "vosk", "model"])
            for it in items:
                self.assertTrue({"name", "ok", "need", "what", "how", "pip", "sys"} <= set(it))
                self.assertTrue(it["how"])
        items = deps.check()
        self.assertTrue(items[0]["ok"])          # тесты идут на Python 3.10+
        self.assertIn("Pillow", deps.pillow_hint())

    def test_system_commands(self):
        self.assertIn(deps.detect_system(), deps.SYSTEMS)
        self.assertEqual(deps.system_command(["tk", "tts"], "apt"), "sudo apt install -y python3-tk espeak-ng")
        self.assertEqual(deps.system_command(["portaudio"], "pacman"), "sudo pacman -S --needed --noconfirm portaudio")
        self.assertEqual(deps.system_command(["tts"], None), "")

    def test_install_nothing_missing(self):
        logs = []
        items = [{"key": "pillow", "ok": True, "pip": ["Pillow"], "sys": []}]
        self.assertTrue(deps.install_all(items, log=logs.append))
        self.assertEqual(logs, ["Готово."])

    @unittest.skipIf(__import__("sys").platform == "win32", "путь Linux")
    def test_default_root_linux(self):
        import os
        from unittest import mock
        from stamina import pilots
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg_x"}, clear=False):
            os.environ.pop("APPDATA", None)
            with mock.patch("pathlib.Path.exists", return_value=False):
                self.assertEqual(str(pilots.default_root()), "/tmp/xdg_x/StarTyping")

    def test_has(self):
        self.assertTrue(deps.has("json"))
        self.assertFalse(deps.has("no_such_module_xyz"))


class WelcomeScreenTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_keys(self):
        from stamina import theme
        from stamina.welcome import WelcomeScreen
        theme.init(self.root)
        calls = []
        w = WelcomeScreen(self.root, on_create=lambda: calls.append("create"), on_import=lambda: None,
                          on_exit=lambda: calls.append("exit"), app_version="test")
        w.pack(fill="both", expand=True)
        self.root.update()

        class E:
            keysym = "Return"
        w.on_key(E())
        E.keysym = "Escape"
        w.on_key(E())
        self.assertEqual(calls, ["create", "exit"])
        self.assertEqual(len(w.items), 5)
        other = "linux" if deps.detect_system() == "windows" else "windows"
        w.set_system(other)
        self.assertIn("команды показаны", w.sys_note.cget("text"))
        w.destroy()


if __name__ == "__main__":
    unittest.main()
