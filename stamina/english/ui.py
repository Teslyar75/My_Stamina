"""Общие виджеты вкладки «Английский» поверх компонентов Star Typing (stamina.hud, stamina.theme).
Новых цветов и шрифтов нет: всё из theme.py (DESIGN.md)."""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel  # noqa: F401  (реэкспорт для страниц)
from stamina.theme import (AMBER, BG, BG2, CYAN, CYAN_DIM, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL,
                           PANEL_HI, PURPLE, RED, TEXT, blend, chamfer, px)

DIFF_COLOR = {"easy": GREEN, "medium": CYAN, "tricky": AMBER}


def L(master, text="", *, fg=TEXT, size=10, bold=False, mono=False, bg=None, **kw) -> tk.Label:
    if bg is None:
        try:
            bg = master.cget("bg")
        except tk.TclError:
            bg = PANEL
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold, mono), **kw)


def chip(master, text, color=MUTED, bg=None, size=8) -> tk.Label:
    bg = bg or master.cget("bg")
    return tk.Label(master, text=f" {text} ", fg=color, bg=bg, font=theme.font(size, True),
                    highlightthickness=1, highlightbackground=blend(color, BG, 0.35), bd=0, padx=px(4))


def hline(master, color=LINE) -> tk.Frame:
    f = tk.Frame(master, bg=color, height=1)
    f.pack(fill=tk.X, pady=px(4))
    return f


def entry(master, width=30, size=11, mono=False) -> tk.Entry:
    return tk.Entry(master, width=width, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat",
                    font=theme.font(size, False, mono), highlightthickness=1, highlightbackground=LINE_HI,
                    highlightcolor=CYAN, disabledbackground=BG2)


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

    def top(self) -> None:
        self.canvas.yview_moveto(0)


class Choice(tk.Frame):
    """Вариант ответа с переносом строк (у HudButton текст в одну строку)."""

    def __init__(self, master, num: int, text: str, command, wrap=560, size=12) -> None:
        super().__init__(master, bg=LINE_HI, padx=1, pady=1, cursor="hand2")
        self.command = command
        self.state = "idle"
        self.inner = tk.Frame(self, bg=PANEL)
        self.inner.pack(fill=tk.BOTH, expand=True)
        self.num = tk.Label(self.inner, text=str(num), bg=PANEL, fg=AMBER, font=theme.font(11, True, mono=True),
                            width=2)
        self.num.pack(side=tk.LEFT, padx=(px(8), px(4)), pady=px(8))
        self.lbl = tk.Label(self.inner, text=text, bg=PANEL, fg=TEXT, font=theme.font(size), justify="left",
                            anchor="w", wraplength=px(wrap))
        self.lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, px(10)), pady=px(8))
        for w in (self, self.inner, self.num, self.lbl):
            w.bind("<Button-1>", lambda _e: self._click())
            w.bind("<Enter>", lambda _e: self._hover(True))
            w.bind("<Leave>", lambda _e: self._hover(False))

    def _click(self) -> None:
        if self.state == "idle" and self.command:
            self.command()

    def _hover(self, on: bool) -> None:
        if self.state != "idle":
            return
        self.configure(bg=CYAN if on else LINE_HI)
        self._paint(blend(CYAN, BG, 0.88) if on else PANEL)

    def _paint(self, bg) -> None:
        for w in (self.inner, self.num, self.lbl):
            w.configure(bg=bg)

    def mark(self, kind: str) -> None:
        """kind: ok | bad | dim."""
        self.state = kind
        col = {"ok": GREEN, "bad": RED, "dim": FAINT}[kind]
        self.configure(bg=col)
        self._paint(blend(col, BG, 0.80) if kind != "dim" else PANEL)
        if kind == "dim":
            self.lbl.configure(fg=MUTED)


