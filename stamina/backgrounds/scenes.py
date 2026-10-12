"""Сцены фонов скинов с тем же контрактом, что living_space.Scene.

Используются LivingSpace вместо космической сцены, когда theme.background.engine
не `living_space`. CPU-лёгкие: кэш фона, ~10–12 объектов, без numpy.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from stamina import theme as _theme

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk  # noqa: F401
except ImportError:
    Image = None  # type: ignore

FS = 2
STATIC_REFRESH = 2.0
FROST_REFRESH = 6.0


def _rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _blend_rgb(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _load_cover(theme_id: str, w: int, h: int):
    if Image is None:
        return None
    root = Path(__file__).resolve().parents[2]
    folder = root / "docs" / "skins" / "images" / theme_id
    path = None
    for name in ("bg1.jpg", "bg2.jpg", "bg1.png"):
        p = folder / name
        if p.is_file():
            path = p
            break
    if path is None:
        return Image.new("RGB", (w, h), _rgb(_theme.BG))
    try:
        src = Image.open(path).convert("RGB")
        sw, sh = src.size
        scale = max(w / max(sw, 1), h / max(sh, 1))
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        src = src.resize((nw, nh), Image.BILINEAR)
        left, top = max(0, (nw - w) // 2), max(0, (nh - h) // 2)
        src = src.crop((left, top, left + w, top + h))
        dark = Image.new("RGB", src.size, _rgb(_theme.BG))
        return Image.blend(src.filter(ImageFilter.GaussianBlur(7)), dark, 0.58)
    except OSError:
        return Image.new("RGB", (w, h), _rgb(_theme.BG))


def frost_small(im, tint: str | None = None, amount: float = 0.76):
    tint = tint or _theme.PANEL
    small = im.reduce(FS).filter(ImageFilter.BoxBlur(6)).filter(ImageFilter.BoxBlur(6))
    return Image.blend(small, Image.new("RGB", small.size, _rgb(tint)), amount)


class SkinScene:
    """База: фото-фон + частицы. Подклассы меняют step/render_fx."""

    engine = "generic"

    def __init__(self, w: int, h: int, mode: str = "light", theme_id: str = "spaceship",
                 seed: int = 7) -> None:
        self.w, self.h = max(w, 50), max(h, 50)
        self.mode = mode
        self.theme_id = theme_id
        self.rng = random.Random(seed)
        self.t = 0.0
        self.base = _load_cover(theme_id, self.w, self.h) if Image else None
        self._static = None
        self._static_t = -1e9
        self.static_gen = 0
        self._frost = None
        self._frost_t = -1e9
        self.frost_gen = 0
        self.particles: list = []
        self._init_particles()

    def _init_particles(self) -> None:
        n = 40 if self.mode == "full" else 22
        self.particles = [
            [self.rng.uniform(0, self.w), self.rng.uniform(0, self.h),
             self.rng.uniform(0.8, 2.5), self.rng.uniform(0.4, 1.2)]
            for _ in range(n)
        ]

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        for p in self.particles:
            p[1] -= (12 + 20 * warp) * dt * p[3]
            p[0] += math.sin(self.t * 1.3 + p[2]) * 8 * dt
            if p[1] < -4:
                p[1] = self.h + 4
                p[0] = self.rng.uniform(0, self.w)

    def static(self, force: bool = False):
        if self.base is None:
            return None
        if self._static is None or force or self.t - self._static_t >= STATIC_REFRESH:
            self._static = self.base.copy()
            self._draw_static(self._static)
            self._static_t = self.t
            self.static_gen += 1
        return self._static

    def _draw_static(self, im) -> None:
        """Постоянные элементы сцены (переопределяется)."""

    def frost_static(self):
        st = self.static()
        if st is None:
            return None
        if self._frost is None or self.t - self._frost_t >= FROST_REFRESH:
            self._frost = frost_small(st)
            self._frost_t = self.t
            self.frost_gen += 1
        return self._frost

    def moving_boxes(self) -> list[tuple[float, float, float, float]]:
        out = []
        for p in self.particles[:12]:
            x, y = p[0], p[1]
            out.append((x - 10, y - 10, x + 10, y + 10))
        return out

    def render(self, box: tuple[int, int, int, int] | None = None):
        st = self.static()
        if st is None:
            return Image.new("RGB", (self.w, self.h), _rgb(_theme.BG)) if Image else None
        x1, y1, x2, y2 = box or (0, 0, self.w, self.h)
        im = st.crop((x1, y1, x2, y2))
        self._draw_fx(im, x1, y1, x2, y2)
        return im

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        accent = _rgb(_theme.CYAN)
        for p in self.particles:
            x, y = p[0], p[1]
            r = p[2] if len(p) > 2 else 1.5
            if x1 - 6 <= x <= x2 + 6 and y1 - 6 <= y <= y2 + 6:
                rr = max(1, int(r))
                col = _blend_rgb(_rgb(_theme.BG), accent, 0.55)
                d.ellipse((x - x1 - rr, y - y1 - rr, x - x1 + rr, y - y1 + rr), fill=col)

    def frost_frame(self):
        fs = self.frost_static()
        if fs is None:
            return None
        out = fs.copy()
        d = ImageDraw.Draw(out)
        accent = _rgb(_theme.CYAN)
        tint = _rgb(_theme.PANEL)
        for p in self.particles[::2]:
            x, y = p[0], p[1]
            col = _blend_rgb(tint, accent, 0.35)
            d.ellipse((x / FS - 2, y / FS - 2, x / FS + 2, y / FS + 2), fill=col)
        return out


class SonarScene(SkinScene):
    """Батискаф: развёртка сонара + пузырьки."""

    engine = "sonar"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.angle = 0.0
        self.pings: list[list[float]] = []

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        self.angle = (self.angle + dt * (0.7 + 0.5 * warp)) % (math.pi * 2)
        # пузырьки вверх
        for p in self.particles:
            p[1] -= (18 + 25 * warp) * dt * p[3]
            p[0] += math.sin(self.t * 2 + p[2]) * 10 * dt
            if p[1] < -4:
                p[1] = self.h + self.rng.uniform(0, 40)
                p[0] = self.rng.uniform(0, self.w)
        # эхо-кольца
        self.pings = [p for p in self.pings if p[2] < 1.0]
        for p in self.pings:
            p[2] += dt * 0.55
        if self.rng.random() < 0.02 * (0.5 + warp):
            self.pings.append([self.w * 0.72, self.h * 0.55, 0.0])

    def ping(self) -> None:
        """Эхо при верном слове (вызывается с мостика)."""
        self.pings.append([self.w * 0.7, self.h * 0.5, 0.0])

    def _draw_static(self, im) -> None:
        d = ImageDraw.Draw(im)
        cx, cy = int(self.w * 0.72), int(self.h * 0.55)
        teal = _rgb(_theme.CYAN)
        for i in range(1, 5):
            r = int(min(self.w, self.h) * 0.08 * i)
            col = _blend_rgb(_rgb(_theme.BG), teal, 0.15 + 0.08 * i)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=1)

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        cx, cy = self.w * 0.72 - x1, self.h * 0.55 - y1
        teal = _rgb(_theme.CYAN)
        # луч сонара
        reach = min(self.w, self.h) * 0.42
        x2b = cx + math.cos(self.angle) * reach
        y2b = cy + math.sin(self.angle) * reach
        d.line((cx, cy, x2b, y2b), fill=_blend_rgb(_rgb(_theme.BG), teal, 0.7), width=2)
        for k in range(1, 4):
            a = self.angle - 0.08 * k
            d.line((cx, cy, cx + math.cos(a) * reach * (1 - 0.15 * k),
                    cy + math.sin(a) * reach * (1 - 0.15 * k)),
                   fill=_blend_rgb(_rgb(_theme.BG), teal, 0.35 - 0.08 * k), width=1)
        for px_, py, age in self.pings:
            r = age * min(self.w, self.h) * 0.35
            col = _blend_rgb(_rgb(_theme.BG), teal, max(0.05, 0.5 - age * 0.45))
            d.ellipse((px_ - x1 - r, py - y1 - r, px_ - x1 + r, py - y1 + r), outline=col, width=2)
        # пузырьки
        for x, y, r, _v in self.particles:
            if x1 - 6 <= x <= x2 + 6 and y1 - 6 <= y <= y2 + 6:
                rr = max(1, int(r))
                d.ellipse((x - x1 - rr, y - y1 - rr, x - x1 + rr, y - y1 + rr),
                          outline=_blend_rgb(_rgb(_theme.BG), teal, 0.6), width=1)


class GearsScene(SkinScene):
    """Стимпанк: шестерни (скорость ~ warp/WPM) + пар."""

    engine = "gears"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rot = 0.0
        self.gears = [
            (0.22, 0.70, 70, 1.0, 12),
            (0.38, 0.62, 48, -1.45, 9),
            (0.78, 0.28, 90, 0.7, 14),
            (0.88, 0.42, 40, -1.8, 8),
        ]

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        self.rot += dt * (0.4 + 1.2 * warp)
        for p in self.particles:  # пар вверх
            p[1] -= (10 + 15 * warp) * dt * p[3]
            p[0] += math.sin(self.t + p[2]) * 6 * dt
            p[2] *= 1.0  # radius drift
            if p[1] < -4:
                p[1] = self.h * 0.85
                p[0] = self.rng.uniform(self.w * 0.1, self.w * 0.5)

    def _draw_gear(self, d, cx, cy, radius, teeth, ang, col):
        pts = []
        for i in range(teeth * 2):
            a = ang + i * math.pi / teeth
            r = radius * (1.12 if i % 2 == 0 else 0.82)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        if len(pts) >= 3:
            d.polygon(pts, outline=col, fill=_blend_rgb(_rgb(_theme.BG), col, 0.25))
        d.ellipse((cx - radius * 0.25, cy - radius * 0.25,
                   cx + radius * 0.25, cy + radius * 0.25), fill=_rgb(_theme.BG), outline=col)

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        brass = _rgb(_theme.AMBER)
        for fx, fy, rad, mult, teeth in self.gears:
            cx, cy = fx * self.w - x1, fy * self.h - y1
            self._draw_gear(d, cx, cy, rad, teeth, self.rot * mult, brass)
        steam = _blend_rgb(_rgb(_theme.BG), _rgb(_theme.TEXT), 0.25)
        for x, y, r, _v in self.particles:
            if x1 - 8 <= x <= x2 + 8 and y1 - 8 <= y <= y2 + 8:
                rr = max(2, int(r * 2))
                d.ellipse((x - x1 - rr, y - y1 - rr, x - x1 + rr, y - y1 + rr), fill=steam)


class CandlesScene(SkinScene):
    """Скрипторий: мерцание свечей + пылинки."""

    engine = "candles"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.flames = [
            [0.18, 0.78, 1.0],
            [0.82, 0.72, 0.85],
            [0.50, 0.85, 1.1],
        ]

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        for f in self.flames:
            f[2] = 0.75 + 0.35 * abs(math.sin(self.t * 7 + f[0] * 9))
        for p in self.particles:  # пыль в луче
            p[1] += (4 + 6 * warp) * dt * p[3]
            p[0] += math.sin(self.t * 0.7 + p[2]) * 5 * dt
            if p[1] > self.h + 4:
                p[1] = -4
                p[0] = self.rng.uniform(self.w * 0.3, self.w * 0.7)

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        warm = _rgb(_theme.AMBER)
        parchment = _rgb(_theme.PANEL)
        for fx, fy, bright in self.flames:
            cx, cy = fx * self.w - x1, fy * self.h - y1
            for k in range(5, 0, -1):
                rr = 6 * k * bright
                col = _blend_rgb(parchment if _theme.theme_id() == "scriptorium" else _rgb(_theme.BG),
                                 warm, 0.15 * k * bright)
                d.ellipse((cx - rr * 0.5, cy - rr, cx + rr * 0.5, cy + rr * 0.2), fill=col)
            d.ellipse((cx - 3, cy - 8 * bright, cx + 3, cy + 2), fill=warm)
        dust = _blend_rgb(_rgb(_theme.BG), _rgb(_theme.TEXT), 0.45)
        for x, y, r, _v in self.particles:
            if x1 <= x <= x2 and y1 <= y <= y2:
                d.point((x - x1, y - y1), fill=dust)


class CityRainScene(SkinScene):
    """Неон-Сити: дождь + редкие «аэрокары»."""

    engine = "city_rain"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        n = 70 if self.mode == "full" else 40
        self.rain = [
            [self.rng.uniform(0, self.w), self.rng.uniform(0, self.h),
             self.rng.uniform(40, 90), self.rng.uniform(8, 16)]
            for _ in range(n)
        ]
        self.cars = [
            [self.rng.uniform(0, self.w), self.h * (0.35 + 0.15 * i),
             self.rng.choice((-1, 1)) * self.rng.uniform(40, 80)]
            for i in range(3)
        ]

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        for r in self.rain:
            r[1] += r[2] * (0.8 + 0.5 * warp) * dt
            r[0] -= 15 * dt
            if r[1] > self.h:
                r[1] = -10
                r[0] = self.rng.uniform(0, self.w + 40)
        for c in self.cars:
            c[0] += c[2] * dt * (0.6 + 0.5 * warp)
            if c[0] < -40 or c[0] > self.w + 40:
                c[0] = self.w + 40 if c[2] < 0 else -40
                c[1] = self.rng.uniform(self.h * 0.25, self.h * 0.55)

    def moving_boxes(self):
        boxes = [(c[0] - 20, c[1] - 8, c[0] + 20, c[1] + 8) for c in self.cars]
        boxes += [(r[0] - 4, r[1] - 4, r[0] + 4, r[1] + 4) for r in self.rain[::8]]
        return boxes

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        pink = _rgb(_theme.LINE) if _theme.LINE else _rgb("#ff2bd6")
        cyan = _rgb(_theme.CYAN)
        rain_c = _blend_rgb(_rgb(_theme.BG), cyan, 0.4)
        for x, y, _sp, length in self.rain:
            if x1 - 20 <= x <= x2 + 20 and y1 - 20 <= y <= y2 + 20:
                d.line((x - x1, y - y1, x - x1 - 2, y - y1 + length * 0.15), fill=rain_c, width=1)
        for x, y, spd in self.cars:
            col = pink if spd > 0 else cyan
            d.rectangle((x - x1 - 14, y - y1 - 3, x - x1 + 14, y - y1 + 3), fill=col)
            d.ellipse((x - x1 + (10 if spd > 0 else -14), y - y1 - 2,
                       x - x1 + (14 if spd > 0 else -10), y - y1 + 2), fill=_rgb(_theme.AMBER))


class ZenScene(SkinScene):
    """Сад дзен: лепестки + рябь."""

    engine = "zen"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.ripples: list[list[float]] = []
        n = 25 if self.mode == "full" else 14
        self.particles = [
            [self.rng.uniform(0, self.w), self.rng.uniform(-20, self.h),
             self.rng.uniform(3, 7), self.rng.uniform(0.3, 1.0), self.rng.uniform(0, 6.28)]
            for _ in range(n)
        ]

    def step(self, dt: float, warp: float = 1.0) -> None:
        self.t += dt
        for p in self.particles:
            p[1] += (8 + 10 * warp) * dt * p[3]
            p[0] += math.sin(self.t * 0.8 + p[4]) * 12 * dt
            p[4] += dt * 0.5
            if p[1] > self.h + 10:
                p[1] = -10
                p[0] = self.rng.uniform(0, self.w)
        self.ripples = [r for r in self.ripples if r[2] < 1.2]
        for r in self.ripples:
            r[2] += dt * 0.4
        if self.rng.random() < 0.015:
            self.ripples.append([self.rng.uniform(self.w * 0.2, self.w * 0.8),
                                 self.rng.uniform(self.h * 0.55, self.h * 0.9), 0.0])

    def _draw_fx(self, im, x1, y1, x2, y2) -> None:
        d = ImageDraw.Draw(im)
        petal = _blend_rgb(_rgb(_theme.BG), _rgb(_theme.AMBER), 0.55)
        ink = _rgb(_theme.LINE)
        for rx, ry, age in self.ripples:
            r = age * 60
            col = _blend_rgb(_rgb(_theme.BG), ink, max(0.05, 0.35 - age * 0.25))
            d.ellipse((rx - x1 - r, ry - y1 - r * 0.4, rx - x1 + r, ry - y1 + r * 0.4), outline=col, width=1)
        for x, y, rr, _v, ang in self.particles:
            if x1 - 8 <= x <= x2 + 8 and y1 - 8 <= y <= y2 + 8:
                ca, sa = math.cos(ang), math.sin(ang)
                pts = [
                    (x - x1 + ca * rr, y - y1 + sa * rr * 0.4),
                    (x - x1 - sa * rr * 0.5, y - y1 + ca * rr * 0.5),
                    (x - x1 - ca * rr, y - y1 - sa * rr * 0.4),
                    (x - x1 + sa * rr * 0.5, y - y1 - ca * rr * 0.5),
                ]
                d.polygon(pts, fill=petal)


ENGINES = {
    "sonar": SonarScene,
    "gears": GearsScene,
    "candles": CandlesScene,
    "city_rain": CityRainScene,
    "zen": ZenScene,
}


def make_skin_scene(w: int, h: int, mode: str, theme_id: str, engine: str):
    cls = ENGINES.get(engine, SkinScene)
    return cls(w, h, mode=mode, theme_id=theme_id)
