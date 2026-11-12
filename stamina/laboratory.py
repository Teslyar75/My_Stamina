"""Отсек «ЛАБОРАТОРИЯ»: созвездия знаний пилота на холсте Tk.

Три уровня детализации (систему не нагружаем):
1. **visual** (по умолчанию) — агрегаты по созвездиям, живая сущность, свой фон;
2. **work** — клик по кластеру/книге лениво подгружает только этот фрагмент, зум, «Назад»;
3. **full** — отдельная кнопка «Полный слепок»: чанки + прогресс + отмена → JSON для Ориона.

Раскладка: английский — полумесяц; слова от книг — веером; печать — рукав справа.
Бюджет кадра: если шаг дороже ~22 мс, геометрия обновляется реже (LOD анимации).
"""
from __future__ import annotations

import json
import math
import os
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import filedialog

from stamina import lab_data, theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import blend, px

FRAME_MS = 33            # ~30 кадров/с
BUDGET_MS = 22.0         # дороже — пропускаем обновление геометрии через кадр
MAX_STARS = 1600         # сверх — свернуть мелкие созвездия (полный граф)
MAX_EDGES = 900
MAX_FLIERS = 60
ROT_SPEED = 0.008        # рад/с — медленное дыхание карты
GOLDEN = math.pi * (3 - math.sqrt(5))
SEEN_FILE = "lab.json"
MODE_VISUAL = "visual"
MODE_WORK = "work"


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
    out.mode = getattr(graph, "mode", "full")
    out.focus = getattr(graph, "focus", None)
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
    """Позиции в единицах «радиус галактики = 1» и рёбра-контуры.

    - английский — полумесяц слева;
    - чтение — книги как центры, слова веером от книги;
    - печать — рукав справа снизу.
    """
    n = len(graph.nodes)
    pos: list[tuple[float, float]] = [(0.0, 0.0)] * n
    shape: list[tuple[int, int]] = []
    if not n:
        return pos, shape

    by_skill: dict[str, list[int]] = {s: [] for s in lab_data.SKILLS}
    for i, node in enumerate(graph.nodes):
        by_skill.setdefault(node["skill"], []).append(i)

    # -- английский: полумесяц -------------------------------------------------
    en_ids = by_skill.get("en") or []
    en_groups: dict[str, list[int]] = {}
    for i in en_ids:
        en_groups.setdefault(graph.nodes[i]["group"], []).append(i)
    en_keys = sorted(en_groups, key=lambda k: (-len(en_groups[k]), k))
    n_en = max(1, len(en_keys))
    for gi, gkey in enumerate(en_keys):
        ids = en_groups[gkey]
        # полумесяц: угол от ~100° до ~260° (открыт вправо к сущности)
        t = (gi + 0.5) / n_en
        ang = math.pi * (0.55 + 1.05 * t)          # ~99° … ~288°
        r_arm = 0.42 + 0.28 * abs(math.sin(t * math.pi))
        cx, cy = r_arm * math.cos(ang), r_arm * math.sin(ang) * 0.92
        _place_cluster(pos, shape, ids, cx, cy, spread=0.018 + 0.16 * math.sqrt(len(ids) / max(1, n)))

    # -- чтение: книги + веера слов -------------------------------------------
    read_ids = by_skill.get("read") or []
    books = [i for i in read_ids if graph.nodes[i]["kind"] == "book"]
    other_read = [i for i in read_ids if graph.nodes[i]["kind"] != "book"]
    # слова, связанные с книгами
    word_of_book: dict[int, list[int]] = {b: [] for b in books}
    linked_words: set[int] = set()
    id_to_book = {i: i for i in books}
    for a, b in graph.edges:
        for src, dst in ((a, b), (b, a)):
            if src in id_to_book and graph.nodes[dst]["kind"] in ("word", "cluster", "form"):
                word_of_book[src].append(dst)
                linked_words.add(dst)
    free_read = [i for i in other_read if i not in linked_words]
    n_books = max(1, len(books))
    for bi, bidx in enumerate(books):
        t = (bi + 0.5) / n_books
        ang = -0.55 + 1.1 * t                       # дуга справа-сверху
        r = 0.38 + 0.12 * (bi % 3) / 2
        bx, by = r * math.cos(ang), r * math.sin(ang) * 0.85
        pos[bidx] = (bx, by)
        fans = word_of_book.get(bidx) or []
        for j, wi in enumerate(fans):
            # веер: сектор ±50° от радиали наружу
            ft = (j + 0.5) / max(1, len(fans))
            fang = ang + (ft - 0.5) * 1.0
            fr = 0.10 + 0.22 * math.sqrt((j + 0.5) / max(1, len(fans)))
            pos[wi] = (bx + fr * math.cos(fang), by + fr * math.sin(fang))
            shape.append((bidx, wi))
    # рубежи/упражнения чтения — кольцо дальше
    free_groups: dict[str, list[int]] = {}
    for i in free_read:
        free_groups.setdefault(graph.nodes[i]["group"], []).append(i)
    for gi, gkey in enumerate(sorted(free_groups)):
        ids = free_groups[gkey]
        t = (gi + 0.5) / max(1, len(free_groups))
        ang = -0.2 + 0.9 * t
        r = 0.62 + 0.08 * (gi % 2)
        _place_cluster(pos, shape, ids, r * math.cos(ang), r * math.sin(ang) * 0.8,
                       spread=0.02 + 0.1 * math.sqrt(len(ids) / max(1, n)))

    # -- печать: рукав справа-снизу -------------------------------------------
    type_ids = by_skill.get("type") or []
    type_groups: dict[str, list[int]] = {}
    for i in type_ids:
        type_groups.setdefault(graph.nodes[i]["group"], []).append(i)
    type_keys = sorted(type_groups, key=lambda k: (-len(type_groups[k]), k))
    for gi, gkey in enumerate(type_keys):
        ids = type_groups[gkey]
        t = (gi + 0.5) / max(1, len(type_keys))
        ang = -0.9 - 0.85 * t                       # нижний правый сектор
        r = 0.30 + 0.55 * math.sqrt(t)
        cx, cy = r * math.cos(ang), r * math.sin(ang) * 0.9
        _place_cluster(pos, shape, ids, cx, cy, spread=0.018 + 0.14 * math.sqrt(len(ids) / max(1, n)))

    return pos, shape


