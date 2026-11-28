"""Мостик выведен из общего зенида: кнопки и зенид-хука там больше нет."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina import docs_hook, english_hook, languages_hook
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
    try:
        yield SimpleNamespace(root=root, app=app, bridge=bridge)
    finally:
        root.destroy()


class TestZenTargets:
    def test_bridge_has_no_zen(self, chrome):
        b = chrome.bridge
        assert not hasattr(b, "btn_zen_full")
        assert not callable(getattr(b, "zen_target", None))
        assert not callable(getattr(b, "after_zen_toggle", None))
        assert b.strip.winfo_ismapped()
        assert all(p.winfo_ismapped() for p in b.panels)

    def test_hook_screens_are_targets(self, chrome):
        docs = SimpleNamespace(zen_target=lambda: "docs-target")
        fake = SimpleNamespace(screens={
            "bridge": chrome.bridge,
            docs_hook.KEY: docs,
            english_hook.KEY: object(),
            languages_hook.KEY: object(),
            "settings": object(),
        })
        assert Cockpit._zen_target_for(fake, "bridge") is None
        assert Cockpit._zen_target_for(fake, docs_hook.KEY) == "docs-target"
        assert Cockpit._zen_target_for(fake, english_hook.KEY) is fake.screens[english_hook.KEY]
        assert Cockpit._zen_target_for(fake, languages_hook.KEY) is fake.screens[languages_hook.KEY]
        assert Cockpit._zen_target_for(fake, "settings") is None
