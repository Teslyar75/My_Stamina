"""Отсек «ЛАБОРАТОРИЯ»: созвездия знаний пилота на холсте Tk.

Данные — ``lab_data.collect`` (только чтение файлов пилота). Отрисовка:
раскладка считается один раз (``layout``), каждый кадр — поворот и «дыхание».
Бюджет кадра следит за временем: если кадр дороже ~22 мс, геометрия
обновляется реже (LOD), а при >MAX_STARS звёзд мелкие созвездия сворачиваются
в одну «туманность». Анимация идёт, только пока отсек на экране.
"""
from __future__ import annotations

import json
import math
import os
import time
import tkinter as tk
from collections import deque
from pathlib import Path

from stamina import lab_data, theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import blend, px

FRAME_MS = 33            # ~30 кадров/с
BUDGET_MS = 22.0         # дороже — пропускаем обновление геометрии через кадр
MAX_STARS = 1600         # сверх — свернуть мелкие созвездия
MAX_EDGES = 900
MAX_FLIERS = 60
ROT_SPEED = 0.012        # рад/с — медленное вращение
SKILL_ARM = {"en": 0.0, "read": 2 * math.pi / 3, "type": 4 * math.pi / 3}
GOLDEN = math.pi * (3 - math.sqrt(5))
SEEN_FILE = "lab.json"


def skill_color(skill: str) -> str:
    """Английский — синий, чтение — золото, печать — зелёный (токены текущей темы)."""
    return {"en": theme.CYAN, "read": theme.AMBER, "type": theme.GREEN}.get(skill, theme.TEXT)


def aggregate(graph: lab_data.Graph, limit: int = MAX_STARS) -> lab_data.Graph:
    """LOD данных: если звёзд больше limit, самые мелкие созвездия → по одной звезде-туманности."""
    if len(graph.nodes) <= limit:
        return graph
    groups: dict[str, list[int]] = {}
    for i, n in enumerate(graph.nodes):
        groups.setdefault(n["group"], []).append(i)
    order = sorted(groups, key=lambda k: len(groups[k]))
    fold: set[str] = set()
    total = len(graph.nodes)
    for k in order:
        if total <= limit:
            break
        fold.add(k)
        total -= len(groups[k]) - 1
    out = lab_data.Graph()
    out.demo, out.active_days, out.gaps = graph.demo, graph.active_days, graph.gaps
    remap: dict[int, int] = {}
    for k, ids in groups.items():
        if k in fold:
            ns = [graph.nodes[i] for i in ids]
            lasts = [n["last"] for n in ns if n["last"]]
            j = out.add("agg:" + k, "cluster", ns[0]["skill"], f"{len(ns)}", k,
                        last=max(lasts) if lasts else None,
                        strength=sum(n["strength"] for n in ns) / len(ns), detail=k)
            out.nodes[j]["count"] = len(ns)
            for i in ids:
                remap[i] = j
        else:
            for i in ids:
                n = graph.nodes[i]
                remap[i] = out.add(n["id"], n["kind"], n["skill"], n["label"], n["group"], last=n["last"],
                                   strength=n["strength"], detail=n["detail"])
    seen = set()
    for a, b in graph.edges:
        e = (remap[a], remap[b])
        if e[0] != e[1] and e not in seen:
            seen.add(e)
            out.edges.append(e)
    return out


def layout(graph: lab_data.Graph) -> tuple[list[tuple[float, float]], list[tuple[int, int]]]:
    """Позиции в единицах «радиус галактики = 1» и рёбра-контуры созвездий.

    Три рукава (английский, чтение, печать); созвездие — кольцо филлотаксиса,
    его центр идёт по рукаву тем дальше, чем позже созвездие в списке.
    """
    groups: dict[str, list[int]] = {}
    for i, n in enumerate(graph.nodes):
        groups.setdefault(n["group"], []).append(i)
    by_skill: dict[str, list[str]] = {}
    for k in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        by_skill.setdefault(graph.nodes[groups[k][0]]["skill"], []).append(k)
    pos: list[tuple[float, float]] = [(0.0, 0.0)] * len(graph.nodes)
    shape: list[tuple[int, int]] = []
    total = max(1, len(graph.nodes))
    for skill, keys in by_skill.items():
        base = SKILL_ARM.get(skill, 0.0)
        for gi, k in enumerate(keys):
            ids = groups[k]
            r = 0.24 + 0.70 * math.sqrt((gi + 0.5) / len(keys))
            # рукав закручен и «распушён»: соседние созвездия расходятся поперёк рукава
            a = base + r * 3.4 + (0.35 if gi % 2 else -0.35) * (1.1 - r)
            cx, cy = r * math.cos(a), r * math.sin(a)
            spread = 0.022 + 0.22 * math.sqrt(len(ids) / total)
            for j, ni in enumerate(ids):
                rr = spread * math.sqrt((j + 0.5) / len(ids))
                aa = j * GOLDEN
                pos[ni] = (cx + rr * math.cos(aa), cy + rr * math.sin(aa))
            # контур созвездия: каждая звезда — к ближайшей из нескольких предыдущих
            for j in range(1, len(ids)):
                x, y = pos[ids[j]]
                best = min(range(max(0, j - 6), j),
                           key=lambda q: (pos[ids[q]][0] - x) ** 2 + (pos[ids[q]][1] - y) ** 2)
                shape.append((ids[best], ids[j]))
    return pos, shape


