"""Вкладка «Грамматика»: 115 уроков по мотивам Essential Grammar in Use.

Слева — список уроков текущего уровня, справа — сам урок: цель, правило, примеры,
частые ошибки и упражнения с проверкой. Всё грузится порциями: индекс (22 КБ) —
одним фоновым чтением при первом открытии, урок (2–4 КБ) — по клику, виджеты —
по 2–3 блока за тик `after(1)`, чтобы окно не замирало даже на слабой машине.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import traceback

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

from stamina.english.grammar import lessons as gl
from stamina.english.ui import L, ScrollFrame, entry

LEVELS = ("a1", "a2", "b1")
LIST_CHUNK = 8      # строк списка за один тик
LESSON_CHUNK = 2    # блоков урока за один тик


class GrammarPage(tk.Frame):
    """Страница грамматики: оболочка сразу, данные и виджеты — порциями."""

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self._index_ready = False
        self._index_error: str | None = None
        self._level = "a1"
        self._unit: int | None = None
        self._token = 0
        self._jobs: dict[str, str] = {}
        self._rows: dict[int, dict] = {}
        self._answers: dict[int, bool] = {}
        self._exercises: list[dict] = []
        self._data: dict | None = None
        self._paused = False
        self._pending: queue.Queue = queue.Queue()
        self._pumping = False
        self._build_skeleton()

    # -- оболочка --------------------------------------------------------------
    def _build_skeleton(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = tk.Frame(self, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=px(14), pady=(px(8), 0))
        L(head, _t("ГРАММАТИКА"), fg=AMBER, size=14, bold=True).pack(side=tk.LEFT)
        L(head, "Essential Grammar in Use · 115", fg=MUTED, size=9).pack(side=tk.LEFT, padx=(px(10), 0))
        self._done_lbl = L(head, "", fg=MUTED, size=9)
        self._done_lbl.pack(side=tk.RIGHT)

        bar = tk.Frame(self, bg=BG)
        bar.grid(row=1, column=0, sticky="ew", padx=px(14), pady=(px(4), px(2)))
        self._level_buttons: dict[str, HudButton] = {}
        for lv in LEVELS:
            b = HudButton(bar, lv.upper(), lambda k=lv: self._select_level(k), height=24, font_size=8)
            b.pack(side=tk.LEFT, padx=(0, px(4)))
            self._level_buttons[lv] = b
        self._level_buttons[self._level].set_active(True)
        self._hint = L(bar, _t("Выберите урок слева"), fg=MUTED, size=8)
        self._hint.pack(side=tk.LEFT, padx=(px(10), 0))

        body = tk.Frame(self, bg=BG)
        body.grid(row=2, column=0, sticky="nsew", padx=px(14), pady=(0, px(8)))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG, width=px(272))
        left.grid(row=0, column=0, sticky="ns", padx=(0, px(8)))
        left.grid_propagate(False)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        panel = HudPanel(left, _t("УРОКИ"))
        panel.grid(row=0, column=0, sticky="nsew")
        self._list_sf = ScrollFrame(panel.body, bg=PANEL)
        self._list_sf.pack(fill=tk.BOTH, expand=True, padx=px(2), pady=(0, px(2)))

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._lesson_sf = ScrollFrame(right, bg=BG)
        self._lesson_sf.grid(row=0, column=0, sticky="nsew")

    # -- жизненный цикл --------------------------------------------------------
    def refresh(self) -> None:
        if not self._index_ready:
            if self._index_error is None:
                self._start_index()
            return
        self._update_counter()

    def destroy(self) -> None:
        self._cancel("list")
        self._cancel("lesson")
        self._cancel("pump")
        self._pumping = False
        super().destroy()

    # -- доставка из потоков ---------------------------------------------------
    def _ensure_pump(self) -> None:
        """Главный поток опрашивает очередь: `after` из воркера вызывать нельзя."""
        if self._pumping:
            return
        self._pumping = True
        self._jobs["pump"] = self.after(20, self._pump)

    def _pump(self) -> None:
        self._jobs.pop("pump", None)
        if not self.winfo_exists():
            self._pumping = False
            return
        busy = False
        for _ in range(8):
            try:
                fn = self._pending.get_nowait()
            except queue.Empty:
                break
            busy = True
            try:
                fn()
            except tk.TclError:
                self._pumping = False
                return
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._jobs["pump"] = self.after(40 if busy else 240, self._pump)

    # -- индекс ----------------------------------------------------------------
    def _start_index(self) -> None:
        self._cancel("index")
        L(self._list_sf.inner, "…", fg=MUTED, size=10).pack(anchor="w", padx=px(8), pady=px(8))

        def worker() -> None:
            try:
                gl.load_index()
                err = None
            except Exception as exc:  # noqa: BLE001
                err = exc
            self._pending.put(lambda: self._on_index(err))

        self._ensure_pump()
        threading.Thread(target=worker, daemon=True).start()

    def _on_index(self, err) -> None:
        if not self.winfo_exists():
            return
        if err is not None:
            self._index_error = str(err)
            for w in self._list_sf.inner.winfo_children():
                w.destroy()
            L(self._list_sf.inner, _t("Не удалось загрузить: {0}").format(err), fg=AMBER, size=9,
              wraplength=px(230), justify="left").pack(anchor="w", padx=px(8), pady=px(8))
            return
        self._index_ready = True
        self._update_counter()
        self._render_unit_list()
        if self._unit is None:
            first = gl.by_level(self._level)
            if first:
                self._open_unit(int(first[0]["n"]))

    def _update_counter(self) -> None:
        try:
            done = len([u for u in gl.units() if self.ctx.progress.grammar_done(int(u["n"]))])
            self._done_lbl.configure(text="{}: {} / {}".format(_t("ПРОЙДЕНО"), done, gl.total()))
        except Exception:  # noqa: BLE001
            pass

    # -- список уроков ---------------------------------------------------------
    def _select_level(self, level: str) -> None:
        if level not in LEVELS:
            return
        self._level = level
        for lv, b in self._level_buttons.items():
            b.set_active(lv == level)
        if not self._index_ready:
            return
        self._render_unit_list()
        first = gl.by_level(level)
        if first:
            self._open_unit(int(first[0]["n"]))

    def _follow_level(self, n: int) -> None:
        """Урок открыт кнопками ← → через границу уровня: переключаем и список."""
        if not self._index_ready:
            return
        info = gl.unit_info(n) or {}
        level = str(info.get("level") or "").lower()
        if level not in LEVELS or level == self._level:
            return
        self._level = level
        for lv, b in self._level_buttons.items():
            b.set_active(lv == level)
        self._render_unit_list()

    def _render_unit_list(self) -> None:
        self._cancel("list")
        inner = self._list_sf.inner
        for w in inner.winfo_children():
            w.destroy()
        self._rows.clear()
        plan: list[tuple] = []
        for m in gl.modules():
            us = [u for u in gl.units_of_module(m["id"]) if str(u.get("level", "")).lower() == self._level]
            if us:
                plan.append(("mod", m))
                plan.extend(("unit", u) for u in us)
        self._plan = plan
        self._plan_i = 0
        self._list_sf.top()
        self._list_chunk()

    def _list_chunk(self) -> None:
        if not getattr(self, "_plan", None):
            return
        inner = self._list_sf.inner
        end = min(self._plan_i + LIST_CHUNK, len(self._plan))
        for i in range(self._plan_i, end):
            kind, item = self._plan[i]
            if kind == "mod":
                L(inner, item["title"].upper(), fg=CYAN, size=8, bold=True).pack(
                    anchor="w", padx=px(8), pady=(px(10), px(2)))
                L(inner, item.get("en", ""), fg=FAINT, size=7).pack(anchor="w", padx=px(8))
            else:
                self._unit_row(inner, item)
        self._plan_i = end
        if end < len(self._plan):
            self._jobs["list"] = self.after(1, self._list_chunk)
        else:
            self._jobs.pop("list", None)
            self._highlight_unit()

    def _unit_row(self, host: tk.Frame, unit: dict) -> None:
        n = int(unit["n"])
        row = tk.Frame(host, bg=PANEL, cursor="hand2", highlightthickness=1, highlightbackground=LINE)
        row.pack(fill=tk.X, padx=px(6), pady=px(1))
        num = L(row, f"{n:02d}", fg=MUTED, size=8, bold=True, mono=True, bg=PANEL)
        num.pack(side=tk.LEFT, padx=(px(6), px(4)), pady=px(4), anchor="n")
        txt = tk.Label(row, text=unit.get("title", ""), fg=TEXT, bg=PANEL, font=theme.font(9),
                       justify="left", anchor="w", wraplength=px(196))
        txt.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(3))
        mark = L(row, "", fg=GREEN, size=10, bold=True, bg=PANEL)
        mark.pack(side=tk.RIGHT, padx=px(6))
        widgets = (row, num, txt, mark)
        for w in widgets:
            w.bind("<Button-1>", lambda _e, k=n: self._open_unit(k))
            w.bind("<Enter>", lambda _e, k=n: self._row_hover(k, True))
            w.bind("<Leave>", lambda _e, k=n: self._row_hover(k, False))
        self._rows[n] = {"row": row, "widgets": widgets, "mark": mark, "num": num, "txt": txt}
        self._paint_row(n)

    def _row_hover(self, n: int, on: bool) -> None:
        data = self._rows.get(n)
        if not data or n == self._unit:
            return
        bg = BG2 if on else PANEL
        for w in data["widgets"]:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass
        data["row"].configure(highlightbackground=CYAN if on else LINE, bg=bg)

    def _paint_row(self, n: int) -> None:
        data = self._rows.get(n)
        if not data:
            return
        done = self.ctx.progress.grammar_done(n)
        active = n == self._unit
        bg = BG2 if active else PANEL
        for w in data["widgets"]:
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass
        data["row"].configure(highlightbackground=CYAN if active else LINE, bg=bg)
        data["mark"].configure(text="✓" if done else "", bg=bg)
        data["num"].configure(fg=CYAN if active else MUTED, bg=bg)
        data["txt"].configure(fg=TEXT if (active or done) else MUTED, bg=bg)

    def _highlight_unit(self) -> None:
        for n in self._rows:
            self._paint_row(n)

    # -- урок ------------------------------------------------------------------
    def _clear_lesson(self) -> None:
        for w in self._lesson_sf.inner.winfo_children():
            w.destroy()
        self._lesson_sf.top()

    def _open_unit(self, n: int) -> None:
        n = int(n)
        if n == self._unit and self._data is not None:
            return
        self._unit = n
        self._data = None
        self._answers = {}
        self._exercises = []
        self._follow_level(n)
        self._highlight_unit()
        self._token += 1
        token = self._token
        self._cancel("lesson")
        self._clear_lesson()
        L(self._lesson_sf.inner, _t("Загрузка урока…"), fg=MUTED, size=10).pack(
            anchor="w", padx=px(12), pady=px(12))

        def worker() -> None:
            try:
                data = gl.load_lesson(n)
                err = None
            except Exception as exc:  # noqa: BLE001
                data, err = None, exc
            self._pending.put(lambda: self._on_lesson(token, n, data, err))

        self._ensure_pump()
        threading.Thread(target=worker, daemon=True).start()

    def _on_lesson(self, token: int, n: int, data, err) -> None:
        if token != self._token or not self.winfo_exists():
            return
        self._clear_lesson()
        if err is not None:
            L(self._lesson_sf.inner, _t("Не удалось загрузить: {0}").format(err), fg=AMBER, size=10,
              wraplength=px(560), justify="left").pack(anchor="w", padx=px(12), pady=px(12))
            return
        self._data = data
        self._exercises = list(data.get("exercises") or [])
        self._answers = {}
        self._hint.configure(text=_t("Урок {0} из {1}").format(n, gl.total()))
        pieces = self._lesson_pieces(data)
        self._piece_i = 0
        self._piece_token = token
        self._lesson_chunk(pieces)

    def _lesson_pieces(self, data: dict) -> list:
        """Порции отрисовки: каждая функция добавляет свои виджеты в конец области."""
        host = self._lesson_sf.inner
        pieces = [lambda: self._piece_head(host, data)]
        pieces.append(lambda: self._piece_goal(host, data))
        for block in data.get("theory") or []:
            pieces.append(lambda b=block: self._piece_theory(host, b))
        pieces.append(lambda: self._piece_examples(host, data))
        if data.get("traps"):
            pieces.append(lambda: self._piece_traps(host, data))
        pieces.append(lambda: self._piece_ex_head(host, data))
        for i, ex in enumerate(self._exercises):
            pieces.append(lambda k=i, e=ex: self._piece_exercise(host, k, e))
        pieces.append(lambda: self._piece_foot(host, data))
        return pieces

    def _lesson_chunk(self, pieces: list) -> None:
        token = self._piece_token
        if token != self._token:
            return
        end = min(self._piece_i + LESSON_CHUNK, len(pieces))
        for i in range(self._piece_i, end):
            try:
                pieces[i]()
            except tk.TclError:
                return
        self._piece_i = end
        if end < len(pieces):
            self._jobs["lesson"] = self.after(1, lambda: self._lesson_chunk(pieces))
        else:
            self._jobs.pop("lesson", None)

    # -- части урока -----------------------------------------------------------
    def _piece_head(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill=tk.X, padx=px(12), pady=(px(10), 0))
        L(top, f"{int(data['n']):02d}", fg=AMBER, size=24, bold=True, mono=True, bg=PANEL).pack(side=tk.LEFT)
        col = tk.Frame(top, bg=PANEL)
        col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(px(10), 0))
        tk.Label(col, text=data.get("title", ""), fg=TEXT, bg=PANEL, font=theme.font(14, True),
                 justify="left", anchor="w", wraplength=px(470)).pack(anchor="w")
        L(col, data.get("en", ""), fg=CYAN, size=10, mono=True, bg=PANEL).pack(anchor="w")
        L(top, str(data.get("level", "")).upper(), fg=MUTED, size=9, bold=True,
          bg=PANEL).pack(side=tk.RIGHT, anchor="n")
        tk.Label(box, text=data.get("summary", ""), fg=TEXT, bg=PANEL, font=theme.font(10),
                 justify="left", anchor="w", wraplength=px(560)).pack(
            fill=tk.X, padx=px(12), pady=(px(6), px(10)))

    def _piece_goal(self, host, data: dict) -> None:
        goals = [g for g in (data.get("can_do") or []) if g]
        if not goals:
            return
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, _t("ЦЕЛЬ УРОКА"), fg=CYAN, size=8, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(8), px(2)))
        for g in goals:
            tk.Label(box, text="▸  " + g, fg=TEXT, bg=PANEL, font=theme.font(10),
                     justify="left", anchor="w", wraplength=px(540)).pack(
                fill=tk.X, padx=px(12), pady=(0, px(4)))

    def _piece_theory(self, host, block: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        L(box, block.get("h", ""), fg=AMBER, size=11, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(8), px(2)))
        tk.Label(box, text=block.get("p", ""), fg=TEXT, bg=PANEL, font=theme.font(10),
                 justify="left", anchor="w", wraplength=px(560)).pack(fill=tk.X, padx=px(12))
        formula = block.get("formula")
        if formula:
            L(box, formula, fg=CYAN, size=10, bold=True, mono=True, bg=BG2,
              wraplength=px(548), justify="left", anchor="w").pack(
                fill=tk.X, padx=px(10), pady=(px(6), px(4)))
        table = block.get("table")
        if table:
            self._piece_table(box, table)
        tk.Frame(box, bg=PANEL, height=px(6)).pack()

    def _piece_table(self, host, table: dict) -> None:
        grid = tk.Frame(host, bg=PANEL)
        grid.pack(fill=tk.X, padx=px(12), pady=(px(4), px(2)))
        head = table.get("head") or []
        for c, name in enumerate(head):
            L(grid, str(name), fg=MUTED, size=8, bold=True, bg=PANEL).grid(
                row=0, column=c, sticky="w", padx=(0, px(12)), pady=(0, px(2)))
        for r, row in enumerate(table.get("rows") or [], start=1):
            for c, cell in enumerate(row):
                L(grid, str(cell), fg=TEXT, size=9, mono=(c == 1), bg=PANEL).grid(
                    row=r, column=c, sticky="w", padx=(0, px(12)))

    def _piece_examples(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, _t("ПРИМЕРЫ"), fg=CYAN, size=8, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(8), px(2)))
        for ex in data.get("examples") or []:
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill=tk.X, padx=px(10), pady=(0, px(4)))
            col = tk.Frame(row, bg=PANEL)
            col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(col, text=ex.get("en", ""), fg=TEXT, bg=PANEL, font=theme.font(11),
                     justify="left", anchor="w", wraplength=px(500)).pack(anchor="w")
            L(col, ex.get("ru", ""), fg=MUTED, size=9, bg=PANEL, wraplength=px(500),
              justify="left", anchor="w").pack(anchor="w")
            speaker = getattr(self.ctx, "audio_button", None)
            if callable(speaker):
                try:
                    en_text = ex.get("en", "")
                    speaker(row, "🔊", lambda s=en_text: s, height=22, font_size=8,
                            width=30).pack(side=tk.RIGHT, padx=(px(4), 0))
                except tk.TclError:
                    pass

    def _piece_traps(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, _t("ЧАСТЫЕ ОШИБКИ"), fg=CYAN, size=8, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(8), px(2)))
        for t in data.get("traps") or []:
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill=tk.X, padx=px(12), pady=(0, px(6)))
            L(row, "✕ " + str(t.get("bad", "")), fg=RED, size=10, bg=PANEL, wraplength=px(520),
              justify="left", anchor="w").pack(anchor="w")
            L(row, "✓ " + str(t.get("good", "")), fg=GREEN, size=10, bg=PANEL, wraplength=px(520),
              justify="left", anchor="w").pack(anchor="w")
            L(row, str(t.get("why", "")), fg=MUTED, size=8, bg=PANEL, wraplength=px(520),
              justify="left", anchor="w").pack(anchor="w")

    def _piece_ex_head(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=BG)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(4)))
        L(box, _t("УПРАЖНЕНИЯ"), fg=CYAN, size=8, bold=True).pack(side=tk.LEFT)
        self._score_lbl = L(box, _t("Верно: {0} из {1}").format(0, len(self._exercises)), fg=MUTED, size=8)
        self._score_lbl.pack(side=tk.RIGHT)
        self._banner_box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        self._banner = L(self._banner_box, "", fg=GREEN, size=10, bold=True, bg=PANEL,
                         wraplength=px(540), justify="left", anchor="w")
        self._banner.pack(anchor="w", padx=px(12), pady=px(8))

    def _piece_exercise(self, host, idx: int, ex: dict) -> None:
        card = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), px(2)))
        L(top, f"{idx + 1}.", fg=AMBER, size=10, bold=True, mono=True, bg=PANEL, width=3).pack(
            side=tk.LEFT, anchor="n")
        tk.Label(top, text=ex.get("q", ""), fg=TEXT, bg=PANEL, font=theme.font(11),
                 justify="left", anchor="w", wraplength=px(520)).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        note = L(card, "", fg=MUTED, size=8, bg=PANEL, wraplength=px(540), justify="left", anchor="w")

        if ex.get("type") == "choice":
            options = list(ex.get("options") or [])
            right = int(ex.get("a", 0))
            chips = []
            for i, opt in enumerate(options):
                chip = tk.Frame(card, bg=PANEL, cursor="hand2", highlightthickness=1,
                                highlightbackground=LINE)
                chip.pack(fill=tk.X, padx=px(14), pady=px(1))
                body = tk.Frame(chip, bg=PANEL)
                body.pack(fill=tk.X)
                num = L(body, str(i + 1), fg=AMBER, size=9, bold=True, mono=True, bg=PANEL, width=2)
                num.pack(side=tk.LEFT, padx=(px(6), px(4)), pady=px(3))
                txt = L(body, str(opt), fg=TEXT, size=10, bg=PANEL, anchor="w", justify="left",
                        wraplength=px(470))
                txt.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(3))
                parts = (chip, body, num, txt)
                for w in parts:
                    w.bind("<Button-1>",
                           lambda _e, k=i, p=parts: self._answer_choice(idx, k, right, ex, p, note))
                chips.append(parts)
            note.pack(fill=tk.X, padx=px(14), pady=(0, px(6)))
            return

        row = tk.Frame(card, bg=PANEL)
        row.pack(fill=tk.X, padx=px(14), pady=(px(2), px(2)))
        var = tk.StringVar()
        field = entry(row, width=30, size=10)
        field.configure(textvariable=var)
        field.pack(side=tk.LEFT, ipady=px(4))
        btn = HudButton(row, _t("ПРОВЕРИТЬ"), None, height=26, font_size=8)
        btn.pack(side=tk.LEFT, padx=(px(6), 0))
        note.pack(fill=tk.X, padx=px(14), pady=(px(2), px(6)))

        def check(_e=None) -> None:
            if idx in self._answers:
                return
            ok = gl.answer_ok(var.get(), gl.lesson_answers(ex))
            self._answer_gap(idx, ok, ex, field, btn, note, var)
            return "break"

        btn.command = check
        field.bind("<Return>", check)

    def _answer_choice(self, idx: int, picked: int, right: int, ex: dict, parts, note) -> None:
        if idx in self._answers:
            return
        ok = picked == right
        for i, (chip, body, num, txt) in enumerate(parts):
            if i == right:
                chip.configure(highlightbackground=GREEN, highlightthickness=2)
                body.configure(bg=BG2)
                num.configure(bg=BG2)
                txt.configure(bg=BG2, fg=GREEN, font=theme.font(10, True))
            elif i == picked:
                chip.configure(highlightbackground=RED, highlightthickness=2)
                body.configure(bg=BG2)
                num.configure(bg=BG2)
                txt.configure(bg=BG2, fg=RED)
            else:
                chip.configure(highlightbackground=LINE)
                body.configure(bg=PANEL)
                num.configure(bg=PANEL)
                txt.configure(bg=PANEL, fg=MUTED)
        self._finish(idx, ok, ex, note)

    def _answer_gap(self, idx: int, ok: bool, ex: dict, field, btn, note, var) -> None:
        variant_ok = any(gl.normalize(var.get()) == gl.normalize(v) for v in gl.lesson_answers(ex))
        try:
            field.configure(state="disabled", disabledforeground=GREEN if variant_ok else RED)
        except tk.TclError:
            return
        btn.set_enabled(False)
        self._finish(idx, variant_ok, ex, note)

    def _finish(self, idx: int, ok: bool, ex: dict, note) -> None:
        if idx in self._answers:
            return
        self._answers[idx] = bool(ok)
        text = ("✓ " + _t("ВЕРНО")) if ok else ("✕ " + _t("НЕВЕРНО") + " · " +
                                               _t("Ответ: {0}").format(", ".join(gl.lesson_answers(ex))))
        why = str(ex.get("why", "")).strip()
        if why:
            text += " · " + why
        try:
            note.configure(text=text, fg=GREEN if ok else AMBER)
        except tk.TclError:
            pass
        self._update_score()
        self._check_complete()

    def _update_score(self) -> None:
        lbl = getattr(self, "_score_lbl", None)
        if lbl is None:
            return
        ok = sum(1 for v in self._answers.values() if v)
        lbl.configure(text=_t("Верно: {0} из {1}").format(ok, len(self._exercises)),
                      fg=GREEN if self._answers and ok == len(self._answers) else MUTED)

    def _check_complete(self) -> None:
        if self._unit is None or not self._exercises:
            return
        if len(self._answers) < len(self._exercises):
            return
        ok = sum(1 for v in self._answers.values() if v)
        done = self.ctx.progress.grammar_mark(self._unit, ok, len(self._exercises))
        self._update_counter()
        self._paint_row(self._unit)
        box = getattr(self, "_banner_box", None)
        if box is not None and not box.winfo_manager():
            text = "{} · {}: {} / {}".format(_t("УРОК ПРОЙДЕН"), _t("ВЕРНО"), ok, len(self._exercises))
            self._banner.configure(text=text, fg=GREEN if ok == len(self._exercises) else AMBER)
            box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        if done:
            try:
                self.ctx.status("{}: {}".format(_t("УРОК ПРОЙДЕН"), self._data.get("title", "")), GREEN)
            except Exception:  # noqa: BLE001
                pass

    def _piece_foot(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=BG)
        box.pack(fill=tk.X, padx=px(10), pady=(px(2), px(14)))
        row = tk.Frame(box, bg=BG)
        row.pack(fill=tk.X)
        prev_n, next_n = gl.neighbours(int(data["n"]))
        if prev_n is not None:
            HudButton(row, "← " + _t("НАЗАД"), lambda k=prev_n: self._open_unit(k), height=28,
                      font_size=8).pack(side=tk.LEFT)
        if next_n is not None:
            HudButton(row, _t("ДАЛЬШЕ") + " →", lambda k=next_n: self._open_unit(k), height=28,
                      font_size=8, color=GREEN).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(row, _t("Заново"), lambda: self._open_unit(int(self._unit)), height=28,
                  font_size=8, color=MUTED).pack(side=tk.RIGHT)

    # -- служебное -------------------------------------------------------------
    def _cancel(self, key: str) -> None:
        job = self._jobs.pop(key, None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:  # noqa: BLE001
                pass


def init_grammar_tab(english_screen) -> None:
    """Устарело: грамматика собирается в EnglishScreen._build как GrammarPage."""
