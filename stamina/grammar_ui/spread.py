"""Общий вид грамматики: слева список уроков, справа весь урок как разворот Murphy.

Оболочка строится сразу; индекс и урок подгружаются порциями, виджеты — по
LIST_CHUNK / LESSON_CHUNK за тик after(1), чтобы окно не замирало.
Страницы языков передают каталог (GrammarCatalog) и не меняют этот каркас.
Вкладки источников показываются только если каталог явно просит (у английского
их нет — экран остаётся прежним).
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

from stamina.english.ui import L, ScrollFrame, entry

LIST_CHUNK = 8
LESSON_CHUNK = 2


class GrammarSpread(tk.Frame):
    """Двухпанельный разворот грамматики. Данные — только через catalog."""

    def __init__(self, master, catalog, ctx=None, *, title: str | None = None) -> None:
        super().__init__(master, bg=BG)
        self.catalog = catalog
        self.ctx = ctx
        self._title = title if title is not None else _t("ГРАММАТИКА")
        self._index_ready = False
        self._index_error: str | None = None
        levels = list(getattr(catalog, "levels", None) or [])
        self._level = levels[0] if levels else "a1"
        self._unit = None
        self._token = 0
        self._jobs: dict[str, str] = {}
        self._rows: dict = {}
        self._answers: dict = {}
        self._exercises: list[dict] = []
        self._data: dict | None = None
        self._pending: queue.Queue = queue.Queue()
        self._pumping = False
        self._table_id: str | None = None
        self._source_buttons: dict[str, HudButton] = {}
        self._build_skeleton()

    # -- оболочка --------------------------------------------------------------
    def _build_skeleton(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        head = tk.Frame(self, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=px(14), pady=(px(8), 0))
        L(head, self._title, fg=AMBER, size=14, bold=True).pack(side=tk.LEFT)
        self._book_lbl = L(head, "", fg=MUTED, size=9)
        self._book_lbl.pack(side=tk.LEFT, padx=(px(10), 0))
        self._done_lbl = L(head, "", fg=MUTED, size=9)
        self._done_lbl.pack(side=tk.RIGHT)

        self._tabs_host = tk.Frame(self, bg=BG)
        self._tabs_host.grid(row=1, column=0, sticky="ew", padx=px(14), pady=(px(2), 0))
        self._rebuild_source_tabs()

        bar = tk.Frame(self, bg=BG)
        bar.grid(row=2, column=0, sticky="ew", padx=px(14), pady=(px(4), px(2)))
        self._level_bar = bar
        self._hint_bar = bar
        self._rebuild_level_buttons()
        self._hint = L(bar, _t("Выберите урок слева"), fg=MUTED, size=8)
        self._hint.pack(side=tk.LEFT, padx=(px(10), 0))
        self._update_book_label()

        body = tk.Frame(self, bg=BG)
        body.grid(row=3, column=0, sticky="nsew", padx=px(14), pady=(0, px(8)))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._body = body

        left = tk.Frame(body, bg=BG, width=px(272))
        left.grid(row=0, column=0, sticky="ns", padx=(0, px(8)))
        left.grid_propagate(False)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._left = left
        panel = HudPanel(left, _t("УРОКИ"))
        panel.grid(row=0, column=0, sticky="nsew")
        self._list_panel = panel
        self._list_sf = ScrollFrame(panel.body, bg=PANEL)
        self._list_sf.pack(fill=tk.BOTH, expand=True, padx=px(2), pady=(0, px(2)))
        self._left_extra = tk.Frame(left, bg=BG)
        self._left_extra.grid(row=1, column=0, sticky="ew", pady=(px(4), 0))

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._lesson_sf = ScrollFrame(right, bg=BG)
        self._lesson_sf.grid(row=0, column=0, sticky="nsew")
        # алиас для тестов: прокручиваемая область урока
        self.content = self
        self._rebuild_left_extra()

    def _rebuild_source_tabs(self) -> None:
        for w in self._tabs_host.winfo_children():
            w.destroy()
        self._source_buttons = {}
        sources = []
        if getattr(self.catalog, "show_source_tabs", False):
            sources = list(self.catalog.sources() or [])
        if not sources:
            self._tabs_host.grid_remove()
            return
        self._tabs_host.grid()
        current = self.catalog.current_source_id()
        # Перенос длинных подписей: вкладки идут потоком, не в одну жёсткую строку.
        inner = tk.Frame(self._tabs_host, bg=BG)
        inner.pack(fill=tk.X)
        for src in sources:
            btn = HudButton(
                inner, src.title, lambda k=src.id: self._select_source(k),
                height=24, font_size=7, active=(src.id == current),
            )
            btn.pack(side=tk.LEFT, padx=(0, px(4)), pady=(0, px(2)))
            self._source_buttons[src.id] = btn

    def _rebuild_level_buttons(self) -> None:
        for w in list(self._level_bar.winfo_children()):
            if w is getattr(self, "_hint", None):
                continue
            try:
                if isinstance(w, HudButton):
                    w.destroy()
            except tk.TclError:
                pass
        self._level_buttons: dict[str, HudButton] = {}
        levels = list(getattr(self.catalog, "levels", None) or [])
        for lv in levels:
            label = lv.upper() if len(lv) <= 3 else lv
            b = HudButton(self._level_bar, label, lambda k=lv: self._select_level(k),
                          height=24, font_size=8)
            b.pack(side=tk.LEFT, padx=(0, px(4)))
            self._level_buttons[lv] = b
        if self._level in self._level_buttons:
            self._level_buttons[self._level].set_active(True)
        hint = getattr(self, "_hint", None)
        if hint is not None:
            hint.pack_forget()
            hint.pack(side=tk.LEFT, padx=(px(10), 0))

    def _rebuild_left_extra(self) -> None:
        for w in self._left_extra.winfo_children():
            w.destroy()
        builder = getattr(self.catalog, "build_left_extra", None)
        if callable(builder):
            builder(self._left_extra, self)

    def _select_source(self, source_id: str) -> None:
        if source_id == self.catalog.current_source_id():
            return
        self.catalog.select_source(source_id)
        for sid, btn in self._source_buttons.items():
            btn.set_active(sid == source_id)
        levels = list(getattr(self.catalog, "levels", None) or [])
        self._level = levels[0] if levels else self._level
        self._unit = None
        self._data = None
        self._rebuild_level_buttons()
        if self._hint is not None:
            self._hint.pack(side=tk.LEFT, padx=(px(10), 0))
        self._rebuild_left_extra()
        self._index_ready = False
        self._index_error = None
        self._clear_lesson()
        self._update_book_label()
        # индекс вкладки маленький: грузим сразу, без гонки с фоновым потоком
        try:
            self.catalog.load_index()
        except Exception as exc:  # noqa: BLE001
            self._on_index(exc)
            return
        self._on_index(None)

    # -- жизненный цикл --------------------------------------------------------
    def refresh(self) -> None:
        if not self._index_ready:
            if self._index_error is None:
                self._start_index()
            return
        self._update_counter()
        self._rebuild_left_extra()

    def destroy(self) -> None:
        self._cancel("list")
        self._cancel("lesson")
        self._cancel("pump")
        self._pumping = False
        super().destroy()

    def _flush_pending(self) -> None:
        """Для тестов: выгрузить очередь потоков и все after-порции."""
        for _ in range(8):
            try:
                fn = self._pending.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        # Несколько проходов: список и урок рисуются after(1)
        for _ in range(80):
            pending = [key for key in ("list", "lesson") if key in self._jobs]
            if not pending:
                break
            for key in pending:
                job = self._jobs.get(key)
                if job is None:
                    continue
                try:
                    self.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
                self._jobs.pop(key, None)
                if key == "list":
                    self._list_chunk()
                elif key == "lesson" and getattr(self, "_chunk_pieces", None):
                    self._lesson_chunk(self._chunk_pieces)

    # -- доставка из потоков ---------------------------------------------------
    def _ensure_pump(self) -> None:
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
        for w in self._list_sf.inner.winfo_children():
            w.destroy()
        L(self._list_sf.inner, "…", fg=MUTED, size=10).pack(anchor="w", padx=px(8), pady=px(8))

        def worker() -> None:
            try:
                self.catalog.load_index()
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
        self._update_book_label()
        self._update_counter()
        self._render_unit_list()
        if self._unit is None and self._table_id is None:
            first = self.catalog.first_unit(self._level)
            if first is not None:
                self._open_unit(first)

    def _update_book_label(self) -> None:
        lbl = getattr(self, "_book_lbl", None)
        if lbl is None:
            return
        if not self._index_ready and not self.catalog.index_loaded():
            return
        try:
            text = self.catalog.header_subtitle(self._level)
            lbl.configure(text=text or "")
        except tk.TclError:
            pass
        except Exception:  # noqa: BLE001
            return

    def _update_counter(self) -> None:
        try:
            self._done_lbl.configure(text=self.catalog.progress_text())
        except Exception:  # noqa: BLE001
            pass

    # -- список уроков ---------------------------------------------------------
    def _select_level(self, level: str) -> None:
        levels = list(getattr(self.catalog, "levels", None) or [])
        if level not in levels:
            return
        self._level = level
        for lv, b in self._level_buttons.items():
            b.set_active(lv == level)
        self._update_book_label()
        if not self._index_ready:
            return
        self._render_unit_list()
        first = self.catalog.first_unit(level)
        if first is not None:
            self._open_unit(first)

    def _follow_level(self, unit_id) -> None:
        if not self._index_ready:
            return
        try:
            level = self.catalog.level_of(unit_id)
        except Exception:  # noqa: BLE001
            return
        levels = list(getattr(self.catalog, "levels", None) or [])
        if not level or level not in levels or level == self._level:
            return
        self._level = level
        for lv, b in self._level_buttons.items():
            b.set_active(lv == level)
        self._update_book_label()
        self._render_unit_list()

    def _render_unit_list(self) -> None:
        self._cancel("list")
        inner = self._list_sf.inner
        for w in inner.winfo_children():
            w.destroy()
        self._rows.clear()
        self._plan = list(self.catalog.list_plan(self._level) or [])
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
                if item.get("en") or item.get("subtitle"):
                    L(inner, item.get("en") or item.get("subtitle") or "", fg=FAINT, size=7).pack(
                        anchor="w", padx=px(8))
            else:
                self._unit_row(inner, item)
        self._plan_i = end
        if end < len(self._plan):
            self._jobs["list"] = self.after(1, self._list_chunk)
        else:
            self._jobs.pop("list", None)
            self._highlight_unit()

    def _unit_row(self, host: tk.Frame, unit: dict) -> None:
        n = unit["id"]
        row = tk.Frame(host, bg=PANEL, cursor="hand2", highlightthickness=1, highlightbackground=LINE)
        row.pack(fill=tk.X, padx=px(6), pady=px(1))
        number = unit.get("number") or ""
        num = L(row, str(number), fg=MUTED, size=8, bold=True, mono=True, bg=PANEL)
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

    def _row_hover(self, n, on: bool) -> None:
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

    def _paint_row(self, n) -> None:
        data = self._rows.get(n)
        if not data:
            return
        try:
            done = self.catalog.is_done(n)
        except Exception:  # noqa: BLE001
            done = False
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
        self._table_id = None
        self._chunk_pieces = None
        for w in self._lesson_sf.inner.winfo_children():
            w.destroy()
        self._lesson_sf.top()

    def _open_unit(self, n) -> None:
        if n == self._unit and self._data is not None and self._table_id is None:
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
                data = self.catalog.load_lesson(n)
                err = None
            except Exception as exc:  # noqa: BLE001
                data, err = None, exc
            self._pending.put(lambda: self._on_lesson(token, n, data, err))

        self._ensure_pump()
        threading.Thread(target=worker, daemon=True).start()

    def _on_lesson(self, token: int, n, data, err) -> None:
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
        try:
            self._hint.configure(text=self.catalog.hint_for_unit(n))
        except Exception:  # noqa: BLE001
            pass
        pieces = self._lesson_pieces(data)
        self._piece_i = 0
        self._piece_token = token
        self._chunk_pieces = pieces
        self._lesson_chunk(pieces)

    def _lesson_pieces(self, data: dict) -> list:
        host = self._lesson_sf.inner
        pieces = []
        if data.get("attribution") or data.get("original_url"):
            pieces.append(lambda: self._piece_attribution(host, data))
        pieces.append(lambda: self._piece_head(host, data))
        if data.get("prereq_warning"):
            pieces.append(lambda: self._piece_prereq(host, data))
        pieces.append(lambda: self._piece_goal(host, data))
        if data.get("bridge"):
            pieces.append(lambda: self._piece_named(
                host, _t("МОСТИК RU/UA → DE"), str(data.get("bridge") or "")))
        if data.get("trap_text"):
            pieces.append(lambda: self._piece_named(
                host, _t("ЛОВУШКА"), str(data.get("trap_text") or "")))
        for block in data.get("theory") or []:
            pieces.append(lambda b=block: self._piece_theory(host, b))
        if data.get("examples"):
            pieces.append(lambda: self._piece_examples(host, data))
        if data.get("traps"):
            pieces.append(lambda: self._piece_traps(host, data))
        if self._exercises:
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
    def _piece_attribution(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        text = str(data.get("attribution") or "").strip()
        url = str(data.get("original_url") or "").strip()
        if text:
            tk.Label(box, text=text, fg=MUTED, bg=PANEL, font=theme.font(8),
                     justify="left", anchor="w", wraplength=px(560)).pack(
                fill=tk.X, padx=px(12), pady=(px(8), px(2)))
        if url:
            L(box, url, fg=CYAN, size=8, bg=PANEL, wraplength=px(560),
              justify="left", anchor="w").pack(fill=tk.X, padx=px(12), pady=(0, px(8)))

    def _piece_prereq(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=AMBER)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, str(data.get("prereq_warning") or ""), fg=AMBER, size=9, bg=PANEL,
          wraplength=px(560), justify="left", anchor="w").pack(
            fill=tk.X, padx=px(12), pady=px(8))

    def _piece_named(self, host, title: str, text: str) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, title, fg=CYAN, size=8, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(8), px(2)))
        tk.Label(box, text=text, fg=TEXT, bg=PANEL, font=theme.font(10),
                 justify="left", anchor="w", wraplength=px(560)).pack(
            fill=tk.X, padx=px(12), pady=(0, px(10)))

    def _piece_head(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill=tk.X, padx=px(12), pady=(px(10), 0))
        try:
            number = self.catalog.unit_number(data.get("n", self._unit))
        except Exception:  # noqa: BLE001
            number = data.get("number") or 0
        L(top, f"{int(number):02d}" if str(number).isdigit() else str(number),
          fg=AMBER, size=24, bold=True, mono=True, bg=PANEL).pack(side=tk.LEFT)
        col = tk.Frame(top, bg=PANEL)
        col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(px(10), 0))
        tk.Label(col, text=data.get("title", ""), fg=TEXT, bg=PANEL, font=theme.font(14, True),
                 justify="left", anchor="w", wraplength=px(470)).pack(anchor="w")
        if data.get("en"):
            L(col, data.get("en", ""), fg=CYAN, size=10, mono=True, bg=PANEL).pack(anchor="w")
        L(top, str(data.get("level", "")).upper(), fg=MUTED, size=9, bold=True,
          bg=PANEL).pack(side=tk.RIGHT, anchor="n")
        if data.get("summary"):
            tk.Label(box, text=data.get("summary", ""), fg=TEXT, bg=PANEL, font=theme.font(10),
                     justify="left", anchor="w", wraplength=px(560)).pack(
                fill=tk.X, padx=px(12), pady=(px(6), px(10)))
        else:
            tk.Frame(box, bg=PANEL, height=px(10)).pack()

    def _piece_goal(self, host, data: dict) -> None:
        goals = [g for g in (data.get("can_do") or []) if g]
        if not goals:
            return
        # Для немецкого курса заголовок тот же смысл, что «цель урока»;
        # тесты ищут «ЧТО ВЫ ОСВОИТЕ», если каталог так пометил блок.
        title = data.get("can_do_title") or _t("ЦЕЛЬ УРОКА")
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        # HudPanel не нужен: как в английском, заголовок — подпись в рамке.
        # Для совместимости с немецкими проверками дублируем текст заголовка.
        head = L(box, title, fg=CYAN, size=8, bold=True, bg=PANEL)
        head.pack(anchor="w", padx=px(12), pady=(px(8), px(2)))
        for g in goals:
            tk.Label(box, text="▸  " + g, fg=TEXT, bg=PANEL, font=theme.font(10),
                     justify="left", anchor="w", wraplength=px(540)).pack(
                fill=tk.X, padx=px(12), pady=(0, px(4)))

    def _piece_theory(self, host, block: dict) -> None:
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        heading = block.get("h") or ""
        if heading:
            L(box, heading, fg=AMBER, size=11, bold=True, bg=PANEL).pack(
                anchor="w", padx=px(12), pady=(px(8), px(2)))
        if block.get("p"):
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
        ref = block.get("table_ref")
        if ref:
            title = block.get("table_title") or ref
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill=tk.X, padx=px(12), pady=(px(6), px(4)))
            HudButton(row, _t("Таблица: {0}").format(title),
                      lambda r=ref: self._open_table(r), height=26, font_size=8,
                      color=CYAN).pack(side=tk.LEFT)
        if not heading and not block.get("p") and not formula and not table and not ref:
            tk.Frame(box, bg=PANEL, height=px(4)).pack()
        else:
            tk.Frame(box, bg=PANEL, height=px(6)).pack()

    def _piece_table(self, host, table: dict) -> None:
        grid = tk.Frame(host, bg=PANEL)
        grid.pack(fill=tk.X, padx=px(12), pady=(px(4), px(2)))
        head = table.get("head") or table.get("columns") or []
        for c, name in enumerate(head):
            L(grid, str(name), fg=MUTED, size=8, bold=True, bg=PANEL).grid(
                row=0, column=c, sticky="w", padx=(0, px(12)), pady=(0, px(2)))
        for r, row in enumerate(table.get("rows") or [], start=1):
            for c, cell in enumerate(row):
                L(grid, str(cell), fg=TEXT, size=9, mono=(c == 1), bg=PANEL).grid(
                    row=r, column=c, sticky="w", padx=(0, px(12)))
        note = table.get("note")
        if note:
            L(host, str(note), fg=MUTED, size=8, bg=PANEL, wraplength=px(540),
              justify="left", anchor="w").pack(fill=tk.X, padx=px(12), pady=(0, px(4)))

    def _open_table(self, table_id: str) -> None:
        loader = getattr(self.catalog, "load_table", None)
        if not callable(loader):
            return
        self._table_id = table_id
        self._cancel("lesson")
        for w in self._lesson_sf.inner.winfo_children():
            w.destroy()
        self._lesson_sf.top()
        try:
            table = loader(table_id)
        except Exception as exc:  # noqa: BLE001
            L(self._lesson_sf.inner, _t("Не удалось загрузить: {0}").format(exc),
              fg=AMBER, size=10, wraplength=px(560), justify="left").pack(
                anchor="w", padx=px(12), pady=px(12))
            return
        if not table:
            L(self._lesson_sf.inner, _t("Таблица не найдена"), fg=AMBER, size=10).pack(
                anchor="w", padx=px(12), pady=px(12))
            return
        host = self._lesson_sf.inner
        box = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        L(box, table.get("title") or table_id, fg=AMBER, size=14, bold=True, bg=PANEL).pack(
            anchor="w", padx=px(12), pady=(px(10), px(4)))
        self._piece_table(box, table)
        tk.Frame(box, bg=PANEL, height=px(8)).pack()
        foot = tk.Frame(host, bg=BG)
        foot.pack(fill=tk.X, padx=px(10), pady=(px(2), px(14)))
        HudButton(foot, "← " + _t("НАЗАД"), self._back_from_table, height=28,
                  font_size=8).pack(side=tk.LEFT)

    def _back_from_table(self) -> None:
        unit = self._unit
        self._unit = None
        self._data = None
        if unit is not None:
            self._open_unit(unit)

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
            primary = ex.get("en") or ex.get("de") or ex.get("primary") or ""
            secondary = ex.get("ru") or ex.get("secondary") or ex.get("en_tr") or ""
            if not secondary and ex.get("en") and ex.get("de"):
                secondary = ex.get("en")
                primary = ex.get("de")
            tk.Label(col, text=primary, fg=TEXT, bg=PANEL, font=theme.font(11),
                     justify="left", anchor="w", wraplength=px(500)).pack(anchor="w")
            if secondary and secondary != primary:
                L(col, secondary, fg=MUTED, size=9, bg=PANEL, wraplength=px(500),
                  justify="left", anchor="w").pack(anchor="w")
            speaker = getattr(self.ctx, "audio_button", None) if self.ctx is not None else None
            spoken = ex.get("speak") or (ex.get("de") if ex.get("de") else primary)
            if callable(speaker) and spoken:
                try:
                    speaker(row, "🔊", lambda s=spoken: s, height=22, font_size=8,
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
            if t.get("bad"):
                L(row, "✕ " + str(t.get("bad", "")), fg=RED, size=10, bg=PANEL, wraplength=px(520),
                  justify="left", anchor="w").pack(anchor="w")
            if t.get("good"):
                L(row, "✓ " + str(t.get("good", "")), fg=GREEN, size=10, bg=PANEL, wraplength=px(520),
                  justify="left", anchor="w").pack(anchor="w")
            if t.get("why"):
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
        custom = getattr(self.catalog, "render_exercise", None)
        if callable(custom):
            if custom(self, host, idx, ex):
                return
        card = tk.Frame(host, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), px(2)))
        L(top, f"{idx + 1}.", fg=AMBER, size=10, bold=True, mono=True, bg=PANEL, width=3).pack(
            side=tk.LEFT, anchor="n")
        q = ex.get("q") or ex.get("prompt") or ""
        tk.Label(top, text=q, fg=TEXT, bg=PANEL, font=theme.font(11),
                 justify="left", anchor="w", wraplength=px(520)).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        note = L(card, "", fg=MUTED, size=8, bg=PANEL, wraplength=px(540), justify="left", anchor="w")
        instruction = ex.get("instruction") or ""
        if instruction:
            L(card, instruction, fg=MUTED, size=8, bg=PANEL, wraplength=px(540),
              justify="left", anchor="w").pack(fill=tk.X, padx=px(14), pady=(0, px(2)))

        if ex.get("type") == "choice" or (ex.get("options") and ex.get("type") in {"choice", "identify", "match"}):
            options = list(ex.get("options") or [])
            try:
                right = self.catalog.choice_index(ex)
            except Exception:  # noqa: BLE001
                right = int(ex.get("a", 0) or 0)
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
                chips.append(parts)
            card._choice_chips = chips  # noqa: SLF001
            for i, parts in enumerate(chips):
                for w in parts:
                    w.bind("<Button-1>",
                           lambda _e, k=i, p=chips: self._answer_choice(idx, k, right, ex, p, note))
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
        if ex.get("hint_enabled"):
            hint_btn = HudButton(row, _t("ПОДСКАЗКА"), None, height=26, font_size=8, color=MUTED)
            hint_btn.pack(side=tk.LEFT, padx=(px(6), 0))

            def show_hint(_e=None, i=idx, n=note, item=ex) -> None:
                if i in self._answers:
                    return
                hint = item.get("hint") or ""
                maker = getattr(self.catalog, "hint_text", None)
                if callable(maker):
                    hint = maker(item)
                if hint:
                    try:
                        n.configure(text=hint, fg=MUTED)
                    except tk.TclError:
                        pass

            hint_btn.command = show_hint
        note.pack(fill=tk.X, padx=px(14), pady=(px(2), px(6)))
        card._gap_var = var  # noqa: SLF001
        card._gap_field = field  # noqa: SLF001
        card._gap_btn = btn  # noqa: SLF001
        self._exercise_vars = getattr(self, "_exercise_vars", {})
        self._exercise_vars[idx] = {"var": var, "field": field, "btn": btn, "note": note, "ex": ex, "card": card}

        def check(_e=None) -> None:
            if idx in self._answers:
                return
            ok = self.catalog.gap_ok(var.get(), ex)
            self._answer_gap(idx, ok, ex, field, btn, note, var)
            return "break"

        btn.command = check
        field.bind("<Return>", check)

    def _answer_choice(self, idx: int, picked: int, right: int, ex: dict, parts, note) -> None:
        if idx in self._answers:
            return
        ok = picked == right
        # parts may be only the clicked chip's tuple; re-find all chips from parent
        chips = parts
        if parts and hasattr(parts[0], "master"):
            parent = parts[0].master
            grouped = getattr(parent, "_choice_chips", None)
            if grouped:
                chips = grouped
        for i, (chip, body, num, txt) in enumerate(chips):
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
        variant_ok = bool(ok)
        try:
            field.configure(state="disabled", disabledforeground=GREEN if variant_ok else RED)
        except tk.TclError:
            return
        try:
            btn.set_enabled(False)
        except Exception:  # noqa: BLE001
            pass
        self._finish(idx, variant_ok, ex, note)

    def _finish(self, idx: int, ok: bool, ex: dict, note) -> None:
        if idx in self._answers:
            return
        self._answers[idx] = bool(ok)
        answers = []
        try:
            answers = list(self.catalog.lesson_answers(ex) or [])
        except Exception:  # noqa: BLE001
            answers = []
        text = ("✓ " + _t("ВЕРНО")) if ok else ("✕ " + _t("НЕВЕРНО") + " · " +
                                               _t("Ответ: {0}").format(", ".join(answers)))
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
        scored = getattr(self.catalog, "records_score", True)
        done = False
        if scored:
            try:
                done = bool(self.catalog.mark_complete(self._unit, ok, len(self._exercises)))
            except Exception:  # noqa: BLE001
                done = False
            self._update_counter()
            if self._unit in self._rows:
                self._paint_row(self._unit)
            self._rebuild_left_extra()
        box = getattr(self, "_banner_box", None)
        if box is not None and not box.winfo_manager():
            passed = True
            checker = getattr(self.catalog, "is_passing", None)
            if callable(checker):
                passed = bool(checker(ok, len(self._exercises)))
            else:
                passed = ok == len(self._exercises) or (len(self._exercises) and ok * 2 >= len(self._exercises))
            text = "{} · {}: {} / {}".format(_t("УРОК ПРОЙДЕН") if passed else _t("ЕЩЁ РАЗ"),
                                             _t("ВЕРНО"), ok, len(self._exercises))
            self._banner.configure(text=text, fg=GREEN if passed else AMBER)
            box.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        if done and self.ctx is not None:
            try:
                self.ctx.status("{}: {}".format(_t("УРОК ПРОЙДЕН"), (self._data or {}).get("title", "")), GREEN)
            except Exception:  # noqa: BLE001
                pass

    def _piece_foot(self, host, data: dict) -> None:
        box = tk.Frame(host, bg=BG)
        box.pack(fill=tk.X, padx=px(10), pady=(px(2), px(14)))
        row = tk.Frame(box, bg=BG)
        row.pack(fill=tk.X)
        prev_n, next_n = self.catalog.neighbours(data.get("n", self._unit))
        if prev_n is not None:
            HudButton(row, "← " + _t("НАЗАД"), lambda k=prev_n: self._open_unit(k), height=28,
                      font_size=8).pack(side=tk.LEFT)
        if next_n is not None:
            HudButton(row, _t("ДАЛЬШЕ") + " →", lambda k=next_n: self._open_unit(k), height=28,
                      font_size=8, color=GREEN).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(row, _t("Заново"), lambda: self._reopen_current(), height=28,
                  font_size=8, color=MUTED).pack(side=tk.RIGHT)

    def _reopen_current(self) -> None:
        unit = self._unit
        self._unit = None
        self._data = None
        if unit is not None:
            self._open_unit(unit)

    def _cancel(self, key: str) -> None:
        job = self._jobs.pop(key, None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:  # noqa: BLE001
                pass