class LabScreen(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.demo = os.environ.get("STAMINA_LAB_DEMO") == "1"
        self.graph = lab_data.Graph()
        self.pos: list[tuple[float, float]] = []
        self.edges: list[tuple[int, int]] = []
        self.fresh: list[float] = []
        self.items: list[int] = []
        self.edge_items: list[int] = []
        self.fliers: list[dict] = []
        self.angle = 0.0
        self.t0 = time.perf_counter()
        self._last_tick = self.t0
        self._job = None
        self._frame = 0
        self._lod = 1
        self.frame_ms: deque = deque(maxlen=120)
        self._screen_xy: list[tuple[float, float]] = []
        self._hover = None
        self._build()

    # -- сборка --------------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), px(4)))
        tk.Label(top, text=_t("ЛАБОРАТОРИЯ · СОЗВЕЗДИЯ ЗНАНИЙ"), bg=theme.BG, fg=theme.TEXT,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        self.badge = tk.Label(top, text="", bg=theme.BG, fg=theme.RED, font=theme.font(9, True))
        self.badge.pack(side=tk.LEFT, padx=px(10))
        HudButton(top, _t("ОБНОВИТЬ"), self.reload, height=30, font_size=9).pack(side=tk.RIGHT)
        self.summary = tk.Label(top, text="", bg=theme.BG, fg=theme.MUTED, font=theme.font(9))
        self.summary.pack(side=tk.RIGHT, padx=px(10))
        self.panel = HudPanel(self, title=_t("КАРТА ЗНАНИЙ ПИЛОТА"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=(0, px(10)))
        self.cv = tk.Canvas(self.panel.body, bg=theme.PANEL, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._redraw())
        self.cv.bind("<Motion>", self._on_motion)
        self.cv.bind("<Leave>", lambda _e: self._hide_tip())

    # -- данные --------------------------------------------------------------------
    def set_demo(self, on: bool, graph: lab_data.Graph | None = None) -> None:
        """Демо-режим только для скриншотов и тестов (плашка «ДЕМО-ДАННЫЕ»)."""
        self.demo = bool(on)
        self._demo_graph = graph
        self.reload()

    def _pilot_dir(self) -> Path | None:
        return lab_data.pilot_root(self.app)

    def reload(self) -> None:
        now = time.time()
        if self.demo:
            from stamina.lab_demo import demo_graph
            g = getattr(self, "_demo_graph", None) or demo_graph(1000, now=now)
        else:
            g = lab_data.collect(self._pilot_dir(), now)
        self.graph = aggregate(g)
        self.fresh = [lab_data.freshness(n["last"], n["strength"], now) for n in self.graph.nodes]
        self.pos, shape = layout(self.graph)
        edges = list(dict.fromkeys(self.graph.edges + shape))
        self.edges = edges[:MAX_EDGES]
        self.entity = self.graph.entity(now)
        self._new_fliers()
        self.badge.configure(text=_t("ДЕМО-ДАННЫЕ") if self.demo else "")
        c = self.graph.counts()
        self.summary.configure(text=_t("английский {0} · чтение {1} · печать {2}").format(
            c.get("en", 0), c.get("read", 0), c.get("type", 0)))
        self._redraw()

    def _new_fliers(self) -> None:
        """Новые звёзды с прошлого визита влетают из центра (не больше MAX_FLIERS)."""
        self.fliers = []
        ids = [n["id"] for n in self.graph.nodes]
        if self.demo:
            fresh_ids = ids[-24:]
        else:
            path = self._pilot_dir() / SEEN_FILE if self._pilot_dir() else None
            data = None
            if path is not None:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    data = None
            seen = set((data or {}).get("seen") or [])
            fresh_ids = [i for i in ids if i not in seen] if data is not None else []
            if path is not None and set(ids) != seen:
                try:   # собственный файл Лаборатории; данные пилота не трогаем
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"seen": ids}, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
        ix = {n["id"]: i for i, n in enumerate(self.graph.nodes)}
        now = time.perf_counter()
        for k, nid in enumerate(fresh_ids[-MAX_FLIERS:]):
            self.fliers.append({"i": ix[nid], "t0": now + k * 0.05})

    # -- рисование -----------------------------------------------------------------
    def _geom(self):
        w, h = max(2, self.cv.winfo_width()), max(2, self.cv.winfo_height())
        return w / 2, h / 2, min(w, h) * 0.46

    def _redraw(self) -> None:
        cv = self.cv
        try:
            cv.delete("all")
        except tk.TclError:
            return
        self.items, self.edge_items = [], []
        cx, cy, R = self._geom()
        if not self.graph.nodes:
            self._draw_empty(cx, cy, R)
            return
        line = blend(theme.PANEL, theme.LINE_HI, 0.55)
        for _ in self.edges:
            self.edge_items.append(cv.create_line(0, 0, 0, 0, fill=line, width=1, tags="edge"))
        flying = {f["i"] for f in self.fliers}
        for i, n in enumerate(self.graph.nodes):
            f = self.fresh[i]
            col = blend(theme.PANEL, skill_color(n["skill"]), 0.25 + 0.75 * f)
            self.items.append(cv.create_oval(0, 0, 0, 0, fill=col, outline="",
                                             state="hidden" if i in flying else "normal", tags="star"))
        self._entity_items = [cv.create_oval(0, 0, 0, 0, outline="", fill="", tags="entity") for _ in range(4)]
        self._tip = None
        self._place(time.perf_counter(), full=True)

    def _draw_empty(self, cx, cy, R) -> None:
        cv = self.cv
        col = blend(theme.PANEL, theme.PURPLE, 0.35)
        for k in range(3):
            r = px(18) + k * px(14)
            cv.create_oval(cx - r, cy - r - px(40), cx + r, cy + r - px(40), outline=col, width=1)
        cv.create_text(cx, cy + px(30), text=_t("Лаборатория ждёт первых знаний"), fill=theme.TEXT,
                       font=theme.font(14, True))
        cv.create_text(cx, cy + px(70), width=max(200, int(R * 1.8)), justify="center", fill=theme.MUTED,
                       font=theme.font(10),
                       text=_t("Звёзды появятся сами: отметьте слово «знаю» или повторяйте карточки в «Английском», "
                               "прочитайте текст в «Скорочтении», пройдите миссию на «Мостике»."))

    def _star_xy(self, i: int, ca: float, sa: float, cx: float, cy: float, R: float) -> tuple[float, float]:
        x, y = self.pos[i]
        return cx + (x * ca - y * sa) * R, cy + (x * sa + y * ca) * R * 0.86

    def _place(self, now: float, full: bool = False) -> None:
        cv = self.cv
        cx, cy, R = self._geom()
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        xy = [self._star_xy(i, ca, sa, cx, cy, R) for i in range(len(self.pos))]
        self._screen_xy = xy
        base = max(1.0, px(1.6))
        coords = cv.coords
        for i, it in enumerate(self.items):
            n = self.graph.nodes[i]
            s = base * (0.7 + 0.9 * self.fresh[i]) * (2.2 if n["kind"] in ("book", "cluster") else
                                                      1.4 if n["kind"] in ("verb", "milestone", "mission") else 1)
            x, y = xy[i]
            coords(it, x - s, y - s, x + s, y + s)
        for k, it in enumerate(self.edge_items):
            a, b = self.edges[k]
            coords(it, *xy[a], *xy[b])
        self._place_entity(now, cx, cy)

    def _place_entity(self, now: float, cx: float, cy: float) -> None:
        e = self.entity
        v = e["vitality"]
        speed = 0.6 + 1.4 * v                       # после перерыва дышит медленнее и тише
        phase = math.sin((now - self.t0) * speed)
        r0 = px(7) * (1 + 0.07 * min(e["growth"], 8.0))   # растёт, но не заслоняет звёзды
        col = theme.PURPLE
        for k, it in enumerate(self._entity_items):
            r = r0 * (1 + 0.45 * k) * (1 + 0.07 * v * phase * (k + 1))
            fill = blend(theme.PANEL, col, (0.85 if k == 0 else 0.22 / k) * (0.45 + 0.55 * v))
            try:
                self.cv.coords(it, cx - r, cy - r, cx + r, cy + r)
                self.cv.itemconfigure(it, fill=fill)
            except tk.TclError:
                return
        for it in reversed(self._entity_items):
            self.cv.tag_raise(it)

    def _fly(self, now: float) -> None:
        if not self.fliers:
            return
        cx, cy, _R = self._geom()
        left = []
        for f in self.fliers:
            k = (now - f["t0"]) / 1.6
            it = self.items[f["i"]]
            if k < 0:
                left.append(f)
                continue
            if k >= 1:
                self.cv.itemconfigure(it, state="normal")
                continue
            x, y = self._screen_xy[f["i"]]
            e = 1 - (1 - k) ** 3
            fx, fy = cx + (x - cx) * e, cy + (y - cy) * e
            s = px(4) * (1.6 - k)
            self.cv.coords(it, fx - s, fy - s, fx + s, fy + s)
            self.cv.itemconfigure(it, state="normal")
            left.append(f)
        self.fliers = left

    # -- цикл анимации ---------------------------------------------------------------
    def refresh(self) -> None:          # вызывается кабиной при показе отсека
        self.reload()
        self.start()

    def start(self) -> None:
        if self._job is None:
            self._last_tick = time.perf_counter()
            self._job = self.after(FRAME_MS, self._tick)

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _visible(self) -> bool:
        try:
            cur = getattr(self.app, "current", "lab")
            return cur in (None, "lab") and bool(self.winfo_ismapped())
        except tk.TclError:
            return False

    def _tick(self) -> None:
        self._job = None
        if not self._visible():
            return                       # отсек скрыт — цикл стоит до следующего refresh()
        t = time.perf_counter()
        try:
            self.step(t)
        except tk.TclError:
            return
        self._job = self.after(FRAME_MS, self._tick)

    def step(self, now: float) -> None:
        dt_ = min(0.2, now - self._last_tick)
        self._last_tick = now
        self.angle += ROT_SPEED * dt_ * self._lod
        self._frame += 1
        t0 = time.perf_counter()
        if self.items:
            if self._frame % self._lod == 0:
                self._place(now)
            else:
                cx, cy, _ = self._geom()
                self._place_entity(now, cx, cy)
            self._fly(now)
        ms = (time.perf_counter() - t0) * 1000
        self.frame_ms.append(ms)
        if len(self.frame_ms) >= 20:
            avg = sum(list(self.frame_ms)[-20:]) / 20
            if avg > BUDGET_MS and self._lod < 4:
                self._lod += 1
                self.frame_ms.clear()
            elif avg < BUDGET_MS / 3 and self._lod > 1:
                self._lod -= 1
                self.frame_ms.clear()

    def perf(self) -> dict:
        ms = list(self.frame_ms)
        return {"avg_ms": round(sum(ms) / len(ms), 2) if ms else 0.0, "max_ms": round(max(ms), 2) if ms else 0.0,
                "lod": self._lod, "stars": len(self.items), "edges": len(self.edge_items)}

    # -- подсказка ---------------------------------------------------------------------
    def star_at(self, x: float, y: float, radius: float | None = None) -> int | None:
        r2 = (radius or px(7)) ** 2
        best, bd = None, r2
        for i, (sx, sy) in enumerate(self._screen_xy):
            d = (sx - x) ** 2 + (sy - y) ** 2
            if d < bd:
                best, bd = i, d
        return best

    def tooltip_text(self, i: int, now: float | None = None) -> str:
        n = self.graph.nodes[i]
        kinds = {"word": _t("слово"), "verb": _t("неправильный глагол"), "form": _t("форма глагола"),
                 "book": _t("книга"), "milestone": _t("рубеж"), "exercise": _t("упражнение"),
                 "mission": _t("миссия"), "cluster": _t("туманность (свёрнутое созвездие)")}
        skills = {"en": _t("английский"), "read": _t("чтение"), "type": _t("печать")}
        lines = [f"{n['label']} — {kinds.get(n['kind'], n['kind'])} · {skills.get(n['skill'], '')}"]
        if n.get("detail"):
            lines.append(n["detail"])
        if n["last"]:
            days = int(max(0, ((now or time.time()) - n["last"]) // lab_data.DAY))
            lines.append(_t("практика: сегодня") if days == 0 else _t("практика: {0} дн. назад").format(days))
        else:
            lines.append(_t("дата практики неизвестна"))
        lines.append(_t("яркость {0} %").format(round(self.fresh[i] * 100)))
        return "\n".join(lines)

    def _on_motion(self, e) -> None:
        i = self.star_at(e.x, e.y)
        if i == self._hover:
            return
        self._hide_tip()
        if i is None:
            return
        self._hover = i
        cv = self.cv
        x, y = self._screen_xy[i]
        try:
            txt = cv.create_text(x + px(12), y - px(10), text=self.tooltip_text(i), anchor="sw",
                                 fill=theme.TEXT, font=theme.font(9), tags="tip")
            x0, y0, x1, y1 = cv.bbox(txt)
            w = cv.winfo_width()
            if x1 > w - 4:
                cv.move(txt, -(x1 - x0) - px(24), 0)
            if y0 < 4:
                cv.move(txt, 0, (y1 - y0) + px(20))
            x0, y0, x1, y1 = cv.bbox(txt)
            cv.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill=theme.PANEL_HI,
                                outline=skill_color(self.graph.nodes[i]["skill"]), tags="tip")
            cv.tag_raise(txt)
        except tk.TclError:
            pass

    def _hide_tip(self) -> None:
        self._hover = None
        try:
            self.cv.delete("tip")
        except tk.TclError:
            pass
