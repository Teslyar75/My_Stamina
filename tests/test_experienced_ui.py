import json
import unittest
from pathlib import Path

import tkinter as tk

import pytest

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


def _experienced_app(tmp_path, monkeypatch, skin):
    from stamina import pilots, storage
    from stamina.ui.earth_downloader import EarthDownloader
    from stamina.ui.slideshow import Slideshow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    pilots.reset_root(Path(tmp_path))
    settings = dict(storage.DEFAULT_SETTINGS)
    settings.update(ui_layout="experienced", skin=skin, sound=False, topmost=False,
                    living_space="off", idle_minutes=0, guide_enabled=False, geometry="")
    storage.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    storage.SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(EarthDownloader, "start", lambda self: None)
    monkeypatch.setattr(Slideshow, "start", lambda self: None)
    from stamina.cockpit import Cockpit
    try:
        app = Cockpit()
    except tk.TclError:
        pytest.skip("нет дисплея")
    guide = getattr(app, "guide", None)
    if callable(getattr(guide, "stop", None)):
        guide.stop()
    return app


def test_experienced_cockpit_all_skins_all_bridge_leaves(tmp_path, monkeypatch):
    from stamina import nav, pilots, theme

    themes = theme.list_themes()
    assert themes
    popups = []
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda self, x, y: popups.append((x, y)))
    try:
        for meta in themes:
            app = None
            try:
                app = _experienced_app(tmp_path, monkeypatch, meta["id"])
                assert app._layout == "experienced"
                for key, _title in nav.BRIDGE_LEAVES:
                    app.show(key)
                    app.update_idletasks()
                    assert app.current == key
                    zone = nav.zone_of(key)
                    for button in (app.nav_buttons.get(zone), app.subnav_buttons.get(key)):
                        assert button is not None
                        button.set_color(theme.CYAN)
                        button.set_narrow(True)
                        button.set_narrow(False)
                        button.set_text("ПРОВЕРКА")
                        button.set_enabled(True)
                        button.configure(cursor="hand2")
                        button.bind("<Button-3>", lambda _e: None)
                        button.set_active(True)
                        button.set_active(False)
                        assert isinstance(button.winfo_manager(), str)
                        assert isinstance(button.winfo_rootx(), int)
                        assert isinstance(button.winfo_rooty(), int)
                        assert isinstance(button.winfo_width(), int)
                        assert isinstance(button.winfo_height(), int)
                        assert isinstance(button.winfo_ismapped(), (bool, int))
                    app.update_comm_badge()
                before = len(popups)
                app.bridge_menu()
                assert len(popups) == before + 1
                assert all(isinstance(v, int) for v in popups[-1])
            finally:
                if app is not None:
                    try:
                        app.destroy()
                    except Exception:
                        pass
    finally:
        pilots.reset_root()
