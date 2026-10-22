"""Регрессия: смена скина/варианта в окне входа не оставляет кусков прежнего скина.

A → B → A и КЛАССИКА ↔ ПУЛЬТ-КАБИНА: окно входа пересобирается целиком; после этого
на экране один LoginScreen, одна сцена, нет лишних таймеров и нет цветов скина B,
которых нет в скине A. Данные пилота не трогаем: APPDATA → временная папка.
"""
from __future__ import annotations

import tkinter as tk

import pytest


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _colors(root) -> set[str]:
    out = set()
    for w in _walk(root):
        for opt in ("bg", "fg", "highlightbackground", "activebackground"):
            try:
                v = str(w.cget(opt)).upper()
            except tk.TclError:
                continue
            if v.startswith("#"):
                out.add(v)
    return out


@pytest.fixture()
def host(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from stamina import pilots, theme
    pilots.reset_root(tmp_path / "Stamina")
    from stamina.pilot_screens import LoginScreen
    for cs in ("ORION", "VEGA"):
        pilots.create(cs)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("1280x720")
    theme.load_theme("spaceship", apply_ui=True, root=root)
    holder = tk.Frame(root)
    holder.pack(fill=tk.BOTH, expand=True)
    cur = {"page": None}

    def show(state=None):
        if cur["page"] is not None:
            cur["page"].destroy()
        cur["page"] = LoginScreen(holder, on_enter=lambda p: None, on_exit=lambda: None,
                                  on_rebuild=show, state=state)
        cur["page"].pack(fill=tk.BOTH, expand=True)
        root.update()

    show()
    yield root, holder, cur
    root.destroy()
    theme.load_theme("spaceship", apply_ui=False)
    pilots.reset_root(None)


def _palette(tid):
    from stamina import theme
    theme.load_theme(tid, apply_ui=False)
    pal = {v.upper() for v in theme._snapshot().values() if v.startswith("#")}
    return pal


def test_skin_switch_rebuilds_without_leftovers(host):
    from stamina import alt_ui, theme
    from stamina.pilot_screens import LoginScreen
    root, holder, cur = host
    star, steam = _palette("spaceship"), _palette("steampunk")
    theme.load_theme("spaceship", apply_ui=True, root=root)
    base_after = len(root.tk.call("after", "info"))
    for skin, layout in (("steampunk", "classic"), ("steampunk", "alt"), ("spaceship", "alt"),
                         ("spaceship", "classic"), ("steampunk", "alt"), ("spaceship", "classic")):
        cur["page"]._pick_layout(layout)
        root.update()
        cur["page"]._preview_skin(skin)
        root.update()
        page = cur["page"]
        assert (page._skin_id, page._layout_id) == (skin, layout)
        assert theme.theme_id() == skin
        logins = [w for w in holder.winfo_children() if isinstance(w, LoginScreen)]
        assert logins == [page]
        stages = [w for w in _walk(root) if isinstance(w, alt_ui.LoginStage)]
        assert len(stages) == 1
        # таймеров не прибавляется от пересборок: часы + слайдшоу + отрисовка сцены
        assert len(root.tk.call("after", "info")) <= base_after + 3
    # вернулись к Звездолёту/классике: цветов, которые есть только у Стимпанка, нет
    only_steam = steam - star
    leftovers = _colors(root) & only_steam
    assert not leftovers, leftovers


def test_variant_row_visible_next_to_skins(host):
    root, holder, cur = host
    for size in ("1024x600", "1280x720"):
        root.geometry(size)
        root.update()
        page = cur["page"]
        for b in page._layout_btns.values():
            x = b.winfo_rootx() - root.winfo_rootx()
            assert b.winfo_ismapped() and x + b.winfo_width() <= root.winfo_width(), size
