"""Арканоид — отражатель щита: отбивайте заряд, сбивайте блоки."""
from __future__ import annotations

from stamina.i18n import t as _t

import math
import random
import tkinter as tk

from stamina import theme
from stamina.theme import AMBER, BG2, CYAN, GREEN, LINE, MUTED, PANEL, PURPLE, RED, TEXT, blend, px

from .base import GameShell

BRICK_ROWS = 5
BRICK_COLS = 10
COLORS = [RED, AMBER, GREEN, CYAN, PURPLE]


class BreakoutGame(GameShell):
    game_id = "breakout"
    title = _t("АРКАНОИД · ОТРАЖАТЕЛЬ ЩИТА")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.set_hint(_t("← → или A D — щит · Пробел — пуск · Esc пауза"))
        self._fw = 800
        self._fh = 520
        self.reset()

    def tick_ms(self) -> int:
        return 16

    def reset(self) -> None:
        self.lives = 3
        self.launched = False
        self.bricks = []
        for r in range(BRICK_ROWS):
            for c in range(BRICK_COLS):
                self.bricks.append({"r": r, "c": c, "alive": True, "color": COLORS[r % len(COLORS)]})
        self.paddle_x = 0.5
        self.paddle_w = 0.16
        self.ball_x = 0.5
        self.ball_y = 0.85
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        self._keys = set()

    def _launch(self) -> None:
        if self.launched or self.over:
            return
        angle = random.uniform(-0.6, 0.6)
        speed = 0.011
        self.ball_vx = math.sin(angle) * speed
        self.ball_vy = -abs(math.cos(angle) * speed)
        self.launched = True

    def tick(self) -> None:
        # движение щита
        step = 0.018
        if "Left" in self._keys or "a" in self._keys:
            self.paddle_x = max(self.paddle_w / 2, self.paddle_x - step)
        if "Right" in self._keys or "d" in self._keys:
            self.paddle_x = min(1 - self.paddle_w / 2, self.paddle_x + step)
        if not self.launched:
            self.ball_x = self.paddle_x
            self.ball_y = 0.88
            return
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy
        # стены
        if self.ball_x <= 0.02:
            self.ball_x = 0.02
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x >= 0.98:
            self.ball_x = 0.98
            self.ball_vx = -abs(self.ball_vx)
        if self.ball_y <= 0.03:
            self.ball_y = 0.03
            self.ball_vy = abs(self.ball_vy)
        # щит
        py = 0.92
        if self.ball_vy > 0 and abs(self.ball_y - py) < 0.03:
            if abs(self.ball_x - self.paddle_x) <= self.paddle_w / 2 + 0.01:
                offset = (self.ball_x - self.paddle_x) / (self.paddle_w / 2)
                self.ball_vy = -abs(self.ball_vy)
                self.ball_vx = max(-0.018, min(0.018, self.ball_vx + offset * 0.008))
                # чуть ускорить
                sp = math.hypot(self.ball_vx, self.ball_vy)
                if sp < 0.02:
                    k = 1.03
                    self.ball_vx *= k
                    self.ball_vy *= k
        # промах
        if self.ball_y > 1.02:
            self.lives -= 1
            self.launched = False
            self.ball_vx = self.ball_vy = 0.0
            if self.lives <= 0:
                self.game_over()
            return
        # блоки
        bw, bh = 1 / BRICK_COLS, 0.06
        top = 0.12
        hit = None
        for b in self.bricks:
            if not b["alive"]:
                continue
            x0 = b["c"] * bw
            y0 = top + b["r"] * bh
            if x0 <= self.ball_x <= x0 + bw and y0 <= self.ball_y <= y0 + bh * 0.9:
                hit = b
                break
        if hit:
            hit["alive"] = False
            self.ball_vy = -self.ball_vy
            self.add_score(10 + hit["r"] * 5)
            if all(not b["alive"] for b in self.bricks):
                self.add_score(200)
                # новый уровень — восстановить блоки, ускорить
                for b in self.bricks:
                    b["alive"] = True
                self.ball_vx *= 1.1
                self.ball_vy *= 1.1

    def on_key(self, e: tk.Event) -> None:
        super().on_key(e)
        k = e.keysym
        if k in ("Left", "Right", "a", "A", "d", "D"):
            self._keys.add(k if k in ("Left", "Right") else k.lower())
            # KeyRelease обрабатываем отдельно через bind на canvas — здесь только press
            # дублируем: после press держим до следующего кадра через after clear? 
            # Проще: мгновенный сдвиг + keep set, очищаем на KeyRelease через shell
        if k == "space":
            self._launch()
        # одноразовый сдвиг на press, если не hold-система
        if not self.paused and not self.over:
            if k == "Left" or k.lower() == "a":
                self.paddle_x = max(self.paddle_w / 2, self.paddle_x - 0.04)
            elif k == "Right" or k.lower() == "d":
                self.paddle_x = min(1 - self.paddle_w / 2, self.paddle_x + 0.04)
            if not self.launched:
                self.ball_x = self.paddle_x

    def key_up(self, e: tk.Event) -> None:
        k = e.keysym
        self._keys.discard(k if k in ("Left", "Right") else k.lower())

    def start(self) -> None:
        super().start()
        self.bind_all("<KeyRelease-Left>", self.key_up)
        self.bind_all("<KeyRelease-Right>", self.key_up)
        self.bind_all("<KeyRelease-a>", self.key_up)
        self.bind_all("<KeyRelease-A>", self.key_up)
        self.bind_all("<KeyRelease-d>", self.key_up)
        self.bind_all("<KeyRelease-D>", self.key_up)

    def stop(self) -> None:
        for seq in ("<KeyRelease-Left>", "<KeyRelease-Right>", "<KeyRelease-a>",
                    "<KeyRelease-A>", "<KeyRelease-d>", "<KeyRelease-D>"):
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        self._keys.clear()
        super().stop()

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        self._fw, self._fh = w, h
        c.create_rectangle(2, 2, w - 2, h - 2, outline=LINE, width=2, fill=BG2)
        # кирпичи
        top = int(h * 0.12)
        bh = int(h * 0.055)
        bw = (w - 20) // BRICK_COLS
        for b in self.bricks:
            if not b["alive"]:
                continue
            x0 = 10 + b["c"] * bw
            y0 = top + b["r"] * bh
            c.create_rectangle(x0 + 1, y0 + 1, x0 + bw - 2, y0 + bh - 2,
                               fill=b["color"], outline=blend(b["color"], PANEL, 0.35))
        # щит
        pw = int(w * self.paddle_w)
        px0 = int(self.paddle_x * w - pw / 2)
        py0 = int(h * 0.92)
        c.create_rectangle(px0, py0, px0 + pw, py0 + px(10), fill=CYAN, outline=blend(CYAN, TEXT, 0.3))
        # шар
        br = px(7)
        bx, by = int(self.ball_x * w), int(self.ball_y * h)
        c.create_oval(bx - br, by - br, bx + br, by + br, fill=AMBER, outline=TEXT)
        # жизни
        for i in range(self.lives):
            c.create_oval(px(12) + i * px(18), h - px(22), px(24) + i * px(18), h - px(10),
                          fill=RED, outline="")
        if not self.launched and not self.over and not self.paused:
            c.create_text(w // 2, int(h * 0.7), text=_t("ПРОБЕЛ — ПУСК"),
                          fill=MUTED, font=theme.font(12, True))
        if self.over:
            self.draw_overlay(_t("ЩИТ ПРОБИТ\nEsc / ЗАНОВО"))
        elif self.paused:
            self.draw_overlay(_t("ПАУЗА"))