class Tile(tk.Canvas):
    """Плитка слова на звёздной карте: #rank, слово, часть речи, сложность, ⟳, ✓ ЗНАЮ, ⊞ В ОТСЕК."""

    W, H = 186, 112

    def __init__(self, master, ctx, word: dict) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, width=px(self.W), height=px(self.H),
                         cursor="hand2")
        self.ctx, self.w = ctx, word
        self.flipped = False
        self.hover = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._h(True))
        self.bind("<Leave>", lambda _e: self._h(False))

    def _h(self, v) -> None:
        self.hover = v
        self.redraw()

    def redraw(self) -> None:
        from .vocab import DIFF_RU, POS_SHORT
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        p = self.ctx.progress
        slug = self.w["slug"]
        known = p.is_known(slug)
        col = GREEN if known else (CYAN if self.hover else LINE_HI)
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(9)), fill=PANEL_HI if self.hover else PANEL,
                            outline=col, width=2 if known else 1)
        self.create_text(px(9), px(8), text=f"#{self.w['rank']}", anchor="nw", fill=MUTED,
                         font=theme.font(8, True, mono=True))
        self.create_text(w - px(10), px(7), text="⟳", anchor="ne", fill=CYAN, font=theme.font(11, True),
                         tags="flip")
        if self.flipped:
            d = self.w.get("definition", "")
            tr = p.tr(slug)
            txt = (tr + " — " if tr else "") + d
            self.create_text(w / 2, px(52), text=txt, width=w - px(18), fill=TEXT, font=theme.font(8),
                             justify="center", tags="open")
        else:
            self.create_text(w / 2, px(38), text=self.w["word"], fill=TEXT, font=theme.font(14, True),
                             tags="open")
            pos = POS_SHORT.get(self.w["pos"], (self.w["pos"] or "?").upper())
            diff = self.w.get("difficulty", "medium")
            dcol = DIFF_COLOR.get(diff, CYAN)
            t1 = self.create_text(w / 2 - px(4), px(62), text=pos, anchor="e", fill=MUTED, font=theme.font(7, True))
            t2 = self.create_text(w / 2 + px(4), px(62), text=DIFF_RU.get(diff, diff), anchor="w", fill=dcol,
                                  font=theme.font(7, True))
            for t, c in ((t1, MUTED), (t2, dcol)):
                x1, y1, x2, y2 = self.bbox(t)
                self.create_rectangle(x1 - px(4), y1 - px(1), x2 + px(4), y2 + px(1), outline=blend(c, BG, 0.4))
        by = h - px(28)
        self.create_line(px(8), by - px(4), w - px(8), by - px(4), fill=LINE)
        kc = GREEN if known else blend(MUTED, BG, 0.1)
        self.create_text(w * 0.28, by + px(10), text=("✓ ЗНАЮ" if known else "✓ знаю"), fill=kc,
                         font=theme.font(8, True), tags="known")
        inl = bool(p.lists_of(slug))
        self.create_text(w * 0.72, by + px(10), text="⊞ В ОТСЕКЕ" if inl else "⊞ В отсек",
                         fill=AMBER if inl else blend(MUTED, BG, 0.1), font=theme.font(8, True), tags="list")
        self.tag_bind("flip", "<Button-1>", lambda _e: self._flip())
        self.tag_bind("known", "<Button-1>", lambda _e: self._known())
        self.tag_bind("list", "<Button-1>", lambda e: self.ctx.list_menu(self, self.w["slug"], e, self.redraw))
        self.bind("<Button-1>", self._click)

    def _click(self, e) -> None:
        items = self.find_overlapping(e.x, e.y, e.x, e.y)
        tags = {t for i in items for t in self.gettags(i)}
        if tags & {"flip", "known", "list"}:
            return
        self.ctx.open_word(self.w["slug"])

    def _flip(self) -> None:
        self.flipped = not self.flipped
        self.redraw()

    def _known(self) -> None:
        p = self.ctx.progress
        p.set_known(self.w["slug"], not p.is_known(self.w["slug"]))
        self.redraw()
        self.ctx.changed()


