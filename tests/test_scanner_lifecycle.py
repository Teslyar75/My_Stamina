"""Регрессия Ubuntu-зависаний: wraplength/Configure и жизненный цикл сканера.

Diagnostic 42416812984: SIGALRM в stamina/english/pages_main.py:1109
(col.bind Configure → label.configure wraplength) на test_alt_parity[steampunk]
и ScannerCompactTest.test_layout_fits_small_screens_and_focus. Изолированный
прогон тех же файлов был зелёный — ловим каскад Configure и последовательность
overview→scanner, а не прячем hang skip/xfail/таймаутом.
"""
from __future__ import annotations

import os
import tempfile
import time
import tkinter as tk
from pathlib import Path

import pytest

os.environ.setdefault("STAR_TYPING_NO_STALL_WATCH", "1")
os.environ.setdefault("STAR_TYPING_NO_LINUX_TTS", "1")

WRAPLENGTH_BOUND = 40


def _cockpit(tmp, *, skin="spaceship"):
    from stamina import pilots, storage
    from stamina.cockpit import Cockpit

    pilots.reset_root(Path(tmp))
    os.environ["APPDATA"] = str(tmp)
    storage.DEFAULT_SETTINGS.update(living_space="off", idle_minutes=0, skin=skin)
    try:
        app = Cockpit()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        app.guide.stop()
    except Exception:
        pass
    return app


def _wait_english(app, timeout=15.0):
    app.show("english")
    scr = app.screens["english"]
    end = time.time() + timeout
    while not getattr(scr, "_built", False) and time.time() < end:
        app.update()
        time.sleep(0.02)
    if not getattr(scr, "_built", False):
        pytest.fail("английский не собрался")
    return scr


def _pump(app, seconds=0.4):
    end = time.time() + seconds
    loops = 0
    while time.time() < end:
        app.update()
        loops += 1
        time.sleep(0.01)
        if loops > 800:
            pytest.fail("update() не вернул управление — каскад Configure")
    return loops


def _spy_wraplength(label):
    n = {"n": 0}
    orig = label.configure

    def wrapped(cnf=None, **kw):
        keys = kw if kw else (cnf if isinstance(cnf, dict) else {})
        if "wraplength" in keys:
            n["n"] += 1
            if n["n"] > WRAPLENGTH_BOUND * 4:
                # остановить каскад, чтобы тест смог сообщить о нём, а не зависнуть
                try:
                    label.master.unbind("<Configure>")
                except tk.TclError:
                    pass
        return orig(cnf, **kw)

    label.configure = label.config = wrapped
    return n


def test_bind_wraplength_ignores_one_pixel_jitter():
    """1px дребезг ширины не должен бесконечно менять wraplength (каскад Configure)."""
    from stamina.adapt import bind_wraplength

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        host = tk.Frame(root, bg="#111")
        host.pack(fill=tk.X)
        lbl = tk.Label(host, text="word " * 40, wraplength=200, justify="left")
        lbl.pack(anchor="w")
        root.geometry("240x80+0+0")
        root.update()
        bind_wraplength(lbl, host, margin=4)
        n = _spy_wraplength(lbl)
        for w in (240, 241, 240, 241, 242, 240):
            root.geometry(f"{w}x80+0+0")
            root.update()
        assert n["n"] <= 2, f"wraplength гонялся за 1px: {n['n']} раз"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_scanner_wraplength_stays_bounded_on_open_and_resize():
    tmp = tempfile.mkdtemp()
    app = _cockpit(tmp)
    try:
        app.geometry("1024x600+0+0")
        scr = _wait_english(app)
        _pump(app, 0.3)
        assert scr.current == "overview"
        scr.show("scanner")
        page = scr.pages["scanner"]
        n = _spy_wraplength(page.ptext)
        _pump(app, 0.5)
        app.geometry("1025x600+0+0")
        _pump(app, 0.3)
        app.geometry("1024x600+0+0")
        _pump(app, 0.3)
        app.geometry("1280x720+0+0")
        _pump(app, 0.4)
        assert n["n"] <= WRAPLENGTH_BOUND, f"сканер: wraplength {n['n']} раз при открытии/ресайзе"
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_overview_then_scanner_sequence_settles():
    """Порядок как в alt_ui_audit: english открывается на обзоре, сканер уже в grid."""
    tmp = tempfile.mkdtemp()
    app = _cockpit(tmp, skin="steampunk")
    try:
        app.geometry("1024x600+0+0")
        scr = _wait_english(app)
        page = scr.pages["scanner"]
        n = _spy_wraplength(page.ptext)
        _pump(app, 0.8)
        assert scr.current == "overview"
        scr.show("scanner")
        _pump(app, 0.8)
        assert n["n"] <= WRAPLENGTH_BOUND, f"overview→scanner wraplength {n['n']}"
        assert page.winfo_ismapped()
        app.update()
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_second_cockpit_after_destroy_opens_scanner():
    """Жизненный цикл: предыдущая кабина уничтожена — следующая не зависает на сканере."""
    tmp1 = tempfile.mkdtemp()
    app1 = _cockpit(tmp1)
    try:
        app1.geometry("1024x600+0+0")
        _wait_english(app1)
        _pump(app1, 0.3)
    finally:
        try:
            app1.destroy()
        except tk.TclError:
            pass

    tmp2 = tempfile.mkdtemp()
    app2 = _cockpit(tmp2, skin="steampunk")
    try:
        app2.geometry("1280x720+0+0")
        scr = _wait_english(app2)
        page = scr.pages["scanner"]
        n = _spy_wraplength(page.ptext)
        scr.show("scanner")
        _pump(app2, 0.8)
        assert n["n"] <= WRAPLENGTH_BOUND, f"вторая кабина wraplength {n['n']}"
        app2.update()
    finally:
        try:
            app2.destroy()
        except tk.TclError:
            pass
