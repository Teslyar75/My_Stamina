"""Точка сборки приложения Star Typing (пакет по-прежнему называется stamina)."""

from __future__ import annotations

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


def run_app() -> None:
    _enable_dpi_awareness()
    _set_app_id()
    from stamina.cockpit import Cockpit
    Cockpit().mainloop()
