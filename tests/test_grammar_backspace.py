"""Backspace в грамматике: шаг назад по меню, не трогает поля ввода и зенид."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina.grammar_ui.spread import GrammarSpread
from stamina.hotkeys import typing_in
from tests.test_grammar_focus import StubCatalog, key


@pytest.fixture
def board():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360+0+0")
    catalog = StubCatalog()
    spread = GrammarSpread(root, catalog, None)
    spread.pack(fill=tk.BOTH, expand=True)
    spread.catalog.load_index()
    spread._on_index(None)
    spread._flush_pending()
    root.update()
    try:
        yield SimpleNamespace(root=root, spread=spread, catalog=catalog)
    finally:
        try:
            spread.toggle_focus(False, remember=False)
        except Exception:
            pass
        root.destroy()


def _open_first(board):
    s = board.spread
    s._open_unit("u1")
    for _ in range(40):
        s._flush_pending()
        board.root.update()
        if s._data is not None:
            break
    assert s._unit == "u1"
    assert s._data is not None


class TestBackspaceMenu:
    def test_from_lesson_to_list(self, board):
        s = board.spread
        _open_first(board)
        assert s.on_key(key("BackSpace", char="\x08")) == "break"
        board.root.update()
        assert s._unit is None
        assert s._data is None
        # список уровней и уроков на месте
        assert s._level_bar.winfo_ismapped()
        assert s._left.winfo_ismapped()

    def test_stays_in_zen(self, board):
        s = board.spread
        _open_first(board)
        s.toggle_focus(True)
        board.root.update()
        assert s.in_focus()
        assert s.on_key(key("BackSpace", char="\x08")) == "break"
        board.root.update()
        assert s.in_focus()
        assert s._unit is None
        assert s._data is None
        assert s._level_bar.winfo_ismapped()

    def test_ignored_in_entry(self, board):
        s = board.spread
        _open_first(board)
        entry = tk.Entry(board.root)
        entry.pack()
        entry.focus_set()
        board.root.update()
        ev = key("BackSpace", char="\x08", widget=entry)
        assert typing_in(entry)
        assert s.on_key(ev) is None
        assert s._unit == "u1"
        assert s._data is not None

    def test_second_backspace_on_list_is_noop(self, board):
        s = board.spread
        _open_first(board)
        assert s.on_key(key("BackSpace", char="\x08")) == "break"
        board.root.update()
        assert s._unit is None
        assert s.on_key(key("BackSpace", char="\x08")) is None
        assert s.winfo_ismapped()
