"""Гладкий рендер роботов-терраформеров: numpy + PIL → ``tk.PhotoImage``.

Почему так. Плоские полигоны Tk Canvas дают «штуковину»: грани видны, нет
бликов, нет свечения. Здесь — отложенное затенение (deferred shading):

1. геометрия из :mod:`stamina.terraformer_models` (``lod="high"``), треугольники
   с нормалями в углах (гладкие сферы/цилиндры, острые рёбра брони);
2. поворот/проекция — матрица из ``laboratory.rotate_xyz`` и формула
   ``laboratory.project_point`` (векторно; совпадение проверяет тест);
3. растеризация — PIL ``ImageDraw.polygon`` (C) в буфер номеров треугольников,
   от дальних к ближним; при SSAA 2× каждый пиксель кадра — 4 сэмпла;
4. затенение в numpy по пикселям: барицентрическая интерполяция нормалей,
   ключевой тёплый + холодный заполняющий + голубой контровой свет, полусфера
   неба/пола, блики Блинна—Фонга, френель-кайма; тонкие «швы» между деталями;
5. ядро и светящиеся полосы — отдельный слой + bloom (размытие на ¼ разрешения),
   пульс ядра — дешёвое пересмешивание слоёв без перерендера;
6. мягкая тень на полу, итог — RGBA (полупрозрачная тень и свечение ложатся
   на любой фон отсека).

При перетаскивании — ``quality="drag"`` (1×, уменьшенный кадр), после отпускания —
``"full"`` (SSAA 2×). Если numpy или ``PIL.ImageTk`` нет — :class:`TerraformerViewer`
сам переходит на Canvas-рендер ``terraformer_models.draw``.

Импорт не создаёт окон Tk.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import lru_cache

from stamina import terraformer_models as tm
from stamina.laboratory import rotate_xyz

try:  # необязательная зависимость: без неё — Canvas-рендер
    import numpy as np
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - проверяется на машине без numpy
    np = None  # type: ignore[assignment]
    HAVE_NUMPY = False

# Константы проекции stamina.laboratory.project_point (тест сверяет поточечно).
SPLIT_LEN = 0.3       # доля радиуса робота: длиннее — режем (точнее painter)
DEPTH_K = 0.42
DEPTH_MIN = 0.45
Y_ASPECT = 0.86

QUALITY = {
    # ss — сэмплов на сторону пикселя; res — доля разрешения кадра; bloom — свечение
    # lod — какая сетка: при перетаскивании хватает «low» (вдвое меньше граней)
    "full": {"ss": 2, "res": 1.0, "bloom": True, "lod": "high"},
    "live": {"ss": 1, "res": 0.8, "bloom": True, "lod": "high"},
    "drag": {"ss": 1, "res": 0.42, "bloom": False, "lod": "low"},
}


def _srgb_to_lin(c):
    return np.power(c, 2.2)


def _lin_to_srgb(c):
    return np.power(np.clip(c, 0.0, 1.0), 1 / 2.2)


@dataclass
class _Mesh:
    v: object        # (T,3,3) float32 локальные координаты
    n: object        # (T,3,3) нормали углов
    albedo: object   # (T,3) линейный цвет
    emis: object     # (T,) bool
    core: object     # (T,) bool — пульсирующее ядро
    prim: object     # (T,) int — номер детали (для швов)
    orbit: object    # (T,) скорость орбиты (0 — нет)
    bob: object      # (T,2) амплитуда, частота
    shadow: object   # (K,3) контур тени
    bias: object     # (T,) сдвиг глубины для сортировки
    animated: bool


@lru_cache(maxsize=32)
def _mesh(robot_id: str, lod: str = "high") -> _Mesh:
    tv, tn, alb, em, co, pr, orb, bob, bias = [], [], [], [], [], [], [], [], []
    shadow = None
    for pi, p in enumerate(tm.build(robot_id, lod)):
        if p.part == "shadow":
            shadow = [p.verts[i] for i in p.faces[0]]
            continue
        rgb = [int(p.color[k:k + 2], 16) / 255.0 for k in (1, 3, 5)]
        o = p.anim[1] if p.anim and p.anim[0] == "orbit" else 0.0
        bb = (p.anim[1], p.anim[2]) if p.anim and p.anim[0] == "bob" else (0.0, 0.0)
        # ядро рисуем поверх своего обода: небольшой сдвиг глубины в сортировке
        bz = {"core": 0.04, "core_ring": 0.02}.get(p.part, 0.0)
        for fi, f in enumerate(p.faces):
            cn = p.cnormals[fi] if p.cnormals else (p.normals[fi],) * len(f)
            pts = [p.verts[i] for i in f]
            if len(f) > 4:                           # крышки — веером от центра, без «щепок»
                cv = tuple(sum(q[j] for q in pts) / len(pts) for j in range(3))
                cnn = p.normals[fi]
                tris = [(cv, pts[k], pts[(k + 1) % len(f)]) for k in range(len(f))]
                nors = [(cnn, cn[k], cn[(k + 1) % len(f)]) for k in range(len(f))]
            else:
                tris = [(pts[0], pts[k], pts[k + 1]) for k in range(1, len(f) - 1)]
                nors = [(cn[0], cn[k], cn[k + 1]) for k in range(1, len(f) - 1)]
            for tri, nor in zip(tris, nors):
                tv.append(tri)
                tn.append(nor)
                alb.append(rgb)
                em.append(p.emissive)
                co.append(p.part == "core")
                pr.append(pi)
                orb.append(o)
                bob.append(bb)
                bias.append(bz)
    # длинные треугольники режем пополам по длинной стороне: точнее сортировка painter'а
    _c, rad = tm._fit(robot_id)
    lim = SPLIT_LEN * rad
    tv, tn, alb, em, co, pr, orb, bob, bias = _split_long(tv, tn, [alb, em, co, pr, orb, bob, bias], lim)
    alb_a = _srgb_to_lin(np.array(alb, dtype=np.float32))
    return _Mesh(np.array(tv, dtype=np.float32), np.array(tn, dtype=np.float32), alb_a,
                 np.array(em, dtype=bool), np.array(co, dtype=bool), np.array(pr, dtype=np.int32),
                 np.array(orb, dtype=np.float32), np.array(bob, dtype=np.float32),
                 np.array(shadow or [(0, 0, 0)] * 3, dtype=np.float32),
                 np.array(bias, dtype=np.float32),
                 bool(np.any(np.array(orb) != 0) or np.any(np.array(bob)[:, 0] != 0)))


def _split_long(tv, tn, extra, lim):
    """Бисекция треугольников длиннее ``lim`` (до 4 уровней); extra — атрибуты на треугольник."""
    out_v, out_n = [], []
    out_x: list[list] = [[] for _ in extra]
    stack = [(tv[i], tn[i], i, 0) for i in range(len(tv) - 1, -1, -1)]
    lim2 = lim * lim
    while stack:
        v, n, src, depth = stack.pop()
        e = [sum((v[(k + 1) % 3][j] - v[k][j]) ** 2 for j in range(3)) for k in range(3)]
        k = max(range(3), key=e.__getitem__)
        if e[k] <= lim2 or depth >= 3:
            out_v.append(v)
            out_n.append(n)
            for lst, src_l in zip(out_x, extra):
                lst.append(src_l[src])
            continue
        a, b, c = k, (k + 1) % 3, (k + 2) % 3
        mv = tuple((v[a][j] + v[b][j]) / 2 for j in range(3))
        mn = tuple((n[a][j] + n[b][j]) / 2 for j in range(3))
        t1 = [None, None, None]
        t2 = [None, None, None]
        # (a, m, c) и (m, b, c) в исходном порядке обхода
        v1, n1 = list(v), list(n)
        v1[b], n1[b] = mv, mn
        v2, n2 = list(v), list(n)
        v2[a], n2[a] = mv, mn
        del t1, t2
        stack.append((tuple(v2), tuple(n2), src, depth + 1))
        stack.append((tuple(v1), tuple(n1), src, depth + 1))
    return (out_v, out_n, *out_x)


def triangle_count(robot_id: str, lod: str = "high") -> int:
    return int(_mesh(robot_id, lod).v.shape[0])


def rotation_matrix(yaw: float, pitch: float):
    """Матрица 3×3, собранная из ``laboratory.rotate_xyz`` (столбцы — образы осей)."""
    cols = [rotate_xyz(*e, yaw, pitch) for e in ((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0))]
    return np.array(cols, dtype=np.float64).T


def project(points, *, yaw, pitch, zoom, cx, cy, R, view_ox=0.0, view_oy=0.0):
    """Векторный двойник ``laboratory.project_point``: (N,3) → sx, sy, depth, rz."""
    M = rotation_matrix(yaw, pitch)
    r = points @ M.T.astype(points.dtype)
    rz = r[..., 2]
    depth = 1.0 / np.maximum(DEPTH_MIN, 1.0 + rz * DEPTH_K)
    sx = cx + r[..., 0] * zoom * R * depth + view_ox
    sy = cy + r[..., 1] * zoom * R * Y_ASPECT * depth + view_oy
    return sx, sy, depth, M


def _norm_rows(a):
    return a / np.maximum(1e-6, np.sqrt((a * a).sum(-1, keepdims=True)))


_KEY = _norm_rows(np.array([-0.55, -0.72, -0.45])) if HAVE_NUMPY else None
_FILL = _norm_rows(np.array([0.75, -0.05, -0.35])) if HAVE_NUMPY else None
_RIM = _norm_rows(np.array([0.25, -0.35, 0.9])) if HAVE_NUMPY else None
_HALF = _norm_rows(_KEY + np.array([0.0, 0.0, -1.0])) if HAVE_NUMPY else None


class Frame:
    """Кадр в слоях (обрезан по рамке робота): база, свечение, альфа — 8-бит PIL.

    ``image(pulse)`` → ``(PIL RGBA, (x, y))`` — картинка и её левый верхний угол
    на холсте. Пульс ядра меняет только вес слоя свечения (LUT + сложение в C,
    без перерендера и без numpy).
    """

    def __init__(self, base, glow, alpha, offset, up, size, ms):
        a = np.clip(alpha, 0.0, 1.0)
        inv = 1.0 / np.maximum(a, 1e-3)
        straight = np.minimum(base * inv[..., None], 1.0)          # снять премультипликацию SSAA
        self.base = Image.fromarray((straight * 255.0).astype(np.uint8), "RGB")
        self.alpha = Image.fromarray((a * 255.0).astype(np.uint8), "L")
        g = np.minimum(glow, 1.0)
        self.glow = Image.fromarray((g * 255.0).astype(np.uint8), "RGB")
        self.glow_a = Image.fromarray((np.minimum(g.max(-1) * 0.9, 1.0) * 255.0).astype(np.uint8), "L")
        self.offset = offset          # (x, y) в пикселях рендера
        self.up = up                  # множитель до размера кадра (drag: 1/res)
        self.size = size              # (width, height) кадра
        self.ms = ms

    def image(self, pulse: float = 0.5):
        k = 0.6 + 0.4 * pulse
        lut = [min(255, int(i * k)) for i in range(256)]
        rgb = ImageChops.add(self.base, self.glow.point(lut * 3))
        a = ImageChops.lighter(self.alpha, self.glow_a.point(lut))
        im = Image.merge("RGBA", (*rgb.split(), a))
        x, y = self.offset
        if self.up != 1.0:
            im = im.resize((max(1, round(im.width * self.up)), max(1, round(im.height * self.up))),
                           Image.BILINEAR)
            x, y = round(x * self.up), round(y * self.up)
        return im, (x, y)

    def composite(self, bg=(11, 17, 24), pulse: float = 0.5):
        """Кадр целиком на сплошном фоне (превью, тесты)."""
        im, (x, y) = self.image(pulse)
        if isinstance(bg, str):
            bg = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
        canvas = Image.new("RGBA", self.size, tuple(bg) + (255,))
        canvas.alpha_composite(im, (x, y))
        return canvas.convert("RGB")


def render(robot_id: str, yaw: float = tm.DEFAULT_YAW, pitch: float = tm.DEFAULT_PITCH,
           zoom: float = 1.0, pan: tuple[float, float] = (0.0, 0.0), t: float = 0.0, *,
           width: int = 640, height: int = 640, quality: str = "full", fit: bool = True,
           scale: float = 0.44) -> Frame:
    """Отрендерить робота в :class:`Frame` размером ``width×height``.

    Параметры камеры — как у ``terraformer_models.draw``: ``pan`` — экранный сдвиг
    ``(view_ox, view_oy)`` из ``laboratory.zoom_toward``, центр — середина кадра.
    """
    t0 = time.perf_counter()
    q = QUALITY[quality]
    ss, res = q["ss"], q["res"]
    m = _mesh(robot_id, q.get("lod", "high"))
    rw, rh = max(8, int(width * res)), max(8, int(height * res))
    W, H = rw * ss, rh * ss
    k = res * ss
    R = min(width, height) * scale * k
    cx, cy = W / 2.0, H / 2.0
    ox, oy = pan[0] * k, pan[1] * k

    c, rad = tm._fit(robot_id)
    if not fit:
        rad = tm._line_radius(tm.robot(robot_id).line)
        lo, hi = tm.bounds(robot_id)
        c = ((lo[0] + hi[0]) / 2, lo[1] + rad * 0.95, (lo[2] + hi[2]) / 2)
    cen = np.array(c, dtype=np.float32)
    s = np.float32(1.0 / rad)

    v, n = m.v, m.n
    if m.animated:
        v = v.copy()
        n = n.copy()
        sel = m.orbit != 0
        if sel.any():
            a = (m.orbit[sel] * t)[:, None]
            ca, sa = np.cos(a), np.sin(a)
            for arr in (v, n):
                x, z = arr[sel, :, 0].copy(), arr[sel, :, 2].copy()
                arr[sel, :, 0] = x * ca + z * sa
                arr[sel, :, 2] = -x * sa + z * ca
        selb = m.bob[:, 0] != 0
        if selb.any():
            dy = m.bob[selb, 0] * np.sin(2 * math.pi * m.bob[selb, 1] * t)
            v[selb, :, 1] += dy[:, None]

    P = (v - cen) * s
    P[..., 1] *= -1.0
    sx, sy, depth, M = project(P, yaw=yaw, pitch=pitch, zoom=zoom, cx=cx, cy=cy, R=R,
                               view_ox=ox, view_oy=oy)
    # отсечение задних граней и вырожденных
    x0, x1, x2 = sx[:, 0], sx[:, 1], sx[:, 2]
    y0, y1, y2 = sy[:, 0], sy[:, 1], sy[:, 2]
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    # меньше ~¼ пикселя кадра — не видно: не тратим вызов растеризации
    vis = np.nonzero(det * tm._CULL_SIGN > 0.5 * ss * ss)[0]
    order = vis[np.argsort(depth[vis].mean(1) + m.bias[vis], kind="stable")]

    # 1) буфер номеров треугольников (painter: дальние → ближние)
    idimg = Image.new("I", (W, H), 0)
    dr = ImageDraw.Draw(idimg)
    pts = np.stack([sx[order], sy[order]], -1).reshape(len(order), 6).tolist()
    core_draw = getattr(dr, "draw", None)
    if core_draw is not None and hasattr(core_draw, "draw_polygon"):
        poly = core_draw.draw_polygon            # без обёртки ImageDraw: ~3× быстрее на тысячах треугольников
        for i, tri in enumerate(pts, 1):
            poly(tri, i, 1)
    else:  # pragma: no cover - другая сборка Pillow
        for i, tri in enumerate(pts, 1):
            dr.polygon(tri, fill=i)
    ids = np.asarray(idimg, dtype=np.int32)
    mask = ids > 0
    yy, xx = np.nonzero(mask)
    li = ids[yy, xx] - 1
    ti = order[li]

    # 2) барицентрика и нормаль в пикселе
    px = xx.astype(np.float32) + 0.5
    py = yy.astype(np.float32) + 0.5
    X0, Y0 = x0[ti], y0[ti]
    dX1, dY1 = x1[ti] - X0, y1[ti] - Y0
    dX2, dY2 = x2[ti] - X0, y2[ti] - Y0
    dd = det[ti]
    qx, qy = px - X0, py - Y0
    b1 = np.clip((qx * dY2 - qy * dX2) / dd, 0, 1)[:, None]
    b2 = np.clip((qy * dX1 - qx * dY1) / dd, 0, 1)[:, None]
    b0 = np.clip(1.0 - b1 - b2, 0, 1)
    Mt = M.T.astype(np.float32)
    nn = n[ti]
    nrm = (b0 * nn[:, 0] + b1 * nn[:, 1] + b2 * nn[:, 2])
    nrm[:, 1] *= -1.0
    nrm = _norm_rows(nrm @ Mt)

    # 3) свет
    alb = m.albedo[ti]
    ndl = np.clip(nrm @ _KEY.astype(np.float32), 0, 1)[:, None]
    ndf = np.clip(nrm @ _FILL.astype(np.float32), 0, 1)[:, None]
    ndr = np.clip(nrm @ _RIM.astype(np.float32), 0, 1)[:, None]
    up = np.clip(-nrm[:, 1:2], -1, 1)
    nv = np.clip(-nrm[:, 2:3], 0, 1)                 # к камере
    amb = 0.10 + 0.07 * up
    diffuse = alb * (amb + 1.05 * ndl * np.array([1.0, 0.95, 0.88], np.float32)
                     + 0.32 * ndf * np.array([0.55, 0.7, 0.95], np.float32))
    spec = np.power(np.clip(nrm @ _HALF.astype(np.float32), 0, 1), 48)[:, None] * 0.55
    fres = np.power(1.0 - nv, 3) * 0.35
    rim = (0.45 * ndr + fres) * np.array([0.35, 0.75, 1.0], np.float32)
    col = diffuse + spec + rim * (0.35 + 0.65 * alb.mean(1, keepdims=True))
    em = m.emis[ti]
    col[em] = alb[em] * 1.0
    col = _lin_to_srgb(col)

    # рабочая рамка: робот + тень + запас под свечение (кратно ss)
    shadow = m.shadow
    Ps = (shadow - cen) * s
    Ps[:, 1] *= -1.0
    shx, shy, _d, _M = project(Ps, yaw=yaw, pitch=pitch, zoom=zoom, cx=cx, cy=cy, R=R,
                               view_ox=ox, view_oy=oy)
    pad = int(min(W, H) * (0.07 if q["bloom"] else 0.01)) + 2 * ss
    if len(xx):
        bx0 = min(int(xx.min()), int(shx.min())) - pad
        bx1 = max(int(xx.max()), int(shx.max())) + pad
        by0 = min(int(yy.min()), int(shy.min())) - pad
        by1 = max(int(yy.max()), int(shy.max())) + pad
    else:
        bx0 = by0 = 0
        bx1 = by1 = 2 * ss
    bx0 = max(0, bx0 // ss * ss)
    by0 = max(0, by0 // ss * ss)
    bx1 = min(W, -(-bx1 // ss) * ss)
    by1 = min(H, -(-by1 // ss) * ss)
    Wc, Hc = max(ss, bx1 - bx0), max(ss, by1 - by0)
    ly, lx = yy - by0, xx - bx0

    # 4) швы между деталями (тёмная линия по смене детали и по силуэту)
    pid = np.full((Hc, Wc), -1, dtype=np.int32)
    pid[ly, lx] = m.prim[ti]
    edge = np.zeros((Hc, Wc), dtype=bool)
    edge[:, 1:] |= pid[:, 1:] != pid[:, :-1]
    edge[1:, :] |= pid[1:, :] != pid[:-1, :]
    e = edge[ly, lx]
    col[e & ~em] *= 0.62

    img = np.zeros((Hc, Wc, 3), dtype=np.float32)
    img[ly, lx] = col
    glow = np.zeros((Hc, Wc, 3), dtype=np.float32)
    has_glow = bool(em.any())
    if has_glow:
        cm = m.core[ti][em][:, None]
        glow[ly[em], lx[em]] = col[em] * np.where(cm, 0.6, 0.35)
        img[ly[em], lx[em]] *= np.where(cm, 0.5, 0.75)
    alpha = np.zeros((Hc, Wc), dtype=np.float32)
    alpha[ly, lx] = 1.0

    # 5) SSAA вниз
    hc, wc = Hc // ss, Wc // ss
    if ss > 1:
        def down(a):
            return a.reshape((hc, ss, wc, ss) + a.shape[2:]).mean(axis=(1, 3))
        img, glow, alpha = down(img), down(glow), down(alpha)

    # 6) мягкая тень на полу (только альфа: чёрная полупрозрачная)
    sh_img = Image.new("L", (wc, hc), 0)
    ImageDraw.Draw(sh_img).polygon(
        list(zip(((shx - bx0) / ss).tolist(), ((shy - by0) / ss).tolist())), fill=150)
    sh_small = sh_img.resize((max(2, wc // 3), max(2, hc // 3)), Image.BILINEAR)
    sh_small = sh_small.filter(ImageFilter.GaussianBlur(max(1.0, rw / 220)))
    sha = np.asarray(sh_small.resize((wc, hc), Image.BILINEAR), dtype=np.float32) * (1 / 255.0)
    alpha = alpha + sha * (1.0 - alpha)

    # 7) bloom вокруг ядра и светящихся полос
    if q["bloom"] and has_glow:
        gimg = Image.fromarray((np.minimum(glow, 1.0) * 255).astype(np.uint8), "RGB")
        small = gimg.resize((max(4, wc // 4), max(4, hc // 4)), Image.BILINEAR)
        small = small.filter(ImageFilter.GaussianBlur(max(1.5, rw / 170)))
        big = np.asarray(small.resize((wc, hc), Image.BILINEAR), dtype=np.float32) * (0.85 / 255.0)
        glow = glow + big
    img = np.ascontiguousarray(img)
    glow = np.ascontiguousarray(glow)
    alpha = np.ascontiguousarray(alpha)
    c0, r0 = bx0 // ss, by0 // ss
    ms = (time.perf_counter() - t0) * 1000.0
    return Frame(img, glow, alpha, (c0, r0), 1.0 / res, (width, height), ms)


def core_pulse(t: float) -> float:
    return 0.5 + 0.5 * math.sin(2 * math.pi * tm.CORE_PULSE_HZ * t)


# ─── виджет для отсека ─────────────────────────────────────────────────────

class TerraformerViewer:
    """Показ робота на готовом ``tk.Canvas`` отсека: гладкий рендер + камера Лаборатории.

    ``viewer = TerraformerViewer(canvas, "a1"); viewer.start()`` — и всё:
    ЛКМ-перетаскивание вращает (кадр 0.6× без bloom — плавно), отпускание — полный
    SSAA-кадр; Ctrl+колёсико — зум к курсору; двойной клик — исходный вид. Ядро
    пульсирует (пересмешивание слоёв), рой C2 и парение S-1000 анимируются кадрами
    ``live``. Без numpy — Canvas-рендер ``terraformer_models.draw``.
    """

    TICK_MS = 50          # пульс ядра — только пересмешивание слоёв (~5 мс)
    TICK_MS_ANIM = 80     # рой C2 / парение S-1000 — перерендер кадра «live»

    def __init__(self, canvas, robot_id: str, *, smooth: bool | None = None, tag: str = "tf_robot") -> None:
        self.cv = canvas
        self.robot_id = robot_id
        self.tag = tag
        self.view = tm.OrbitView()
        self.smooth = HAVE_NUMPY if smooth is None else (smooth and HAVE_NUMPY)
        if self.smooth:
            try:
                from PIL import ImageTk
                self._ImageTk = ImageTk
            except ImportError:  # pragma: no cover
                self.smooth = False
        self._photo = None
        self._frame: Frame | None = None
        self._dragging = False
        self._job = None
        self._full_job = None
        self._t0 = time.monotonic()
        self.last_ms = 0.0
        self.view.attach(canvas, self._on_view)
        canvas.bind("<ButtonPress-1>", self._press, add="+")
        canvas.bind("<ButtonRelease-1>", self._release, add="+")
        canvas.bind("<Configure>", lambda _e: self.redraw("full"), add="+")

    # публичное
    def set_robot(self, robot_id: str) -> None:
        self.robot_id = robot_id
        self.view.reset()
        self.redraw("full")
        self._warm()

    def _warm(self) -> None:
        """Заранее собрать сетку «drag», чтобы первое перетаскивание не дёрнулось."""
        if self.smooth:
            _mesh(self.robot_id, QUALITY["drag"]["lod"])

    def start(self) -> None:
        self.redraw("full")
        self._warm()
        if self._job is None:
            self._job = self.cv.after(self.TICK_MS, self._tick)

    def stop(self) -> None:
        for j in (self._job, self._full_job):
            if j is not None:
                try:
                    self.cv.after_cancel(j)
                except Exception:  # noqa: BLE001
                    pass
        self._job = self._full_job = None

    def redraw(self, quality: str = "full") -> None:
        t = time.monotonic() - self._t0
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 16 or h < 16:
            return
        v = self.view
        t0 = time.perf_counter()
        if not self.smooth:
            tm.draw(self.cv, self.robot_id, v.yaw, v.pitch, v.zoom, v.pan, t, tag=self.tag)
        else:
            self._frame = render(self.robot_id, v.yaw, v.pitch, v.zoom, v.pan, t,
                                 width=w, height=h, quality=quality)
            self._show(core_pulse(t))
        self.last_ms = (time.perf_counter() - t0) * 1000.0

    # внутреннее
    def _show(self, pulse: float) -> None:
        im, (x, y) = self._frame.image(pulse)
        if self._photo is not None and (self._photo.width(), self._photo.height()) == im.size:
            self._photo.paste(im)
            self.cv.coords(self._item, x, y)
        else:
            self._photo = self._ImageTk.PhotoImage(im, master=self.cv)
            self.cv.delete(self.tag)
            self._item = self.cv.create_image(x, y, image=self._photo, anchor="nw", tags=self.tag)

    def _on_view(self) -> None:
        self.redraw("drag" if self._dragging else "live")
        if not self._dragging:
            self._schedule_full()

    def _press(self, _e) -> None:
        self._dragging = True

    def _release(self, _e) -> None:
        self._dragging = False
        self._schedule_full()

    def _schedule_full(self) -> None:
        if self._full_job is not None:
            self.cv.after_cancel(self._full_job)
        self._full_job = self.cv.after(120, self._do_full)

    def _do_full(self) -> None:
        self._full_job = None
        self.redraw("full")

    def _tick(self) -> None:
        self._job = None
        try:
            if not self.cv.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        if not self._dragging and self._full_job is None:
            t = time.monotonic() - self._t0
            if not self.smooth:
                self.redraw("live")
            elif _mesh(self.robot_id).animated:
                self.redraw("live")
            elif self._frame is not None:
                self._show(core_pulse(t))
        busy = self.smooth and _mesh(self.robot_id).animated
        self._job = self.cv.after(self.TICK_MS_ANIM if busy else self.TICK_MS, self._tick)
