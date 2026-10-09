"""«ЖИВОЙ КОСМОС»: живой фон за стеклянными панелями во всех разделах Star Typing.

Сцена (Pillow): туманности, звёзды в 3 слоях с параллаксом, кометы с хвостами, планеты, астероиды.
В открытых местах (иллюминатор мостика, просветы между панелями) она резкая; под панелями —
«матовое стекло»: размытая, затемнённая и подкрашенная в цвет панели. Текст и кнопки — поверх, чёткие.

Как держим 20–24 к/с на слабом ноутбуке без numpy:
- статичный слой (туманности + планеты) кэшируется и пересчитывается раз в ~1,5 с (планеты ползут);
- каждый кадр рисуются только звёзды/кометы/астероиды и только в резких окнах;
- стекло: размытый статичный слой в 1/2 размера тоже кэшируется, поверх — только кометы и астероиды
  (маленькими пятнами, без повторного размытия); панели обновляются по кругу с бюджетом времени;
- PhotoImage создаётся один раз на холст и дальше только paste();
- свой таймер (after) с точным интервалом; при печати резкое окно — реже; окно свёрнуто — пауза;
- «уменьшение движения» Windows → неподвижная картинка.
Настройка пилота `living_space`: "off" | "light" (по умолчанию) | "full".
"""
from __future__ import annotations

import math
import random
import sys
import time
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:  # без Pillow режим недоступен, всё работает как раньше
    Image = None

from stamina.theme import BG, CYAN, PANEL

MODES = ("off", "light", "full")
MODE_TITLES = {"off": "ВЫКЛ", "light": "ЛЁГКИЙ", "full": "ПОЛНЫЙ"}
DEFAULT_MODE = "light"
PROFILE = {
    # к/с резкого окна, к/с просветов, к/с стекла, бюджет стекла на кадр (мс), объекты
    "light": dict(fps=12, gap_fps=3, glass_fps=2, glass_ms=4, stars=90, comets=1, rocks=3, planets=1),
    "full": dict(fps=24, gap_fps=8, glass_fps=5, glass_ms=6, stars=170, comets=2, rocks=6, planets=2),
}
STATIC_REFRESH = 1.5     # с: планеты в резких окнах
SLOW_MS = 30.0           # мс: «полный» дольше этого 5 с подряд → «лёгкий»
FROST_REFRESH = 6.0      # с: планеты под стеклом (сдвиг на 2–4 пикселя размытия не виден)


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
    """Мир в пикселях экрана; объекты летят справа налево (корабль движется вперёд)."""

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
                 ((0.18, 0.80), 0.12, (210, 140, 80), (90, 40, 30), False)]
        for i in range(self.p["planets"]):
            (fx, fy), fr, c1, c2, ring = specs[i]
            rad = int(min(self.h, self.w * 0.6) * fr)
            self.planets.append([fx * self.w, fy * self.h, self._planet_sprite(rad, c1, c2, ring), 0.6 + i * 0.5])
        self.base = self._base()
        self.t = 0.0
        self._static = None
        self._static_t = -1e9
        self.static_gen = 0
        self._frost = None
        self._frost_t = -1e9
        self.frost_gen = 0

    # -- заготовки
    def _base(self):
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
        rad = max(rad, 8)
        size = rad * 2 + (rad if ring else 0) + 4
        im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx = cy = size
        R = rad * 2
        for k in range(24, 0, -1):
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

    # -- движение
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

    # -- статичный слой (туманности + планеты), кэш
    def static(self, force: bool = False):
        if self._static is None or force or self.t - self._static_t >= STATIC_REFRESH:
            im = self.base.copy()
            for px_, py, spr, _v in self.planets:
                im.paste(spr, (int(px_ - spr.width / 2), int(py - spr.height / 2)), spr)
            self._static = im
            self._static_t = self.t
            self.static_gen += 1
        return self._static

    def frost_static(self):
        """Размытое стекло статичного слоя в 1/2 размера (кэш вместе со статичным слоем)."""
        st = self.static()
        if self._frost is None or self.t - self._frost_t >= FROST_REFRESH:
            self._frost = frost_small(st)
            self._frost_t = self.t
            self.frost_gen += 1
        return self._frost

    def moving_boxes(self) -> list[tuple[float, float, float, float]]:
        """Где сейчас кометы и астероиды (с запасом) — «грязные» области стекла."""
        out = []
        for x, y, _sp, _dr, tail in self.comets:
            out.append((x - 8, y - tail * 0.2 - 8, x + tail + 8, y + 8))
        for x, y, *_ in self.rocks:
            out.append((x - 16, y - 16, x + 16, y + 16))
        return out

    # -- кадры
    def render(self, box: tuple[int, int, int, int] | None = None):
        """Резкий кадр всей сцены или области box=(x1, y1, x2, y2)."""
        x1, y1, x2, y2 = box or (0, 0, self.w, self.h)
        im = self.static().crop((x1, y1, x2, y2))
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
            if x - x1 > -tail * 1.5 and x - x1 < (x2 - x1) + 10 and y1 - 20 < y < y2 + 20:
                hx, hy = x - x1, y - y1
                for k in range(12, 0, -1):
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

    def frost_frame(self):
        """Стекло в 1/FS размера: кэш статичного стекла + размытые пятна комет и астероидов (без пересчёта блюра)."""
        fs = self.frost_static().copy()
        d = ImageDraw.Draw(fs)
        tint = _rgb(PANEL)
        mix = lambda c, a: tuple(int(tint[j] + (c[j] - tint[j]) * a) for j in range(3))  # noqa: E731
        for x, y, _sp, _dr, tail in self.comets:
            hx, hy = x / FS, y / FS
            for k in range(4, 0, -1):
                t = k / 4
                d.line((hx + tail / FS * t, hy, hx + tail / FS * (t - 0.25), hy), fill=mix((150, 220, 245), 0.25 * (1 - t) + 0.08),
                       width=3)
            d.ellipse((hx - 3, hy - 3, hx + 3, hy + 3), fill=mix((235, 250, 255), 0.35))
        for x, y, *_ in self.rocks:
            d.ellipse((x / FS - 4, y / FS - 4, x / FS + 4, y / FS + 4), fill=mix((90, 86, 96), 0.4))
        return fs


