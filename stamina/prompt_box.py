"""Пульт набора: поле сообщения с несколькими строками, прокруткой и подсказками.

Заменяет однострочный `tk.Entry` в чате ОРИОНА и в ЭФИРЕ: у Entry нет переноса и
прокрутки, поэтому последняя набранная буква уезжала за край, а длинный черновик
было не видно.

Что умеет:

* 3 строки по умолчанию, растёт до `max_rows` по мере набора, вертикальная прокрутка;
* курсор всегда на виду (`see(INSERT)`) — буква больше не прячется за краем;
* `Enter` — отправить, `Shift+Enter` — новое строке;
* подсказки (`stamina/suggest.py`): `Tab` принимает, второй `Tab` — следующая,
  `↑`/`↓` — выбор, `Esc` — отказ. Вне пульта `Tab` по-прежнему переключает
  элементы корабля;
* `on_draft` — сообщает экрану о черновике (для «ОРИОН ВИДИТ ЧЕРНОВИК»).

Кнопок и логики отправки здесь нет: пульт только набирает текст и зовёт `on_send`.
"""

from __future__ import annotations

import tkinter as tk

from stamina.adapt import make_vscroll
from stamina.i18n import t as _t
from stamina.suggest import Suggester
from stamina.theme import px

DEFAULT_ROWS = 3
DEFAULT_MAX_ROWS = 8

SHIFT = 0x0001          # модификатор Shift в event.state
CTRL = 0x0004           # модификатор Ctrl в event.state


def hud_colors() -> dict:
    """Палитра пульта в цветах скина — одна на чат ОРИОНА и ЭФИР."""
    from stamina.theme import BG, BG2, CYAN, LINE, MUTED, TEXT
    return {"bg": BG2, "fg": TEXT, "line": LINE, "accent": CYAN, "hint": MUTED,
            "ghost": MUTED, "insert": CYAN, "sel_bg": CYAN, "sel_fg": BG}


