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
