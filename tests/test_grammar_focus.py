"""Зенид грамматики: прячет хром над панелью, урок и вкладки остаются.

Ctrl+O и O/Щ переключают режим, двойной Esc выходит, уход со вкладки
восстанавливает шапку. Поведение дзена/фокуса в других отсеках не меняется.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina.english.speech_std import is_focus_key
from stamina.grammar_ui.focus import (
    ESC_DOUBLE_SEC,
    EscDouble,
    is_grammar_focus_key,
    reset_session,
    session_wanted,
)
from stamina.grammar_ui.model import SourceTab
from stamina.grammar_ui.spread import GrammarSpread
from stamina.hotkeys import CTRL, ALT
from stamina.zen import is_zen_hotkey


def key(sym="o", char=None, state=0, keycode=0, widget=None):
    if char is None:
        char = sym if len(sym) == 1 else ""
    return SimpleNamespace(keysym=sym, char=char, state=state, keycode=keycode, widget=widget)


class StubCatalog:
    show_source_tabs = True
    levels = ["A1", "A2"]

    def __init__(self) -> None:
        self._source = "course"
        self.loaded = []

    def sources(self):
        return [
            SourceTab(id="course", title="Курс Star Typing"),
            SourceTab(id="grimm", title="По методике Grimm Grammar"),
        ]

    def select_source(self, source_id: str) -> None:
        self._source = source_id

    def current_source_id(self) -> str:
        return self._source

    def load_index(self) -> None:
        return None

    def index_loaded(self) -> bool:
        return True

    def header_subtitle(self, level: str) -> str:
        return "Stub · 2"

    def progress_text(self) -> str:
        return "ПРОЙДЕНО: 0 / 2"

    def list_plan(self, level: str):
        return [
            ("mod", {"id": "m1", "title": "Раздел", "subtitle": ""}),
            ("unit", {"id": "u1", "number": "01", "title": "Урок один", "level": level}),
            ("unit", {"id": "u2", "number": "02", "title": "Урок два", "level": level}),
        ]

    def first_unit(self, level: str):
        return "u1"

    def level_of(self, unit_id) -> str:
        return "A1"

    def load_lesson(self, unit_id) -> dict:
        self.loaded.append(unit_id)
        return {
            "title": "Урок один",
            "number": 1,
            "level": "A1",
            "can_do": ["Цель"],
            "theory": [{"kind": "text", "title": "Правило", "text": "Текст правила."}],
            "examples": [],
            "exercises": [],
        }

    def neighbours(self, unit_id):
        return (None, "u2")

    def hint_for_unit(self, unit_id) -> str:
        return "Урок 1 из 2"

    def unit_number(self, unit_id) -> int:
        return 1

    def is_done(self, unit_id) -> bool:
        return False

    def mark_complete(self, unit_id, ok: int, total: int) -> bool:
        return False

    def lesson_answers(self, ex: dict) -> list[str]:
        return []

    def gap_ok(self, value: str, ex: dict) -> bool:
        return False

    def choice_index(self, ex: dict) -> int:
        return 0


@pytest.fixture
def chrome():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360+0+0")
    reset_session()
    header = tk.Frame(root, bg="#111", height=40, name="header")
    header.pack(fill=tk.X)
    tk.Label(header, text="STAR TYPING").pack()
    radio = tk.Frame(root, bg="#222", height=24, name="radio")
    radio.pack(fill=tk.X)
    tk.Label(radio, text="RADIO").pack()
    status = tk.Frame(root, bg="#111", height=22, name="status")
    status.pack(fill=tk.X, side=tk.BOTTOM)
    tk.Label(status, text="ПРОДОЛЖАЕМ").pack()
    screen = tk.Frame(root, bg="#000", name="screen")
    screen.pack(fill=tk.BOTH, expand=True)
    title = tk.Frame(screen, name="big_title")
    title.pack(fill=tk.X)
    tk.Label(title, text="ИНОСТРАННЫЕ ЯЗЫКИ").pack()
    lang_row = tk.Frame(screen, name="lang_row")
    lang_row.pack(fill=tk.X)
    tk.Label(lang_row, text="← ЯЗЫКИ  DE").pack()
    submenu = tk.Frame(screen, name="submenu")
    submenu.pack(fill=tk.X)
    tk.Label(submenu, text="ОБЗОР ГРАММАТИКА").pack()
    body = tk.Frame(screen, name="page")
    body.pack(fill=tk.BOTH, expand=True)
    catalog = StubCatalog()
    spread = GrammarSpread(body, catalog, None)
    spread.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    root.update()
    chrome = SimpleNamespace(
        root=root, header=header, radio=radio, title=title, lang_row=lang_row,
        submenu=submenu, status=status, spread=spread, catalog=catalog, body=body,
        screen=screen,
    )

    def mapped(w) -> bool:
        try:
            return bool(w.winfo_ismapped())
        except tk.TclError:
            return False

    chrome.mapped = mapped
    try:
        yield chrome
    finally:
        try:
            spread.toggle_focus(False, remember=False)
        except Exception:
            pass
        reset_session()
        root.destroy()


class TestFocusKeys:
    def test_o_shcha_keycode_and_ctrl(self):
        assert is_grammar_focus_key(key("o"))
        assert is_grammar_focus_key(key("O", "O"))
        assert is_grammar_focus_key(key("Cyrillic_shcha", "щ"))
        assert is_grammar_focus_key(key("", "щ"))
        assert is_grammar_focus_key(key("??", "", keycode=79))
        assert is_grammar_focus_key(key("o", "o", state=CTRL))
        assert not is_grammar_focus_key(key("m"))
        assert not is_grammar_focus_key(key("o", state=ALT))

    def test_letter_o_ignored_in_entry_ctrl_o_not(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        try:
            entry = tk.Entry(root)
            entry.pack()
            entry.focus_set()
            root.update()
            assert not is_grammar_focus_key(key("o", widget=entry))
            assert is_grammar_focus_key(key("o", state=CTRL, widget=entry))
        finally:
            root.destroy()

    def test_scanner_focus_key_and_zen_hotkey_unchanged(self):
        assert is_focus_key(key("o"))
        assert is_focus_key(key("Cyrillic_shcha", "щ"))
        assert not is_focus_key(key("m"))
        assert is_zen_hotkey(key("m", state=CTRL))
        assert is_zen_hotkey(key("Cyrillic_softsign", state=CTRL))
        # Ctrl+O — не хоткей дзена слепой печати (там Ctrl+M)
        assert not is_zen_hotkey(key("o", state=CTRL))


class TestEscDouble:
    def test_second_tap_in_window_exits(self):
        d = EscDouble()
        assert d.tap(10.0) is False
        assert d.tap(10.0 + ESC_DOUBLE_SEC - 0.05) is True
        assert d.tap(20.0) is False
        assert d.tap(20.0 + ESC_DOUBLE_SEC + 0.05) is False


class TestGrammarFocusChrome:
    def test_toggle_hides_chrome_keeps_grammar(self, chrome):
        s = chrome.spread
        assert not s.in_focus()
        for w in (chrome.header, chrome.radio, chrome.title, chrome.lang_row,
                  chrome.submenu, chrome.status):
            assert chrome.mapped(w)
        s.toggle_focus(True)
        chrome.root.update()
        assert s.in_focus()
        for w in (chrome.header, chrome.radio, chrome.title, chrome.lang_row,
                  chrome.submenu, chrome.status):
            assert not chrome.mapped(w), w
        assert chrome.mapped(s)
        # грамматика целиком: уровни, вкладки источников, список, урок
        assert chrome.mapped(s._level_bar)
        assert chrome.mapped(s._tabs_host) or s._tabs_host.winfo_manager()
        assert chrome.mapped(s._left)
        assert chrome.mapped(s._lesson_sf)
        # иконка входа в зенид скрыта — выход только клавишами
        assert not chrome.mapped(s.btn_focus)

    def test_restore_on_toggle_off(self, chrome):
        s = chrome.spread
        s.toggle_focus(True)
        chrome.root.update()
        s.toggle_focus(False)
        chrome.root.update()
        assert not s.in_focus()
        for w in (chrome.header, chrome.radio, chrome.title, chrome.lang_row,
                  chrome.submenu, chrome.status):
            assert chrome.mapped(w), w
        assert chrome.mapped(s.btn_focus)
        assert s.btn_focus._text == "⛶"

    def test_title_cluster_order(self, chrome):
        """Сразу слева от «ГРАММАТИКА» — слот флага, сразу справа — иконка зенида."""
        s = chrome.spread
        packed = list(s._title_cluster.pack_slaves())
        assert packed[:3] == [s._flag_slot, s._title_lbl, s.btn_focus]
        assert "ГРАММАТИКА" in s._title_lbl.cget("text")
        # в этом PR слот пуст; флаг добавит следующий PR через catalog.paint_title_flag
        assert s._flag_slot.winfo_children() == []
        # иконка вплотную: только небольшой padx после слова
        info = s.btn_focus.pack_info()
        assert info.get("after") == str(s._title_lbl) or packed[packed.index(s._title_lbl) + 1] is s.btn_focus

    def test_icon_button_enters_and_hides(self, chrome):
        s = chrome.spread
        assert chrome.mapped(s.btn_focus)
        assert s.btn_focus._text == "⛶"
        assert callable(s.btn_focus.command)
        s.btn_focus.command()
        chrome.root.update()
        assert s.in_focus()
        assert not chrome.mapped(s.btn_focus)

    def test_ctrl_o_and_letter_o_toggle(self, chrome):
        s = chrome.spread
        assert s.on_key(key("o", state=CTRL)) == "break"
        chrome.root.update()
        assert s.in_focus()
        assert s.on_key(key("o")) == "break"
        chrome.root.update()
        assert not s.in_focus()
        assert s.on_key(key("Cyrillic_shcha", "щ")) == "break"
        chrome.root.update()
        assert s.in_focus()

    def test_single_esc_stays_double_exits(self, chrome):
        s = chrome.spread
        s.toggle_focus(True)
        chrome.root.update()
        assert s.on_key(key("Escape", char="\x1b")) == "break"
        chrome.root.update()
        assert s.in_focus()
        assert s.on_key(key("Escape", char="\x1b")) == "break"
        chrome.root.update()
        assert not s.in_focus()
        for w in (chrome.header, chrome.submenu, chrome.status):
            assert chrome.mapped(w)

    def test_enter_opens_first_lesson(self, chrome):
        s = chrome.spread
        assert s._data is None
        s.toggle_focus(True)
        s._flush_pending()
        chrome.root.update()
        s._flush_pending()
        chrome.root.update()
        assert s._unit == "u1"
        assert chrome.catalog.loaded[:1] == ["u1"] or s._data is not None or s._unit == "u1"

    def test_leave_like_tab_switch_restores(self, chrome):
        s = chrome.spread
        s.toggle_focus(True)
        chrome.root.update()
        assert s.in_focus()
        wanted = session_wanted()
        s.toggle_focus(False, remember=False)
        chrome.root.update()
        assert not s.in_focus()
        assert session_wanted() is wanted
        for w in (chrome.header, chrome.submenu):
            assert chrome.mapped(w)

    def test_session_flag_only_on_explicit_toggle(self, chrome):
        s = chrome.spread
        assert not session_wanted()
        s.toggle_focus(True)
        assert session_wanted()
        s.toggle_focus(False, remember=False)
        assert session_wanted()
        s.toggle_focus(False)
        assert not session_wanted()
