"""Общие помощники горячих клавиш, которые не ломают печать.

Правило всего приложения: если фокус в поле ввода, буквы и пробел принадлежат
тексту. Одиночные клавиши-команды (M, T, O…) срабатывают только вне полей.
Модуль без Tk-состояния — его проверяют тесты.
"""
from __future__ import annotations

import sys
import tkinter as tk

# Битовая маска модификаторов в event.state. Ctrl и Shift одинаковы везде,
# а Alt — нет: на X11 это Mod1 (0x8), на Windows — 0x20000, а 0x8 там NumLock.
# Проверять «не Alt» через 0x8 нельзя: с включённым NumLock глохнут Ctrl+M,
# Home и другие хоткеи. Одна правда — здесь, ею пользуются zen.py и cockpit.py.
SHIFT = 0x0001
CTRL = 0x0004
ALT = 0x20000 if sys.platform == "win32" else 0x0008


def typing_in(widget) -> bool:
    """Фокус в поле ввода — пробел и буквы принадлежат тексту, не горячим клавишам."""
    if isinstance(widget, (tk.Entry, tk.Spinbox)):
        return True
    try:
        from tkinter import ttk
        if isinstance(widget, (ttk.Entry, ttk.Spinbox, ttk.Combobox)):
            return True
    except ImportError:  # pragma: no cover
        pass
    if isinstance(widget, tk.Text):
        try:
            return str(widget.cget("state")) == "normal"
        except tk.TclError:
            return False
    return False


def letter_key(e, keys) -> bool:
    """Одиночная клавиша-команда из keys (keysym в нижнем регистре), но не во время набора."""
    return (getattr(e, "keysym", "") or "").lower() in keys and not typing_in(getattr(e, "widget", None))
