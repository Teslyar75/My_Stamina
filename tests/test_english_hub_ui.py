"""НАБОРЫ: каждая вкладка хаба должна быть реально показана, а не только создана.

Ошибка, которую ловим: страницы лежали в кадре-держателе без pack() — хаб
рисовал вкладки и подсказку, а тело оставалось пустым.
"""
import tkinter as tk

import pytest

from stamina.english.pages_setshub import SetsHubPage
from stamina.english.progress import Progress
from stamina.english.vocab import Vocab
from stamina.english import cefr


class Ctx:
    def __init__(self, tmp_path) -> None:
        self.progress = Progress(tmp_path / "english.json")
        self.vocab = Vocab()
        self.pages = {}
        self.app = None
        self.shown = []
        self.statuses = []
        self.sessions = []

    def status(self, text="", color=None, *a, **k):
        self.statuses.append((text, color))

    def start_session(self, *a, **k):
        self.sessions.append((a, k))

    def show(self, name=None, *a, **k):
        self.shown.append(name)

    def open_book_cards(self, *a, **k):
        pass

    def open_word(self, *a, **k):
        pass

    def changed(self):
        pass

    def audio_button(self, parent, label, text_fn, **kw):
        from stamina.hud import HudButton
        return HudButton(parent, label, lambda: None, **kw)


def test_hub_tabs_are_packed_and_visible(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1400x800+30+30")
        hub = SetsHubPage(root, Ctx(tmp_path))
        hub.pack(fill="both", expand=True)
        root.update()
        pages = {"std": hub.standard, "cefr": hub.cefr, "verbs": hub.verbs, "book": hub.book}
        for key, page in pages.items():
            hub.show_tab(key)
            root.update()
            assert page.winfo_manager() == "pack", f"{key}: страница не упакована"
            assert page.winfo_height() > 100, f"{key}: высота {page.winfo_height()}px"
        assert hub.cefr.items, "CEFR A1 не загрузился"
        assert hub.cefr.tiles, "CEFR не построил плитки"
    finally:
        root.destroy()

def test_cefr_pages_by_24(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1400x800+30+30")
        hub = SetsHubPage(root, Ctx(tmp_path))
        hub.pack(fill="both", expand=True)
        root.update()
        hub.show_tab("cefr")
        hub.cefr.select("A1")
        root.update()
        assert hub.cefr.COLS * hub.cefr.ROWS == 24
        assert len(hub.cefr.tiles) == 24
        assert "1 /" in hub.cefr.pg.cget("text")
        hub.cefr.go(1)
        root.update()
        assert hub.cefr.page == 1
        assert 0 < len(hub.cefr.tiles) <= 24
    finally:
        root.destroy()


def test_cefr_blocks_unlock_after_work(tmp_path):
    """Порции по 50: следующая грузится сама, когда закрыта текущая."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1400x800+30+30")
        ctx = Ctx(tmp_path)
        hub = SetsHubPage(root, ctx)
        hub.pack(fill="both", expand=True)
        root.update()
        hub.show_tab("cefr")
        page = hub.cefr
        page.select("A1")
        root.update()

        total = len(cefr.prepared("A1"))
        sizes = [len(b) for b in page.blocks]
        assert sizes[0] == cefr.BLOCK_SIZE
        assert sum(sizes) == total
        assert page.block == 0
        assert page.block_btns[1]._text.endswith("закр")

        page.pick_block(1)
        assert page.block == 0, "закрытый блок не должен открываться"
        assert any("откроется" in s[0] for s in ctx.statuses)

        first = {w["slug"] for w in page.blocks[0]}
        page._done = lambda slug: slug in first
        page.refresh()
        root.update()
        assert page.max_open == 1
        assert page.block == 1, "после закрытия блока 1 сразу грузится блок 2"
        assert len(page.items) == sizes[1]
        assert any("Блок 1 пройден" in s[0] for s in ctx.statuses)

        page.learn()
        assert len(ctx.sessions[-1][1]["ids"]) == sizes[1]

        page._done = lambda slug: True
        page.refresh()
        root.update()
        assert page.level == "A2", "после уровня A1 открывается A2"
        assert page.blocks and len(page.blocks[0]) == len(cefr.prepared("A2"))
    finally:
        root.destroy()


def test_cefr_fits_short_window(tmp_path):
    """На низком окне нижняя панель не уезжает, рядов меньше, плитки не в полоску."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1350x800+20+20")
        hub = SetsHubPage(root, Ctx(tmp_path))
        hub.pack(fill="both", expand=True)
        root.update()
        hub.show_tab("cefr")
        root.update()
        page = hub.cefr

        root.geometry("1350x500")
        root.update()
        assert page.rows == 2
        assert page.pg.winfo_ismapped(), "листалка уехала за край"
        assert len(page.tiles) == page.COLS * 2
        assert page.tiles[0].winfo_height() >= 60

        root.geometry("1350x600")
        root.update()
        assert page.rows == 3
        assert page.pg.winfo_ismapped()
        assert len(page.tiles) == page.COLS * 3
    finally:
        root.destroy()


def test_open_set_switches_screen_and_set(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1400x800+30+30")
        ctx = Ctx(tmp_path)
        hub = SetsHubPage(root, ctx)
        hub.pack(fill="both", expand=True)
        root.update()
        hub.open_set("top-3000")
        root.update()
        assert hub.standard.f["set"] == "top-3000"
        assert ctx.shown and ctx.shown[-1] == "sets"
        hub.open_cefr("A2")
        root.update()
        # A2 закрыт до прохождения A1 — уровни идут последовательно
        assert hub.cefr.level == "A1"
        assert hub.cefr.lv_btns["A2"]._text.endswith("закр")
        assert ctx.statuses and "A1" in ctx.statuses[-1][0]
        assert ctx.shown[-1] == "sets"
    finally:
        root.destroy()


def test_overview_plates_fit_the_window(tmp_path):
    """Плашки секторов и частотных наборов не обрезаются на низком окне."""
    from stamina.english.pages_main import OverviewPage

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        root.attributes("-alpha", 0.0)
        root.geometry("1350x600+20+20")
        ctx = Ctx(tmp_path)
        ov = OverviewPage(root, ctx)
        ov.pack(fill="both", expand=True)
        root.update()
        assert len(ov.cards) == 3
        assert len(ov.freq_cards) == 4
        bottom = ov.sec.winfo_y() + ov.sec.winfo_height()
        assert bottom <= ov.left_col.winfo_height() + 1
        assert all(c.winfo_ismapped() for c in ov.freq_cards)
        # совсем низкое окно: книга убирается, ряд плашек остаётся целиком
        root.geometry("1350x500")
        root.update()
        assert not ov.book_panel.winfo_manager()
        assert not ov.footnote.winfo_manager()
        bottom = ov.sec.winfo_y() + ov.sec.winfo_height()
        assert bottom <= ov.left_col.winfo_height() + 1
        assert all(c.winfo_ismapped() for c in ov.freq_cards)
    finally:
        root.destroy()
