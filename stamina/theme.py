"""Палитра, шрифты и масштаб интерфейса «пульт космического корабля».

Цвета подобраны под тёмный HUD: глубокий космос + неоновый циан и янтарь.
В Tkinter нет прозрачности, поэтому «свечение» рисуется несколькими
контурами заранее смешанных цветов (см. :func:`blend`).
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

# --- Фон и панели ------------------------------------------------------
BG = "#03060C"          # глубокий космос
BG2 = "#060C17"
PANEL = "#081221"       # заливка панелей
PANEL_HI = "#0D1C33"    # наведение / активная панель
LINE = "#15314D"        # тонкие рамки
LINE_HI = "#1F4F7A"

# --- Неон ----------------------------------------------------------------
CYAN = "#00E5FF"
CYAN_DIM = "#0B7285"
CYAN_DEEP = "#06303B"
AMBER = "#FFB000"
AMBER_DIM = "#7A5300"
RED = "#FF3B5C"
RED_DIM = "#5E1426"
GREEN = "#3DFF8A"
GREEN_DIM = "#155E36"
PURPLE = "#B76BFF"

TEXT = "#D6F4FF"
MUTED = "#6F90AB"
FAINT = "#2B4762"

# --- Зоны пальцев (неоновые версии цветов исходного Stamina) ------------
ZONE_PINKY = "#FF4FA3"
ZONE_RING = "#FFD84A"
ZONE_MIDDLE = "#4CFF8F"
ZONE_L_INDEX = "#2ED8FF"
ZONE_R_INDEX = "#B76BFF"
ZONE_THUMB = "#8FA6BF"
ZONE_MOD = "#4A6580"

# --- Шрифты (определяются при запуске, есть запасные варианты) ----------
HUD_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

# Масштаб: 1.0 при 96 DPI, 1.25 при 120 DPI и т.д.
S = 1.0


def px(value: float) -> int:
    """Пиксели с учётом масштаба экрана."""
    return int(round(value * S))


def init(root: tk.Tk) -> None:
    """Определить масштаб и доступные шрифты. Вызывать один раз."""
    global S, HUD_FAMILY, MONO_FAMILY
    try:
        S = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
    except tk.TclError:
        S = 1.0
    families = set(tkfont.families(root))
    for name in ("Bahnschrift", "Segoe UI", "Noto Sans", "DejaVu Sans", "Ubuntu", "Liberation Sans", "Cantarell", "Helvetica"):
        if name in families:
            HUD_FAMILY = name
            break
    for name in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Noto Sans Mono", "Ubuntu Mono", "Liberation Mono", "Courier New"):
        if name in families:
            MONO_FAMILY = name
            break


def font(size: int, bold: bool = False, mono: bool = False) -> tuple:
    family = MONO_FAMILY if mono else HUD_FAMILY
    return (family, size, "bold") if bold else (family, size)


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def blend(c1: str, c2: str, t: float) -> str:
    """Смешать цвета: t=0 → c1, t=1 → c2."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _rgb(c1)
    r2, g2, b2 = _rgb(c2)
    return "#{:02X}{:02X}{:02X}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


def chamfer(x1: float, y1: float, x2: float, y2: float, c: float) -> list[float]:
    """Точки прямоугольника со срезанными углами (левый верх и правый низ)."""
    return [x1 + c, y1, x2, y1, x2, y2 - c, x2 - c, y2, x1, y2, x1, y1 + c]


def heat_color(rate: float) -> str:
    """Цвет тепловой карты: 0 → спокойный, 1 → ярко-красный."""
    if rate <= 0:
        return blend(PANEL, GREEN_DIM, 0.6)
    if rate < 0.5:
        return blend(GREEN_DIM, AMBER, rate * 2)
    return blend(AMBER, RED, (rate - 0.5) * 2)
