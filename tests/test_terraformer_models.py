"""Модели роботов-терраформеров: состав, детали, рост по уровням, рендер."""
import os
import sys
import time

import pytest

from stamina import terraformer_models as tm


def test_twelve_robots_two_lines():
    assert len(tm.ROBOTS) == 12
    assert len(set(tm.ROBOT_IDS)) == 12
    lines = {r.line for r in tm.ROBOTS}
    assert lines == {"cefr", "freq"}
    assert [r.name for r in tm.ROBOTS if r.line == "cefr"] == ["A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"]
    assert [r.name for r in tm.ROBOTS if r.line == "freq"] == ["S-1000", "S-3000", "S-10K", "S-20K"]
    for r in tm.ROBOTS:
        assert r.caption and r.palette["core"]


def test_a1_has_shovel():
    parts = {p.part for p in tm.build("a1")}
    assert "shovel" in parts
    assert "probe" in parts


@pytest.mark.parametrize("rid", tm.ROBOT_IDS)
def test_every_robot_has_glowing_core(rid):
    cores = [p for p in tm.build(rid) if p.part == "core"]
    assert cores and all(p.emissive for p in cores)


@pytest.mark.parametrize("rid", tm.ROBOT_IDS)
def test_polygon_budget_and_geometry(rid):
    prims = tm.build(rid)
    assert 0 < tm.polygon_count(rid) <= 3500                 # плоский Canvas-рендер (запасной)
    assert tm.polygon_count(rid, "high") <= 7000             # гладкий рендер
    for p in prims:
        assert len(p.faces) == len(p.normals)
        for f in p.faces:
            assert len(f) >= 3 and all(0 <= i < len(p.verts) for i in f)
        for n in p.normals:
            assert abs(sum(c * c for c in n) - 1.0) < 1e-3


def test_signature_parts():
    want = {
        "a2": "drill", "b1_1": "scanner", "b1_2": "seed_pods", "b2_1": "solar",
        "b2_2": "atmo_vent", "c1": "drone_bay", "c2": "atmo_gen", "s1000": "seeder",
        "s3000": "hose", "s10k": "crane", "s20k": "forest",
    }
    for rid, part in want.items():
        assert part in {p.part for p in tm.build(rid)}, (rid, part)
    assert {"harvester", "cloud_seeder"} <= {p.part for p in tm.build("s10k")}
    assert "weather_tower" in {p.part for p in tm.build("s20k")}
    assert sum(1 for p in tm.build("c2") if p.part == "drone" and p.anim) >= 10


@pytest.mark.parametrize("line", ["cefr", "freq"])
def test_size_grows_with_level(line):
    rows = sorted((r for r in tm.ROBOTS if r.line == line), key=lambda r: r.level)
    heights = [tm.bounds(r.id)[1][1] for r in rows]
    assert heights == sorted(heights) and len(set(heights)) == len(heights), heights
    # и сложнее: у старшего больше граней, чем у младшего
    assert tm.polygon_count(rows[-1].id) > tm.polygon_count(rows[0].id)


def test_build_deterministic():
    for rid in tm.ROBOT_IDS:
        assert tm.build(rid) == tm.build(rid)
        assert tm.build(rid, "high") == tm.build(rid, "high")
    tm._built.cache_clear()
    a = tm.build("c2", "high")
    tm._built.cache_clear()
    assert tm.build("c2", "high") == a


def test_high_lod_is_smoother():
    for rid in ("a1", "s1000"):
        assert tm.polygon_count(rid, "high") > 1.5 * tm.polygon_count(rid)
    # у гладких деталей нормали углов отличаются от нормали грани, у брони — нет
    head = next(p for p in tm.build("a1", "high") if p.part == "head")
    assert any(c != head.normals[0] for c in head.cnormals[5])


def test_frame_polys_animated_and_sorted():
    p0 = tm.frame_polys("c2", tm.DEFAULT_YAW, tm.DEFAULT_PITCH, t=0.0)
    p1 = tm.frame_polys("c2", tm.DEFAULT_YAW, tm.DEFAULT_PITCH, t=2.0)
    assert p0 and p1
    assert p0 != p1                          # рой летит, ядро дышит
    assert p0[0][1] == "#05080c"             # тень — первой
    core = [f for f in tm.frame_polys("a1", 0.0, 0.0, t=0.0, parts=True) if f[3] == "core"]
    assert core                              # ядро видно спереди
    back = [f for f in tm.frame_polys("a1", 3.14159, 0.0, parts=True) if f[3] == "core"]
    assert len(back) < len(core)             # сзади видна лишь задняя крышка, её закрывает голова


