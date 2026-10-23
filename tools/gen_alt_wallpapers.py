"""Генератор обоев отсеков ALT UI: реальные фото (NASA/ESA, Wikimedia Commons) + процедурный фолбэк.

python tools/gen_alt_wallpapers.py  ->  stamina/assets/alt_wallpapers/<profile>/<zone>.jpg
Звездолёт: вид из окон корпуса (иллюминаторы, обзорные окна, консоли).
Стимпанк: комнаты мастерской изобретателя (верстаки, чертежи, смотровые стёкла).
"""
from __future__ import annotations
import math, random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 900
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stamina" / "assets" / "alt_wallpapers"


def grad(c1, c2, vertical=True):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    n = H if vertical else W
    for i in range(n):
        t = i / (n - 1); c = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
        d.line([(0, i), (W, i)] if vertical else [(i, 0), (i, H)], fill=c)
    return im


def _add(im, blur, sharp):
    from PIL import ImageChops
    return ImageChops.add(ImageChops.add(im, blur), sharp)


def stars(d, rnd, n=600, box=(0, 0, W, H)):
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1); b = rnd.randint(90, 255)
        r = rnd.choice([0, 0, 0, 1, 1, 2]); c = (b, b, min(255, b + 20))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)


def nebula(im, rnd, col, n=7):
    lay = Image.new("RGB", im.size); d = ImageDraw.Draw(lay)
    for _ in range(n):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(150, 420)
        d.ellipse([x - r, y - r * .6, x + r, y + r * .6], fill=tuple(int(c * rnd.uniform(.25, .5)) for c in col))
    return _add(im, lay.filter(ImageFilter.GaussianBlur(120)), Image.new("RGB", im.size))


def space(rnd, col=(40, 90, 160)):
    im = grad((3, 6, 14), (8, 14, 30)); im = nebula(im, rnd, col); stars(ImageDraw.Draw(im), rnd); return im


def plate_over(im, holes, rnd, base=(26, 34, 46), seam=(14, 18, 26), accent=(0, 200, 230)):
    """Переборка с вырезанными окнами holes: список ('ellipse'|'poly'|'rect', coords)."""
    plate = grad(tuple(c + 8 for c in base), base); d = ImageDraw.Draw(plate)
    for x in range(0, W, 200): d.line([(x, 0), (x, H)], fill=seam, width=3)
    for y in range(0, H, 150): d.line([(0, y), (W, y)], fill=seam, width=3)
    for x in range(0, W, 200):
        for y in range(0, H, 150):
            for dx, dy in ((10, 10), (190, 10), (10, 140), (190, 140)):
                d.ellipse([x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3], fill=tuple(c + 25 for c in base))
    mask = Image.new("L", (W, H), 255); md = ImageDraw.Draw(mask)
    rim = Image.new("RGB", (W, H)); rd = ImageDraw.Draw(rim)
    for kind, c in holes:
        getattr(md, {"rect": "rectangle"}.get(kind, kind))(c, fill=0)
        if kind == "ellipse":
            x0, y0, x1, y1 = c
            rd.ellipse([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=accent, width=3)
            d.ellipse([x0 - 26, y0 - 26, x1 + 26, y1 + 26], outline=tuple(c + 40 for c in base), width=22)
            cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 + 14
            for k in range(16):
                a = k / 16 * math.tau; d.ellipse([cx + r * math.cos(a) - 4, cy + r * math.sin(a) - 4,
                                                   cx + r * math.cos(a) + 4, cy + r * math.sin(a) + 4], fill=(120, 130, 140))
        else:
            pts = c if kind == "polygon" else [(c[0], c[1]), (c[2], c[1]), (c[2], c[3]), (c[0], c[3])]
            rd.line(pts + [pts[0]], fill=accent, width=3)
            d.line(pts + [pts[0]], fill=tuple(c + 40 for c in base), width=24)
    out = Image.composite(plate, im, mask)
    return _add(out, rim.filter(ImageFilter.GaussianBlur(10)), rim)


def planet(im, x, y, r, c1, c2, ring=False):
    lay = Image.new("RGB", im.size); d = ImageDraw.Draw(lay)
    for i in range(int(r), 0, -2):
        t = i / r; c = tuple(int(a * t + b * (1 - t)) for a, b in zip(c2, c1))
        d.ellipse([x - i - (r - i) * .3, y - i - (r - i) * .3, x + i - (r - i) * .3, y + i - (r - i) * .3], fill=c)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).ellipse([x - r, y - r, x + r, y + r], fill=255)
    im = Image.composite(lay, im, m)
    if ring:
        d = ImageDraw.Draw(im); d.ellipse([x - r * 1.9, y - r * .35, x + r * 1.9, y + r * .35], outline=(200, 180, 140), width=4)
    return im


