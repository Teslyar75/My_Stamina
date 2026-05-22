"""Виджеты в стиле WPF: скруглённые клавиши, слайдер-прогресс, строка набора."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

from stamina.theme import (
    FONT_SEQUENCE,
    KEY_RADIUS,
    MUTED_FG,
    PANEL_BG,
    SEQUENCE_BORDER,
    SEQUENCE_DONE_BG,
    SEQUENCE_REMAINING_BG,
    TEXT_FG,
    WINDOW_BG,
)


def _rounded_rectangle(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: int,
    **kwargs,
) -> int:
    """Полигон со сглаживанием — визуально соответствует Border CornerRadius=10."""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedKey(tk.Canvas):
    """Клавиша со скруглёнными углами — аналог стиля Button из MainWindow.xaml."""

    def __init__(
        self,
        master: tk.Misc,
        label: str,
        color: str,
        *,
        font: tuple[str, int] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            highlightthickness=0,
            bd=0,
            bg=WINDOW_BG,
            **kwargs,
        )
        self._label = label
        self._color = color
        self._font = font
        self.bind("<Configure>", self._redraw)

    def set_color(self, color: str) -> None:
        if color == self._color:
            return
        self._color = color
        self._redraw()

    def _pick_font(self, width: int, height: int) -> tuple[str, int]:
        if self._font is not None:
            return self._font
        label = self._label
        base = min(width, height)
        if base < 28:
            size = 9
        elif len(label) >= 6:
            size = 10
        elif len(label) >= 3:
            size = 12
        else:
            size = 16
        return ("Segoe UI", size)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 4)
        h = max(self.winfo_height(), 4)
        pad = 1
        r = min(KEY_RADIUS, h // 4, w // 4)
        _rounded_rectangle(
            self, pad, pad, w - pad, h - pad, r,
            fill=self._color, outline=self._color,
        )
        self.create_text(
            w / 2,
            h / 2,
            text=self._label,
            fill=TEXT_FG,
            font=self._pick_font(w, h),
        )


class StatsPanel(tk.Frame):
    """Горизонтальная полоска статистики над строкой набора:

    ``00:00   ·   85 симв./мин   ·   ошибок: 3``
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=WINDOW_BG, **kwargs)
        self._cpm = tk.StringVar(value="0 симв./мин")
        self._err = tk.StringVar(value="ошибок: 0")
        self._time = tk.StringVar(value="00:00")

        sep_kwargs = dict(text="  ·  ", bg=WINDOW_BG, fg=MUTED_FG,
                          font=("Segoe UI", 10))

        tk.Label(
            self, textvariable=self._time,
            font=("Consolas", 12, "bold"),
            fg=TEXT_FG, bg=WINDOW_BG,
        ).pack(side=tk.LEFT, padx=(18, 0))
        tk.Label(self, **sep_kwargs).pack(side=tk.LEFT)
        tk.Label(
            self, textvariable=self._cpm,
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_FG, bg=WINDOW_BG,
        ).pack(side=tk.LEFT)
        tk.Label(self, **sep_kwargs).pack(side=tk.LEFT)
        tk.Label(
            self, textvariable=self._err,
            font=("Segoe UI", 11),
            fg=MUTED_FG, bg=WINDOW_BG,
        ).pack(side=tk.LEFT)

    def update_stats(self, *, cpm: float, errors: int, elapsed: float) -> None:
        self._cpm.set(f"{int(round(cpm))} симв./мин")
        self._err.set(f"ошибок: {errors}")
        m, s = divmod(int(elapsed), 60)
        self._time.set(f"{m:02d}:{s:02d}")

    def reset(self) -> None:
        self._cpm.set("0 симв./мин")
        self._err.set("ошибок: 0")
        self._time.set("00:00")


class SequencePanel(tk.Canvas):
    """Двухцветная полоса набора с **фиксированной** границей по центру.

    Граница цветов всегда стоит в середине панели; сам текст «проезжает»
    под ней по мере набора. Слева от границы — бирюзовый цвет уже
    набранных символов, справа — серый цвет того, что ещё предстоит.
    """

    HEIGHT = 60
    LEFT_PAD = 18
    BAR_VERT_PAD = 6

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(
            master,
            height=self.HEIGHT,
            bg=PANEL_BG,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self._font_spec = FONT_SEQUENCE
        self._font = tkfont.Font(family=FONT_SEQUENCE[0], size=FONT_SEQUENCE[1])
        self._char_w = max(self._font.measure("m"), 1)
        self._line_h = self._font.metrics("linespace")
        self._text = ""
        self._index = 0
        self._active = False
        self._placeholder = ""
        self.bind("<Configure>", lambda _e: self._redraw())

    # -- Публичное API ---------------------------------------------

    def show_placeholder(self, text: str) -> None:
        """Серый подсказывающий текст; цветная полоса не рисуется."""
        self._placeholder = text
        self._active = False
        self._redraw()

    def set_progress(self, text: str, index: int) -> None:
        """Активный режим набора: цветная полоса с границей в центре."""
        self._text = text
        self._index = max(0, min(index, len(text)))
        self._active = True
        self._placeholder = ""
        self._redraw()

    # -- Отрисовка --------------------------------------------------

    def _redraw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 4)
        h = max(self.winfo_height(), self.HEIGHT)

        if not self._active:
            self.create_text(
                self.LEFT_PAD, h // 2,
                anchor="w",
                text=self._placeholder,
                font=self._font_spec,
                fill=TEXT_FG,
            )
            return

        avail_w = max(w - self.LEFT_PAD * 2, self._char_w)
        n_visible = max(2, avail_w // self._char_w)
        mid = n_visible // 2  # позиция границы (фиксированно — центр)

        # Хотим, чтобы text[index] оказался в позиции `mid` (первый
        # ненабранный символ — сразу справа от границы). Поэтому текст
        # начинается с index-mid; если уходим за начало/конец строки —
        # дополняем пробелами, чтобы граница не «дрожала».
        start = self._index - mid
        left_pad = max(0, -start)
        real_start = max(0, start)
        right_chars = n_visible - left_pad
        real_end = min(len(self._text), real_start + right_chars)
        body = self._text[real_start:real_end]
        right_pad = n_visible - left_pad - len(body)
        shown = " " * left_pad + body + " " * max(right_pad, 0)
        cut = mid  # граница всегда в центре видимой полосы

        x0 = self.LEFT_PAD
        y_top = (h - self._line_h) // 2 - self.BAR_VERT_PAD
        y_bot = y_top + self._line_h + self.BAR_VERT_PAD * 2

        # Левая (бирюзовая) часть — уже набрано.
        self.create_rectangle(
            x0, y_top,
            x0 + cut * self._char_w, y_bot,
            fill=SEQUENCE_DONE_BG, outline=SEQUENCE_DONE_BG,
        )
        # Правая (серая) часть — осталось.
        self.create_rectangle(
            x0 + cut * self._char_w, y_top,
            x0 + n_visible * self._char_w, y_bot,
            fill=SEQUENCE_REMAINING_BG, outline=SEQUENCE_REMAINING_BG,
        )
        # Тонкая рамка вокруг всей полосы.
        self.create_rectangle(
            x0, y_top,
            x0 + n_visible * self._char_w, y_bot,
            outline=SEQUENCE_BORDER, width=1,
        )
        # Текст поверх; моноширинный шрифт = ширина каждого символа = self._char_w.
        self.create_text(
            x0, h // 2,
            anchor="w",
            text=shown,
            font=self._font_spec,
            fill=TEXT_FG,
        )