class Bar(tk.Canvas):
    """Тонкая полоса прогресса (как «ПРОГРЕСС МАРШРУТА» в MissionStrip)."""

    def __init__(self, master, color=CYAN, height=8, width=200) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=px(height),
                         width=px(width))
        self.color, self.frac = color, 0.0
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, frac: float) -> None:
        self.frac = max(0.0, min(1.0, frac))
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, w - 1, h - 1, fill=BG2, outline=LINE)
        if self.frac > 0:
            self.create_rectangle(1, 1, max(2, (w - 2) * self.frac), h - 2, fill=self.color, outline="")


class Strip(tk.Canvas):
    """Полоса миссии: янтарная метка, заголовок, подзаголовок, прогресс справа (как bridge.MissionStrip)."""

    def __init__(self, master) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, height=px(52))
        self.title = self.sub = self.ptext = ""
        self.prog: float | None = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, title="", sub="", prog=None, ptext="") -> None:
        self.title, self.sub, self.prog, self.ptext = title, sub, prog, ptext
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        self.create_rectangle(px(2), px(6), px(7), px(46), fill=AMBER, outline="")
        self.create_text(px(16), px(16), text=self.title, anchor="w", fill=TEXT, font=theme.font(14, True))
        self.create_text(px(16), px(38), text=self.sub, anchor="w", fill=MUTED, font=theme.font(8))
        if self.prog is not None:
            x1, x2 = w - px(320), w - px(6)
            self.create_text(x1, px(14), text="ПРОГРЕСС МАРШРУТА", anchor="w", fill=MUTED, font=theme.font(8, True))
            self.create_text(x2, px(14), text=self.ptext, anchor="e", fill=CYAN, font=theme.font(9, True, mono=True))
            self.create_rectangle(x1, px(26), x2, px(34), fill=BG2, outline=LINE)
            if self.prog > 0:
                self.create_rectangle(x1 + 1, px(27), x1 + 1 + (x2 - x1 - 2) * min(1, self.prog), px(33),
                                      fill=CYAN, outline="")


class Segments(tk.Canvas):
    """Ряд сегментов с явными флагами (серия дней): заполненный / пустой / сегодня."""

    def __init__(self, master, title="", height=40) -> None:
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, height=px(height), width=px(200))
        self.title, self.flags, self.text = title, [], ""
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, flags: list[bool], text: str) -> None:
        self.flags, self.text = flags, text
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or not self.flags:
            return
        self.create_text(px(4), px(2), text=self.title, anchor="nw", fill=blend(CYAN, TEXT, 0.3),
                         font=theme.font(9, True))
        self.create_text(w - px(4), px(2), text=self.text, anchor="ne", fill=TEXT, font=theme.font(10, True, mono=True))
        n, gap = len(self.flags), px(3)
        sw = (w - px(8) - gap * (n - 1)) / n
        y1, y2 = h * 0.52, h - px(4)
        for i, f in enumerate(self.flags):
            x1 = px(4) + i * (sw + gap)
            last = i == n - 1
            if f:
                self.create_rectangle(x1, y1, x1 + sw, y2, fill=GREEN, outline=GREEN)
            elif last:
                self.create_rectangle(x1, y1, x1 + sw, y2, fill=blend(AMBER, BG, 0.5), outline=AMBER)
            else:
                self.create_rectangle(x1, y1, x1 + sw, y2, fill=BG2, outline=LINE)


