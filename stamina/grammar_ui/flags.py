"""Флаги у названия грамматики: рисуются на Tk Canvas, без эмодзи и шрифтов.

Слева от слова «ГРАММАТИКА»: Великобритания для английской (красный Murphy —
британский английский), Германия для немецкой, Франция, Испания, Италия.
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
FR_BLUE = "#002654"
FR_WHITE = "#FFFFFF"
FR_RED = "#ED2939"
ES_RED = "#AA151B"
ES_GOLD = "#F1BF00"
IT_GREEN = "#009246"
IT_WHITE = "#FFFFFF"
IT_RED = "#CE2B37"


def paint_title_flag(parent: tk.Misc, code: str, *, height: int | None = None) -> tk.Canvas:
    """Нарисовать флаг страны в слоте слева от заголовка. code: 'de' | 'gb' | 'fr' | 'es' | 'it'."""
    h = height if height is not None else px(16)
    code = (code or "").lower()
    if code in ("de", "germany", "ger"):
        w = max(2, int(round(h * 5 / 3)))
        return _paint_de(parent, w, h)
    if code in ("gb", "uk", "gb-ukm", "en-gb"):
        w = max(2, int(round(h * 2)))
        return _paint_uk(parent, w, h)
    if code in ("fr", "france", "fra"):
        w = max(2, int(round(h * 5 / 3)))
        return _paint_fr(parent, w, h)
    if code in ("es", "spain", "esp"):
        w = max(2, int(round(h * 5 / 3)))
        return _paint_es(parent, w, h)
    if code in ("it", "italy", "ita"):
        w = max(2, int(round(h * 5 / 3)))
        return _paint_it(parent, w, h)
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


def _paint_fr(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    """Французский триколор: синий, белый, красный (вертикальные полосы)."""
    c = _canvas(parent, w, h)
    band = w / 3
    c.create_rectangle(0, 0, band, h, fill=FR_BLUE, outline="")
    c.create_rectangle(band, 0, band * 2, h, fill=FR_WHITE, outline="")
    c.create_rectangle(band * 2, 0, w, h, fill=FR_RED, outline="")
    return c


def _paint_es(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    """Испанский флаг: красный, золотой, красный (горизонтальные полосы 1:2:1)."""
    c = _canvas(parent, w, h)
    band = h / 4
    c.create_rectangle(0, 0, w, band, fill=ES_RED, outline="")
    c.create_rectangle(0, band, w, band * 3, fill=ES_GOLD, outline="")
    c.create_rectangle(0, band * 3, w, h, fill=ES_RED, outline="")
    return c


def _paint_it(parent: tk.Misc, w: int, h: int) -> tk.Canvas:
    """Итальянский триколор: зеленый, белый, красный (вертикальные полосы)."""
    c = _canvas(parent, w, h)
    band = w / 3
    c.create_rectangle(0, 0, band, h, fill=IT_GREEN, outline="")
    c.create_rectangle(band, 0, band * 2, h, fill=IT_WHITE, outline="")
    c.create_rectangle(band * 2, 0, w, h, fill=IT_RED, outline="")
    return c
