"""НАБОРЫ: каждая вкладка хаба должна быть реально показана, а не только создана.

Ошибка, которую ловим: страницы лежали в кадре-держателе без pack() — хаб
рисовал вкладки и подсказку, а тело оставалось пустым.
"""
import tkinter as tk

import pytest

from stamina.english.pages_setshub import SetsHubPage
from stamina.english.progress import Progress
from stamina.english.vocab import Vocab


class Ctx:
    def __init__(self, tmp_path) -> None:
        self.progress = Progress(tmp_path / "english.json")
        self.vocab = Vocab()
        self.pages = {}
        self.app = None

    def status(self, *a, **k):
        pass

    def start_session(self, *a, **k):
        pass

    def show(self, *a, **k):
        pass

    def open_book_cards(self, *a, **k):
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
