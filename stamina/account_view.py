"""«Страница аккаунта» на Canvas: карточка пилота, рекорды, тепловая карта за 12 месяцев.

Одна отрисовка для трёх источников (общая таблица / Star Typing / Monkeytype) и двух
мест: панель Бортжурнала (цвета скина) и портал (serika dark). Своя реализация на Tk.
"""
from __future__ import annotations

import datetime as dt
import tkinter as tk

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def rrect(cv: tk.Canvas, x0, y0, x1, y1, r, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0)
    return cv.create_polygon(pts, smooth=True, **kw)


def blend(a: str, b: str, k: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(ca, cb))


def fmt_hms(secs: float) -> str:
    s = int(secs)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_k(v: float) -> str:
    return f"{v / 1000:.1f}k" if v >= 1000 else str(int(v))


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def draw(cv: tk.Canvas, s: dict | None, pal: dict, family: str, width: int, *,
         scale: float = 1.0, empty: str = "") -> int:
    """Нарисовать страницу в cv (очищается). Возвращает высоту. pal: bg sub subalt text main."""
    cv.delete("acct")
    p = lambda v: int(round(v * scale))   # noqa: E731
    F = lambda n, w="normal": (family, -p(n), w)   # noqa: E731
    W = width
    if not s:
        cv.create_text(p(8), p(16), anchor="w", text=empty, fill=pal["sub"], font=F(13), tags="acct")
        return p(40)
    y = 0
    gap = p(20)
    # -- карточка пилота -------------------------------------------------
    h = p(100)
    rrect(cv, 0, y, W, y + h, p(10), fill=pal["subalt"], outline="", tags="acct")
    cx, cy, r = p(36), y + p(36), p(26)
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=pal["sub"], outline="", tags="acct")
    cv.create_oval(cx - p(9), cy - p(14), cx + p(9), cy + p(4), fill=pal["subalt"], outline="", tags="acct")
    cv.create_arc(cx - p(17), cy + p(6), cx + p(17), cy + p(34), start=0, extent=180,
                  fill=pal["subalt"], outline="", tags="acct")
    nx = p(76)
    cv.create_text(nx, y + p(22), anchor="w", text=s.get("name") or "—", fill=pal["text"], font=F(26), tags=("acct", "acct_name"))
    joined = s.get("joined")
    jtxt = ""
    if joined:
        d = dt.date.fromtimestamp(float(joined))
        jtxt = f"Joined {d.day} {MONTHS[d.month - 1]} {d.year}"
    cv.create_text(nx, y + p(48), anchor="w", text=jtxt, fill=pal["sub"], font=F(10), tags="acct")
    cv.create_text(nx, y + p(61), anchor="w", text=f"Current streak {s.get('streak', 0)} days",
                   fill=pal["sub"], font=F(10), tags="acct")
    by = y + p(84)
    cv.create_text(p(10), by, anchor="w", text=str(s.get("level") or 1), fill=pal["text"], font=F(12), tags="acct")
    bx0, bx1 = p(36), p(140)
    rrect(cv, bx0, by - p(3), bx1, by + p(3), p(3), fill=pal["bg"], outline="", tags="acct")
    need = max(1, int(s.get("level_need") or 1))
    k = max(0.0, min(1.0, (s.get("level_have") or 0) / need))
    if k > 0:
        rrect(cv, bx0, by - p(3), bx0 + (bx1 - bx0) * k, by + p(3), p(3), fill=pal["main"], outline="", tags="acct")
    cv.create_text(bx1 + p(6), by, anchor="w", text=f"{fmt_k(s.get('level_have') or 0)}/{fmt_k(need)}",
                   fill=pal["sub"], font=F(9), tags="acct")
    sx = max(p(220), int(W * 0.25))
    cv.create_line(sx, y + p(14), sx, y + h - p(14), fill=pal["bg"], width=p(3), tags="acct")
    cols = (("tests started", f"{s.get('started', 0)}"), ("tests completed", f"{s.get('tests', 0)}"),
            ("time typing", fmt_hms(s.get("seconds") or float(s.get("hours") or 0) * 3600)))
    cw = (W - sx - p(20)) / 3
    for i, (cap, val) in enumerate(cols):
        x = sx + p(16) + i * cw
        cv.create_text(x, y + p(40), anchor="w", text=cap, fill=pal["sub"], font=F(12), tags="acct")
        cv.create_text(x, y + p(62), anchor="w", text=val, fill=pal["text"], font=F(22), tags="acct")
    y += h + gap
    # -- лидерборды ------------------------------------------------------
    lbs = [lb for lb in s.get("lbs") or [] if lb.get("mode") == "time"][:2]
    if lbs:
        h = p(48)
        rrect(cv, 0, y, W, y + h, p(10), fill=pal["subalt"], outline="", tags="acct")
        cv.create_text(p(50), y + h / 2, anchor="w", text="All-Time English Leaderboards",
                       fill=pal["sub"], font=F(11), tags="acct")
        for i, lb in enumerate(lbs):
            x = W * (0.55 + 0.33 * i)
            cv.create_text(x, y + p(17), anchor="e", text=f"{lb['mode2']} seconds", fill=pal["sub"],
                           font=F(11), tags="acct")
            if lb.get("count"):
                cv.create_text(x, y + p(32), anchor="e", text=f"Top {lb['rank'] / lb['count'] * 100:.2f}%",
                               fill=pal["sub"], font=F(8), tags="acct")
            cv.create_text(x + p(8), y + h / 2, anchor="w", text=ordinal(int(lb["rank"])), fill=pal["text"],
                           font=F(19), tags="acct")
        y += h + gap
    # -- рекорды ---------------------------------------------------------
    h = p(84)
    half = (W - gap) / 2
    labels = {"time": "seconds", "words": "words"}
    for gi, mode in enumerate(("time", "words")):
        x0 = gi * (half + gap)
        rrect(cv, x0, y, x0 + half, y + h, p(10), fill=pal["subalt"], outline="", tags="acct")
        items = [pb for pb in s.get("pbs") or [] if pb["mode"] == mode]
        cw = (half - p(30)) / max(1, len(items))
        for i, pb in enumerate(items):
            cx = x0 + p(10) + cw * (i + 0.5)
            cv.create_text(cx, y + p(20), text=f"{pb['mode2']} {labels[mode]}", fill=pal["sub"], font=F(8), tags="acct")
            cv.create_text(cx, y + p(42), text="-" if pb.get("wpm") is None else f"{pb['wpm']:.0f}",
                           fill=pal["text"], font=F(24), tags="acct")
            cv.create_text(cx, y + p(64), text="-" if pb.get("acc") is None else f"{pb['acc']:.0f}%",
                           fill=pal["text"], font=F(13), tags="acct")
            if pb.get("src"):
                cv.create_text(cx + cw / 2 - p(4), y + p(9), anchor="ne", text=pb["src"],
                               fill=blend(pal["sub"], pal["subalt"], 0.35), font=F(7), tags="acct")
        cv.create_text(x0 + half - p(12), y + h / 2, text="⋮", fill=pal["sub"], font=F(12), tags="acct")
    y += h + gap
    # -- тепловая карта --------------------------------------------------
    act = s.get("activity") or []
    if act:
        cell_gap = max(1, p(3))
        first = dt.date.fromisoformat(act[0][0])
        pad = first.weekday()
        weeks = (len(act) + pad + 6) // 7
        lx = p(90)
        cell = max(3, min(p(14), int((W - lx - p(20)) / weeks) - cell_gap))
        h = p(52) + 7 * (cell + cell_gap) + p(26)
        rrect(cv, 0, y, W, y + h, p(10), fill=pal["subalt"], outline="", tags="acct")
        rrect(cv, p(12), y + p(12), p(170), y + p(38), p(6), fill=pal["bg"], outline="", tags="acct")
        cv.create_text(p(20), y + p(25), anchor="w", text="last 12 months", fill=pal["text"], font=F(12), tags="acct")
        cv.create_text(p(158), y + p(25), text="⌄", fill=pal["text"], font=F(12), tags="acct")
        tot = sum(v for _d, v in act)
        cv.create_text(p(184), y + p(25), anchor="w", text=f"{tot} tests", fill=pal["sub"], font=F(11), tags="acct")
        mx = max(v for _d, v in act) or 1
        shades = [blend(pal["subalt"], pal["main"], k) for k in (0.25, 0.45, 0.7, 1.0)]
        lgx = W - p(16)
        cv.create_text(lgx, y + p(25), anchor="e", text="more", fill=pal["sub"], font=F(11), tags="acct")
        lgx -= p(42)
        for col in reversed([blend(pal["subalt"], pal["bg"], 0.6)] + shades):
            cv.create_rectangle(lgx - p(11), y + p(19), lgx, y + p(30), fill=col, outline="", tags="acct")
            lgx -= p(13)
        cv.create_text(lgx - p(2), y + p(25), anchor="e", text="less", fill=pal["sub"], font=F(11), tags="acct")
        gy = y + p(52)
        for row, name in ((0, "monday"), (2, "wednesday"), (4, "friday"), (6, "sunday")):
            cv.create_text(p(12), gy + row * (cell + cell_gap) + cell / 2, anchor="w", text=name,
                           fill=pal["sub"], font=F(10), tags="acct")
        both = s.get("both") or {}
        cells = []
        for i, (day, v) in enumerate(act):
            kx = i + pad
            x0, y0 = lx + (kx // 7) * (cell + cell_gap), gy + (kx % 7) * (cell + cell_gap)
            if v:
                q = v / mx
                col = shades[0 if q < 0.15 else 1 if q < 0.4 else 2 if q < 0.7 else 3]
            else:
                col = blend(pal["subalt"], pal["bg"], 0.6)
            cid = cv.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=col, outline="", tags=("acct", "hm"))
            cells.append((cid, day, v, both.get(day)))
        tip = cv.create_text(0, 0, anchor="sw", text="", fill=pal["text"], font=F(9), tags="acct")
        tipbg = cv.create_rectangle(0, 0, 0, 0, fill=pal["bg"], outline="", tags="acct", state="hidden")
        lookup = {c[0]: c for c in cells}

        def on_motion(e, cv=cv):
            hit = cv.find_overlapping(cv.canvasx(e.x), cv.canvasy(e.y), cv.canvasx(e.x), cv.canvasy(e.y))
            c = next((lookup[h] for h in hit if h in lookup), None)
            if c is None:
                cv.itemconfigure(tip, text="")
                cv.itemconfigure(tipbg, state="hidden")
                return
            _cid, day, v, b = c
            txt = f"{day}: {v} tests" + (f"  (ST {b[0]} · MT {b[1]})" if b else "")
            x, yy = cv.canvasx(e.x) + p(10), cv.canvasy(e.y) - p(6)
            cv.coords(tip, x, yy)
            cv.itemconfigure(tip, text=txt)
            bb = cv.bbox(tip)
            if bb:
                cv.coords(tipbg, bb[0] - p(4), bb[1] - p(2), bb[2] + p(4), bb[3] + p(2))
                cv.itemconfigure(tipbg, state="normal")
                cv.tag_raise(tipbg)
                cv.tag_raise(tip)

        cv.tag_bind("hm", "<Motion>", on_motion)
        cv.tag_bind("hm", "<Button-1>", on_motion)     # щелчок по дню — та же подсказка
        cv.tag_bind("hm", "<Leave>", lambda _e: (cv.itemconfigure(tip, text=""),
                                                 cv.itemconfigure(tipbg, state="hidden")))
        y += h
    return int(y)