FS = 2   # масштаб стекла: 1/2 — растягиваем «ближайшим» (в 1,5–3 раза быстрее сглаживающего), блоки 2×2 не видны


def frost_small(im, tint: str = PANEL, amount: float = 0.76):
    """Матовое стекло в 1/FS размера: reduce + два box-размытия (≈ гаусс) + подкраска в цвет панели."""
    small = im.reduce(FS).filter(ImageFilter.BoxBlur(12 // FS)).filter(ImageFilter.BoxBlur(12 // FS))
    return Image.blend(small, Image.new("RGB", small.size, _rgb(tint)), amount)


def frost(im, tint: str = PANEL, amount: float = 0.76):
    return frost_small(im, tint, amount).resize(im.size, Image.BILINEAR)


def frost_crop(fs, box):
    """Область box (в полных координатах) из стекла 1/FS, растянутая до её размера."""
    x1, y1, x2, y2 = box
    return fs.resize((x2 - x1, y2 - y1), Image.NEAREST, box=(x1 / FS, y1 / FS, x2 / FS, y2 / FS))


# ============================================================================ контроллер
class LivingSpace:
    """Живой фон для «хоста» (область экранов кабины или окно входа).

    attach(screen) — включить для видимого экрана: под экран кладётся холст просветов, все холсты
    экрана становятся «стеклом» (картинка-подложка с тегом ls_bg), холсты с атрибутом living_sharp —
    резкими окнами. Свой таймер; работает, только пока окно видно.
    """

    TAG = "ls_bg"

    def __init__(self, root: tk.Misc, host: tk.Misc, mode: str = DEFAULT_MODE) -> None:
        self.root, self.host = root, host
        self.mode = mode if (mode in MODES and available()) else "off"
        self.screen: tk.Misc | None = None
        self.scene: Scene | None = None
        self.sharp: list = []
        self.glass: list = []
        self._bgs: dict = {}
        self._photos: dict = {}
        self._pending: list = []
        self._boxes: dict = {}
        self._last_check = 0.0
        self._last_key = 0.0
        self._glass_gen = 0
        self._fs_gen_seen = -1
        self._ema = None
        self._slow_since = None
        self.downgraded = False
        self._dirty_prev: list = []
        self._fs = None
        self._last_glass = self._last_gap = self._last_scan = 0.0
        self._last_step = time.monotonic()
        self.static = reduced_motion()
        self._static_done = False
        self.warp = 1.0
        self._job = None
        self.stats = {"frames": 0, "render_ms": 0.0, "glass_paints": 0, "t0": time.monotonic()}

    def key(self) -> None:
        """Нажатие клавиши: пока печатают, резкое окно обновляется вдвое реже."""
        self._last_key = time.monotonic()

    @property
    def typing(self) -> bool:
        return time.monotonic() - self._last_key < 0.8

    # -- режим и экран
    @property
    def on(self) -> bool:
        return self.mode in ("light", "full")

    def set_mode(self, mode: str) -> None:
        mode = mode if (mode in MODES and available()) else "off"
        if mode == self.mode:
            return
        self.mode = mode
        self.scene = None
        scr = self.screen
        self.detach()
        if scr is not None:
            self.attach(scr)

    def attach(self, screen: tk.Misc) -> None:
        if self.screen is not None and self.screen is not screen:
            self._mark(self.sharp + self.glass, False)
            self.sharp, self.glass = [], []
        self.screen = screen
        if not self.on:
            return
        bg = self._bgs.get(str(screen))
        if bg is None or not bg.winfo_exists():
            bg = tk.Canvas(screen, highlightthickness=0, bd=0, bg=BG)
            bg.living_gap = True
            self._bgs[str(screen)] = bg
        bg.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lower(bg)
        self.scan()
        self._schedule(30)

    def detach(self) -> None:
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        self._mark(self.sharp + self.glass, False)
        for c in self.sharp + self.glass:
            try:
                c.delete(self.TAG)
            except tk.TclError:
                pass
        for bg in self._bgs.values():
            try:
                bg.place_forget()
            except tk.TclError:
                pass
        self.sharp, self.glass = [], []
        self._photos.clear()
        self._pending, self._boxes = [], {}
        self.screen = None

    def _mark(self, canvases, on: bool) -> None:
        for c in canvases:
            try:
                changed = getattr(c, "glass", False) != on
                c.glass = on
                if hasattr(c, "living_sharp"):
                    changed = changed or getattr(c, "living", False) != on
                    c.living = on
                if changed and c.winfo_exists():
                    c.event_generate("<Configure>")
            except tk.TclError:
                pass

    def scan(self) -> None:
        """Найти все холсты экрана (рекурсивно)."""
        if self.screen is None:
            return
        sharp, glass = [], []
        stack = list(self.screen.winfo_children())
        while stack:
            w = stack.pop()
            if isinstance(w, tk.Toplevel):
                continue
            if isinstance(w, tk.Canvas) and not getattr(w, "living_gap", False) and not getattr(w, "living_skip", False):
                (sharp if getattr(w, "living_sharp", False) else glass).append(w)
            stack.extend(w.winfo_children())
        new = [c for c in sharp + glass if c not in self.sharp and c not in self.glass]
        self.sharp, self.glass = sharp, glass
        self._mark(new, True)
        self._boxes = {}
        if self.scene is not None:
            for c in sharp + glass:
                try:
                    if c.winfo_ismapped():
                        self._boxes[c] = self._box(c)
                except tk.TclError:
                    pass
        self._pending = [c for c in glass if c in self._boxes]
        self._last_scan = time.monotonic()

    # -- таймер
    def _schedule(self, ms: int) -> None:
        if self._job is None:
            self._job = self.root.after(ms, self._loop)

    def _loop(self) -> None:
        self._job = None
        if not self.on or self.screen is None:
            return
        try:
            if self.root.winfo_toplevel().state() == "iconic" or not self.screen.winfo_viewable():
                self._schedule(300)
                return
            delay = self.frame()
        except tk.TclError:
            return
        if delay is not None:
            self._schedule(delay)

    # -- кадр
    def _ensure_scene(self) -> bool:
        w, h = self.host.winfo_width(), self.host.winfo_height()
        if w < 100 or h < 100:
            return False
        if self.scene is None or (self.scene.w, self.scene.h) != (w, h):
            self.scene = Scene(w, h, self.mode)
            self._photos.clear()
            self._fs = None
            self.scan()
        return True

    def _box(self, c):
        x = c.winfo_rootx() - self.host.winfo_rootx()
        y = c.winfo_rooty() - self.host.winfo_rooty()
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(self.scene.w, x + c.winfo_width()), min(self.scene.h, y + c.winfo_height())
        return (x1, y1, x2, y2), (x1 - x, y1 - y)

    def _put(self, c, im, off=(0, 0)) -> None:
        key = str(c)
        ph = self._photos.get(key)
        if ph is None or (ph.width(), ph.height()) != im.size:
            ph = ImageTk.PhotoImage(im)
            self._photos[key] = ph
            c.delete(self.TAG)
        else:
            ph.paste(im)
        if not c.find_withtag(self.TAG):
            c.create_image(off[0], off[1], anchor="nw", image=ph, tags=self.TAG)
            c.tag_lower(self.TAG)

    def frame(self) -> int | None:
        """Один кадр; → задержка до следующего (мс) или None (неподвижная картинка готова)."""
        if not self._ensure_scene():
            return 200
        prof = PROFILE[self.mode]
        now = time.monotonic()
        t0 = time.perf_counter()
        if now - self._last_scan > 2.0:
            self.scan()
        dt = min(0.2, now - self._last_step)
        self._last_step = now
        if not self.static:
            self.scene.step(dt, 0.6 + 0.4 * self.warp)
        for c in self.sharp:                                   # резкие окна — каждый кадр
            if c in self._boxes:
                box, off = self._boxes[c]
                if box[2] - box[0] > 4 and box[3] - box[1] > 4:
                    self._put(c, self.scene.render(box), off)
        if self.static or now - self._last_gap >= 1 / prof["gap_fps"]:   # просветы
            self._last_gap = now
            bg = self._bgs.get(str(self.screen))
            if bg is not None:
                self._put(bg, self.scene.render())
        if (self._fs is None) if self.static else (now - self._last_glass >= 1 / prof["glass_fps"]):  # новое поколение стекла
            self._last_glass = now
            fg = self.scene.frost_gen
            self._fs = self.scene.frost_frame()
            self._glass_gen += 1
            dirty = self.scene.moving_boxes()
            if fg != self.scene.frost_gen or self._fs_gen_seen != fg:
                self._pending = list(self.glass)           # сменился статичный слой — всё стекло
            else:                                          # иначе — только панели, где пролетают объекты
                hit = lambda b: any(d[0] < b[2] and d[2] > b[0] and d[1] < b[3] and d[3] > b[1]  # noqa: E731
                                    for d in dirty + self._dirty_prev)
                self._pending = [c for c in self.glass if c in self._boxes and hit(self._boxes[c][0])
                                 and c not in self._pending] + self._pending
            self._fs_gen_seen = self.scene.frost_gen
            self._dirty_prev = dirty
        if now - self._last_check > 0.3:                      # кто-то перерисовал холст и стёр подложку?
            self._last_check = now
            for c in self.glass:
                try:
                    if c not in self._pending and not c.find_withtag(self.TAG):
                        self._pending.append(c)
                except tk.TclError:
                    pass
        if self._fs is not None and self._pending:            # стекло по очереди, в пределах бюджета
            budget = 1e9 if self.static else prof["glass_ms"] / 1000
            g0 = time.perf_counter()
            while self._pending and time.perf_counter() - g0 <= budget:
                c = self._pending.pop(0)
                try:
                    box, off = self._boxes.get(c) or self._box(c)
                    if box[2] - box[0] > 2 and box[3] - box[1] > 2:
                        self._put(c, frost_crop(self._fs, box), off)
                        self.stats["glass_paints"] += 1
                except tk.TclError:
                    continue
        ms = (time.perf_counter() - t0) * 1000
        self._ema = ms if self._ema is None else self._ema * 0.95 + ms * 0.05
        if self.mode == "full" and self._ema > SLOW_MS:       # ноутбук не тянет → тихо ЛЁГКИЙ до перезапуска
            if self._slow_since is None:
                self._slow_since = now
            elif now - self._slow_since > 5:
                self.downgraded = True
                self.root.after_idle(lambda: self.set_mode("light"))
                return None
        else:
            self._slow_since = None
        self.stats["frames"] += 1
        self.stats["render_ms"] += ms
        if self.static:
            if not self._pending:
                return 2000      # раз в 2 с проверить, не появились ли новые панели
            return 50
        fps = prof["fps"] / (2 if self.typing else 1)
        return max(5, int(1000 / fps - ms))

    def fps(self) -> float:
        el = time.monotonic() - self.stats["t0"]
        return self.stats["frames"] / el if el > 0 else 0.0


def edge_glow(canvas: tk.Canvas, pts, tag: str = "frame") -> None:
    """Голубое свечение кромки стеклянной панели (2 полупрозрачных «слоя» линий)."""
    from stamina.theme import blend
    canvas.create_polygon(pts, fill="", outline=blend(PANEL, CYAN, 0.35), width=4, tags=tag)
    canvas.create_polygon(pts, fill="", outline=blend(PANEL, CYAN, 0.65), width=1, tags=tag)
