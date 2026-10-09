"""ТРЕНАЖЁРЫ ОБЗОРА: таблицы Шульте и Горбова, пирамида, вспышка (тахистоскоп)."""
from __future__ import annotations

import random
import time
import tkinter as tk

from stamina import theme
from stamina.theme import (AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL, RED,
                           TEXT, blend, px)

from .ui import HudButton, HudPanel, L, entry

CATALOG = [
    # code, title, description, ready
    ("R-HYP", "Гипердрайв", "Чтение по слову (RSVP), красная буква", True),
    ("E-SHL", "Таблица Шульте", "Числа или буквы по порядку, 3×3…7×7", True),
    ("E-GRB", "Таблица Горбова", "Чёрные ↑ и красные ↓ поочерёдно", True),
    ("E-PYR", "Пирамида", "Расширение поля зрения по клину", True),
    ("E-TAC", "Вспышка", "Тахистоскоп: слова на 50–300 мс", True),
    ("E-FND", "Поиск слов", "Найди заданные слова в тексте", False),
    ("E-GAP", "Пропущенные буквы", "Прочти слова с пропусками", False),
    ("E-EYE", "Глазодвигатель", "Точки-мишени, саккады", False),
    ("E-PCR", "Указка", "Ведущая строка без возвратов", False),
]

RU_ABC = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ"
EN_ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def fmt_s(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:04.1f}"


def schulte_norm(n: int) -> tuple[float, float, float]:
    """Пороги ★★★/★★/★ в секундах для N×N (база 5×5: 35/50/70)."""
    k = (n * n) / 25
    return 35 * k, 50 * k, 70 * k


def stars_for(value: float, thresholds: tuple[float, float, float], lower_is_better=True) -> int:
    a, b, c = thresholds
    if lower_is_better:
        return 3 if value <= a else 2 if value <= b else 1 if value <= c else 0
    return 3 if value >= a else 2 if value >= b else 1 if value >= c else 0


def gorbov_sequence(n: int) -> list[tuple[str, int]]:
    """Порядок для таблицы Горбова: чёрное 1, красное max, чёрное 2, красное max-1…"""
    cells = n * n
    black = (cells + 1) // 2
    red = cells - black
    seq = []
    for i in range(black):
        seq.append(("b", i + 1))
        if i < red:
            seq.append(("r", red - i))
    return seq


class ExerciseBase(tk.Frame):
    code = ""
    title = ""

    def __init__(self, master, ctx, on_exit) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.on_exit = on_exit
        self._job = None
        strip = tk.Frame(self, bg=BG)
        strip.pack(fill=tk.X, padx=px(14), pady=(px(4), px(8)))
        tk.Frame(strip, bg=AMBER, width=px(5)).pack(side=tk.LEFT, fill=tk.Y, padx=(0, px(10)))
        box = tk.Frame(strip, bg=BG)
        box.pack(side=tk.LEFT)
        self.h1 = L(box, "", fg=TEXT, size=14, bold=True, bg=BG)
        self.h1.pack(anchor="w")
        self.h2 = L(box, "", fg=MUTED, size=8, bg=BG)
        self.h2.pack(anchor="w")
        HudButton(strip, "← ТРЕНАЖЁРЫ  ESC", self.exit, height=30, font_size=9).pack(side=tk.RIGHT)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))

    def exit(self) -> None:
        self.stop()
        self.on_exit()

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def on_key(self, e) -> None:
        if e.keysym == "Escape":
            self.exit()

    def result_banner(self, parent, text: str, color=GREEN) -> None:
        L(parent, text, fg=color, size=12, bold=True).pack(pady=px(6))


