"""Единый стандарт оценки речи и управления микрофоном (docs/english/SPEECH_SCORING.md).

Только константы и мелкие помощники без Tk-состояния: одни числа для сканера,
миссий, склада, CEFR, книги и уроков. Сами алгоритмы оценки здесь не меняются.
"""
from __future__ import annotations

import tkinter as tk

from stamina.hotkeys import letter_key, typing_in  # noqa: F401  (общий помощник, реэкспорт)

ITEM_OK = 80        # зачёт слова/предложения в одной попытке (= warehouse.FLIP_OK)
RUN_OK = 85         # средняя прогона карточки (= warehouse.PASS_QUALITY)
ADVANCE_MS = 900    # пауза перед авто-переходом: успеть увидеть зелёный результат
MIC_KEYS = ("m", "cyrillic_softsign")      # M (в RU/UK раскладке та же клавиша — «ь»)
HINT_KEYS = ("t", "cyrillic_ie")           # T — подсказка, удерживать (RU/UK — «е»); пробел свободен
FOCUS_KEYS = ("o", "cyrillic_shcha")       # O — фокус-режим рабочей панели (RU/UK — «щ»), Esc — выход


def is_mic_key(e) -> bool:
    return letter_key(e, MIC_KEYS)


def is_hint_key(e) -> bool:
    return letter_key(e, HINT_KEYS)


def is_focus_key(e) -> bool:
    return letter_key(e, FOCUS_KEYS)


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
