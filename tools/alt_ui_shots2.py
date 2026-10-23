"""Скриншоты alt UI при заданном размере: настройки (секции), ящик/подменю,
раскрытые выпадающие списки «⋯ ЕЩЁ». Данные пилота не трогаем (APPDATA → temp).
python tools/alt_ui_shots2.py SKIN WxH"""
import os, sys, tempfile
try:
    import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="stamina_alt_")
sys.path.insert(0, os.getcwd())
skin, size = sys.argv[1], sys.argv[2]
from stamina import storage
storage.DEFAULT_SETTINGS.update(ui_layout="alt", skin=skin, living_space="off", idle_minutes=0)
from stamina import alt_ui
from stamina.cockpit import Cockpit
from PIL import ImageGrab
app = Cockpit()
app.geometry(f"{size}+10+10")
OUT = "screenshots"
os.makedirs(OUT, exist_ok=True)


def grab(name):
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True).save(
        f"{OUT}/alt_{skin}_{size}_{name}.png")


def rows(w):
    out = []
    for c in w.winfo_children():
        r = getattr(c, "_alt_row", None)
        if r is not None and r.more.winfo_ismapped():
            out.append(r)
        out += rows(c)
    return out


def popup_shot(name):
    scr = app.screens[app.current]
    rs = rows(scr) or rows(app)
    if not rs:
        print("нет свёрнутых рядов", name); return
    rs[0].popup()
    def done():
        grab(name)
        if alt_ui.DropList.current is not None:
            alt_ui.DropList.current.close()
        else:
            print("список не открылся", name)
    app.after(700, done)


def settings(scroll):
    app.show("settings")
    vp = getattr(app, "_alt_view", None)
    if vp is not None:
        vp.canvas.yview_moveto(scroll)


steps = [("settings_top", lambda: settings(0.0), False),
         ("settings_mid", lambda: settings(0.45), False),
         ("settings_end", lambda: settings(1.0), False),
         ("settings_collapsed", lambda: (settings(0.0), [app.screens["settings"]._alt_set_open(k, False, save=False)
                                                       for k in ("systems", "more")]), False),
         ("drawer", lambda: (app.show_zone("bridge"), alt_ui.toggle_drawer(app, True)), False),
         ("bridge_dropdown", lambda: (alt_ui.toggle_drawer(app, False), app.show_zone("bridge")), True),
         ("english_dropdown", lambda: app.show_zone("english"), True),
         ("orion_dropdown", lambda: app.show_zone("orion"), True),
         ("radio", lambda: app.show_zone("radio"), False)]


def step(i=0):
    if i >= len(steps):
        print("SHOTS OK", skin, size); os._exit(0)
    name, act, pop = steps[i]
    try:
        act()
    except Exception as e:  # noqa: BLE001
        print("ERR", name, e)
    def after():
        if pop:
            popup_shot(name)
        else:
            grab(name)
        app.after(1300 if pop else 400, lambda: step(i + 1))
    app.after(1600, after)


app.after(2500, step)
app.after(90000, lambda: os._exit(3))
app.mainloop()
