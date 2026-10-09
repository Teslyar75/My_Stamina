"""«ЖИВОЙ КОСМОС» (прототип, только МОСТИК).

Фон мостика — живая сцена, которую рисует Pillow: звёзды в 3 слоях с параллаксом, кометы с хвостами,
далёкие планеты, астероиды. В открытом «окне» (иллюминатор с текстом и просветы между панелями) сцена
резкая; под панелями — размытая, затемнённая и подкрашенная в цвет панели («матовое стекло»).
Текст и кнопки рисуются поверх и остаются чёткими.

Бюджет для слабых ноутбуков:
- резкий иллюминатор: до 24 к/с («полный»), 12 к/с («лёгкий»); во время печати — вдвое реже;
- матовое стекло: 5 к/с / 2 к/с (просветы — вдвое реже), размытие считается на картинке в 1/4 размера;
- мало объектов, планеты — заранее нарисованные спрайты; кадр пропускается, если предыдущий был долгим;
- «уменьшение движения» Windows → один неподвижный кадр.
Настройка `living_space`: "off" | "light" | "full".
"""
from __future__ import annotations

import math
import random
import sys
import time
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:  # Pillow необязателен: без него режим просто недоступен
    Image = None

from stamina.theme import BG, CYAN, PANEL

MODES = ("off", "light", "full")
MODE_TITLES = {"off": "ВЫКЛ", "light": "ЛЁГКИЙ", "full": "ПОЛНЫЙ"}
PROFILE = {   # к/с резкого окна, к/с стекла, звёзд, комет, астероидов
    "light": dict(fps=12, glass_fps=2, stars=90, comets=1, rocks=3, planets=1),
    "full": dict(fps=24, glass_fps=5, stars=170, comets=2, rocks=6, planets=2),
}


def available() -> bool:
    return Image is not None


