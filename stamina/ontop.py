"""«Поверх всех окон»: окно программы держится над остальными.

Tk-атрибут ``-topmost`` ставит окно в верхний слой Windows, но новое окно,
которое тоже просит быть сверху (консоль, установщик), может его перекрыть.
Поэтому, пока настройка включена, раз в ``PERIOD_MS`` окно тихо поднимается
обратно через SetWindowPos(HWND_TOPMOST) — без активации, фокус не крадём.
Свои диалоги (Toplevel, messagebox, filedialog) принадлежат главному окну
и Windows держит их над ним, так что они не прячутся; отдельным Toplevel
без хозяина тоже ставится ``-topmost``.
"""
from __future__ import annotations

import sys
import tkinter as tk

PERIOD_MS = 1500
KEY = "topmost"
HOTKEYS = ("<Control-Shift-T>", "<Control-Shift-t>")

_HWND_TOPMOST = -1
_SWP_NOSIZE, _SWP_NOMOVE, _SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
_FLAGS = _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE


def _hwnd(win) -> int:
    try:
        return int(win.wm_frame(), 16)
    except (tk.TclError, ValueError, TypeError):
        return 0


def _lift_native(win) -> None:
    if sys.platform != "win32":
        return
    h = _hwnd(win)
    if not h:
        return
    try:
        import ctypes
        ctypes.windll.user32.SetWindowPos(h, _HWND_TOPMOST, 0, 0, 0, 0, _FLAGS)
    except Exception:  # noqa: BLE001
        pass


def _toplevels(root) -> list:
    out = []
    try:
        for w in root.winfo_children():
            if isinstance(w, tk.Toplevel):
                out.append(w)
    except tk.TclError:
        pass
    return out


def enabled(root) -> bool:
    return bool(getattr(root, "_ontop_on", False))


def apply(root, on: bool) -> None:
    """Включить/выключить «поверх всех окон» для root и его окон."""
    on = bool(on)
    root._ontop_on = on
    for w in [root, *_toplevels(root)]:
        try:
            w.attributes("-topmost", on)
        except tk.TclError:
            pass
    if on:
        _lift_native(root)
        if getattr(root, "_ontop_job", None) is None:
            root._ontop_job = root.after(PERIOD_MS, lambda: _tick(root))
    else:
        job = getattr(root, "_ontop_job", None)
        root._ontop_job = None
        if job is not None:
            try:
                root.after_cancel(job)
            except tk.TclError:
                pass


def _tick(root) -> None:
    root._ontop_job = None
    if not enabled(root):
        return
    try:
        if not root.winfo_exists():
            return
        if root.state() not in ("iconic", "withdrawn"):
            for w in _toplevels(root):
                try:
                    if not w.wm_transient() and w.winfo_viewable():
                        w.attributes("-topmost", True)
                except tk.TclError:
                    pass
            _lift_native(root)
    except tk.TclError:
        return
    root._ontop_job = root.after(PERIOD_MS, lambda: _tick(root))
