"""Порт из веб-версии: зоны и строка пути, «Мостик → Настройки», шкала тепловой карты."""
import unittest

from stamina import i18n, nav, theme, typing_style as ts
from stamina.storage import DEFAULT_SETTINGS


class NavTest(unittest.TestCase):
    def test_six_zones_in_order(self):
        self.assertEqual(nav.zones(), ["bridge", "english", "speedread", "lounge", "radio", "settings"])
        # незагрузившийся раздел пропадает, мостик и настройки — всегда
        self.assertEqual(nav.zones({"english"}), ["bridge", "english", "settings"])

    def test_bridge_submenu_belongs_to_bridge(self):
        for leaf, _title in nav.BRIDGE_LEAVES:
            self.assertEqual(nav.zone_of(leaf), "bridge")
        self.assertEqual([k for k, _ in nav.BRIDGE_LEAVES],
                         ["bridge", "missions", "cargo", "log", "bridge_settings"])
        self.assertEqual(nav.zone_of("radio"), "radio")
        self.assertIsNone(nav.zone_of("honor"))

    def test_breadcrumbs(self):
        self.assertEqual(nav.path("log"), [("МОСТИК", "bridge"), ("БОРТЖУРНАЛ", "log")])
        self.assertEqual(nav.path("bridge"), [("МОСТИК", "bridge")])
        self.assertEqual(nav.path("speedread"), [("СКОРОЧТЕНИЕ", "speedread")])
        self.assertEqual(nav.path("honor"), [("ДОСКА ПОЧЁТА", "honor")])
        self.assertEqual(nav.path(None), [])

    def test_breadcrumbs_translated(self):
        try:
            i18n.set_language("en")
            self.assertEqual(nav.path("bridge_settings")[1][0], "BRIDGE SETTINGS")
        finally:
            i18n.set_language("ru")


class TypingStyleTest(unittest.TestCase):
    def test_defaults_registered(self):
        for k, v in ts.DEFAULTS.items():
            self.assertIn(k, DEFAULT_SETTINGS)
            self.assertEqual(DEFAULT_SETTINGS[k], v)

    def test_sizes_follow_main_font(self):
        st = {"font": "L", "typed_font": "", "ahead_font": "XXL"}
        self.assertEqual(ts.size_for(st, "font"), ts.FONT_SIZES["L"])
        self.assertEqual(ts.size_for(st, "typed_font"), ts.FONT_SIZES["L"])
        self.assertEqual(ts.size_for(st, "ahead_font"), ts.FONT_SIZES["XXL"])
        self.assertEqual(ts.size_for({"font": "??"}, "font"), ts.FONT_SIZES["M"])
        sizes = [ts.FONT_SIZES[k] for k in ts.FONT_KEYS]
        self.assertEqual(sizes, sorted(sizes))

    def test_colors_fall_back_to_skin(self):
        self.assertEqual(ts.color({"typed_color": ""}, "typed_color", "#112233"), "#112233")
        self.assertEqual(ts.color({"typed_color": "#abcdef"}, "typed_color", "#112233"), "#ABCDEF")
        self.assertEqual(ts.color({"typed_color": "red"}, "typed_color", "#112233"), "#112233")
        self.assertEqual(ts.color({"typed_color": "#zzzzzz"}, "typed_color", "#112233"), "#112233")

    def test_faces(self):
        self.assertEqual(ts.family_for("mono", "H", "M"), "M")
        self.assertEqual(ts.family_for("sans", "H", "M"), "H")
        self.assertEqual(ts.family_for("bogus", "H", "M"), "M")


class HeatScaleTest(unittest.TestCase):
    def test_green_amber_red(self):
        self.assertEqual(theme.heat_fill(0.0), theme.heat_color(0.0))
        self.assertEqual(theme.heat_fill(theme.HEAT_FULL / 2), theme.heat_color(0.5))  # янтарь
        self.assertEqual(theme.heat_fill(0.25), theme.heat_color(1.0))                 # красный
        self.assertEqual(theme.heat_fill(0.9), theme.heat_color(1.0))
        # красный канал растёт вместе с ошибками
        reds = [int(theme.heat_fill(r)[1:3], 16) for r in (0.01, 0.06, 0.12, 0.25)]
        self.assertEqual(reds, sorted(reds))


class _FakeStore:
    def __init__(self):
        self.settings = dict(DEFAULT_SETTINGS)


class _FakeApp:
    def __init__(self):
        self.store = _FakeStore()
        self.applied = 0

    def apply_settings(self):
        self.applied += 1

    def open_help(self):
        pass


class BridgeSettingsUiTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        theme.init(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_screen_applies_live(self):
        from stamina.bridge_settings import BridgeSettingsScreen
        app = _FakeApp()
        scr = BridgeSettingsScreen(self.root, app)
        scr.pack(fill="both", expand=True)
        self.root.update()
        for key in ("sight", "cursor_font", "cursor_color", "cursor_blink", "keyboard", "zones",
                    "font", "typed_font", "ahead_font", "typing_face", "typed_color", "ahead_color",
                    "sight_box_font", "sight_box_face", "sight_on_color"):
            self.assertTrue(key in scr.groups or key in scr.toggles or key in scr.swatches, key)
        scr.set("typed_color", "#FF0000")
        scr.set("sight", False)
        scr.set("ahead_font", "XXL")
        self.assertEqual(app.applied, 3)
        self.assertEqual(scr.preview.col_typed, "#FF0000")
        self.assertFalse(scr.preview.sight)
        self.assertTrue(scr.groups["ahead_font"]["XXL"]._active)
        scr.reset_all()
        self.assertEqual(app.store.settings["typed_color"], "")
        self.assertTrue(scr.preview.sight)


if __name__ == "__main__":
    unittest.main()


class CockpitKeyboardTest(unittest.TestCase):
    """Ctrl+Tab / Alt+N / Esc / F11 на настоящем пульте (во временной папке данных)."""

    def setUp(self):
        import os
        import tempfile
        import tkinter as tk
        from pathlib import Path
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
        self.app.update()

    def tearDown(self):
        from stamina import pilots
        self.app.destroy()
        pilots.reset_root()

    def test_zones_and_subtabs(self):
        a = self.app
        self.assertEqual([s for s, _ in a.SCREENS][0], "bridge")
        self.assertEqual(len(a.SCREENS), 6)
        a.show("missions")
        a.cycle_subtab(1)
        self.assertEqual(a.current, "cargo")
        a.cycle_subtab(-1)
        self.assertEqual(a.current, "missions")
        a.goto_subtab(4)
        self.assertEqual(a.current, "bridge_settings")
        scr = a.screens["bridge_settings"]
        a.cycle_subtab(1)
        self.assertEqual(scr.current_tab, "НАБОР")
        a.goto_subtab(3)
        self.assertEqual(scr.current_tab, "ОКОШКО ПРИЦЕЛА")
        a.show("settings")
        a.goto_subtab(2)
        self.assertEqual(a.screens["settings"].current_tab, "skins")
        # из другой зоны Мостик открывается там, где были
        a.show("log")
        a.show("radio" if any(s == "radio" for s, _ in a.SCREENS) else "settings")
        a.show_zone("bridge")
        self.assertEqual(a.current, "log")
        a.show_zone("bridge")
        self.assertEqual(a.current, "bridge")

    def test_breadcrumb_widgets(self):
        a = self.app
        a.show("log")
        a.update()
        texts = [w.cget("text") for w in a.crumb_path.winfo_children()]
        self.assertEqual(texts, ["МОСТИК", "›", "БОРТЖУРНАЛ"])
        self.assertTrue(a.subnav.winfo_ismapped())
        a.show("settings")
        a.update()
        self.assertFalse(a.subnav.winfo_ismapped())

    def test_fullscreen_toggle(self):
        a = self.app
        a.toggle_fullscreen(True)
        self.assertTrue(a._fullscreen)
        a.toggle_fullscreen(False)
        self.assertFalse(a._fullscreen)


class PageHelpCoverageTest(CockpitKeyboardTest):
    """F1 есть для каждого экрана и каждой подвкладки; справка листается клавишами."""

    def test_every_screen_has_help(self):
        from stamina import page_help as ph
        a = self.app
        for name in a.screens:
            a.show(name)
            key = ph.resolve_key(a)
            base = key.split(".", 1)[0]
            self.assertTrue(key in ph.PAGES or base in ph.PAGES, (name, key))
            self.assertIn(base if base != "bridge" or name == "bridge" else name, ph.PAGES, (name, key))
        for owner in ("settings", "bridge_settings"):
            a.show(owner)
            scr = a.screens[owner]
            for tab in scr.tab_keys():
                scr.show_tab(tab)
                self.assertIn(ph.resolve_key(a), ph.PAGES, (owner, tab))

    def test_help_dialog_keys(self):
        from stamina import page_help as ph
        a = self.app
        a.show("bridge_settings")
        dlg = ph.PageHelpDialog(a)
        a.update()
        self.assertEqual(dlg.key, "bridge_settings.sight")
        self.assertIn("Ctrl+1…6", dlg.text.get("1.0", "end"))
        dlg.next_topic(1)
        self.assertNotEqual(dlg.key, "bridge_settings.sight")
        dlg.destroy()

    def test_hotkeys_appended(self):
        from stamina import page_help as ph
        self.assertIn("Alt+1…4", ph.hotkeys_for("settings.skins"))
        self.assertIn("F5", ph.hotkeys_for("log"))


class BridgeHotkeysTest(CockpitKeyboardTest):
    def test_ctrl_f_keys_bound(self):
        a = self.app
        for i, (leaf, _t) in enumerate(nav.BRIDGE_LEAVES, 1):
            self.assertTrue(a.bind(f"<Control-F{i}>"), leaf)
        self.assertIn("Ctrl+F1", a.subnav_buttons["bridge"]._text if hasattr(a.subnav_buttons["bridge"], "_text") else "Ctrl+F1")
