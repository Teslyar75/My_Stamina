"""Общий зенид приложения: ⛶ / Ctrl+O вход, двойной Esc выход.

Состояние живёт в этом модуле и не трогает сессию зенида грамматики.
Один и тот же FocusMode сохраняется при входе и восстанавливается при выходе.
"""
from __future__ import annotations

import time

from stamina.grammar_ui.focus import is_o_physical
from stamina.hotkeys import CTRL

ESC_WINDOW = 0.6

_ACTIVE: dict[int, tuple[object, object]] = {}


class EscDouble:
    def __init__(self, window: float = ESC_WINDOW) -> None:
        self.window = window
        self._at = 0.0

    def reset(self) -> None:
        self._at = 0.0

    def tap(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self._at and (now - self._at) <= self.window:
            self._at = 0.0
            return True
        self._at = now
        return False


_ESC = EscDouble()


def _alive(widget) -> bool:
    try:
        return bool(widget is not None and widget.winfo_exists())
    except Exception:
        return False


def active_widget():
    for widget, _mode in list(_ACTIVE.values()):
        if _alive(widget):
            return widget
    _ACTIVE.clear()
    return None


def active_mode():
    rec = _ACTIVE.get(id(active_widget())) if active_widget() is not None else None
    return rec[1] if rec else None


def mode_of(widget=None):
    if widget is None:
        widget = active_widget()
    rec = _ACTIVE.get(id(widget)) if widget is not None else None
    return rec[1] if rec else None


def is_active(widget=None) -> bool:
    current = active_widget()
    if current is None:
        return False
    return widget is None or current is widget


def is_zen_hotkey(e) -> bool:
    state = int(getattr(e, "state", 0) or 0)
    return bool(state & CTRL) and is_o_physical(e)


def _is_esc(e) -> bool:
    ks = (getattr(e, "keysym", "") or "").lower()
    return ks == "escape" or int(getattr(e, "keycode", 0) or 0) == 27


def enter(widget) -> bool:
    if not _alive(widget) or not hasattr(widget, "winfo_toplevel"):
        return False
    if is_active(widget):
        return True
    exit_zen()
    from stamina.english.ui import FocusMode
    mode = FocusMode(widget)
    _ACTIVE[id(widget)] = (widget, mode)
    _ESC.reset()
    return True


def exit_zen(widget=None) -> bool:
    target = widget if widget is not None else active_widget()
    if target is None:
        return False
    rec = _ACTIVE.pop(id(target), None)
    if rec is None:
        return False
    try:
        rec[1].restore()
    finally:
        _ESC.reset()
    return True


def toggle(widget) -> bool:
    if is_active(widget):
        exit_zen(widget)
        return False
    return enter(widget)


def handle_key(e, widget=None, *, allow_esc: bool = True) -> bool:
    if widget is None:
        widget = active_widget() or getattr(e, "widget", None)
    if is_zen_hotkey(e):
        if widget is not None:
            toggle(widget)
        return True
    if _is_esc(e):
        if not is_active(widget):
            _ESC.reset()
            return False
        if _ESC.tap():
            exit_zen(widget)
            return True
        return False
    if is_active(widget):
        _ESC.reset()
    return False
