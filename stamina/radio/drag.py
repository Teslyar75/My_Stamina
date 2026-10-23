"""Перетаскивание плашки радио мышью; позиция — ОТНОСИТЕЛЬНО окна программы.

Позиция хранится долями свободного места контейнера (0..1 по x и y), поэтому плашка
едет вместе с окном на любой монитор, а при сужении окна остаётся в видимой области.
Двойной щелчок по ручке — сброс на место по умолчанию (``None``).
"""
from __future__ import annotations

import tkinter as tk

Pos = tuple[float, float]


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def to_frac(x: int, y: int, w: int, h: int, cw: int, ch: int) -> Pos:
    """Пиксели левого верхнего угла → доли свободного места (с ограничением)."""
    fx = x / (cw - w) if cw > w else 0.0
    fy = y / (ch - h) if ch > h else 0.0
    return clamp01(fx), clamp01(fy)


def from_frac(pos: Pos, w: int, h: int, cw: int, ch: int) -> tuple[int, int]:
    """Доли → пиксели внутри контейнера (всегда в видимой области)."""
    fx, fy = clamp01(pos[0]), clamp01(pos[1])
    return int(round(fx * max(0, cw - w))), int(round(fy * max(0, ch - h)))


def load(settings: dict, key: str) -> Pos | None:
    v = (settings or {}).get(key)
    try:
        if v and len(v) == 2:
            return clamp01(v[0]), clamp01(v[1])
    except (TypeError, ValueError):
        pass
    return None


class Dragger:
    """Ручка ``handles`` двигает ``widget`` внутри ``container`` (place).

    ``on_change(pos)`` — после отпускания/сброса (pos=None — по умолчанию).
    """

    def __init__(self, widget, container, handles, pos: Pos | None, on_change) -> None:
        self.widget, self.container, self.pos, self.on_change = widget, container, pos, on_change
        self._start = None
        for h in handles:
            h.bind("<ButtonPress-1>", self._press, add="+")
            h.bind("<B1-Motion>", self._motion, add="+")
            h.bind("<ButtonRelease-1>", self._release, add="+")
            h.bind("<Double-Button-1>", self._reset, add="+")
            try:
                h.configure(cursor="fleur")
            except tk.TclError:
                pass

    def size(self) -> tuple[int, int, int, int]:
        w = self.widget
        return (max(1, w.winfo_width() if w.winfo_ismapped() else w.winfo_reqwidth()),
                max(1, w.winfo_height() if w.winfo_ismapped() else w.winfo_reqheight()),
                self.container.winfo_width(), self.container.winfo_height())

    def xy(self) -> tuple[int, int] | None:
        if self.pos is None:
            return None
        return from_frac(self.pos, *self.size())

    def _press(self, e) -> None:
        w = self.widget
        self._start = (e.x_root, e.y_root, w.winfo_rootx() - self.container.winfo_rootx(),
                       w.winfo_rooty() - self.container.winfo_rooty(), False)

    def _motion(self, e) -> None:
        if not self._start:
            return
        sx, sy, x0, y0, moved = self._start
        dx, dy = e.x_root - sx, e.y_root - sy
        if not moved and abs(dx) + abs(dy) < 4:
            return                       # щелчок, а не перетаскивание
        self._start = (sx, sy, x0, y0, True)
        w, h, cw, ch = self.size()
        self.pos = to_frac(x0 + dx, y0 + dy, w, h, cw, ch)
        x, y = from_frac(self.pos, w, h, cw, ch)
        self.widget.place_configure(in_=self.container, x=x, y=y, relx=0, rely=0, anchor="nw")
        self.widget.lift()

    def _release(self, _e) -> None:
        if self._start and self._start[4]:
            self.on_change(self.pos)
        self._start = None

    def _reset(self, _e=None) -> None:
        self.pos = None
        self._start = None
        self.on_change(None)
