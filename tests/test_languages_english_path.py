"""Английский открывается из сетки языков, но содержимое — его родной отсек.

Вход делается той же карточкой, что и у немецкого/французского, однако внутри
английского остаётся старый хаб «СТАНДАРТ · CEFR · ГЛАГОЛЫ · ИЗ КНИГИ»: общая
страница «Наборы» рассчитана на частотные наборы с суффиксом уровня и потому
английскому не подходит.
"""
from __future__ import annotations

import pytest


class _FakeApp:
    def __init__(self):
        self.shown = []

    def show(self, name):
        self.shown.append(name)


def _screen(root, monkeypatch, app):
    from stamina.languages import screen as screen_module

    monkeypatch.setattr(screen_module.pilots, "active", lambda: None)
    return screen_module.LanguagesScreen(root, app)


def test_english_card_leads_to_its_own_compartment(monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    app = _FakeApp()
    try:
        root.withdraw()
        scr = _screen(root, monkeypatch, app)
        codes = [entry["plugin"].code for entry in scr.lang_cards]
        assert codes.count("en") == 1
        english = next(entry for entry in scr.lang_cards if entry["plugin"].code == "en")
        assert english["locked"] is False
        scr._select_language("en")
        assert app.shown == ["english"], "карточка ведёт в родной отсек английского"
        assert scr.current_lang != "en", "общая страница «Наборы» для английского не строится"
        container = getattr(scr, "page_container", None)
        assert container is None or not container.winfo_children()
    finally:
        root.destroy()


@pytest.mark.parametrize("code", ["de", "fr", "es", "it"])
def test_other_languages_share_inplace_ui(monkeypatch, code):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    app = _FakeApp()
    try:
        root.withdraw()
        scr = _screen(root, monkeypatch, app)
        scr._select_language(code)
        assert scr.current_lang == code
        assert scr.current_page == "overview"
        assert scr.page_container.winfo_children(), "встроенная страница языка должна собраться"
        assert app.shown == []
    finally:
        root.destroy()


def test_english_place_does_not_rebuild_generic_page(monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    app = _FakeApp()
    try:
        root.withdraw()
        scr = _screen(root, monkeypatch, app)
        from stamina.nav_back import Place

        scr.restore_place(Place(screen="languages", lang="en", sub="sets"))
        assert app.shown == ["english"]
        assert scr.current_lang != "en"
        container = getattr(scr, "page_container", None)
        assert container is None or not container.winfo_children()
    finally:
        root.destroy()