TIPS = [
    "Повторяй слово вслух 3 раза: мозг запоминает звук вместе с написанием.",
    "Придумай смешную историю или образ для трудного слова — так оно держится дольше.",
    "Лучше 15 минут каждый день, чем 2 часа раз в неделю: серия дней работает.",
    "Учись словами в предложениях, а не по одному: контекст подсказывает смысл.",
    "Ошибки — нормально: проверка систем вернёт трудные слова в нужный момент.",
    "Слушай голос и повторяй с той же интонацией — это тренирует произношение.",
    "Свяжи новое слово с уже знакомым: lead → leader → leadership.",
    "Отмечай «Знаю» честно — иначе слово не попадёт в повторение.",
    "Говори в микрофон спокойно и чётко: распознавание любит паузы между фразами.",
    "Держи под рукой отсек «Избранное» для слов, которые встретил в жизни.",
]


class MatchReadout(tk.Canvas):
    """Итог проверки произношения в стиле HUD: крупное «СОВПАДЕНИЕ: 86%», шкала из 20 сегментов
    (порог 60% и 85% отмечены), вердикт, сколько слов засчитано и какие пропущены.
    Цвета — только из theme.py: ≥85 GREEN, 60–84 AMBER, <60 RED (как RingGauge Star Typing)."""

    SEG = 20

    def __init__(self, master, height=86) -> None:
        bg = master.cget("bg")
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, height=px(height))
        self.data = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def clear(self) -> None:
        self.data = None
        self.redraw()

    def set(self, score: int, marks=None, heard: str = "", target_missed: bool = False, self_rated=False) -> None:
        self.data = (int(score), marks or [], heard, target_missed, self_rated)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if not self.data or w < 60:
            return
        score, marks, heard, tmiss, selfr = self.data
        col = GREEN if score >= 85 else AMBER if score >= 60 else RED
        verdict = "ОТЛИЧНО" if score >= 85 else "ХОРОШО" if score >= 60 else "ЕЩЁ РАЗ"
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(10)), fill=blend(col, PANEL, 0.88), outline=col)
        self.create_rectangle(px(2), px(8), px(6), h - px(8), fill=col, outline="")
        label = "САМООЦЕНКА" if selfr else "СОВПАДЕНИЕ"
        self.create_text(px(16), px(22), text=f"{label}:", anchor="w", fill=MUTED, font=theme.font(10, True))
        self.create_text(px(16) + px(118), px(22), text=f"{score}%", anchor="w", fill=col,
                         font=theme.font(24, True, mono=True))
        self.create_text(w - px(12), px(22), text=verdict, anchor="e", fill=col, font=theme.font(14, True))
        # сегментная шкала
        x1, x2, y1, y2 = px(16), w - px(12), px(42), px(52)
        sw = (x2 - x1) / self.SEG
        lit = round(self.SEG * score / 100)
        for i in range(self.SEG):
            self.create_rectangle(x1 + i * sw + 1, y1, x1 + (i + 1) * sw - 2, y2,
                                  fill=col if i < lit else BG2, outline="" if i < lit else LINE)
        for thr in (60, 85):
            x = x1 + (x2 - x1) * thr / 100
            self.create_line(x, y1 - px(3), x, y2 + px(3), fill=TEXT)
        if marks:
            ok = sum(1 for _t, m in marks if m)
            miss = [t for t, m in marks if not m]
            line = f"слов засчитано {ok} / {len(marks)}"
            if miss:
                line += " · пропущено: " + ", ".join(miss[:8]) + ("…" if len(miss) > 8 else "")
            if tmiss:
                line += " · ключевое слово не распознано (максимум 59%)"
        elif selfr:
            line = "распознавание недоступно — оценка по кнопке"
        else:
            line = ""
        if heard:
            line = (line + "   ·   " if line else "") + f"услышано: «{heard}»"
        self.create_text(px(16), px(70), text=line, anchor="w", fill=MUTED, font=theme.font(9), width=w - px(28))


def target_missed(marks, target: str) -> bool:
    """True, если изучаемое слово есть в образце, но не засчитано."""
    from .textutil import word_forms
    forms = word_forms(target)
    return any(t in forms for t, _m in marks) and not any(m and t in forms for t, m in marks)
