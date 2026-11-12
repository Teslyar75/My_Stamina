"""P0: отсеки не импортируются на старте; виджеты — только при первом заходе."""
from __future__ import annotations

import sys

import pytest

from stamina import (
    comm_hook,
    docs_hook,
    english_hook,
    lounge_hook,
    orion_hook,
    radio_hook,
    speedread_hook,
)

# Модули экранов отсеков. Пакет stamina.radio может подтянуться мини-баром
# мостика, но stamina.radio.screen — только при открытии РАДИОРУБКИ.
LAZY_MODULES = (
    "stamina.english.screen",
    "stamina.speedread.screen",
    "stamina.lounge.screen",
    "stamina.radio.screen",
    "stamina.comm_screen",
    "stamina.docs_screen",
    "stamina.orion_screen",
)

HOOKS = (
    english_hook,
    speedread_hook,
    lounge_hook,
    radio_hook,
    comm_hook,
    docs_hook,
    orion_hook,
)


def _purge_lazy_modules() -> None:
    drop_prefixes = (
        "stamina.english.",
        "stamina.speedread.",
        "stamina.lounge.",
        "stamina.radio.",
    )
    keep = {"stamina.english.paths"}
    for name in list(sys.modules):
        if name in LAZY_MODULES or name in (
            "stamina.english", "stamina.speedread", "stamina.lounge", "stamina.radio",
        ):
            del sys.modules[name]
            continue
        if any(name.startswith(p) for p in drop_prefixes) and name not in keep:
            del sys.modules[name]


@pytest.fixture()
def clean_lazy_modules():
    _purge_lazy_modules()
    yield
    # не восстанавливаем — следующий тест сам почистит при необходимости


def test_load_class_does_not_import_screen_modules(clean_lazy_modules):
    for hook in HOOKS:
        assert hook.load_class() is hook.AVAILABLE
    loaded = [m for m in LAZY_MODULES if m in sys.modules]
    assert loaded == [], f"load_class импортировал: {loaded}"


def test_cockpit_start_keeps_lazy_modules_unimported(clean_lazy_modules, monkeypatch):
    monkeypatch.setenv("STAR_TYPING_SAFE", "1")
    import tkinter as tk
    from stamina.cockpit import Cockpit

    # на случай, если предыдущие импорты уже тянули пакеты
    _purge_lazy_modules()
    app = Cockpit()
    try:
        app.update_idletasks()
        loaded = [m for m in LAZY_MODULES if m in sys.modules]
        assert loaded == [], f"на старте уже загружены: {loaded}"
        assert "lounge" in app._factories
        assert "lounge" not in app.screens
        # первый заход тянет модуль (lounge легче english — без словаря)
        scr = app._ensure_screen("lounge")
        assert scr is not None
        assert "stamina.lounge.screen" in sys.modules
        assert "lounge" in app.screens
        assert "lounge" not in app._factories
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_build_pending_is_noop(monkeypatch):
    monkeypatch.setenv("STAR_TYPING_SAFE", "0")
    import tkinter as tk
    from stamina.cockpit import Cockpit

    app = Cockpit()
    try:
        pending = dict(app._factories)
        assert pending, "ожидали отложенные фабрики"
        app._build_pending()
        assert app._factories == pending
        assert not any(k in app.screens for k in pending)
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
