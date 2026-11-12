"""Лаборатория: адаптер данных, три уровня LOD, раскладка, экран, слепок."""
from __future__ import annotations

import json
import os
import tempfile
import time
import types
import unittest
from pathlib import Path

from stamina import lab_data, nav
from stamina.lab_demo import demo_graph
from stamina.laboratory import (
    DRAG_CLICK_PX, MAX_STARS, MODE_VISUAL, MODE_WORK, PITCH_MAX, WORK_ZOOM,
    ZOOM_MAX, ZOOM_MIN, ZOOM_STEP, aggregate, clamp_pitch, layout, project_point,
    zoom_toward,
)

NOW = time.mktime((2026, 11, 4, 12, 0, 0, 0, 0, -1))


def _day(days_ago: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(NOW - days_ago * 86400))


def _write(root: Path, name: str, data: dict) -> None:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class LabDataTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def _fill(self):
        _write(self.root, "english.json", {
            "words": {"case": {"known": True, "known_at": _day(3)}},
            "cards": {"time": {"interval": 25, "reps": 4, "last": _day(1)},
                      "dog": {"interval": 3, "reps": 1, "last": _day(1)}},   # ещё не выучено
            "verb_scores": {"go:0": 92, "go:1": 85, "be:0": 40},
            "xp": {"by_day": {_day(0): 5}},
            "book_sentences": {
                "books": {"t1": {"title": "Tale", "sentences": [
                    {"id": "t1:0", "en": "In any case, it is time.", "w0": 0},
                    {"id": "t1:9", "en": "Never practised.", "w0": 9}]}},
                "cards": {"t1:0": {"reps": 2, "last": _day(2)}}},
        })
        _write(self.root, "stats.json", {
            "runs": [{"ts": NOW - 86400, "chars": 300, "cpm": 210, "acc": 96},
                     {"ts": NOW - 5 * 86400, "chars": 300, "cpm": 120, "acc": 91, "mission": "en-01"}],
            "missions": {"en-01": {"stars": 2}, "en-02": {"stars": 1}, "en-03": {"stars": 0}},
        })
        _write(self.root, "speedread.json", {
            "sessions": [{"title": "Tale", "words": 900, "eff_wpm": 260, "ts": NOW - 2 * 86400}],
            "exercises": {"E-SHL": {"5x5-a": {"runs": [{"ts": NOW - 86400, "result": 40}]}}},
            "days": [_day(1)],
        })
        _write(self.root, "library/library.json", {"texts": [{"id": "t1", "title": "Tale"}]})

    def test_empty_pilot_gives_empty_graph(self):
        g = lab_data.collect(self.root, NOW)
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.entity(NOW)["quiet_days"], -1)
        self.assertEqual(lab_data.collect(None, NOW).nodes, [])

    def test_real_files_become_stars_and_edges(self):
        self._fill()
        g = lab_data.collect(self.root, NOW)
        ids = {n["id"] for n in g.nodes}
        self.assertTrue({"w:case", "w:time", "v:go", "vf:go:v2", "vf:go:v3", "b:t1"} <= ids)
        self.assertNotIn("w:dog", ids)                       # интервал 3 дня — не выдумываем знание
        self.assertNotIn("v:be", ids)                        # 40 баллов — не зачтено
        self.assertTrue({"ty:cpm:100", "ty:cpm:200", "ty:acc:95", "ty:m:en-01", "ty:m:en-02"} <= ids)
        self.assertNotIn("ty:cpm:250", ids)
        self.assertNotIn("ty:m:en-03", ids)
        self.assertTrue({"sr:wpm:250", "sr:ex:E-SHL"} <= ids)
        self.assertNotIn("sr:wpm:300", ids)
        edges = {(g.nodes[a]["id"], g.nodes[b]["id"]) for a, b in g.edges}
        self.assertIn(("v:go", "vf:go:v2"), edges)
        self.assertIn(("w:case", "b:t1"), edges)             # слово из отработанного предложения
        self.assertIn(("w:time", "b:t1"), edges)
        self.assertIn(("ty:cpm:100", "ty:cpm:150"), edges)
        self.assertIn(("ty:m:en-01", "ty:m:en-02"), edges)
        case = next(n for n in g.nodes if n["id"] == "w:case")
        self.assertTrue(case["group"].startswith("cefr:"))   # созвездие = набор CEFR и тема
        self.assertEqual(g.counts()["read"], 5)  # книга + 3 рубежа (150-250) + упражнение
        self.assertGreaterEqual(g.entity(NOW)["recent_days"], 2)

    def test_collect_is_read_only(self):
        self._fill()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        lab_data.collect(self.root, NOW)
        lab_data.collect_visual(self.root, NOW)
        list(lab_data.iter_snapshot(self.root, now=NOW))
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_broken_files_do_not_crash(self):
        (self.root / "english.json").write_text("{not json", encoding="utf-8")
        _write(self.root, "stats.json", {"runs": "oops", "missions": []})
        g = lab_data.collect(self.root, NOW)
        self.assertIsInstance(g.nodes, list)

    def test_freshness_dims_but_never_disappears(self):
        f0 = lab_data.freshness(NOW, 0, NOW)
        f10 = lab_data.freshness(NOW - 10 * 86400, 0, NOW)
        f10_strong = lab_data.freshness(NOW - 10 * 86400, 8, NOW)
        f_old = lab_data.freshness(NOW - 3650 * 86400, 0, NOW)
        self.assertAlmostEqual(f0, 1.0)
        self.assertLess(f10, f0)
        self.assertGreater(f10_strong, f10)                  # крепкое знание тускнеет медленнее
        self.assertGreaterEqual(f_old, lab_data.FLOOR - 1e-9)

    def test_entity_quiets_after_break(self):
        busy = {_day(i) for i in range(14)}
        pause = {_day(i) for i in range(10, 24)}
        a = lab_data.entity_state(busy, 100, NOW)
        b = lab_data.entity_state(pause, 100, NOW)
        self.assertEqual(a["quiet_days"], 0)
        self.assertEqual(b["quiet_days"], 10)
        self.assertGreater(a["vitality"], b["vitality"])
        self.assertGreaterEqual(b["vitality"], 0.08)


