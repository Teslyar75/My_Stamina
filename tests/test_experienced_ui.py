import json
import os
import types
import unittest
from pathlib import Path

import tkinter as tk

from stamina import alt_ui, storage
from stamina.ui import experienced


class _DummyStore:
    def __init__(self):
        self.settings = dict(storage.DEFAULT_SETTINGS)
        self.settings["ui_layout"] = "experienced"


class _DummyIdle:
    def open(self):
        pass


class DummyApp(tk.Tk):
    SCREENS = [("bridge", "МОСТИК"), ("settings", "НАСТРОЙКИ")]
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.store = _DummyStore()
        self.idle = _DummyIdle()
        self.current = "bridge"
        self.nav_buttons = {}
        self.subnav_buttons = {}
        self._alt_profile = "starship"
    def _draw_logo(self, canvas):
        canvas.create_text(10,10,text="logo")
    def open_help(self): pass
    def toggle_sound(self): pass
    def toggle_fullscreen(self): pass
    def _call_orion(self): pass
    def pilot_menu(self): pass
    def show(self, key): self.current = key
    def show_zone(self, key): self.current = key


class ExperiencedUiTest(unittest.TestCase):
    def setUp(self):
        try:
            self.app = DummyApp()
        except tk.TclError:
            self.skipTest("no display")

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_build_chrome_contract(self):
        host = experienced.build_chrome(self.app)
        self.assertIsInstance(host, tk.Frame)
        for attr in ["btn_sound","btn_screen","btn_slides","btn_orion","btn_help","rank_label","clock","nav_buttons","nav_strip","subnav","subnav_buttons","_mini_row","crumbs","crumb_path","_alt_body"]:
            self.assertTrue(hasattr(self.app, attr), attr)
        self.assertIn("bridge", self.app.nav_buttons)
        experienced.on_screen(self.app)

    def test_layout_of_accepts_experienced(self):
        self.assertEqual(alt_ui.layout_of({"ui_layout":"experienced"}), "experienced")


    def test_i18n_keys(self):
        root = Path(__file__).resolve().parents[1]
        keys = (
            "ОПЫТНЫЙ ПИЛОТ",
            "ОПЫТНЫЙ ПИЛОТ — ленты сверху и справа поверх слайдшоу Земли из космоса. Набор фото докачивается при первом запуске.",
        )
        for lang in ("ru", "uk", "en", "de", "es", "fr", "it"):
            data = json.loads((root / "stamina" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
            for key in keys:
                self.assertIn(key, data, lang)
                self.assertTrue(str(data[key]).strip(), (lang, key))

    def test_manifest_and_cache_path(self):
        root = Path(__file__).resolve().parents[1]
        manifest = root / "stamina" / "assets" / "backgrounds" / "earth" / "manifest.json"
        self.assertTrue(manifest.is_file())
        data = json.loads(manifest.read_text(encoding="utf-8"))
        items = data.get("items") or []
        self.assertGreaterEqual(len(items), 40)
        self.assertGreaterEqual(sum(1 for it in items if it.get("priority")), 2)
        from stamina.ui.earth_downloader import cache_root
        cache = cache_root().resolve()
        self.assertNotEqual(cache, storage.DATA_DIR.resolve())
        self.assertFalse(str(cache).startswith(str(storage.DATA_DIR.resolve())))
        self.assertFalse(str(cache).startswith(str(root.resolve())))
