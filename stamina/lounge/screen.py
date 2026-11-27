"""Комната отдыха экипажа — лобби выбора игр."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, PURPLE, TEXT, blend, px

from . import store
from .breakout import BreakoutGame
from .snake import SnakeGame
from .tetris import TetrisGame
from .trainer import TrainerGame
from .vim_trainer import VimTrainerGame
from .docker_trainer import DockerTrainerGame
from .linux_trainer import LinuxTrainerGame
from .powershell_trainer import PowerShellTrainerGame


def _draw_terminal_preview(
    c: tk.Canvas,
    ww: int,
    hh: int,
    ox: int,
    oy: int,
    box_w: int,
    box_h: int,
    bg_color: str,
    border_color: str,
    lines: list[tuple[str, str]],
    mono_font_spec: tuple,
) -> None:
    """Draw a terminal-style preview with proper line spacing and clipping.

    Args:
        c: Canvas to draw on.
        ww, hh: Canvas width/height.
        ox, oy: Top-left of terminal box.
        box_w, box_h: Terminal box width/height.
        bg_color: Terminal background color.
        border_color: Terminal border color.
        lines: List of (text, color) tuples.
        mono_font_spec: Font spec from theme.font(7, mono=True).
    """
    # Draw terminal chrome
    c.create_rectangle(ox, oy, ox + box_w, oy + box_h, fill=bg_color, outline=border_color, width=1)

    # Measure actual line height from the font
    mono_font = tkfont.Font(font=mono_font_spec)
    line_h = mono_font.metrics("linespace")
    # Add 1px gap between lines
    line_h = max(line_h, 1) + 1

    # Inner padding
    pad_x = 4
    pad_y = 2

    # Max lines that fit inside the box
    max_lines = max(1, (box_h - 2 * pad_y) // line_h)

    # Draw lines, clipped to max_lines
    for i, (text, color) in enumerate(lines[:max_lines]):
        y = oy + pad_y + i * line_h
        # Horizontal clip: measure text width and truncate if needed
        text_w = mono_font.measure(text)
        max_text_w = box_w - 2 * pad_x
        if text_w > max_text_w:
            # Truncate with ellipsis
            ellipsis = "…"
            ellipsis_w = mono_font.measure(ellipsis)
            # Binary search for max chars that fit
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if mono_font.measure(text[:mid]) + ellipsis_w <= max_text_w:
                    lo = mid
                else:
                    hi = mid - 1
            text = text[:lo] + ellipsis
        c.create_text(ox + pad_x, y, text=text, fill=color, anchor="nw", font=mono_font_spec)


def _mission_count(cls) -> int:
    """Сколько настоящих миссий в игре: песочница — режим, а не задание."""
    return len([m for m in cls.missions if m.get("id") != "sandbox"])


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
    {
        "id": "trainer",
        "title": _t("ТРЕНАЖЁР"),
        "subtitle": _t("ТЕРРАФОРМЕР A1 · УЧЕБНАЯ СМЕНА"),
        "blurb": _t("Учебная смена перед настоящим терраформированием: снимай грунт слоями, "
                    "собирай блоки и закладывай фундамент."),
        "color": AMBER,
        "cls": TrainerGame,
    },
    {
        "id": "vim_trainer",
        "title": _t("VIM ТРЕНАЖЁР"),
        "subtitle": _t("РЕДАКТОР КОДА · 12 УРОКОВ"),
        "blurb": _t("Освой VIM: h/j/k/l, w/b/e, x/dw/dd, i/a/o, cw/cc, v/V, /, u, счетчики. "
                    "Интерактивные уроки на игровой сетке."),
        "color": PURPLE,
        "cls": VimTrainerGame,
    },
    {
        "id": "docker_trainer",
        "title": _t("DOCKER ТРЕНАЖЁР"),
        "subtitle": _t("{0} · миссий: {1}").format(_t("ДОК-СТАНЦИЯ"), _mission_count(DockerTrainerGame)),
        "blurb": _t("Освой Docker: run, ps, logs, stop, rm, volumes, networks, compose. "
                    "Интерактивный терминал с подсказками."),
        "color": CYAN,
        "cls": DockerTrainerGame,
    },
    {
        "id": "linux_trainer",
        "title": _t("LINUX ТРЕНАЖЁР"),
        "subtitle": _t("{0} · миссий: {1}").format(_t("BASH ТЕРМИНАЛ"), _mission_count(LinuxTrainerGame)),
        "blurb": _t("Освой Linux: ls, cd, grep, find, ps, systemctl, сеть, архивы. "
                    "Интерактивный терминал с подсказками."),
        "color": GREEN,
        "cls": LinuxTrainerGame,
    },
    {
        "id": "powershell_trainer",
        "title": _t("POWERSHELL ТРЕНАЖЁР"),
        "subtitle": _t("{0} · миссий: {1}").format(
            _t("СИСТЕМНЫЙ ИНТЕРФЕЙС"), _mission_count(PowerShellTrainerGame)),
        "blurb": _t("Освой PowerShell: Get-Process, Get-Service, файлы, сеть, службы. "
                    "Интерактивный терминал с подсказками."),
        "color": AMBER,
        "cls": PowerShellTrainerGame,
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

        # Header (fixed at top)
        head = tk.Frame(self.lobby, bg=BG)
        head.pack(fill=tk.X, padx=px(16), pady=(px(10), px(4)))
        tk.Label(head, text=_t("КОМНАТА ОТДЫХА ЭКИПАЖА"), bg=BG, fg=AMBER,
                 font=theme.font(18, True)).pack(side=tk.LEFT)
        HudButton(head, "?", lambda: self.app.open_help(), height=32, font_size=12,
                  width=36, color=AMBER).pack(side=tk.RIGHT)
        tk.Label(head, text=_t("короткий перерыв между полётами · рекорды сохраняются на борту"),
                 bg=BG, fg=MUTED, font=theme.font(11)).pack(side=tk.LEFT, padx=px(14))

        # Scrollable grid area
        scroll_frame = tk.Frame(self.lobby, bg=BG)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(8))

        canvas = tk.Canvas(scroll_frame, bg=BG, highlightthickness=0, bd=0)
        vbar = tk.Scrollbar(scroll_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        grid = tk.Frame(canvas, bg=BG)
        grid_id = canvas.create_window((0, 0), window=grid, anchor="nw")

        def _on_grid_configure(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(grid_id, width=canvas.winfo_width())
        grid.bind("<Configure>", _on_grid_configure)

        def _on_canvas_configure(_e):
            canvas.itemconfigure(grid_id, width=_e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _scroll(step: int) -> None:
            # Колесо привязано глобально: после выхода из лобби холст уже мёртв.
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(step, "units")
            except tk.TclError:
                pass

        def _on_mousewheel(e):
            _scroll(int(-1 * (e.delta / 120)))

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: _scroll(-1))
        canvas.bind_all("<Button-5>", lambda e: _scroll(1))

        # 3 columns
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="g")

        self.cards = []
        for i, g in enumerate(GAMES):
            card = HudPanel(grid, g["subtitle"], accent=g["color"])
            row = i // 3
            col = i % 3
            card.grid(row=row, column=col, sticky="nsew", padx=px(6), pady=px(6))
            body = card.body
            tk.Label(body, text=g["title"], bg=PANEL, fg=g["color"],
                     font=theme.font(20, True)).pack(anchor="w", pady=(px(8), px(4)))
            tk.Label(body, text=g["blurb"], bg=PANEL, fg=TEXT, wraplength=px(260),
                     justify="left", font=theme.font(13)).pack(anchor="w", pady=(0, px(12)))
            rec = tk.Label(body, text="", bg=PANEL, fg=MUTED, font=theme.font(12, True, mono=True))
            rec.pack(anchor="w")
            HudButton(body, _t("▶ ИГРАТЬ"), lambda gid=g["id"]: self.launch(gid),
                      color=g["color"], height=48, font_size=14).pack(
                side=tk.BOTTOM, fill=tk.X, pady=(px(12), px(8)))
            # мини-превью на canvas (без Living Space — иначе превью тоже «дрожит»)
            prev = tk.Canvas(body, bg=blend(PANEL, g["color"], 0.12), highlightthickness=0,
                             height=px(80))
            prev.living_skip = True
            prev.pack(fill=tk.X, pady=(px(8), px(10)))
            self.cards.append({"id": g["id"], "rec": rec, "prev": prev, "color": g["color"]})
            self._draw_preview(prev, g["id"], g["color"])

        # Footer (fixed at bottom of scroll area)
        foot = tk.Frame(grid, bg=BG)
        foot.grid(row=99, column=0, columnspan=3, sticky="ew", pady=(px(12), 0))
        tk.Label(foot, text=_t("Esc — пауза в игре · R — заново · выход в лобби — кнопка «← В ЛОББИ»"),
                 bg=BG, fg=MUTED, font=theme.font(10)).pack()

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
            elif gid == "trainer":
                cell = max(6, min(ww, hh) // 9)
                ox = ww // 2 - 3 * cell
                oy = hh // 2 - 2 * cell
                # снятые слои грунта
                for bx, by in ((0, 0), (1, 0), (0, 1)):
                    c.create_rectangle(ox + bx * cell, oy + by * cell,
                                       ox + (bx + 1) * cell - 1, oy + (by + 1) * cell - 1,
                                       fill=blend(color, PANEL, 0.45), outline="")
                # контур площадки 4×3 и несколько блоков
                c.create_rectangle(ox + 3 * cell, oy, ox + 7 * cell, oy + 3 * cell,
                                   outline=AMBER, dash=(3, 2))
                for bx in range(4):
                    for by in range(3):
                        if (bx + by) % 2 == 0:
                            c.create_rectangle(ox + (3 + bx) * cell + 1, oy + by * cell + 1,
                                               ox + (4 + bx) * cell - 1, oy + (by + 1) * cell - 1,
                                               fill=blend(AMBER, PANEL, 0.35), outline="")
                # маленький робот
                c.create_rectangle(ox, oy + 2 * cell, ox + cell - 1, oy + 3 * cell - 1,
                                   fill=CYAN, outline="")
                c.create_line(ox + cell, oy + 2.5 * cell, ox + cell * 2, oy + 2.5 * cell,
                              fill=AMBER, width=2, arrow="last")
            elif gid == "vim_trainer":
                cell = max(6, min(ww, hh) // 10)
                ox = ww // 2 - 4 * cell
                oy = hh // 2 - 2 * cell
                # VIM-like grid preview
                for y in range(4):
                    for x in range(8):
                        cx = ox + x * cell
                        cy = oy + y * cell
                        is_cursor = (x == 3 and y == 1)
                        fill = CYAN if is_cursor else blend(color, PANEL, 0.15 + y * 0.05)
                        c.create_rectangle(cx, cy, cx + cell - 1, cy + cell - 1, fill=fill, outline=blend(fill, TEXT, 0.2))
                        if is_cursor:
                            c.create_text(cx + cell // 2, cy + cell // 2, text="@", fill=BG, font=theme.font(8, True, mono=True))
                        elif (x + y) % 3 == 0:
                            c.create_text(cx + cell // 2, cy + cell // 2, text="vim"[x % 3], fill=MUTED, font=theme.font(7, mono=True))
                # Key hints
                c.create_text(ox + 4 * cell, oy + 4 * cell + 5, text="h j k l  w b e  x dw dd  i a o  v / u",
                              fill=AMBER, font=theme.font(7), anchor="center")
            elif gid == "docker_trainer":
                mono_font_spec = theme.font(7, mono=True)
                box_w = int(ww * 0.85)
                box_h = int(hh * 0.7)
                ox = (ww - box_w) // 2
                oy = (hh - box_h) // 2
                lines = [
                    ("$ docker run -d ship/radio", AMBER),
                    ("abc123def456", TEXT),
                    ("$ docker ps", AMBER),
                    ("CONTAINER ID   IMAGE          STATUS    PORTS     NAMES", TEXT),
                    ("abc123def456   ship/radio     Up 5s     8080/tcp  ship_abc", TEXT),
                    ("$ docker logs abc123", AMBER),
                    ("[radio] Module ready ✓", CYAN),
                ]
                _draw_terminal_preview(c, ww, hh, ox, oy, box_w, box_h, "#0D1117", AMBER, lines, mono_font_spec)
            elif gid == "linux_trainer":
                mono_font_spec = theme.font(7, mono=True)
                box_w = int(ww * 0.85)
                box_h = int(hh * 0.7)
                ox = (ww - box_w) // 2
                oy = (hh - box_h) // 2
                lines = [
                    ("$ pwd", AMBER),
                    ("/home/cosmonaut", TEXT),
                    ("$ whoami", AMBER),
                    ("cosmonaut", TEXT),
                    ("$ ls -la /var/log", AMBER),
                    ("syslog  auth.log  kern.log", TEXT),
                    ("$ grep -i error syslog", AMBER),
                    ("[error] module radio timeout", CYAN),
                ]
                _draw_terminal_preview(c, ww, hh, ox, oy, box_w, box_h, "#1a1a2e", CYAN, lines, mono_font_spec)
            elif gid == "powershell_trainer":
                mono_font_spec = theme.font(7, mono=True)
                box_w = int(ww * 0.85)
                box_h = int(hh * 0.7)
                ox = (ww - box_w) // 2
                oy = (hh - box_h) // 2
                lines = [
                    ("PS C:\\ship> Get-Process", AMBER),
                    ("  123  pwsh    12.4  45MB", TEXT),
                    ("  456  orion   8.1   128MB", TEXT),
                    ("PS C:\\ship> Get-Service", AMBER),
                    ("Running  ship-radio   Radio Module", TEXT),
                    ("Stopped  ship-scanner Offline", TEXT),
                    ("PS C:\\ship> Test-NetConnection localhost -Port 8080", AMBER),
                    ("TcpTestSucceeded : True", CYAN),
                ]
                _draw_terminal_preview(c, ww, hh, ox, oy, box_w, box_h, "#012456", AMBER, lines, mono_font_spec)
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
        # Перескан Living Space: игровой холст с living_skip не должен попасть в «стекло»
        living = getattr(self.app, "living", None)
        if living is not None:
            try:
                living.scan()
            except Exception:
                pass
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

    def handle_back(self) -> bool:
        if self.game is not None:
            self.show_lobby()
            return True
        return False

    def backspace_edits(self) -> bool:
        """Backspace правит текст в игре (Docker-тренажёр), а не выходит в лобби."""
        return bool(self.game is not None and getattr(self.game, "backspace_edits", False))

    def on_key(self, e: tk.Event) -> None:
        # F1 уже обрабатывает cockpit.open_help → game.on_help; не слать второй раз.
        if getattr(e, "keysym", "") == "F1":
            return
        if self.game is not None:
            self.game.on_key(e)

    def on_help(self) -> bool:
        """F1: у игры своя инструкция (тренажёр) — отдать ей; иначе обычная справка страницы."""
        handler = getattr(self.game, "on_help", None)
        return bool(handler()) if callable(handler) else False

    def on_leave(self) -> None:
        if self.game is not None:
            self.game.pause_leave()

    def close(self) -> None:
        self._clear_game()
