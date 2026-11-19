"""Флаги у названия грамматики: рисуются на Tk Canvas, без эмодзи и шрифтов.

Слева от слова «ГРАММАТИКА»: Великобритания для английской (красный Murphy —
британский английский), Германия для немецкой.
"""
from __future__ import annotations

import tkinter as tk

from stamina.theme import BG, px

# Официальные цвета (приближение Pantone для экрана)
DE_BLACK = "#000000"
DE_RED = "#DD0000"
DE_GOLD = "#FFCE00"
UK_BLUE = "#012169"
UK_RED = "#C8102E"
UK_WHITE = "#FFFFFF"


def paint_title_flag(parent: tk.Misc, code: str, *, height: int | None = None) -> tk.Canvas:
    """Нарисовать флаг страны в слоте слева от заголовка. code: 'de' | 'gb'."""
    h = height if height is not None else px(16)
    code = (code or "").lower()
    if code in ("de", "germany", "ger"):
        w = max(2, int(round(h * 5 / 3)))
        return _paint_de(parent, w, h)
    if code in ("gb", "uk", "gb-ukm", "en-gb"):
        w = max(2, int(round(h * 2)))
        return _paint_uk(parent, w, h)
    raise ValueError("unknown flag code: %s" % code)


def _canvas(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    c = tk.Canvas(
        parent, width=w, height=h, bg=BG, highlightthickness=0, bd=0,
        takefocus=0, cursor="arrow")
    c.pack(side=tk.LEFT)
    return c


def _paint_de(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    c = _canvas(parent, w, h)
    band = h / 3
    c.create_rectangle(0, 0, w, band, fill=DE_BLACK, outline="")
    c.create_rectangle(0, band, w, band * 2, fill=DE_RED, outline="")
    c.create_rectangle(0, band * 2, w, h, fill=DE_GOLD, outline="")
    return c


def _paint_uk(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    """Упрощённый, но узнаваемый Union Jack (синее поле, белые и красные кресты)."""
    c = _canvas(parent, w, h)
    c.create_rectangle(0, 0, w, h, fill=UK_BLUE, outline="")
    # Белая диагональ св. Андрея, поверх — красная св. Патрика
    saltire_w = max(3, int(round(h * 0.28)))
    paler_w = max(1, int(round(h * 0.12)))
    c.create_line(0, 0, w, h, fill=UK_WHITE, width=saltire_w)
    c.create_line(0, h, w, 0, fill=UK_WHITE, width=saltire_w)
    c.create_line(0, 0, w, h, fill=UK_RED, width=paler_w)
    c.create_line(0, h, w, 0, fill=UK_RED, width=paler_w)
    # Белый и красный крест св. Георгия
    cross_w = max(4, int(round(h * 0.36)))
    red_w = max(2, int(round(h * 0.20)))
    cx, cy = w / 2, h / 2
    c.create_rectangle(cx - cross_w / 2, 0, cx + cross_w / 2, h, fill=UK_WHITE, outline="")
    c.create_rectangle(0, cy - cross_w / 2, w, cy + cross_w / 2, fill=UK_WHITE, outline="")
    c.create_rectangle(cx - red_w / 2, 0, cx + red_w / 2, h, fill=UK_RED, outline="")
    c.create_rectangle(0, cy - red_w / 2, w, cy + red_w / 2, fill=UK_RED, outline="")
    return c
