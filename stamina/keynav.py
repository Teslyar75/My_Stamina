"""Навигация с клавиатуры по всем экранам: стрелки, Tab, Enter, Esc.

Правило простое и не мешает печати: стрелки двигают фокус только когда он уже на кнопке
(янтарные «скобки прицела»). Без фокуса клавиши работают как раньше (печать, горячие клавиши экранов).

- Tab — прыжок в главное меню (вкладка текущего раздела); ещё раз Tab — из меню к кнопкам раздела.
- ← → ↑ ↓ — к соседней кнопке в эту сторону (по положению на экране: вкладки, подвкладки, панели).
- Enter / пробел — нажать кнопку. После вкладки меню фокус возвращается разделу (можно печатать).
- Esc или Shift+Tab — убрать фокус с кнопок.
- В поле печати мостика во время полёта Tab и стрелки по-прежнему уходят в печать:
  сначала Esc (пауза), потом Tab.
В диалогах (окна поверх) Tab работает как обычно — по полям и кнопкам, Enter нажимает кнопку в фокусе.
"""
from __future__ import annotations

import tkinter as tk

TAG = "HudNav"
ARROWS = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}


def attach(button: tk.Misc) -> None:
    """Добавить кнопке клавиши навигации (тег перед остальными, чтобы клавиши не уходили в печать)."""
    tags = button.bindtags()
    if TAG not in tags:
        button.bindtags((TAG,) + tuple(tags))
    root = button.winfo_toplevel()
    if not getattr(root, "_keynav_class", False):
        root._keynav_class = True
        button.bind_class(TAG, "<KeyPress>", _on_button_key)


def _center(w):
    return w.winfo_rootx() + w.winfo_width() / 2, w.winfo_rooty() + w.winfo_height() / 2


def visible_buttons(top: tk.Misc) -> list:
    """Кнопки окна, которые реально видны (не под другим экраном/страницей) и доступны."""
    from stamina.hud import HudButton
    out, stack = [], [top]
    while stack:
        w = stack.pop()
        for ch in w.winfo_children():
            if isinstance(ch, tk.Toplevel):
                continue
            stack.append(ch)
            if isinstance(ch, HudButton) and ch._enabled and ch.winfo_viewable():
                cx, cy = _center(ch)
                hit = top.winfo_containing(int(cx), int(cy))
                if hit is ch or (hit is not None and str(hit).startswith(str(ch))):
                    out.append(ch)
    out.sort(key=lambda b: (round(_center(b)[1] / 20), _center(b)[0]))
    return out


def neighbour(cur, buttons: list, dx: int, dy: int):
    cx, cy = _center(cur)
    best, score = None, None
    for b in buttons:
        if b is cur:
            continue
        bx, by = _center(b)
        prim = (bx - cx) * dx + (by - cy) * dy
        if prim <= 2:
            continue
        sec = abs(by - cy) if dx else abs(bx - cx)
        if dx and sec > max(cur.winfo_height(), b.winfo_height()):    # ← → сначала в своём ряду
            sec *= 4
        s = prim + 2 * sec
        if score is None or s < score:
            best, score = b, s
    return best


def _on_button_key(e):
    b = e.widget
    k = e.keysym
    if k in ARROWS:
        dx, dy = ARROWS[k]
        nb = neighbour(b, visible_buttons(b.winfo_toplevel()), dx, dy)
        if nb is not None:
            nb.focus_set()
        return "break"
    if k in ("Return", "KP_Enter", "space"):
        menu = getattr(b, "nav_menu", False)
        b.invoke()
        try:
            if menu or not (b.winfo_exists() and b.winfo_viewable()):
                b.winfo_toplevel().focus_set()
        except tk.TclError:
            pass
        return "break"
    if k == "Escape":
        b.winfo_toplevel().focus_set()
        return "break"
    if k in ("Tab", "ISO_Left_Tab"):
        top = b.winfo_toplevel()
        if getattr(top, "_keynav_main", False):
            return on_tab(top, e)
        return None          # диалоги: обычный обход Tab
    return None


def install(top: tk.Misc, current_menu=None, before_tab=None) -> None:
    """Главное окно: Tab → меню. current_menu() → кнопка меню текущего раздела (или None).
    before_tab(e) → True, если Tab уже обработан экраном (например, идёт печать на мостике)."""
    top._keynav_main = True
    top._keynav_menu = current_menu

    def handler(e):
        f = top.focus_get()
        if isinstance(f, tk.Text) or (f is not None and f.winfo_toplevel() is not top):
            return None                  # в многострочном поле Tab — символ; диалоги — свой обход
        if before_tab is not None and before_tab(e):
            return "break"
        return on_tab(top, e)
    for seq in ("<Tab>", "<Shift-Tab>", "<ISO_Left_Tab>"):
        try:
            top.bind(seq, handler)
        except tk.TclError:          # ISO_Left_Tab есть не везде
            pass


def on_tab(top: tk.Misc, e) -> str:
    """Tab в главном окне. → "break"."""
    shift = bool(e.state & 0x1) or e.keysym == "ISO_Left_Tab"
    focus = top.focus_get()
    if shift:
        top.focus_set()
        return "break"
    buttons = visible_buttons(top)
    if not buttons:
        return "break"
    menu_btns = [b for b in buttons if getattr(b, "nav_menu", False)]
    getter = getattr(top, "_keynav_menu", None)
    cur_menu = getter() if getter else None
    if focus in menu_btns:                                   # из меню — к кнопкам раздела
        content = [b for b in buttons if not getattr(b, "nav_menu", False)
                   and _center(b)[1] > _center(focus)[1] + 5]
        (content or buttons)[0].focus_set()
    elif menu_btns:
        (cur_menu if cur_menu in menu_btns else menu_btns[0]).focus_set()
    else:                                                    # окно без меню: по кругу
        prim = [b for b in buttons if getattr(b, "nav_primary", False)]
        if focus in buttons:
            buttons[(buttons.index(focus) + 1) % len(buttons)].focus_set()
        else:
            (prim or buttons)[0].focus_set()
    return "break"