# ---------------- Звездолёт ----------------
def s_bridge(rnd):
    im = space(rnd); im = planet(im, 1150, 520, 210, (40, 110, 170), (5, 20, 40), ring=True)
    poly = [(150, 120), (1450, 120), (1560, 520), (1400, 700), (200, 700), (40, 520)]
    im = plate_over(im, [("polygon", poly)], rnd)
    d = ImageDraw.Draw(im)
    d.polygon([(0, 760), (W, 760), (W, H), (0, H)], fill=(14, 20, 30))
    for i in range(12):
        x = 60 + i * 128; d.rectangle([x, 790, x + 100, 850], fill=(10, 30, 44), outline=(0, 160, 200))
        for k in range(4): d.line([(x + 8, 800 + k * 12), (x + rnd.randint(30, 92), 800 + k * 12)], fill=(0, 200, 230), width=2)
    return im


def s_english(rnd):
    im = space(rnd, (40, 70, 140)); im = planet(im, 800, 450, 230, (60, 140, 220), (10, 30, 70))
    d = ImageDraw.Draw(im)
    for _ in range(30):
        x, y = rnd.uniform(620, 980), rnd.uniform(280, 620); d.ellipse([x, y, x + rnd.uniform(20, 70), y + rnd.uniform(10, 30)], fill=(70, 130, 80))
    return plate_over(im, [("ellipse", (470, 120, 1130, 780))], rnd)


