"""Эмблемы пилотов: 16 встроенных (рисуются на Canvas) и своя картинка (avatar.png 256×256)."""
from __future__ import annotations

from stamina.i18n import t

import math
import tkinter as tk
from pathlib import Path

from stamina import pilots, theme
from stamina.theme import AMBER, BG, CYAN, GREEN, PURPLE, RED, blend

ACCENT_COLORS = {"cyan": CYAN, "amber": AMBER, "green": GREEN, "red": RED, "purple": PURPLE}

# ключ, символ, цвет по умолчанию
GLYPHS = [
    ("star", "★", "amber"), ("comet", "☄", "cyan"), ("plane", "✈", "cyan"), ("trident", "♆", "purple"),
    ("bolt", "⚡", "amber"), ("eye", "◉", "red"), ("delta", "▲", "green"), ("crown", "♛", "amber"),
    ("anchor", "⚓", "cyan"), ("moon", "☾", "purple"), ("badge", "✪", "red"), ("atom", "☢", "green"),
    ("spark", "✦", "cyan"), ("hex", "⬡", "amber"), ("knight", "♞", "purple"), ("orbit", "⊕", "green"),
]
GLYPH = {k: (g, c) for k, g, c in GLYPHS}
MAX_FILE = 15 * 1024 * 1024
SIZE = 256


def accent_color(accent: str | None) -> str:
    return ACCENT_COLORS.get(accent or "cyan", CYAN)


def hex_points(cx: float, cy: float, r: float) -> list[float]:
    pts = []
    for i in range(6):
        a = math.radians(60 * i + 30)
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


_img_cache: dict[tuple, tk.PhotoImage] = {}


def _photo(path: Path, size: int) -> tk.PhotoImage | None:
    """avatar.png → PhotoImage нужного размера (Pillow при наличии, иначе subsample)."""
    try:
        key = (str(path), path.stat().st_mtime, size)
    except OSError:
        return None
    if key in _img_cache:
        return _img_cache[key]
    img = None
    try:
        from PIL import Image, ImageTk  # необязательно
        im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        img = ImageTk.PhotoImage(im)
    except Exception:  # noqa: BLE001
        try:
            full = tk.PhotoImage(file=str(path))
            k = max(1, round(full.width() / size))
            img = full.subsample(k, k)
        except tk.TclError:
            return None
    _img_cache[key] = img
    return img


def draw(canvas: tk.Canvas, cx: float, cy: float, size: float, pilot: dict, *, bg: str | None = None,
         tag: str = "avatar") -> None:
    """Нарисовать эмблему пилота в шестиугольнике (size — высота шестиугольника, px)."""
    bg = bg or canvas.cget("bg")
    r = size / 2
    av = pilot.get("avatar") or {}
    col = accent_color(pilot.get("accent"))
    canvas.create_polygon(hex_points(cx, cy, r), fill=blend(BG, col, 0.14), outline="", tags=tag)
    shown = False
    if av.get("kind") == "file":
        img = _photo(pilots.pilot_dir(pilot["id"]) / "avatar.png", int(r * 1.75))
        if img is not None:
            canvas.create_image(cx, cy, image=img, tags=tag)
            # маска: широкий шестиугольный «обод» цвета фона закрывает углы картинки
            canvas.create_polygon(hex_points(cx, cy, r * 1.27), fill="", outline=bg, width=r * 0.52,
                                  joinstyle="miter", tags=tag)
            shown = True
    if not shown:
        g, _c = GLYPH.get(av.get("glyph", "star"), GLYPH["star"])
        canvas.create_text(cx, cy + size * 0.02, text=g, fill=col,
                           font=(theme.HUD_FAMILY, max(6, int(size * 0.42 / theme.S)), "bold"), tags=tag)
    canvas.create_polygon(hex_points(cx, cy, r), fill="", outline=col, width=max(1, int(size / 40)), tags=tag)


def save_image(src: str | Path, pid: str) -> Path:
    """Своя картинка → центральный квадрат → avatar.png 256×256 в папке пилота."""
    src = Path(src)
    if src.stat().st_size > MAX_FILE:
        raise ValueError(t("Файл больше 15 МБ"))
    dest = pilots.pilot_dir(pid) / "avatar.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageOps
        with Image.open(src) as im:
            ImageOps.fit(im.convert("RGBA"), (SIZE, SIZE), Image.LANCZOS).save(dest, "PNG")
        return dest
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        raise ValueError(t("Не удалось прочитать картинку: {0}").format(exc)) from exc
    if src.suffix.lower() not in (".png", ".gif"):
        raise ValueError(t("Без Pillow поддерживаются только PNG и GIF — сохраните картинку как PNG"))
    try:
        full = tk.PhotoImage(file=str(src))
    except tk.TclError as exc:
        raise ValueError(t("Не удалось прочитать картинку: {0}").format(exc)) from exc
    w, h = full.width(), full.height()
    side = min(w, h)
    sq = tk.PhotoImage()
    sq.tk.call(sq, "copy", full, "-from", (w - side) // 2, (h - side) // 2,
               (w - side) // 2 + side, (h - side) // 2 + side)
    k = max(1, side // SIZE)
    out = sq.subsample(k, k)
    out.write(str(dest), format="png")
    return dest
