"""Дзен-режим «Слепой печати» (Ctrl+M): мгновенный вход/выход, позиция не теряется."""
import os
import tempfile
import time
import tkinter as tk
import types
import unittest
from pathlib import Path


def key(keysym, state=0, char="", keycode=0):
    return types.SimpleNamespace(keysym=keysym, state=state, char=char, keycode=keycode, widget=None)


class ZenHotkeyTest(unittest.TestCase):
    def test_hotkey_any_layout(self):
        from stamina.zen import is_zen_hotkey
        self.assertTrue(is_zen_hotkey(key("m", 0x4)))
        self.assertTrue(is_zen_hotkey(key("Cyrillic_softsign", 0x4)))
        self.assertTrue(is_zen_hotkey(key("??", 0x4, keycode=77)))
        self.assertFalse(is_zen_hotkey(key("m")))
        self.assertFalse(is_zen_hotkey(key("m", 0x4 | 0x8)))


class ZenCockpitTest(unittest.TestCase):
    def setUp(self):
        from stamina import pilots
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        os.environ.setdefault("APPDATA", self._tmp)
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.app.store.save_settings = lambda: None
        self.app.store.settings["zen_mode"] = False
        self.app.update()

    def tearDown(self):
        from stamina import pilots
        self.app.destroy()
        pilots.reset_root()

    def test_toggle_keeps_position(self):
        a = self.app
        a.show("bridge")
        br = a.screens["bridge"]
        br.start("hello world again", mode="free", title="T", subtitle="")
        for ch in "hel":
            a._on_key(key(ch, char=ch))
        self.assertEqual(br.engine.index, 3)
        layout, skin = a._layout, a.store.settings.get("skin")
        self.assertEqual(a._on_key(key("m", 0x4)), "break")
        a.update()
        self.assertTrue(a.zen.on)
        self.assertTrue(a.zen.overlay.winfo_ismapped())
        self.assertTrue(a.store.settings["zen_mode"])
        a._on_key(key("l", char="l"))           # набор работает как обычно
        self.assertEqual(br.engine.index, 4)
        # Esc Esc — назад на борт, без перезапуска
        a._on_key(key("Escape"))
        a._on_key(key("Escape"))
        a.update()
        self.assertFalse(a.zen.on)
        self.assertFalse(a.zen.overlay.winfo_ismapped())
        self.assertEqual(br.engine.index, 4)
        self.assertEqual((a.current, a._layout, a.store.settings.get("skin")), ("bridge", layout, skin))

    def test_single_esc_restarts_and_other_zones_hide(self):
        a = self.app
        a.show("bridge")
        a.zen.toggle(True)
        calls = []
        a.restart_current = lambda: calls.append(1)
        a._on_key(key("Escape"))
        t0 = time.time()
        while time.time() - t0 < 0.7:
            a.update()
        self.assertEqual(calls, [1])
        self.assertTrue(a.zen.on)
        a.show("log")
        a.update()
        self.assertFalse(a.zen.on)              # дзен — только на «Полёте»
        a.show("bridge")
        self.assertTrue(a.zen.on)               # выбор запомнен
        a.zen.set_palette("serika")
        self.assertEqual(a.zen.overlay.pal["bg"], "#323437")


if __name__ == "__main__":
    unittest.main()