def s_speedread(rnd):
    im = grad((2, 4, 12), (6, 4, 20)); d = ImageDraw.Draw(im); cx, cy = 800, 420
    for _ in range(700):
        a = rnd.uniform(0, math.tau); r0 = rnd.uniform(30, 200); r1 = r0 + rnd.uniform(120, 700)
        b = rnd.randint(120, 255); d.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))],
                                          fill=(b // 2, int(b / 1.3), b), width=rnd.choice([1, 1, 2]))
    im = _add(im, im.filter(ImageFilter.GaussianBlur(8)), Image.new("RGB", im.size))
    return plate_over(im, [("rect", (180, 110, 1420, 730))], rnd, accent=(170, 90, 255))


def s_lounge(rnd):
    im = space(rnd, (40, 120, 90)); d = ImageDraw.Draw(im)
    for _ in range(60):
        x = rnd.uniform(0, W); h = rnd.uniform(120, 420); c = (10, rnd.randint(50, 90), 30)
        for k in range(7):
            a = -math.pi / 2 + rnd.uniform(-.9, .9); d.line([(x, H), (x + h * math.cos(a), H + h * math.sin(a))], fill=c, width=rnd.randint(4, 10))
    im = plate_over(im, [("polygon", [(100, 900), (100, 380), (800, 60), (1500, 380), (1500, 900)])], rnd, accent=(60, 230, 140))
    d = ImageDraw.Draw(im)
    for k in range(1, 6): d.line([(100 + k * 233, 900), (800, 60)], fill=(30, 50, 46), width=8)
    return im


def s_radio(rnd):
    im = space(rnd, (120, 60, 160)); d = ImageDraw.Draw(im)
    for i, x in enumerate((350, 800, 1250)):
        y = 600 - (i % 2) * 60; d.pieslice([x - 160, y - 160, x + 160, y + 40], 180, 360, fill=(40, 50, 64), outline=(140, 160, 180), width=3)
        d.line([(x, y - 60), (x, y - 220)], fill=(160, 170, 190), width=4); d.ellipse([x - 8, y - 230, x + 8, y - 214], fill=(255, 190, 60))
        d.rectangle([x - 12, y - 60, x + 12, H], fill=(30, 36, 46))
    for r in range(80, 600, 70): d.arc([800 - r, 380 - r, 800 + r, 380 + r], 230, 310, fill=(90, 70, 150), width=2)
    return plate_over(im, [("rect", (60, 90, 1540, 760))], rnd, accent=(255, 180, 60))


def s_comm(rnd):
    im = grad((6, 12, 20), (10, 18, 30)); d = ImageDraw.Draw(im)
    for row in range(3):
        for col in range(5):
            x, y = 120 + col * 280, 120 + row * 200; d.rectangle([x, y, x + 240, y + 160], fill=(6, 26, 40), outline=(0, 190, 220), width=3)
            for k in range(6): d.line([(x + 14, y + 20 + k * 22), (x + rnd.randint(60, 226), y + 20 + k * 22)], fill=(0, rnd.randint(140, 230), 200), width=3)
    d.polygon([(0, 760), (W, 760), (W, H), (0, H)], fill=(18, 24, 34))
    return _add(im, im.filter(ImageFilter.GaussianBlur(12)), Image.new("RGB", im.size))


def s_orion(rnd):
    im = grad((4, 4, 14), (10, 6, 24)); lay = Image.new("RGB", im.size); d = ImageDraw.Draw(lay)
    for r in range(40, 420, 34): d.ellipse([800 - r, 450 - r, 800 + r, 450 + r], outline=(80 + r // 6, 60, 200), width=3)
    d.ellipse([740, 390, 860, 510], fill=(220, 200, 255))
    for _ in range(40):
        a = rnd.uniform(0, math.tau); d.line([(800, 450), (800 + 700 * math.cos(a), 450 + 700 * math.sin(a))], fill=(40, 20, 90), width=1)
    im = _add(im, lay.filter(ImageFilter.GaussianBlur(20)), lay)
    return plate_over(im, [("ellipse", (380, 30, 1220, 870))], rnd, accent=(170, 120, 255))


def s_settings(rnd):
    im = grad((14, 18, 24), (22, 26, 32)); d = ImageDraw.Draw(im)
    for x in range(0, W, 40): d.line([(x, 0), (x, H)], fill=(24, 32, 40))
    for y in range(0, H, 40): d.line([(0, y), (W, y)], fill=(24, 32, 40))
    for i in range(7):
        y = 100 + i * 110; d.rectangle([0, y, W, y + 26], fill=(40, 48, 58), outline=(70, 80, 90))
        for x in range(80, W, 260): d.rectangle([x, y - 8, x + 30, y + 34], fill=(60, 66, 74))
    d.ellipse([1150, 300, 1450, 600], outline=(255, 170, 50), width=8)
    return _add(im, im.filter(ImageFilter.GaussianBlur(10)), Image.new("RGB", im.size))


# ---------------- Стимпанк ----------------
def wood(rnd, base=(70, 42, 22)):
    im = grad(tuple(c + 10 for c in base), tuple(int(c * .6) for c in base)); d = ImageDraw.Draw(im)
    for x in range(0, W, 120):
        d.line([(x, 0), (x, H)], fill=tuple(int(c * .5) for c in base), width=3)
        for _ in range(14):
            xx = x + rnd.uniform(5, 115); d.line([(xx, 0), (xx + rnd.uniform(-20, 20), H)], fill=tuple(int(c * rnd.uniform(.7, 1.15)) for c in base), width=1)
    return im


BRASS, COPPER, DARK = (190, 145, 60), (170, 95, 50), (40, 26, 14)


def rivets(d, x0, y0, x1, y1, step=40):
    for x in range(int(x0), int(x1), step):
        for y in (y0, y1): d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(220, 180, 90))


def gear(d, cx, cy, r, teeth=12, fill=BRASS):
    pts = []
    for k in range(teeth * 2):
        a = k / (teeth * 2) * math.tau; rr = r if k % 2 == 0 else r * .82
        pts += [(cx + rr * math.cos(a - .12), cy + rr * math.sin(a - .12)), (cx + rr * math.cos(a + .12), cy + rr * math.sin(a + .12))]
    d.polygon(pts, fill=fill, outline=DARK); d.ellipse([cx - r * .55, cy - r * .55, cx + r * .55, cy + r * .55], fill=tuple(int(c * .7) for c in fill), outline=DARK)
    d.ellipse([cx - r * .15, cy - r * .15, cx + r * .15, cy + r * .15], fill=DARK)


def gauge(d, cx, cy, r, rnd):
    d.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], fill=BRASS, outline=DARK, width=3)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(235, 222, 190))
    for k in range(11):
        a = math.pi * .75 + k / 10 * math.pi * 1.5; d.line([(cx + r * .8 * math.cos(a), cy + r * .8 * math.sin(a)), (cx + r * .95 * math.cos(a), cy + r * .95 * math.sin(a))], fill=DARK, width=2)
    a = math.pi * .75 + rnd.uniform(.2, .9) * math.pi * 1.5; d.line([(cx, cy), (cx + r * .75 * math.cos(a), cy + r * .75 * math.sin(a))], fill=(160, 20, 20), width=4)


