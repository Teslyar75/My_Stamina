"""Скриншоты кабины для скина и вида: python tools/skin_shots.py SKIN LAYOUT OUTDIR [экраны…]

Временный APPDATA — данные пилота не трогаются. Для сравнения «до/после» контраста.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    skin, layout, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    names = sys.argv[4:] or ["bridge", "missions", "settings"]
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    tmp = tempfile.mkdtemp(prefix="stamina_shot_")
    os.environ["APPDATA"] = tmp
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp) / "Stamina")
    storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
    from PIL import ImageGrab
    from stamina.cockpit import Cockpit
    app = Cockpit()
    app.geometry("1280x720+0+0")
    out.mkdir(parents=True, exist_ok=True)
    for n in names:
        app.show(n)
        app.lift()
        app.attributes("-topmost", True)
        for _ in range(5):
            app.update()
            app.after(120)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height())).save(out / f"{skin}_{layout}_{n}.png")
    app.destroy()
    os._exit(0)


if __name__ == "__main__":
    main()
