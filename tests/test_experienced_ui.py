import json
import unittest
from pathlib import Path

import tkinter as tk

import pytest

from stamina import alt_ui, storage, zen_mode
from stamina.ui import experienced
from stamina.radio.altpanel import AltRadioPanel


ROOT = Path(__file__).resolve().parents[1]


class _DummyStore:
    def __init__(self):
        self.settings = dict(storage.DEFAULT_SETTINGS)
        self.settings["ui_layout"] = "experienced"

    def save_settings(self):
        pass


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
        canvas.create_text(10, 10, text="logo")

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
        for attr in ["btn_sound", "btn_screen", "btn_slides", "btn_orion", "btn_help",
                     "rank_label", "clock", "nav_buttons", "nav_strip", "subnav",
                     "subnav_buttons", "_mini_row", "crumbs", "crumb_path", "_alt_body",
                     "_xp_canvas", "_xp_slideshow", "_xp_work", "_xp_top", "_xp_side"]:
            self.assertTrue(hasattr(self.app, attr), attr)
        self.assertIn("bridge", self.app.nav_buttons)
        self.assertFalse(self.app._xp_work_open)
        self.assertIsNone(getattr(self.app, "_alt_title", None))
        self.assertIsNone(self.app._radio_mini)
        experienced.on_screen(self.app)

    def test_layout_of_accepts_experienced(self):
        self.assertEqual(alt_ui.layout_of({"ui_layout": "experienced"}), "experienced")

    def test_i18n_keys(self):
        keys = (
            "ОПЫТНЫЙ ПИЛОТ",
            "ОПЫТНЫЙ ПИЛОТ — ленты сверху и справа поверх слайдшоу Земли из космоса. Набор фото докачивается при первом запуске.",
            "ДОМОЙ",
        )
        for lang in ("ru", "uk", "en", "de", "es", "fr", "it"):
            data = json.loads((ROOT / "stamina" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
            for key in keys:
                self.assertIn(key, data, lang)
                self.assertTrue(str(data[key]).strip(), (lang, key))

    def test_manifest_and_cache_path(self):
        from stamina.ui.earth_downloader import cache_root
        manifest = ROOT / "stamina" / "assets" / "backgrounds" / "earth" / "manifest.json"
        self.assertTrue(manifest.is_file())
        data = json.loads(manifest.read_text(encoding="utf-8"))
        items = data.get("items") or []
        self.assertGreaterEqual(len(items), 40)
        self.assertGreaterEqual(sum(1 for it in items if it.get("priority")), 2)
        cache = cache_root().resolve()
        self.assertNotEqual(cache, storage.DATA_DIR.resolve())
        self.assertFalse(str(cache).startswith(str(storage.DATA_DIR.resolve())))
        self.assertFalse(str(cache).startswith(str(ROOT.resolve())))


@pytest.fixture
def xp_app(tmp_path, monkeypatch):
    """Isolated Cockpit with experienced layout; never downloads or writes pilot data."""
    from stamina import cockpit as cockpit_mod
    from stamina import pilots, session_storage, storage
    from stamina.ui.earth_downloader import EarthDownloader
    from stamina.ui.slideshow import Slideshow

    monkeypatch.setenv("APPDATA", str(tmp_path))
    pilots.reset_root(Path(tmp_path))
    session_storage.reset_path()
    storage.reset_paths()
    settings = dict(storage.DEFAULT_SETTINGS)
    settings.update(ui_layout="experienced", skin="spaceship", sound=False, topmost=False,
                    living_space="off", idle_minutes=0, guide_enabled=False, geometry="")
    storage.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    storage.SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(EarthDownloader, "start", lambda self: None)
    monkeypatch.setattr(cockpit_mod.Cockpit, "_show_update_notice", lambda self: None)
    monkeypatch.setattr(cockpit_mod.Cockpit, "_check_updates_bg", lambda self: None)

    made = []

    def make(*, skin="spaceship", slides=True):
        for old in list(made):
            try:
                old.destroy()
            except Exception:
                pass
            made.remove(old)
        if skin != "spaceship":
            settings["skin"] = skin
            storage.SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        if not slides:
            monkeypatch.setattr(Slideshow, "start", lambda self: None)
        # общий зенид — глобальное состояние: снимаем перед созданием нового окна
        for widget, _mode in list(zen_mode._ACTIVE.values()):
            zen_mode.exit_zen(widget)
        zen_mode._ESC.reset()
        app = cockpit_mod.Cockpit()
        app.deiconify()
        app.update()                     # idletasks не разворачивает окно на Windows
        guide = getattr(app, "guide", None)
        if callable(getattr(guide, "stop", None)):
            guide.stop()
        made.append(app)
        return app

    yield make

    for app in made:
        try:
            app.destroy()
        except Exception:
            pass
    pilots.reset_root()
    session_storage.reset_path()
    storage.reset_paths()


def _esc_event(app):
    e = tk.Event()
    e.keysym = "Escape"
    e.keycode = 9
    e.state = 0
    e.char = ""
    e.widget = app
    return e


def _fire_esc(app):
    app._on_key(_esc_event(app))
    app.update_idletasks()


def _open_missions_from_ribbon(app):
    ribbon = app._xp_side
    item = next(i for i in ribbon.items() if i.id == "missions")
    ribbon._show_popup(item)
    assert ribbon._popup_buttons
    ribbon._popup_buttons[0].invoke()
    app.update_idletasks()


def test_experienced_starts_empty(xp_app):
    app = xp_app()
    app.update()

    assert app._layout == "experienced"
    assert hasattr(app, "_xp_slideshow") and not hasattr(alt_ui, "build_chrome_called")
    assert isinstance(app._alt_radio, AltRadioPanel)
    assert not app._xp_work_open
    assert not app._xp_work.winfo_ismapped()
    assert not app._status_hint.winfo_ismapped()
    assert getattr(app, "_alt_title", None) is None
    assert app._xp_top.items() and app._xp_side.items()
    assert any(i.id == experienced.HOME_ID for i in app._xp_top.items())

    canvas = app._xp_canvas
    assert canvas.find_withtag("slide")
    assert canvas.find_withtag("dash")


def test_music_widget_visible_on_empty_screen(xp_app):
    app = xp_app()
    radio = app._alt_radio
    radio.eng.station = {"name": "Тест FM"}
    radio.refresh(force=True)
    app.update_idletasks()

    assert radio.frame.winfo_ismapped()
    panel_right = radio.frame.winfo_rootx() + radio.frame.winfo_width()
    dash_x0, _y0, _x1, _y1 = app._xp_side._dash_screen_box(app._xp_side.items()[0])
    assert panel_right <= dash_x0 + 24   # панель левее правой ленты (DPI-допуск)


def test_work_window_fullscreen_and_double_esc(xp_app):
    """Отсек из чёрточки — общий зенид на весь экран, выход — двойной Esc."""
    app = xp_app()
    app._alt_radio.eng.station = {"name": "Тест FM"}
    app._alt_radio.refresh(force=True)
    canvas = app._xp_canvas
    cx, cy = canvas.winfo_rootx(), canvas.winfo_rooty()
    cw, ch = canvas.winfo_width(), canvas.winfo_height()

    _open_missions_from_ribbon(app)
    work = app._xp_work

    # рабочее окно — в полноэкранном зениде, ничего не обрезано сверху
    assert app.current == "missions"
    assert app._xp_work_open
    assert work.winfo_ismapped()
    assert zen_mode.is_active(work)
    assert (work.winfo_rootx(), work.winfo_rooty()) == (cx, cy)
    assert (work.winfo_width(), work.winfo_height()) == (cw, ch)

    # ленты — на узких накладках поверх окна, радио — выше всех
    assert app._xp_top_overlay.winfo_ismapped()
    assert app._xp_side_overlay.winfo_ismapped()
    assert app._xp_top_overlay.find_withtag("dash")
    assert app._xp_side_overlay.find_withtag("dash")
    radio = app._alt_radio
    assert radio.frame.winfo_ismapped()

    # один Esc держит зенид, второй возвращает пустой вид
    _fire_esc(app)
    assert app._xp_work_open and zen_mode.is_active(work)

    _fire_esc(app)
    assert not app._xp_work_open
    assert not work.winfo_ismapped()
    assert not zen_mode.is_active()
    assert canvas.find_withtag("dash")
    assert radio.frame.winfo_ismapped()


def test_work_window_opens_by_popup_and_closes(xp_app):
    app = xp_app()
    _open_missions_from_ribbon(app)

    assert app._xp_work_open
    assert app._xp_work.winfo_ismapped()
    assert app.current == "missions"

    _fire_esc(app)                       # первый Esc — зенид ещё держится
    assert app._xp_work_open
    _fire_esc(app)                       # второй — пустой вид
    assert not app._xp_work_open
    assert not app._xp_work.winfo_ismapped()
    assert app._alt_radio is not None

    # чёрточка «домой» тоже возвращает в пустой вид
    _open_missions_from_ribbon(app)
    home = next(i for i in app._xp_top.items() if i.id == experienced.HOME_ID)
    app._xp_top.activate(home)
    assert not app._xp_work_open


def test_esc_keeps_fullscreen_and_zen_priority(xp_app, monkeypatch):
    app = xp_app()
    _open_missions_from_ribbon(app)

    seen = []
    monkeypatch.setattr(app.zen, "handle_key", lambda e: seen.append(e.keysym) or "break")
    _fire_esc(app)
    assert seen == ["Escape"]
    assert app._xp_work_open
    assert zen_mode.is_active(app._xp_work)

    del app.zen.handle_key               # вернулись к общему зениду
    _fire_esc(app)
    assert app._xp_work_open             # первый Esc не закрывает окно
    _fire_esc(app)
    assert not app._xp_work_open         # двойной Esc — выход в пустой вид


def test_side_ribbon_centered_under_radio(xp_app):
    app = xp_app()
    app.geometry("1200x800")
    app.update()

    canvas = app._xp_canvas
    ch = canvas.winfo_height()
    cw = canvas.winfo_width()
    rx, ry, rw, rh = app._xp_side._region()
    _tx, _ty, _tw, th = app._xp_top._region()

    assert cw >= 100 and ch >= 100
    assert abs((ry + rh / 2) - (ch / 2)) <= 8
    assert rx + rw >= cw - 2
    assert ry >= th
    assert rh < ch * 0.85

    radio = app._alt_radio
    radio.eng.station = {"name": "Тест FM"}
    radio.refresh(force=True)
    app.update()
    assert radio.frame.winfo_ismapped()
    panel_right = radio.frame.winfo_rootx() + radio.frame.winfo_width()
    dash_x0, dash_y0, _x1, dash_y1 = app._xp_side._dash_screen_box(app._xp_side.items()[0])
    last = app._xp_side.items()[-1]
    _lx0, _ly0, _lx1, last_y1 = app._xp_side._dash_screen_box(last)
    assert panel_right <= dash_x0 + 24
    # радио в середине экрана, лента под ним и тоже по центру
    mid_screen = canvas.winfo_rooty() + ch / 2
    assert dash_y0 < mid_screen < last_y1


def test_dashes_stay_above_new_frame(xp_app):
    app = xp_app()
    app.update()
    slideshow = app._xp_slideshow
    slideshow._show_next(initial=False)
    app.update()

    canvas = app._xp_canvas
    ids = canvas.find_all()
    slides = set(canvas.find_withtag("slide"))
    dashes = set(canvas.find_withtag("dash"))
    assert slides and dashes
    assert max(ids.index(i) for i in slides) < min(ids.index(i) for i in dashes)


def test_experienced_cockpit_all_skins_all_bridge_leaves(xp_app, monkeypatch):
    from stamina import nav, theme

    popups = []
    monkeypatch.setattr(tk.Menu, "tk_popup", lambda self, x, y: popups.append((x, y)))
    for meta in theme.list_themes():
        app = xp_app(skin=meta["id"], slides=False)
        assert app._layout == "experienced"
        app.update_idletasks()

        # сначала открываем рабочее окно выбором пункта ленты
        _open_missions_from_ribbon(app)
        assert app._xp_work_open

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
        before = len(popups)
        app.bridge_menu()
        assert len(popups) == before + 1
        assert all(isinstance(v, int) for v in popups[-1])
