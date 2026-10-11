"""Змейка — навигационный шнур по сетке отсека."""
from __future__ import annotations

from stamina.i18n import t as _t

import random
import tkinter as tk

from stamina import theme
from stamina.theme import AMBER, BG2, CYAN, GREEN, LINE, PANEL, RED, TEXT, blend, px

from .base import GameShell

GRID = 20


class SnakeGame(GameShell):
    game_id = "snake"
    title = _t("ЗМЕЙКА · НАВИГАЦИОННЫЙ ШНУР")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.set_hint(_t("← ↑ → ↓ или WASD · Esc пауза · R заново"))
        self.reset()

    def tick_ms(self) -> int:
        return max(70, 160 - self.score // 5)

    def reset(self) -> None:
        mid = GRID // 2
        self.snake = [(mid, mid), (mid - 1, mid), (mid - 2, mid)]
        self.dir = (1, 0)
        self.next_dir = (1, 0)
        self.food = self._place_food()
        self.grow = 0

    def _place_food(self):
        free = {(x, y) for x in range(GRID) for y in range(GRID)} - set(self.snake)
        return random.choice(list(free)) if free else (0, 0)

    def tick(self) -> None:
        self.dir = self.next_dir
        hx, hy = self.snake[0]
        nx, ny = hx + self.dir[0], hy + self.dir[1]
        if not (0 <= nx < GRID and 0 <= ny < GRID) or (nx, ny) in self.snake:
            self.game_over()
            return
        self.snake.insert(0, (nx, ny))
        if (nx, ny) == self.food:
            self.add_score(10)
            self.grow += 1
            self.food = self._place_food()
        if self.grow > 0:
            self.grow -= 1
        else:
            self.snake.pop()

    def on_key(self, e: tk.Event) -> None:
        super().on_key(e)
        if self.paused or self.over:
            return
        k = e.keysym.lower()
        mapping = {
            "left": (-1, 0), "a": (-1, 0),
            "right": (1, 0), "d": (1, 0),
            "up": (0, -1), "w": (0, -1),
            "down": (0, 1), "s": (0, 1),
        }
        if k not in mapping:
            return
        nd = mapping[k]
        # нельзя развернуться в себя
        if (nd[0] + self.dir[0], nd[1] + self.dir[1]) != (0, 0):
            self.next_dir = nd

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        cell = min((w - px(40)) // GRID, (h - px(40)) // GRID)
        cell = max(cell, 10)
        gw, gh = cell * GRID, cell * GRID
        ox, oy = (w - gw) // 2, (h - gh) // 2
        c.create_rectangle(ox - 2, oy - 2, ox + gw + 2, oy + gh + 2, outline=LINE, width=2)
        c.create_rectangle(ox, oy, ox + gw, oy + gh, fill=BG2, outline="")
        for i in range(GRID + 1):
            c.create_line(ox + i * cell, oy, ox + i * cell, oy + gh, fill=blend(LINE, BG2, 0.5))
            c.create_line(ox, oy + i * cell, ox + gw, oy + i * cell, fill=blend(LINE, BG2, 0.5))
        fx, fy = self.food
        c.create_oval(ox + fx * cell + 3, oy + fy * cell + 3,
                      ox + (fx + 1) * cell - 3, oy + (fy + 1) * cell - 3,
                      fill=AMBER, outline=blend(AMBER, TEXT, 0.3))
        for i, (x, y) in enumerate(self.snake):
            color = CYAN if i == 0 else blend(GREEN, CYAN, 0.4 if i % 2 == 0 else 0.7)
            c.create_rectangle(ox + x * cell + 1, oy + y * cell + 1,
                               ox + (x + 1) * cell - 1, oy + (y + 1) * cell - 1,
                               fill=color, outline=blend(color, PANEL, 0.4))
        c.create_text(ox + gw // 2, oy - px(10), text=_t("длина {0}").format(len(self.snake)),
                      fill=TEXT, font=theme.font(9, True, mono=True))
        if self.over:
            self.draw_overlay(_t("ШНУР ОБОРВАН\nEsc / ЗАНОВО"))
        elif self.paused:
            self.draw_overlay(_t("ПАУЗА"))
