"""Мониторы: где открывать выпадашки, подсказки и диалоги.

Окно можно перетащить на другой монитор (в т. ч. с отрицательными координатами —
слева/сверху от основного). Поэтому позиция всплывающего окна считается В МОМЕНТ
открытия от якоря (winfo_rootx/rooty), а пределы — по рабочей области монитора, на
котором якорь стоит сейчас. winfo_screenwidth() — это только ОСНОВНОЙ монитор:
им не ограничиваем.

Для тестов: ``set_provider(fn)``, где ``fn(x, y, nearest) -> (l, t, r, b) | None``.
"""
from __future__ import annotations

import sys
import tkinter as tk

Rect = tuple[int, int, int, int]
_provider = None          # подмена раскладки мониторов в тестах


def set_provider(fn) -> None:
    global _provider
    _provider = fn


def _win32(x: int, y: int, nearest: bool) -> Rect | None:
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    u = ctypes.windll.user32
    u.MonitorFromPoint.restype = wintypes.HANDLE
    u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    h = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2 if nearest else 0)
    if not h:
        return None
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not u.GetMonitorInfoW(h, ctypes.byref(mi)):
        return None
    r = mi.rcWork
    return int(r.left), int(r.top), int(r.right), int(r.bottom)


def _query(x: int, y: int, nearest: bool) -> Rect | None:
    if _provider is not None:
        return _provider(x, y, nearest)
    if sys.platform == "win32":
        try:
            return _win32(x, y, nearest)
        except Exception:
            return None
    return None


def work_area(widget, x: int | None = None, y: int | None = None) -> Rect:
    """Рабочая область монитора с точкой (x, y) — по умолчанию центр окна widget."""
    try:
        if x is None or y is None:
            top = widget.winfo_toplevel()
            x = top.winfo_rootx() + top.winfo_width() // 2
            y = top.winfo_rooty() + top.winfo_height() // 2
        r = _query(x, y, True)
        if r is not None:
            return r
        vx, vy = widget.winfo_vrootx(), widget.winfo_vrooty()
        vw, vh = widget.winfo_vrootwidth(), widget.winfo_vrootheight()
        if vw > 1 and vh > 1 and vx <= x < vx + vw and vy <= y < vy + vh and (vx, vy) != (0, 0):
            return vx, vy, vx + vw, vy + vh
        return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()
    except tk.TclError:
        return 0, 0, 1920, 1080


def on_some_monitor(x: int, y: int) -> bool | None:
    """Точка лежит на каком-то мониторе? None — неизвестно (не Windows, без подмены)."""
    if _provider is None and sys.platform != "win32":
        return None
    return _query(x, y, False) is not None


def fit(x: int, y: int, w: int, h: int, area: Rect) -> tuple[int, int]:
    l, t, r, b = area
    x = max(l, min(x, r - w))
    y = max(t, min(y, b - h))
    return x, y


def below_pos(anchor, w: int, h: int) -> tuple[int, int]:
    """Позиция окна w×h под якорем; не влезает — вверх/влево; всегда в мониторе якоря."""
    ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
    aw, ah = anchor.winfo_width(), anchor.winfo_height()
    area = work_area(anchor, ax + aw // 2, ay + ah // 2)
    l, t, r, b = area
    x, y = ax, ay + ah
    if y + h > b and ay - h >= t:
        y = ay - h                      # вверх
    if x + w > r:
        x = ax + aw - w                 # влево: правый край к правому краю якоря
    return fit(x, y, w, h, area)


def place_below(win, anchor) -> None:
    try:
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x, y = below_pos(anchor, w, h)
        win.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass


def center_geometry(master, w: int, h: int, dy: int = 0) -> str:
    """Строка geometry окна w×h по центру окна master, в пределах его монитора."""
    top = master.winfo_toplevel()
    l, t, r, b = work_area(top)
    w, h = min(w, r - l), min(h, b - t)
    x = top.winfo_rootx() + (top.winfo_width() - w) // 2
    y = top.winfo_rooty() + (top.winfo_height() - h) // 2 + dy
    x, y = fit(x, y, w, h, (l, t, r, b))
    return f"{w}x{h}+{x}+{y}"


def area_size(master) -> tuple[int, int]:
    l, t, r, b = work_area(master)
    return r - l, b - t


def follow_toplevels(root) -> None:
    """Окна-спутники (диалоги, просмотр картинки, выпадашки) едут вместе с главным окном.

    Tk не двигает transient-окна за хозяином (Windows), и при переносе программы на
    другой монитор открытые диалоги оставались на старом. На каждый сдвиг корня
    сдвигаем дочерние Toplevel на ту же дельту и прижимаем к монитору окна;
    выпадающие списки (overrideredirect) — закрываем.
    """
    state = {"xy": None}

    def on_cfg(e) -> None:
        if e.widget is not root:
            return
        try:
            xy = (root.winfo_rootx(), root.winfo_rooty())
        except tk.TclError:
            return
        old, state["xy"] = state["xy"], xy
        if old is None or old == xy:
            return
        move_children(root, xy[0] - old[0], xy[1] - old[1])

    root.bind("<Configure>", on_cfg, add="+")


def move_children(root, dx: int, dy: int) -> None:
    area = None
    for w in list(root.winfo_children()):
        if not isinstance(w, tk.Toplevel):
            continue
        try:
            if not w.winfo_ismapped():
                continue
            if hasattr(w, "close") and w.overrideredirect():
                w.close()               # выпадающий список — привязан к кнопке, закрываем
                continue
            if area is None:
                area = work_area(root)
            ww, hh = w.winfo_width(), w.winfo_height()
            gx, gy = parse_xy(w.geometry())     # те же координаты, что принимает geometry()
            x, y = fit(gx + dx, gy + dy, ww, hh, area)
            w.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass


def parse_xy(geo: str) -> tuple[int, int]:
    """'WxH+X+Y' / 'WxH-X+Y' → (X, Y) с учётом отрицательных координат."""
    import re
    m = re.match(r"\d+x\d+([+-]-?\d+)([+-]-?\d+)", geo)
    if not m:
        raise tk.TclError(geo)
    return int(m.group(1).replace("+-", "-").lstrip("+") or 0), int(m.group(2).replace("+-", "-").lstrip("+") or 0)
