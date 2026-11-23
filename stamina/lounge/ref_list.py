"""Прокручиваемый список строк для панелей-учебников.

Один и тот же список нужен и Docker/Linux/PowerShell (команды), и VIM
(клавиши), поэтому он живёт отдельно от панелей. Строка — заголовок
(моноширинный) и пояснение под ним; клик по любой части отдаёт ключ строки
в ``on_pick``.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from stamina import theme, wheel_router
from stamina.adapt import make_vscroll
from stamina.theme import CYAN, MUTED, PANEL, TEXT, blend, px


class ScrollList(tk.Frame):
    """Холст + внутренняя рамка + колесо и полоса прокрутки."""

    def __init__(self, master, *, bg: str = PANEL) -> None:
        super().__init__(master, bg=bg)
        self._bg = bg
        self._wrap = px(240)
        self._rows: list[dict] = []
        self._selected = None
        self._sb = make_vscroll(self)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, yscrollcommand=self._sb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._sb.configure(command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", tags="inner")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        wheel_router.bind_scroll(self.canvas, self._wheel)
        wheel_router.bind_scroll(self.inner, self._wheel)

    # -- прокрутка ----------------------------------------------------------
    def _on_inner(self, _e=None) -> None:
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _on_canvas(self, e) -> None:
        if e.width < 4:
            return
        self.canvas.itemconfigure("inner", width=e.width)
        wrap = max(px(100), e.width - px(14))
        if wrap != self._wrap:
            self._wrap = wrap
            for row in self._rows:
                for lbl in row["labels"]:
                    lbl.configure(wraplength=wrap)

    def _wheel(self, d: int) -> None:
        self.canvas.yview_scroll(d * 3, "units")

    # -- наполнение ---------------------------------------------------------
    def clear(self) -> None:
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        self._selected = None
        self.canvas.yview_moveto(0)

    def add(self, key, title: str, note: str, on_pick: Callable, *, color: str = TEXT) -> None:
        frame = tk.Frame(self.inner, bg=self._bg, cursor="hand2")
        frame.pack(fill=tk.X, padx=px(2), pady=px(1))
        head = tk.Label(frame, text=title, bg=self._bg, fg=color, font=theme.font(10, mono=True),
                        anchor="w", justify="left", wraplength=self._wrap)
        head.pack(fill=tk.X, padx=px(4))
        labels = [head]
        if note:
            tail = tk.Label(frame, text=note, bg=self._bg, fg=MUTED, font=theme.font(9),
                            anchor="w", justify="left", wraplength=self._wrap)
            tail.pack(fill=tk.X, padx=px(4))
            labels.append(tail)
        row = {"key": key, "frame": frame, "labels": labels}
        self._rows.append(row)
        for widget in [frame, *labels]:
            widget.bind("<Button-1>", lambda _e, k=key: on_pick(k))
            widget.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
            widget.bind("<Leave>", lambda _e, r=row: self._hover(r, False))

    def _hover(self, row: dict, on: bool) -> None:
        if row["key"] == self._selected:
            return
        bg = blend(self._bg, CYAN, 0.14) if on else self._bg
        row["frame"].configure(bg=bg)
        for lbl in row["labels"]:
            lbl.configure(bg=bg)

    def select(self, key) -> None:
        previous = self._selected
        self._selected = key
        for row in self._rows:
            if row["key"] in (key, previous):
                self._paint(row)

    def _paint(self, row: dict) -> None:
        on = row["key"] == self._selected
        bg = blend(self._bg, CYAN, 0.22) if on else self._bg
        row["frame"].configure(bg=bg)
        for lbl in row["labels"]:
            lbl.configure(bg=bg)
            if on:
                lbl.configure(fg=TEXT if lbl is row["labels"][-1] else CYAN)
            elif len(row["labels"]) > 1 and lbl is row["labels"][-1]:
                lbl.configure(fg=MUTED)

    def keys(self) -> list:
        return [row["key"] for row in self._rows]
