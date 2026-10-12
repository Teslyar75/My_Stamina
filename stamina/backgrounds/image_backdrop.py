"""Фон скина: cover-картинка из docs/skins/images/<id>/bg*.jpg + лёгкая анимация.

Не заменяет LivingSpace на мостике целиком — используется как запасной/доп.
слой, если Pillow есть. Без Pillow — тихий no-op.
"""

from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path

from stamina import theme

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:
    Image = None  # type: ignore


class ImageBackdrop:
    def __init__(self, theme_id: str) -> None:
        self.theme_id = theme_id
        self.canvas: tk.Canvas | None = None
        self._photo = None
        self._job = None
        self._particles: list[list[float]] = []
        self._speed = 1.0
        self._w = 0
        self._h = 0
        self._base = None

    def _image_path(self) -> Path | None:
        root = Path(__file__).resolve().parents[2]
        folder = root / "docs" / "skins" / "images" / self.theme_id
        if not folder.is_dir():
            return None
        for name in ("bg1.jpg", "bg2.jpg", "bg1.png", "bg2.png"):
            p = folder / name
            if p.is_file():
                return p
        return None

    def start(self, canvas: tk.Canvas) -> None:
        self.stop()
        self.canvas = canvas
        if Image is None:
            return
        try:
            self._w = max(canvas.winfo_width(), 40)
            self._h = max(canvas.winfo_height(), 40)
        except tk.TclError:
            return
        self._load_base()
        self._particles = [
            [random.uniform(0, self._w), random.uniform(0, self._h),
             random.uniform(0.3, 1.2), random.uniform(1.0, 2.5)]
            for _ in range(28)
        ]
        self._paint()
        self._tick()

    def stop(self) -> None:
        if self._job and self.canvas is not None:
            try:
                self.canvas.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
        self._job = None

    def resize(self, w: int, h: int) -> None:
        self._w, self._h = max(w, 40), max(h, 40)
        self._load_base()
        self._paint()

    def set_speed(self, cpm: float) -> None:
        self._speed = max(0.4, min(3.0, cpm / 200.0)) if cpm > 0 else 0.6

    def _load_base(self) -> None:
        if Image is None:
            return
        path = self._image_path()
        img = None
        if path is not None:
            try:
                src = Image.open(path).convert("RGB")
                # cover
                sw, sh = src.size
                scale = max(self._w / sw, self._h / sh)
                nw, nh = int(sw * scale), int(sh * scale)
                src = src.resize((nw, nh), Image.Resampling.BILINEAR)
                left = max(0, (nw - self._w) // 2)
                top = max(0, (nh - self._h) // 2)
                src = src.crop((left, top, left + self._w, top + self._h))
                # затемнение + лёгкое размытие
                dark = Image.new("RGB", src.size, theme._rgb(theme.BG))
                src = Image.blend(src, dark, 0.62)
                src = src.filter(ImageFilter.GaussianBlur(radius=8))
                img = src
            except OSError:
                img = None
        if img is None:
            img = Image.new("RGB", (self._w, self._h), theme._rgb(theme.BG))
        self._base = img

    def _paint(self) -> None:
        if self.canvas is None or Image is None or self._base is None:
            return
        frame = self._base.copy()
        draw = ImageDraw.Draw(frame)
        accent = theme._rgb(theme.CYAN)
        for x, y, r, _v in self._particles:
            a = max(40, min(180, int(90 + 40 * self._speed)))
            col = (accent[0], accent[1], accent[2], a)
            # RGB без alpha — просто кружки
            c = tuple(int(c * 0.55 + 40) for c in accent)
            rr = max(1, int(r))
            draw.ellipse((x - rr, y - rr, x + rr, y + rr), fill=c)
        self._photo = ImageTk.PhotoImage(frame)
        self.canvas.delete("skin_bg")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo, tags="skin_bg")
        self.canvas.tag_lower("skin_bg")

    def _tick(self) -> None:
        if self.canvas is None:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return
        for p in self._particles:
            p[1] -= 0.35 * self._speed * p[3]  # вверх (пузырьки / лепестки)
            p[0] += random.uniform(-0.4, 0.4) * self._speed
            if p[1] < -5:
                p[1] = self._h + 5
                p[0] = random.uniform(0, self._w)
        self._paint()
        self._job = self.canvas.after(80, self._tick)