# ---------------------------------------------------------------------------
class SchulteEx(ExerciseBase):
    """Таблица Шульте (классика) и Горбова (gorbov=True)."""

    def __init__(self, master, ctx, on_exit, gorbov: bool = False) -> None:
        super().__init__(master, ctx, on_exit)
        self.gorbov = gorbov
        self.code = "E-GRB" if gorbov else "E-SHL"
        st = ctx.sstore.settings
        self.n = int(st.get("grb_n" if gorbov else "shl_n", 5))
        self.symbols = st.get("shl_sym", "num")
        self.fade = True
        self.body.grid_columnconfigure(1, weight=1)
        self.body.grid_rowconfigure(0, weight=1)
        left = tk.Frame(self.body, bg=BG, width=px(250))
        left.grid(row=0, column=0, sticky="ns")
        left.grid_propagate(False)
        tp = HudPanel(left, "НАЙДИ", accent=AMBER)
        tp.pack(fill=tk.X)
        tp.configure(height=px(190))
        tp.pack_propagate(False)
        self.lbl_target = L(tp.body, "", fg=AMBER, size=40, bold=True, mono=True)
        self.lbl_target.pack()
        self.lbl_next = L(tp.body, "", fg=MUTED, size=8, bold=True)
        self.lbl_next.pack()
        self.lbl_found = L(tp.body, "", fg=AMBER, size=9, bold=True, mono=True)
        self.lbl_found.pack(pady=(px(8), 0))
        mp = HudPanel(left, "РЕЖИМ")
        mp.pack(fill=tk.BOTH, expand=True, pady=(px(10), 0))
        L(mp.body, "РАЗМЕР", fg=MUTED, size=8, bold=True).pack(anchor="w")
        r = tk.Frame(mp.body, bg=PANEL)
        r.pack(anchor="w", pady=px(3))
        self.size_btns = {}
        for n in ((5, 7) if gorbov else (3, 4, 5, 6, 7)):
            b = HudButton(r, f"{n}×{n}", lambda n=n: self.set_size(n), height=26, font_size=8, width=42)
            b.pack(side=tk.LEFT, padx=1)
            self.size_btns[n] = b
        if not gorbov:
            L(mp.body, "СИМВОЛЫ", fg=MUTED, size=8, bold=True).pack(anchor="w", pady=(px(8), 0))
            r = tk.Frame(mp.body, bg=PANEL)
            r.pack(anchor="w", pady=px(3))
            self.sym_btns = {}
            for key, t in (("num", "1–N"), ("ru", "А–Я"), ("en", "A–Z")):
                b = HudButton(r, t, lambda k=key: self.set_symbols(k), height=26, font_size=8, width=60)
                b.pack(side=tk.LEFT, padx=1)
                self.sym_btns[key] = b
        L(mp.body, ("Чередуйте: чёрное по возрастанию,\nкрасное по убыванию (ч1 → к12 → ч2 → к11…)."
                    if gorbov else "Смотрите в центр (красная точка).\nИщите периферийным зрением, щёлкайте\n"
                    "мышью. Ошибка — +2 с."), fg=MUTED, size=8, justify="left").pack(anchor="w", pady=(px(10), 0))
        self.board = tk.Canvas(self.body, bg=BG2, highlightthickness=0, bd=0)
        self.board.grid(row=0, column=1, sticky="nsew", padx=px(12))
        self.board.bind("<Configure>", lambda _e: self.draw())
        self.board.bind("<Button-1>", self.click)
        right = tk.Frame(self.body, bg=BG, width=px(250))
        right.grid(row=0, column=2, sticky="ns")
        right.grid_propagate(False)
        tm = HudPanel(right, "ТАЙМЕР")
        tm.pack(fill=tk.X)
        tm.configure(height=px(130))
        tm.pack_propagate(False)
        self.lbl_timer = L(tm.body, "00:00.0", fg=CYAN, size=28, bold=True, mono=True)
        self.lbl_timer.pack()
        self.lbl_rec = L(tm.body, "", fg=GREEN, size=8, bold=True)
        self.lbl_rec.pack()
        te = HudPanel(right, "ТЕЛЕМЕТРИЯ", accent=LINE_HI)
        te.pack(fill=tk.BOTH, expand=True, pady=(px(10), 0))
        self.lbl_tele = L(te.body, "", fg=TEXT, size=10, mono=True, justify="left", anchor="nw")
        self.lbl_tele.pack(fill=tk.BOTH, expand=True)
        acts = tk.Frame(right, bg=BG)
        acts.pack(fill=tk.X, pady=(px(8), 0))
        HudButton(acts, "⟲ ЗАНОВО  R", self.new_game, color=AMBER, height=36).pack(fill=tk.X)
        self.new_game()

    # -- игра ---------------------------------------------------------------
    def set_size(self, n: int) -> None:
        self.n = n
        self.ctx.sstore.settings["grb_n" if self.gorbov else "shl_n"] = n
        self.ctx.sstore.save()
        self.new_game()

    def set_symbols(self, key: str) -> None:
        self.symbols = key
        self.ctx.sstore.settings["shl_sym"] = key
        self.ctx.sstore.save()
        self.new_game()

    def _labels(self) -> list[tuple[str, str]]:
        """(подпись, цвет) в порядке поиска."""
        cells = self.n * self.n
        if self.gorbov:
            return [(str(v), RED if c == "r" else TEXT) for c, v in gorbov_sequence(self.n)]
        if self.symbols == "num":
            return [(str(i + 1), TEXT) for i in range(cells)]
        abc = RU_ABC if self.symbols == "ru" else EN_ABC
        if cells > len(abc):
            return [(str(i + 1), TEXT) for i in range(cells)]
        return [(abc[i], TEXT) for i in range(cells)]

    def new_game(self) -> None:
        self.stop()
        self.order = self._labels()
        self.cells = list(range(len(self.order)))
        random.shuffle(self.cells)        # cells[pos] = номер в порядке поиска
        self.found = 0
        self.errors = 0
        self.t0 = None
        self.done = False
        self.flash = None
        variant = f"{self.n}x{self.n}" + ("" if self.gorbov or self.symbols == "num" else f"-{self.symbols}")
        self.variant = variant
        best = (self.ctx.sstore.data["exercises"].get(self.code, {}).get(variant) or {}).get("best")
        self.lbl_rec.configure(text=f"РЕКОРД {self.n}×{self.n}: {fmt_s(best)}" if best else "РЕКОРДА ЕЩЁ НЕТ")
        self.h1.configure(text=f"ТРЕНАЖЁР {self.code} · {'ТАБЛИЦА ГОРБОВА' if self.gorbov else 'ТАБЛИЦА ШУЛЬТЕ'} "
                               f"{self.n}×{self.n}")
        self.h2.configure(text="← тренажёры обзора · таймер стартует с первого щелчка · взгляд — в центр")
        for n, b in self.size_btns.items():
            b.set_active(n == self.n)
        if not self.gorbov:
            for k, b in self.sym_btns.items():
                b.set_active(k == self.symbols)
        self._update()
        self.draw()

    def _geom(self):
        c = self.board
        w, h = c.winfo_width(), c.winfo_height()
        size = min(w, h) - px(30)
        cell = size / self.n
        x0, y0 = (w - size) / 2, (h - size) / 2
        return x0, y0, cell

    def draw(self) -> None:
        c = self.board
        c.delete("all")
        if c.winfo_width() < 50:
            return
        x0, y0, cell = self._geom()
        fs = max(10, int(cell / theme.S * 0.36))
        for pos, k in enumerate(self.cells):
            r, col = divmod(pos, self.n)
            x, y = x0 + col * cell, y0 + r * cell
            label, color = self.order[k]
            done = k < self.found
            bg = PANEL
            if self.flash and self.flash[0] == pos:
                bg = blend(self.flash[1], BG, 0.6)
            outline = LINE if done else LINE_HI
            c.create_rectangle(x + 2, y + 2, x + cell - 2, y + cell - 2, fill=bg, outline=outline)
            fg = FAINT if (done and self.fade) else color
            c.create_text(x + cell / 2, y + cell / 2, text=label, fill=fg, font=theme.font(fs, True, mono=True))
        cx, cy = x0 + cell * self.n / 2, y0 + cell * self.n / 2
        rr = px(5)
        c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=RED, outline=blend(RED, BG, 0.3))

    def click(self, e) -> None:
        if self.done:
            return
        x0, y0, cell = self._geom()
        col, row = int((e.x - x0) // cell), int((e.y - y0) // cell)
        if not (0 <= col < self.n and 0 <= row < self.n):
            return
        pos = row * self.n + col
        if self.t0 is None:
            self.t0 = time.perf_counter()
            self._tick()
        if self.cells[pos] == self.found:
            self.found += 1
            self.flash = (pos, GREEN)
            if self.found >= len(self.order):
                self.finish()
        elif self.cells[pos] > self.found or self.cells[pos] < self.found:
            if self.cells[pos] >= self.found:
                self.errors += 1
                self.flash = (pos, RED)
        self._update()
        self.draw()

    def elapsed(self) -> float:
        if self.t0 is None:
            return 0.0
        end = self.t_end if self.done else time.perf_counter()
        return end - self.t0 + self.errors * 2

    def _tick(self) -> None:
        self._job = None
        if self.done or self.t0 is None:
            return
        self.lbl_timer.configure(text=fmt_s(self.elapsed()))
        self._job = self.after(100, self._tick)

    def _update(self) -> None:
        total = len(self.order)
        if self.found < total:
            label, color = self.order[self.found]
            self.lbl_target.configure(text=label, fg=RED if color == RED else AMBER)
            nxt = self.order[self.found + 1][0] if self.found + 1 < total else "—"
            self.lbl_next.configure(text=f"СЛЕДУЮЩЕЕ: {nxt}")
        else:
            self.lbl_target.configure(text="✓", fg=GREEN)
            self.lbl_next.configure(text="ТАБЛИЦА ПРОЙДЕНА")
        self.lbl_found.configure(text=f"НАЙДЕНО {self.found} / {total}")
        el = self.elapsed()
        tempo = el / self.found if self.found else 0
        a, b, c = schulte_norm(self.n) if not self.gorbov else tuple(v * 1.7 for v in schulte_norm(self.n))
        self.lbl_tele.configure(text=f"ОШИБКИ        {self.errors}\nТЕМП, С/ЗНАК  {tempo:4.2f}\n"
                                     f"НОРМА ★★★   ≤ {a:.0f} С\nНОРМА ★★    ≤ {b:.0f} С\nНОРМА ★     ≤ {c:.0f} С")

    def finish(self) -> None:
        self.done = True
        self.t_end = time.perf_counter()
        self.stop()
        el = round(self.elapsed(), 1)
        self.lbl_timer.configure(text=fmt_s(el))
        norm = schulte_norm(self.n) if not self.gorbov else tuple(v * 1.7 for v in schulte_norm(self.n))
        stars = stars_for(el, norm)
        xp, record = self.ctx.sstore.add_exercise(self.code, self.variant, el, stars,
                                                  extra={"errors": self.errors})
        self.ctx.changed()
        self.lbl_rec.configure(text=("★ НОВЫЙ РЕКОРД! " if record else "") + f"{'★' * stars}{'☆' * (3 - stars)}"
                               f"  +{xp} XP", fg=AMBER)

    def on_key(self, e) -> None:
        if e.keysym in ("r", "R", "Cyrillic_ka", "Cyrillic_KA"):
            self.new_game()
        else:
            super().on_key(e)


# ---------------------------------------------------------------------------
class PyramidEx(ExerciseBase):
    """Пирамида: пары символов расходятся всё шире; смотреть на красную линию, отметить строку,
    где обе части ещё видны без движения глаз."""
    code = "E-PYR"

    def __init__(self, master, ctx, on_exit) -> None:
        super().__init__(master, ctx, on_exit)
        self.h1.configure(text="ТРЕНАЖЁР E-PYR · ПИРАМИДА (ПОЛЕ ЗРЕНИЯ)")
        self.h2.configure(text="смотрите только на красную линию · читайте обе части строки · "
                               "щёлкните по последней строке, где видно обе части без движения глаз")
        self.canvas = tk.Canvas(self.body, bg=BG2, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<Button-1>", self.click)
        self.result = L(self.body, "", fg=AMBER, size=11, bold=True, bg=BG)
        self.result.pack(pady=px(6))
        HudButton(self.body, "⟲ НОВАЯ ПИРАМИДА  R", self.new, color=AMBER, height=34).pack()
        self.new()

    def new(self) -> None:
        lang = self.ctx.sstore.settings.get("pyr_lang", "ru")
        abc = RU_ABC if lang == "ru" else EN_ABC
        self.rows = []
        for i in range(14):
            width = 2 + i * 3            # расстояние между частями, знаков
            a = "".join(random.choice(abc) for _ in range(2))
            b = "".join(random.choice(abc) for _ in range(2))
            self.rows.append((a, b, width))
        self.chosen = None
        self.result.configure(text="")
        self.draw()

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        f = theme.font(16, True, mono=True)
        import tkinter.font as tkfont
        cw = tkfont.Font(font=f).measure("0")
        cx = w / 2
        rh = (h - px(30)) / len(self.rows)
        c.create_line(cx, px(10), cx, h - px(10), fill=RED, width=2)
        for i, (a, b, width) in enumerate(self.rows):
            y = px(15) + rh * (i + 0.5)
            half = width * cw / 2
            col = AMBER if self.chosen == i else TEXT
            c.create_text(cx - half, y, text=a, anchor="e", fill=col, font=f)
            c.create_text(cx + half, y, text=b, anchor="w", fill=col, font=f)
            c.create_text(px(20), y, text=f"{width + 4:2d} зн.", anchor="w", fill=FAINT, font=theme.font(8, True))

    def click(self, e) -> None:
        h = self.canvas.winfo_height()
        rh = (h - px(30)) / len(self.rows)
        i = int((e.y - px(15)) // rh)
        if not 0 <= i < len(self.rows):
            return
        self.chosen = i
        width = self.rows[i][2] + 4
        stars = stars_for(width, (34, 24, 14), lower_is_better=False)
        xp, rec = self.ctx.sstore.add_exercise(self.code, "default", width, stars, lower_is_better=False)
        self.ctx.changed()
        self.result.configure(text=f"ШИРИНА ПОЛЯ: {width} знаков  {'★' * stars}{'☆' * (3 - stars)}  +{xp} XP"
                                   + ("  · НОВЫЙ РЕКОРД!" if rec else ""))
        self.draw()

    def on_key(self, e) -> None:
        if e.keysym in ("r", "R", "Cyrillic_ka", "Cyrillic_KA"):
            self.new()
        else:
            super().on_key(e)


# ---------------------------------------------------------------------------
class FlashEx(ExerciseBase):
    """Вспышка (тахистоскоп): слова на короткое время, затем маска; ввести увиденное.
    Лестница: 3 верных подряд — время −20 мс, ошибка — +20 мс; длина растёт на 2 уровнях."""
    code = "E-TAC"
    ROUNDS = 15

    def __init__(self, master, ctx, on_exit) -> None:
        super().__init__(master, ctx, on_exit)
        self.h1.configure(text="ТРЕНАЖЁР E-TAC · ВСПЫШКА (ТАХИСТОСКОП)")
        self.h2.configure(text="смотрите в центр прицела · слово мелькнёт и скроется · введите его и Enter")
        self.canvas = tk.Canvas(self.body, bg=BG2, highlightthickness=0, height=px(300))
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._frame())
        row = tk.Frame(self.body, bg=BG)
        row.pack(pady=px(8))
        self.inp = entry(row, width=34, size=16, mono=True)
        self.inp.pack(side=tk.LEFT, ipady=px(4))
        self.inp.bind("<Return>", lambda _e: self.check())
        HudButton(row, "ПРОВЕРИТЬ  ENTER", self.check, color=GREEN, height=36).pack(side=tk.LEFT, padx=px(8))
        HudButton(row, "⟲ ЗАНОВО", self.new, color=AMBER, height=36).pack(side=tk.LEFT)
        self.status = L(self.body, "", fg=MUTED, size=10, bold=True, bg=BG)
        self.status.pack()
        self.new()

    def _pool(self) -> list[str]:
        lang = self.ctx.sstore.settings.get("tac_lang", "ru")
        words: list[str] = []
        try:
            lib = self.ctx.lib
            tid = lib.index.get("active_reading")
            if tid:
                import re
                txt = lib.reading_text(tid)[:200000]
                words = [w.lower() for w in re.findall(r"[A-Za-zА-Яа-яЁё]{3,9}", txt)]
                if words:
                    return list(dict.fromkeys(words))
        except Exception:  # noqa: BLE001
            pass
        base = ("дом лес мир свет поле река небо окно море город книга время слово ветер звезда планета "
                "корабль пилот ракета космос орбита сигнал радар " if lang == "ru" else
                "home tree world light field river sky window sea city book time word wind star planet "
                "ship pilot rocket space orbit signal radar ")
        return base.split()

    def new(self) -> None:
        self.stop()
        self.pool = self._pool()
        self.ms = 300
        self.nwords = 1
        self.streak = 0
        self.round = 0
        self.ok = 0
        self.best_ms = None
        self.status.configure(text="")
        self._next_round()

    def _frame(self, text: str = "", mask: bool = False) -> None:
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        cx, cy = w / 2, h / 2
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx + dx * px(200), cy + dy * px(50)
            c.create_line(x, y, x - dx * px(18), y, fill=CYAN, width=2)
            c.create_line(x, y, x, y - dy * px(18), fill=CYAN, width=2)
        c.create_text(px(20), px(16), text=f"РАУНД {self.round}/{self.ROUNDS} · ПОКАЗ {self.ms} МС · СЛОВ {self.nwords}",
                      anchor="w", fill=MUTED, font=theme.font(9, True))
        if mask:
            c.create_text(cx, cy, text="#" * max(5, len(getattr(self, "answer", "")) or 5), fill=FAINT,
                          font=theme.font(28, True, mono=True))
        elif text:
            c.create_text(cx, cy, text=text, fill=TEXT, font=theme.font(28, True, mono=True))
        else:
            c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=RED, outline=RED)

    def _next_round(self) -> None:
        self.round += 1
        if self.round > self.ROUNDS:
            self.finish()
            return
        self.answer = " ".join(random.choice(self.pool) for _ in range(self.nwords))
        self.inp.delete(0, tk.END)
        self._frame()
        self._job = self.after(800, self._show)

    def _show(self) -> None:
        self._frame(self.answer)
        self._job = self.after(self.ms, self._mask)

    def _mask(self) -> None:
        self._frame(mask=True)
        self._job = None
        self.inp.focus_set()

    def check(self) -> None:
        if self._job is not None or self.round > self.ROUNDS:
            return
        got = " ".join(self.inp.get().lower().split())
        ok = got == self.answer.lower()
        if ok:
            self.ok += 1
            self.streak += 1
            if self.best_ms is None or (self.nwords, -self.ms) > (self.best_nw, -self.best_ms):
                self.best_ms, self.best_nw = self.ms, self.nwords
            if self.streak >= 3:
                self.streak = 0
                if self.ms > 60:
                    self.ms = max(50, self.ms - 20)
                elif self.nwords < 3:
                    self.nwords += 1
                    self.ms = 200
        else:
            self.streak = 0
            self.ms = min(500, self.ms + 20)
        self.status.configure(text=(f"✓ ВЕРНО: {self.answer}" if ok else f"✕ БЫЛО: {self.answer}"),
                              fg=GREEN if ok else RED)
        self._next_round()

    def finish(self) -> None:
        self.stop()
        if self.best_ms is None:
            self.status.configure(text="Нет верных ответов — попробуйте ещё раз (время показа вернётся к 300 мс).",
                                  fg=AMBER)
            return
        score = self.best_nw * 1000 - self.best_ms     # больше — лучше
        stars = 3 if (self.best_nw >= 3 and self.best_ms <= 100) else 2 if (self.best_nw >= 2 or self.best_ms <= 100) \
            else 1 if self.best_ms <= 200 else 0
        xp, rec = self.ctx.sstore.add_exercise(self.code, "default", score, stars, lower_is_better=False,
                                               extra={"ms": self.best_ms, "words": self.best_nw, "ok": self.ok})
        self.ctx.changed()
        self._frame()
        self.status.configure(text=f"ИТОГ: {self.best_nw} сл. за {self.best_ms} мс · верно {self.ok}/{self.ROUNDS}  "
                                   f"{'★' * stars}{'☆' * (3 - stars)}  +{xp} XP" + ("  · НОВЫЙ РЕКОРД!" if rec else ""),
                              fg=AMBER)

    def on_key(self, e) -> None:
        if e.keysym == "Escape":
            self.exit()


def best_text(code: str, rec: dict | None) -> str:
    if not rec:
        return "не начат"
    variant, r = rec
    b = r.get("best")
    if b is None:
        return "—"
    if code in ("E-SHL", "E-GRB"):
        return f"{variant.split('-')[0].replace('x', '×')} · {b:.1f} с"
    if code == "E-PYR":
        return f"ширина {int(b)} зн."
    if code == "E-TAC":
        best_run = max(r["runs"], key=lambda x: x["result"])
        return f"{best_run.get('words', 1)} сл · {best_run.get('ms', '?')} мс"
    return str(b)
