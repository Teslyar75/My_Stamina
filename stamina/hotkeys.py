"""Общие помощники горячих клавиш, которые не ломают печать.

Правило всего приложения: если фокус в поле ввода, буквы и пробел принадлежат
тексту. Одиночные клавиши-команды (M, T, O…) срабатывают только вне полей.
Модуль без Tk-состояния — его проверяют тесты.
"""
from __future__ import annotations

import tkinter as tk


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
