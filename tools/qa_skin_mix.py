"""QA стабильности: смешение скинов, утечки таймеров/потоков/памяти, изоляция классики и alt.

    python tools/qa_skin_mix.py all [--rounds 3]       всё: окно входа + кабина 7 скинов × 2 вида
    python tools/qa_skin_mix.py login OUT.json [R]     окно входа: R кругов по всем скинам × 2 вариантам
    python tools/qa_skin_mix.py cockpit LAYOUT SKIN OUT.json   кабина: все отсеки, проверка после каждого

«Чужой цвет» — цвет из палитры другого скина, которого нет в палитре текущего.
Проверяются фон/текст/рамки всех виджетов и fill/outline всех фигур на холстах,
шрифты (семейства других скинов) и обои/сцены alt (профиль = текущий скин).
Данные пилота не трогаем: APPDATA → временная папка, у каждого прогона своя.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_FONTS = {"Segoe UI", "Consolas", "Courier New", "Arial", "TkDefaultFont"}  # запасные шрифты Windows
NEUTRAL = {"#000000", "#FFFFFF", "#C9D6E3", "#D08A4E"}
OPTS = ("bg", "fg", "highlightbackground", "highlightcolor", "activebackground", "activeforeground",
        "selectcolor", "insertbackground", "troughcolor")


def _tmp_appdata() -> str:
    tmp = tempfile.mkdtemp(prefix="stamina_qa_")
    os.environ["APPDATA"] = tmp
    sys.path.insert(0, ROOT)
    from pathlib import Path
    from stamina import pilots
    pilots.reset_root(Path(tmp) / "Stamina")
    return tmp


def palettes() -> dict[str, set[str]]:
    from stamina import theme
    out = {}
    for m in theme.list_themes():
        cols = (m["data"].get("colors") or {}).values()
        out[m["id"]] = {str(c).upper() for c in cols if str(c).startswith("#")}
    return out


def font_families(root) -> dict[str, set[str]]:
    from stamina import theme
    cur = theme.theme_id()
    out = {}
    for m in theme.list_themes():
        theme.load_theme(m["id"], apply_ui=False, root=root)
        out[m["id"]] = {theme.HUD_FAMILY, theme.MONO_FAMILY}
    theme.load_theme(cur, apply_ui=False, root=root)
    return out


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def colors_and_fonts(root):
    cols, fonts = {}, {}
    for w in walk(root):
        for o in OPTS:
            try:
                v = str(w.cget(o)).upper()
            except Exception:  # noqa: BLE001
                continue
            if v.startswith("#"):
                cols.setdefault(v, str(w))
        try:
            f = w.cget("font")
            fam = w.tk.call("font", "actual", f, "-family")
            fonts.setdefault(str(fam), str(w))
        except Exception:  # noqa: BLE001
            pass
        if w.winfo_class() == "Canvas":
            for it in w.find_all():
                for o in ("fill", "outline"):
                    try:
                        v = str(w.itemcget(it, o)).upper()
                    except Exception:  # noqa: BLE001
                        continue
                    if v.startswith("#"):
                        cols.setdefault(v, f"{w}#{it}")
    return cols, fonts


def _ratio(a: str, b: str) -> float:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from contrast_audit import ratio
    return ratio(a, b)


def _hex(w, c: str) -> str | None:
    try:
        r, g, b = (v // 257 for v in w.winfo_rgb(c))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:  # noqa: BLE001
        return None


def low_contrast(root, need: float = 4.5, large: float = 3.0) -> list:
    """Реальные пары «текст — фон» из настроенных виджетов (ловит и цвета мимо токенов).

    Крупный текст (≥14 pt жирный или ≥18 pt) — порог 3:1. Холсты: text-элементы против фона холста.
    """
    import tkinter.font as tkf
    out = []
    for w in walk(root):
        try:
            if not w.winfo_ismapped():
                continue
            cls = w.winfo_class()
            if cls in ("Label", "Button", "Checkbutton", "Radiobutton", "Entry", "Text", "Listbox", "Menubutton"):
                txt = w.cget("text") if cls not in ("Entry", "Text", "Listbox") else "x"
                if not str(txt).strip():
                    continue
                fg, bg = _hex(w, w.cget("fg")), _hex(w, w.cget("bg"))
                f = tkf.Font(font=w.cget("font"))
                big = abs(f.actual("size")) >= 18 or (abs(f.actual("size")) >= 14 and f.actual("weight") == "bold")
                if fg and bg and _ratio(fg, bg) < (large if big else need):
                    out.append((str(w), str(txt)[:30], fg, bg, round(_ratio(fg, bg), 2)))
            elif cls == "Canvas":
                bg = _hex(w, w.cget("bg"))
                for it in w.find_all():
                    if w.type(it) != "text" or not str(w.itemcget(it, "text")).strip():
                        continue
                    fg = _hex(w, w.itemcget(it, "fill") or "black")
                    if fg and bg and _ratio(fg, bg) < large:   # на холстах часто крупные надписи и подложки
                        out.append((f"{w}#{it}", w.itemcget(it, "text")[:30], fg, bg, round(_ratio(fg, bg), 2)))
        except Exception:  # noqa: BLE001
            continue
    return out


def foreign(root, skin, pals, fams) -> dict:
    cur = pals.get(skin, set())
    other = set().union(*(p for k, p in pals.items() if k != skin)) - cur - NEUTRAL
    other_f = set().union(*(f for k, f in fams.items() if k != skin)) - fams.get(skin, set()) - SYSTEM_FONTS
    cols, fonts = colors_and_fonts(root)
    return {"colors": {c: w for c, w in cols.items() if c in other},
            "fonts": {f: w for f, w in fonts.items() if f in other_f},
            "contrast": low_contrast(root)}


def rss_mb() -> float:
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                        ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize / 1048576
    except Exception:  # noqa: BLE001
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


# --------------------------------------------------------------------- окно входа
def run_login_qa(out_path: str, rounds: int = 3) -> None:
    _tmp_appdata()
    import tkinter as tk
    from stamina import alt_ui, pilots, theme
    from stamina.pilot_screens import LoginScreen, run_login
    for cs in ("ORION", "VEGA"):
        pilots.create(cs)
    root = tk.Tk()
    errors: list[str] = []
    root.report_callback_exception = lambda *a: errors.append("".join(__import__("traceback").format_exception(*a)))
    theme.load_theme("spaceship", apply_ui=True, root=root)
    root.geometry("1280x720+10+10")
    pals = palettes()
    fams = font_families(root)
    skins = [m["id"] for m in theme.list_themes()]
    combos = [(s, v) for _ in range(rounds) for s in skins for v in ("classic", "alt")]
    rep = {"switches": [], "errors": errors}

    def page():
        return next(w for w in walk(root) if isinstance(w, LoginScreen))

    def step(i=0):
        if i >= len(combos):
            rep["threads"] = [t.name for t in threading.enumerate()]
            json.dump(rep, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            page().on_exit()
            return
        sk, lay = combos[i]
        page()._pick_layout(lay)
        root.update()
        page()._preview_skin(sk)

        def check():
            root.update()
            p = page()
            stages = [w for w in walk(root) if isinstance(w, alt_ui.LoginStage)]
            prof = alt_ui.profile_id(sk)
            bad_stage = [s.profile for s in stages if s.shown and s.profile != prof]
            rep["switches"].append({
                "skin": sk, "layout": lay, "ok_pair": (p._skin_id, p._layout_id, theme.theme_id()) == (sk, lay, sk),
                "logins": sum(isinstance(w, LoginScreen) for w in walk(root)), "stages": len(stages),
                "bad_stage": bad_stage, "after": len(root.tk.call("after", "info")),
                "threads": threading.active_count(), "rss": round(rss_mb(), 1),
                "foreign": foreign(root, sk, pals, fams)})
            root.after(10, lambda: step(i + 1))
        root.after(250, check)

    root.after(800, step)
    root.after(240000, lambda: os._exit(3))
    run_login(root)
    root.destroy()


# --------------------------------------------------------------------- кабина
def run_cockpit_qa(layout: str, skin: str, out_path: str) -> None:
    tmp = _tmp_appdata()
    from stamina import storage
    storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
    import tkinter as tk
    try:
        from stamina import alt_ui
    except ImportError:          # база до ALT UI (сравнение классики с master)
        alt_ui = None
    from stamina.cockpit import Cockpit
    app = Cockpit()
    errors: list[str] = []
    app.report_callback_exception = lambda *a: errors.append("".join(__import__("traceback").format_exception(*a)))
    app.geometry("1280x720+0+0")
    app.update()
    pals = palettes()
    fams = font_families(app)
    names = list(app.screens) + [n for n in getattr(app, "_factories", {}) if n not in app.screens]
    rep = {"layout": layout, "skin": skin, "screens": {}, "errors": errors}
    for n in names:
        try:
            app.show(n)
            app.update()
            time.sleep(0.05)
            app.update()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{n}: {exc!r}")
            continue
        f = foreign(app, skin, pals, fams)
        wall = getattr(app, "_alt_wall", None)
        rep["screens"][n] = {"foreign": f, "wall_profile": getattr(wall, "profile", None)}
    # изоляция: в классике нет ни одного объекта alt
    alt_classes = () if alt_ui is None else tuple(c for c in vars(alt_ui).values() if isinstance(c, type) and issubclass(c, tk.Misc)
                        and c.__module__ == alt_ui.__name__)
    rep["alt_widgets"] = 0 if not alt_classes else sum(isinstance(w, alt_classes) for w in walk(app))
    rep["alt_attrs"] = sorted(a for a in vars(app) if a.startswith("_alt") and getattr(app, a) is not None)
    rep["alt_compactors"] = sum(1 for w in walk(app) if getattr(w, "_alt_compactor", None) is not None)
    rep["droplist_open"] = alt_ui is not None and alt_ui.DropList.current is not None
    rep["profile_expected"] = alt_ui.profile_id(skin) if alt_ui else None
    rep["after"] = len(app.tk.call("after", "info"))
    rep["rss"] = round(rss_mb(), 1)
    t0 = time.time()
    try:
        app._save_all()
    except Exception:  # noqa: BLE001
        pass
    app.destroy()
    rep["exit_s"] = round(time.time() - t0, 2)
    rep["threads_after_exit"] = [t.name for t in threading.enumerate() if t is not threading.main_thread()
                                 and not t.daemon]
    log = os.path.join(tmp, "Stamina", "debug.log")
    rep["debug_log_tracebacks"] = (open(log, encoding="utf-8", errors="replace").read().count("Traceback")
                                   if os.path.exists(log) else 0)
    json.dump(rep, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# --------------------------------------------------------------------- сводка
def run_all(rounds: int) -> int:
    sys.path.insert(0, ROOT)
    from stamina import theme
    skins = [m["id"] for m in theme.list_themes()]
    tmpd = tempfile.mkdtemp(prefix="stamina_qa_out_")
    py = sys.executable
    bad = 0
    lj = os.path.join(tmpd, "login.json")
    r = subprocess.run([py, __file__, "login", lj, str(rounds)], cwd=ROOT, timeout=400,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.exists(lj):
        print("LOGIN: нет отчёта", r.returncode, r.stderr[-800:])
        return 1
    L = json.load(open(lj, encoding="utf-8"))
    sw = L["switches"]
    mix = [s for s in sw if s["foreign"]["colors"] or s["foreign"]["fonts"] or s["bad_stage"]]
    lc = {tuple(x[1:4]) + (s["skin"], s["layout"]) for s in sw for x in s["foreign"]["contrast"]}
    print(f"LOGIN: низкий контраст — {len(lc)} пар")
    for x in sorted(lc)[:12]:
        print("   контраст:", x)
    bad += len(lc)
    wrong = [s for s in sw if not s["ok_pair"] or s["logins"] != 1 or s["stages"] != 1]
    aft = [s["after"] for s in sw]
    rss = [s["rss"] for s in sw]
    print(f"LOGIN: переключений {len(sw)}; смешение {len(mix)}; неверная пара/дубли {len(wrong)}; "
          f"ошибок Tk {len(L['errors'])}; таймеры {min(aft)}..{max(aft)}; "
          f"потоки {min(s['threads'] for s in sw)}..{max(s['threads'] for s in sw)}; "
          f"память {rss[0]}→{rss[len(rss) // 2]}→{rss[-1]} МБ; выход {r.returncode}")
    for s in mix[:5]:
        print("  смешение:", s["skin"], s["layout"], json.dumps(s["foreign"], ensure_ascii=False)[:300], s["bad_stage"])
    for e in L["errors"][:3]:
        print("  ошибка:", e[-400:])
    bad += len(mix) + len(wrong) + len(L["errors"]) + (r.returncode != 0)
    if max(rss) - rss[len(rss) // 2] > 40:
        print("  ВНИМАНИЕ: память растёт"); bad += 1
    for layout in ("classic", "alt"):
        for sk in skins:
            cj = os.path.join(tmpd, f"c_{layout}_{sk}.json")
            r = subprocess.run([py, __file__, "cockpit", layout, sk, cj], cwd=ROOT, timeout=300,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if not os.path.exists(cj):
                print(f"COCKPIT {layout} {sk}: нет отчёта, код {r.returncode}", r.stderr[-600:])
                bad += 1
                continue
            C = json.load(open(cj, encoding="utf-8"))
            mixs = {n: v["foreign"] for n, v in C["screens"].items() if v["foreign"]["colors"] or v["foreign"]["fonts"]}
            lcs = {tuple(x[1:]) for v in C["screens"].values() for x in v["foreign"]["contrast"]}
            if lcs:
                bad += 1
                print(f"CONTRAST {layout} {sk}: пар ниже нормы {len(lcs)}")
                for x in sorted(lcs, key=lambda x: x[3])[:8]:
                    print("   ", x)
            walls = {n: v["wall_profile"] for n, v in C["screens"].items()
                     if v["wall_profile"] not in (None, C["profile_expected"])}
            iso = (C["alt_widgets"] or C["alt_attrs"] or C["alt_compactors"]) if layout == "classic" else 0
            ok = not (mixs or walls or iso or C["errors"] or C["threads_after_exit"] or C["debug_log_tracebacks"]
                      or r.returncode)
            bad += not ok
            print(f"COCKPIT {layout:7} {sk:12} отсеков {len(C['screens'])}; смешение {len(mixs)}; обои чужие {len(walls)}; "
                  f"alt в классике {iso or 0}; ошибок {len(C['errors'])}; Traceback в debug.log {C['debug_log_tracebacks']}; "
                  f"потоки после выхода {len(C['threads_after_exit'])}; выход {C['exit_s']} с; "
                  f"память {C['rss']} МБ; {'OK' if ok else 'ПРОБЛЕМА'}")
            for n, v in list(mixs.items())[:3]:
                print("   ", n, json.dumps(v, ensure_ascii=False)[:300])
            for e in C["errors"][:2]:
                print("    ошибка:", e[-300:])
            if layout == "classic" and iso:
                print("    alt в классике:", C["alt_widgets"], C["alt_attrs"], C["alt_compactors"])
    print("ИТОГО:", "OK" if not bad else f"проблем {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "login":
        run_login_qa(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3)
        os._exit(0)
    elif mode == "cockpit":
        run_cockpit_qa(sys.argv[2], sys.argv[3], sys.argv[4])
        os._exit(0)
    else:
        rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 3
        raise SystemExit(run_all(rounds))
