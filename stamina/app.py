"""Точка сборки приложения Stamina."""

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


def run_app() -> None:
    _enable_dpi_awareness()
    from stamina.cockpit import Cockpit
    Cockpit().mainloop()
