"""Колесо мыши везде: прокручивается та область, над которой курсор.

Один глобальный обработчик (``bind_all``) ищет ближайшего прокручиваемого предка
виджета под курсором: Canvas с прокруткой, Text, Listbox, Treeview. Если область
уже упёрлась в край в эту сторону — колесо уходит выше (вложенные списки внутри
прокручиваемой страницы). Виджеты со своей привязкой колеса (масштаб картинки,
горизонтальные ленты кнопок, чат) обрабатывают его сами — роутер их не трогает.
Text/Listbox/Treeview прокручиваются своими классовыми привязками Tk, роутер
лишь передаёт колесо дальше, когда им прокручивать нечего.
"""
from __future__ import annotations

import tkinter as tk

_INSTALLED: set[str] = set()
SELF_SCROLL = ("Text", "Listbox", "Treeview")
WHEEL = ("<MouseWheel>", "<Button-4>", "<Button-5>")


def installed(widget=None) -> bool:
    """Включён ли роутер (для этого окна — если передан виджет)."""
    if widget is None:
        return bool(_INSTALLED)
    try:
        return str(widget.winfo_toplevel().winfo_toplevel()) in _INSTALLED or "." in _INSTALLED
    except tk.TclError:
        return False


def install(root: tk.Misc) -> None:
    key = str(root.winfo_toplevel())
    if key in _INSTALLED:
        return
    for seq in WHEEL:
        root.bind_all(seq, route, add="+")
    _INSTALLED.add(key)


def direction(e) -> int:
    num = getattr(e, "num", 0)
    if num == 4:
        return -1
    if num == 5:
        return 1
    delta = int(getattr(e, "delta", 0) or 0)
    return -1 if delta > 0 else (1 if delta < 0 else 0)


def _own_wheel(w) -> bool:
    """У виджета своя привязка колеса — он сам решает, что делать."""
    try:
        return any(w.bind(seq) for seq in WHEEL)
    except tk.TclError:
        return False


def _can_scroll(w, d: int) -> bool:
    try:
        cls = w.winfo_class()
        if cls == "Canvas" and not str(w.cget("yscrollcommand")):
            return False
        if cls not in ("Canvas",) + SELF_SCROLL:
            return False
        top, bot = (float(v) for v in w.yview())
    except (tk.TclError, ValueError, TypeError):
        return False
    if top <= 0.0 and bot >= 1.0:
        return False
    return top > 0.0 if d < 0 else bot < 1.0


def target(w, d: int):
    """Ближайший предок (или сам виджет), который может прокрутиться в сторону d."""
    x = w
    while x is not None:
        if _can_scroll(x, d):
            return x
        x = getattr(x, "master", None)
    return None


def route(e):
    d = direction(e)
    w = e.widget
    if not d or not isinstance(w, tk.Misc):
        return None
    if _own_wheel(w):
        return None
    t = target(w, d)
    if t is None:
        return None
    if t is w and t.winfo_class() in SELF_SCROLL:
        return None            # Tk уже прокрутил его классовой привязкой
    try:
        if t.winfo_class() == "Canvas":
            inc = str(t.cget("yscrollincrement"))
            t.yview_scroll(d * (2 if inc not in ("", "0") else 3), "units")
        else:
            t.yview_scroll(d * 3, "units")
    except tk.TclError:
        pass
    return None
