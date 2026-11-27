"""Английский открывается из сетки языков тем же путём, что и остальные языки.

Раньше карточка en уводила на отдельный старый экраны english; теперь это обычная
карточка plugin-а: она собирает встроенный отсек с подстраницами (слова, миссии,
грамматика), как немецкий, французский, испанский и итальянский.
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


def test_english_card_uses_same_select_path(monkeypatch):
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
        # У карточки en обычный для всех языков обработчик: _select_language(code).
        assert english["locked"] is False
        scr._select_language("en")
        assert scr.current_lang == "en"
        assert app.shown == [], "английский не должен уводить на отдельный экран english"
    finally:
        root.destroy()


@pytest.mark.parametrize("code", ["en", "de", "fr", "es", "it"])
def test_all_languages_share_inplace_ui(monkeypatch, code):
    """Любая карточка, включая английский, собирает один и тот же встроенный отсек."""
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


def test_english_restores_subpage_like_other_languages(monkeypatch):
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

        scr.restore_place(Place(screen="languages", lang="en", sub="grammar"))
        assert scr.current_lang == "en"
        assert scr.current_page == "grammar"
    finally:
        root.destroy()
