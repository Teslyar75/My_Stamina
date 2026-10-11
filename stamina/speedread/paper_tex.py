"""Фактура бумаги старых книг для читалки (кэш PhotoImage)."""
from __future__ import annotations

import random
from pathlib import Path

import tkinter as tk

_ASSET = Path(__file__).resolve().parent.parent / "assets" / "book_paper.jpg"
_cache: dict[tuple, tk.PhotoImage] = {}
_base_rgb = None  # PIL Image cache


def _load_base():
    global _base_rgb
    if _base_rgb is not None:
        return _base_rgb
    try:
        from PIL import Image
        if _ASSET.exists():
            _base_rgb = Image.open(_ASSET).convert("RGB")
            return _base_rgb
    except Exception:  # noqa: BLE001
        pass
    return None


def _procedural(w: int, h: int, variant: str):
    """Запасная текстура без файла: шум + волокна + пятна."""
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
    if variant == "dark":
        base = (22, 26, 34)
        stain = (40, 36, 30)
    elif variant == "sepia":
        base = (220, 198, 158)
        stain = (170, 130, 80)
    else:
        base = (238, 226, 200)
        stain = (190, 150, 100)
    im = Image.new("RGB", (w, h), base)
    px = im.load()
    rng = random.Random(42 + w + h * 7 + hash(variant) % 997)
    for y in range(h):
        for x in range(w):
            n = rng.randint(-14, 14)
            r, g, b = base
            px[x, y] = (max(0, min(255, r + n)),
                        max(0, min(255, g + n - 1)),
                        max(0, min(255, b + n - 2)))
    draw = ImageDraw.Draw(im)
    for _ in range(max(8, w * h // 40000)):
        x0 = rng.randint(0, w)
        y0 = rng.randint(0, h)
        rw = rng.randint(w // 20, w // 5)
        rh = rng.randint(h // 30, h // 8)
        alpha = rng.randint(8, 28)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        col = (*stain, alpha)
        od.ellipse([x0 - rw, y0 - rh, x0 + rw, y0 + rh], fill=col)
        im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    # тонкие волокна
    draw = ImageDraw.Draw(im)
    for _ in range(max(20, w // 8)):
        x0, y0 = rng.randint(0, w), rng.randint(0, h)
        x1 = x0 + rng.randint(-w // 3, w // 3)
        y1 = y0 + rng.randint(-2, 2)
        c = tuple(max(0, min(255, v + rng.randint(-20, 10))) for v in stain)
        draw.line([(x0, y0), (x1, y1)], fill=c, width=1)
    im = im.filter(ImageFilter.GaussianBlur(radius=0.6))
    return ImageEnhance.Contrast(im).enhance(1.05)


def _tint(im, variant: str):
    from PIL import ImageEnhance, ImageOps
    if variant == "paper":
        return ImageEnhance.Color(im).enhance(0.95)
    if variant == "sepia":
        g = ImageOps.grayscale(im).convert("RGB")
        # тёплый сепия
        r, gch, b = g.split()
        from PIL import Image
        r = r.point(lambda v: min(255, int(v * 1.05 + 18)))
        gch = gch.point(lambda v: min(255, int(v * 0.95 + 8)))
        b = b.point(lambda v: max(0, int(v * 0.75)))
        out = Image.merge("RGB", (r, gch, b))
        return ImageEnhance.Contrast(out).enhance(1.05)
    # dark: затемнить и чуть охладить
    from PIL import ImageEnhance
    dark = ImageEnhance.Brightness(im).enhance(0.22)
    return ImageEnhance.Color(dark).enhance(0.35)


def paper_photo(master: tk.Misc, w: int, h: int, variant: str = "paper") -> tk.PhotoImage | None:
    """Готовый PhotoImage фактуры под размер страницы (с кэшем)."""
    w = max(40, int(w))
    h = max(40, int(h))
    # округлить к шагу 32 — меньше пересозданий при resize
    wk, hk = (w // 32) * 32, (h // 32) * 32
    wk, hk = max(64, wk), max(64, hk)
    key = (wk, hk, variant)
    if key in _cache:
        return _cache[key]
    try:
        from PIL import Image, ImageTk
    except Exception:  # noqa: BLE001
        return None
    base = _load_base()
    if base is None:
        im = _procedural(wk, hk, variant)
    else:
        # cover-crop
        bw, bh = base.size
        scale = max(wk / bw, hk / bh)
        nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
        # BILINEAR быстрее LANCZOS; размер кэшируем по шагу 32
        im = base.resize((nw, nh), Image.BILINEAR)
        x0 = max(0, (nw - wk) // 2)
        y0 = max(0, (nh - hk) // 2)
        im = im.crop((x0, y0, x0 + wk, y0 + hk))
        im = _tint(im, variant)
    # не растягивать до (w,h): разница ≤31px, края зальёт фон страницы
    photo = ImageTk.PhotoImage(im, master=master)
    _cache[key] = photo
    if len(_cache) > 12:
        for k in list(_cache.keys())[:4]:
            if k != key:
                del _cache[k]
    return photo
