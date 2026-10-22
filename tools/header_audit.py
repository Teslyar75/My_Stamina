"""Аудит ПРАВИЛ НАВИГАЦИИ alt: python tools/header_audit.py SKIN OUT [WxH] [SCALE]

В каждом отсеке (nav.ZONE_ORDER) и листах мостика: кнопка «ОБЗОР ▾» видна, подпись одна,
стоит сразу справа от заголовка (отступ SLOT_GAP), целиком в окне; меню открывается и
отмечает ✓ текущий экран. Временный APPDATA. Итог - OUT/header_SKIN_WxH_SCALE.json + png."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    skin, out = sys.argv[1], Path(sys.argv[2])
    size = sys.argv[3] if len(sys.argv) > 3 else "1280x720"
    scale = sys.argv[4] if len(sys.argv) > 4 else "M"
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    tmp = tempfile.mkdtemp(prefix="stamina_hd_")
    os.environ["APPDATA"] = tmp
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp) / "Stamina")
    storage.DEFAULT_SETTINGS.update(ui_layout="alt", skin=skin, ui_scale=scale, living_space="off", idle_minutes=0)
    from PIL import ImageGrab
    from stamina import alt_ui, nav
    from stamina.cockpit import Cockpit
    app = Cockpit()
    errors: list[str] = []
    app.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a))[-500:])
    app.geometry(f"{size}+0+0")
    app.attributes("-topmost", True)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{skin}_{size}_{scale}"

    def pump(sec=0.4):
        t = time.time() + sec
        while time.time() < t:
            app.update()
            time.sleep(0.02)

    pump(2)
    rows = []
    names = list(dict.fromkeys([*nav.ZONE_ORDER, *[k for k, _ in nav.BRIDGE_LEAVES]]))
    for name in names:
        app.show(name)
        pump(1.2)
        ax, ay, aw = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width()
        t, b = app._alt_title, app._alt_slot_btn
        d = {"zone": name, "text": b._text, "label_ok": b._text == alt_ui.overview_label(),
             "visible": bool(b.winfo_viewable()),
             "title_right": t.winfo_rootx() + t.winfo_width() - ax,
             "x": b.winfo_rootx() - ax, "y": b.winfo_rooty() - ay, "w": b.winfo_width()}
        d["gap"] = d["x"] - d["title_right"]
        d["in_window"] = d["x"] >= 0 and d["x"] + d["w"] <= aw
        ents = alt_ui.overview_entries(app)
        d["entries"] = [e[0] for e in ents]
        d["checked"] = [e[0] for e in ents if e[2]]
        b.invoke()
        pump(0.5)
        dl = alt_ui.DropList.current
        d["menu_open"] = dl is not None and bool(dl.winfo_viewable())
        ImageGrab.grab((ax, ay, ax + aw, ay + app.winfo_height()), all_screens=True).save(out / f"header_{tag}_{name}.png")
        if dl is not None:
            dl.destroy()
            alt_ui.DropList.current = None
        pump(0.2)
        d["errors"] = list(errors)
        errors.clear()
        rows.append(d)
    res = {"skin": skin, "size": size, "scale": scale, "gap_px": alt_ui.px(alt_ui.SLOT_GAP), "rows": rows}
    (out / f"header_{tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    app.destroy()


if __name__ == "__main__":
    main()
