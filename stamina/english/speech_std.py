"""Единый стандарт оценки речи и управления микрофоном (docs/english/SPEECH_SCORING.md).

Только константы и мелкие помощники без Tk-состояния: одни числа для сканера,
миссий, склада, CEFR, книги и уроков. Сами алгоритмы оценки здесь не меняются.
"""
from __future__ import annotations

import tkinter as tk

ITEM_OK = 80        # зачёт слова/предложения в одной попытке (= warehouse.FLIP_OK)
RUN_OK = 85         # средняя прогона карточки (= warehouse.PASS_QUALITY)
ADVANCE_MS = 900    # пауза перед авто-переходом: успеть увидеть зелёный результат
MIC_KEYS = ("m", "space")


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


def is_mic_key(e) -> bool:
    return (getattr(e, "keysym", "") or "").lower() in MIC_KEYS and not typing_in(getattr(e, "widget", None))


def passed(score) -> bool:
    return score is not None and int(score) >= ITEM_OK


def advance_later(widget, step, still_same) -> None:
    """После зачёта перейти дальше, если ученик за паузу сам ничего не переключил."""
    def go():
        try:
            if widget.winfo_exists() and still_same():
                step()
        except tk.TclError:
            pass
    widget.after(ADVANCE_MS, go)
