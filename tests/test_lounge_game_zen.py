"""Общий зенид: Ctrl+O, двойной Esc и восстановление хрома при выходе."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina.grammar_ui.focus import O_KEYCODE
from stamina.hotkeys import CTRL
from stamina import zen_mode


def key(sym="o", char=None, state=CTRL, keycode=0, widget=None):
    if char is None:
        char = sym if len(sym) == 1 else ""
    return SimpleNamespace(keysym=sym, char=char, state=state, keycode=keycode, widget=widget)


@pytest.fixture
def chrome():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360+0+0")
    header = tk.Frame(root, bg="#111", height=40, name="header")
    header.pack(fill=tk.X)
    tk.Label(header, text="STAR TYPING").pack()
    game = tk.Frame(root, bg="#000", name="game")
    game.pack(fill=tk.BOTH, expand=True)
    tk.Label(game, text="ИГРА").pack()
    root.update_idletasks()
    root.update()
    zen_mode._ACTIVE.clear()
    zen_mode._ESC.reset()
    try:
        yield SimpleNamespace(root=root, header=header, game=game)
    finally:
        zen_mode.exit_zen(game)
        root.destroy()


class TestZenHotkey:
    def test_ctrl_o_variants(self):
        assert zen_mode.is_zen_hotkey(key("o", state=CTRL))
        assert zen_mode.is_zen_hotkey(key("O", "O", state=CTRL))
        assert zen_mode.is_zen_hotkey(key("Cyrillic_shcha", "щ", state=CTRL))
        assert zen_mode.is_zen_hotkey(key("", "", state=CTRL, keycode=O_KEYCODE))
        assert not zen_mode.is_zen_hotkey(key("o", state=0))
        assert not zen_mode.is_zen_hotkey(key("m", state=CTRL))

    def test_single_o_does_not_toggle(self, chrome):
        assert zen_mode.handle_key(key("o", state=0), widget=chrome.game) is False
        assert not zen_mode.is_active(chrome.game)
        assert chrome.header.winfo_ismapped()


class TestZenChrome:
    def test_toggle_hides_and_restores_saved_mode(self, chrome):
        assert chromeless(chrome)
        assert zen_mode.handle_key(key("o", state=CTRL), widget=chrome.game) is True
        chrome.root.update()
        assert zen_mode.is_active(chrome.game)
        mode = zen_mode.mode_of(chrome.game)
        assert mode is not None and mode.saved
        assert not chrome.header.winfo_ismapped()
        assert chrome.game.winfo_ismapped()
        assert zen_mode.handle_key(key("o", state=CTRL), widget=chrome.game) is True
        chrome.root.update()
        assert not zen_mode.is_active(chrome.game)
        assert chrome.header.winfo_ismapped()
        assert zen_mode.mode_of(chrome.game) is None

    def test_allow_esc_false_leaves_esc_to_the_game(self, chrome):
        esc = key("Escape", char="\x1b", state=0)
        assert zen_mode.enter(chrome.game)
        assert zen_mode.handle_key(esc, widget=chrome.game, allow_esc=False) is False
        assert zen_mode.is_active(chrome.game)

    def test_first_esc_passes_second_exits(self, chrome):
        assert zen_mode.enter(chrome.game)
        chrome.root.update()
        esc = key("Escape", char="\x1b", state=0)
        assert zen_mode.handle_key(esc, widget=chrome.game) is False
        assert zen_mode.is_active(chrome.game)
        assert zen_mode.handle_key(esc, widget=chrome.game) is True
        chrome.root.update()
        assert not zen_mode.is_active(chrome.game)
        assert chrome.header.winfo_ismapped()

    def test_esc_timeout_resets(self, chrome):
        assert zen_mode.enter(chrome.game)
        esc = key("Escape", char="\x1b", state=0)
        assert zen_mode.handle_key(esc, widget=chrome.game) is False
        zen_mode._ESC._at = time.monotonic() - 1.0
        assert zen_mode.handle_key(esc, widget=chrome.game) is False
        assert zen_mode.is_active(chrome.game)

    def test_exit_on_leave_clears_active(self, chrome):
        assert zen_mode.enter(chrome.game)
        assert zen_mode.is_active(chrome.game)
        assert zen_mode.exit_zen(chrome.game)
        chrome.root.update()
        assert not zen_mode.is_active(chrome.game)
        assert chrome.header.winfo_ismapped()


def chromeless(chrome) -> bool:
    return chrome.header.winfo_ismapped()
