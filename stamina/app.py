"""Точка сборки приложения Star Typing (пакет по-прежнему называется stamina)."""

from __future__ import annotations

import os
import sys


def _enable_dpi_awareness() -> None:
    """Чёткий текст на экранах с масштабом 125–150 % (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _set_app_id() -> None:
    """Своя иконка на панели задач Windows вместо иконки Python."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Teslyar75.StarTyping")
    except Exception:
        pass


def _arg(argv: list[str], name: str) -> str | None:
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def _center(root, w: int, h: int) -> None:
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(w, int(sw * 0.94)), min(h, int(sh * 0.9))
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")


def choose_pilot(argv: list[str]) -> str | None:
    """Миграция → реестр → (при необходимости) «ВХОД В КАБИНУ», код доступа, задание кода.

    → id пилота, "" (работать по-старому, без пилотов) или None (выход)."""
    from stamina import pilot_migrate, pilots
    rep = pilot_migrate.migrate()
    reg = pilots.load_registry()
    if reg is None and rep.get("reason") == "error":
        return ""          # миграция не удалась — по-старому, данные не тронуты
    if reg is not None:
        pilot_migrate.late_sync()
    want = _arg(argv, "--pilot") or os.environ.get("STAMINA_PILOT")
    plist = pilots.pilots()
    p = pilots.find(want) if want else None
    need_login = "--select" in argv or "--board" in argv or (
        p is None and (not plist or (len(plist) >= 2 and (reg or {}).get("ask_on_start", True))))
    if p is None and not need_login:
        p = pilots.get((reg or {}).get("last_pilot") or "") or plist[0]
    import tkinter as tk
    from stamina import __version__, pilot_pin, pilot_screens, theme
    root = tk.Tk()
    theme.init(root)
    root.configure(bg=theme.BG)
    try:
        from pathlib import Path
        img = tk.PhotoImage(file=str(Path(__file__).resolve().parent / "assets" / "star_typing_64.png"))
        root.iconphoto(True, img)
    except tk.TclError:
        pass
    pid = None
    try:
        if need_login:
            _center(root, theme.px(1260), theme.px(800))
            pid = pilot_screens.run_login(root, app_version=__version__, initial_board="--board" in argv)
            if pid is None:
                return None
            p = pilots.get(pid)
        else:
            if pilot_pin.has_pin(p["id"]):
                root.title("Star Typing — код доступа")
                _center(root, theme.px(520), theme.px(560))
                root.update_idletasks()
                if not pilot_screens.ask_pin(root, p, "ВХОД В КАБИНУ"):
                    return None
            pid = p["id"]
        p = pilots.get(pid) or p
        if p.get("pin_setup_pending") and not pilot_pin.has_pin(pid):
            if not root.winfo_viewable():
                _center(root, theme.px(620), theme.px(420))
            root.title("Star Typing — код доступа")
            root.update_idletasks()
            pilot_screens.SetPinDialog(root, p, first_time=True).run()
        return pid
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def run_app(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else list(argv)
    _enable_dpi_awareness()
    _set_app_id()
    try:
        pid = choose_pilot(argv)
    except Exception:  # noqa: BLE001 — экипаж не должен мешать полётам
        import traceback
        from stamina import pilots
        pilots.log_error("Ошибка выбора пилота:\n" + traceback.format_exc())
        # с реестром нельзя молча работать «по-старому» (корень уже пуст) — выходим, ошибка в логе
        pid = None if pilots.load_registry() is not None else ""
    if pid is None:
        return
    if pid:
        from stamina import pilots
        pilots.activate(pid)
    from stamina.cockpit import Cockpit
    Cockpit().mainloop()
