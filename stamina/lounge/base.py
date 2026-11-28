"""Общая оболочка игры: HUD-шапка, счёт, пауза, выход в лобби."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import Callable

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, MUTED, PANEL, TEXT, px

from . import store
from .help_overlay import HelpOverlay


class GameShell(tk.Frame):
    """Рамка вокруг игрового поля."""

    game_id = ""
    title = ""
    # Игра читает набранные команды с холста (Docker-тренажёр): тогда в панели
    # появляется галка «⌫ Backspace — стирать» и Backspace достаётся игре.
    text_input = False
    # Игра хочет вторую строку кнопок (учебник, песочница): тогда панель
    # создаёт self.tools и зовёт build_tools().
    tools_row = False

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
                                  font=theme.font(15, True))
        self.lbl_title.pack(side=tk.LEFT)
        self.lbl_score = tk.Label(top, text="", bg=BG, fg=CYAN,
                                  font=theme.font(13, True, mono=True))
        self.lbl_score.pack(side=tk.RIGHT)
        self.lbl_best = tk.Label(top, text="", bg=BG, fg=MUTED,
                                 font=theme.font(11, True, mono=True))
        self.lbl_best.pack(side=tk.RIGHT, padx=(0, px(16)))

        bar = tk.Frame(self, bg=BG)
        self.toolbar = bar
        bar.pack(fill=tk.X, padx=px(12), pady=(0, px(4)))
        self.btn_pause = HudButton(bar, _t("ПАУЗА"), self.toggle_pause, height=34, font_size=10, width=100)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, px(4)))
        HudButton(bar, _t("ЗАНОВО"), self.restart, height=34, font_size=10, width=100, color=AMBER).pack(
            side=tk.LEFT, padx=(0, px(4)))
        HudButton(bar, _t("← В ЛОББИ"), self._back, height=34, font_size=10, width=120).pack(side=tk.LEFT)
        self.btn_help = HudButton(bar, "?", self.on_help, height=34, font_size=12, width=40, color=AMBER)
        self.btn_help.pack(side=tk.LEFT, padx=(px(8), 0))
        self.btn_zen = HudButton(bar, "⛶", self.toggle_zen, height=34, font_size=12, width=40, color=CYAN)
        self.btn_zen.pack(side=tk.LEFT, padx=(px(4), 0))
        # Галка для игр с вводом: Backspace стирает символ, а не уводит в лобби.
        # Вне игры глобальный Backspace не меняется — настройка живёт в lounge.json.
        self.backspace_edits = bool(store.setting("backspace_edits", True))
        self.var_backspace = None
        if self.text_input:
            self.var_backspace = tk.BooleanVar(value=self.backspace_edits)
            tk.Checkbutton(
                bar, text=_t("⌫ Backspace — стирать"),
                variable=self.var_backspace, command=self._on_backspace_toggle,
                bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
                selectcolor=PANEL, highlightthickness=0, bd=0, takefocus=0,
                font=theme.font(10),
            ).pack(side=tk.LEFT, padx=(px(10), 0))
        # Вторая строка: своя у игр, которым мало одной (Docker: учебник, песочница)
        self.tools = None
        if self.tools_row:
            self.tools = tk.Frame(self, bg=BG)
            self.tools.pack(fill=tk.X, padx=px(12), pady=(0, px(4)))
            self.build_tools()
        self.lbl_hint = tk.Label(self.tools if self.tools is not None else bar,
                                 text="", bg=BG, fg=MUTED, font=theme.font(10))
        self.lbl_hint.pack(side=tk.RIGHT)

        panel = HudPanel(self, _t("ИГРОВОЕ ПОЛЕ"), accent=CYAN)
        panel.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(0, px(10)))
        self.canvas = tk.Canvas(panel.body, bg=PANEL, highlightthickness=0, bd=0)
        # Не участвует в Living Space «стекле»: иначе каждый delete("all") в tick
        # срывает ls_bg, фон космоса снова красится → дрожь/мерцание за игрой.
        self.canvas.living_skip = True
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas_size = (0, 0)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.help_overlay = HelpOverlay(self)
        self._wrap_redraw_for_help()
        self._update_labels()

    def _wrap_redraw_for_help(self) -> None:
        orig = self.redraw

        def _redraw_with_help(*a, **k):
            orig(*a, **k)
            ov = getattr(self, "help_overlay", None)
            if ov is not None and ov.is_visible():
                ov.draw()

        self.redraw = _redraw_with_help

    def _on_canvas_configure(self, e: tk.Event) -> None:
        size = (int(e.width), int(e.height))
        if size == self._canvas_size or size[0] < 4 or size[1] < 4:
            return
        self._canvas_size = size
        self.redraw()

    def set_hint(self, text: str) -> None:
        self.lbl_hint.configure(text=text)

    def build_tools(self) -> None:
        """Свои кнопки во второй строке панели (переопределяют игры с tools_row)."""

    def _on_backspace_toggle(self) -> None:
        """Галка «Backspace — стирать»: запомнить выбор и вернуть фокус игре."""
        self.backspace_edits = bool(self.var_backspace.get())
        store.set_setting("backspace_edits", self.backspace_edits)
        self.focus_set()          # иначе пробел будет нажимать сам чек-бокс
        self.redraw()

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

    def help_game_id(self) -> str:
        return self.game_id

    def help_level_id(self) -> str | None:
        """id уровня из help_texts/<game>.json; None — только обзор."""
        return None

    def toggle_zen(self) -> bool:
        """Общий зенид приложения: ⛶ / Ctrl+O, выход — двойной Esc."""
        from stamina import zen_mode
        return zen_mode.toggle(self)

    def on_help(self) -> bool:
        """F1 / «?»: открыть или закрыть оверлей справки. True — событие обработано."""
        ov = getattr(self, "help_overlay", None)
        if ov is None:
            return False
        ov.toggle()
        return True

    def handle_help_keys(self, e: tk.Event) -> bool:
        """True, если клавиша съедена справкой (F1 или Esc при открытом оверлее)."""
        ov = getattr(self, "help_overlay", None)
        if ov is None:
            return False
        k = e.keysym
        if k == "F1":
            self.on_help()
            return True
        if ov.is_visible():
            if k == "Escape":
                ov.hide()
                return True
            # Остальные клавиши (в частности h/j/k/l и стрелки VIM) должны
            # доходить до игры: справка — это оверлей, а не модальный диалог.
            return False
        return False

    def on_key(self, e: tk.Event) -> None:
        if self.handle_help_keys(e):
            return
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
        c.create_text(w // 2, h // 2, text=msg, fill=AMBER, font=theme.font(20, True),
                      justify="center", tags="overlay")
