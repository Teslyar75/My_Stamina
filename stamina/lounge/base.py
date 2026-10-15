"""Общая оболочка игры: HUD-шапка, счёт, пауза, выход в лобби."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import Callable

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, TEXT, px

from . import store


class GameShell(tk.Frame):
    """Рамка вокруг игрового поля."""

    game_id = ""
    title = ""

    def __init__(self, master, *, on_back: Callable[[], None], app=None) -> None:
        super().__init__(master, bg=BG)
        self.on_back = on_back
        self.app = app
        self.score = 0
        self.paused = False
        self.over = False
        self._tick_id = None
        self._running = False

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(12), pady=(px(6), px(4)))
        self.lbl_title = tk.Label(top, text=self.title, bg=BG, fg=AMBER,
                                  font=theme.font(13, True))
        self.lbl_title.pack(side=tk.LEFT)
        self.lbl_score = tk.Label(top, text="", bg=BG, fg=CYAN,
                                  font=theme.font(11, True, mono=True))
        self.lbl_score.pack(side=tk.RIGHT)
        self.lbl_best = tk.Label(top, text="", bg=BG, fg=MUTED,
                                 font=theme.font(9, True, mono=True))
        self.lbl_best.pack(side=tk.RIGHT, padx=(0, px(16)))

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X, padx=px(12), pady=(0, px(4)))
        self.btn_pause = HudButton(bar, _t("ПАУЗА"), self.toggle_pause, height=30, font_size=8, width=90)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, px(4)))
        HudButton(bar, _t("ЗАНОВО"), self.restart, height=30, font_size=8, width=90, color=AMBER).pack(
            side=tk.LEFT, padx=(0, px(4)))
        HudButton(bar, _t("← В ЛОББИ"), self._back, height=30, font_size=8, width=110).pack(side=tk.LEFT)
        self.lbl_hint = tk.Label(bar, text="", bg=BG, fg=MUTED, font=theme.font(8))
        self.lbl_hint.pack(side=tk.RIGHT)

        panel = HudPanel(self, _t("ИГРОВОЕ ПОЛЕ"), accent=CYAN)
        panel.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(0, px(10)))
        self.canvas = tk.Canvas(panel.body, bg=PANEL, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self._update_labels()

    def set_hint(self, text: str) -> None:
        self.lbl_hint.configure(text=text)

    def _update_labels(self) -> None:
        self.lbl_score.configure(text=_t("СЧЁТ  {0}").format(self.score))
        self.lbl_best.configure(text=_t("РЕКОРД  {0}").format(store.best(self.game_id)))

    def add_score(self, n: int) -> None:
        self.score += n
        store.set_best(self.game_id, self.score)
        self._update_labels()

    def set_score(self, n: int) -> None:
        self.score = n
        store.set_best(self.game_id, self.score)
        self._update_labels()

    def toggle_pause(self) -> None:
        if self.over:
            return
        self.paused = not self.paused
        self.btn_pause.set_text(_t("ДАЛЬШЕ") if self.paused else _t("ПАУЗА"))
        self.redraw()
        if not self.paused and self._running:
            self.schedule_tick()

    def game_over(self) -> None:
        self.over = True
        self.paused = True
        store.set_best(self.game_id, self.score)
        self._update_labels()
        self.btn_pause.set_text(_t("ПАУЗА"))
        if self.app is not None:
            self.app.set_status(_t("ИГРА ОКОНЧЕНА · счёт {0}").format(self.score), AMBER)
        self.redraw()

    def restart(self) -> None:
        self.stop()
        self.score = 0
        self.paused = False
        self.over = False
        self.btn_pause.set_text(_t("ПАУЗА"))
        self._update_labels()
        self.reset()
        self.start()

    def _back(self) -> None:
        self.stop()
        self.on_back()

    def start(self) -> None:
        self._running = True
        self.schedule_tick()
        self.redraw()

    def stop(self) -> None:
        self._running = False
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except tk.TclError:
                pass
            self._tick_id = None

    def pause_leave(self) -> None:
        if self._running and not self.over and not self.paused:
            self.toggle_pause()

    def schedule_tick(self) -> None:
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except tk.TclError:
                pass
            self._tick_id = None
        if self._running and not self.paused and not self.over:
            self._tick_id = self.after(self.tick_ms(), self._on_tick)

    def _on_tick(self) -> None:
        self._tick_id = None
        if not self._running or self.paused or self.over:
            return
        self.tick()
        self.redraw()
        self.schedule_tick()

    # -- переопределить в играх ------------------------------------------------
    def tick_ms(self) -> int:
        return 200

    def reset(self) -> None:
        pass

    def tick(self) -> None:
        pass

    def redraw(self) -> None:
        pass

    def on_key(self, e: tk.Event) -> None:
        k = e.keysym
        if k in ("Escape", "p", "P"):
            # после поражения Esc должен перезапускать (оверлей «Esc / ЗАНОВО»),
            # а не молча игнорировать — иначе кнопка «не работает»
            if self.over:
                self.restart()
            else:
                self.toggle_pause()
        elif k in ("r", "R"):
            self.restart()

    def draw_overlay(self, msg: str) -> None:
        c = self.canvas
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        c.create_rectangle(0, 0, w, h, fill=BG, stipple="gray50", outline="")
        c.create_text(w // 2, h // 2, text=msg, fill=AMBER, font=theme.font(18, True),
                      justify="center")
