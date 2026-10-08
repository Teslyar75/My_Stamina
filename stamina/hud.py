"""HUD-виджеты пульта: кнопки, панели, приборы, иллюминатор, клавиатура.

Всё нарисовано на обычном ``tkinter.Canvas`` — без сторонних библиотек,
поэтому работает быстро даже на слабом ноутбуке.
"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from stamina import layouts, theme
from stamina.theme import (
    AMBER, AMBER_DIM, BG, BG2, CYAN, CYAN_DEEP, CYAN_DIM, FAINT, GREEN, LINE,
    LINE_HI, MUTED, PANEL, RED, RED_DIM, TEXT, blend, chamfer, px,
)


def _bg_of(widget: tk.Misc) -> str:
    try:
        return widget.cget("bg")
    except tk.TclError:
        return BG


# ---------------------------------------------------------------------------
# Кнопка
# ---------------------------------------------------------------------------

class HudButton(tk.Canvas):
    """Плоская неоновая кнопка со срезанными углами."""

    def __init__(self, master: tk.Misc, text: str, command: Callable[[], None] | None = None,
                 *, color: str = CYAN, width: int | None = None, height: int = 34,
                 font_size: int = 10, bold: bool = True, active: bool = False) -> None:
        self._font = theme.font(font_size, bold)
        self._text = text
        measured = tkfont.Font(font=self._font).measure(text)
        w = px(width) if width else measured + px(30)
        super().__init__(master, width=w, height=px(height), bg=_bg_of(master),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.color = color
        self._hover = False
        self._pressed = False
        self._active = active
        self._enabled = True
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _set_hover(self, value: bool) -> None:
        self._hover = value
        if not value:
            self._pressed = False
        self._draw()

    def _on_press(self, _e) -> None:
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, e) -> None:
        was = self._pressed
        self._pressed = False
        self._draw()
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        if was and inside and self._enabled and self.command:
            self.command()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_active(self, value: bool) -> None:
        self._active = value
        self._draw()

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        self.configure(cursor="hand2" if value else "arrow")
        self._draw()

    def set_color(self, color: str) -> None:
        self.color = color
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        c = min(px(8), h // 3)
        col = self.color
        if not self._enabled:
            fill, outline, fg = PANEL, FAINT, FAINT
        elif self._pressed:
            fill, outline, fg = blend(col, BG, 0.55), col, "#FFFFFF"
        elif self._active:
            fill, outline, fg = blend(col, BG, 0.78), col, col
        elif self._hover:
            fill, outline, fg = blend(col, BG, 0.88), col, TEXT
        else:
            fill, outline, fg = PANEL, blend(col, BG, 0.5), blend(col, TEXT, 0.45)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill=fill, outline=outline,
                            width=2 if self._active else 1)
        if self._enabled and (self._active or self._hover):
            self.create_line(1 + c, 1, 1 + c + px(14), 1, fill=col, width=3)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)


# ---------------------------------------------------------------------------
# Панель-контейнер
# ---------------------------------------------------------------------------

class HudPanel(tk.Canvas):
    """Рамка со срезанными углами; содержимое кладите в ``.body``."""

    def __init__(self, master: tk.Misc, title: str = "", *, accent: str = CYAN,
                 pad: int = 10) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0)
        self.title = title
        self.accent = accent
        self.body = tk.Frame(self, bg=PANEL)
        top = px(26) if title else px(pad)
        self.body.pack(fill=tk.BOTH, expand=True, padx=px(pad), pady=(top, px(pad)))
        self.bind("<Configure>", lambda _e: self._draw())

    def _draw(self) -> None:
        self.delete("frame")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        c = px(12)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill=PANEL, outline=LINE_HI,
                            tags="frame")
        a = self.accent
        self.create_line(1, 1 + c, 1, 1 + c + px(22), fill=a, width=2, tags="frame")
        self.create_line(1 + c, 1, 1 + c + px(40), 1, fill=a, width=2, tags="frame")
        self.create_line(w - 2, h - 2 - c, w - 2, h - 2 - c - px(22), fill=a, width=2, tags="frame")
        self.create_line(w - 2 - c, h - 2, w - 2 - c - px(40), h - 2, fill=a, width=2, tags="frame")
        if self.title:
            self.create_text(px(16), px(13), text=self.title, anchor="w",
                             fill=blend(a, TEXT, 0.25), font=theme.font(9, True), tags="frame")
        self.tag_lower("frame")


# ---------------------------------------------------------------------------
# Спидометр
# ---------------------------------------------------------------------------

class SpeedGauge(tk.Canvas):
    START, SWEEP = 215.0, 250.0

    def __init__(self, master: tk.Misc, *, title: str = "СКОРОСТЬ",
                 unit: str = "ЗН/МИН", vmax: int = 400) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         width=px(210), height=px(200))
        self.title, self.unit, self.vmax = title, unit, vmax
        self.target = 0.0
        self.shown = 0.0
        self.goal: float | None = None
        self.sub = ""
        self.bind("<Configure>", lambda _e: self._draw_all())

    def set(self, value: float, *, goal: float | None = None, sub: str = "") -> None:
        self.target = max(0.0, value)
        self.goal = goal
        self.sub = sub
        new_max = 400 if max(self.target, goal or 0) < 380 else 600
        if new_max != self.vmax:
            self.vmax = new_max
            self._draw_all()
        else:
            self._draw_dyn()

    def animate(self) -> bool:
        diff = self.target - self.shown
        if abs(diff) < 0.4:
            if self.shown != self.target:
                self.shown = self.target
                self._draw_dyn()
            return False
        self.shown += diff * 0.22
        self._draw_dyn()
        return True

    def _geom(self):
        w, h = self.winfo_width(), self.winfo_height()
        r = max(10, min(w / 2 - px(10), h / 2 - px(6)))
        return w / 2, h / 2 + px(8), r

    def _angle(self, v: float) -> float:
        return self.START - self.SWEEP * max(0.0, min(1.0, v / self.vmax))

    def _draw_all(self) -> None:
        self.delete("all")
        cx, cy, r = self._geom()
        if r < 20:
            return
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=BG2, outline=LINE)
        self.create_oval(cx - r * 0.93, cy - r * 0.93, cx + r * 0.93, cy + r * 0.93,
                         outline=blend(LINE, BG, 0.4))
        tr = r * 0.80
        self.create_arc(cx - tr, cy - tr, cx + tr, cy + tr, start=self.START - self.SWEEP,
                        extent=self.SWEEP, style=tk.ARC, outline=CYAN_DEEP, width=px(9))
        step = 20
        for v in range(0, self.vmax + 1, step):
            a = math.radians(self._angle(v))
            major = v % 100 == 0
            r1 = r * (0.86 if major else 0.89)
            r2 = r * 0.95
            self.create_line(cx + r1 * math.cos(a), cy - r1 * math.sin(a),
                             cx + r2 * math.cos(a), cy - r2 * math.sin(a),
                             fill=MUTED if major else FAINT, width=2 if major else 1)
            if major:
                rl = r * 0.64
                self.create_text(cx + rl * math.cos(a), cy - rl * math.sin(a), text=str(v),
                                 fill=MUTED, font=theme.font(8))
        self.create_text(px(4), px(4), text=self.title, anchor="nw",
                         fill=blend(CYAN, TEXT, 0.3), font=theme.font(9, True))
        self._draw_dyn()

    def _draw_dyn(self) -> None:
        self.delete("dyn")
        cx, cy, r = self._geom()
        if r < 20:
            return
        tr = r * 0.80
        frac = max(0.0, min(1.0, self.shown / self.vmax))
        reached = self.goal is not None and self.shown >= self.goal
        col = GREEN if reached else CYAN
        if frac > 0.002:
            self.create_arc(cx - tr, cy - tr, cx + tr, cy + tr, start=self.START,
                            extent=-self.SWEEP * frac, style=tk.ARC,
                            outline=blend(col, BG, 0.55), width=px(13), tags="dyn")
            self.create_arc(cx - tr, cy - tr, cx + tr, cy + tr, start=self.START,
                            extent=-self.SWEEP * frac, style=tk.ARC,
                            outline=col, width=px(5), tags="dyn")
        if self.goal:
            a = math.radians(self._angle(self.goal))
            self.create_line(cx + r * 0.70 * math.cos(a), cy - r * 0.70 * math.sin(a),
                             cx + r * 0.97 * math.cos(a), cy - r * 0.97 * math.sin(a),
                             fill=AMBER, width=3, tags="dyn")
        a = math.radians(self._angle(self.shown))
        nl = r * 0.74
        self.create_line(cx, cy, cx + nl * math.cos(a), cy - nl * math.sin(a),
                         fill=blend(AMBER, BG, 0.5), width=px(6), tags="dyn")
        self.create_line(cx, cy, cx + nl * math.cos(a), cy - nl * math.sin(a),
                         fill=AMBER, width=px(2), tags="dyn")
        hub = px(7)
        self.create_oval(cx - hub, cy - hub, cx + hub, cy + hub, fill=AMBER_DIM,
                         outline=AMBER, tags="dyn")
        self.create_text(cx, cy + r * 0.40, text=f"{int(round(self.shown))}",
                         fill=TEXT, font=theme.font(22, True, mono=True), tags="dyn")
        self.create_text(cx, cy + r * 0.66, text=self.unit, fill=MUTED,
                         font=theme.font(8, True), tags="dyn")
        if self.sub:
            self.create_text(px(4), px(22), text=self.sub, anchor="nw",
                             fill=MUTED, font=theme.font(8), tags="dyn")


# ---------------------------------------------------------------------------
# Кольцевой индикатор
# ---------------------------------------------------------------------------

class RingGauge(tk.Canvas):
    def __init__(self, master: tk.Misc, *, title: str = "ТОЧНОСТЬ") -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         width=px(200), height=px(170))
        self.title = title
        self.value: float | None = None
        self.sub = ""
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, value: float | None, sub: str = "") -> None:
        if value == self.value and sub == self.sub:
            return
        self.value, self.sub = value, sub
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        r = min(w / 2 - px(12), h / 2 - px(12))
        if r < 15:
            return
        cx, cy = w / 2, h / 2 + px(6)
        self.create_text(px(4), px(4), text=self.title, anchor="nw",
                         fill=blend(CYAN, TEXT, 0.3), font=theme.font(9, True))
        # деления по кругу
        for i in range(40):
            a = math.radians(90 - i * 9)
            r1, r2 = r * 1.04, r * (1.12 if i % 5 == 0 else 1.08)
            self.create_line(cx + r1 * math.cos(a), cy - r1 * math.sin(a),
                             cx + r2 * math.cos(a), cy - r2 * math.sin(a), fill=FAINT)
        tr = r * 0.9
        self.create_oval(cx - tr, cy - tr, cx + tr, cy + tr, outline=CYAN_DEEP, width=px(9))
        v = self.value
        if v is None:
            col, label = MUTED, "—"
        else:
            col = GREEN if v >= 96 else (AMBER if v >= 90 else RED)
            label = f"{v:.1f}%"
            frac = max(0.0, min(1.0, v / 100))
            if frac > 0:
                self.create_arc(cx - tr, cy - tr, cx + tr, cy + tr, start=90,
                                extent=-359.9 * frac, style=tk.ARC,
                                outline=blend(col, BG, 0.55), width=px(13))
                self.create_arc(cx - tr, cy - tr, cx + tr, cy + tr, start=90,
                                extent=-359.9 * frac, style=tk.ARC, outline=col, width=px(5))
        self.create_text(cx, cy - px(4), text=label, fill=TEXT if v is not None else MUTED,
                         font=theme.font(17, True, mono=True))
        if self.sub:
            self.create_text(cx, cy + r * 0.42, text=self.sub, fill=MUTED, font=theme.font(8, True))


# ---------------------------------------------------------------------------
# Сегментная шкала и цифровые табло
# ---------------------------------------------------------------------------

class SegmentBar(tk.Canvas):
    def __init__(self, master: tk.Misc, title: str, *, segments: int = 16,
                 color: str = CYAN, height: int = 44) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         height=px(height), width=px(200))
        self.title, self.segments, self.color = title, segments, color
        self.value: float | None = None
        self.text = "—"
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, value: float | None, text: str) -> None:
        if value == self.value and text == self.text:
            return
        self.value, self.text = value, text
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        self.create_text(px(4), px(2), text=self.title, anchor="nw",
                         fill=blend(CYAN, TEXT, 0.3), font=theme.font(9, True))
        self.create_text(w - px(4), px(2), text=self.text, anchor="ne", fill=TEXT,
                         font=theme.font(10, True, mono=True))
        y1, y2 = h * 0.52, h - px(4)
        gap = px(3)
        sw = (w - px(8) - gap * (self.segments - 1)) / self.segments
        filled = 0 if self.value is None else round(self.value * self.segments)
        for i in range(self.segments):
            x1 = px(4) + i * (sw + gap)
            if i < filled:
                t = i / max(1, self.segments - 1)
                col = blend(RED, AMBER, t * 2) if t < 0.5 else blend(AMBER, GREEN, (t - 0.5) * 2)
                if self.color != "auto":
                    col = self.color
                self.create_rectangle(x1, y1, x1 + sw, y2, fill=col, outline=col)
            else:
                self.create_rectangle(x1, y1, x1 + sw, y2, fill=BG2, outline=LINE)


class Readouts(tk.Canvas):
    """Колонка цифровых табло: (подпись, значение, цвет)."""

    def __init__(self, master: tk.Misc, rows: int = 4) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         width=px(200), height=px(rows * 46))
        self.rows: list[tuple[str, str, str]] = []
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, rows: list[tuple[str, str, str]]) -> None:
        if rows == self.rows:
            return
        self.rows = rows
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if not self.rows or w < 20:
            return
        rh = h / len(self.rows)
        for i, (title, value, color) in enumerate(self.rows):
            y = i * rh
            self.create_line(px(4), y + rh - px(3), w - px(4), y + rh - px(3), fill=LINE)
            self.create_rectangle(px(4), y + rh * 0.30, px(7), y + rh * 0.78,
                                  fill=color, outline=color)
            self.create_text(px(13), y + rh * 0.30, text=title, anchor="nw", fill=MUTED,
                             font=theme.font(8, True))
            self.create_text(w - px(4), y + rh * 0.55, text=value, anchor="e", fill=color,
                             font=theme.font(15, True, mono=True))


# ---------------------------------------------------------------------------
# Иллюминатор — строка набора на фоне звёзд
# ---------------------------------------------------------------------------

class Viewport(tk.Canvas):
    STAR_COUNT = 70

    def __init__(self, master: tk.Misc, font_size: int = 26) -> None:
        super().__init__(master, bg=BG2, highlightthickness=0, bd=0, height=px(140))
        self._rng = random.Random(7)
        self.set_font_size(font_size)
        self.text = ""
        self.index = 0
        self.mode = "idle"          # idle | ready | run | pause | done
        self.message = ""
        self.sub_message = ""
        self.status = ""
        self.status_color = MUTED
        self.finger: tuple[str, str] | None = None
        self._err_until = 0.0
        self._err_text = ""
        self._err_shown = False
        self._stars: list[list] = []
        self.bind("<Configure>", lambda _e: self._rebuild())

    def set_font_size(self, size: int) -> None:
        self._font = theme.font(size, mono=True)
        self._font_b = theme.font(size, True, mono=True)
        f = tkfont.Font(font=self._font)
        self._cw = max(f.measure("m"), 1)
        self._lh = f.metrics("linespace")
        if self.winfo_width() > 10:
            self.redraw()

    def set_state(self, *, text: str | None = None, index: int | None = None,
                  mode: str | None = None, message: str | None = None,
                  sub_message: str | None = None, status: str | None = None,
                  status_color: str | None = None, finger=None) -> None:
        if text is not None:
            self.text = text
        if index is not None:
            self.index = index
        if mode is not None:
            self.mode = mode
        if message is not None:
            self.message = message
        if sub_message is not None:
            self.sub_message = sub_message
        if status is not None:
            self.status = status
        if status_color is not None:
            self.status_color = status_color
        if finger is not None:
            self.finger = finger or None
        self.redraw()

    def flash_error(self, pressed: str, expected: str, hint: str = "") -> None:
        self._err_until = time.monotonic() + 0.22
        exp = "пробел" if expected == " " else expected
        prs = "пробел" if pressed == " " else pressed
        self._err_text = f"▲ НАЖАТО «{prs}» — НУЖНО «{exp}»" + (f"  ·  {hint}" if hint else "")
        self._err_text_until = time.monotonic() + 1.1
        self._err_shown = True
        self.redraw()

    # -- звёзды --------------------------------------------------------
    def _rebuild(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        bands = 8
        for i in range(bands):
            t = abs(i - (bands - 1) / 2) / (bands / 2)
            col = blend(blend(BG2, CYAN, 0.035), BG, t * 0.9)
            self.create_rectangle(0, h * i / bands, w, h * (i + 1) / bands + 1,
                                  fill=col, outline="", tags="bg")
        for y in range(0, h, px(4)):
            self.create_line(0, y, w, y, fill=blend(BG2, CYAN, 0.025), tags="bg")
        self._stars = []
        layer_cols = {1: FAINT, 2: MUTED, 3: blend(TEXT, CYAN, 0.3)}
        for _ in range(self.STAR_COUNT):
            layer = self._rng.choice((1, 1, 1, 2, 2, 3))
            x, y = self._rng.uniform(0, w), self._rng.uniform(px(6), h - px(6))
            item = self.create_line(x, y, x + 1, y, fill=layer_cols[layer],
                                    width=2 if layer == 3 else 1, tags="star")
            self._stars.append([x, y, layer, item])
        self.redraw()

    def tick(self, warp: float, animate: bool) -> None:
        """Сдвинуть звёзды. warp — множитель скорости (зависит от темпа печати)."""
        now = time.monotonic()
        if self._err_shown and now > getattr(self, "_err_text_until", 0):
            self._err_shown = False
            self.redraw()
        elif self._err_until and now > self._err_until:
            self._err_until = 0.0
            self.redraw()
        if not animate or not self._stars:
            return
        w = self.winfo_width()
        base = px(0.35)
        for star in self._stars:
            x, y, layer, item = star
            dx = base * layer * warp
            x -= dx
            if x < -px(20):
                x = w + self._rng.uniform(0, px(30))
                y = self._rng.uniform(px(6), self.winfo_height() - px(6))
            star[0], star[1] = x, y
            tail = max(1.0, dx * (2.5 if warp > 1.6 else 1.0))
            self.coords(item, x, y, x + tail, y)

    def set_stars_visible(self, visible: bool) -> None:
        self.itemconfigure("star", state=tk.NORMAL if visible else tk.HIDDEN)

    # -- текст ---------------------------------------------------------
    def redraw(self) -> None:
        self.delete("txt")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        cw, lh = self._cw, self._lh
        cx, cy = w / 2, h / 2 + px(4)
        T = ("txt",)
        # рамка-иллюминатор
        c = px(14)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill="", outline=LINE_HI, tags=T)
        self.create_line(1 + c, 1, 1 + c + px(60), 1, fill=CYAN, width=2, tags=T)
        self.create_line(w - 2 - c, h - 2, w - 2 - c - px(60), h - 2, fill=CYAN, width=2, tags=T)
        self.create_text(px(18), px(12), text="◉ НАВИГАЦИОННЫЙ КАНАЛ", anchor="w",
                         fill=CYAN_DIM, font=theme.font(8, True), tags=T)
        if self.status:
            self.create_text(w - px(18), px(12), text=self.status, anchor="e",
                             fill=self.status_color, font=theme.font(9, True), tags=T)

        show_text = self.mode in ("ready", "run", "pause") and self.text
        if not show_text:
            self.create_text(cx, cy - px(8), text=self.message, fill=TEXT,
                             font=theme.font(15, True), tags=T)
            if self.sub_message:
                self.create_text(cx, cy + px(22), text=self.sub_message, fill=MUTED,
                                 font=theme.font(10), tags=T)
            return

        n_side = max(2, int((w / 2 - px(24)) / cw))
        i = self.index
        typed = self.text[max(0, i - n_side):i]
        cur = self.text[i] if i < len(self.text) else ""
        rest = self.text[i + 1:i + 1 + n_side]
        left_edge = cx - cw / 2
        right_edge = cx + cw / 2
        recent, older = typed[-10:], typed[:-10]
        if recent:
            self.create_text(left_edge, cy, text=recent, anchor="e", fill=CYAN_DIM,
                             font=self._font, tags=T)
        if older:
            self.create_text(left_edge - len(recent) * cw, cy, text=older, anchor="e",
                             fill=blend(CYAN_DIM, BG, 0.5), font=self._font, tags=T)
        near, far = rest[:14], rest[14:]
        if near:
            self.create_text(right_edge, cy, text=near, anchor="w", fill=TEXT,
                             font=self._font, tags=T)
        if far:
            self.create_text(right_edge + len(near) * cw, cy, text=far, anchor="w",
                             fill=blend(TEXT, BG, 0.45), font=self._font, tags=T)
        # прицел на текущем символе
        err = time.monotonic() < self._err_until
        col = RED if err else AMBER
        top, bot = cy - lh / 2 - px(5), cy + lh / 2 + px(5)
        self.create_rectangle(left_edge - px(3), top, right_edge + px(3), bot,
                              fill=RED_DIM if err else blend(AMBER, BG, 0.85),
                              outline=blend(col, BG, 0.4), width=px(5), tags=T)
        self.create_rectangle(left_edge - px(3), top, right_edge + px(3), bot,
                              outline=col, width=1, tags=T)
        tri = px(6)
        self.create_polygon(cx - tri, top - px(9), cx + tri, top - px(9), cx, top - px(2),
                            fill=col, outline="", tags=T)
        self.create_polygon(cx - tri, bot + px(9), cx + tri, bot + px(9), cx, bot + px(2),
                            fill=col, outline="", tags=T)
        if cur == " ":
            self.create_line(left_edge + px(3), cy + lh * 0.30, right_edge - px(3), cy + lh * 0.30,
                             fill=col, width=px(3), tags=T)
        elif cur:
            self.create_text(cx, cy, text=cur, fill="#FFFFFF" if not err else RED,
                             font=self._font_b, tags=T)
        if self.finger and self.mode != "pause":
            name, color = self.finger
            self.create_text(px(18), h - px(13), text=f"▸ {name}", anchor="w", fill=color,
                             font=theme.font(9, True), tags=T)
        if self._err_shown:
            self.create_text(cx, px(12), text=self._err_text, fill=RED,
                             font=theme.font(9, True), tags=T)
        elif self.mode == "ready":
            self.create_text(cx, px(12), text="НАЧНИТЕ ПЕЧАТАТЬ — ТАЙМЕР СТАРТУЕТ С ПЕРВОЙ КЛАВИШИ",
                             fill=AMBER, font=theme.font(9, True), tags=T)
        if self.mode == "pause":
            band = h * 0.62
            self.create_rectangle(px(4), cy - band / 2, w - px(4), cy + band / 2,
                                  fill=blend(BG, AMBER, 0.07), outline=AMBER_DIM, tags=T)
            self.create_text(cx, cy - px(10), text="❚❚  ПАУЗА", fill=AMBER,
                             font=theme.font(18, True), tags=T)
            self.create_text(cx, cy + px(18),
                             text=self.sub_message or "Esc или Пробел — продолжить полёт",
                             fill=TEXT, font=theme.font(10), tags=T)


# ---------------------------------------------------------------------------
# Клавиатура
# ---------------------------------------------------------------------------

class HudKeyboard(tk.Canvas):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         width=px(640), height=px(230))
        self.lang = "en"
        self.zones = True
        self.heat: dict[str, float] | None = None
        self.highlighted: str | None = None
        self._flash: dict[str, float] = {}
        self._geom: dict[str, tuple] = {}
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_lang(self, lang: str) -> None:
        if lang != self.lang:
            self.lang = lang
            self.redraw()

    def set_zones(self, value: bool) -> None:
        self.zones = value
        self.redraw()

    def set_heat(self, heat: dict[str, float] | None) -> None:
        self.heat = heat
        self.redraw()

    def highlight(self, kid: str | None) -> None:
        if kid == self.highlighted:
            return
        old, self.highlighted = self.highlighted, kid
        for k in (old, kid):
            if k:
                self._draw_key(k)

    def flash(self, kid: str | None) -> None:
        if kid and kid in self._geom:
            self._flash[kid] = time.monotonic() + 0.2
            self._draw_key(kid)

    def tick(self) -> None:
        if not self._flash:
            return
        now = time.monotonic()
        for k in [k for k, t in self._flash.items() if t < now]:
            del self._flash[k]
            self._draw_key(k)

    def _key_heat(self, kid: str) -> float | None:
        if self.heat is None:
            return None
        en, ru = layouts.KEY_LABELS[kid]
        rates = [self.heat.get(ch) for ch in (en.lower(), ru.lower()) if ch]
        rates = [r for r in rates if r is not None]
        if kid == "space":
            rates = [self.heat.get(" ")] if self.heat.get(" ") is not None else []
        return max(rates) if rates else None

    def redraw(self) -> None:
        self.delete("all")
        self._geom = {}
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 30:
            return
        pad = px(4)
        u = min((w - 2 * pad) / layouts.ROW_UNITS, (h - 2 * pad) / 5)
        total_w = u * layouts.ROW_UNITS
        x0 = (w - total_w) / 2
        y0 = (h - u * 5) / 2
        gap = max(2, u * 0.08)
        self._u = u
        for r, row in enumerate(layouts.ROWS):
            x = x0
            for kid, _en, _ru, units, finger in row:
                kw = units * u
                self._geom[kid] = (x + gap / 2, y0 + r * u + gap / 2,
                                   x + kw - gap / 2, y0 + (r + 1) * u - gap / 2, finger)
                x += kw
        for kid in self._geom:
            self._draw_key(kid)

    def _draw_key(self, kid: str) -> None:
        if kid not in self._geom:
            return
        self.delete(f"k_{kid}")
        x1, y1, x2, y2, finger = self._geom[kid]
        tag = ("key", f"k_{kid}")
        zone = layouts.FINGER_COLORS[finger]
        is_mod = finger == layouts.MOD
        heat = self._key_heat(kid)
        hl = kid == self.highlighted
        flashing = kid in self._flash
        c = (y2 - y1) * 0.18
        en, ru = layouts.KEY_LABELS[kid]
        main, second = (ru, en) if self.lang == "ru" else (en, ru)
        fg = TEXT
        if flashing:
            fill, outline, fg = RED_DIM, RED, RED
        elif hl:
            fill, outline, fg = blend(AMBER, BG, 0.1), AMBER, BG
        elif self.heat is not None:
            if heat is None:
                fill, outline = PANEL, LINE
                fg = FAINT if is_mod else MUTED
            else:
                fill = theme.heat_color(min(1.0, heat * 4))
                outline = blend(fill, TEXT, 0.3)
        elif self.zones and not is_mod:
            fill, outline = blend(PANEL, zone, 0.13), blend(zone, BG, 0.35)
        else:
            fill, outline = PANEL, LINE_HI if not is_mod else LINE
            if is_mod:
                fg = MUTED
        if hl and not flashing:
            g = px(4)
            self.create_polygon(chamfer(x1 - g, y1 - g, x2 + g, y2 + g, c + g), fill="",
                                outline=blend(AMBER, BG, 0.55), width=px(3), tags=tag)
        self.create_polygon(chamfer(x1, y1, x2, y2, c), fill=fill, outline=outline,
                            width=2 if (hl or flashing) else 1, tags=tag)
        kh = y2 - y1
        size = max(7, int(kh / theme.S * 0.30)) if len(main) <= 2 else max(6, int(kh / theme.S * 0.20))
        if main:
            self.create_text((x1 + x2) / 2 - (kh * 0.08 if second != main else 0),
                             (y1 + y2) / 2 - (kh * 0.06 if second != main else 0),
                             text=main, fill=fg, font=theme.font(size, True), tags=tag)
        if second and second != main and len(second) <= 2:
            self.create_text(x2 - kh * 0.14, y2 - kh * 0.16, text=second,
                             fill=BG if hl else blend(AMBER, TEXT, 0.15),
                             font=theme.font(max(7, int(size * 0.62)), True), tags=tag)
        if kid in layouts.HOME_BUMPS:
            cx = (x1 + x2) / 2
            self.create_line(cx - kh * 0.14, y2 - kh * 0.13, cx + kh * 0.14, y2 - kh * 0.13,
                             fill=fg, width=2, tags=tag)
        if heat is not None and not hl and heat > 0:
            self.create_text(x1 + kh * 0.10, y2 - kh * 0.16, text=f"{heat * 100:.0f}",
                             anchor="w", fill=TEXT, font=theme.font(max(6, int(size * 0.5))),
                             tags=tag)


# ---------------------------------------------------------------------------
# График истории
# ---------------------------------------------------------------------------

class LineChart(tk.Canvas):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0,
                         height=px(200), width=px(500))
        self.runs: list[dict] = []
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_runs(self, runs: list[dict]) -> None:
        self.runs = runs[-30:]
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or h < 60:
            return
        l, r, t, b = px(44), px(44), px(14), px(22)
        pw, ph = w - l - r, h - t - b
        for i in range(5):
            y = t + ph * i / 4
            self.create_line(l, y, l + pw, y, fill=LINE, dash=(2, 4))
        self.create_rectangle(l, t, l + pw, t + ph, outline=LINE_HI)
        if len(self.runs) < 1:
            self.create_text(w / 2, h / 2, text="Пока нет записей о полётах — пройдите первую миссию",
                             fill=MUTED, font=theme.font(11))
            return
        cpms = [x.get("cpm", 0) for x in self.runs]
        accs = [x.get("acc", 0) for x in self.runs]
        vmax = max(100, int(math.ceil(max(cpms) / 50.0)) * 50)
        amin = min(80, int(min(accs) // 5 * 5))
        for i in range(5):
            y = t + ph * i / 4
            self.create_text(l - px(6), y, text=str(int(vmax * (4 - i) / 4)), anchor="e",
                             fill=CYAN_DIM, font=theme.font(8))
            self.create_text(l + pw + px(6), y, text=f"{amin + (100 - amin) * (4 - i) / 4:.0f}%",
                             anchor="w", fill=AMBER_DIM, font=theme.font(8))
        n = len(self.runs)

        def xy(i, v, lo, hi):
            x = l + (pw * i / (n - 1) if n > 1 else pw / 2)
            y = t + ph * (1 - (v - lo) / max(1e-6, hi - lo))
            return x, y

        for series, lo, hi, col in ((accs, amin, 100, AMBER), (cpms, 0, vmax, CYAN)):
            pts = [xy(i, v, lo, hi) for i, v in enumerate(series)]
            if len(pts) > 1:
                flat = [c for p in pts for c in p]
                self.create_line(*flat, fill=blend(col, BG, 0.6), width=px(5))
                self.create_line(*flat, fill=col, width=2)
            for x, y in pts:
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=col, outline=col)
        x, y = xy(n - 1, cpms[-1], 0, vmax)
        self.create_text(x - px(6), y - px(10), text=f"{cpms[-1]:.0f}", anchor="e",
                         fill=CYAN, font=theme.font(9, True))
        self.create_text(l, h - px(10), text="● скорость, зн/мин", anchor="w", fill=CYAN,
                         font=theme.font(8, True))
        self.create_text(l + pw, h - px(10), text="точность, % ●", anchor="e", fill=AMBER,
                         font=theme.font(8, True))


# ---------------------------------------------------------------------------
# Переводчик UPLINK
# ---------------------------------------------------------------------------

class TranslatorPanel(tk.Canvas):
    """Панель UPLINK с внутренним окном слова под прицелом.

    Схема сверху вниз:
    1. заголовок + статус;
    2. исходное предложение (приглушённо);
    3. **внутреннее окно** чуть выше середины — набираемое слово и его перевод;
    4. **под ним** — строка перевода всего предложения (крупный шрифт).
    """

    def __init__(self, master: tk.Misc) -> None:
        # Выше прежнего UPLINK: место под окно слова и под крупный перевод предложения.
        super().__init__(master, bg=_bg_of(master), highlightthickness=0, bd=0, height=px(158))
        self.direction = "EN → RU"
        self.source = ""
        self.translation = ""
        self.word = ""            # слово под прицелом (оригинал)
        self.word_tr = ""         # его перевод
        self.word_cursor = -1     # индекс буквы внутри слова (−1 = нет подсветки)
        self.status = ""
        self.status_color = MUTED
        self._f_tr = theme.font(18)             # перевод всего предложения — крупно
        self._f_src = theme.font(8)
        self._f_word = theme.font(22, True)     # оригинал слова слева (EN)
        self._f_word_tr = theme.font(26, True)  # перевод слова справа
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, *, direction: str | None = None, source: str | None = None,
            translation: str | None = None, word: str | None = None,
            word_tr: str | None = None, word_cursor: int | None = None,
            status: str | None = None, status_color: str | None = None) -> None:
        changed = False
        for name, val in (("direction", direction), ("source", source),
                          ("translation", translation), ("word", word),
                          ("word_tr", word_tr), ("word_cursor", word_cursor),
                          ("status", status), ("status_color", status_color)):
            if val is not None and getattr(self, name) != val:
                setattr(self, name, val)
                changed = True
        if changed:
            self.redraw()

    @staticmethod
    def _fit(text: str, font: tuple, width: float, lines: int) -> str:
        f = tkfont.Font(font=font)
        avg = max(1, f.measure("абвгдеёжзиклмнопрстabcdefghij") / 29)
        limit = int(width / avg * lines * 0.97)
        return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60:
            return
        c = px(10)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill=PANEL, outline=LINE_HI)
        self.create_line(1, 1 + c, 1, h - 2, fill=AMBER, width=3)

        # 1) Заголовок + статус
        self.create_text(px(14), px(12), text=f"UPLINK // ПЕРЕВОДЧИК   {self.direction}",
                         anchor="w", fill=AMBER, font=theme.font(8, True))
        if self.status:
            self.create_text(w - px(14), px(12), text=self.status, anchor="e",
                             fill=self.status_color, font=theme.font(8, True))

        margin = px(14)
        full_w = w - margin * 2
        center_x = w / 2  # ось прицела иллюминатора — по центру панели

        # 2) Исходное предложение — узкая полоска под заголовком (окошко слова выше)
        src = self._fit(self.source, self._f_src, full_w * 0.72, 1)
        self.create_text(margin, px(22), text=src or "—", anchor="w",
                         fill=MUTED, font=self._f_src)

        # 3) Внутреннее окошко под прицелом: слово и перевод целиком, без обрезки
        word_src = (self.word or "—").strip() or "—"
        word_dst = (self.word_tr or "…").strip() or "…"
        f_word = tkfont.Font(font=self._f_word)
        f_arrow = tkfont.Font(font=theme.font(14, True))
        f_wtr = tkfont.Font(font=self._f_word_tr)
        pad = px(16)
        gap = px(10)
        arrow_w = f_arrow.measure("→")
        need_w = (pad + f_word.measure(word_src) + gap + arrow_w + gap
                  + f_wtr.measure(word_dst) + pad)
        # Расширяем до нужной ширины (почти на всю панель, если слово длинное)
        box_w = min(full_w, max(px(200), need_w))
        box_h = px(56)
        box_x0 = center_x - box_w / 2
        box_x1 = center_x + box_w / 2
        box_top = px(26)   # ещё выше — ближе к прицелу
        box_bot = box_top + box_h

        # Если даже на полной ширине не влезает — чуть уменьшаем шрифт перевода слова
        word_tr_font = self._f_word_tr
        show_dst = word_dst
        if need_w > full_w:
            for size in (24, 22, 20, 18, 16):
                trial = theme.font(size, True)
                ft = tkfont.Font(font=trial)
                trial_need = (pad + f_word.measure(word_src) + gap + arrow_w + gap
                              + ft.measure(word_dst) + pad)
                if trial_need <= full_w:
                    word_tr_font = trial
                    f_wtr = ft
                    box_w = full_w
                    box_x0 = margin
                    box_x1 = margin + full_w
                    break
            else:
                word_tr_font = theme.font(16, True)
                f_wtr = tkfont.Font(font=word_tr_font)
                box_w = full_w
                box_x0 = margin
                box_x1 = margin + full_w
                avail = box_w - pad * 2 - f_word.measure(word_src) - gap * 2 - arrow_w
                show_dst = self._fit(word_dst, word_tr_font, max(avail, px(40)), 1)

        self.create_rectangle(
            box_x0, box_top, box_x1, box_bot,
            fill=blend(PANEL, AMBER, 0.10), outline=AMBER, width=2,
        )
        tick = px(6)
        self.create_line(center_x, box_top - tick, center_x, box_top, fill=AMBER, width=2)
        self.create_line(center_x, box_bot, center_x, box_bot + tick, fill=AMBER, width=2)

        mid_y = (box_top + box_bot) / 2
        # Раскладка: слово (по буквам, текущая — красная) | → | перевод
        left_x = box_x0 + pad
        right_x = box_x1 - pad
        x = left_x
        cursor = self.word_cursor
        for i, ch in enumerate(word_src):
            color = RED if i == cursor else CYAN
            # уже набранные буквы слова — чуть приглушённые
            if 0 <= cursor and i < cursor:
                color = blend(CYAN, PANEL, 0.45)
            self.create_text(x, mid_y, text=ch, anchor="w",
                             fill=color, font=self._f_word)
            x += f_word.measure(ch)
        self.create_text(center_x, mid_y, text="→", anchor="center",
                         fill=AMBER, font=theme.font(14, True))
        self.create_text(right_x, mid_y, text=show_dst, anchor="e",
                         fill=TEXT, font=word_tr_font)

        # 4) Под окошком — крупный перевод всего предложения
        sent_y = box_bot + px(14)
        sent = self._fit(self.translation, self._f_tr, full_w, 2)
        self.create_text(margin, sent_y, text=sent or "—", anchor="nw",
                         fill=TEXT, font=self._f_tr, width=full_w)
