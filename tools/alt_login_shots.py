"""Скриншоты окна входа: 2 скина × 2 варианта (КЛАССИКА / ПУЛЬТ-КАБИНА) при WxH.
Данные пилота не трогаем (APPDATA → temp). python tools/alt_login_shots.py [WxH]"""
import os, sys, tempfile
try:
    import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="stamina_login_")
sys.path.insert(0, os.getcwd())
size = sys.argv[1] if len(sys.argv) > 1 else "1280x720"
import tkinter as tk
from PIL import ImageGrab
from stamina import pilots, theme
from stamina.pilot_screens import LoginScreen
for cs in ("ORION", "VEGA"):
    pilots.create(cs)
pid = pilots.pilots()[0]["id"]
root = tk.Tk()
theme.load_theme("spaceship", apply_ui=True, root=root)
root.geometry(f"{size}+10+10")
os.makedirs("screenshots", exist_ok=True)
combos = [("spaceship", "classic"), ("spaceship", "alt"), ("steampunk", "classic"), ("steampunk", "alt"),
          ("spaceship", "classic")]   # последний — назад со Стимпанка: проверка, что не осталось кусков


def page():
    return next(w for w in _walk(root) if isinstance(w, LoginScreen))


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def step(i=0):
    if i >= len(combos):
        print("LOGIN SHOTS OK"); os._exit(0)
    sk, lay = combos[i]
    page()._pick_layout(lay)
    root.update()
    page()._preview_skin(sk)

    def shot():
        root.update()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        tail = "_back" if i == len(combos) - 1 else ""
        ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True).save(
            f"screenshots/login_{sk}_{lay}_{size}{tail}.png")
        root.after(200, lambda: step(i + 1))
    root.after(1800, shot)


# Тот же путь, что у ярлыка: настоящий run_login (с пересборкой окна при смене скина)
from stamina.pilot_screens import run_login  # noqa: E402
root.after(1500, step)
root.after(60000, lambda: os._exit(3))
run_login(root)
