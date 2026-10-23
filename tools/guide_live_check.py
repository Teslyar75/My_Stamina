"""Р–РёРІР°СЏ РїСЂРѕРІРµСЂРєР° РіРёРґР° РІ РЅР°СЃС‚РѕСЏС‰РµРј РѕРєРЅРµ: python tools/guide_live_check.py OUTDIR

Р’СЂРµРјРµРЅРЅС‹Р№ APPDATA (РґР°РЅРЅС‹Рµ РїРёР»РѕС‚Р° РЅРµ С‚СЂРѕРіР°СЋС‚СЃСЏ). РќР°Р¶РёРјР°РµС‚ В«в–¶ РџР РћР’Р•Р РРўР¬В»-СЌРєРІРёРІР°Р»РµРЅС‚,
Enter/Esc, РїРµСЂРµРєР»СЋС‡Р°РµС‚ РіРѕР»РѕСЃ, Shift+F1 РІ РЅРµСЃРєРѕР»СЊРєРёС… РѕРєРЅР°С…, РґРµР»Р°РµС‚ СЃРєСЂРёРЅС€РѕС‚С‹ Рё РїРёС€РµС‚ Р»РѕРі.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "guide_live")
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "log.txt", "w", encoding="utf-8")


def log(*a):
    msg = f"{time.strftime('%H:%M:%S')} " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n"); LOG.flush()


def main() -> None:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass
    tmp = tempfile.mkdtemp(prefix="stamina_guide_")
    os.environ["APPDATA"] = tmp
    from stamina import pilots, storage
    pilots.reset_root(Path(tmp) / "Stamina")
    storage.DEFAULT_SETTINGS.update(living_space="off", idle_minutes=0,
                                     skin=os.environ.get("GUIDE_SKIN", "spaceship"))
    from PIL import ImageGrab
    from stamina.cockpit import Cockpit
    from stamina.radio.engine import get_engine
    app = Cockpit()
    app.geometry("1280x760+0+0")
    g = app.guide
    eng = get_engine()
    calls = []
    od, ou = eng.duck, eng.unduck
    eng.duck = lambda *a, **k: (calls.append("duck"), log("RADIO duck, vol", eng.volume), od(*a, **k))[-1]
    eng.unduck = lambda *a, **k: (calls.append("unduck"), log("RADIO unduck"), ou(*a, **k))[-1]
    op = g.player.play
    def play(path, done=None):
        ok = op(path, done)
        app.after(400, lambda: log("  MCI mode:", g.player._mci(f"status {g.player.ALIAS} mode") if g.player._open else "closed"))
        log("PLAY", Path(path).parent.name + "/" + Path(path).name, "started" if ok else "FAILED")
        return ok
    g.player.play = play
    import traceback
    oa = g.accept
    def acc():
        st = traceback.format_stack(limit=8)[:-1]
        log("  ACCEPT via", " | ".join(x.strip().splitlines()[0][-70:] for x in st))
        oa()
    g.accept = acc

    def shot(name):
        app.lift(); app.attributes("-topmost", True); app.update()
        x, y = app.winfo_rootx(), app.winfo_rooty()
        ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height())).save(OUT / f"{name}.png")
        log("shot", name)

    def wait(cond, timeout=40):
        t0 = time.monotonic()
        while not cond() and time.monotonic() - t0 < timeout:
            app.update(); time.sleep(0.05)
        return cond()

    def pump(sec):
        t0 = time.monotonic()
        while time.monotonic() - t0 < sec:
            app.update(); time.sleep(0.03)

    def key(ks):
        w = app.focus_get() or app
        log("KEY", ks, "focus:", w.winfo_class())
        w.event_generate(f"<{ks}>")
        app.update()

    pump(2)
    # СЂР°РґРёРѕ (РїРѕС‚РѕРє РёР· СЃРµС‚Рё; РµСЃР»Рё СЃРµС‚Рё РЅРµС‚ вЂ” РїСЂРѕРїСѓСЃРєР°РµРј)
    url = os.environ.get("GUIDE_RADIO_URL", "https://icecast.radiofrance.fr/fip-midfi.mp3")
    ok = eng.play_station({"name": "test", "url": url})
    pump(4)
    log("radio play:", ok, "playing:", eng.playing, "backend:", eng.backend)

    app.show("settings"); pump(1)
    try:
        app.screens["settings"].show_tab("more")
    except Exception as e:  # noqa: BLE001
        log("tab switch:", e)
    pump(1); shot("01_settings")

    # 1) РіРёРґ, Enter
    g.fire(force=True); pump(1.5); shot("02_intro_prompt")
    log("phase", g.phase, "radio playing", eng.playing)
    log("prompt reached:", wait(lambda: g.phase == "prompt"))
    key("Return"); pump(1); shot("03_item"); log("phase", g.phase)
    log("item done:", wait(lambda: g.phase == "idle", 60)); pump(1)
    # 2) РіРёРґ, Esc
    g.fire(force=True); pump(1); shot("04_buttons")
    log("click NO button"); g._btn_no.event_generate("<Button-1>"); app.update(); log("phase", g.phase, "streak", g.state.data["decline_streak"])
    log("decline done:", wait(lambda: g.phase == "idle")); pump(1)
    # 3) Р¶РµРЅСЃРєРёР№ РіРѕР»РѕСЃ
    app.store.settings["guide_voice"] = "female"
    g.fire(force=True); log("prompt reached:", wait(lambda: g.phase == "prompt"))
    key("Return"); wait(lambda: g.phase == "idle", 60)
    app.store.settings["guide_voice"] = "male"
    # 4) Shift+F1 РїРѕ РѕРєРЅР°Рј
    for i, scr in enumerate(["bridge", "english", "radio", "speedread"]):
        app.show(scr); pump(1)
        (app.focus_get() or app).event_generate("<Shift-F1>"); app.update()
        log("Shift+F1 on", scr, "phase", g.phase)
        pump(2.5); shot(f"1{i}_help_{scr}")
        g.player.stop(); g._help_done(); pump(0.3)
    log("duck/unduck sequence:", calls)
    # 5) СЃРѕСЃРµРґРё: F1, СЃРєРёРЅС‹, СЃР»Р°Р№РґС€РѕСѓ РїСЂРѕСЃС‚РѕСЏ
    app.show("bridge"); pump(0.5)
    app.event_generate("<F1>"); pump(1.5); shot("20_plain_F1")
    for w in app.winfo_children():
        if w.winfo_class() == "Toplevel":
            w.destroy()
    try:
        app.idle.open(); pump(12); shot("21_idle_slideshow")
    except Exception as e:  # noqa: BLE001
        log("idle open:", e)
    eng.stop(); pump(0.5)
    log("DONE")
    app.destroy()
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback
        log(traceback.format_exc())
        os._exit(1)
