"""Флаги у заголовка грамматики: UK слева для английского, Германия для немецкого."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina import pilots
from stamina.english.pages_grammar import GrammarPage
from stamina.english.progress import Progress
from stamina.grammar_ui.flags import DE_BLACK, DE_GOLD, DE_RED, UK_BLUE, UK_RED, UK_WHITE, paint_title_flag
from stamina.languages.core.progress import LanguageProgress
from stamina.languages.grammar_page import build_grammar_page
from stamina.languages.plugins.de import GermanPlugin


def _colors(canvas: tk.Canvas) -> set[str]:
    found = set()
    for item in canvas.find_all():
        typ = canvas.type(item)
        keys = ("fill",) if typ == "line" else ("fill", "outline")
        for key in keys:
            try:
                val = canvas.itemcget(item, key)
            except tk.TclError:
                continue
            if val:
                found.add(val.upper())
    return found


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.withdraw()
    try:
        yield r
    finally:
        r.destroy()


class TestFlagDrawing:
    def test_german_stripes(self, root):
        c = paint_title_flag(root, "de")
        cols = _colors(c)
        assert DE_BLACK.upper() in cols
        assert DE_RED.upper() in cols
        assert DE_GOLD.upper() in cols
        assert not isinstance(c, tk.Label)

    def test_uk_union_jack(self, root):
        c = paint_title_flag(root, "gb")
        cols = _colors(c)
        assert UK_BLUE.upper() in cols
        assert UK_RED.upper() in cols
        assert UK_WHITE.upper() in cols

    def test_unknown_code_raises(self, root):
        with pytest.raises(ValueError):
            paint_title_flag(root, "us")


class TestTitlePlacement:
    def test_english_uk_flag_left_of_title_icon_right(self, tmp_path):
        try:
            r = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        try:
            ctx = SimpleNamespace(
                progress=Progress(path=tmp_path / "en.json", app=None),
                audio_button=None, status=lambda *a, **k: None,
            )
            page = GrammarPage(r, ctx)
            page.pack()
            r.update()
            packed = list(page._title_cluster.pack_slaves())
            assert packed[:3] == [page._flag_slot, page._title_lbl, page.btn_focus]
            kids = page._flag_slot.winfo_children()
            assert len(kids) == 1 and isinstance(kids[0], tk.Canvas)
            cols = _colors(kids[0])
            assert UK_BLUE.upper() in cols and UK_RED.upper() in cols
            assert "ГРАММАТИКА" in page._title_lbl.cget("text")
        finally:
            r.destroy()

    def test_german_flag_left_of_title(self, tmp_path):
        try:
            r = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        pilots.reset_root(tmp_path)
        try:
            pilot = pilots.create("FlagTest", accent="amber")
            pilots.activate(pilot["id"])
            progress = LanguageProgress(pilots.pilot_dir(pilot["id"]), "de")
            page = build_grammar_page(r, GermanPlugin(), progress, None)
            r.update()
            s = page.spread
            packed = list(s._title_cluster.pack_slaves())
            assert packed[:3] == [s._flag_slot, s._title_lbl, s.btn_focus]
            kids = s._flag_slot.winfo_children()
            assert len(kids) == 1 and isinstance(kids[0], tk.Canvas)
            cols = _colors(kids[0])
            assert DE_BLACK.upper() in cols and DE_RED.upper() in cols and DE_GOLD.upper() in cols
            assert UK_BLUE.upper() not in cols
        finally:
            try:
                page.destroy()
            except Exception:
                pass
            r.destroy()
            pilots.reset_root(None)
