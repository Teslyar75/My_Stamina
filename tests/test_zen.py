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
        br.start("hello world again and more words here", mode="free", title="T", subtitle="")
        for ch in "hel":
            a._on_key(key(ch, char=ch))
        self.assertEqual(br.engine.index, 3)
        layout, skin = a._layout, a.store.settings.get("skin")
        self.assertEqual(a._on_key(key("m", 0x4)), "break")
        a.update()
        self.assertTrue(a.zen.on)
        ov = a.zen.overlay
        self.assertTrue(ov.winfo_ismapped())
        self.assertEqual(ov.test.words[:2], ["hello", "world"])   # слова — с текущего места мостика
        for ch in "hello wor":
            a._on_key(key("space" if ch == " " else ch, char=ch))
        self.assertEqual((ov.test.wi, ov.test.inputs[1]), (1, "wor"))
        self.assertEqual(br.engine.index, 3)                    # мостик не тронут
        a._on_key(key("Escape"))
        a._on_key(key("Escape"))
        a.update()
        self.assertFalse(a.zen.on)
        self.assertFalse(ov.winfo_ismapped())
        self.assertEqual(br.engine.index, 6)   # «hello » набрано в портале → на мостике
        self.assertEqual((a.current, a._layout, a.store.settings.get("skin")), ("bridge", layout, skin))

    def test_words_mode_finish_and_records(self):
        a = self.app
        from stamina import portal_stats
        a.store.settings["zen_mt_mode"] = "words"
        a.store.settings["zen_mt_counts"] = {"words": 10}
        a.show("bridge")
        br = a.screens["bridge"]
        br.start(" ".join(["ab"] * 30), mode="free", title="T", subtitle="")
        a.zen.toggle(True)
        a.update()
        ov = a.zen.overlay
        self.assertEqual(len(ov.test.words), 10)
        for ch in " ".join(["ab"] * 10):
            a._on_key(key("space" if ch == " " else ch, char=ch))
        self.assertTrue(ov.test.finished)
        self.assertTrue(ov.result.winfo_manager())
        self.assertEqual(portal_stats.load()["results"][-1]["mode2"], 10)
        a._on_key(key("Tab"))                                   # следующий тест
        self.assertFalse(ov.test.finished)

    def test_underline_caret_under_next_char_and_space(self):
        a = self.app
        a.show("bridge")
        a.zen.toggle(True)
        ov = a.zen.overlay
        self.assertEqual(ov.caret_style(), "underline")
        w0 = ov.test.words[0]
        for ch in w0[:1]:
            a._on_key(key("x", char=ch))
        t0 = time.time()
        while time.time() - t0 < 0.3:
            a.update()
        bb = ov.words.bbox("1.0+1c")
        lh = ov.f_words.metrics("linespace")
        x, y, w, h = ov._caret_target
        self.assertEqual(x, ov.words.winfo_x() + bb[0] + 1)
        self.assertGreater(y, ov.words.winfo_y() + bb[1] + lh * 0.6)   # под буквой
        self.assertGreater(w, h)
        self.assertLessEqual(abs(ov._caret_x - x) + abs(ov._caret_y - y), 2)   # доехала плавно
        for ch in w0[1:]:
            a._on_key(key("x", char=ch))
        self.assertEqual(ov.words.get(f"1.0+{ov._caret_index}c"), " ")              # под пробелом

    def test_portal_typing_advances_bridge(self):
        a = self.app
        a.store.settings["zen_mt_mode"] = "words"
        a.store.settings["zen_mt_counts"] = {"words": 10}
        a.show("bridge")
        br = a.screens["bridge"]
        text = "Hello, World! It's a fine day. " * 20
        br.start(text, mode="free", title="T", subtitle="")
        a.zen.toggle(True)
        a.update()
        ov = a.zen.overlay
        self.assertEqual(ov.test.words[:3], ["hello", "world", "it's"])
        for ch in " ".join(ov.test.words):
            a._on_key(key("space" if ch == " " else ch, char=ch))
        self.assertTrue(ov.test.finished)
        # 10 слов = фраза (6) + «hello world it's a» → мостик сразу после «a »
        self.assertEqual(br._full_index(), len("Hello, World! It's a fine day. ") + len("Hello, World! It's a "))
        self.assertGreater(br.engine.typed, 0)
        a._on_key(key("Tab"))
        self.assertEqual(ov.test.words[0], "fine")
        # частичный тест + выход: курсор после последнего законченного слова (с ошибкой — тоже)
        for ch in "fine dxy hel":
            a._on_key(key("space" if ch == " " else ch, char=ch))
        a._on_key(key("Escape")); a._on_key(key("Escape"))
        a.update()
        self.assertFalse(a.zen.on)
        self.assertEqual(br._full_index(), len("Hello, World! It's a fine day. ") * 2)
        self.assertEqual(br.engine.text[br.engine.index:br.engine.index + 6], "Hello,")
        a.zen.toggle(True)
        self.assertEqual(a.zen.overlay.test.words[0], "hello")       # портал продолжает оттуда же

    def test_single_esc_restarts_and_other_zones_hide(self):
        a = self.app
        a.show("bridge")
        a.zen.toggle(True)
        ov = a.zen.overlay
        a._on_key(key("x", char=ov.test.words[0][0]))
        self.assertTrue(ov.test.started)
        a._on_key(key("Escape"))
        t0 = time.time()
        while time.time() - t0 < 0.7:
            a.update()
        self.assertFalse(ov.test.started)                       # тест заново
        self.assertTrue(a.zen.on)
        a.show("log")
        a.update()
        self.assertFalse(a.zen.on)
        a.show("bridge")
        self.assertTrue(a.zen.on)
        a.zen.set_palette("serika")
        self.assertEqual(a.zen.overlay.pal["bg"], "#323437")


if __name__ == "__main__":
    unittest.main()
