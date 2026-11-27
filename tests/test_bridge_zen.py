"""Общий зенид мостика ⛶ / Ctrl+O: текст, каретка и мелкие числа в углу."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina import docs_hook, english_hook, languages_hook, zen_mode
from stamina.bridge import Bridge
from stamina.cockpit import Cockpit
from stamina.typing_style import DEFAULTS


def make_app(*, keyboard: bool = True):
    settings = dict(DEFAULTS)
    settings.update(font="M", keyboard=keyboard, zones=True, cursor_blink="on")
    sound = SimpleNamespace(
        start=lambda: None, click=lambda: None, error=lambda: None, bell=lambda: None,
    )
    return SimpleNamespace(
        store=SimpleNamespace(settings=settings),
        zen=SimpleNamespace(toggle=lambda: None),
        sound=sound,
        screens={},
        focus_set=lambda: None,
        open_help=lambda: None,
        restart_current=lambda: None,
        update_rank=lambda: None,
        start_mission=lambda *_a, **_kw: None,
        start_repair=lambda *_a, **_kw: None,
        get_translator=lambda: None,
        translator=None,
        living=None,
    )


def mapped(widget) -> bool:
    try:
        return bool(widget.winfo_ismapped())
    except tk.TclError:
        return False


@pytest.fixture
def chrome():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360+0+0")
    app = make_app()
    bridge = Bridge(root, app)
    bridge.pack(fill=tk.BOTH, expand=True)
    root.update()
    zen_mode._ACTIVE.clear()
    zen_mode._ESC.reset()
    try:
        yield SimpleNamespace(root=root, app=app, bridge=bridge)
    finally:
        zen_mode.exit_zen(bridge)
        root.destroy()


class TestBridgeZen:
    def test_only_text_and_small_readout(self, chrome):
        b = chrome.bridge
        base_font = tuple(b.viewport._font_b)
        assert mapped(b.strip)
        assert all(mapped(p) for p in b.panels)
        zen_mode.enter(b)
        chrome.root.update()
        assert zen_mode.is_active(b)
        assert mapped(b.viewport)
        assert not mapped(b.strip)
        assert not mapped(b.uplink)
        assert not any(mapped(p) for p in b.panels)
        assert set(b.viewport.grid_info().get("sticky") or "") == set("nsew")
        assert tuple(b.viewport._font_b)[1] > base_font[1]
        assert mapped(b._zen_stats)
        assert b._zen_stats.winfo_manager() == "place"
        assert "0" in b._zen_stats.cget("text")

        zen_mode.exit_zen(b)
        chrome.root.update()
        assert not zen_mode.is_active(b)
        assert mapped(b.strip)
        assert all(mapped(p) for p in b.panels)
        assert not mapped(b.uplink)
        assert int(b.viewport.grid_info().get("row")) == 1
        assert tuple(b.viewport._font_b) == base_font
        assert not b._zen_stats.winfo_ismapped()

    def test_button_uses_same_zen_mode(self, chrome):
        b = chrome.bridge
        assert callable(b.btn_zen_full.command)
        b.btn_zen_full.command()
        chrome.root.update()
        assert zen_mode.is_active(b)
        b.btn_zen_full.command()
        chrome.root.update()
        assert not zen_mode.is_active(b)
        assert mapped(b.strip)

    def test_hidden_keyboard_stays_hidden(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        root.geometry("900x360+0+0")
        app = make_app(keyboard=False)
        b = Bridge(root, app)
        b.pack(fill=tk.BOTH, expand=True)
        root.update()
        assert not b.keyboard.winfo_manager()
        try:
            zen_mode.enter(b)
            root.update()
            assert not b.keyboard.winfo_manager()
            zen_mode.exit_zen(b)
            root.update()
            assert not b.keyboard.winfo_manager()
            assert mapped(b.center)
        finally:
            zen_mode.exit_zen(b)
            root.destroy()


class TestZenTargets:
    def test_bridge_and_hook_screens_are_targets(self, chrome):
        docs = SimpleNamespace(zen_target=lambda: "docs-target")
        fake = SimpleNamespace(screens={
            "bridge": chrome.bridge,
            docs_hook.KEY: docs,
            english_hook.KEY: object(),
            languages_hook.KEY: object(),
            "settings": object(),
        })
        assert Cockpit._zen_target_for(fake, "bridge") is chrome.bridge
        assert Cockpit._zen_target_for(fake, docs_hook.KEY) == "docs-target"
        assert Cockpit._zen_target_for(fake, english_hook.KEY) is fake.screens[english_hook.KEY]
        assert Cockpit._zen_target_for(fake, languages_hook.KEY) is fake.screens[languages_hook.KEY]
        assert Cockpit._zen_target_for(fake, "settings") is None