def reduced_motion() -> bool:
    """Windows: «Показывать анимацию в Windows» выключено → True."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        val = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(val), 0)  # SPI_GETCLIENTAREAANIMATION
        return not bool(val.value)
    except Exception:  # noqa: BLE001
        return False


def _rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


# ============================================================================ сцена
class Scene:
    """Мир в единицах экрана; объекты летят справа налево (корабль движется вперёд)."""

    def __init__(self, w: int, h: int, mode: str = "full", seed: int = 5) -> None:
        self.w, self.h = max(w, 50), max(h, 50)
        self.p = PROFILE[mode]
        self.rng = random.Random(seed)
        r = self.rng
        self.stars = [[r.uniform(0, self.w), r.uniform(0, self.h), r.choice((1, 1, 1, 2, 2, 3)),
                       r.uniform(0.4, 1.0)] for _ in range(self.p["stars"])]
        self.comets = [self._new_comet(initial=True) for _ in range(self.p["comets"])]
        self.rocks = [self._new_rock(initial=True) for _ in range(self.p["rocks"])]
        self.planets = []
        specs = [((0.78, 0.30), 0.30, (70, 120, 200), (30, 40, 90), True),
                 ((0.18, 0.78), 0.12, (210, 140, 80), (90, 40, 30), False)]
        for i in range(self.p["planets"]):
            (fx, fy), fr, c1, c2, ring = specs[i]
            rad = int(self.h * fr)
            self.planets.append([fx * self.w, fy * self.h, self._planet_sprite(rad, c1, c2, ring), 0.6 + i * 0.5])
        self.base = self._base()
        self.t = 0.0

    # -- заготовки
    def _base(self):
        """Фон: глубокий космос + две слабые туманности (рисуется один раз)."""
        small = Image.new("RGB", (max(8, self.w // 8), max(8, self.h // 8)), _rgb(BG))
        d = ImageDraw.Draw(small)
        sw, sh = small.size
        for (fx, fy, fr, col) in ((0.3, 0.35, 0.45, (20, 40, 80)), (0.75, 0.7, 0.35, (45, 20, 60))):
            for k in range(6, 0, -1):
                rr = fr * sw * k / 6
                a = (7 - k) / 7
                c = tuple(int(_rgb(BG)[j] + (col[j] - _rgb(BG)[j]) * a * 0.5) for j in range(3))
                d.ellipse((fx * sw - rr, fy * sh - rr * 0.6, fx * sw + rr, fy * sh + rr * 0.6), fill=c)
        return small.filter(ImageFilter.GaussianBlur(3)).resize((self.w, self.h), Image.BILINEAR)

    def _planet_sprite(self, rad: int, c1, c2, ring: bool):
        size = rad * 2 + (rad if ring else 0) + 4
        im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx = cy = size
        R = rad * 2
        for k in range(24, 0, -1):          # шар с терминатором
            t = k / 24
            col = tuple(int(c2[j] + (c1[j] - c2[j]) * (1 - t) ** 0.7) for j in range(3))
            off = R * (1 - t) * 0.45
            d.ellipse((cx - R * t - off, cy - R * t - off, cx + R * t - off, cy + R * t - off), fill=col + (255,))
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)
        im.putalpha(mask)
        glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((cx - R - 6, cy - R - 6, cx + R + 6, cy + R + 6), outline=c1 + (90,), width=5)
        im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)), im)
        if ring:
            rl = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(rl).ellipse((cx - R * 1.7, cy - R * 0.38, cx + R * 1.7, cy + R * 0.38),
                                       outline=(200, 210, 230, 140), width=max(2, R // 18))
            im = Image.alpha_composite(im, rl)
        return im.resize((size, size), Image.LANCZOS)

    def _new_comet(self, initial=False):
        r = self.rng
        x = r.uniform(0.2, 1.0) * self.w if initial else self.w + r.uniform(50, 400)
        return [x, r.uniform(0.05, 0.7) * self.h, r.uniform(14, 30), r.uniform(4, 10), r.uniform(60, 120)]

    def _new_rock(self, initial=False):
        r = self.rng
        x = r.uniform(0, self.w) if initial else self.w + r.uniform(20, 300)
        n = r.randint(6, 9)
        size = r.uniform(4, 12)
        shape = [(math.cos(2 * math.pi * k / n) * size * r.uniform(0.6, 1.1),
                  math.sin(2 * math.pi * k / n) * size * r.uniform(0.6, 1.1)) for k in range(n)]
        return [x, r.uniform(0, self.h), r.uniform(25, 60), shape, r.uniform(0, 6.28), r.uniform(-0.8, 0.8)]

    # -- шаг и кадр
    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        w = self.w
        for s in self.stars:
            s[0] -= s[2] * 9 * warp * dt
            if s[0] < -4:
                s[0] = w + self.rng.uniform(0, 30)
                s[1] = self.rng.uniform(0, self.h)
        for c in self.comets:
            c[0] -= c[2] * warp * dt
            c[1] += c[3] * dt * 0.25
            if c[0] < -c[4] * 2:
                c[:] = self._new_comet()
        for rk in self.rocks:
            rk[0] -= rk[2] * warp * dt
            rk[4] += rk[5] * dt
            if rk[0] < -20:
                rk[:] = self._new_rock()
        for p in self.planets:
            p[0] -= p[3] * warp * dt
            if p[0] < -p[2].width:
                p[0] = w + p[2].width

    def render(self, box: tuple[int, int, int, int] | None = None):
        """Кадр всей сцены или только области box=(x1, y1, x2, y2)."""
        x1, y1, x2, y2 = box or (0, 0, self.w, self.h)
        im = self.base.crop((x1, y1, x2, y2))
        for px_, py, spr, _v in self.planets:
            im.paste(spr, (int(px_ - spr.width / 2 - x1), int(py - spr.height / 2 - y1)), spr)
        d = ImageDraw.Draw(im)
        for x, y, layer, b in self.stars:
            if x1 - 6 <= x <= x2 and y1 <= y <= y2:
                v = int((80 + 60 * layer) * b)
                col = (v, min(255, v + 15), min(255, v + 30))
                if layer == 3:
                    d.line((x - x1, y - y1, x - x1 + 3, y - y1), fill=col, width=2)
                else:
                    d.point((x - x1, y - y1), fill=col)
        for x, y, _sp, _dr, tail in self.comets:
            if x - x1 > -tail * 1.5 and x - x1 < (x2 - x1) + 10:
                hx, hy = x - x1, y - y1
                for k in range(12, 0, -1):     # хвост: от тусклого к яркому
                    t = k / 12
                    a = 1 - t
                    col = (int(60 + 140 * a), int(150 + 90 * a), int(190 + 60 * a))
                    d.line((hx + tail * t, hy - tail * t * 0.12, hx + tail * (t - 1 / 12), hy - tail * (t - 1 / 12) * 0.12),
                           fill=col, width=max(1, int(4 * a)))
                d.ellipse((hx - 2.5, hy - 2.5, hx + 2.5, hy + 2.5), fill=(235, 250, 255))
        for x, y, _sp, shape, ang, _rot in self.rocks:
            if x1 - 15 <= x <= x2 + 15 and y1 - 15 <= y <= y2 + 15:
                ca, sa = math.cos(ang), math.sin(ang)
                pts = [(x - x1 + px_ * ca - py * sa, y - y1 + px_ * sa + py * ca) for px_, py in shape]
                d.polygon(pts, fill=(58, 54, 62), outline=(110, 104, 112))
        return im


def frost_small(im, tint: str = PANEL, amount: float = 0.76):
    """Матовое стекло в 1/4 размера: reduce + два box-размытия (≈ гаусс) + подкраска в цвет панели."""
    small = im.reduce(4).filter(ImageFilter.BoxBlur(3)).filter(ImageFilter.BoxBlur(3))
    return Image.blend(small, Image.new("RGB", small.size, _rgb(tint)), amount)


def frost(im, tint: str = PANEL, amount: float = 0.76):
    """Матовое стекло в полный размер (для макетов и тестов)."""
    return frost_small(im, tint, amount).resize(im.size, Image.BILINEAR)


def frost_crop(fs, box):
    """Область box (в полных координатах) из уменьшенного стекла, растянутая до её размера."""
    x1, y1, x2, y2 = box
    return fs.resize((x2 - x1, y2 - y1), Image.BILINEAR, box=(x1 / 4, y1 / 4, x2 / 4, y2 / 4))


# ============================================================================ контроллер
class LivingSpace:
    """Подключается к мостику: фон-холст за панелями + картинка-подложка в каждой «стеклянной» панели."""

    TAG = "ls_bg"

    def __init__(self, bridge: tk.Misc, mode: str = "full") -> None:
        self.bridge = bridge
        self.mode = mode
        self.scene: Scene | None = None
        self.sharp: list[tk.Canvas] = []
        self.glass: list[tk.Canvas] = []
        self._photos: dict[str, object] = {}
        self._last = self._last_glass = 0.0
        self._last_step = time.monotonic()
        self._frame_ms = 0.0
        self.static = reduced_motion()
        self._static_done = False
        self.bg = tk.Canvas(bridge, highlightthickness=0, bd=0, bg=BG)
        self.stats = {"frames": 0, "glass": 0, "render_ms": 0.0}

    # -- регистрация
    def add_sharp(self, c: tk.Canvas) -> None:
        self.sharp.append(c)

    def add_glass(self, c: tk.Canvas) -> None:
        self.glass.append(c)

    def enable(self) -> None:
        self.bg.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lower(self.bg)

    def disable(self) -> None:
        self.bg.place_forget()
        for c in self.sharp + self.glass:
            try:
                c.delete(self.TAG)
            except tk.TclError:
                pass
        self._photos.clear()
        self.scene = None

    # -- кадр
    def _ensure_scene(self) -> bool:
        w, h = self.bridge.winfo_width(), self.bridge.winfo_height()
        if w < 100 or h < 100:
            return False
        if self.scene is None or (self.scene.w, self.scene.h) != (w, h):
            self.scene = Scene(w, h, self.mode)
            self._last = self._last_glass = 0.0
            self._static_done = False
        return True

    def _offset(self, c: tk.Canvas) -> tuple[int, int, int, int]:
        x = c.winfo_rootx() - self.bridge.winfo_rootx()
        y = c.winfo_rooty() - self.bridge.winfo_rooty()
        return x, y, x + c.winfo_width(), y + c.winfo_height()

    def _put(self, c: tk.Canvas, key: str, im) -> None:
        ph = self._photos.get(key)
        if ph is None or (ph.width(), ph.height()) != im.size:
            ph = ImageTk.PhotoImage(im)
            self._photos[key] = ph
        else:
            ph.paste(im)
        if not c.find_withtag(self.TAG):
            c.create_image(0, 0, anchor="nw", image=ph, tags=self.TAG)
        else:
            c.itemconfigure(self.TAG, image=ph)
        c.tag_lower(self.TAG)

    def _clip(self, box):
        x1, y1, x2, y2 = box
        return max(0, x1), max(0, y1), min(self.scene.w, x2), min(self.scene.h, y2)

    def tick(self, *, typing: bool, warp: float = 1.0) -> bool:
        """Вызывается таймером мостика. True — нужен быстрый таймер."""
        if self.mode == "off" or not self._ensure_scene():
            return False
        now = time.monotonic()
        prof = PROFILE[self.mode]
        fps = prof["fps"] / (2 if typing else 1)
        if self.static:
            if self._static_done:
                return False
            fps = 1000
        if now - self._last < 1 / fps or (self._frame_ms > 1000 / fps * 0.8 and now - self._last < 2 / fps):
            return True
        t0 = time.perf_counter()
        dt = min(0.2, now - self._last_step)
        self._last_step = now
        if not self.static:
            self.scene.step(dt, 0.6 + 0.4 * warp)
        self._last = now
        for i, c in enumerate(self.sharp):          # резкие окна
            if c.winfo_ismapped():
                box = self._clip(self._offset(c))
                if box[2] - box[0] > 4 and box[3] - box[1] > 4:
                    self._put(c, f"s{i}", self.scene.render(box))
        for i, c in enumerate(self.glass):          # виджет мог стереть всё (delete("all")) — вернуть подложку
            ph = self._photos.get(f"g{i}")
            if ph is not None and not c.find_withtag(self.TAG):
                c.create_image(0, 0, anchor="nw", image=ph, tags=self.TAG)
                c.tag_lower(self.TAG)
        if self.static or now - self._last_glass >= 1 / prof["glass_fps"]:
            self._last_glass = now
            full = self.scene.render()
            if self.stats["glass"] % 2 == 0 or self.static:   # просветы между панелями — вдвое реже
                self._put(self.bg, "bg", full)
            fs = frost_small(full)
            for i, c in enumerate(self.glass):
                if c.winfo_ismapped():
                    box = self._clip(self._offset(c))
                    if box[2] - box[0] > 4 and box[3] - box[1] > 4:
                        self._put(c, f"g{i}", frost_crop(fs, box))
            self.stats["glass"] += 1
        self._frame_ms = (time.perf_counter() - t0) * 1000
        self.stats["frames"] += 1
        self.stats["render_ms"] += self._frame_ms
        self._static_done = self.static
        return True


def edge_glow(canvas: tk.Canvas, pts, tag: str = "frame") -> None:
    """Голубое свечение кромки стеклянной панели (2 полупрозрачных «слоя» линий)."""
    from stamina.theme import blend
    canvas.create_polygon(pts, fill="", outline=blend(PANEL, CYAN, 0.35), width=4, tags=tag)
    canvas.create_polygon(pts, fill="", outline=blend(PANEL, CYAN, 0.65), width=1, tags=tag)
