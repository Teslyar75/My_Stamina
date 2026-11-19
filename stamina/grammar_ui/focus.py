"""Клавиши и сессия зенида грамматики (O/Щ, Ctrl+O, двойной Esc).

Переиспользует общий FocusMode из английского сканера и те же FOCUS_KEYS.
Состояние «хочу зенид» живёт только в сессии процесса — не пишется в пилота.
"""
from __future__ import annotations

import time

from stamina.english.speech_std import FOCUS_KEYS
from stamina.hotkeys import ALT, CTRL, typing_in

# Физическая клавиша O на Windows (VK_O); на других ОС опираемся на keysym.
O_KEYCODE = 79
ESC_DOUBLE_SEC = 0.7

_session_wanted = False


def session_wanted() -> bool:
    return _session_wanted


def set_session_wanted(on: bool) -> None:
    global _session_wanted
    _session_wanted = bool(on)


def reset_session() -> None:
    """Для тестов."""
    set_session_wanted(False)


def is_o_physical(e) -> bool:
    """O/o/Щ/щ в любой раскладке и регистре, плюс физическая клавиша O."""
    ks = (getattr(e, "keysym", "") or "").lower()
    ch = (getattr(e, "char", "") or "").lower()
    code = int(getattr(e, "keycode", 0) or 0)
    if code == O_KEYCODE:
        return True
    return ks in FOCUS_KEYS or ks in ("o", "щ") or ch in ("o", "щ")


def is_grammar_focus_key(e) -> bool:
    """Переключить зенид грамматики: O/Щ или Ctrl+O.

    Одиночная буква не срабатывает, если фокус в настоящем Entry/Text.
    Аккорд Ctrl+O срабатывает и тогда: это не ввод буквы.
    """
    state = int(getattr(e, "state", 0) or 0)
    if state & ALT:
        return False
    if not is_o_physical(e):
        return False
    if typing_in(getattr(e, "widget", None)) and not (state & CTRL):
        return False
    return True


class EscDouble:
    """Первый Esc запоминается, второй в окне ESC_DOUBLE_SEC подтверждает выход."""

    def __init__(self) -> None:
        self._at = 0.0

    def reset(self) -> None:
        self._at = 0.0

    def tap(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self._at and (now - self._at) <= ESC_DOUBLE_SEC:
            self._at = 0.0
            return True
        self._at = now
        return False
