"""Аудит выпадающих списков и навигационных рядов: python tools/dropdown_audit.py LAYOUT SKIN OUT [WxH]

Для каждого отсека (и вкладок английского): скриншот; каждый сворачивающий ряд
(_alt_compactor) — щелчок по «▾/⋯ ЕЩЁ» → всплывающий список должен быть отображён,
видим и лежать на мониторе якоря; ни один ряд/столбец навигационных кнопок не длиннее
MAX_NAV видимых кнопок. Временный APPDATA. Итог — JSON в OUT.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MAX_NAV = 6


def main() -> None:
    layout, skin, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    size = sys.argv[4] if len(sys.argv) > 4 else "1280x720"
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    tmp = tempfile.mkdtemp(prefix="stamina_dd_")
    os.environ["APPDATA"] = tmp
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp) / "Stamina")
    storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
    from PIL import ImageGrab
    from stamina import alt_ui, monitors
    from stamina.cockpit import Cockpit
    from stamina.hud import HudButton
    app = Cockpit()
    errors: list[str] = []
    app.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a)))
    app.geometry(f"{size}+0+0")
    app.attributes("-topmost", True)
    out.mkdir(parents=True, exist_ok=True)

    def pump(sec=0.4):
        t = time.time() + sec
        while time.time() < t:
            app.update()
            time.sleep(0.02)

    def walk(w):
        for k in w.winfo_children():
            yield k
            yield from walk(k)

    def visible(w) -> bool:
        try:
            if not w.winfo_viewable():
                return False
            x, y = w.winfo_rootx(), w.winfo_rooty()
            ax, ay = app.winfo_rootx(), app.winfo_rooty()
            return ax <= x < ax + app.winfo_width() and ay <= y < ay + app.winfo_height()
        except Exception:  # noqa: BLE001
            return False

    def nav_runs(scr) -> int:
        """Самый длинный ряд/столбец видимых кнопок-«вкладок» у одного родителя."""
        best = 0
        for parent in [scr, *walk(scr)]:
            try:
                kids = [k for k in parent.winfo_children() if isinstance(k, HudButton) and visible(k)]
            except Exception:  # noqa: BLE001
                continue
            best = max(best, len(kids))
        return best

    trace: list = []
    _init, _close = alt_ui.DropList.__init__, alt_ui.DropList.close

    def init_spy(self, *a, **k):
        trace.append("INIT")
        _init(self, *a, **k)

    def close_spy(self):
        trace.append("CLOSE<" + "/".join(f.name for f in traceback.extract_stack()[-4:-1]) + ">")
        _close(self)
    alt_ui.DropList.__init__, alt_ui.DropList.close = init_spy, close_spy
    _press, _rel = HudButton._on_press, HudButton._on_release

    def press_spy(self, e):
        trace.append(f"P{'m' if getattr(self, '_alt_more', False) else '?'}")
        _press(self, e)

    def rel_spy(self, e):
        trace.append(f"R{'m' if getattr(self, '_alt_more', False) else '?'}:{self._pressed}:{e.x},{e.y}/{self.winfo_width()}x{self.winfo_height()}")
        _rel(self, e)
    HudButton._on_press, HudButton._on_release = press_spy, rel_spy
    _rs = alt_ui.refresh_screen

    def rs_spy(a):
        trace.append("REFRESH")
        _rs(a)
    alt_ui.refresh_screen = rs_spy

    def real_click(w) -> None:
        import ctypes
        x = w.winfo_rootx() + w.winfo_width() // 2
        y = w.winfo_rooty() + w.winfo_height() // 2
        u = ctypes.windll.user32
        u.SetCursorPos(x, y)
        pump(0.1)
        under = app.winfo_containing(x, y)
        trace.append(f"under={'MORE' if under is w else under}")
        u.mouse_event(2, 0, 0, 0, 0)
        pump(0.05)
        u.mouse_event(4, 0, 0, 0, 0)
        for _ in range(12):
            pump(0.05)
            dl = alt_ui.DropList.current
            trace.append("O" if dl is not None else "-")

    rows = []
    zones = [s[0] for s in app.SCREENS]
    for zone in zones:
        targets = [(zone, None)]
        for name, sub in targets:
            rec = {"zone": name, "sub": sub, "dropdowns": [], "max_nav": 0}
            try:
                app.show(name)
                pump(1.2)
                scr = app.screens.get(name)
                if scr is None:
                    rec["error"] = "нет экрана"
                    rows.append(rec)
                    continue
                if name == "english":
                    t0 = time.time()
                    while not getattr(scr, "_built", False) and time.time() - t0 < 60:
                        pump(0.3)
                    pump(1.0)
                ImageGrab.grab((app.winfo_rootx(), app.winfo_rooty(), app.winfo_rootx() + app.winfo_width(),
                                app.winfo_rooty() + app.winfo_height())).save(out / f"dd_{layout}_{skin}_{name}.png")
                rec["max_nav"] = nav_runs(scr)
                comps = []
                for w in [app, *walk(app)]:
                    c = getattr(w, "_alt_row", None)
                    if c is not None and c not in comps:
                        comps.append(c)
                for c in comps:
                    more = getattr(c, "more", None)
                    d = {"hidden": len(getattr(c, "hidden", []) or []), "more_visible": bool(more and visible(more))}
                    if d["more_visible"]:
                        # кнопка видна, только если щелчок по её центру попадает именно в неё
                        # (не закрыта соседней страницей, не прокручена за край)
                        mx = more.winfo_rootx() + more.winfo_width() // 2
                        my = more.winfo_rooty() + more.winfo_height() // 2
                        d["more_visible"] = app.winfo_containing(mx, my) is more
                    if more is not None and d["more_visible"]:
                        try:
                            trace.clear()
                            real_click(more)            # настоящий щелчок мыши, как у пилота
                            d["trace"] = " ".join(trace)
                        except Exception:  # noqa: BLE001
                            d["invoke_error"] = traceback.format_exc()[-300:]
                        pump(0.4)
                        dl = alt_ui.DropList.current
                        ok = False
                        if dl is not None:
                            try:
                                ok = bool(dl.winfo_exists() and dl.winfo_ismapped() and dl.winfo_viewable())
                                cx, cy = dl.winfo_rootx() + 5, dl.winfo_rooty() + 5
                                d["on_monitor"] = monitors.on_some_monitor(cx, cy) is not False
                                d["items"] = len(dl.items)
                                ImageGrab.grab(all_screens=True).crop((app.winfo_rootx(), app.winfo_rooty(),
                                    app.winfo_rootx() + app.winfo_width(), app.winfo_rooty() + app.winfo_height())
                                ).save(out / f"dd_{layout}_{skin}_{name}_open{len(rec['dropdowns'])}.png")
                                dl.close()
                            except Exception:  # noqa: BLE001
                                d["dl_error"] = traceback.format_exc()[-300:]
                        d["popup_ok"] = ok
                        pump(0.2)
                    rec["dropdowns"].append(d)
            except Exception:  # noqa: BLE001
                rec["error"] = traceback.format_exc()[-500:]
            rows.append(rec)
    rep = {"layout": layout, "skin": skin, "size": size, "rows": rows, "errors": errors}
    (out / f"dd_{layout}_{skin}_{size}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    app.destroy()
    os._exit(0)


if __name__ == "__main__":
    main()
