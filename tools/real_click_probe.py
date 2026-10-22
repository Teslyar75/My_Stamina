"""Real-mouse probe of «ОБЗОР ▾» in English, with a COPY of the user's settings.
python tools/real_click_probe.py SKIN OUTDIR [pick]  (APPDATA is copied to temp; original untouched)"""
import ctypes, ctypes.wintypes, json, os, shutil, sys, tempfile, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass
skin, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
real = Path(os.environ["APPDATA"]) / "Stamina"
tmp = Path(tempfile.mkdtemp(prefix="stamina_rc_")); shutil.copytree(real, tmp / "Stamina")
os.environ["APPDATA"] = str(tmp)
from stamina import pilots, storage
pilots.reset_root(tmp / "Stamina")
storage.reset_paths()
pj = tmp / "Stamina" / "pilots.json"
j = json.loads(pj.read_text(encoding="utf-8")); j["ask_on_start"] = False
for p_ in j.get("pilots", []): p_["locked"] = False  # copy only: skip PIN prompt
pj.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
pilots.activate(j["last_pilot"])
for f in (tmp / "Stamina").rglob("settings.json"):
    try:
        j = json.loads(f.read_text(encoding="utf-8")); j["skin"] = skin
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    except Exception: pass
from stamina.cockpit import Cockpit
from stamina import alt_ui
from PIL import ImageGrab
log = []
_close = alt_ui.DropList.close
def close(self):
    log.append({"t": round(time.time() - T0, 3), "close_by": [f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-6:-1]]})
    return _close(self)
alt_ui.DropList.close = close
app = Cockpit(); T0 = time.time()
errs = []; app.report_callback_exception = lambda *a: errs.append("".join(traceback.format_exception(*a))[-600:])
def pump(s):
    t = time.time() + s
    while time.time() < t: app.update(); time.sleep(0.01)
u = ctypes.windll.user32
clicks = []
def click(x, y):
    u.SetCursorPos(int(x), int(y)); pump(0.15)
    w = app.winfo_containing(int(x), int(y)); pt = ctypes.wintypes.POINT(); u.GetCursorPos(ctypes.byref(pt))
    clicks.append({"t": round(time.time() - T0, 3), "at": [int(x), int(y)], "cursor": [pt.x, pt.y], "widget": str(w)})
    u.mouse_event(2, 0, 0, 0, 0); pump(0.08); u.mouse_event(4, 0, 0, 0, 0)
def shot(name):
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True).save(out / f"{skin}_{COMP}_{name}.png")
pump(2.5); COMP = os.environ.get("COMP", "english"); app.show(COMP); pump(2)
app.lift(); app.focus_force(); pump(0.5)
b = app._alt_slot_btn
r = {"skin": skin, "win": [app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()],
     "settings": {k: getattr(getattr(app, "store", None), "settings", {}).get(k) for k in ("ui_layout", "ui_scale", "geometry", "skin")},
     "btn": [b.winfo_rootx(), b.winfo_rooty(), b.winfo_width(), b.winfo_height(), b._text], "title": app._alt_title.cget("text")}
click(b.winfo_rootx() + b.winfo_width() / 2, b.winfo_rooty() + b.winfo_height() / 2)
for t in (0.1, 0.6, 1.5):
    pump(t if t == 0.1 else t - 0.1 if t == 0.6 else 0.9)
    d = alt_ui.DropList.current
    r[f"open@{t}"] = bool(d and d.winfo_exists() and d.winfo_viewable())
d = alt_ui.DropList.current
if d:
    r["droplist"] = {"geo": d.winfo_geometry(), "root": [d.winfo_rootx(), d.winfo_rooty()],
                     "entries": [lab.cget("text") for lab, _b, _e in d.items],
                     "shown": str(app.winfo_containing(d.winfo_rootx() + d.winfo_width() // 2, d.winfo_rooty() + d.winfo_height() // 2)).startswith(str(d))}
    shot("open")
    if len(sys.argv) > 3:
        lab = [it for it in d.items if not it[0].cget("text").startswith("✓")][0][0]
        r["picked"] = lab.cget("text").strip()
        click(lab.winfo_rootx() + lab.winfo_width() / 2, lab.winfo_rooty() + lab.winfo_height() / 2)
        pump(1.5); shot("picked"); r["toplevels_after_pick"] = [str(w) for w in app.winfo_children() if isinstance(w, __import__("tkinter").Toplevel) and w.winfo_viewable()]
        click(b.winfo_rootx() + b.winfo_width() / 2, b.winfo_rooty() + b.winfo_height() / 2); pump(0.6)
        d2 = alt_ui.DropList.current
        r["after_pick_entries"] = [lab.cget("text") for lab, _b, _e in d2.items] if d2 else None
else:
    shot("closed")
r["close_log"] = log; r["clicks"] = clicks; r["screen_after"] = str(getattr(app, "current", None) or getattr(app, "_screen", None)); r["errors"] = errs[:3]
(out / f"{skin}_{COMP}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok")
app.destroy(); shutil.rmtree(tmp, ignore_errors=True)
