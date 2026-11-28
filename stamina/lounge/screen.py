"""Комната отдыха экипажа — лобби выбора игр."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, PURPLE, RED, TEXT, blend, px

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
            ellipsis = "\u2026"
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


def _draw_game_frame(
    c: tk.Canvas,
    ww: int,
    hh: int,
    color: str,
    bg_tint: float = 0.15,
) -> tuple[int, int, int, int]:
    """Draw a wide framed playfield for game previews.

    Returns (ox, oy, box_w, box_h) of the inner content area (inside the border).
    """
    box_w = int(ww * 0.85)
    box_h = int(hh * 0.8)
    ox = (ww - box_w) // 2
    oy = (hh - box_h) // 2

    bg_color = blend(PANEL, color, bg_tint)
    c.create_rectangle(ox, oy, ox + box_w, oy + box_h, fill=bg_color, outline=color, width=2)

    # Inner content area (1px inset from border)
    return ox + 1, oy + 1, box_w - 2, box_h - 2


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
        "subtitle": _t("ТЕРРАФОРМЕР · СТРАТЕГИЯ ПЛАНЕТЫ"),
        "blurb": _t("Стратегическая смена: восемь уровней A1–C2, отряд, задания-тревоги, "
                    "туман войны, здания и песчаный червь."),
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
                ox, oy, box_w, box_h = _draw_game_frame(c, ww, hh, color)
                # Tetris well: 10 cols x ~15 rows visible, scaled to fit
                cols = 10
                rows = 14
                cell = min(box_w // cols, box_h // rows)
                # Center the grid in the frame
                gx = ox + (box_w - cols * cell) // 2
                gy = oy + (box_h - rows * cell) // 2

                # Stacked tetrominoes (frozen pieces)
                frozen = [
                    # Bottom row - almost complete line (missing one)
                    (0, 13), (1, 13), (2, 13), (3, 13), (4, 13), (5, 13), (6, 13), (7, 13), (9, 13),
                    # Row above
                    (0, 12), (2, 12), (3, 12), (4, 12), (5, 12), (6, 12), (7, 12), (8, 12), (9, 12),
                    # Scattered blocks above
                    (1, 11), (3, 11), (6, 11), (8, 11),
                    (0, 10), (2, 10), (5, 10), (9, 10),
                    (4, 9), (7, 9),
                ]
                for x, y in frozen:
                    cx = gx + x * cell
                    cy = gy + y * cell
                    c.create_rectangle(cx, cy, cx + cell - 1, cy + cell - 1,
                                       fill=blend(color, PANEL, 0.3), outline=blend(color, PANEL, 0.6))

                # Active falling piece (I-piece, vertical, about to complete the line)
                active = [(8, 5), (8, 6), (8, 7), (8, 8)]
                for x, y in active:
                    cx = gx + x * cell
                    cy = gy + y * cell
                    c.create_rectangle(cx, cy, cx + cell - 1, cy + cell - 1,
                                       fill=color, outline=blend(color, TEXT, 0.3))
            elif gid == "snake":
                ox, oy, box_w, box_h = _draw_game_frame(c, ww, hh, color)
                # Wide grid: ~16 cols x 10 rows
                cols = 16
                rows = 10
                cell = min(box_w // cols, box_h // rows)
                gx = ox + (box_w - cols * cell) // 2
                gy = oy + (box_h - rows * cell) // 2

                # Faint grid lines
                for x in range(cols + 1):
                    c.create_line(gx + x * cell, gy, gx + x * cell, gy + rows * cell,
                                  fill=blend(color, PANEL, 0.8), width=1)
                for y in range(rows + 1):
                    c.create_line(gx, gy + y * cell, gx + cols * cell, gy + y * cell,
                                  fill=blend(color, PANEL, 0.8), width=1)

                # Longer snake weaving across the grid
                # Head at right, body weaving left
                snake_body = [
                    (14, 5), (13, 5), (12, 5), (11, 5), (10, 5),
                    (10, 4), (10, 3), (9, 3), (8, 3), (7, 3),
                    (7, 4), (7, 5), (6, 5), (5, 5), (4, 5),
                ]
                for i, (x, y) in enumerate(snake_body):
                    cx = gx + x * cell
                    cy = gy + y * cell
                    is_head = (i == 0)
                    fill = CYAN if is_head else (blend(color, CYAN, 0.3) if i < 3 else color)
                    c.create_rectangle(cx + 1, cy + 1, cx + cell - 1, cy + cell - 1,
                                       fill=fill, outline=blend(fill, PANEL, 0.3))
                    # Head indicator
                    if is_head:
                        c.create_oval(cx + cell // 3, cy + cell // 3,
                                      cx + 2 * cell // 3, cy + 2 * cell // 3,
                                      fill=AMBER, outline="")

                # Apple/beacon at top-left area
                ax, ay = 2, 2
                c.create_oval(gx + ax * cell + 2, gy + ay * cell + 2,
                              gx + (ax + 1) * cell - 2, gy + (ay + 1) * cell - 2,
                              fill=AMBER, outline=blend(AMBER, TEXT, 0.5), width=1)
            elif gid == "trainer":
                ox, oy, box_w, box_h = _draw_game_frame(c, ww, hh, color)
                # Wide work site: layered soil, dug cells, foundation footprint, robot
                cols = 14
                rows = 8
                cell = min(box_w // cols, box_h // rows)
                gx = ox + (box_w - cols * cell) // 2
                gy = oy + (box_h - rows * cell) // 2

                # Layered soil (bottom rows, darker)
                soil_colors = [
                    blend(AMBER, PANEL, 0.15),  # top soil
                    blend(AMBER, PANEL, 0.25),
                    blend(AMBER, PANEL, 0.35),
                    blend(AMBER, PANEL, 0.45),  # deep soil
                ]
                for row in range(rows):
                    soil_idx = min(row, len(soil_colors) - 1)
                    for col in range(cols):
                        cx = gx + col * cell
                        cy = gy + row * cell
                        c.create_rectangle(cx, cy, cx + cell - 1, cy + cell - 1,
                                           fill=soil_colors[soil_idx], outline="")

                # Dug cells (excavated - lighter)
                dug = [(2, 5), (3, 5), (4, 5), (5, 5), (2, 4), (5, 4)]
                for x, y in dug:
                    cx = gx + x * cell
                    cy = gy + y * cell
                    c.create_rectangle(cx + 1, cy + 1, cx + cell - 1, cy + cell - 1,
                                       fill=blend(AMBER, PANEL, 0.05), outline=blend(AMBER, PANEL, 0.3))

                # Dashed foundation footprint (4x3 area)
                fx, fy = 7, 4
                fw, fh = 5, 3
                c.create_rectangle(gx + fx * cell, gy + fy * cell,
                                   gx + (fx + fw) * cell, gy + (fy + fh) * cell,
                                   outline=AMBER, dash=(4, 3), width=1)

                # Placed foundation blocks inside footprint
                for bx in range(fw):
                    for by in range(fh):
                        if (bx + by) % 2 == 0 or by == fh - 1:
                            cx = gx + (fx + bx) * cell
                            cy = gy + (fy + by) * cell
                            c.create_rectangle(cx + 2, cy + 2, cx + cell - 2, cy + cell - 2,
                                               fill=blend(AMBER, CYAN, 0.3), outline=blend(AMBER, TEXT, 0.4))

                # Robot (left side)
                rx, ry = 1, 2
                c.create_rectangle(gx + rx * cell, gy + ry * cell,
                                   gx + (rx + 1) * cell - 1, gy + (ry + 2) * cell - 1,
                                   fill=CYAN, outline=blend(CYAN, TEXT, 0.4))
                # Robot arm/indicator
                c.create_line(gx + (rx + 1) * cell, gy + (ry + 1) * cell,
                              gx + (rx + 2) * cell, gy + (ry + 1) * cell,
                              fill=AMBER, width=2, arrow="last")
            elif gid == "vim_trainer":
                ox, oy, box_w, box_h = _draw_game_frame(c, ww, hh, color)

                # Use a small mono font; compute actual linespace
                mono_font_spec = theme.font(7, mono=True)
                mono_font = tkfont.Font(font=mono_font_spec)
                line_h = mono_font.metrics("linespace") + 1  # actual linespace + 1px gap

                # Inner padding
                pad_x = 4
                pad_y = 2
                max_text_w = box_w - 2 * pad_x

                # Editor content lines
                buffer_lines = [
                    "def navigate(ship):",
                    "    if ship.radar:",  # cursor on 'i' of 'if'
                    "        scan()",
                    "    return course",
                    "",
                    "-- NORMAL --",
                ]

                # Truncate each line to fit, compute actual drawn lines count
                drawn_lines = []
                for line in buffer_lines:
                    text_w = mono_font.measure(line)
                    if text_w > max_text_w:
                        ellipsis = "\u2026"
                        ellipsis_w = mono_font.measure(ellipsis)
                        lo, hi = 0, len(line)
                        while lo < hi:
                            mid = (lo + hi + 1) // 2
                            if mono_font.measure(line[:mid]) + ellipsis_w <= max_text_w:
                                lo = mid
                            else:
                                hi = mid - 1
                        line = line[:lo] + ellipsis
                    drawn_lines.append(line)

                # Max lines that fit with optional status line
                status_text = "h j k l  w b e  x dw dd  i a o  v / u"
                status_font_spec = theme.font(6, mono=True)
                status_font = tkfont.Font(font=status_font_spec)
                status_h = status_font.metrics("linespace") + 1

                # Determine how many buffer lines fit with status
                max_buffer_lines = max(1, (box_h - 2 * pad_y - status_h) // line_h)
                if max_buffer_lines > len(drawn_lines):
                    max_buffer_lines = len(drawn_lines)

                # Vertically center the buffer+status block
                total_h = max_buffer_lines * line_h + status_h
                gy = oy + pad_y + (box_h - 2 * pad_y - total_h) // 2
                if gy < oy + pad_y:
                    gy = oy + pad_y

                gx = ox + pad_x

                # ---- Editor chrome (non-text) ----
                # Top title/tab bar
                tab_h = line_h
                c.create_rectangle(ox, oy, ox + box_w, oy + tab_h,
                                   fill=blend(PANEL, color, 0.2), outline="")
                # Thin separator under tab bar
                sep_y = oy + tab_h
                c.create_line(ox, sep_y, ox + box_w, sep_y, fill=blend(color, PANEL, 0.5), width=1)

                # Left gutter (narrow strip)
                gutter_w = 3
                c.create_rectangle(ox, oy + tab_h, ox + gutter_w, oy + box_h,
                                   fill=blend(PANEL, color, 0.15), outline="")

                # Right scrollbar track + thumb
                sb_w = 4
                sb_x = ox + box_w - sb_w
                c.create_rectangle(sb_x, oy + tab_h, ox + box_w, oy + box_h,
                                   fill=blend(PANEL, color, 0.1), outline="")
                # Thumb (small, near top)
                thumb_h = max(8, box_h // 6)
                thumb_y = oy + tab_h + 4
                c.create_rectangle(sb_x + 1, thumb_y, sb_x + sb_w - 1, thumb_y + thumb_h,
                                   fill=blend(color, PANEL, 0.4), outline="")

                # Adjust text start x to account for gutter
                gx = ox + gutter_w + pad_x
                max_text_w = box_w - gutter_w - 2 * pad_x

                # Draw buffer lines
                for row, line in enumerate(drawn_lines[:max_buffer_lines]):
                    y = gy + row * line_h
                    # Line background
                    c.create_rectangle(gx, y, gx + max_text_w, y + line_h - 1,
                                       fill=blend(PANEL, color, 0.1), outline="")
                    # Text
                    c.create_text(gx, y, text=line, fill=TEXT, anchor="nw",
                                  font=mono_font_spec)

                # Block cursor on 'i' of 'if' (line 1, col 4)
                cursor_row = 1
                cursor_col = 4  # character index in the original line
                if cursor_row < max_buffer_lines:
                    line = buffer_lines[cursor_row]
                    # Measure exact x position of cursor character
                    cursor_x = mono_font.measure(line[:cursor_col])
                    cx = gx + cursor_x
                    cy = gy + cursor_row * line_h
                    char_w = mono_font.measure(line[cursor_col:cursor_col+1]) or mono_font.measure("i")
                    c.create_rectangle(cx, cy, cx + char_w, cy + line_h - 1,
                                       fill=CYAN, outline="")
                    # Do NOT add extra text for cursor letter; line text already shows it

                # Extra empty-row backgrounds below buffer (no text, just tilde-less rows)
                # Add 2 more row rects below the last buffer line if space permits
                extra_rows = 2
                for i in range(extra_rows):
                    y = gy + max_buffer_lines * line_h + i * line_h
                    if y + line_h <= oy + box_h - pad_y - status_h:
                        c.create_rectangle(gx, y, gx + max_text_w, y + line_h - 1,
                                           fill=blend(PANEL, color, 0.05), outline="")

                # Status line below buffer, anchor nw, strictly inside frame
                status_y = gy + max_buffer_lines * line_h + extra_rows * line_h
                if status_y + status_h <= oy + box_h - pad_y:
                    status_w = status_font.measure(status_text)
                    if status_w > max_text_w:
                        # Truncate status with ellipsis
                        ellipsis = "\u2026"
                        ellipsis_w = status_font.measure(ellipsis)
                        lo, hi = 0, len(status_text)
                        while lo < hi:
                            mid = (lo + hi + 1) // 2
                            if status_font.measure(status_text[:mid]) + ellipsis_w <= max_text_w:
                                lo = mid
                            else:
                                hi = mid - 1
                        status_text = status_text[:lo] + ellipsis
                    c.create_text(gx, status_y, text=status_text, fill=AMBER, anchor="nw",
                                  font=status_font_spec)
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
            elif gid == "breakout":
                ox, oy, box_w, box_h = _draw_game_frame(c, ww, hh, color)
                # Brick rows spanning frame width
                brick_rows = 5
                brick_cols = 14
                cell_w = box_w // brick_cols
                cell_h = (box_h // 2) // brick_rows  # bricks in upper half
                bx0 = ox + (box_w - brick_cols * cell_w) // 2
                by0 = oy + 4

                # Color variations per row
                row_colors = [
                    blend(PURPLE, RED, 0.6),
                    blend(PURPLE, AMBER, 0.5),
                    blend(PURPLE, CYAN, 0.4),
                    blend(PURPLE, GREEN, 0.4),
                    blend(PURPLE, TEXT, 0.3),
                ]

                for row in range(brick_rows):
                    for col in range(brick_cols):
                        # Skip some bricks to show gaps (like broken ones)
                        if (row == 2 and col in (3, 4, 5)) or (row == 4 and col in (8, 9)):
                            continue
                        bx = bx0 + col * cell_w
                        by = by0 + row * cell_h
                        c.create_rectangle(bx + 1, by + 1, bx + cell_w - 1, by + cell_h - 1,
                                           fill=row_colors[row], outline=blend(row_colors[row], TEXT, 0.3))

                # Paddle near bottom
                paddle_w = box_w // 3
                paddle_h = max(4, cell_h // 2)
                px = ox + (box_w - paddle_w) // 2
                py = oy + box_h - paddle_h - 6
                c.create_rectangle(px, py, px + paddle_w, py + paddle_h,
                                   fill=CYAN, outline=blend(CYAN, TEXT, 0.4), width=1)

                # Ball in flight
                ball_r = max(3, cell_h // 2)
                ball_x = ox + box_w // 2 + 10
                ball_y = py - 20
                c.create_oval(ball_x - ball_r, ball_y - ball_r,
                              ball_x + ball_r, ball_y + ball_r,
                              fill=AMBER, outline=blend(AMBER, TEXT, 0.5), width=1)

                # Three lives indicators (small circles top-right)
                for i in range(3):
                    lx = ox + box_w - 18 - i * 14
                    ly = oy + 8
                    c.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill=RED, outline="")
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
            from stamina import zen_mode
            zen_mode.exit_zen(self.game)
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
            # Ctrl+O приходит из cockpit._on_key; здесь хелпер для прямых вызовов.
            from stamina import zen_mode
            if zen_mode.handle_key(e, widget=self.game, allow_esc=False):
                return
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
