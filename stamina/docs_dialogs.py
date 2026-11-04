"""Окна отсека «Документы» в стиле пульта (общий pilot_screens.Modal).

Вместо системных messagebox — свои окна: цвета и шрифты темы, любой скин.
Каждое окно возвращает result через run(); в тестах run() подменяют.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.pilot_screens import Modal
from stamina.theme import px


class ConfirmDialog(Modal):
    """Да/нет: result = True или None. danger — красная кнопка подтверждения."""

    def __init__(self, master, title: str, message: str, ok: str, *, danger: bool = False,
                 cancel: str | None = None) -> None:
        accent = theme.RED if danger else theme.AMBER
        super().__init__(master, title, accent=accent)
        tk.Label(self.body, text=message, bg=theme.PANEL, fg=theme.TEXT, font=theme.font(10),
                 justify="left", anchor="w", wraplength=px(420)).pack(fill=tk.X)
        row = tk.Frame(self.body, bg=theme.PANEL)
        row.pack(fill=tk.X, pady=(px(12), 0))
        self.ok_btn = HudButton(row, ok, self.ok, color=accent, height=34, font_size=9)
        self.ok_btn.pack(side=tk.LEFT)
        HudButton(row, cancel or _t("ОТМЕНА"), self.cancel, height=34, font_size=9,
                  color=theme.MUTED).pack(side=tk.LEFT, padx=px(6))
        self.bind("<Return>", lambda _e: self.ok())

    def ok(self) -> None:
        self.result = True
        self.destroy()


def confirm(master, title: str, message: str, ok: str, *, danger: bool = False) -> bool:
    return bool(ConfirmDialog(master, title, message, ok, danger=danger).run())


class PickDialog(Modal):
    """Список и кнопки действий (корзина, версии): result = (ключ действия, значение строки)."""

    def __init__(self, master, title: str, hint: str, rows: list[tuple[str, object]],
                 actions: list[tuple[str, str, object]], empty: str) -> None:
        super().__init__(master, title, accent=theme.CYAN)
        tk.Label(self.body, text=hint, bg=theme.PANEL, fg=theme.MUTED, font=theme.font(9),
                 justify="left", anchor="w", wraplength=px(440)).pack(fill=tk.X, pady=(0, px(6)))
        self.values = [v for _l, v in rows]
        lb = self.listbox = tk.Listbox(self.body, width=52, height=min(12, max(4, len(rows))),
                                       bg=theme.BG2, fg=theme.TEXT, relief=tk.FLAT, bd=0,
                                       highlightthickness=1, highlightbackground=theme.LINE,
                                       selectbackground=theme.blend(theme.CYAN, theme.BG2, 0.55),
                                       selectforeground=theme.TEXT, activestyle="none",
                                       font=theme.font(10), exportselection=False)
        for label, _v in rows:
            lb.insert(tk.END, " " + label)
        if not rows:
            lb.insert(tk.END, " " + empty)
            lb.configure(fg=theme.MUTED)
        else:
            lb.selection_set(0)
        lb.pack(fill=tk.BOTH, expand=True)
        row = tk.Frame(self.body, bg=theme.PANEL)
        row.pack(fill=tk.X, pady=(px(10), 0))
        for label, key, color in actions:
            b = HudButton(row, label, lambda k=key: self.choose(k), color=color, height=32, font_size=9)
            b.pack(side=tk.LEFT, padx=(0, px(6)))
            b.set_enabled(bool(rows))
        HudButton(row, _t("ЗАКРЫТЬ"), self.cancel, height=32, font_size=9,
                  color=theme.MUTED).pack(side=tk.RIGHT)
        if rows and actions:
            lb.bind("<Double-Button-1>", lambda _e: self.choose(actions[0][1]))
            self.bind("<Return>", lambda _e: self.choose(actions[0][1]))

    def choose(self, key: str) -> None:
        sel = self.listbox.curselection()
        if not sel or not self.values:
            return
        self.result = (key, self.values[sel[0]])
        self.destroy()


def pick(master, title, hint, rows, actions, empty):
    return PickDialog(master, title, hint, rows, actions, empty).run()
