"""Смоук + скриншоты ALT UI: данные пилота не трогаем (APPDATA -> временная папка)."""
import os, sys, tempfile
try:
    import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
tmp = tempfile.mkdtemp(prefix="stamina_alt_")
os.environ["APPDATA"] = tmp
sys.path.insert(0, os.getcwd())
skin, layout = sys.argv[1], sys.argv[2]
from stamina import storage
storage.DEFAULT_SETTINGS.update(ui_layout=layout, skin=skin, living_space="off", idle_minutes=0)
from stamina.cockpit import Cockpit
from PIL import ImageGrab
app = Cockpit()
app.geometry("1440x800+10+10")
zones = ["bridge", "speedread", "radio", "orion", "settings"]
os.makedirs("screenshots", exist_ok=True)
def step(i=0):
    if i > 0:
        app.update()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True).save(
            f"screenshots/alt_ui_{layout}_{skin}_{zones[i-1]}.png")
    if i >= len(zones):
        print("SMOKE OK", skin, layout); app._on_close() if hasattr(app, "_on_close") else app.destroy(); return
    if zones[i] == "settings":
        app.show("settings"); app.screens["settings"].show_tab("skins")
    else:
        app.show_zone(zones[i])
    app.after(1500, lambda: step(i + 1))
app.after(2500, step)
app.after(40000, lambda: os._exit(3))
app.mainloop()
