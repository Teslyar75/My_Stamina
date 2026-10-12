"""Комната отдыха экипажа — лобби выбора игр."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, PURPLE, TEXT, blend, px

from . import store
from .breakout import BreakoutGame
from .snake import SnakeGame
from .tetris import TetrisGame

GAMES = [
    {
        "id": "tetris",
        "title": _t("ТЕТРИС"),
        "subtitle": _t("СТЫКОВКА БЛОКОВ"),
        "blurb": _t("Соберите линии из падающих блоков. Классика на орбитальной станции."),
        "color": CYAN,
        "cls": TetrisGame,
    },
    {
        "id": "snake",
        "title": _t("ЗМЕЙКА"),
        "subtitle": _t("НАВИГАЦИОННЫЙ ШНУР"),
        "blurb": _t("Ведите шнур по сетке, собирайте маяки, не врежьтесь в стены и в себя."),
        "color": GREEN,
        "cls": SnakeGame,
    },
    {
        "id": "breakout",
        "title": _t("АРКАНОИД"),
        "subtitle": _t("ОТРАЖАТЕЛЬ ЩИТА"),
        "blurb": _t("Отбивайте заряд щитом и сбивайте блоки обшивки. Три жизни на заход."),
        "color": PURPLE,
        "cls": BreakoutGame,
    },
]


class LoungeScreen(tk.Frame):
    def page_help_key(self) -> str:
        return "lounge"

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.game = None

        self.lobby = tk.Frame(self, bg=BG)
        self.lobby.pack(fill=tk.BOTH, expand=True)
        self.game_host = tk.Frame(self, bg=BG)

        head = tk.Frame(self.lobby, bg=BG)
        head.pack(fill=tk.X, padx=px(16), pady=(px(10), px(4)))
        tk.Label(head, text=_t("КОМНАТА ОТДЫХА ЭКИПАЖА"), bg=BG, fg=AMBER,
                 font=theme.font(16, True)).pack(side=tk.LEFT)
        HudButton(head, "?", lambda: self.app.open_help(), height=28, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        tk.Label(head, text=_t("короткий перерыв между полётами · рекорды сохраняются на борту"),
                 bg=BG, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT, padx=px(14))

        grid = tk.Frame(self.lobby, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(8))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="g")
        grid.grid_rowconfigure(0, weight=1)

        self.cards = []
        for i, g in enumerate(GAMES):
            card = HudPanel(grid, g["subtitle"], accent=g["color"])
            card.grid(row=0, column=i, sticky="nsew", padx=px(6), pady=px(4))
            body = card.body
            tk.Label(body, text=g["title"], bg=PANEL, fg=g["color"],
                     font=theme.font(18, True)).pack(anchor="w", pady=(px(4), px(2)))
            tk.Label(body, text=g["blurb"], bg=PANEL, fg=TEXT, wraplength=px(220),
                     justify="left", font=theme.font(10)).pack(anchor="w", pady=(0, px(10)))
            rec = tk.Label(body, text="", bg=PANEL, fg=MUTED, font=theme.font(10, True, mono=True))
            rec.pack(anchor="w")
            HudButton(body, _t("▶ ИГРАТЬ"), lambda gid=g["id"]: self.launch(gid),
                      color=g["color"], height=40, font_size=11).pack(
                side=tk.BOTTOM, fill=tk.X, pady=(px(12), px(4)))
            # мини-превью на canvas
            prev = tk.Canvas(body, bg=blend(PANEL, g["color"], 0.12), highlightthickness=0,
                             height=px(90))
            prev.pack(fill=tk.X, pady=px(8))
            self.cards.append({"id": g["id"], "rec": rec, "prev": prev, "color": g["color"]})
            self._draw_preview(prev, g["id"], g["color"])

        foot = tk.Frame(self.lobby, bg=BG)
        foot.pack(fill=tk.X, padx=px(16), pady=(0, px(10)))
        tk.Label(foot, text=_t("Esc — пауза в игре · R — заново · выход в лобби — кнопка «← В ЛОББИ»"),
                 bg=BG, fg=MUTED, font=theme.font(8)).pack(side=tk.LEFT)

    def _draw_preview(self, c: tk.Canvas, gid: str, color: str) -> None:
        c.delete("all")
        w, h = px(240), px(90)
        c.configure(width=w)

        def draw(_e=None):
            c.delete("all")
            ww = max(c.winfo_width(), 40)
            hh = max(c.winfo_height(), 40)
            if gid == "tetris":
                blocks = [(1, 0), (1, 1), (1, 2), (2, 2), (0, 3), (1, 3), (2, 3)]
                cell = min(ww, hh) // 8
                ox, oy = ww // 2 - cell * 1.5, hh // 2 - cell * 2
                for x, y in blocks:
                    c.create_rectangle(ox + x * cell, oy + y * cell,
                                       ox + (x + 1) * cell - 1, oy + (y + 1) * cell - 1,
                                       fill=color, outline=blend(color, PANEL, 0.4))
            elif gid == "snake":
                path = [(2, 3), (3, 3), (4, 3), (5, 3), (5, 2), (5, 1)]
                cell = min(ww, hh) // 10
                ox, oy = ww // 2 - 3 * cell, hh // 2 - 2 * cell
                for i, (x, y) in enumerate(path):
                    col = CYAN if i == len(path) - 1 else color
                    c.create_rectangle(ox + x * cell, oy + y * cell,
                                       ox + (x + 1) * cell - 1, oy + (y + 1) * cell - 1,
                                       fill=col, outline="")
                c.create_oval(ox + 7 * cell, oy + 1 * cell, ox + 8 * cell, oy + 2 * cell, fill=AMBER)
            else:
                for r in range(3):
                    for col in range(8):
                        c.create_rectangle(10 + col * ((ww - 20) // 8), 12 + r * 14,
                                           10 + (col + 1) * ((ww - 20) // 8) - 2, 24 + r * 14,
                                           fill=blend(color, PANEL, 0.2 * r), outline="")
                c.create_rectangle(ww // 2 - 30, hh - 22, ww // 2 + 30, hh - 12, fill=CYAN, outline="")
                c.create_oval(ww // 2 - 5, hh - 40, ww // 2 + 5, hh - 30, fill=AMBER, outline="")

        c.bind("<Configure>", draw)
        self.after(50, draw)

    def refresh(self) -> None:
        if self.game is not None:
            return
        for card in self.cards:
            card["rec"].configure(text=_t("РЕКОРД  {0}").format(store.best(card["id"])))

    def launch(self, game_id: str) -> None:
        meta = next((g for g in GAMES if g["id"] == game_id), None)
        if not meta:
            return
        self._clear_game()
        self.lobby.pack_forget()
        self.game_host.pack(fill=tk.BOTH, expand=True)
        self.game = meta["cls"](self.game_host, on_back=self.show_lobby, app=self.app)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.game.start()
        self.app.set_status(_t("КОМНАТА ОТДЫХА · {0}").format(meta["title"]), CYAN)
        self.focus_set()

    def show_lobby(self) -> None:
        self._clear_game()
        self.game_host.pack_forget()
        self.lobby.pack(fill=tk.BOTH, expand=True)
        self.refresh()
        self.app.set_status(_t("КОМНАТА ОТДЫХА ЭКИПАЖА"), CYAN)

    def _clear_game(self) -> None:
        if self.game is not None:
            try:
                self.game.stop()
            except Exception:
                pass
            self.game.destroy()
            self.game = None
        for w in self.game_host.winfo_children():
            w.destroy()

    def on_key(self, e: tk.Event) -> None:
        if self.game is not None:
            self.game.on_key(e)

    def on_leave(self) -> None:
        if self.game is not None:
            self.game.pause_leave()

    def close(self) -> None:
        self._clear_game()