def test_backface_culling_halves_faces():
    for rid in ("a1", "s20k"):
        drawn = len(tm.frame_polys(rid, 0.4, 0.3))
        assert drawn < tm.polygon_count(rid) * 0.7


def test_pan_and_zoom_move_image():
    def bbox(polys):
        xs = [v for c, _f, _o in polys for v in c[0::2]]
        return min(xs), max(xs)
    a = bbox(tm.frame_polys("b1_1", 0.0, 0.2, 1.0, (0.0, 0.0)))
    b = bbox(tm.frame_polys("b1_1", 0.0, 0.2, 1.0, (50.0, 0.0)))
    c = bbox(tm.frame_polys("b1_1", 0.0, 0.2, 2.0, (0.0, 0.0)))
    assert abs((b[0] - a[0]) - 50.0) < 1e-6
    assert (c[1] - c[0]) > 1.8 * (a[1] - a[0])


def test_orbit_view_uses_lab_math():
    from stamina import laboratory as lab
    v = tm.OrbitView()
    v.orbit(100, 0)
    assert v.yaw == pytest.approx(tm.DEFAULT_YAW + 100 * lab.ORBIT_SENS)
    v.orbit(0, -10_000)
    assert v.pitch == pytest.approx(lab.PITCH_MAX)
    v.zoom_at(1000.0, (10.0, 10.0), (100.0, 100.0))
    assert v.zoom == pytest.approx(lab.ZOOM_MAX)
    v.reset()
    assert (v.yaw, v.pitch, v.zoom, v.pan) == (tm.DEFAULT_YAW, tm.DEFAULT_PITCH, 1.0, (0.0, 0.0))


def _tk_root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("нет дисплея")
    tk = pytest.importorskip("tkinter")
    try:
        return tk, tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Tk недоступен: {e}")


def test_draw_on_canvas_fast():
    tk, root = _tk_root()
    try:
        cv = tk.Canvas(root, width=800, height=600)
        cv.pack()
        root.update()
        worst = 0.0
        for rid in tm.ROBOT_IDS:
            st = tm.draw(cv, rid, 0.3, 0.2, 1.2, (10.0, -5.0), 1.0)
            assert st["polys"] > 0 and st["total"] == tm.polygon_count(rid)
            assert len(cv.find_withtag("tf_robot")) == st["polys"]
            t0 = time.perf_counter()
            for i in range(5):
                tm.draw(cv, rid, 0.3 + i * 0.1, 0.2, 1.0, (0.0, 0.0), i * 0.05)
            worst = max(worst, (time.perf_counter() - t0) * 1000 / 5)
        assert worst < 120.0  # плоский запасной рендер; запас под медленный CI
        # Ctrl+колесо и ЛКМ-орбита через OrbitView
        v = tm.OrbitView()
        calls = []
        v.attach(cv, lambda: calls.append(1))
        ev = type("E", (), {"state": 0x0004, "num": 4, "delta": 0, "x": 400, "y": 300})()
        assert v.on_wheel(ev) == "break" and v.zoom > 1.0
        ev.state = 0
        assert v.on_wheel(ev) is None
        v.on_press(type("E", (), {"x": 100, "y": 100})())
        v.on_drag(type("E", (), {"x": 160, "y": 100})())
        v.on_release(None)
        assert v.yaw != tm.DEFAULT_YAW and len(calls) == 2
    finally:
        root.destroy()


# ─── гладкий рендер (numpy) ────────────────────────────────────────────────

def _tr():
    pytest.importorskip("numpy")
    from stamina import terraformer_render as tr
    return tr


