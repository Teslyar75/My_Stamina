"""Мелкие виджеты отсека «СКОРОЧТЕНИЕ» поверх компонентов Star Typing (только theme/hud)."""
from __future__ import annotations

from stamina.i18n import t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel  # noqa: F401  (реэкспорт)
from stamina.theme import (AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL,
                           RED, TEXT, blend, px)


def L(master, text="", *, fg=TEXT, size=10, bold=False, mono=False, bg=None, **kw) -> tk.Label:
    if bg is None:
        try:
            bg = master.cget("bg")
        except tk.TclError:
            bg = PANEL
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold, mono), **kw)


def entry(master, width=30, size=11, mono=False) -> tk.Entry:
    return tk.Entry(master, width=width, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat",
                    font=theme.font(size, False, mono), highlightthickness=1,
                    highlightbackground=LINE_HI, highlightcolor=CYAN)


class ScrollFrame(tk.Frame):
    """Вертикальная прокрутка колесом мыши; содержимое — в .inner."""

    def __init__(self, master, bg=BG, **kw) -> None:
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, width=px(12))
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))

    def _wheel(self, e) -> None:
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120) * 3, "units")

    def clear(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)


class Toggle(HudButton):
    """Переключатель ВКЛ/ВЫКЛ в стиле HudButton."""

    def __init__(self, master, value: bool, command=None, width=86) -> None:
        self.value = bool(value)
        self._cb = command
        super().__init__(master, t("ВКЛ") if value else t("ВЫКЛ"), self._flip, height=26, font_size=8,
                         width=width, color=GREEN if value else MUTED, active=value)

    def _flip(self) -> None:
        self.set(not self.value)
        if self._cb:
            self._cb(self.value)

    def set(self, value: bool) -> None:
        self.value = bool(value)
        self.set_text(t("ВКЛ") if self.value else t("ВЫКЛ"))
        self.set_color(GREEN if self.value else MUTED)
        self.set_active(self.value)


class Choice(tk.Frame):
    """Вариант ответа с переносом строк."""

    def __init__(self, master, num: int, text: str, command, wrap=520, size=12) -> None:
        super().__init__(master, bg=LINE_HI, padx=1, pady=1, cursor="hand2")
        self.command = command
        self.state = "idle"
        self.inner = tk.Frame(self, bg=PANEL)
        self.inner.pack(fill=tk.BOTH, expand=True)
        self.num = tk.Label(self.inner, text=str(num), bg=PANEL, fg=AMBER,
                            font=theme.font(11, True, mono=True), width=2)
        self.num.pack(side=tk.LEFT, padx=(px(8), px(4)), pady=px(6))
        self.lbl = tk.Label(self.inner, text=text, bg=PANEL, fg=TEXT, font=theme.font(size),
                            justify="left", anchor="w", wraplength=px(wrap))
        self.lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, px(10)), pady=px(6))
        for w in (self, self.inner, self.num, self.lbl):
            w.bind("<Button-1>", lambda _e: self.command() if self.state == "idle" and self.command else None)

    def mark(self, kind: str) -> None:
        self.state = kind
        col = {"ok": GREEN, "bad": RED, "dim": FAINT}[kind]
        self.configure(bg=col)
        bg = blend(col, BG, 0.80) if kind != "dim" else PANEL
        for w in (self.inner, self.num, self.lbl):
            w.configure(bg=bg)


class WpmChart(tk.Canvas):
    """График скорости по сессиям: линия скорости (циан), эффективной (зелёный), цель (янтарь)."""

    def __init__(self, master, height=150) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=px(height))
        self.sessions: list[dict] = []
        self.goal = 600
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, sessions: list[dict], goal: int) -> None:
        self.sessions, self.goal = sessions, goal
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        pad = px(10)
        vals = [s["avg_wpm"] for s in self.sessions]
        vmax = max([self.goal * 1.1] + [v * 1.1 for v in vals] + [100])
        y = lambda v: h - pad - (h - 2 * pad) * v / vmax  # noqa: E731
        self.create_line(pad, h - pad, w - pad, h - pad, fill=LINE)
        gy = y(self.goal)
        self.create_line(pad, gy, w - pad, gy, fill=blend(AMBER, BG, 0.4), dash=(4, 4))
        self.create_text(w - pad, gy - px(7), text=t("ЦЕЛЬ {0}").format(self.goal), anchor="e", fill=AMBER,
                         font=theme.font(7, True))
        if not vals:
            self.create_text(w / 2, h / 2, text=t("ещё нет сессий чтения"), fill=MUTED, font=theme.font(9))
            return
        n = len(vals)
        xs = [pad + (w - 2 * pad) * (i / max(1, n - 1) if n > 1 else 0.5) for i in range(n)]
        for key, col in (("eff_wpm", GREEN), ("avg_wpm", CYAN)):
            pts = [(xs[i], y(s[key])) for i, s in enumerate(self.sessions) if s.get(key)]
            if len(pts) > 1:
                self.create_line(*[c for p in pts for c in p], fill=col, width=2)
            for x0, y0 in pts:
                self.create_oval(x0 - 3, y0 - 3, x0 + 3, y0 + 3, fill=col, outline=col)
