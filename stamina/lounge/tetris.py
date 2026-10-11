"""Тетрис — стыковка блоков на орбите."""
from __future__ import annotations

from stamina.i18n import t as _t

import random
import tkinter as tk

from stamina import theme
from stamina.theme import AMBER, BG2, CYAN, GREEN, LINE, PANEL, PURPLE, RED, TEXT, blend, px

from .base import GameShell

COLS, ROWS = 10, 20
SHAPES = {
    "I": [[1, 1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "Z": [[1, 1, 0], [0, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
}
COLORS = {
    "I": CYAN, "O": AMBER, "T": PURPLE, "S": GREEN,
    "Z": RED, "J": "#4C8CFF", "L": "#FF8C4C",
}


def _rot(m):
    return [list(row) for row in zip(*m[::-1])]


class TetrisGame(GameShell):
    game_id = "tetris"
    title = _t("ТЕТРИС · СТЫКОВКА БЛОКОВ")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.set_hint(_t("← → двигать · ↑ поворот · ↓ ускорить · Пробел — сброс · Esc пауза"))
        self.reset()

    def tick_ms(self) -> int:
        return max(80, 480 - self.level * 35)

    def reset(self) -> None:
        self.board = [[None] * COLS for _ in range(ROWS)]
        self.level = 1
        self.lines = 0
        self.bag: list[str] = []
        self.piece = None
        self.piece_x = 0
        self.piece_y = 0
        self._spawn()

    def _next_kind(self) -> str:
        if not self.bag:
            self.bag = list(SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self) -> None:
        kind = self._next_kind()
        shape = [row[:] for row in SHAPES[kind]]
        self.piece = {"kind": kind, "shape": shape, "color": COLORS[kind]}
        self.piece_x = COLS // 2 - len(shape[0]) // 2
        self.piece_y = 0
        if self._hits(self.piece_x, self.piece_y, shape):
            self.game_over()

    def _hits(self, x, y, shape) -> bool:
        for r, row in enumerate(shape):
            for c, cell in enumerate(row):
                if not cell:
                    continue
                xx, yy = x + c, y + r
                if xx < 0 or xx >= COLS or yy >= ROWS:
                    return True
                if yy >= 0 and self.board[yy][xx]:
                    return True
        return False

    def _lock(self) -> None:
        sh = self.piece["shape"]
        col = self.piece["color"]
        for r, row in enumerate(sh):
            for c, cell in enumerate(row):
                if cell and self.piece_y + r >= 0:
                    self.board[self.piece_y + r][self.piece_x + c] = col
        cleared = 0
        new = []
        for row in self.board:
            if all(row):
                cleared += 1
            else:
                new.append(row)
        for _ in range(cleared):
            new.insert(0, [None] * COLS)
        self.board = new
        if cleared:
            pts = {1: 100, 2: 300, 3: 500, 4: 800}.get(cleared, cleared * 200)
            self.add_score(pts * self.level)
            self.lines += cleared
            self.level = 1 + self.lines // 10
        self._spawn()

    def tick(self) -> None:
        if not self.piece:
            return
        if not self._hits(self.piece_x, self.piece_y + 1, self.piece["shape"]):
            self.piece_y += 1
        else:
            self._lock()

    def _hard_drop(self) -> None:
        if not self.piece or self.over:
            return
        while not self._hits(self.piece_x, self.piece_y + 1, self.piece["shape"]):
            self.piece_y += 1
            self.add_score(2)
        self._lock()
        self.redraw()

    def on_key(self, e: tk.Event) -> None:
        super().on_key(e)
        if self.paused or self.over or not self.piece:
            return
        k = e.keysym
        sh = self.piece["shape"]
        if k == "Left" and not self._hits(self.piece_x - 1, self.piece_y, sh):
            self.piece_x -= 1
        elif k == "Right" and not self._hits(self.piece_x + 1, self.piece_y, sh):
            self.piece_x += 1
        elif k == "Down":
            if not self._hits(self.piece_x, self.piece_y + 1, sh):
                self.piece_y += 1
                self.add_score(1)
            else:
                self._lock()
        elif k in ("Up", "x", "X"):
            rot = _rot(sh)
            if not self._hits(self.piece_x, self.piece_y, rot):
                self.piece["shape"] = rot
            elif not self._hits(self.piece_x - 1, self.piece_y, rot):
                self.piece_x -= 1
                self.piece["shape"] = rot
            elif not self._hits(self.piece_x + 1, self.piece_y, rot):
                self.piece_x += 1
                self.piece["shape"] = rot
        elif k == "space":
            self._hard_drop()
            return
        self.redraw()

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        cell = min((w - px(40)) // COLS, (h - px(40)) // ROWS)
        cell = max(cell, 8)
        gw, gh = cell * COLS, cell * ROWS
        ox, oy = (w - gw) // 2, (h - gh) // 2
        c.create_rectangle(ox - 2, oy - 2, ox + gw + 2, oy + gh + 2, outline=LINE, width=2)
        c.create_rectangle(ox, oy, ox + gw, oy + gh, fill=BG2, outline="")
        for r in range(ROWS):
            for col in range(COLS):
                color = self.board[r][col]
                if color:
                    self._cell(c, ox, oy, cell, col, r, color)
        if self.piece and not self.over:
            sh = self.piece["shape"]
            # ghost
            gy = self.piece_y
            while not self._hits(self.piece_x, gy + 1, sh):
                gy += 1
            for r, row in enumerate(sh):
                for col, cell_on in enumerate(row):
                    if cell_on:
                        self._cell(c, ox, oy, cell, self.piece_x + col, gy + r,
                                   blend(self.piece["color"], BG2, 0.75), ghost=True)
            for r, row in enumerate(sh):
                for col, cell_on in enumerate(row):
                    if cell_on:
                        self._cell(c, ox, oy, cell, self.piece_x + col, self.piece_y + r,
                                   self.piece["color"])
        c.create_text(ox + gw + px(12), oy + px(8), anchor="nw",
                      text=_t("УР. {0}\nЛИНИИ {1}").format(self.level, self.lines),
                      fill=TEXT, font=theme.font(10, True, mono=True))
        if self.over:
            self.draw_overlay(_t("СТЫКОВКА ПРОВАЛЕНА\nEsc / ЗАНОВО"))
        elif self.paused:
            self.draw_overlay(_t("ПАУЗА"))

    def _cell(self, c, ox, oy, cell, x, y, color, ghost=False):
        if y < 0:
            return
        x0, y0 = ox + x * cell, oy + y * cell
        pad = 1
        c.create_rectangle(x0 + pad, y0 + pad, x0 + cell - pad, y0 + cell - pad,
                           fill=color, outline=blend(color, PANEL, 0.35) if not ghost else color,
                           width=1)