def test_vector_projection_matches_lab_project_point():
    tr = _tr()
    import numpy as np
    from stamina import laboratory as lab
    rng = np.random.default_rng(7)
    pts = rng.uniform(-1.2, 1.2, size=(200, 3))
    for yaw, pitch, zoom in ((0.0, 0.0, 1.0), (-0.55, 0.22, 1.7), (2.6, -0.9, 0.6)):
        sx, sy, depth, _m = tr.project(pts, yaw=yaw, pitch=pitch, zoom=zoom, cx=320.0, cy=240.0, R=150.0,
                                       view_ox=12.0, view_oy=-7.0)
        for i in range(0, 200, 13):
            ex = lab.project_point(*pts[i], yaw=yaw, pitch=pitch, zoom=zoom, pan_x=0.0, pan_y=0.0,
                                   cx=320.0, cy=240.0, R=150.0, view_ox=12.0, view_oy=-7.0)
            assert (sx[i], sy[i], depth[i]) == pytest.approx(ex, abs=1e-6)


@pytest.mark.parametrize("rid", tm.ROBOT_IDS)
def test_smooth_render_frame(rid):
    tr = _tr()
    import numpy as np
    f = tr.render(rid, width=320, height=280, quality="live", t=0.4)
    im, (x, y) = f.image(0.7)
    assert im.mode == "RGBA" and im.width > 40 and im.height > 40
    assert 0 <= x < 320 and 0 <= y < 280
    a = np.asarray(im)
    assert (a[..., 3] == 255).sum() > 1500            # робот непрозрачен
    # светится голубое ядро: есть яркие пиксели с B > R
    rgb = a[..., :3].astype(int)
    assert ((rgb[..., 2] > 200) & (rgb[..., 2] > rgb[..., 0] + 40)).sum() > 10
    comp = f.composite("#0b1118")
    assert comp.size == (320, 280)


def test_smooth_render_deterministic_and_pulse():
    tr = _tr()
    import numpy as np
    a = np.asarray(tr.render("b1_1", width=200, height=200, quality="drag").image(0.5)[0])
    b = np.asarray(tr.render("b1_1", width=200, height=200, quality="drag").image(0.5)[0])
    assert (a == b).all()
    f = tr.render("b1_1", width=200, height=200, quality="live")
    lo = np.asarray(f.image(0.0)[0]).astype(int).sum()
    hi = np.asarray(f.image(1.0)[0]).astype(int).sum()
    assert hi > lo                                     # ядро «дышит» без перерендера


def test_smooth_drag_frame_fast():
    tr = _tr()
    import statistics
    worst = []
    for rid in ("c2", "s20k", "s3000"):
        tr.render(rid, width=700, height=600, quality="drag")
        ts = []
        for i in range(5):
            t0 = time.perf_counter()
            tr.render(rid, 0.2 * i, 0.2, width=700, height=600, quality="drag", t=i * 0.1).image(0.5)
            ts.append((time.perf_counter() - t0) * 1000)
        worst.append(statistics.median(ts))
    assert max(worst) < 60.0   # цель < 20 мс на обычной машине; запас под медленный CI


def test_viewer_on_canvas():
    tr = _tr()
    tk, root = _tk_root()
    try:
        cv = tk.Canvas(root, width=500, height=420, bg="#0b1118")
        cv.pack()
        root.update()
        v = tr.TerraformerViewer(cv, "c1")
        v.start()
        root.update()
        assert cv.find_withtag("tf_robot")
        assert v.smooth
        v.view.on_press(type("E", (), {"x": 100, "y": 100})())
        v._press(None)
        v.view.on_drag(type("E", (), {"x": 180, "y": 120})())
        assert v.last_ms > 0
        v._release(None)
        v.set_robot("s20k")
        root.update()
        ev = type("E", (), {"state": 0x0004, "num": 4, "delta": 0, "x": 250, "y": 200})()
        assert v.view.on_wheel(ev) == "break"
        v.stop()
    finally:
        root.destroy()


def test_viewer_canvas_fallback():
    tr = _tr()
    tk, root = _tk_root()
    try:
        cv = tk.Canvas(root, width=400, height=300)
        cv.pack()
        root.update()
        v = tr.TerraformerViewer(cv, "a1", smooth=False)
        v.redraw("full")
        assert len(cv.find_withtag("tf_robot")) > 50     # плоские полигоны
    finally:
        root.destroy()
