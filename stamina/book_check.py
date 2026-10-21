"""Проверка книги у Ориона: режем текст на куски, спрашиваем агента, показываем правки.

Корабль не переписывает книгу сам: агент ищет только склейки слов и явные опечатки
внутри них, возвращает пары «было → стало», а пилот галочками выбирает, что применить.
"""
from __future__ import annotations

import threading
import tkinter as tk

from stamina import orion, theme
from stamina.adapt import make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import BG, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT, px


def split_chunks(text: str, size: int = orion.CHECK_CHUNK) -> list[str]:
    """Резать текст на куски по `size` символов, не разрывая строку посреди слова.

    Длинная строка без переводов режется принудительно — иначе кусок не пролезет.
    """
    size = max(500, int(size or orion.CHECK_CHUNK))
    out: list[str] = []
    buf = ""
    for para in (text or "").splitlines(keepends=True):
        while len(para) > size:
            if buf:
                out.append(buf)
                buf = ""
            out.append(para[:size])
            para = para[size:]
        if len(buf) + len(para) > size:
            out.append(buf)
            buf = ""
        buf += para
    if buf.strip():
        out.append(buf)
    return [c for c in out if c.strip()]


def collect(replies: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    """Свести ответы по кускам в один список без повторов (первое вхождение важнее)."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for fixes in replies:
        for bad, good in fixes or ():
            key = bad.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((bad, good))
    return out


def run_check(text: str, ask, chunks: list[str] | None = None, progress=None):
    """Спросить агента по каждому куску. `ask(prompt) -> reply`, возвращает правки."""
    parts = split_chunks(text) if chunks is None else list(chunks)
    replies = []
    for i, part in enumerate(parts, 1):
        if progress is not None:
            progress(i, len(parts))
        replies.append(orion.parse_fixes(ask(orion.check_prompt(part))))
    return collect(replies)


class FixesWindow(tk.Toplevel):
    """Окно правок: список «было → стало» с галочками, применить выбранное."""

    def __init__(self, app, fixes: list[tuple[str, str]], on_apply) -> None:
        super().__init__(app)
        self.app = app
        self.on_apply = on_apply
        self.vars: list[tk.BooleanVar] = []
        self.fixes = list(fixes or [])
        self.title(_t("ПРОВЕРКА КНИГИ"))
        self.configure(bg=BG)
        self.transient(app)
        try:
            self.geometry(f"{px(760)}x{px(560)}")
        except tk.TclError:
            pass

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=px(12), pady=(px(10), 0))
        tk.Label(head, text=_t("ПРОВЕРКА КНИГИ"), bg=BG, fg=CYAN,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        tk.Label(head, text=_t("Найдено правок: {0}").format(len(self.fixes)), bg=BG,
                 fg=MUTED, font=theme.font(9)).pack(side=tk.RIGHT)

        panel = HudPanel(self, title=_t("БЫЛО → СТАЛО"))
        panel.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(px(6), 0))
        body = tk.Frame(panel.body, bg=PANEL)
        body.pack(fill=tk.BOTH, expand=True)
        sb = make_vscroll(body)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cv = tk.Canvas(body, bg=PANEL, highlightthickness=0, yscrollcommand=sb.set)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.configure(command=self.cv.yview)
        inner = tk.Frame(self.cv, bg=PANEL)
        self.cv.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>",
                   lambda _e: self.cv.configure(scrollregion=self.cv.bbox("all")))

        if not self.fixes:
            tk.Label(inner, text=_t("Правок не найдено — текст чистый"), bg=PANEL, fg=GREEN,
                     font=theme.font(10), anchor="w").pack(fill=tk.X, padx=px(6), pady=px(8))
        for bad, good in self.fixes:
            row = tk.Frame(inner, bg=PANEL)
            row.pack(fill=tk.X, padx=px(4), pady=px(2))
            var = tk.BooleanVar(value=True)
            self.vars.append(var)
            tk.Checkbutton(row, variable=var, bg=PANEL, activebackground=PANEL,
                           selectcolor=BG, highlightthickness=0, bd=0).pack(side=tk.LEFT)
            tk.Label(row, text=bad, bg=PANEL, fg=RED, font=theme.font(10, mono=True),
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=" → ", bg=PANEL, fg=MUTED, font=theme.font(10)).pack(side=tk.LEFT)
            tk.Label(row, text=good, bg=PANEL, fg=GREEN, font=theme.font(10, mono=True),
                     anchor="w").pack(side=tk.LEFT)

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill=tk.X, padx=px(12), pady=px(10))
        HudButton(foot, _t("ПРИМЕНИТЬ ВЫБРАННОЕ"), self._apply, color=GREEN,
                  height=36, font_size=10).pack(side=tk.LEFT)
        HudButton(foot, _t("ВЫБРАТЬ ВСЁ"), self._all, color=CYAN,
                  height=36, font_size=9).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(foot, _t("СНЯТЬ ВСЁ"), self._none, color=MUTED,
                  height=36, font_size=9).pack(side=tk.LEFT, padx=(px(6), 0))
        HudButton(foot, _t("ОТМЕНА"), self.destroy, color=MUTED,
                  height=36, font_size=9).pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _e: self.destroy())
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _all(self) -> None:
        for v in self.vars:
            v.set(True)

    def _none(self) -> None:
        for v in self.vars:
            v.set(False)

    def selected(self) -> list[tuple[str, str]]:
        return [f for f, v in zip(self.fixes, self.vars) if v.get()]

    def _apply(self) -> None:
        chosen = self.selected()
        self.destroy()
        if chosen and self.on_apply:
            self.on_apply(chosen)


def ask_agent(rec: dict, prompt: str) -> str:
    """Один вопрос агенту (профиль доклада): так проверка не меняет файлы."""
    res = orion.run_profile(rec, prompt, profile="orion-recon")
    if res.error or not res.reply:
        return ""
    return res.reply


def check_in_background(app, text: str, rec: dict, on_done, on_progress=None,
                        ask=None) -> threading.Thread:
    """Проверить книгу в фоне и вернуть правки в главный поток через `app.after`."""

    def work() -> None:
        found = []
        try:
            found = run_check(text, ask or (lambda p: ask_agent(rec, p)),
                              progress=lambda i, n: app.after(0, lambda: on_progress(i, n)
                                                              if on_progress else None))
        except Exception:  # noqa: BLE001
            found = []
        app.after(0, lambda: on_done(found))

    thread = threading.Thread(target=work, daemon=True, name="book-check")
    thread.start()
    return thread