def pipe(d, pts, w=26, c=COPPER):
    d.line(pts, fill=tuple(int(x * .6) for x in c), width=w + 6, joint="curve"); d.line(pts, fill=c, width=w, joint="curve")
    d.line([(x, y - w // 4) for x, y in pts], fill=tuple(min(255, int(x * 1.3)) for x in c), width=max(2, w // 5))


def blueprint(d, x0, y0, x1, y1, rnd):
    d.rectangle([x0 - 18, y0 - 18, x1 + 18, y1 + 18], fill=BRASS, outline=DARK, width=3); d.rectangle([x0, y0, x1, y1], fill=(28, 62, 110))
    for x in range(int(x0), int(x1), 24): d.line([(x, y0), (x, y1)], fill=(50, 90, 140))
    for y in range(int(y0), int(y1), 24): d.line([(x0, y), (x1, y)], fill=(50, 90, 140))
    for _ in range(4):
        cx, cy, r = rnd.uniform(x0 + 80, x1 - 80), rnd.uniform(y0 + 60, y1 - 60), rnd.uniform(30, 70); d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(200, 225, 255), width=2)
        d.line([(cx - r * 1.4, cy), (cx + r * 1.4, cy)], fill=(200, 225, 255)); d.line([(cx, cy - r * 1.4), (cx, cy + r * 1.4)], fill=(200, 225, 255))
    rivets(d, x0 - 9, y0 - 9, x1 + 9, y1 + 9)


def lamp_glow(im, pts, col=(255, 170, 60)):
    lay = Image.new("RGB", im.size); d = ImageDraw.Draw(lay)
    for x, y in pts: d.ellipse([x - 120, y - 120, x + 120, y + 120], fill=tuple(c // 3 for c in col)); d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=col)
    return _add(im, lay.filter(ImageFilter.GaussianBlur(50)), Image.new("RGB", im.size))


def p_bridge(rnd):
    im = wood(rnd, (50, 30, 18)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([520, 140, 1080, 860], 120, fill=(110, 50, 28), outline=DARK, width=6)
    for y in range(200, 860, 90): rivets(d, 540, y, 1060, y, 30)
    d.ellipse([700, 420, 900, 620], fill=(30, 12, 6), outline=BRASS, width=14); d.ellipse([740, 460, 860, 580], fill=(255, 120, 30))
    pipe(d, [(1080, 300), (1300, 300), (1300, 0)]); pipe(d, [(520, 500), (260, 500), (260, 900)]); pipe(d, [(800, 140), (800, 0)], 40)
    for x, y in ((1350, 520), (1500, 300), (150, 260)): gauge(d, x, y, 70, rnd)
    return lamp_glow(im, [(800, 520)], (255, 110, 30))


def p_english(rnd):
    im = wood(rnd, (60, 36, 20)); d = ImageDraw.Draw(im)
    for sy in range(60, 840, 160):
        d.rectangle([0, sy + 130, W, sy + 150], fill=(90, 56, 28)); x = 10
        while x < W - 30:
            w = rnd.randint(18, 42); h = rnd.randint(90, 128); c = rnd.choice([(110, 30, 26), (40, 70, 50), (40, 50, 90), (120, 90, 40), (80, 40, 70)])
            d.rectangle([x, sy + 130 - h, x + w, sy + 130], fill=c, outline=DARK); d.line([(x + 3, sy + 140 - h), (x + w - 3, sy + 140 - h)], fill=BRASS, width=2); x += w + rnd.randint(1, 4)
    gauge(d, 1450, 120, 60, rnd)
    return lamp_glow(im, [(300, 60), (1300, 60)])


def p_speedread(rnd):
    im = wood(rnd, (54, 34, 20)); d = ImageDraw.Draw(im)
    for _ in range(18): gear(d, rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(40, 160), rnd.randint(10, 24), rnd.choice([BRASS, COPPER, (150, 120, 70)]))
    cx, cy = 800, 450; d.ellipse([cx - 260, cy - 260, cx + 260, cy + 260], fill=(235, 222, 190), outline=BRASS, width=24)
    for k in range(12):
        a = k / 12 * math.tau; d.line([(cx + 200 * math.cos(a), cy + 200 * math.sin(a)), (cx + 235 * math.cos(a), cy + 235 * math.sin(a))], fill=DARK, width=6)
    d.line([(cx, cy), (cx + 150, cy - 90)], fill=DARK, width=10); d.line([(cx, cy), (cx - 40, cy + 190)], fill=DARK, width=6)
    return lamp_glow(im, [(800, 40)])


def p_lounge(rnd):
    im = grad((70, 30, 34), (40, 16, 20)); d = ImageDraw.Draw(im)
    for y in range(0, 620, 60):
        for x in range((y // 60 % 2) * 40, W, 80): d.ellipse([x - 10, y - 10, x + 10, y + 10], outline=(130, 80, 50), width=2)
    d.rectangle([0, 620, W, H], fill=(70, 42, 22)); d.rectangle([0, 610, W, 630], fill=BRASS)
    d.rounded_rectangle([600, 100, 1000, 520], 200, fill=(30, 50, 70), outline=BRASS, width=18)
    d.line([(800, 100), (800, 520)], fill=BRASS, width=8); d.line([(600, 330), (1000, 330)], fill=BRASS, width=8)
    d.ellipse([200, 700, 400, 840], fill=COPPER, outline=DARK, width=3); d.line([(400, 740), (470, 700)], fill=COPPER, width=14)
    return lamp_glow(im, [(300, 200), (1300, 200)])


def p_radio(rnd):
    im = wood(rnd, (64, 38, 22)); d = ImageDraw.Draw(im)
    d.rectangle([500, 600, 1100, 820], fill=(80, 46, 24), outline=BRASS, width=8); d.ellipse([620, 560, 980, 640], fill=(20, 12, 8), outline=BRASS, width=4)
    d.polygon([(800, 560), (780, 380), (560, 80), (1240, 40), (840, 380)], fill=(190, 140, 60), outline=DARK)
    for k in range(6): d.line([(800, 560 - k * 4), (600 + k * 120, 70 - k * 4)], fill=(150, 105, 40), width=3)
    for r in range(90, 700, 90): d.arc([900 - r, 200 - r, 900 + r, 200 + r], 300, 30, fill=(140, 100, 50), width=2)
    gauge(d, 200, 300, 80, rnd); gauge(d, 1400, 600, 80, rnd)
    return lamp_glow(im, [(800, 590)])


def p_comm(rnd):
    im = wood(rnd, (56, 34, 20)); d = ImageDraw.Draw(im)
    for i in range(6): pipe(d, [(100 + i * 260, 0), (100 + i * 260, 520), (60 + i * 260 + 200, 700)], 34, rnd.choice([BRASS, COPPER]))
    d.rectangle([0, 700, W, H], fill=(70, 42, 22)); d.rectangle([600, 640, 1000, 720], fill=(40, 26, 14), outline=BRASS, width=6)
    d.ellipse([760, 600, 840, 660], fill=BRASS, outline=DARK, width=3); d.line([(800, 630), (920, 560)], fill=BRASS, width=10)
    for x in range(100, W, 200): d.line([(x, 720), (x + 300, 900)], fill=(30, 18, 10), width=3)
    return lamp_glow(im, [(800, 600)])


def p_orion(rnd):
    im = grad((24, 18, 32), (10, 8, 16)); d = ImageDraw.Draw(im); stars(d, rnd, 250)
    cx, cy = 800, 400
    for r, pr, c in ((120, 16, COPPER), (200, 22, (120, 140, 160)), (290, 30, (180, 120, 80)), (380, 18, (120, 160, 200))):
        d.ellipse([cx - r, cy - r * .35, cx + r, cy + r * .35], outline=BRASS, width=4); a = rnd.uniform(0, math.tau)
        x, y = cx + r * math.cos(a), cy + r * .35 * math.sin(a); d.line([(cx, cy), (x, y)], fill=BRASS, width=3); d.ellipse([x - pr, y - pr, x + pr, y + pr], fill=c, outline=DARK)
    d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(255, 190, 70))
    d.rectangle([cx - 30, cy + 50, cx + 30, 820], fill=BRASS); d.ellipse([cx - 160, 780, cx + 160, 860], fill=(90, 56, 28), outline=BRASS, width=6)
    d.rounded_rectangle([1250, 380, 1450, 860], 60, fill=(140, 100, 50), outline=DARK, width=4); d.ellipse([1290, 240, 1410, 380], fill=(170, 125, 60), outline=DARK, width=4)
    d.ellipse([1315, 290, 1345, 320], fill=(120, 220, 255)); d.ellipse([1355, 290, 1385, 320], fill=(120, 220, 255)); gear(d, 1350, 560, 50)
    return lamp_glow(im, [(cx, cy), (1330, 305), (1370, 305)], (255, 200, 90))


def p_settings(rnd):
    im = wood(rnd, (60, 38, 22)); d = ImageDraw.Draw(im)
    blueprint(d, 160, 90, 1000, 560, rnd)
    d.rectangle([0, 660, W, 700], fill=(110, 70, 34)); d.rectangle([0, 700, W, H], fill=(46, 28, 16))
    for x in (1150, 1300, 1450): d.line([(x, 100), (x, 520)], fill=(40, 26, 14), width=4)
    for x, n in ((1150, 0), (1300, 1), (1450, 2)): gear(d, x, 180 + n * 40, 40)
    gauge(d, 1300, 480, 90, rnd)
    for k in range(5): d.rectangle([200 + k * 160, 620, 300 + k * 160, 660], fill=rnd.choice([BRASS, COPPER, (120, 120, 120)]), outline=DARK)
    return lamp_glow(im, [(580, 40), (1300, 60)])


SCENES = {"starship": {"bridge": s_bridge, "english": s_english, "speedread": s_speedread, "lounge": s_lounge,
                       "radio": s_radio, "comm": s_comm, "orion": s_orion, "settings": s_settings},
          "steampunk": {"bridge": p_bridge, "english": p_english, "speedread": p_speedread, "lounge": p_lounge,
                        "radio": p_radio, "comm": p_comm, "orion": p_orion, "settings": p_settings}}


def main(out=OUT):
    for prof, zones in SCENES.items():
        (out / prof).mkdir(parents=True, exist_ok=True)
        for z, fn in zones.items():
            rnd = random.Random(sum(map(ord, prof + z)))
            fn(rnd).convert("RGB").save(out / prof / f"{z}.jpg", quality=86, optimize=True)
            print(prof, z)




# ---------------- Реальные фото (основной источник с 22.10.2026) ----------------
# Источники и лицензии — docs/skins/ATTRIBUTION.md. Процедурные сцены выше — фолбэк
# и запасной вариант, если фото недоступны.
PORTHOLE = {  # отсеки Звездолёта, где фото космоса видно «сквозь корпус»
    "bridge": [("polygon", [(150, 120), (1450, 120), (1560, 520), (1400, 700), (200, 700), (40, 520)])],
    "speedread": [("rect", (180, 110, 1420, 730))],
    "radio": [("rect", (60, 90, 1540, 760))],
    "orion": [("ellipse", (380, 30, 1220, 870))],
}


def cover(im):
    im = im.convert("RGB"); sc = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((l, t, l + W, t + H))


def vignette(im, strength=0.55):
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).ellipse([-W * .15, -H * .2, W * 1.15, H * 1.2], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(im, Image.blend(im, Image.new("RGB", im.size), strength), m)


def warm(im, tint=(255, 190, 120), k=0.18):
    from PIL import ImageEnhance
    im = ImageEnhance.Color(im).enhance(0.85)
    return Image.blend(im, Image.new("RGB", im.size, tint), k) if k else im


def from_photo(prof, zone, src: Path):
    im = cover(Image.open(src)); rnd = random.Random(sum(map(ord, prof + zone)))
    if prof == "starship":
        if zone in PORTHOLE:
            im = plate_over(im, PORTHOLE[zone], rnd, base=(40, 36, 32), seam=(20, 18, 16), accent=(255, 176, 70))
            stencil(im, zone, rnd)
            if zone == "bridge":
                d = ImageDraw.Draw(im); d.polygon([(0, 760), (W, 760), (W, H), (0, H)], fill=(30, 26, 22))
                for i in range(12):
                    x = 60 + i * 128; d.rectangle([x, 790, x + 100, 850], fill=(20, 30, 34), outline=(240, 170, 70))
                    for k in range(4): d.line([(x + 8, 800 + k * 12), (x + rnd.randint(30, 92), 800 + k * 12)], fill=(0, 200, 230), width=2)
        else:
            im = warm(im, (255, 200, 140), 0.08)   # обжитые отсеки — тёплый свет
        return vignette(im, 0.45)
    return vignette(warm(im, (255, 185, 110), 0.16), 0.55)   # мастерская: тёплая лампа


STENCIL = {"bridge": "DECK 1 · BRIDGE", "speedread": "DECK 4 · DRIVE", "radio": "DECK 2 · ARRAY", "orion": "CORE · 00"}


def stencil(im, zone, rnd):
    """Трафаретная маркировка обжитого корабля: номер палубы, полосы, потёртости."""
    from PIL import ImageFont
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.load_default(size=30)
    except TypeError:
        f = ImageFont.load_default()
    d.text((40, 30), STENCIL.get(zone, ""), fill=(210, 160, 70), font=f)
    for k in range(6):                       # жёлто-чёрные полосы у края
        x = W - 300 + k * 44
        d.polygon([(x, 0), (x + 22, 0), (x - 8, 40), (x - 30, 40)], fill=(200, 150, 40))
    for _ in range(140):                     # потёртости
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r, g, b = im.getpixel((int(x), int(y)))[:3]
        if not (r > b + 3 and 25 < r < 70):  # только по тёплому металлу, не по иллюминатору
            continue
        d.line([(x, y), (x + rnd.uniform(-30, 30), y + rnd.uniform(-3, 3))], fill=(70, 64, 58), width=1)


def main_photos(src_dir: Path, out=OUT):
    for prof, zones in SCENES.items():
        (out / prof).mkdir(parents=True, exist_ok=True)
        for z in zones:
            src = src_dir / f"{prof}_{z}.jpg"
            im = from_photo(prof, z, src) if src.is_file() else zones[z](random.Random(sum(map(ord, prof + z))))
            im.convert("RGB").save(out / prof / f"{z}.jpg", quality=84, optimize=True, progressive=True)
            print(prof, z, "photo" if src.is_file() else "procedural")


if __name__ == "__main__":
    # python tools/gen_alt_wallpapers.py                 — процедурные обои
    # python tools/gen_alt_wallpapers.py --photos DIR    — из фото DIR/<profile>_<zone>.jpg
    a = sys.argv[1:]
    if a[:1] == ["--photos"]:
        main_photos(Path(a[1]), Path(a[2]) if len(a) > 2 else OUT)
    else:
        main(Path(a[0]) if a else OUT)
