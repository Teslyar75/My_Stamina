"""3D-модели роботов-терраформеров для отсека «ТЕРРАФОРМЕР» (холст Tk).

Две линейки по одобренным концептам:

* **cefr** — бело-стальная, голубое ядро: A1 … C2 (8 роботов);
* **freq** — янтарно-белая, голубое ядро: S-1000 … S-20K (4 робота).

Каждый робот — набор выпуклых примитивов (боксы, цилиндры/конусы, сферы),
разложенных в грани-полигоны с цветом и именем детали. Рисование — painter
(сортировка граней по глубине) + отсечение задних граней + простое освещение
по нормали + пульс ядра по времени ``t``.

Камера та же, что у сущности в Лаборатории: математика проекции, орбиты и
зума к курсору импортируется из :mod:`stamina.laboratory`
(``rotate_xyz``, ``project_point``, ``zoom_toward``, ``clamp_pitch``,
``ZOOM_*``, ``ORBIT_SENS``), своей второй реализации здесь нет.
Ctrl+колёсико — зум к курсору, ЛКМ-перетаскивание — орбита (см. :class:`OrbitView`).

Импорт модуля не создаёт окон Tk.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from functools import lru_cache

from stamina.hotkeys import CTRL
from stamina.laboratory import (
    ORBIT_SENS,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_STEP,
    clamp_pitch,
    project_point,
    rotate_xyz,
    zoom_toward,
)
from stamina.wheel_router import direction as wheel_direction

__all__ = [
    "ROBOTS", "ROBOT_IDS", "Robot", "Prim", "OrbitView",
    "build", "bounds", "polygon_count", "frame_polys", "draw",
    "DEFAULT_YAW", "DEFAULT_PITCH", "ZOOM_MIN", "ZOOM_MAX",
]

Vec = tuple[float, float, float]

DEFAULT_YAW = 0.45       # вид в три четверти, как на концептах (лицом чуть влево)
DEFAULT_PITCH = 0.22     # чуть сверху
CORE_PULSE_HZ = 0.42     # «дыхание» ядра, раз в ~2.4 с
_LIGHT = (-0.42, -0.62, -0.66)   # в видовых координатах (y вниз, камера на −z)
_CULL_SIGN = 1.0         # знак площади видимой грани на экране (проверяется тестом)


# ─── палитры ────────────────────────────────────────────────────────────────

CEFR_PALETTE: dict[str, str] = {
    "body": "#e3e7ec", "plate": "#c9d0d8", "steel": "#8f98a3", "joint": "#596270",
    "dark": "#2f353d", "accent": "#35bfe8", "core": "#5fe6ff", "core_dim": "#1d9fd0",
    "glass": "#14202b", "solar": "#2c5a8c", "spray": "#9fe4ff",
}
FREQ_PALETTE: dict[str, str] = {
    "body": "#ece5d3", "plate": "#d8ccb0", "steel": "#a89878", "amber": "#d29a22",
    "joint": "#6a5636", "dark": "#3a3024", "accent": "#e7b437", "core": "#5fe6ff",
    "core_dim": "#1d9fd0", "glass": "#201a12", "green": "#4c7a2c", "green2": "#62953a",
    "soil": "#4d3b28", "cloud": "#d9dee3", "spray": "#9fe4ff",
}


@dataclass(frozen=True)
class Robot:
    id: str
    line: str            # "cefr" | "freq"
    level: int           # 1… внутри линейки
    name: str            # подпись уровня: "A1", "S-1000"
    caption: str         # роль робота
    palette: dict = field(compare=False, hash=False)


ROBOTS: tuple[Robot, ...] = (
    Robot("a1", "cefr", 1, "A1", "Колёсный разведчик · почвенный зонд и лопата", CEFR_PALETTE),
    Robot("a2", "cefr", 2, "A2", "Гусеничный модуль · буровая рука", CEFR_PALETTE),
    Robot("b1_1", "cefr", 3, "B1.1", "Шагоход · сканер почвы", CEFR_PALETTE),
    Robot("b1_2", "cefr", 4, "B1.2", "Шагоход · водомёт и семенные капсулы", CEFR_PALETTE),
    Robot("b2_1", "cefr", 5, "B2.1", "Четвероног · плуг и солнечные крылья", CEFR_PALETTE),
    Robot("b2_2", "cefr", 6, "B2.2", "Четвероног · атмосферные вентили и рабочие руки", CEFR_PALETTE),
    Robot("c1", "cefr", 7, "C1", "Тяжёлая платформа · мульти-манипулятор и дрон-отсек", CEFR_PALETTE),
    Robot("c2", "cefr", 8, "C2", "Мега-терраформер · генератор атмосферы и рой дронов", CEFR_PALETTE),
    Robot("s1000", "freq", 1, "S-1000", "ФУНДАМЕНТ · парящий дрон-сеятель", FREQ_PALETTE),
    Robot("s3000", "freq", 2, "S-3000", "РАЗГОВОРНЫЙ · паук с поливочными шлангами", FREQ_PALETTE),
    Robot("s10k", "freq", 3, "S-10K", "СВОБОДНЫЙ · кран, сборщик минералов, засев облаков", FREQ_PALETTE),
    Robot("s20k", "freq", 4, "S-20K", "КАК НОСИТЕЛЬ · станция с лесом и метеобашнями", FREQ_PALETTE),
)
ROBOT_IDS: tuple[str, ...] = tuple(r.id for r in ROBOTS)
_BY_ID = {r.id: r for r in ROBOTS}


def robot(robot_id: str) -> Robot:
    try:
        return _BY_ID[robot_id]
    except KeyError:
        raise KeyError(f"unknown terraformer {robot_id!r}; known: {', '.join(ROBOT_IDS)}") from None


# ─── примитивы ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Prim:
    """Выпуклый примитив в локальных координатах робота (y вверх, перед — −z, метры)."""
    part: str
    color: str
    verts: tuple[Vec, ...]
    faces: tuple[tuple[int, ...], ...]
    normals: tuple[Vec, ...]          # внешняя нормаль на каждую грань
    emissive: bool = False            # не освещается (ядро, огни)
    double: bool = False              # без отсечения задних граней (плоские)
    anim: tuple = ()                  # ("orbit", speed) | ("bob", amp, hz)
    cnormals: tuple[tuple[Vec, ...], ...] = ()   # нормали углов граней (гладкое затенение)


def _sub(a: Vec, b: Vec) -> Vec:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _add(a: Vec, b: Vec) -> Vec:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _mul(a: Vec, k: float) -> Vec:
    return a[0] * k, a[1] * k, a[2] * k


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _norm(a: Vec) -> Vec:
    n = math.sqrt(_dot(a, a)) or 1.0
    return a[0] / n, a[1] / n, a[2] / n


def _rot(v: Vec, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> Vec:
    """Локальный поворот детали: сначала крен (z), потом наклон (x), потом поворот (y)."""
    x, y, z = v
    if rz:
        c, s = math.cos(rz), math.sin(rz)
        x, y = x * c - y * s, x * s + y * c
    if rx:
        c, s = math.cos(rx), math.sin(rx)
        y, z = y * c - z * s, y * s + z * c
    if ry:
        c, s = math.cos(ry), math.sin(ry)
        x, z = x * c + z * s, -x * s + z * c
    return x, y, z


def _basis(axis: Vec, side: Vec | None = None) -> tuple[Vec, Vec, Vec]:
    a = _norm(axis)
    ref = side if side is not None else ((0.0, 1.0, 0.0) if abs(a[1]) < 0.9 else (1.0, 0.0, 0.0))
    u = _sub(ref, _mul(a, _dot(ref, a)))
    if _dot(u, u) < 1e-9:
        ref = (0.0, 0.0, 1.0) if abs(a[2]) < 0.9 else (1.0, 0.0, 0.0)
        u = _sub(ref, _mul(a, _dot(ref, a)))
    u = _norm(u)
    v = _cross(a, u)
    return a, u, v


def _newell(pts: list[Vec]) -> Vec:
    nx = ny = nz = 0.0
    m = len(pts)
    for i in range(m):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % m]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return _norm((nx, ny, nz))


_SMOOTH_COS = math.cos(math.radians(40.0))


def _dedup_faces(vs: list[Vec], faces: list[tuple[int, ...]]):
    """Склеить совпавшие вершины и выбросить вырожденные грани (фаска на углах)."""
    key: dict[tuple, int] = {}
    nv: list[Vec] = []
    remap = []
    for v in vs:
        k = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
        if k not in key:
            key[k] = len(nv)
            nv.append(v)
        remap.append(key[k])
    out = []
    for f in faces:
        g: list[int] = []
        for i in f:
            j = remap[i]
            if not g or g[-1] != j:
                g.append(j)
        if len(g) > 1 and g[0] == g[-1]:
            g.pop()
        if len(g) >= 3:
            out.append(tuple(g))
    return nv, out


class _B:
    """Сборщик примитивов одного робота."""

    def __init__(self, pal: dict[str, str], q: float = 1.0, scale: float = 1.0) -> None:
        self.pal = pal
        self.scale = scale            # общий масштаб робота (пропорции не меняет)
        self.q = q                    # множитель сегментов: 1 — Canvas, 2 — гладкий рендер
        self.prims: list[Prim] = []
        self.anim: tuple = ()

    def c(self, key: str) -> str:
        return self.pal.get(key, key)

    def add(self, part, color, verts, faces, *, emissive=False, double=False) -> None:
        k = self.scale
        verts = [(round(x * k, 5), round(y * k, 5), round(z * k, 5)) for x, y, z in verts]
        cen = _mul((sum(v[0] for v in verts), sum(v[1] for v in verts), sum(v[2] for v in verts)),
                   1.0 / len(verts))
        out_f, out_n = [], []
        for f in faces:
            pts = [verts[i] for i in f]
            n = _newell(pts)
            fc = _mul((sum(p[0] for p in pts), sum(p[1] for p in pts), sum(p[2] for p in pts)),
                      1.0 / len(pts))
            if _dot(n, _sub(fc, cen)) < 0:
                f = tuple(reversed(f))
                n = _mul(n, -1.0)
            out_f.append(tuple(f))
            out_n.append((round(n[0], 5), round(n[1], 5), round(n[2], 5)))
        # нормали углов: усредняем соседние грани с изломом < SMOOTH_DEG (сферы, цилиндры гладкие,
        # рёбра боксов и фаски — острые)
        around: dict[int, list[int]] = {}
        for fi, f in enumerate(out_f):
            for i in f:
                around.setdefault(i, []).append(fi)
        cn = []
        for fi, f in enumerate(out_f):
            nf = out_n[fi]
            corners = []
            for i in f:
                acc = (0.0, 0.0, 0.0)
                for fj in around[i]:
                    if _dot(out_n[fj], nf) >= _SMOOTH_COS:
                        acc = _add(acc, out_n[fj])
                n = _norm(acc)
                corners.append((round(n[0], 4), round(n[1], 4), round(n[2], 4)))
            cn.append(tuple(corners))
        self.prims.append(Prim(part, self.c(color), tuple(verts), tuple(out_f), tuple(out_n),
                               emissive, double, self.anim, tuple(cn)))

    def _n(self, n: int, lo: int = 4) -> int:
        return max(lo, int(round(n * self.q)))

    # боксы ------------------------------------------------------------------
    def box(self, part, color, c: Vec, s: Vec, *, rx=0.0, ry=0.0, rz=0.0,
            top=(1.0, 1.0), bot=(1.0, 1.0), emissive=False) -> None:
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        vs = []
        for yy, (kx, kz) in ((-hy, bot), (hy, top)):
            for xx, zz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                vs.append(_add(c, _rot((xx * hx * kx, yy, zz * hz * kz), rx, ry, rz)))
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.add(part, color, vs, faces, emissive=emissive)

    def rbox(self, part, color, c: Vec, s: Vec, *, bev: float = 0.18, rx=0.0, ry=0.0, rz=0.0,
             top=(1.0, 1.0), emissive=False, basis: tuple[Vec, Vec, Vec] | None = None) -> None:
        """Бронепластина/корпус со скошенными рёбрами (фаска ``bev`` доля от меньшей стороны)."""
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        b = min(hx, hy, hz) * bev * 2
        b = min(b, hx * 0.9, hy * 0.9, hz * 0.9)
        vs: list[Vec] = []
        # 3 уровня по y: низ (сужен на фаску), низ-полный, верх-полный, верх (сужен) → октагональные слои
        layers = ((-hy, b, 1.0), (-hy + b, 0.0, 1.0), (hy - b, 0.0, 1.0), (hy, b, 1.0))
        for li, (yy, inset, _k) in enumerate(layers):
            kx, kz = (1.0, 1.0) if li < 2 else top
            ax, az = hx * kx, hz * kz
            ring8 = ((-ax + b, -az), (ax - b, -az), (ax, -az + b), (ax, az - b),
                     (ax - b, az), (-ax + b, az), (-ax, az - b), (-ax, -az + b))
            for x, z in ring8:
                if inset:
                    x = max(-ax + inset, min(ax - inset, x))
                    z = max(-az + inset, min(az - inset, z))
                if basis is None:
                    vs.append(_add(c, _rot((x, yy, z), rx, ry, rz)))
                else:
                    u, a, w = basis
                    vs.append(_add(c, _add(_add(_mul(u, x), _mul(a, yy)), _mul(w, z))))
        faces: list[tuple[int, ...]] = [tuple(range(8)), tuple(range(24, 32))]
        for L in range(3):
            a0, b0 = L * 8, (L + 1) * 8
            faces += [(a0 + i, a0 + (i + 1) % 8, b0 + (i + 1) % 8, b0 + i) for i in range(8)]
        nv, nf = _dedup_faces(vs, faces)
        self.add(part, color, nv, nf, emissive=emissive)

    def rbeam(self, part, color, p0: Vec, p1: Vec, w: float, d: float, *, taper=1.0, bev=0.25,
              side: Vec | None = None) -> None:
        """Скруглённый (фаска) брус от p0 к p1 — броня конечностей."""
        a, u, v = _basis(_sub(p1, p0), side or (1.0, 0.0, 0.0))
        L = math.dist(p0, p1)
        c = _mul(_add(p0, p1), 0.5)
        self.rbox(part, color, c, (w, L, d), bev=bev, top=(taper, taper), basis=(u, a, v))

    def beam(self, part, color, p0: Vec, p1: Vec, w: float, d: float, *, taper=1.0,
             side: Vec | None = None, emissive=False) -> None:
        """Брус от p0 к p1 (ширина w по side, толщина d); taper сужает конец p1."""
        a, u, v = _basis(_sub(p1, p0), side or (1.0, 0.0, 0.0))
        vs = []
        for p, k in ((p0, 1.0), (p1, taper)):
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                vs.append(_add(p, _add(_mul(u, su * w / 2 * k), _mul(v, sv * d / 2 * k))))
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.add(part, color, vs, faces, emissive=emissive)

    # тела вращения ---------------------------------------------------------
    def seg(self, part, color, p0: Vec, p1: Vec, r: float, *, r2: float | None = None, n=8,
            caps=True, emissive=False) -> None:
        """Цилиндр/усечённый конус от p0 (радиус r) к p1 (радиус r2)."""
        r2 = r if r2 is None else r2
        n = self._n(n)
        _a, u, v = _basis(_sub(p1, p0))
        ring = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
        vs = [_add(p0, _add(_mul(u, cs * r), _mul(v, sn * r))) for cs, sn in ring]
        faces: list[tuple[int, ...]] = []
        if r2 < 1e-6:
            vs.append(p1)
            faces += [(i, (i + 1) % n, n) for i in range(n)]
        else:
            vs += [_add(p1, _add(_mul(u, cs * r2), _mul(v, sn * r2))) for cs, sn in ring]
            faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
            if caps:
                faces.append(tuple(range(n, 2 * n)))
        if caps:
            faces.append(tuple(range(n)))
        self.add(part, color, vs, faces, emissive=emissive)

    def cyl(self, part, color, c: Vec, r: float, h: float, *, axis="y", n=10, r2=None,
            emissive=False) -> None:
        ax = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}[axis]
        p0 = _sub(c, _mul(ax, h / 2))
        p1 = _add(c, _mul(ax, h / 2))
        self.seg(part, color, p0, p1, r, r2=r2, n=n, emissive=emissive)

    def sphere(self, part, color, c: Vec, r: float, *, n=10, m=6, sc=(1.0, 1.0, 1.0),
               emissive=False) -> None:
        n, m = self._n(n, 6), self._n(m, 3)
        vs: list[Vec] = [(c[0], c[1] + r * sc[1], c[2])]
        for j in range(1, m):
            th = math.pi * j / m
            y, rr = math.cos(th) * r * sc[1], math.sin(th) * r
            for i in range(n):
                ph = 2 * math.pi * i / n
                vs.append((c[0] + math.cos(ph) * rr * sc[0], c[1] + y, c[2] + math.sin(ph) * rr * sc[2]))
        vs.append((c[0], c[1] - r * sc[1], c[2]))
        bottom = len(vs) - 1
        faces: list[tuple[int, ...]] = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
        for j in range(m - 2):
            a0, b0 = 1 + j * n, 1 + (j + 1) * n
            faces += [(a0 + i, a0 + (i + 1) % n, b0 + (i + 1) % n, b0 + i) for i in range(n)]
        last = 1 + (m - 2) * n
        faces += [(last + i, bottom, last + (i + 1) % n) for i in range(n)]
        self.add(part, color, vs, faces, emissive=emissive)

    def ring(self, part, color, c: Vec, rx: float, rz: float, h: float, *, n=12,
             tilt: tuple[float, float] = (0.0, 0.0)) -> None:
        """Эллиптический пояс (ось y, ``tilt=(rz, ry)`` — наклон оси), для сферических корпусов."""
        n = self._n(n)
        vs = []
        for yy in (-h / 2, h / 2):
            vs += [_add(c, _rot((math.cos(2 * math.pi * i / n) * rx, yy, math.sin(2 * math.pi * i / n) * rz),
                                0.0, tilt[1], tilt[0])) for i in range(n)]
        faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        faces += [tuple(range(n)), tuple(range(n, 2 * n))]
        self.add(part, color, vs, faces)

    # общие детали -----------------------------------------------------------
    def shadow(self, rx: float, rz: float | None = None, *, y=0.002, n=16) -> None:
        rz = rx if rz is None else rz
        vs = [(math.cos(2 * math.pi * i / n) * rx, y, math.sin(2 * math.pi * i / n) * rz) for i in range(n)]
        saved, self.anim = self.anim, ()
        self.add("shadow", "#05080c", vs, [tuple(range(n))], emissive=True, double=True)
        self.anim = saved

    def core(self, c: Vec, r: float, *, housing="dark", ring="accent", facing: Vec = (0.0, 0.0, -1.0),
             n=14) -> None:
        """Светящееся ядро: корпус-обод, светящееся кольцо и пульсирующий диск ``core``."""
        f = _norm(facing)
        self.seg("core_housing", housing, _sub(c, _mul(f, r * 0.35)), _add(c, _mul(f, r * 0.05)),
                 r * 1.5, n=n)
        self.seg("core_ring", ring, _add(c, _mul(f, r * 0.05)), _add(c, _mul(f, r * 0.12)),
                 r * 1.2, n=n, emissive=True)
        self.seg("core", "core", _add(c, _mul(f, r * 0.12)), _add(c, _mul(f, r * 0.3)),
                 r, r2=r * 0.8, n=n, emissive=True)
        self.seg("core", "#dffbff", _add(c, _mul(f, r * 0.28)), _add(c, _mul(f, r * 0.36)),
                 r * 0.42, r2=r * 0.3, n=n, emissive=True)


# ─── роботы линейки CEFR ────────────────────────────────────────────────────

def _joint(b: _B, p: Vec, r: float, *, axis="x", glow=True, color="joint") -> None:
    """Шарнир: цилиндр-втулка и (опционально) голубое кольцо, как на концептах."""
    b.cyl("joint", color, p, r, r * 1.3, axis=axis, n=12)
    if glow:
        off = {"x": (r * 0.68, 0, 0), "y": (0, r * 0.68, 0), "z": (0, 0, r * 0.68)}[axis]
        for sgn in (-1, 1):
            b.cyl("joint_glow", "accent", _add(p, _mul(off, sgn)), r * 0.62, r * 0.06, axis=axis, n=12,
                  emissive=True)


def _walker_legs(b: _B, k: float, *, width: float, hip_y: float) -> None:
    """Пальцеходящие ноги шагохода (колено вперёд, голень назад) с бронёй и поршнем."""
    for s in (-1, 1):
        hip = (s * width, hip_y, 0.03 * k)
        knee = (s * (width + 0.02 * k), hip_y * 0.56, -0.11 * k)
        ankle = (s * (width + 0.02 * k), 0.08 * k, 0.07 * k)
        _joint(b, hip, 0.055 * k)
        b.rbeam("leg", "body", hip, knee, 0.105 * k, 0.115 * k, taper=0.8, bev=0.25)
        b.seg("leg", "steel", _add(hip, (0, -0.02 * k, 0.05 * k)), _add(knee, (0, 0.05 * k, 0.05 * k)),
              0.012 * k, n=8)
        _joint(b, knee, 0.043 * k, glow=False, color="dark")
        b.rbeam("leg", "steel", knee, ankle, 0.07 * k, 0.075 * k, taper=0.8, bev=0.3)
        b.rbeam("leg", "plate", _add(knee, (0, -0.03 * k, -0.035 * k)), _add(knee, (0, -0.2 * k, 0.03 * k)),
                0.07 * k, 0.025 * k, taper=0.8, bev=0.3)
        b.sphere("leg", "joint", ankle, 0.03 * k, n=10, m=6)
        b.rbox("foot", "dark", (ankle[0], 0.032 * k, -0.01 * k), (0.11 * k, 0.055 * k, 0.17 * k),
               bev=0.25, top=(0.85, 0.85))
        for dx in (-0.03, 0.03):
            b.rbox("foot", "joint", (ankle[0] + dx * k, 0.022 * k, -0.115 * k), (0.045 * k, 0.04 * k, 0.07 * k),
                   bev=0.3)
        b.rbox("foot", "joint", (ankle[0], 0.025 * k, 0.09 * k), (0.05 * k, 0.04 * k, 0.05 * k), bev=0.3)


def _mech_legs(b: _B, k: float, *, width: float, hip_y: float, bulk: float = 1.0) -> None:
    """Массивные ноги гуманоидных платформ (B2.2, C1, C2); ``bulk`` — толщина брони."""
    kk = k
    for s in (-1, 1):
        k = kk * bulk
        hip = (s * width, hip_y, 0.04 * kk)
        knee = (s * (width + 0.03 * kk), hip_y * 0.55, -0.07 * kk)
        ankle = (s * (width + 0.04 * kk), 0.14 * kk, 0.04 * kk)
        _joint(b, hip, 0.08 * k)
        b.rbeam("leg", "body", hip, knee, 0.16 * k, 0.18 * k, taper=0.85, bev=0.25)
        b.rbeam("leg", "plate", _add(hip, (s * 0.07 * k, -0.04 * k, 0)), _add(knee, (s * 0.07 * k, 0.1 * k, 0)),
                0.04 * k, 0.15 * k, taper=0.85, bev=0.3)
        _joint(b, knee, 0.068 * k, glow=True, color="dark")
        b.rbox("leg", "plate", _add(knee, (0, 0.02 * k, -0.09 * k)), (0.14 * k, 0.17 * k, 0.06 * k),
               bev=0.3, rx=0.25, top=(0.8, 0.9))
        b.rbeam("leg", "steel", knee, ankle, 0.12 * k, 0.14 * k, taper=0.9, bev=0.3)
        b.rbeam("leg", "body", _add(knee, (0, -0.07 * k, -0.06 * k)), _add(ankle, (0, 0.1 * k, -0.06 * k)),
                0.14 * k, 0.05 * k, taper=0.8, bev=0.3)
        b.rbeam("leg", "body", _add(knee, (0, -0.06 * k, 0.07 * k)), _add(ankle, (0, 0.14 * k, 0.07 * k)),
                0.12 * k, 0.07 * k, taper=0.75, bev=0.3)
        b.sphere("leg", "joint", ankle, 0.06 * k, n=10, m=6)
        b.rbox("foot", "dark", (ankle[0], 0.055 * k, -0.03 * k), (0.21 * k, 0.11 * k, 0.34 * k),
               bev=0.3, top=(0.85, 0.75))
        b.rbox("foot", "steel", (ankle[0], 0.04 * k, -0.2 * k), (0.19 * k, 0.07 * k, 0.07 * k), bev=0.3)
        b.rbox("foot", "plate", (ankle[0], 0.1 * k, -0.08 * k), (0.15 * k, 0.04 * k, 0.16 * k), bev=0.3)


def _claw(b: _B, wr: Vec, k: float, s: int, fingers: int = 3) -> None:
    b.rbox("manipulator", "dark", _add(wr, (0, -0.045 * k, 0)), (0.12 * k, 0.09 * k, 0.12 * k), bev=0.25)
    spots = ((-0.035, -0.035), (0.035, -0.035), (0.0, 0.045), (0.0, -0.05))[:fingers]
    for fx, fz in spots:
        p0 = _add(wr, (fx * k, -0.085 * k, fz * k))
        p1 = _add(p0, (fx * 0.5 * k, -0.08 * k, (fz * 0.4 - 0.02) * k))
        p2 = _add(p1, (-fx * 0.3 * k, -0.06 * k, -fz * 0.5 * k))
        b.rbeam("manipulator", "steel", p0, p1, 0.028 * k, 0.03 * k, taper=0.85, bev=0.3)
        b.rbeam("manipulator", "plate", p1, p2, 0.025 * k, 0.027 * k, taper=0.45, bev=0.3)


def _drone(b: _B, c: Vec, k: float, spin: float) -> None:
    b.rbox("drone", "body", c, (0.12 * k, 0.04 * k, 0.12 * k), ry=spin, bev=0.28, top=(0.8, 0.8))
    for a in (0.785, -0.785, 2.356, -2.356):
        tip = _add(c, _rot((0.12 * k, 0.012 * k, 0), ry=spin + a))
        b.beam("drone", "dark", _add(c, (0, 0.01 * k, 0)), tip, 0.02 * k, 0.012 * k)
        b.cyl("drone", "steel", tip, 0.04 * k, 0.006 * k, n=8)
    b.cyl("drone", "accent", _add(c, _rot((0, -0.004 * k, -0.062 * k), ry=spin)), 0.012 * k, 0.012 * k,
          axis="y", n=6, emissive=True)


def _a1(b: _B) -> None:
    b.shadow(0.3, 0.28)
    for s in (-1, 1):
        for zz in (-0.085, 0.095):
            b.cyl("wheel", "dark", (s * 0.16, 0.115, zz), 0.115, 0.075, axis="x", n=18)
            b.cyl("wheel", "body", (s * 0.2, 0.115, zz), 0.07, 0.012, axis="x", n=16)
            b.cyl("wheel", "steel", (s * 0.208, 0.115, zz), 0.03, 0.01, axis="x", n=12)
            b.cyl("wheel", "accent", (s * 0.214, 0.115, zz), 0.012, 0.004, axis="x", n=8, emissive=True)
    b.rbox("chassis", "steel", (0, 0.13, 0.005), (0.2, 0.06, 0.24), bev=0.3)
    b.rbox("chassis", "body", (0, 0.215, 0.005), (0.25, 0.13, 0.26), bev=0.38, top=(0.86, 0.84))
    for s in (-1, 1):
        b.rbox("chassis", "plate", (s * 0.135, 0.225, 0.005), (0.03, 0.08, 0.2), bev=0.35)
    b.box("chassis", "accent", (0, 0.225, -0.13), (0.11, 0.014, 0.006), emissive=True)
    b.box("chassis", "dark", (0, 0.19, -0.131), (0.15, 0.03, 0.006))
    b.cyl("neck", "joint", (0, 0.285, 0.01), 0.05, 0.02, n=16)
    b.cyl("neck", "steel", (0, 0.305, 0.01), 0.03, 0.05, n=12)
    b.sphere("head", "body", (0, 0.4, 0.0), 0.115, n=16, m=10, sc=(1.1, 0.95, 1.0))
    b.ring("head", "plate", (0, 0.4, 0.0), 0.128, 0.117, 0.014, n=18)
    for s in (-1, 1):
        b.cyl("head", "joint", (s * 0.128, 0.4, 0.0), 0.046, 0.04, axis="x", n=16)
        b.cyl("head", "accent", (s * 0.15, 0.4, 0.0), 0.03, 0.006, axis="x", n=14, emissive=True)
    b.core((0, 0.4, -0.127), 0.052)
    b.seg("antenna", "steel", (-0.04, 0.49, 0.02), (-0.06, 0.575, 0.04), 0.006, n=6)
    b.sphere("antenna", "accent", (-0.06, 0.58, 0.04), 0.012, n=8, m=5, emissive=True)
    # рука с лопатой — фирменная деталь A1
    b.sphere("arm", "joint", (0.135, 0.24, -0.05), 0.028, n=10, m=6)
    b.seg("arm", "steel", (0.135, 0.24, -0.05), (0.235, 0.25, -0.12), 0.017, n=8)
    b.sphere("arm", "joint", (0.24, 0.25, -0.125), 0.024, n=10, m=6)
    b.seg("shovel", "#b9a27a", (0.205, 0.39, -0.08), (0.3, 0.08, -0.2), 0.011, n=8)
    b.rbeam("shovel", "dark", (0.17, 0.395, -0.077), (0.24, 0.385, -0.083), 0.02, 0.02, bev=0.3)
    b.seg("shovel", "steel", (0.29, 0.115, -0.187), (0.302, 0.075, -0.202), 0.016, n=8)
    b.beam("shovel", "#cfd6de", (0.302, 0.085, -0.202), (0.33, -0.0, -0.236), 0.1, 0.012, taper=0.45,
           side=(0.8, 0.0, -0.6))
    # почвенный зонд слева
    b.seg("probe", "steel", (-0.1, 0.2, -0.12), (-0.15, 0.08, -0.2), 0.008, n=6)
    b.sphere("probe", "accent", (-0.15, 0.078, -0.202), 0.013, n=8, m=5, emissive=True)


def _a2(b: _B) -> None:
    b.shadow(0.44, 0.42)
    for s in (-1, 1):
        b.rbox("track", "dark", (s * 0.21, 0.12, 0.0), (0.14, 0.22, 0.54), bev=0.4)
        for i in range(10):
            b.box("track", "#22272e", (s * 0.21, 0.233, -0.243 + i * 0.054), (0.146, 0.012, 0.024))
        for zz in (-0.17, -0.057, 0.057, 0.17):
            b.cyl("track", "steel", (s * 0.283, 0.105, zz), 0.052, 0.012, axis="x", n=14)
            b.cyl("track", "accent", (s * 0.29, 0.105, zz), 0.016, 0.004, axis="x", n=10, emissive=True)
        for zz in (-0.23, 0.23):
            b.cyl("track", "joint", (s * 0.283, 0.13, zz), 0.07, 0.016, axis="x", n=14)
        b.rbox("track", "plate", (s * 0.21, 0.25, 0.0), (0.16, 0.025, 0.5), bev=0.3)
    b.rbox("body", "steel", (0, 0.29, 0.03), (0.3, 0.06, 0.4), bev=0.25)
    b.rbox("body", "body", (0, 0.42, 0.03), (0.4, 0.24, 0.44), bev=0.3, top=(0.92, 0.9))
    b.rbox("body", "plate", (0, 0.36, -0.195), (0.32, 0.09, 0.03), bev=0.3)
    for i in range(3):
        b.box("body", "dark", (0.03, 0.542, 0.06 + i * 0.05), (0.2, 0.008, 0.02))
    b.core((0.07, 0.43, -0.2), 0.065)
    b.rbox("head", "body", (-0.12, 0.47, -0.17), (0.15, 0.13, 0.12), bev=0.3)
    b.box("head", "glass", (-0.12, 0.475, -0.232), (0.11, 0.08, 0.005))
    b.box("head", "#2a8fb8", (-0.12, 0.475, -0.235), (0.085, 0.058, 0.004), emissive=True)
    for s in (-1, 1):
        b.cyl("head", "joint", (-0.12 + s * 0.082, 0.47, -0.17), 0.03, 0.015, axis="x", n=12)
    # буровая рука — сегментная колонна сзади справа
    b.cyl("drill_arm", "joint", (0.14, 0.56, 0.14), 0.07, 0.05, n=16)
    for i in range(6):
        b.cyl("drill_arm", "steel" if i % 2 else "body", (0.14, 0.61 + i * 0.045, 0.14),
              0.045 if i % 2 else 0.052, 0.042, n=14)
    b.sphere("drill_arm", "joint", (0.14, 0.89, 0.14), 0.055, n=14, m=8)
    b.rbeam("drill_arm", "body", (0.14, 0.89, 0.14), (0.17, 0.92, 0.0), 0.07, 0.08, bev=0.25)
    b.sphere("drill_arm", "joint", (0.17, 0.92, 0.0), 0.042, n=12, m=7)
    b.seg("drill", "dark", (0.17, 0.92, 0.0), (0.175, 0.84, -0.04), 0.044, n=14)
    b.seg("drill", "steel", (0.175, 0.84, -0.04), (0.18, 0.68, -0.09), 0.038, r2=0.0, n=12)
    for k in range(3):
        b.ring("drill", "joint", (0.176, 0.82 - k * 0.04, -0.045 - k * 0.012), 0.036 - k * 0.009,
               0.036 - k * 0.009, 0.008, n=12)


def _b1_1(b: _B) -> None:
    b.shadow(0.36, 0.32)
    _walker_legs(b, 1.0, width=0.16, hip_y=0.64)
    b.rbox("hip", "dark", (0, 0.66, 0.03), (0.27, 0.08, 0.16), bev=0.25)
    b.rbox("body", "steel", (0, 0.71, 0.02), (0.22, 0.06, 0.22), bev=0.3)
    b.rbox("body", "body", (0, 0.84, 0.0), (0.36, 0.23, 0.32), bev=0.3, top=(0.92, 0.9))
    b.rbox("body", "plate", (0, 0.937, 0.02), (0.2, 0.025, 0.18), bev=0.3)
    for s in (-1, 1):
        b.cyl("body", "joint", (s * 0.08, 0.952, 0.08), 0.02, 0.02, n=10)
    b.core((0.03, 0.845, -0.168), 0.062)
    b.rbox("scanner", "body", (-0.205, 0.86, -0.02), (0.1, 0.12, 0.15), bev=0.25)
    b.box("scanner", "glass", (-0.205, 0.86, -0.097), (0.08, 0.085, 0.005))
    b.box("scanner", "#2a8fb8", (-0.205, 0.86, -0.1), (0.065, 0.068, 0.004), emissive=True)
    b.cyl("scanner", "steel", (0.17, 0.86, -0.02), 0.04, 0.04, axis="x", n=12)
    b.seg("scanner", "steel", (0.08, 0.95, 0.05), (0.1, 0.99, 0.06), 0.006, n=6)
    b.seg("soil_scanner", "dark", (0, 0.66, -0.06), (0, 0.6, -0.1), 0.03, n=10)
    b.seg("soil_scanner", "accent", (0, 0.597, -0.102), (0, 0.59, -0.106), 0.022, n=10, emissive=True)


def _b1_2(b: _B) -> None:
    k = 1.05
    b.shadow(0.4, 0.34)
    _walker_legs(b, k, width=0.18, hip_y=0.68)
    b.rbox("hip", "dark", (0, 0.7, 0.04), (0.3, 0.08, 0.18), bev=0.25)
    b.rbox("body", "body", (0, 0.88, 0.03), (0.46, 0.32, 0.4), bev=0.3, top=(0.88, 0.88))
    b.rbox("body", "plate", (0, 1.05, 0.05), (0.26, 0.03, 0.24), bev=0.3)
    b.rbox("seed_pods", "steel", (-0.07, 0.87, -0.185), (0.27, 0.2, 0.04), bev=0.25)
    for i, x in enumerate((-0.16, -0.07, 0.02)):
        for j, y in enumerate((0.81, 0.91)):
            b.sphere("seed_pods", "plate" if (i + j) % 2 else "body", (x, y, -0.22), 0.048, n=12, m=7)
            b.cyl("seed_pods", "joint", (x, y, -0.265), 0.018, 0.008, axis="z", n=10)
    b.core((0.14, 0.92, -0.205), 0.048)
    b.seg("sprayer", "steel", (0.19, 0.84, -0.04), (0.27, 0.85, -0.2), 0.03, n=12)
    b.seg("sprayer", "dark", (0.27, 0.85, -0.2), (0.29, 0.855, -0.25), 0.036, r2=0.02, n=12)
    b.seg("spray", "spray", (0.293, 0.856, -0.258), (0.42, 0.88, -0.5), 0.012, r2=0.08, n=12, emissive=True)
    b.rbox("head", "body", (0.0, 1.1, -0.07), (0.13, 0.07, 0.11), bev=0.3)
    b.box("head", "accent", (0.0, 1.1, -0.127), (0.09, 0.016, 0.005), emissive=True)


def _quad_legs(b: _B, k: float, *, width: float, hip_y: float, front_z: float, back_z: float) -> None:
    for s in (-1, 1):
        for zz in (front_z, back_z):
            hip = (s * width, hip_y, zz)
            knee = (s * (width + 0.04 * k), hip_y * 0.52, zz + 0.09 * k)
            foot = (s * (width + 0.05 * k), 0.06 * k, zz - 0.05 * k)
            _joint(b, hip, 0.06 * k)
            b.rbox("leg", "plate", _add(hip, (s * 0.045 * k, 0.0, 0.0)), (0.05 * k, 0.13 * k, 0.15 * k), bev=0.3)
            b.rbeam("leg", "body", hip, knee, 0.105 * k, 0.115 * k, taper=0.8, bev=0.25)
            _joint(b, knee, 0.045 * k, glow=False, color="dark")
            b.rbeam("leg", "steel", knee, foot, 0.075 * k, 0.08 * k, taper=0.85, bev=0.3)
            b.rbox("foot", "dark", (foot[0], 0.035 * k, foot[2] - 0.03 * k), (0.1 * k, 0.07 * k, 0.16 * k),
                   bev=0.25, top=(0.8, 0.7))


def _b2_1(b: _B) -> None:
    k = 1.1
    b.shadow(0.42, 0.62)
    _quad_legs(b, k, width=0.18, hip_y=0.56, front_z=-0.22, back_z=0.3)
    b.rbox("body", "body", (0, 0.56, 0.05), (0.38, 0.24, 0.72), bev=0.3, top=(0.9, 0.95))
    b.rbox("body", "steel", (0, 0.66, 0.1), (0.24, 0.03, 0.5), bev=0.3)
    b.rbox("body", "dark", (0, 0.45, 0.05), (0.26, 0.05, 0.56), bev=0.3)
    b.rbox("head", "steel", (0, 0.6, -0.3), (0.16, 0.12, 0.12), bev=0.25)
    b.rbox("head", "body", (0, 0.6, -0.42), (0.26, 0.2, 0.2), bev=0.28, top=(0.85, 0.85))
    b.core((0, 0.6, -0.525), 0.07)
    for s in (-1, 1):
        b.box("head", "accent", (s * 0.1, 0.665, -0.512), (0.03, 0.012, 0.005), emissive=True)
        b.rbeam("plow", "steel", (s * 0.07, 0.5, -0.42), (s * 0.12, 0.26, -0.52), 0.04, 0.045, bev=0.25)
        b.beam("plow", "#d3d9e0", (s * 0.11, 0.27, -0.5), (s * 0.17, 0.02, -0.64), 0.12, 0.03, taper=0.25)
    b.seg("solar", "steel", (0, 0.67, 0.12), (0, 0.93, 0.12), 0.02, n=10)
    b.rbox("solar", "joint", (0, 0.95, 0.12), (0.12, 0.04, 0.05), bev=0.3)
    for s in (-1, 1):
        rx, rz = -0.25, s * 0.35
        pc = (s * 0.2, 1.12, 0.12)
        b.box("solar", "steel", pc, (0.3, 0.5, 0.016), rx=rx, rz=rz)
        b.box("solar", "solar", _add(pc, _rot((0, 0, -0.01), rx=rx, rz=rz)), (0.28, 0.48, 0.008), rx=rx, rz=rz)
        for gx in (-0.045, 0.045):
            b.box("solar", "steel", _add(pc, _rot((gx, 0, -0.015), rx=rx, rz=rz)), (0.006, 0.48, 0.003),
                  rx=rx, rz=rz)
        for gy in (-0.16, -0.08, 0.0, 0.08, 0.16):
            b.box("solar", "steel", _add(pc, _rot((0, gy, -0.015), rx=rx, rz=rz)), (0.28, 0.006, 0.003),
                  rx=rx, rz=rz)


def _arm(b: _B, s: int, sh: Vec, el: Vec, wr: Vec, k: float, *, fingers=3) -> None:
    b.seg("arm", "steel", sh, el, 0.055 * k, n=12)
    b.rbeam("arm", "body", _add(sh, (0, -0.06 * k, 0)), _mul(_add(sh, el), 0.5), 0.12 * k, 0.12 * k,
            taper=0.85, bev=0.3)
    _joint(b, el, 0.06 * k, color="dark")
    b.rbeam("arm", "body", el, wr, 0.14 * k, 0.14 * k, taper=0.82, bev=0.25)
    b.rbeam("arm", "plate", _add(el, (s * 0.07 * k, -0.04 * k, 0)), _add(wr, (s * 0.06 * k, 0.08 * k, 0)),
            0.03 * k, 0.11 * k, taper=0.8, bev=0.3)
    _claw(b, wr, k, s, fingers)


def _b2_2(b: _B) -> None:
    k = 1.0
    b.shadow(0.45, 0.4)
    _mech_legs(b, 0.72, width=0.13, hip_y=0.62)
    b.rbox("pelvis", "dark", (0, 0.66, 0.04), (0.28, 0.12, 0.2), bev=0.25)
    b.rbox("torso", "steel", (0, 0.77, 0.03), (0.26, 0.12, 0.22), bev=0.3)
    b.rbox("torso", "body", (0, 0.96, 0.0), (0.44, 0.3, 0.3), bev=0.25, top=(1.08, 1.0))
    for s in (-1, 1):
        b.rbox("torso", "plate", (s * 0.13, 0.98, -0.15), (0.13, 0.15, 0.03), bev=0.3, rz=-s * 0.15)
    b.core((0, 0.98, -0.16), 0.068)
    for s in (-1, 1):
        # атмосферные вентили — сдвоенные «турбины»-окуляры
        b.cyl("atmo_vent", "body", (s * 0.115, 1.23, -0.02), 0.1, 0.26, axis="z", n=16)
        b.cyl("atmo_vent", "steel", (s * 0.115, 1.23, 0.12), 0.09, 0.03, axis="z", n=16)
        b.cyl("atmo_vent", "accent", (s * 0.115, 1.23, -0.151), 0.084, 0.004, axis="z", n=16, emissive=True)
        b.cyl("atmo_vent", "dark", (s * 0.115, 1.23, -0.155), 0.07, 0.006, axis="z", n=16)
        for gy in (-0.03, 0.0, 0.03):
            b.box("atmo_vent", "steel", (s * 0.115, 1.23 + gy, -0.16), (0.12, 0.006, 0.004))
        sh = (s * 0.29, 1.03, 0.0)
        b.rbox("shoulder", "body", (s * 0.3, 1.08, 0.0), (0.15, 0.13, 0.2), bev=0.28, top=(0.85, 0.85))
        _arm(b, s, sh, (s * 0.33, 0.83, -0.05), (s * 0.34, 0.63, -0.14), 0.8)
    b.rbox("atmo_vent", "steel", (0, 1.23, 0.0), (0.08, 0.08, 0.18), bev=0.25)
    b.box("atmo_vent", "accent", (0, 1.25, -0.092), (0.04, 0.012, 0.004), emissive=True)


def _c1(b: _B) -> None:
    b.shadow(0.55, 0.47)
    _mech_legs(b, 1.0, width=0.21, hip_y=0.88, bulk=1.35)
    b.rbox("pelvis", "dark", (0, 0.93, 0.05), (0.36, 0.15, 0.26), bev=0.25)
    for s in (-1, 1):
        b.rbox("pelvis", "plate", (s * 0.2, 0.87, -0.06), (0.14, 0.18, 0.04), bev=0.3, rx=0.15, rz=s * 0.12)
    b.rbox("torso", "steel", (0, 1.06, 0.03), (0.34, 0.16, 0.28), bev=0.3)
    b.rbox("torso", "body", (0, 1.3, 0.02), (0.68, 0.42, 0.46), bev=0.3, top=(1.12, 1.0))
    for s in (-1, 1):
        b.rbox("torso", "plate", (s * 0.18, 1.34, -0.2), (0.17, 0.2, 0.035), bev=0.3, rz=-s * 0.18)
        b.box("torso", "accent", (s * 0.18, 1.22, -0.215), (0.08, 0.012, 0.004), emissive=True)
    b.core((0, 1.32, -0.215), 0.085)
    for s in (-1, 1):
        b.rbox("shoulder", "body", (s * 0.47, 1.46, 0.02), (0.32, 0.26, 0.4), bev=0.28, top=(0.85, 0.85))
        b.box("shoulder", "accent", (s * 0.47, 1.46, -0.182), (0.14, 0.016, 0.004), emissive=True)
        _joint(b, (s * 0.49, 1.33, 0.0), 0.08)
        _arm(b, s, (s * 0.49, 1.33, 0.0), (s * 0.55, 1.02, -0.04), (s * 0.57, 0.72, -0.14), 1.45)
        # вспомогательный манипулятор на предплечье
        b.seg("manipulator", "steel", (s * 0.68, 0.96, -0.06), (s * 0.74, 0.82, -0.18), 0.018, n=8)
        b.rbeam("manipulator", "dark", (s * 0.74, 0.82, -0.18), (s * 0.75, 0.76, -0.22), 0.035, 0.022, taper=0.5)
    b.cyl("head", "joint", (0, 1.52, -0.02), 0.06, 0.06, n=14)
    b.rbox("head", "body", (0, 1.585, -0.03), (0.18, 0.13, 0.18), bev=0.3)
    b.box("head", "accent", (0, 1.585, -0.122), (0.12, 0.028, 0.004), emissive=True)
    b.rbox("drone_bay", "body", (0, 1.74, 0.02), (0.46, 0.17, 0.3), bev=0.25, top=(0.95, 0.95))
    for s in (-1, 1):
        b.box("drone_bay", "glass", (s * 0.11, 1.74, -0.131), (0.16, 0.09, 0.006))
        b.box("drone_bay", "accent", (s * 0.11, 1.7, -0.136), (0.12, 0.01, 0.004), emissive=True)
    _drone(b, (0.0, 1.85, 0.02), 0.9, 0.3)
    b.rbox("back", "steel", (0, 1.3, 0.28), (0.4, 0.34, 0.14), bev=0.25)
    for s in (-1, 1):
        b.cyl("back", "dark", (s * 0.12, 1.12, 0.32), 0.06, 0.1, n=14)
        b.cyl("back", "accent", (s * 0.12, 1.065, 0.32), 0.045, 0.008, n=14, emissive=True)
    b.seg("head", "steel", (0.07, 1.65, 0.05), (0.09, 1.82, 0.07), 0.007, n=6)
    b.sphere("head", "accent", (0.09, 1.83, 0.07), 0.014, n=8, m=5, emissive=True)


def _c2(b: _B) -> None:
    b.shadow(0.85, 0.7)
    _mech_legs(b, 1.55, width=0.31, hip_y=1.3, bulk=1.25)
    b.rbox("pelvis", "dark", (0, 1.36, 0.05), (0.52, 0.22, 0.38), bev=0.25)
    for s in (-1, 1):
        b.rbox("pelvis", "plate", (s * 0.3, 1.28, -0.1), (0.2, 0.26, 0.06), bev=0.3, rx=0.15, rz=s * 0.12)
    b.rbox("torso", "steel", (0, 1.54, 0.03), (0.56, 0.22, 0.42), bev=0.3)
    b.rbox("torso", "body", (0, 1.9, 0.03), (0.92, 0.56, 0.6), bev=0.3, top=(1.12, 1.0))
    for s in (-1, 1):
        b.rbox("torso", "plate", (s * 0.27, 1.96, -0.29), (0.25, 0.3, 0.05), bev=0.3, rz=-s * 0.18)
        b.box("torso", "accent", (s * 0.27, 1.78, -0.31), (0.12, 0.016, 0.005), emissive=True)
    b.rbox("torso", "plate", (0, 1.69, -0.28), (0.3, 0.12, 0.05), bev=0.3)
    b.core((0, 1.93, -0.3), 0.125)
    b.cyl("core_ring", "accent", (0, 1.93, -0.305), 0.21, 0.008, axis="z", n=20, emissive=True)
    b.cyl("core_housing", "steel", (0, 1.93, -0.3), 0.225, 0.012, axis="z", n=20)
    for s in (-1, 1):
        b.rbox("shoulder", "body", (s * 0.68, 2.15, 0.03), (0.38, 0.32, 0.48), bev=0.28, top=(0.85, 0.85))
        b.rbox("shoulder", "plate", (s * 0.7, 2.05, -0.2), (0.3, 0.16, 0.06), bev=0.3)
        b.box("shoulder", "accent", (s * 0.68, 2.2, -0.215), (0.18, 0.02, 0.005), emissive=True)
        _joint(b, (s * 0.72, 1.98, 0.0), 0.11)
        _arm(b, s, (s * 0.74, 1.98, 0.0), (s * 0.84, 1.45, -0.06), (s * 0.87, 0.95, -0.2), 2.0, fingers=4)
        # генератор атмосферы — две высокие башни за плечами
        tx, tz = s * 0.34, 0.27
        b.rbox("atmo_gen", "steel", (tx, 2.2, tz), (0.26, 0.2, 0.26), bev=0.25)
        b.cyl("atmo_gen", "body", (tx, 2.65, tz), 0.11, 0.8, n=16)
        b.rbox("atmo_gen", "plate", (tx, 2.6, tz - 0.1), (0.16, 0.5, 0.04), bev=0.3)
        for yy in (2.4, 2.62, 2.84):
            b.cyl("atmo_gen", "accent", (tx, yy, tz), 0.116, 0.022, n=16, emissive=True)
        b.cyl("atmo_gen", "joint", (tx, 3.07, tz), 0.13, 0.05, n=16)
        b.cyl("atmo_gen", "dark", (tx, 3.1, tz), 0.09, 0.02, n=16)
    b.rbox("head", "body", (0, 2.32, -0.06), (0.24, 0.2, 0.24), bev=0.3, top=(0.85, 0.85))
    b.box("head", "accent", (0, 2.32, -0.181), (0.16, 0.035, 0.005), emissive=True)
    b.rbox("back", "steel", (0, 2.0, 0.36), (0.5, 0.42, 0.14), bev=0.25)
    # рой дронов вокруг — вращается по орбите
    for i in range(10):
        a = 2 * math.pi * i / 10
        rad = 1.0 + 0.14 * (i % 3)
        y = 1.65 + 0.34 * ((i * 7) % 5) / 2.0
        b.anim = ("orbit", 0.32 if i % 2 else 0.26)
        _drone(b, (math.cos(a) * rad, y, math.sin(a) * rad), 1.6, a)
    b.anim = ()


# ─── частотная линейка ─────────────────────────────────────────────────────

def _orb_body(b: _B, c: Vec, r: float, *, sc=(1.0, 1.0, 1.0), n=16, m=10, meridians=True) -> None:
    """Сферический корпус с янтарными поясами-рамами, как на концепте."""
    b.sphere("shell", "body", c, r, n=n, m=m, sc=sc)
    if meridians and abs(sc[0] - sc[1]) < 1e-6 and abs(sc[0] - sc[2]) < 1e-6:
        for ry in (0.95, -0.95, 2.4, -2.4):
            b.ring("shell", "amber", c, r * 1.012, r * 1.012, r * 0.08, n=n, tilt=(math.pi / 2, ry))
    b.ring("shell", "amber", c, r * sc[0] * 1.015, r * sc[2] * 1.015, r * 0.12, n=n)
    for yk in (-0.62, 0.62):
        rr = math.sqrt(1 - yk * yk) * 1.02
        b.ring("shell", "amber", (c[0], c[1] + yk * r * sc[1], c[2]), r * sc[0] * rr, r * sc[2] * rr,
               r * 0.07, n=n)


def _s1000(b: _B) -> None:
    b.shadow(0.26)
    b.anim = ("bob", 0.035, 0.55)
    c = (0.0, 0.55, 0.0)
    _orb_body(b, c, 0.25)
    b.cyl("core_housing", "amber", (0, 0.55, -0.24), 0.125, 0.05, axis="z", n=18)
    b.core((0, 0.55, -0.265), 0.075, n=18)
    for s in (-1, 1):
        b.cyl("thruster", "amber", (s * 0.255, 0.53, 0.04), 0.06, 0.07, axis="x", n=14)
        b.cyl("thruster", "dark", (s * 0.292, 0.53, 0.04), 0.042, 0.008, axis="x", n=14)
        b.cyl("thruster", "accent", (s * 0.297, 0.53, 0.04), 0.026, 0.004, axis="x", n=12, emissive=True)
        b.sphere("arm", "joint", (s * 0.13, 0.36, -0.03), 0.03, n=10, m=6)
        b.rbeam("arm", "amber", (s * 0.13, 0.36, -0.03), (s * 0.19, 0.25, -0.07), 0.04, 0.04, bev=0.3)
        b.rbeam("arm", "body", (s * 0.19, 0.25, -0.07), (s * 0.18, 0.18, -0.09), 0.035, 0.035, taper=0.5,
                bev=0.3)
    b.cyl("seeder", "dark", (0, 0.305, 0.0), 0.07, 0.04, n=14)
    b.cyl("seeder", "accent", (0, 0.283, 0.0), 0.05, 0.006, n=14, emissive=True)
    b.seg("seeder_beam", "spray", (0, 0.278, 0.0), (0, 0.1, 0.0), 0.045, r2=0.08, n=14, emissive=True)
    b.seg("antenna", "amber", (0.05, 0.79, 0.04), (0.07, 0.86, 0.06), 0.008, n=6)
    b.anim = ()


def _s3000(b: _B) -> None:
    b.shadow(0.6, 0.56)
    c = (0.0, 0.66, 0.03)
    _orb_body(b, c, 0.3, sc=(1.1, 0.9, 1.0))
    b.cyl("dome", "amber", (0, 0.93, 0.05), 0.12, 0.05, n=16)
    b.cyl("dome", "joint", (0, 0.97, 0.05), 0.08, 0.04, n=16)
    b.sphere("dome", "body", (0, 1.0, 0.05), 0.14, n=16, m=8, sc=(1.0, 0.35, 1.0))
    b.ring("dome", "amber", (0, 0.995, 0.05), 0.145, 0.145, 0.015, n=16)
    b.cyl("core_housing", "amber", (0, 0.66, -0.275), 0.155, 0.05, axis="z", n=18)
    b.core((0, 0.66, -0.3), 0.09, n=18)
    b.cyl("side_pod", "amber", (0.33, 0.68, 0.0), 0.085, 0.09, axis="x", n=16)
    b.cyl("side_pod", "accent", (0.378, 0.68, 0.0), 0.05, 0.006, axis="x", n=14, emissive=True)
    for deg in (-38, 38, 142, 218):
        a = math.radians(deg)
        dx, dz = math.cos(a), math.sin(a)
        hip = (dx * 0.25, 0.58, 0.03 + dz * 0.22)
        knee = (dx * 0.56, 0.82, 0.03 + dz * 0.5)
        foot = (dx * 0.8, 0.04, 0.03 + dz * 0.7)
        b.sphere("leg", "joint", hip, 0.06, n=12, m=7)
        b.rbeam("leg", "amber", hip, knee, 0.13, 0.14, taper=0.9, bev=0.3)
        _joint(b, knee, 0.05, axis="z" if abs(dz) > abs(dx) else "x", color="dark", glow=False)
        b.rbeam("leg", "amber", knee, foot, 0.12, 0.13, taper=0.7, bev=0.3)
        b.rbeam("leg", "body", _add(knee, (dx * 0.04, -0.1, dz * 0.04)), _add(knee, (dx * 0.1, -0.45, dz * 0.09)),
                0.12, 0.04, taper=0.75, bev=0.3, side=(-dz, 0.0, dx))
        b.rbox("foot", "dark", (foot[0], 0.03, foot[2]), (0.08, 0.06, 0.08), bev=0.3)
    for hx, hz, ex, ez in ((0.05, -0.12, 0.2, -0.42), (-0.06, -0.08, -0.25, -0.36), (0.0, 0.1, 0.1, 0.45)):
        pts = [(hx + (ex - hx) * f, 0.42 - 0.4 * (1 - (1 - f) ** 2), hz + (ez - hz) * f)
               for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
        for a0, a1 in zip(pts, pts[1:]):
            b.seg("hose", "#3c372b", a0, a1, 0.016, n=8)
        b.seg("hose", "amber", pts[-1], _add(pts[-1], (0, 0.025, 0)), 0.026, n=10)


def _s10k(b: _B) -> None:
    b.shadow(0.95, 0.8)
    c = (0.0, 0.98, 0.05)
    for s in (-1, 1):
        for zz in (-0.3, 0.38):
            hip = (s * 0.46, 0.74, zz)
            knee = (s * 0.78, 0.6, zz * 1.3)
            foot = (s * 0.8, 0.1, zz * 1.35)
            b.rbox("leg", "amber", hip, (0.22, 0.26, 0.26), bev=0.3)
            b.rbeam("leg", "amber", hip, knee, 0.2, 0.21, taper=0.9, bev=0.3)
            b.sphere("leg", "dark", knee, 0.1, n=12, m=7)
            b.rbeam("leg", "body", knee, foot, 0.18, 0.19, taper=0.9, bev=0.25)
            b.rbeam("leg", "amber", _add(knee, (s * 0.08, -0.08, 0)), _add(foot, (s * 0.08, 0.16, 0)),
                    0.05, 0.17, taper=0.85, bev=0.3)
            b.rbox("foot", "dark", (foot[0], 0.06, foot[2]), (0.3, 0.12, 0.3), bev=0.25, top=(0.8, 0.8))
    _orb_body(b, c, 0.56, sc=(1.1, 0.88, 1.0), n=18, m=10)
    for s in (-1, 1):
        b.rbox("armor", "amber", (s * 0.5, 0.9, -0.2), (0.12, 0.3, 0.26), ry=s * 0.6, bev=0.3)
    b.cyl("core_housing", "amber", (0, 0.98, -0.52), 0.25, 0.07, axis="z", n=20)
    b.core((0, 0.98, -0.555), 0.15, n=20)
    # голова-сенсор сверху
    b.sphere("head", "body", (-0.22, 1.42, -0.12), 0.09, n=12, m=7)
    b.cyl("head", "amber", (-0.22, 1.42, -0.12), 0.093, 0.03, n=12)
    b.cyl("head", "accent", (-0.22, 1.43, -0.205), 0.03, 0.008, axis="z", n=10, emissive=True)
    # кран
    b.cyl("crane", "amber", (0.05, 1.42, 0.18), 0.15, 0.12, n=16)
    b.rbeam("crane", "amber", (0.05, 1.46, 0.18), (0.32, 2.2, -0.2), 0.09, 0.09, taper=0.8, bev=0.3)
    b.rbeam("crane", "dark", (0.06, 1.5, 0.22), (0.1, 1.85, 0.34), 0.05, 0.05, bev=0.3)
    b.sphere("crane", "dark", (0.32, 2.2, -0.2), 0.055, n=10, m=6)
    b.rbeam("crane", "amber", (0.32, 2.2, -0.2), (0.62, 2.04, -0.5), 0.07, 0.07, taper=0.8, bev=0.3)
    b.seg("crane", "dark", (0.62, 2.04, -0.5), (0.62, 1.62, -0.5), 0.006, n=6)
    b.rbox("crane", "amber", (0.62, 1.6, -0.5), (0.06, 0.05, 0.04), bev=0.3)
    b.beam("crane", "dark", (0.62, 1.58, -0.5), (0.64, 1.5, -0.52), 0.02, 0.02, taper=0.4)
    # сборщик минералов
    b.seg("harvester", "steel", (0.52, 1.02, -0.18), (0.78, 1.1, -0.36), 0.04, n=12)
    b.seg("harvester", "amber", (0.78, 1.1, -0.36), (0.88, 1.18, -0.46), 0.06, r2=0.19, n=18)
    b.seg("harvester", "glass", (0.885, 1.184, -0.465), (0.888, 1.186, -0.468), 0.17, n=18)
    # засев облаков
    b.cyl("cloud_seeder", "amber", (-0.32, 1.45, 0.25), 0.07, 0.26, n=14)
    b.cyl("cloud_seeder", "dark", (-0.32, 1.59, 0.25), 0.055, 0.03, n=14)
    for i, (dx, dy, r) in enumerate(((0.0, 0.1, 0.07), (0.06, 0.22, 0.09), (-0.03, 0.36, 0.11))):
        b.sphere("cloud_seeder", "cloud", (-0.32 + dx, 1.6 + dy, 0.25 + 0.02 * i), r, n=12, m=7)


def _s20k(b: _B) -> None:
    b.shadow(1.6, 1.45)
    # лесные посадки под станцией
    b.rbox("forest", "soil", (0, 0.16, 0.0), (1.5, 0.28, 1.25), bev=0.25, top=(0.95, 0.95))
    b.rbox("forest", "amber", (0, 0.31, 0.0), (1.56, 0.03, 1.31), bev=0.3)
    for i in range(18):
        a = i * 2.39996
        rr = 0.15 + 0.5 * ((i * 37) % 18) / 18.0
        x, z = math.cos(a) * rr * 1.2, math.sin(a) * rr
        h = 0.3 + 0.24 * ((i * 11) % 7) / 7.0
        g = "green2" if i % 3 else "green"
        b.seg("forest", "dark", (x, 0.32, z), (x, 0.42, z), 0.02, n=6)
        b.seg("forest", g, (x, 0.38, z), (x, 0.38 + h * 0.6, z), 0.12, r2=0.05, n=8)
        b.seg("forest", g, (x, 0.38 + h * 0.4, z), (x, 0.38 + h, z), 0.09, r2=0.0, n=8)
    # опоры
    for deg in (40, 140, 220, 320):
        a = math.radians(deg)
        dx, dz = math.cos(a), math.sin(a)
        hip = (dx * 1.0, 1.55, dz * 0.9)
        knee = (dx * 1.55, 1.05, dz * 1.35)
        foot = (dx * 1.6, 0.1, dz * 1.42)
        b.rbeam("leg", "amber", hip, knee, 0.24, 0.26, taper=0.9, bev=0.25)
        b.sphere("leg", "dark", knee, 0.14, n=12, m=7)
        b.rbeam("leg", "body", knee, foot, 0.22, 0.24, taper=0.9, bev=0.25)
        b.rbeam("leg", "amber", _add(knee, (dx * 0.12, -0.15, dz * 0.12)), _add(foot, (dx * 0.12, 0.3, dz * 0.12)),
                0.2, 0.06, taper=0.85, bev=0.3, side=(-dz, 0.0, dx))
        b.rbox("foot", "dark", (foot[0], 0.07, foot[2]), (0.38, 0.14, 0.38), ry=-a, top=(0.8, 0.8), bev=0.25)
    # станция
    b.cyl("station", "steel", (0, 1.6, 0), 1.0, 0.24, r2=1.25, n=24)
    b.cyl("station", "body", (0, 1.92, 0), 1.25, 0.42, n=24)
    b.cyl("station", "amber", (0, 1.92, 0), 1.275, 0.08, n=24)
    b.cyl("station", "amber", (0, 1.73, 0), 1.26, 0.04, n=24)
    b.cyl("station", "plate", (0, 2.15, 0), 1.18, 0.06, n=24, r2=1.0)
    b.cyl("station", "spray", (0, 1.47, 0), 0.32, 0.03, n=18, emissive=True)
    # модули по ободу
    for i in range(14):
        a = 2 * math.pi * (i + 0.5) / 14
        if abs(math.sin(a) + 1) < 0.25:      # спереди — ядро
            continue
        p = (math.cos(a) * 1.22, 1.98, math.sin(a) * 1.22)
        b.rbox("station", "plate", p, (0.36, 0.2, 0.14), ry=-a + math.pi / 2, bev=0.25)
        b.box("station", "accent", _add(p, (math.cos(a) * 0.072, 0.0, math.sin(a) * 0.072)),
              (0.22, 0.03, 0.005), ry=-a + math.pi / 2, emissive=True)
    b.sphere("dome", "body", (0, 2.18, 0.05), 0.62, n=18, m=8, sc=(1.0, 0.5, 1.0))
    b.ring("dome", "amber", (0, 2.3, 0.05), 0.5, 0.5, 0.04, n=18)
    b.cyl("core_housing", "amber", (0, 1.92, -1.25), 0.37, 0.12, axis="z", n=20)
    b.core((0, 1.92, -1.32), 0.25, n=20)
    # метеобашни
    towers = ((-0.75, 0.3, 0.75), (0.78, 0.25, 0.6), (-0.35, -0.55, 0.55), (0.45, -0.45, 0.45),
              (0.1, 0.62, 0.95), (-0.15, 0.1, 1.1))
    for x, z, h in towers:
        y0 = 2.15
        b.cyl("weather_tower", "body", (x, y0 + h / 2, z), 0.1, h, n=14)
        b.cyl("weather_tower", "amber", (x, y0 + h * 0.35, z), 0.115, 0.05, n=14)
        b.cyl("weather_tower", "accent", (x, y0 + h * 0.7, z), 0.106, 0.03, n=14, emissive=True)
        b.cyl("weather_tower", "amber", (x, y0 + h + 0.01, z), 0.13, 0.03, n=14)
        b.sphere("weather_tower", "body", (x, y0 + h + 0.05, z), 0.11, n=12, m=6, sc=(1, 0.8, 1))
        b.seg("weather_tower", "steel", (x, y0 + h + 0.12, z), (x, y0 + h + 0.3, z), 0.008, n=6)
    # кран на палубе
    b.rbeam("crane", "amber", (-0.55, 2.2, -0.45), (-0.95, 3.05, -0.2), 0.09, 0.09, taper=0.8, bev=0.3)
    b.rbeam("crane", "amber", (-0.95, 3.05, -0.2), (-1.4, 2.85, -0.45), 0.07, 0.07, taper=0.8, bev=0.3)
    b.seg("crane", "dark", (-1.4, 2.85, -0.45), (-1.4, 2.45, -0.45), 0.008, n=6)
    b.rbox("crane", "amber", (-1.4, 2.43, -0.45), (0.07, 0.06, 0.05), bev=0.3)


_BUILDERS = {
    "a1": _a1, "a2": _a2, "b1_1": _b1_1, "b1_2": _b1_2, "b2_1": _b2_1, "b2_2": _b2_2,
    "c1": _c1, "c2": _c2, "s1000": _s1000, "s3000": _s3000, "s10k": _s10k, "s20k": _s20k,
}


LOD_Q = {"low": 1.0, "high": 2.0}
_SCALE = {"b2_2": 1.14}       # B2.2 крупнее B2.1, как на концепте


@lru_cache(maxsize=None)
def _built(robot_id: str, lod: str = "low") -> tuple[Prim, ...]:
    rb = robot(robot_id)
    b = _B(rb.palette, LOD_Q[lod], _SCALE.get(robot_id, 1.0))
    _BUILDERS[robot_id](b)
    return tuple(b.prims)


def build(robot_id: str, lod: str = "low") -> list[Prim]:
    """Примитивы робота в локальных координатах (метры, y вверх, перед −z, земля y=0).

    ``lod="low"`` — для Canvas-рендера (плоские грани), ``"high"`` — вдвое больше
    сегментов у тел вращения, для гладкого рендера :mod:`stamina.terraformer_render`.
    Детерминирован; масштаб растёт с уровнем. Кэшируется, Prim неизменяемы.
    """
    return list(_built(robot_id, lod))


def polygon_count(robot_id: str, lod: str = "low") -> int:
    return sum(len(p.faces) for p in _built(robot_id, lod))


@lru_cache(maxsize=None)
def bounds(robot_id: str) -> tuple[Vec, Vec]:
    """(min, max) по всем вершинам в позе t=0 (без тени)."""
    xs, ys, zs = [], [], []
    for p in _built(robot_id):
        if p.part == "shadow":
            continue
        for x, y, z in p.verts:
            xs.append(x)
            ys.append(y)
            zs.append(z)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


@lru_cache(maxsize=None)
def _fit(robot_id: str) -> tuple[Vec, float]:
    lo, hi = bounds(robot_id)
    c = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
    rad = max(math.dist(c, v) for p in _built(robot_id) if p.part != "shadow" for v in p.verts)
    return c, rad


@lru_cache(maxsize=None)
def _line_radius(line: str) -> float:
    return max(_fit(r.id)[1] for r in ROBOTS if r.line == line)


# ─── рендер ─────────────────────────────────────────────────────────────────

def _rgb(hexc: str) -> tuple[int, int, int]:
    return int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)


@lru_cache(maxsize=8192)
def _shade(hexc: str, q: int) -> str:
    """q — яркость в 1/32: 32 = исходный цвет, больше — к белому."""
    r, g, b = _rgb(hexc)
    k = q / 32.0
    if k <= 1.0:
        r, g, b = r * k, g * k, b * k
    else:
        w = min(1.0, k - 1.0)
        r, g, b = r + (255 - r) * w, g + (255 - g) * w, b + (255 - b) * w
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _mix(a: str, b: str, w: float) -> str:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * w), int(ga + (gb - ga) * w), int(ba + (bb - ba) * w))


def _animated(p: Prim, t: float) -> tuple[tuple[Vec, ...], tuple[Vec, ...]]:
    if not p.anim:
        return p.verts, p.normals
    kind = p.anim[0]
    if kind == "bob":
        dy = p.anim[1] * math.sin(2 * math.pi * p.anim[2] * t)
        return tuple((x, y + dy, z) for x, y, z in p.verts), p.normals
    if kind == "orbit":
        a = p.anim[1] * t
        c, s = math.cos(a), math.sin(a)
        return (tuple((x * c + z * s, y, -x * s + z * c) for x, y, z in p.verts),
                tuple((x * c + z * s, y, -x * s + z * c) for x, y, z in p.normals))
    return p.verts, p.normals


def frame_polys(robot_id: str, yaw: float, pitch: float, zoom: float = 1.0,
                pan: tuple[float, float] = (0.0, 0.0), t: float = 0.0, *,
                width: int = 640, height: int = 640, fit: bool = True,
                scale: float = 0.44, parts: bool = False) -> list[tuple]:
    """Готовые к рисованию полигоны, от дальних к ближним: ``(coords, fill, outline)``.

    Без Tk — годится и для PIL. ``pan`` — экранный сдвиг ``(view_ox, view_oy)`` в
    пикселях, тот же, что возвращает ``laboratory.zoom_toward`` (зум к курсору).
    ``fit=True`` — робот вписан в кадр целиком; ``fit=False`` — общий масштаб линейки
    (видно, как роботы растут от уровня к уровню). ``parts=True`` — четвёртым
    элементом имя детали (подсказка «что под курсором»).
    """
    rb = robot(robot_id)
    c, rad = _fit(robot_id)
    if not fit:
        rad = _line_radius(rb.line)
        lo, hi = bounds(robot_id)
        c = ((lo[0] + hi[0]) / 2, lo[1] + rad * 0.95, (lo[2] + hi[2]) / 2)
    sc = 1.0 / rad
    cx, cy = width / 2.0, height / 2.0
    R = min(width, height) * scale
    ox, oy = pan
    c0, c1, c2 = c
    lx, ly, lz = _norm(_LIGHT)
    pal = rb.palette
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * CORE_PULSE_HZ * t)
    core_fill = _mix(pal["core_dim"], "#e9fdff", 0.35 + 0.6 * pulse)
    core_line = _mix(pal["core"], "#ffffff", 0.5 * pulse)
    pp = project_point
    rot = rotate_xyz
    out: list[tuple[float, int, list[float], str, str, str]] = []
    order = 0
    for p in _built(robot_id):
        verts, normals = _animated(p, t)
        proj = [pp((x - c0) * sc, -(y - c1) * sc, (z - c2) * sc, yaw=yaw, pitch=pitch, zoom=zoom,
                   pan_x=0.0, pan_y=0.0, cx=cx, cy=cy, R=R, view_ox=ox, view_oy=oy)
                for x, y, z in verts]
        is_shadow = p.part == "shadow"
        for fi, f in enumerate(p.faces):
            pts = [proj[i] for i in f]
            if not p.double:
                area = 0.0
                m = len(pts)
                for i in range(m):
                    x1, y1, _d1 = pts[i]
                    x2, y2, _d2 = pts[(i + 1) % m]
                    area += x1 * y2 - x2 * y1
                if area * _CULL_SIGN <= 0.0:
                    continue
            if is_shadow:
                fill = outline = p.color
                depth = -1e9
            else:
                depth = sum(q[2] for q in pts) / len(pts)
                if p.emissive:
                    if p.part == "core":
                        fill, outline = core_fill, core_line
                    elif p.part == "core_ring":
                        fill = _mix(p.color, "#ffffff", 0.25 * pulse)
                        outline = fill
                    else:
                        fill = outline = p.color
                else:
                    nx, ny, nz = normals[fi]
                    rx, ry, rz = rot(nx, -ny, nz, yaw, pitch)
                    lam = rx * lx + ry * ly + rz * lz
                    if lam < 0.0:
                        lam = 0.0
                    rim = 0.12 if rz > -0.25 else 0.0      # подсветка граней «в профиль»
                    q = int(32 * (0.36 + 0.78 * lam + rim))
                    fill = _shade(p.color, q)
                    outline = _shade(p.color, max(4, q - 7))
            coords = [v for q in pts for v in (q[0], q[1])]
            out.append((depth, order, coords, fill, outline, p.part))
            order += 1
    out.sort(key=lambda e: (e[0], e[1]))
    if parts:
        return [(e[2], e[3], e[4], e[5]) for e in out]
    return [(e[2], e[3], e[4]) for e in out]


def draw(canvas, robot_id: str, yaw: float = DEFAULT_YAW, pitch: float = DEFAULT_PITCH,
         zoom: float = 1.0, pan: tuple[float, float] = (0.0, 0.0), t: float = 0.0, *,
         fit: bool = True, tag: str = "tf_robot", size: tuple[int, int] | None = None,
         scale: float = 0.44) -> dict:
    """Нарисовать робота на ``tk.Canvas`` (стирает прежние элементы с тегом ``tag``).

    Центр кадра — середина холста; он же ``origin_xy`` для ``zoom_toward``.
    Возвращает ``{"polys": нарисовано, "total": граней в модели, "ms": время}``.
    """
    t0 = time.perf_counter()
    if size is None:
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            w = int(canvas.cget("width"))
            h = int(canvas.cget("height"))
    else:
        w, h = size
    polys = frame_polys(robot_id, yaw, pitch, zoom, pan, t, width=w, height=h, fit=fit, scale=scale)
    canvas.delete(tag)
    cp = canvas.create_polygon
    for coords, fill, outline in polys:
        cp(coords, fill=fill, outline=outline, tags=tag)
    return {"polys": len(polys), "total": polygon_count(robot_id),
            "ms": (time.perf_counter() - t0) * 1000.0}


# ─── управление камерой (как у сущности в Лаборатории) ────────────────────

class OrbitView:
    """Состояние камеры отсека + привязки мыши.

    Ctrl+колёсико — ``zoom_toward`` к курсору, ЛКМ-перетаскивание — орбита
    yaw/pitch с ``ORBIT_SENS`` и ``clamp_pitch``. ``pan`` → передавать в :func:`draw`.
    """

    def __init__(self, yaw: float = DEFAULT_YAW, pitch: float = DEFAULT_PITCH, zoom: float = 1.0) -> None:
        self.home = (yaw, pitch, zoom)
        self.yaw, self.pitch, self.zoom = yaw, pitch, zoom
        self.view_ox = self.view_oy = 0.0
        self._drag: list | None = None
        self._canvas = None
        self._on_change = None

    @property
    def pan(self) -> tuple[float, float]:
        return self.view_ox, self.view_oy

    def reset(self) -> None:
        self.yaw, self.pitch, self.zoom = self.home
        self.view_ox = self.view_oy = 0.0
        self._changed()

    def attach(self, canvas, on_change) -> None:
        """Повесить обработчики на холст; ``on_change()`` вызывается после каждой смены вида."""
        self._canvas, self._on_change = canvas, on_change
        canvas.bind("<ButtonPress-1>", self.on_press, add="+")
        canvas.bind("<B1-Motion>", self.on_drag, add="+")
        canvas.bind("<ButtonRelease-1>", self.on_release, add="+")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(seq, self.on_wheel, add="+")
        canvas.bind("<Double-Button-1>", lambda _e: self.reset(), add="+")

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _origin(self) -> tuple[float, float]:
        cv = self._canvas
        return cv.winfo_width() / 2.0, cv.winfo_height() / 2.0

    def zoom_at(self, factor: float, cursor_xy: tuple[float, float], origin_xy: tuple[float, float]) -> None:
        self.zoom, self.view_ox, self.view_oy = zoom_toward(
            self.zoom, self.view_ox, self.view_oy, factor=factor, cursor_xy=cursor_xy, origin_xy=origin_xy)

    def orbit(self, dx: float, dy: float, yaw0: float | None = None, pitch0: float | None = None) -> None:
        self.yaw = (self.yaw if yaw0 is None else yaw0) + dx * ORBIT_SENS
        self.pitch = clamp_pitch((self.pitch if pitch0 is None else pitch0) - dy * ORBIT_SENS)

    def on_wheel(self, e):
        if not (int(getattr(e, "state", 0) or 0) & CTRL):
            return None
        d = wheel_direction(e)
        if not d:
            return None
        self.zoom_at(ZOOM_STEP if d < 0 else 1.0 / ZOOM_STEP, (float(e.x), float(e.y)), self._origin())
        self._changed()
        return "break"

    def on_press(self, e) -> None:
        self._drag = [float(e.x), float(e.y), self.yaw, self.pitch]

    def on_drag(self, e) -> None:
        if not self._drag:
            return
        x0, y0, yaw0, pitch0 = self._drag
        self.orbit(float(e.x) - x0, float(e.y) - y0, yaw0, pitch0)
        self._changed()

    def on_release(self, _e) -> None:
        self._drag = None