class PromptBox(tk.Frame):
    """Многострочное поле набора с подсказками. API похож на Entry: get/set/clear."""

    def __init__(self, master, *, on_send, colors: dict, font=None,
                 rows: int = DEFAULT_ROWS, max_rows: int = DEFAULT_MAX_ROWS,
                 suggester: Suggester | None = None, on_draft=None,
                 draft_delay: float = 1.2) -> None:
        bg = colors.get("bg", "#101418")
        super().__init__(master, bg=bg, highlightthickness=1,
                         highlightbackground=colors.get("line", bg),
                         highlightcolor=colors.get("accent", colors.get("line", bg)))
        self._on_send = on_send
        self._on_draft = on_draft
        self._draft_delay = draft_delay
        self._suggester = suggester
        self._colors = dict(colors)
        self._rows = max(1, int(rows))
        self._max_rows = max(self._rows, int(max_rows))
        self._draft_job = None
        self._cycle: dict | None = None      # приём подсказки: префикс, список, номер
        self._ghost = ""                     # призрак подсказки в строке (как в Cursor)
        self._enabled = True
        self._ctrl_enter = False             # режим программиста: Ctrl+Enter отправляет
        self._history: list[str] = []        # что уже отправляли — по стрелке вверх
        self._hist_pos = 0
        self._browsing = False

        self.text = tk.Text(self, height=self._rows, wrap="word", undo=True,
                            relief=tk.FLAT, bd=0, padx=px(8), pady=px(6),
                            bg=bg, fg=colors.get("fg", "#E6E6E6"),
                            insertbackground=colors.get("insert", colors.get("fg", "#E6E6E6")),
                            selectbackground=colors.get("sel_bg", bg),
                            selectforeground=colors.get("sel_fg", colors.get("fg", "#FFFFFF")),
                            highlightthickness=0)
        if font is not None:
            self.text.configure(font=font)
        # призрак подсказки: серый хвост сразу за курсором, принимается по Tab
        self.text.tag_configure("ghost",
                                foreground=colors.get("ghost",
                                                      colors.get("hint", colors.get("fg"))))
        self.bar = make_vscroll(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self._on_scroll)
        self.hint = tk.Label(self, text="", anchor="w", justify="left",
                             bg=bg, fg=colors.get("hint", colors.get("fg", "#888888")),
                             font=font)
        self.bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hint.pack(side=tk.BOTTOM, fill=tk.X, padx=px(8))
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.text.bind("<Return>", self._on_return, add="+")
        self.text.bind("<KP_Enter>", self._on_return, add="+")
        self.text.bind("<Tab>", self._on_tab, add="+")
        self.text.bind("<ISO_Left_Tab>", self._on_tab, add="+")
        self.text.bind("<Down>", lambda e: self._on_arrow(1), add="+")
        self.text.bind("<Up>", lambda e: self._on_arrow(-1), add="+")
        self.text.bind("<Escape>", self._on_escape, add="+")
        self.text.bind("<KeyPress>", self._on_keypress, add="+")
        self.text.bind("<KeyRelease>", self._after_change, add="+")
        self.text.bind("<<Paste>>", self._after_change, add="+")
        self.text.bind("<<Cut>>", self._after_change, add="+")
        self.text.bind("<ButtonRelease-1>", self._after_change, add="+")

    # -- содержимое --------------------------------------------------------
    def get(self) -> str:
        """Текст пульта как есть (переводы строк сохранены; призрак не в счёт)."""
        text = self.text.get("1.0", "end-1c")
        if self._ghost:
            idx = self._cursor()
            return text[:idx] + text[idx + len(self._ghost):]
        return text

    def set(self, text: str) -> None:
        self.clear()
        if text:
            self.text.insert("1.0", text)
        self._after_change()

    def clear(self) -> None:
        self.text.delete("1.0", tk.END)
        self._after_change()

    def insert_text(self, text: str) -> None:
        """Текст из микрофона: добавить к набранному и показать курсор."""
        if not text:
            return
        self._drop_ghost()
        tail = self.get()
        self.text.insert(tk.INSERT, (" " if tail and not tail.endswith((" ", "\n")) else "") + text)
        self.text.focus_set()
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.see(tk.INSERT)
        self._after_change()

    def paste(self, text: str) -> None:
        """Вставка из буфера — как есть, без лишнего пробела."""
        if not text:
            return
        self._drop_ghost()
        self.text.insert(tk.INSERT, text)
        self.text.focus_set()
        self._after_change()

    def selected(self) -> str:
        """Выделенный кусок текста (пустая строка, если выделения нет)."""
        try:
            return self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return ""

    # -- совместимость с tk.Entry (старый код зовёт поле так же) ------------
    def insert(self, index=tk.INSERT, text: str = "") -> None:
        """Как у Entry: `insert(0, «текст»)` — в начало, `insert(tk.INSERT, …)` — по курсору."""
        self._drop_ghost()
        if index in (tk.INSERT, "insert"):
            where = tk.INSERT
        elif index in (tk.END, "end"):
            where = tk.END
        else:
            where = "1.0"
        self.text.insert(where, text)
        if where != tk.INSERT:
            self.text.mark_set(tk.INSERT, tk.END)
        self._after_change()

    def delete(self, first=tk.INSERT, last=None) -> None:
        """Как у Entry: `delete(0, tk.END)` — очистить поле."""
        if last in (tk.END, "end"):
            self.clear()
            return
        self._drop_ghost()
        self.text.delete(first, last if last is not None else f"{first}+1c")
        self._after_change()

    def cget(self, key: str):
        if key == "state":
            return self.state()
        raise tk.TclError(f"unknown option {key}")

    def focus_set(self) -> None:  # noqa: N802 — как у tk-виджетов
        self.text.focus_set()

    def state(self) -> str:
        return "normal" if self._enabled else "disabled"

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)
        if not self._enabled:
            self._render_ghost("")
        self.text.configure(state=tk.NORMAL if self._enabled else tk.DISABLED)
        if self._enabled:
            self.text.focus_set()

    def bind_text(self, sequence: str, func) -> None:
        """Повесить обработчик на само поле (Ctrl+V, правая кнопка мыши)."""
        self.text.bind(sequence, func, add="+")

    def set_ctrl_enter(self, on: bool) -> None:
        """Режим программиста: `Ctrl+Enter` отправляет, `Enter` — новая строка."""
        self._ctrl_enter = bool(on)

    def set_history(self, items) -> None:
        """Что пилот уже отправлял: `↑` возвращает прежние сообщения."""
        self._history = [str(i) for i in (items or []) if str(i).strip()]
        self._hist_pos = len(self._history)
        self._browsing = False

    def destroy(self) -> None:
        """Снять отложенный показ черновика: иначе `after` стреляет в мёртвый виджет."""
        if self._draft_job is not None:
            try:
                self.after_cancel(self._draft_job)
            except tk.TclError:
                pass
            self._draft_job = None
        super().destroy()

    # -- события -----------------------------------------------------------
    def _on_return(self, event) -> str:
        state = getattr(event, "state", 0)
        if self._ctrl_enter:                       # ремонтный отсек: Enter — новая строка
            if state & CTRL:
                self._on_send()
                return "break"
            self.text.insert(tk.INSERT, "\n")
            self._after_change()
            return "break"
        if state & SHIFT:      # Shift+Enter — новая строка
            self.text.insert(tk.INSERT, "\n")
            self._after_change()
            return "break"
        self._on_send()
        return "break"

    def _on_tab(self, _event=None):
        """Tab принимает подсказку; если подсказок нет — обычная навигация корабля."""
        return "break" if self.accept_hint() else None

    def _on_arrow(self, delta: int):
        if self._cycle and self._cycle["hints"]:
            self._cycle["index"] = (self._cycle["index"] + delta) % len(self._cycle["hints"])
            self._apply_cycle()
            return "break"
        if self._history_allowed(delta) and self._history_step(delta):
            return "break"
        return None

    def _history_allowed(self, delta: int) -> bool:
        """История — только там, где стрелка не двигает курсор внутри набранного."""
        if not self._history:
            return False
        if self._browsing:
            return True
        if delta < 0:
            return self.text.index(tk.INSERT).startswith("1.")
        return False

    def _history_step(self, delta: int) -> bool:
        if not self._history_allowed(delta):
            return False
        self._browsing = True
        self._hist_pos = max(0, min(len(self._history), self._hist_pos + delta))
        text = "" if self._hist_pos >= len(self._history) else self._history[self._hist_pos]
        self._drop_ghost()
        self.text.delete("1.0", tk.END)
        if text:
            self.text.insert("1.0", text)
        self.text.mark_set(tk.INSERT, tk.END)
        self._after_change()
        return True

    def _on_escape(self, _event=None):
        if self._cycle or self._ghost or self.hint.cget("text"):
            self._reset_cycle()
            self._render_ghost("")
            self.hint.configure(text="")
            return "break"
        return None

    def _on_keypress(self, _event=None):
        """Перед вставкой символа убрать призрак: иначе буква встанет посреди него."""
        self._drop_ghost()
        self._browsing = False
        return None

    def _on_scroll(self, first, last) -> None:
        self.bar.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(side=tk.RIGHT, fill=tk.Y, before=self.text)

    def _after_change(self, _event=None) -> None:
        self._drop_ghost()
        self.text.see(tk.INSERT)
        self._fit_rows()
        self._refresh_hints()
        self._queue_draft()

    # -- высота ------------------------------------------------------------
    def _fit_rows(self) -> None:
        lines = self._display_lines()
        rows = max(self._rows, min(self._max_rows, lines + 1))
        if rows != int(self.text.cget("height")):
            self.text.configure(height=rows)

    def _display_lines(self) -> int:
        """Сколько строк текст занимает на экране (с учётом переноса)."""
        try:
            got = self.text.count("1.0", "end-1c", "displaylines")
        except tk.TclError:
            got = None
        if isinstance(got, int):
            return got
        try:
            return int(got[0])
        except (TypeError, IndexError, ValueError):
            return int(self.text.index("end-1c").split(".")[0])

    # -- призрак подсказки (как в Cursor: серый хвост за курсором) ----------
    def ghost(self) -> str:
        """Что сейчас показано призраком (пустая строка — ничего)."""
        return self._ghost

    def _drop_ghost(self) -> None:
        if not self._ghost:
            return
        tail, self._ghost = self._ghost, ""
        try:
            self.text.delete(tk.INSERT, f"{tk.INSERT}+{len(tail)}c")
        except tk.TclError:
            pass

    def _render_ghost(self, tail: str) -> None:
        self._drop_ghost()
        if not tail or not self._enabled:
            return
        pos = self.text.index(tk.INSERT)
        try:
            self.text.insert(tk.INSERT, tail, "ghost")
        except tk.TclError:
            return
        self.text.mark_set(tk.INSERT, pos)      # курсор остаётся перед призраком
        self._ghost = tail

    # -- подсказки ---------------------------------------------------------
    def set_suggester(self, suggester: Suggester | None) -> None:
        self._suggester = suggester
        self._refresh_hints()

    def hints(self):
        """Подсказки для текста до курсора (готовый список `Suggestion`)."""
        if self._suggester is None or not self._enabled:
            return []
        try:
            cursor = len(self.text.get("1.0", tk.INSERT))
        except tk.TclError:
            cursor = None
        return self._suggester.suggestions(self.get(), cursor)

    def accept_hint(self) -> bool:
        """Принять подсказку (Tab): призрак становится текстом, второй Tab — следующий."""
        self._drop_ghost()
        if self._cycle is not None and self._cycle["hints"]:
            self._cycle["index"] = (self._cycle["index"] + 1) % len(self._cycle["hints"])
            self._apply_cycle()
            return True
        items = self.hints()
        if not items:
            return False
        prefix = self.get()[:self._cursor()]
        self._cycle = {"prefix": prefix, "hints": items, "index": 0, "tail": ""}
        self._apply_cycle()
        return True

    def _apply_cycle(self) -> None:
        cycle = self._cycle
        if not cycle:
            return
        item = cycle["hints"][cycle["index"]]
        self.text.delete(f"1.0+{len(cycle['prefix'])}c", tk.INSERT)
        self.text.insert(tk.INSERT, item.tail)
        cycle["tail"] = item.tail
        self.text.see(tk.INSERT)
        self._fit_rows()
        label = _t("Tab: {0}").format(item.label)
        if len(cycle["hints"]) > 1:
            label += " · " + _t("ещё {0}").format(len(cycle["hints"]) - 1)
            label += " · " + _t("↑↓ выбор")
        self.hint.configure(text=label)
        self._queue_draft()

    def _refresh_hints(self) -> None:
        """Показ подсказки: пилот набрал слово — видно, чем его можно закончить."""
        if self._cycle is not None:
            # после приёма подсказки ждём: пока текст не меняли, список «заморожен»
            head = self.get()[:self._cursor()]
            if head == self._cycle["prefix"] + self._cycle["tail"]:
                return
            self._reset_cycle()
        items = self.hints()
        if not items:
            self._render_ghost("")
            self.hint.configure(text="")
            return
        label = _t("Tab: {0}").format(items[0].label)
        if len(items) > 1:
            label += " · " + _t("ещё {0}").format(len(items) - 1) + " · " + _t("↑↓ выбор")
        self.hint.configure(text=label)
        self._render_ghost(items[0].tail)

    def _reset_cycle(self) -> None:
        self._cycle = None

    def _cursor(self) -> int:
        try:
            return len(self.text.get("1.0", tk.INSERT))
        except tk.TclError:
            return 0

    # -- черновик ----------------------------------------------------------
    def draft(self) -> str:
        return self.get().strip()

    def _queue_draft(self) -> None:
        if self._on_draft is None:
            return
        if self._draft_job is not None:
            try:
                self.after_cancel(self._draft_job)
            except tk.TclError:
                pass
        self._draft_job = self.after(int(self._draft_delay * 1000), self._fire_draft)

    def _fire_draft(self) -> None:
        self._draft_job = None
        if self._on_draft is None:
            return
        text = self.draft()
        if text:
            self._on_draft(text)
