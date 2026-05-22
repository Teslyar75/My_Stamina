"""Виртуальная клавиатура — сетка 30×5, как в ``MainWindow.xaml``."""

from __future__ import annotations

import tkinter as tk

from stamina.keyboard_layout import GRID_COLUMNS, KEYBOARD_ROWS
from stamina.theme import (
    HIGHLIGHT,
    KEY_PADX,
    KEY_PADY,
    KEYBOARD_ROW_HEIGHT,
    WINDOW_BG,
)
from stamina.widgets import RoundedKey


class VirtualKeyboard(tk.Frame):
    """Сетка из 60 скруглённых клавиш с подсветкой текущей."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=WINDOW_BG, **kwargs)
        self._keys: dict[str, list[RoundedKey]] = {}
        self._default_colors: dict[str, str] = {}
        self._highlighted: str | None = None
        self._build()

    # -- Построение --------------------------------------------------

    def _build(self) -> None:
        # weight=1 + uniform="cols" — Tk гарантированно делает 30 равных колонок.
        for col in range(GRID_COLUMNS):
            self.grid_columnconfigure(col, weight=1, uniform="kbcols", minsize=20)

        for row_idx, row in enumerate(KEYBOARD_ROWS):
            self.grid_rowconfigure(
                row_idx,
                weight=1,
                uniform="kbrows",
                minsize=KEYBOARD_ROW_HEIGHT,
            )
            for label, col, colspan, color in row:
                key_id = self._key_id(label)
                key = RoundedKey(self, label, color, width=10, height=20)
                key.grid(
                    row=row_idx,
                    column=col,
                    columnspan=colspan,
                    sticky="nsew",
                    padx=KEY_PADX,
                    pady=KEY_PADY,
                )
                self._keys.setdefault(key_id, []).append(key)
                self._default_colors.setdefault(key_id, color)

    # -- Подсветка ---------------------------------------------------

    @staticmethod
    def _key_id(label: str) -> str:
        if label == "Space":
            return "space"
        if len(label) == 1 and label.isalpha():
            return label.upper()
        return label

    @staticmethod
    def _lookup_char(char: str) -> str:
        if char == " ":
            return "space"
        if len(char) == 1 and char.isalpha():
            return char.upper()
        return char

    def highlight(self, char: str | None) -> None:
        """Подсветить клавишу красным (как ``Brushes.Red`` в C#)."""
        new_id = self._lookup_char(char) if char else None
        if new_id == self._highlighted:
            return

        if self._highlighted is not None:
            color = self._default_colors.get(self._highlighted)
            if color is not None:
                for widget in self._keys.get(self._highlighted, []):
                    widget.set_color(color)

        if new_id is not None and new_id in self._keys:
            for widget in self._keys[new_id]:
                widget.set_color(HIGHLIGHT)
            self._highlighted = new_id
        else:
            self._highlighted = None