def _place_cluster(pos, shape, ids, cx, cy, *, spread: float) -> None:
    for j, ni in enumerate(ids):
        rr = spread * math.sqrt((j + 0.5) / max(1, len(ids)))
        aa = j * GOLDEN
        pos[ni] = (cx + rr * math.cos(aa), cy + rr * math.sin(aa))
    for j in range(1, len(ids)):
        x, y = pos[ids[j]]
        best = min(range(max(0, j - 6), j),
                   key=lambda q: (pos[ids[q]][0] - x) ** 2 + (pos[ids[q]][1] - y) ** 2)
        shape.append((ids[best], ids[j]))


class LabScreen(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=theme.BG)
        self.app = app
        self.demo = os.environ.get("STAMINA_LAB_DEMO") == "1"
        self.mode = MODE_VISUAL
        self.focus_group: str | None = None
        self._full_cache: lab_data.Graph | None = None
        self.graph = lab_data.Graph()
        self.pos: list[tuple[float, float]] = []
        self.edges: list[tuple[int, int]] = []
        self.fresh: list[float] = []
        self.items: list[int] = []
        self.edge_items: list[int] = []
        self.bg_items: list[int] = []
        self.fliers: list[dict] = []
        self.angle = 0.0
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.t0 = time.perf_counter()
        self._last_tick = self.t0
        self._job = None
        self._frame = 0
        self._lod = 1
        self.frame_ms: deque = deque(maxlen=120)
        self._screen_xy: list[tuple[float, float]] = []
        self._hover = None
        self._export_cancel = False
        self._export_dlg = None
        self.entity = lab_data.entity_state(set(), 0, time.time())
        self._build()

    # -- сборка --------------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), px(4)))
        tk.Label(top, text=_t("ЛАБОРАТОРИЯ · СОЗВЕЗДИЯ ЗНАНИЙ"), bg=theme.BG, fg=theme.TEXT,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        self.badge = tk.Label(top, text="", bg=theme.BG, fg=theme.RED, font=theme.font(9, True))
        self.badge.pack(side=tk.LEFT, padx=px(10))
        self.mode_lbl = tk.Label(top, text="", bg=theme.BG, fg=theme.MUTED, font=theme.font(9))
        self.mode_lbl.pack(side=tk.LEFT, padx=px(6))
        HudButton(top, _t("ОБНОВИТЬ"), self.reload, height=30, font_size=9).pack(side=tk.RIGHT)
        self.export_btn = HudButton(top, _t("ПОЛНЫЙ СЛЕПОК"), self.export_full, height=30, font_size=9)
        self.export_btn.pack(side=tk.RIGHT, padx=(0, px(6)))
        self.back_btn = HudButton(top, _t("НАЗАД"), self.back_to_visual, height=30, font_size=9)
        # back_btn пакуется только в рабочем режиме
        self.summary = tk.Label(top, text="", bg=theme.BG, fg=theme.MUTED, font=theme.font(9))
        self.summary.pack(side=tk.RIGHT, padx=px(10))
        self.panel = HudPanel(self, title=_t("КАРТА ЗНАНИЙ ПИЛОТА"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=(0, px(10)))
        self.cv = tk.Canvas(self.panel.body, bg=theme.PANEL, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._redraw())
        self.cv.bind("<Motion>", self._on_motion)
        self.cv.bind("<Leave>", lambda _e: self._hide_tip())
        self.cv.bind("<Button-1>", self._on_click)

    # -- данные --------------------------------------------------------------------
    def set_demo(self, on: bool, graph: lab_data.Graph | None = None) -> None:
        """Демо-режим только для скриншотов и тестов (плашка «ДЕМО-ДАННЫЕ»)."""
        self.demo = bool(on)
        self._demo_graph = graph
        self._full_cache = None
        self.mode = MODE_VISUAL
        self.focus_group = None
        self.reload()

    def _pilot_dir(self) -> Path | None:
        return lab_data.pilot_root(self.app)

    def _raw_graph(self, now: float) -> lab_data.Graph:
        if self.demo:
            from stamina.lab_demo import demo_graph
            g = getattr(self, "_demo_graph", None) or demo_graph(1000, now=now)
            g.mode = "full"
            return g
        return lab_data.collect(self._pilot_dir(), now)

    def _ensure_full(self, now: float) -> lab_data.Graph:
        if self._full_cache is None:
            self._full_cache = self._raw_graph(now)
        return self._full_cache

    def reload(self) -> None:
        now = time.time()
        self._full_cache = None
        if self.mode == MODE_WORK and self.focus_group:
            self._load_fragment(self.focus_group, now)
            return
        full = self._ensure_full(now)
        g = lab_data.collapse_to_clusters(full)
        self._apply_graph(g, now, zoom=1.0, pan=(0.0, 0.0))

    def _load_fragment(self, group: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        full = self._ensure_full(now)
        g = lab_data.fragment_of(full, group)
        # если фрагмент пуст — остаёмся в визуальном
        if not g.nodes:
            self.mode = MODE_VISUAL
            self.focus_group = None
            self.reload()
            return
        self.mode = MODE_WORK
        self.focus_group = group
        self._apply_graph(g, now, zoom=1.55, pan=_focus_pan(g))

    def _apply_graph(self, g: lab_data.Graph, now: float, *, zoom: float, pan: tuple[float, float]) -> None:
        self.graph = aggregate(g) if self.mode != MODE_WORK else g
        self.fresh = [lab_data.freshness(n["last"], n["strength"], now) for n in self.graph.nodes]
        self.pos, shape = layout(self.graph)
        edges = list(dict.fromkeys(list(self.graph.edges) + shape))
        self.edges = edges[:MAX_EDGES]
        self.entity = self.graph.entity(now)
        self.zoom = zoom
        self.pan_x, self.pan_y = pan
        self._new_fliers()
        self.badge.configure(text=_t("ДЕМО-ДАННЫЕ") if self.demo else "")
        c = self.graph.counts()
        if self.mode == MODE_WORK:
            self.mode_lbl.configure(text=_t("режим: рабочий"))
            self.summary.configure(text=_t("фрагмент · {0} звёзд").format(len(self.graph.nodes)))
            try:
                self.back_btn.pack(side=tk.RIGHT, padx=(0, px(6)))
            except tk.TclError:
                pass
        else:
            self.mode_lbl.configure(text=_t("режим: визуальный"))
            self.summary.configure(text=_t("английский {0} · чтение {1} · печать {2}").format(
                c.get("en", 0), c.get("read", 0), c.get("type", 0)))
            try:
                self.back_btn.pack_forget()
            except tk.TclError:
                pass
        self._redraw()

    def back_to_visual(self) -> None:
        self.mode = MODE_VISUAL
        self.focus_group = None
        self.reload()

    def _new_fliers(self) -> None:
        """Новые звёзды с прошлого визита влетают из центра (не больше MAX_FLIERS)."""
        self.fliers = []
        ids = [n["id"] for n in self.graph.nodes]
        if self.demo:
            fresh_ids = ids[-min(24, len(ids)):]
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
            if nid in ix:
                self.fliers.append({"i": ix[nid], "t0": now + k * 0.05})

    # -- полный слепок -------------------------------------------------------------
    def export_full(self) -> None:
        """Уровень 3: полный слепок чанками с прогрессом и отменой → JSON."""
        if self._export_dlg is not None:
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), (_t("Все файлы"), "*.*")],
            initialfile="lab_entity_snapshot.json",
            title=_t("ПОЛНЫЙ СЛЕПОК"),
        )
        if not path:
            return
        self._export_cancel = False
        dlg = tk.Toplevel(self)
        dlg.title(_t("ПОЛНЫЙ СЛЕПОК"))
        dlg.configure(bg=theme.BG)
        dlg.transient(self.winfo_toplevel())
        self._export_dlg = dlg
        tk.Label(dlg, text=_t("Сборка слепка сущности…"), bg=theme.BG, fg=theme.TEXT,
                 font=theme.font(11, True)).pack(padx=px(16), pady=(px(12), px(6)))
        self._export_status = tk.Label(dlg, text="0 %", bg=theme.BG, fg=theme.MUTED, font=theme.font(10))
        self._export_status.pack(padx=px(16))
        self._export_bar = tk.Canvas(dlg, width=px(280), height=px(14), bg=theme.PANEL,
                                     highlightthickness=1, highlightbackground=theme.LINE)
        self._export_bar.pack(padx=px(16), pady=px(8))
        self._export_fill = self._export_bar.create_rectangle(0, 0, 0, px(14), outline="", fill=theme.PURPLE)
        row = tk.Frame(dlg, bg=theme.BG)
        row.pack(pady=(px(4), px(12)))
        HudButton(row, _t("ОТМЕНИТЬ"), self._cancel_export, height=30, font_size=9).pack()
        dlg.protocol("WM_DELETE_WINDOW", self._cancel_export)
        self.after(30, lambda: self._export_step(Path(path)))

    def _cancel_export(self) -> None:
        self._export_cancel = True

    def _export_step(self, path: Path) -> None:
        root = None if self.demo else self._pilot_dir()
        # демо: пишем слепок демо-графа через временный обход collect
        try:
            if self.demo:
                self._export_demo(path)
                return
            snap = None
            for ev in lab_data.iter_snapshot(root, cancel=lambda: self._export_cancel):
                self._export_progress(ev)
                try:
                    self.update_idletasks()
                except tk.TclError:
                    return
                if ev.get("phase") == "cancelled":
                    self._close_export()
                    return
                if ev.get("phase") == "done":
                    snap = ev["snapshot"]
            if snap is None:
                self._close_export()
                return
            path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
            self._export_status.configure(text=_t("Готово: {0}").format(path.name))
            self.after(600, self._close_export)
        except Exception:  # noqa: BLE001
            self._close_export()

    def _export_demo(self, path: Path) -> None:
        """Слепок демо-графа (файлы пилота не трогаем)."""
        now = time.time()
        g = self._ensure_full(now)
        total = len(g.nodes)
        nodes_out = []
        chunk = lab_data.SNAPSHOT_CHUNK
        for i in range(0, max(total, 1), chunk):
            if self._export_cancel:
                self._close_export()
                return
            if total == 0:
                break
            for n in g.nodes[i:i + chunk]:
                row = dict(n)
                row["fresh"] = round(lab_data.freshness(n["last"], n["strength"], now), 4)
                nodes_out.append(row)
            self._export_progress({"phase": "nodes", "done": min(i + chunk, total), "total": total})
            try:
                self.update_idletasks()
            except tk.TclError:
                return
        snap = {
            "version": lab_data.SNAPSHOT_VERSION,
            "kind": "lab_entity_snapshot",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "entity": g.entity(now),
            "counts": g.counts(),
            "nodes": nodes_out,
            "edges": [[g.nodes[a]["id"], g.nodes[b]["id"]] for a, b in g.edges],
            "gaps": list(g.gaps),
            "demo": True,
        }
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        self._export_status.configure(text=_t("Готово: {0}").format(path.name))
        self.after(600, self._close_export)

    def _export_progress(self, ev: dict) -> None:
        if self._export_dlg is None:
            return
        total = max(1, int(ev.get("total") or 1))
        done = int(ev.get("done") or 0)
        frac = 0.05 if ev.get("phase") == "collect" else done / total
        try:
            w = int(self._export_bar.winfo_width() * max(0.0, min(1.0, frac)))
            self._export_bar.coords(self._export_fill, 0, 0, w, px(14))
            pct = int(round(frac * 100))
            self._export_status.configure(text=f"{pct} % · {done}/{total}")
        except tk.TclError:
            pass

    def _close_export(self) -> None:
        dlg = self._export_dlg
        self._export_dlg = None
        if dlg is not None:
            try:
                dlg.destroy()
            except tk.TclError:
                pass

    # -- рисование -----------------------------------------------------------------
    def _geom(self):
        w, h = max(2, self.cv.winfo_width()), max(2, self.cv.winfo_height())
        return w / 2, h / 2, min(w, h) * 0.46

    def _draw_backdrop(self, cx: float, cy: float, R: float) -> None:
        """Свой фон отсека: лёгкая туманность (кольца + едва заметные пятна)."""
        cv = self.cv
        self.bg_items = []
        # концентрические кольца — глубина без «грязи»
        for k in range(1, 5):
            r = R * (0.28 + 0.22 * k)
            col = blend(theme.PANEL, theme.PURPLE, 0.10 + 0.04 * k)
            self.bg_items.append(cv.create_oval(
                cx - r, cy - r * 0.88, cx + r, cy + r * 0.88,
                fill="", outline=col, width=1, tags="bg"))
        # едва заметные цветовые пятна навыков (не перекрывают звёзды)
        for ang0, col in ((2.4, theme.CYAN), (-0.25, theme.AMBER), (-2.0, theme.GREEN)):
            rr = R * 0.55
            x = cx + rr * math.cos(ang0)
            y = cy + rr * math.sin(ang0) * 0.86
            rad = R * 0.28
            fill = blend(theme.PANEL, col, 0.06)
            self.bg_items.append(cv.create_oval(
                x - rad, y - rad * 0.65, x + rad, y + rad * 0.65,
                fill=fill, outline="", tags="bg"))

    def _redraw(self) -> None:
        cv = self.cv
        try:
            cv.delete("all")
        except tk.TclError:
            return
        self.items, self.edge_items, self.bg_items = [], [], []
        cx, cy, R = self._geom()
        if not self.graph.nodes:
            # пустое состояние — только тонкие кольца сущности, без пятен фона
            col = blend(theme.PANEL, theme.PURPLE, 0.35)
            for k in range(3):
                r = px(18) + k * px(14)
                cv.create_oval(cx - r, cy - r - px(40), cx + r, cy + r - px(40), outline=col, width=1)
            self._draw_empty(cx, cy, R)
            return
        self._draw_backdrop(cx, cy, R)
        line = blend(theme.PANEL, theme.LINE_HI, 0.55)
        for _ in self.edges:
            self.edge_items.append(cv.create_line(0, 0, 0, 0, fill=line, width=1, tags="edge"))
        flying = {f["i"] for f in self.fliers}
        for i, n in enumerate(self.graph.nodes):
            f = self.fresh[i]
            col = blend(theme.PANEL, skill_color(n["skill"]), 0.25 + 0.75 * f)
            self.items.append(cv.create_oval(0, 0, 0, 0, fill=col, outline="",
                                             state="hidden" if i in flying else "normal", tags="star"))
        # живой сгусток-сущность: ядро + оболочка + «туман» + орбитали
        self._entity_items = [cv.create_oval(0, 0, 0, 0, outline="", fill="", tags="entity")
                              for _ in range(7)]
        self._tip = None
        self._place(time.perf_counter(), full=True)

    def _draw_empty(self, cx, cy, R) -> None:
        cv = self.cv
        cv.create_text(cx, cy + px(30), text=_t("Лаборатория ждёт первых знаний"), fill=theme.TEXT,
                       font=theme.font(14, True))
        cv.create_text(cx, cy + px(70), width=max(200, int(R * 1.8)), justify="center", fill=theme.MUTED,
                       font=theme.font(10),
                       text=_t("Звёзды появятся сами: отметьте слово «знаю» или повторяйте карточки в «Английском», "
                               "прочитайте текст в «Скорочтении», пройдите миссию на «Мостике»."))

    def _star_xy(self, i: int, ca: float, sa: float, cx: float, cy: float, R: float) -> tuple[float, float]:
        x, y = self.pos[i]
        x = (x + self.pan_x) * self.zoom
        y = (y + self.pan_y) * self.zoom
        return cx + (x * ca - y * sa) * R, cy + (x * sa + y * ca) * R * 0.86

    def _place(self, now: float, full: bool = False) -> None:
        cv = self.cv
        cx, cy, R = self._geom()
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        xy = [self._star_xy(i, ca, sa, cx, cy, R) for i in range(len(self.pos))]
        self._screen_xy = xy
        base = max(1.0, px(1.6)) * (1.15 if self.mode == MODE_WORK else 1.0)
        coords = cv.coords
        for i, it in enumerate(self.items):
            n = self.graph.nodes[i]
            kind_mul = (2.4 if n["kind"] in ("book", "cluster") else
                        1.5 if n["kind"] in ("verb", "milestone", "mission") else 1.0)
            # пульс свежести
            pulse = 1.0 + 0.04 * self.fresh[i] * math.sin((now - self.t0) * (1.2 + 0.8 * self.fresh[i]) + i * 0.3)
            s = base * (0.7 + 0.9 * self.fresh[i]) * kind_mul * pulse
            x, y = xy[i]
            coords(it, x - s, y - s, x + s, y + s)
        for k, it in enumerate(self.edge_items):
            a, b = self.edges[k]
            coords(it, *xy[a], *xy[b])
        self._place_entity(now, cx, cy)

    def _place_entity(self, now: float, cx: float, cy: float) -> None:
        """Живой сгусток: переливается и движется; без практики — тише, в тумане."""
        e = self.entity
        v = e["vitality"]
        quiet = e.get("quiet_days", 0) or 0
        mist = 0.0 if quiet < 0 else min(0.55, max(0.0, (quiet - 2) / 14))
        speed = 0.55 + 1.6 * v
        t = (now - self.t0) * speed
        # ядро слегка «дышит» и смещается — живой сгусток, не точка
        breath = math.sin(t)
        wob_x = math.sin(t * 0.7) * px(3) * (0.35 + 0.65 * v)
        wob_y = math.cos(t * 0.55) * px(2.5) * (0.35 + 0.65 * v)
        ex, ey = cx + wob_x, cy + wob_y
        r0 = px(8) * (1 + 0.08 * min(e["growth"], 8.0))
        # цвета перелива: purple ↔ cyan/amber по фазе
        shimmer = 0.5 + 0.5 * math.sin(t * 0.9)
        core = blend(theme.PURPLE, theme.CYAN, 0.25 * shimmer * v)
        haze = blend(theme.PANEL, theme.PURPLE, 0.18 * (1 - mist) + 0.06)
        items = self._entity_items
        # 0..2 — туман/оболочка, 3 — ядро, 4..6 — орбитали-капельки
        specs = [
            (2.8, blend(theme.PANEL, haze, 0.35 + 0.25 * mist), 0.35),
            (1.9, blend(theme.PANEL, core, 0.18 * (1 - mist)), 0.5),
            (1.35, blend(theme.PANEL, core, 0.40 * (0.5 + 0.5 * v)), 0.7),
            (0.95, blend(theme.PANEL, core, 0.80 * (0.45 + 0.55 * v)), 1.0),
        ]
        for k, (mul, fill, amp) in enumerate(specs):
            if k >= len(items):
                break
            # лёгкая асимметрия сгустка
            rx = r0 * mul * (1 + 0.08 * v * breath * amp)
            ry = r0 * mul * (0.82 + 0.08 * v * math.cos(t * 1.1) * amp)
            ox = wob_x * 0.15 * k
            oy = wob_y * 0.15 * k
            try:
                self.cv.coords(items[k], ex - rx + ox, ey - ry + oy, ex + rx + ox, ey + ry + oy)
                self.cv.itemconfigure(items[k], fill=fill)
            except tk.TclError:
                return
        # орбитали
        for k in range(4, min(7, len(items))):
            oi = k - 4
            oa = t * (0.8 + 0.2 * oi) + oi * 2.1
            orad = r0 * (1.8 + 0.35 * oi) * (0.85 + 0.15 * v)
            ox = ex + orad * math.cos(oa)
            oy = ey + orad * math.sin(oa) * 0.75
            s = px(2.2) * (0.7 + 0.5 * v) * (1 + 0.1 * math.sin(t + oi))
            fill = blend(theme.PANEL, skill_color(("en", "read", "type")[oi]), 0.35 + 0.4 * v)
            try:
                self.cv.coords(items[k], ox - s, oy - s, ox + s, oy + s)
                self.cv.itemconfigure(items[k], fill=fill)
            except tk.TclError:
                return
        for it in reversed(items):
            try:
                self.cv.tag_raise(it)
            except tk.TclError:
                return

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
        else:
            # пустой граф — всё равно дышим сущностью, если есть items сущности после empty
            pass
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
                "lod": self._lod, "stars": len(self.items), "edges": len(self.edge_items),
                "mode": self.mode}

    # -- подсказка и клик ----------------------------------------------------------
    def star_at(self, x: float, y: float, radius: float | None = None) -> int | None:
        r2 = (radius or px(10)) ** 2
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
        if n.get("count"):
            lines.append(_t("внутри: {0}").format(n["count"]))
        if n.get("detail") and n["kind"] != "cluster":
            lines.append(n["detail"])
        if n["last"]:
            days = int(max(0, ((now or time.time()) - n["last"]) // lab_data.DAY))
            lines.append(_t("практика: сегодня") if days == 0 else _t("практика: {0} дн. назад").format(days))
        else:
            lines.append(_t("дата практики неизвестна"))
        lines.append(_t("яркость {0} %").format(round(self.fresh[i] * 100)))
        if self.mode == MODE_VISUAL and n["kind"] in ("cluster", "book"):
            lines.append(_t("клик — открыть фрагмент"))
        return "\n".join(lines)

    def _on_click(self, e) -> None:
        i = self.star_at(e.x, e.y)
        if i is None:
            return
        n = self.graph.nodes[i]
        if self.mode == MODE_VISUAL and n["kind"] in ("cluster", "book", "verb", "milestone",
                                                       "mission", "exercise"):
            self._load_fragment(n["group"])

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


def _focus_pan(g: lab_data.Graph) -> tuple[float, float]:
    """Сместить центр зума к центру масс фрагмента (в координатах раскладки ≈ 0)."""
    # раскладка ещё не посчитана — лёгкий сдвиг к навыку фрагмента
    if not g.nodes:
        return (0.0, 0.0)
    skill = g.nodes[0]["skill"]
    return {"en": (0.25, 0.0), "read": (-0.15, 0.05), "type": (-0.2, 0.25)}.get(skill, (0.0, 0.0))