class LabLodLevelsTest(unittest.TestCase):
    """Три уровня: visual / fragment / full snapshot."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        LabDataTest._fill(self)  # type: ignore[arg-type]

    def test_visual_has_no_individual_words(self):
        vis = lab_data.collect_visual(self.root, NOW)
        kinds = {n["kind"] for n in vis.nodes}
        self.assertNotIn("word", kinds)
        self.assertNotIn("form", kinds)
        self.assertTrue(any(n["kind"] == "cluster" for n in vis.nodes) or any(n["kind"] == "book" for n in vis.nodes))
        self.assertEqual(vis.mode, "visual")
        # визуальный заметно легче полного
        full = lab_data.collect(self.root, NOW)
        self.assertLessEqual(len(vis.nodes), len(full.nodes))

    def test_fragment_loads_only_one_group(self):
        full = lab_data.collect(self.root, NOW)
        case = next(n for n in full.nodes if n["id"] == "w:case")
        frag = lab_data.collect_fragment(self.root, case["group"], NOW)
        self.assertEqual(frag.mode, "fragment")
        self.assertEqual(frag.focus, case["group"])
        # все «свои» узлы группы на месте; чужие CEFR-темы не тянем
        groups = {n["group"] for n in frag.nodes}
        self.assertIn(case["group"], groups)
        # книга может приехать как сосед по ребру
        self.assertTrue(any(n["id"] == "w:case" for n in frag.nodes))
        self.assertLess(len(frag.nodes), len(full.nodes))

    def test_book_fragment_includes_linked_words(self):
        frag = lab_data.collect_fragment(self.root, "book:t1", NOW)
        ids = {n["id"] for n in frag.nodes}
        self.assertIn("b:t1", ids)
        self.assertTrue({"w:case", "w:time"} & ids)

    def test_snapshot_chunks_progress_and_cancel(self):
        events = list(lab_data.iter_snapshot(self.root, chunk_size=2, now=NOW))
        self.assertEqual(events[0]["phase"], "collect")
        self.assertEqual(events[-1]["phase"], "done")
        snap = events[-1]["snapshot"]
        self.assertEqual(snap["version"], lab_data.SNAPSHOT_VERSION)
        self.assertEqual(snap["kind"], "lab_entity_snapshot")
        self.assertIn("entity", snap)
        self.assertIn("nodes", snap)
        self.assertIn("edges", snap)
        self.assertTrue(all("fresh" in n for n in snap["nodes"]))
        # отмена на первом же шаге после collect
        flag = {"n": 0}

        def cancel():
            flag["n"] += 1
            return flag["n"] > 1

        ev2 = list(lab_data.iter_snapshot(self.root, chunk_size=1, now=NOW, cancel=cancel))
        self.assertTrue(any(e.get("phase") == "cancelled" for e in ev2))
        self.assertFalse(any(e.get("phase") == "done" for e in ev2))

    def test_export_snapshot_writes_json(self):
        out = Path(tempfile.mkdtemp()) / "snap.json"
        snap = lab_data.export_snapshot(self.root, out, chunk_size=5, now=NOW)
        self.assertIsNotNone(snap)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["kind"], "lab_entity_snapshot")
        self.assertEqual(len(data["nodes"]), len(snap["nodes"]))

    def test_star_neighborhood_one_hop_batched(self):
        full = lab_data.collect(self.root, NOW)
        bund = lab_data.star_neighborhood(full, "b:t1", limit=1, offset=0, now=NOW)
        self.assertIsNotNone(bund)
        self.assertEqual(bund["selected"]["id"], "b:t1")
        self.assertEqual(bund["selected"]["detail_level"], "full")
        self.assertLessEqual(len(bund["neighbors"]), 1)
        self.assertTrue(all(n["detail_level"] == "compact" for n in bund["neighbors"]))
        self.assertGreaterEqual(bund["neighbor_total"], 1)
        # вторая порция
        if bund["has_more"]:
            more = lab_data.star_neighborhood(
                full, "b:t1", limit=1, offset=1, now=NOW)
            self.assertTrue(more["neighbors"])
            ids1 = {n["id"] for n in bund["neighbors"]}
            ids2 = {n["id"] for n in more["neighbors"]}
            self.assertTrue(ids1.isdisjoint(ids2))
        miss = lab_data.star_neighborhood(full, "nope", now=NOW)
        self.assertIsNone(miss)


class LabLayoutTest(unittest.TestCase):
    def test_demo_is_marked_and_sized(self):
        g = demo_graph(1000, now=NOW)
        self.assertTrue(g.demo)
        self.assertEqual(len(g.nodes), 1000)

    def test_layout_fits_unit_disc(self):
        g = demo_graph(1000, now=NOW)
        pos, shape = layout(g)
        self.assertEqual(len(pos), 1000)
        self.assertEqual(len(pos[0]), 3)
        self.assertTrue(all(x * x + y * y < 1.6 for x, y, _z in pos))
        # контурные рёбра — внутри группы или книга→слово
        for a, b in shape:
            ga, gb = g.nodes[a]["group"], g.nodes[b]["group"]
            kinds = {g.nodes[a]["kind"], g.nodes[b]["kind"]}
            self.assertTrue(ga == gb or "book" in kinds)

    def test_english_crescent_and_book_fans(self):
        g = demo_graph(400, now=NOW)
        pos, _ = layout(g)
        en = [pos[i] for i, n in enumerate(g.nodes) if n["skill"] == "en"]
        self.assertTrue(en)
        # полумесяц: центр масс английского слева от нуля (x < 0)
        cx = sum(p[0] for p in en) / len(en)
        self.assertLess(cx, 0.05)
        books = [i for i, n in enumerate(g.nodes) if n["kind"] == "book"]
        self.assertTrue(books)
        # слова у книги ближе к ней, чем случайная точка у края
        bi = books[0]
        linked = [b if a == bi else a for a, b in g.edges if a == bi or b == bi]
        linked = [i for i in linked if g.nodes[i]["kind"] == "word"]
        if linked:
            bx, by, _bz = pos[bi]
            dists = [((pos[i][0] - bx) ** 2 + (pos[i][1] - by) ** 2) ** 0.5 for i in linked]
            self.assertTrue(all(d < 0.55 for d in dists))

    def test_project_zoom_and_pitch_clamp(self):
        sx0, sy0, d0 = project_point(0.2, 0.0, 0.0, yaw=0.0, pitch=0.0, zoom=1.0,
                                     pan_x=0, pan_y=0, cx=100, cy=100, R=50)
        sx1, sy1, d1 = project_point(0.2, 0.0, 0.0, yaw=0.0, pitch=0.0, zoom=2.0,
                                     pan_x=0, pan_y=0, cx=100, cy=100, R=50)
        self.assertGreater(abs(sx1 - 100), abs(sx0 - 100))
        self.assertGreater(d0, 0.5)
        self.assertEqual(clamp_pitch(10), PITCH_MAX)
        self.assertEqual(clamp_pitch(-10), -PITCH_MAX)
        z, px_, py_ = zoom_toward(1.0, 0.0, 0.0, factor=ZOOM_STEP, cursor_uv=(0.3, -0.1))
        self.assertGreater(z, 1.0)
        self.assertLessEqual(z, ZOOM_MAX)
        z2, _, _ = zoom_toward(ZOOM_MAX, 0.0, 0.0, factor=ZOOM_STEP, cursor_uv=(0.1, 0.1))
        self.assertEqual(z2, ZOOM_MAX)
        self.assertGreaterEqual(ZOOM_MIN, 0.2)
        self.assertGreater(WORK_ZOOM, 1.0)
        self.assertGreaterEqual(DRAG_CLICK_PX, 3)

    def test_aggregate_caps_star_count(self):
        g = demo_graph(3000, now=NOW)
        a = aggregate(g, 1200)
        self.assertLessEqual(len(a.nodes), 1200)
        self.assertTrue(any(n["kind"] == "cluster" for n in a.nodes))
        self.assertIs(aggregate(demo_graph(500, now=NOW)).__class__, lab_data.Graph)
        self.assertLessEqual(MAX_STARS, 2000)

    def test_visual_collapse_of_demo_is_light(self):
        g = demo_graph(1000, now=NOW)
        vis = lab_data.collapse_to_clusters(g)
        self.assertLess(len(vis.nodes), 200)
        self.assertFalse(any(n["kind"] == "word" for n in vis.nodes))

    def test_hotkeys_keep_settings_on_ctrl9(self):
        keys = dict((n, k) for k, n in nav.zone_hotkeys(nav.zones()))
        self.assertEqual(keys["lab"], "0")
        self.assertEqual(keys["settings"], "9")
        self.assertEqual(keys["bridge"], "1")
        self.assertIn("lab", nav.ZONE_ORDER)


class LabScreenTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from stamina import theme
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        theme.init(self.root)
        self.root.geometry("1024x600")
        self.dir = Path(tempfile.mkdtemp())
        self.app = types.SimpleNamespace(current="lab", pilot=None)
        from stamina import laboratory
        self._orig = laboratory.lab_data.pilot_root
        laboratory.lab_data.pilot_root = lambda app: self.dir
        from stamina.laboratory import LabScreen
        self.scr = LabScreen(self.root, self.app)
        self.scr.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        from stamina import laboratory
        laboratory.lab_data.pilot_root = self._orig
        self.root.destroy()

    def _texts(self):
        cv = self.scr.cv
        return " ".join(cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text")

    def test_empty_state(self):
        self.scr.reload()
        self.root.update()
        self.assertIn("Лаборатория ждёт первых знаний", self._texts())
        self.assertFalse(self.scr.demo)
        self.assertEqual(self.scr.mode, MODE_VISUAL)

    def test_demo_visual_perf_and_tooltip(self):
        self.scr.set_demo(True)
        self.root.update()
        self.assertEqual(self.scr.badge.cget("text"), "ДЕМО-ДАННЫЕ")
        self.assertEqual(self.scr.mode, MODE_VISUAL)
        # визуальный уровень — кластеры, не 1000 слов
        self.assertLess(len(self.scr.items), 250)
        self.assertGreater(len(self.scr.items), 5)
        t = time.perf_counter()
        for k in range(30):
            self.scr.step(t + k * 0.033)
            self.root.update_idletasks()
        p = self.scr.perf()
        self.assertLess(p["avg_ms"], 40.0, p)
        x, y = self.scr._screen_xy[0]
        i = self.scr.star_at(x, y)
        self.assertIsNotNone(i)
        tip = self.scr.tooltip_text(i)
        self.assertIn("яркость", tip)
        self.assertFalse((self.dir / "lab.json").exists())   # демо ничего не пишет

    def test_work_mode_zoom_and_back(self):
        self.scr.set_demo(True)
        self.root.update()
        # берём первый кластер и входим в фрагмент
        cluster = next(n for n in self.scr.graph.nodes if n["kind"] == "cluster")
        self.scr._load_fragment(cluster["group"])
        self.root.update()
        self.assertEqual(self.scr.mode, MODE_WORK)
        self.assertGreater(self.scr.zoom, 1.0)
        self.assertTrue(any(n["group"] == cluster["group"] for n in self.scr.graph.nodes))
        self.scr.back_to_visual()
        self.root.update()
        self.assertEqual(self.scr.mode, MODE_VISUAL)
        self.assertEqual(self.scr.zoom, 1.0)

    def test_ctrl_wheel_zooms_without_reload(self):
        self.scr.set_demo(True)
        self.root.update()
        n0 = len(self.scr.graph.nodes)
        z0 = self.scr.zoom
        # имитация Ctrl+Wheel вверх
        ev = types.SimpleNamespace(state=0x4, delta=120, num=0, x=200, y=150)
        self.assertEqual(self.scr._on_wheel(ev), "break")
        self.assertGreater(self.scr.zoom, z0)
        self.assertEqual(len(self.scr.graph.nodes), n0)  # без перезагрузки данных
        # без Ctrl — не зумим
        z1 = self.scr.zoom
        self.assertIsNone(self.scr._on_wheel(types.SimpleNamespace(state=0, delta=120, num=0, x=200, y=150)))
        self.assertEqual(self.scr.zoom, z1)
        self.scr.reset_view()
        self.assertAlmostEqual(self.scr.zoom, self.scr._view_home[0], places=3)

    def test_orbit_drag_vs_click_and_selection(self):
        self.scr.set_demo(True)
        self.root.update()
        cluster = next(n for n in self.scr.graph.nodes if n["kind"] == "cluster")
        self.scr._load_fragment(cluster["group"])
        self.root.update()
        yaw0 = self.scr.yaw
        # drag: орбита, не выбор
        self.scr._on_press(types.SimpleNamespace(x=100, y=100))
        self.scr._on_drag(types.SimpleNamespace(x=100 + DRAG_CLICK_PX + 20, y=110))
        self.scr._on_release(types.SimpleNamespace(x=140, y=110))
        self.assertNotEqual(self.scr.yaw, yaw0)
        self.assertIsNone(self.scr.selected_id)
        # короткий клик по звезде → выбор + 1-hop
        i = 0
        x, y = self.scr._screen_xy[i]
        nid = self.scr.graph.nodes[i]["id"]
        self.scr._on_press(types.SimpleNamespace(x=x, y=y))
        self.scr._on_release(types.SimpleNamespace(x=x, y=y))
        # after(1) в select_star — дождёмся без mainloop
        deadline = time.time() + 1.0
        while self.scr._selection is None and time.time() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.scr.selected_id, nid)
        self.assertIsNotNone(self.scr._selection)
        self.assertEqual(self.scr._selection["selected"]["detail_level"], "full")
        # кэш: повторный выбор без новой сборки
        self.scr._selection_cache[nid]["cached"] = True
        self.scr.select_star(nid)
        self.assertTrue(self.scr._selection.get("cached"))
        # смена выбора отменяет устаревший token
        tok = self.scr._selection_token
        other = next(n["id"] for n in self.scr.graph.nodes if n["id"] != nid)
        self.scr.select_star(other)
        self.assertGreater(self.scr._selection_token, tok)

    def test_real_data_writes_only_own_seen_file(self):
        _write(self.dir, "english.json", {"words": {"case": {"known": True, "known_at": _day(1)}}})
        self.scr.reload()
        # визуальный: одно слово → один кластер (или одиночный узел-кластер)
        self.assertEqual(len(self.scr.items), 1)
        seen = json.loads((self.dir / "lab.json").read_text(encoding="utf-8"))
        self.assertEqual(len(seen["seen"]), 1)
        self.assertEqual(self.scr.fliers, [])                # первый визит — без «ливня»
        _write(self.dir, "english.json", {"words": {"case": {"known": True}, "time": {"known": True}}})
        self.scr._full_cache = None
        self.scr.reload()
        # новая звезда/кластер может влететь
        self.assertGreaterEqual(len(self.scr.items), 1)

    def test_loop_stops_when_hidden(self):
        self.scr.set_demo(True)
        self.scr.start()
        self.app.current = "bridge"
        self.scr._tick()
        self.assertIsNone(self.scr._job)

    def test_entity_items_drawn(self):
        self.scr.set_demo(True)
        self.root.update()
        self.assertGreaterEqual(len(self.scr._entity_items), 4)
        self.assertGreater(len(self.scr.bg_items), 0)


class LabCockpitTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from stamina import pilots
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        os.environ.setdefault("APPDATA", self._tmp)
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.app.update()

    def tearDown(self):
        from stamina import pilots
        self.app.destroy()
        pilots.reset_root()

    def test_zone_in_menu_and_opens(self):
        keys = [s for s, _ in self.app.SCREENS]
        self.assertIn("lab", keys)
        self.assertEqual(keys.index("lab"), keys.index("settings") - 1)
        self.assertIn("lab", self.app.nav_buttons)
        scr = self.app._ensure_screen("lab")
        self.assertIsNotNone(scr)
        self.app.show("lab")
        self.app.update()
        self.assertEqual(self.app.current, "lab")
