"""Вкладка «Грамматика»: уровни A1–C2, порционная подгрузка тем."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from stamina.i18n import t as _t

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, MUTED, TEXT, px

from stamina.english.grammar import grammar_engine

LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")
LEVEL_TITLES = {
    "a1": "A1 (Elementary)",
    "a2": "A2 (Pre-intermediate)",
    "b1": "B1 (Intermediate)",
    "b2": "B2 (Upper-intermediate)",
    "c1": "C1 (Advanced)",
    "c2": "C2 (Proficiency)",
}
TOPIC_BATCH = 3  # сколько карточек тем рисуем за один тик Tk


def _engine():
  return grammar_engine


class GrammarPage(tk.Frame):
    """Страница грамматики: оболочка сразу, JSON и виджеты — порциями по выбору уровня."""

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self._level_key = "a1"
        self._load_token = 0
        self._topic_job: str | None = None
        self._level_buttons: dict[str, tk.Button] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = tk.Frame(self, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=px(12), pady=px(8))
        tk.Label(
            header,
            text=_t("ГРАММАТИКА АНГЛИЙСКОГО ЯЗЫКА"),
            fg=AMBER,
            bg=BG,
            font=theme.font(14, True),
        ).pack(side=tk.LEFT)
        tk.Label(header, text=_t("(A1–C2)"), fg=MUTED, bg=BG, font=theme.font(10)).pack(
            side=tk.LEFT, padx=px(6)
        )

        bar = tk.Frame(self, bg=BG)
        bar.grid(row=1, column=0, sticky="ew", padx=px(12), pady=px(4))
        for lk in LEVELS:
            btn = HudButton(
                bar,
                LEVEL_TITLES[lk],
                lambda k=lk: self._select_level(k),
                height=28,
                font_size=9,
            )
            btn.pack(side=tk.LEFT, padx=px(2))
            self._level_buttons[lk] = btn

        self._content = tk.Frame(self, bg=BG)
        self._content.grid(row=2, column=0, sticky="nsew", padx=px(12), pady=px(4))
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._status = tk.Label(self._content, text=_t("Выберите уровень."), fg=MUTED, bg=BG, font=theme.font(10))
        self._status.grid(row=0, column=0, sticky="nw")

        self._scroll_host: tk.Frame | None = None
        self._gen_host: tk.Frame | None = None

    def refresh(self) -> None:
        self._select_level(self._level_key)

    def _select_level(self, level_key: str) -> None:
        self._level_key = level_key
        for lk, btn in self._level_buttons.items():
            if hasattr(btn, "set_active"):
                btn.set_active(lk == level_key)
        self._cancel_topic_job()
        self._load_token += 1
        token = self._load_token
        self._clear_content()
        self._status = tk.Label(
            self._content, text=_t("Загрузка уровня {0}…").format(level_key.upper()), fg=CYAN, bg=BG, font=theme.font(10)
        )
        self._status.grid(row=0, column=0, sticky="nw")

        def worker() -> None:
            try:
                data = _engine().load_grammar(level_key)
                err = None
            except Exception as exc:  # noqa: BLE001
                data, err = None, exc
            self.after(0, lambda: self._on_level_loaded(token, level_key, data, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_level_loaded(self, token: int, level_key: str, data, err) -> None:
        if token != self._load_token:
            return
        self._clear_content()
        if err is not None:
            tk.Label(
                self._content,
                text=_t("Не удалось загрузить: {0}").format(err),
                fg=AMBER,
                bg=BG,
                font=theme.font(10),
                wraplength=px(520),
                justify="left",
            ).grid(row=0, column=0, sticky="nw")
            return
        tk.Label(
            self._content,
            text=LEVEL_TITLES.get(level_key, level_key.upper()),
            fg=AMBER,
            bg=BG,
            font=theme.font(12, True),
        ).grid(row=0, column=0, sticky="nw", pady=(0, px(6)))

        canvas = tk.Canvas(self._content, bg=BG, highlightthickness=0)
        canvas.grid(row=1, column=0, sticky="nsew")
        vsb = tk.Scrollbar(self._content, orient="vertical", command=canvas.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)
        self._content.grid_rowconfigure(1, weight=1)

        inner = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.grid_columnconfigure(0, weight=1)

        def _resize(_e=None):
            canvas.itemconfigure(win, width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", _resize)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        topics = list((data or {}).get("topics") or [])
        self._scroll_host = inner
        self._append_topics_batch(topics, 0, token, level_key)

        gen = tk.LabelFrame(self._content, text=_t("Генерировать упражнение"), bg=BG, fg=AMBER)
        gen.grid(row=2, column=0, sticky="ew", pady=px(8))
        self._gen_host = gen
        self._build_generator(gen, level_key, topics)

    def _append_topics_batch(self, topics: list, start: int, token: int, level_key: str) -> None:
        if token != self._load_token or self._scroll_host is None:
            return
        end = min(start + TOPIC_BATCH, len(topics))
        for i in range(start, end):
            t = topics[i]
            row = i * 3
            tk.Label(
                self._scroll_host,
                text=t.get("name", ""),
                fg=TEXT,
                bg=BG,
                font=theme.font(10, True),
                anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=px(4), pady=(px(6), 0))
            summary = t.get("focus") or ""
            if summary:
                tk.Label(
                    self._scroll_host,
                    text=summary,
                    fg=MUTED,
                    bg=BG,
                    font=theme.font(9),
                    wraplength=px(480),
                    justify="left",
                    anchor="w",
                ).grid(row=row + 1, column=0, sticky="ew", padx=px(8), pady=(0, px(2)))
            n_ex = t.get("total_exercises", 0)
            tk.Label(
                self._scroll_host,
                text=_t("Упражнений: {0}").format(n_ex),
                fg=MUTED,
                bg=BG,
                font=theme.font(8),
                anchor="w",
            ).grid(row=row + 2, column=0, sticky="w", padx=px(8), pady=(0, px(4)))

        if end < len(topics):
            self._topic_job = self.after(1, lambda: self._append_topics_batch(topics, end, token, level_key))
        else:
            self._topic_job = None

    def _build_generator(self, host: tk.Frame, level_key: str, topics: list) -> None:
        level_var = tk.StringVar(value=level_key)
        names = [t.get("name", "") for t in topics if t.get("name")]
        topic_var = tk.StringVar(value=names[0] if names else "")

        tk.Label(host, text=_t("Уровень:"), bg=BG, fg=TEXT, font=theme.font(9)).grid(row=0, column=0, padx=px(4), pady=px(2))
        ttk.Combobox(
            host,
            textvariable=level_var,
            values=list(LEVELS),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, padx=px(4), pady=px(2))

        tk.Label(host, text=_t("Тема:"), bg=BG, fg=TEXT, font=theme.font(9)).grid(row=1, column=0, padx=px(4), pady=px(2))
        ttk.Combobox(host, textvariable=topic_var, values=names, state="readonly", width=28).grid(
            row=1, column=1, padx=px(4), pady=px(2)
        )

        result = tk.Label(host, text="", bg=BG, fg=CYAN, font=theme.font(9, True), wraplength=px(400), justify="left")

        def _gen() -> None:
            try:
                ex = _engine().generate_exercise(level_var.get(), topic_var.get() or None)
                result.config(
                    text=_t("Уровень: {0}, тема: {1}, тип: {2}, всего: {3}").format(
                        ex["level"], ex["topic"], ex["type"], ex["exercise_count"]
                    ),
                    fg=CYAN,
                )
            except Exception as exc:  # noqa: BLE001
                result.config(text=_t("Ошибка: {0}").format(exc), fg=AMBER)

        tk.Button(host, text=_t("Сгенерировать"), bg=BG, fg=AMBER, command=_gen, font=theme.font(9)).grid(
            row=2, column=0, columnspan=2, pady=px(4), sticky="w"
        )
        result.grid(row=3, column=0, columnspan=2, sticky="w")

    def _clear_content(self) -> None:
        self._cancel_topic_job()
        for w in self._content.winfo_children():
            w.destroy()
        self._scroll_host = None
        self._gen_host = None

    def _cancel_topic_job(self) -> None:
        if self._topic_job is not None:
            try:
                self.after_cancel(self._topic_job)
            except Exception:  # noqa: BLE001
                pass
            self._topic_job = None


def init_grammar_tab(english_screen) -> None:
    """Устарело: грамматика собирается в EnglishScreen._build как GrammarPage."""
