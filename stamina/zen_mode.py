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


def mark_handled(event) -> None:
    """Пометить: cockpit уже обработал Ctrl+O/Esc, страница не должна повторить."""
    try:
        setattr(event, "_zen_mode_handled", True)
    except Exception:
        pass


def was_handled(event) -> bool:
    # unittest.mock.Mock отдаёт дочерний Mock для любого атрибута — нужен именно True.
    return getattr(event, "_zen_mode_handled", False) is True


def is_escape(e) -> bool:
    return _is_esc(e)


def double_esc_pending() -> bool:
    """Первый Esc уже нажат недавно — следующий закроет зенид (или шаг назад)."""
    return bool(_ESC._at and (time.monotonic() - _ESC._at) <= ESC_WINDOW)


def _is_esc(e) -> bool:
    ks = (getattr(e, "keysym", "") or "").lower()
    return ks == "escape" or int(getattr(e, "keycode", 0) or 0) == 27


def _contains(ancestor, widget) -> bool:
    """ancestor — сам widget или один из его предков по дереву Tk."""
    node = widget
    while node is not None:
        if node is ancestor:
            return True
        node = getattr(node, "master", None)
    return False


def _notify(widget, on: bool) -> None:
    """Один путь раскладки: хук ищется на виджете или его владельце выше по дереву."""
    node = widget
    while node is not None:
        method = getattr(node, "after_zen_toggle", None)
        if callable(method):
            try:
                method(on)
            except Exception:  # noqa: BLE001 — сбой раскладки не должен ломать вход/выход
                pass
            return
        node = getattr(node, "master", None)


def enter(widget) -> bool:
    if not _alive(widget) or not hasattr(widget, "winfo_toplevel"):
        return False
    if is_active(widget):
        return True
    previous = active_widget()
    if previous is not None and previous is not widget:
        rec = _ACTIVE.pop(id(previous), None)
        if rec is not None and not _contains(previous, widget):
            # Разные зениды: старый раскладываем обратно. Если же новый зенид
            # живёт ВНУТРИ предыдущего (грамматика внутри рабочего окна опытного
            # вида), рабочее окно обязано остаться открытым — иначе экран чёрный.
            try:
                rec[1].restore()
            finally:
                _notify(previous, False)
    from stamina.english.ui import FocusMode
    mode = FocusMode(widget)
    _ACTIVE[id(widget)] = (widget, mode)
    _ESC.reset()
    _notify(widget, True)
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
        _notify(target, False)
    return True


def toggle(widget) -> bool:
    if is_active(widget):
        exit_zen(widget)
        return False
    return enter(widget)


def handle_escape(widget=None) -> bool:
    """Один общий таймер двойного Esc для всех экранов зенида."""
    if widget is None:
        widget = active_widget()
    if not is_active(widget):
        _ESC.reset()
        return False
    if _ESC.tap():
        exit_zen(widget)
        return True
    return False


def handle_key(e, widget=None, *, allow_esc: bool = True) -> bool:
    if widget is None:
        widget = active_widget() or getattr(e, "widget", None)
    if is_zen_hotkey(e):
        mark_handled(e)
        if widget is not None:
            toggle(widget)
        return True
    if _is_esc(e):
        return handle_escape(widget)
    if is_active(widget):
        _ESC.reset()
    return False
