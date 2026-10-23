"""Настройки в «Пульт-кабине»: все группы видны разом, каждая сворачивается,
свёрнутые запоминаются у пилота; кнопка вкладки раскрывает свою группу."""
import tkinter as tk

import pytest

from stamina import alt_ui
from stamina.hud import HudButton


class _Store:
    def __init__(self):
        self.settings = {}
        self.saved = 0

    def save_settings(self):
        self.saved += 1


class _App:
    def __init__(self, root):
        self.store = _Store()
        self._root = root

    def after(self, *_a):
        return None

    def after_cancel(self, *_a):
        pass


@pytest.fixture()
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.withdraw()
    yield r
    r.destroy()


def test_sections_collapse_and_remember(root):
    host = tk.Frame(root)
    scr = tk.Frame(root)
    scr.app = _App(root)
    scr.tabs, scr.tab_btns = {}, {}
    for k, t in (("systems", "СИСТЕМЫ"), ("more", "ЕЩЁ")):
        p = tk.Frame(host)
        p.grid(row=0, column=0)
        scr.tabs[k] = (p, tk.Frame(p))
        scr.tab_btns[k] = HudButton(root, f"{t} · Alt+1")
    alt_ui.settings_sections(scr)
    pnl, head = scr._alt_sections["more"]
    assert pnl.winfo_manager() == "grid" and head._text.startswith("▾ ЕЩЁ")
    scr._alt_set_open("more", False)
    assert not pnl.winfo_manager() and scr.app.store.settings[alt_ui.SECTION_KEY] == ["more"]
    scr.show_tab("more")
    assert pnl.winfo_manager() == "grid" and scr.app.store.settings[alt_ui.SECTION_KEY] == []
    assert scr.tabs["systems"][0].winfo_manager() == "grid"


def test_droplist_keyboard(root):
    btn = HudButton(root, "X")
    btn.pack()
    got = []
    dl = alt_ui.DropList(btn, [("A", "a", False, True), ("B", "b", True, False), ("C", "c", False, True)],
                         got.append)
    assert alt_ui.DropList.current is dl and dl.cur == 0
    dl.step(1)
    assert dl.cur == 2          # недоступный пункт пропущен
    dl.enter()
    assert got == ["c"] and alt_ui.DropList.current is None
