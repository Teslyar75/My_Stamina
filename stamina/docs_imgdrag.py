"""Размер картинки в документе — перетаскиванием правого нижнего угла.

Мышь у угла картинки (зона GRIP px) меняет курсор; нажали и тянете — картинка
меняет ширину на лету (быстрый ресайз), отпустили — чистый ресайз и ОДИН шаг
Ctrl+Z (docs_undo.record_resize). Высота следует за шириной (пропорции).
Подмешивается в DocsScreen: нужны self.text, self._widths, self._set_width,
self.undo, self._changed.
"""
from __future__ import annotations

import re
import tkinter as tk

from stamina import docs

GRIP = 14                 # экранные px от угла
CURSOR = "bottom_right_corner"   # стандартный курсор Tk: есть и в X11, и в Windows
THROTTLE_MS = 30


class ImageDragMixin:
    def setup_image_drag(self) -> None:
        self._drag: dict | None = None
        self._drag_job = None
        self._grip_on = False
        t = self.text
        t.bind("<Motion>", self._grip_motion, add="+")
        t.bind("<Leave>", lambda _e: self._grip_cursor(False), add="+")
        t.bind("<ButtonPress-1>", self._grip_press, add="+")
        t.bind("<B1-Motion>", self._grip_drag, add="+")
        t.bind("<ButtonRelease-1>", self._grip_release, add="+")

    # -- поиск угла --------------------------------------------------------------
    def image_corner_at(self, x: int, y: int) -> tuple[str, str] | None:
        """(имя картинки, индекс), если точка (x, y) — у правого нижнего угла видимой картинки."""
        t = self.text
        try:
            first = t.index("@0,0")
            last = t.index(f"@0,{t.winfo_height()} lineend")
            items = t.dump(first, f"{last}+1c", image=True)
        except tk.TclError:
            return None
        for key, value, idx in items:
            if key != "image":
                continue
            box = t.bbox(idx)
            if not box:
                continue
            bx, by, bw, bh = box
            right, bottom = bx + bw, by + bh
            if right - GRIP <= x <= right + 2 and bottom - GRIP <= y <= bottom + 2:
                return re.sub(r"#\d+$", "", value), idx
        return None

    def _grip_cursor(self, on: bool) -> None:
        if on == self._grip_on:
            return
        self._grip_on = on
        self.text.config(cursor=CURSOR if on else "xterm")

    def _grip_motion(self, e):
        if self._drag is None:
            self._grip_cursor(self.image_corner_at(e.x, e.y) is not None)

    # -- перетаскивание ----------------------------------------------------------
    def _grip_press(self, e):
        hit = self.image_corner_at(e.x, e.y)
        if hit is None or not getattr(self, "doc", None):
            return None
        name, idx = hit
        bx, _by, bw, _bh = self.text.bbox(idx)
        old = self._widths.get(name) or 0
        if not old:          # 0 = «как есть»: логическая ширина из экранной
            old = max(1, round((bw - 4) / max(docs.ui_scale(), 0.01)))
        self._drag = {"name": name, "old": old, "x0": e.x, "w": old,
                      "max": self._max_drag_width()}
        self._grip_cursor(True)
        return "break"       # не начинать выделение текста

    def _max_drag_width(self) -> int:
        t = self.text
        pad = int(t.cget("padx")) * 2 + 8
        return max(self.MIN_IMG_W, round((t.winfo_width() - pad) / max(docs.ui_scale(), 0.01)))

    def drag_width(self, dx: int, d: dict | None = None) -> int:
        d = d or self._drag
        w = d["old"] + round(dx / max(docs.ui_scale(), 0.01))
        return max(self.MIN_IMG_W, min(d["max"], w))

    def _grip_drag(self, e):
        d = self._drag
        if d is None:
            return None
        d["w"] = self.drag_width(e.x - d["x0"])
        if self._drag_job is None:
            self._drag_job = self.after(THROTTLE_MS, self._drag_apply)
        return "break"

    def _drag_apply(self) -> None:
        self._drag_job = None
        d = self._drag
        if d is not None:
            self._set_width(d["name"], d["w"], fast=True)

    def _grip_release(self, e):
        d = self._drag
        if d is None:
            return None
        if self._drag_job is not None:
            self.after_cancel(self._drag_job)
            self._drag_job = None
        self._drag = None
        final = self.drag_width(e.x - d["x0"], d)
        self._grip_cursor(self.image_corner_at(e.x, e.y) is not None)
        self.finish_drag(d["name"], d["old"], final)
        return "break"

    def finish_drag(self, name: str, old: int, new: int) -> None:
        """Конец перетаскивания: чистая картинка и один шаг истории."""
        self._set_width(name, new)
        if new != old:
            self.undo.record_resize(name, old, new)
            self._changed()
