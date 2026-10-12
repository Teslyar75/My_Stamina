"""Адаптивная вёрстка: wraplength по ширине, перенос кнопок, скроллбар HUD."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from stamina.theme import BG2, CYAN, PANEL, PANEL_HI, px


def bind_wraplength(label: tk.Label, host: tk.Misc | None = None, *, margin: int = 16) -> None:
    """Обновлять wraplength лейбла при изменении ширины host (по умолчанию — master)."""
    host = host or label.master
    last = {"w": -1}

    def _on(e) -> None:
        if e.widget is not host:
            return
        w = int(e.width) - px(margin)
        if w <= 40 or w == last["w"]:
            return
        last["w"] = w
        try:
            label.configure(wraplength=w)
        except tk.TclError:
            pass

    host.bind("<Configure>", _on, add="+")


def bind_wraplengths(labels: list[tk.Label], host: tk.Misc, *, margin: int = 16) -> None:
    last = {"w": -1}

    def _on(e) -> None:
        if e.widget is not host:
            return
        w = int(e.width) - px(margin)
        if w <= 40 or w == last["w"]:
            return
        last["w"] = w
        for lab in labels:
            try:
                lab.configure(wraplength=w)
            except tk.TclError:
                pass

    host.bind("<Configure>", _on, add="+")


def ensure_hud_scrollbar_style(widget: tk.Misc) -> str:
    """Стиль ttk-скроллбара под тёмный HUD (без системной «белой» полосы)."""
    name = "Hud.Vertical.TScrollbar"
    style = ttk.Style(widget)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(name, background=PANEL_HI, troughcolor=BG2, bordercolor=PANEL,
                    arrowcolor=CYAN, lightcolor=PANEL_HI, darkcolor=PANEL_HI,
                    arrowsize=px(12))
    return name


def make_vscroll(parent: tk.Misc, **kw) -> ttk.Scrollbar:
    return ttk.Scrollbar(parent, orient=tk.VERTICAL, style=ensure_hud_scrollbar_style(parent), **kw)


class FlowFrame(tk.Frame):
    """Ряд кнопок с переносом через обычный pack (без Configure/place).

    Прежняя реализация на place+Configure зацикливала очередь Tk и после ввода
    пароля пульт «замирал» (события after не доходили).
    """

    def __init__(self, master, *, bg=None, padx: int = 2, pady: int = 2, **kw) -> None:
        super().__init__(master, bg=bg if bg is not None else master.cget("bg"), **kw)
        self._padx = px(padx)
        self._pady = px(pady)

    def add(self, widget: tk.Misc) -> tk.Misc:
        widget.pack(side=tk.LEFT, padx=(0, self._padx), pady=self._pady)
        return widget
