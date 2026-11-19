# -*- coding: utf-8 -*-
"""Прокрутка ScrollFrame на Linux (Button-4/5) и Windows/macOS (MouseWheel).

Проверяем classic без alt_ui: свои привязки и общий wheel_router.install
(как в Cockpit), без двойного шага, видимую полосу в узкой колонке и
клавиши PgUp/PgDn/Home/End на развороте грамматики.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina import pilots, wheel_router
from stamina.english.ui import ScrollFrame


@pytest.fixture
def root():
    wheel_router._INSTALLED.clear()
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.geometry("900x500+0+0")
    r.update()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass
    wheel_router._INSTALLED.clear()


def _fill(sf, rows: int = 40, text: str = "row") -> None:
    for i in range(rows):
        tk.Label(sf.inner, text=f"{text} {i}", font=("TkDefaultFont", 14)).pack(anchor="w")
    sf.update_idletasks()


def _frac(sf) -> float:
    return float(sf.canvas.yview()[0])


def _warp(widget, x: int = 20, y: int = 30) -> None:
    widget.update_idletasks()
    widget.event_generate("<Enter>", x=x, y=y)
    widget.event_generate("<Motion>", warp=True, x=x, y=y)
    widget.update()


def test_linux_button5_scrolls_without_router(root):
    """Classic без роутера: реальное Linux-колесо — Button-4/5."""
    assert not wheel_router.installed(root)
    sf = ScrollFrame(root)
    sf.pack(fill=tk.BOTH, expand=True)
    _fill(sf)
    root.update()
    assert sf.inner.winfo_height() > sf.canvas.winfo_height()
    _warp(sf)
    assert root.bind_all("<Button-5>")
    assert root.bind_all("<Button-4>")
    before = _frac(sf)
    child = sf.inner.winfo_children()[2]
    for _ in range(4):
        child.event_generate("<Button-5>")
        root.update()
    assert _frac(sf) > before
    mid = _frac(sf)
    for _ in range(4):
        child.event_generate("<Button-4>")
        root.update()
    assert _frac(sf) < mid


def test_windows_mousewheel_delta_and_small_macos_delta(root):
    """MouseWheel: ±120 (Windows) и малый delta (тачпад / macOS) дают шаг, 0 — нет."""
    sf = ScrollFrame(root)
    sf.pack(fill=tk.BOTH, expand=True)
    _fill(sf)
    root.update()
    _warp(sf)
    child = sf.inner.winfo_children()[2]
    child.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert _frac(sf) > 0
    sf.top()
    root.update()
    child.event_generate("<MouseWheel>", delta=-30)  # |delta| < 120
    root.update()
    assert _frac(sf) > 0
    sf.top()
    root.update()
    child.event_generate("<MouseWheel>", delta=0)
    root.update()
    assert _frac(sf) == 0


def test_router_install_scrolls_once_not_twice(root):
    """Как в classic Cockpit: роутер стоит, ScrollFrame не вешает свой bind_all — шаг один."""
    wheel_router.install(root)
    sf = ScrollFrame(root)
    sf.pack(fill=tk.BOTH, expand=True)
    _fill(sf)
    root.update()
    _warp(sf)
    # свои глобальные привязки не ставим — иначе двойной шаг
    assert not sf.bind("<MouseWheel>")
    assert not sf.bind("<Button-5>")
    child = sf.inner.winfo_children()[2]
    child.event_generate("<Button-5>")
    root.update()
    stepped = _frac(sf)
    assert stepped > 0
    sf.top()
    root.update()
    child.event_generate("<MouseWheel>", delta=-120)
    root.update()
    wheeled = _frac(sf)
    assert wheeled > 0
    sf.top()
    root.update()
    sf.canvas.yview_scroll(3, "units")
    one = _frac(sf)
    sf.top()
    root.update()
    sf.canvas.yview_scroll(6, "units")
    two = _frac(sf)
    assert abs(wheeled - one) < 1e-6
    assert abs(stepped - one) < 1e-6
    assert two > one + 1e-6


def test_scrollbar_mapped_in_narrow_column(root):
    """Полоса упакована до холста и видна в узкой колонке при переполнении."""
    host = tk.Frame(root, width=180, height=260)
    host.pack_propagate(False)
    host.pack(side=tk.LEFT)
    sf = ScrollFrame(host)
    sf.pack(fill=tk.BOTH, expand=True)
    _fill(sf, rows=50)
    root.update()
    slaves = list(sf.pack_slaves())
    assert slaves[0] is sf.bar
    assert slaves[1] is sf.canvas
    assert sf.bar.winfo_manager() == "pack"
    assert sf.bar.winfo_ismapped()
    assert sf.bar.winfo_width() > 1
    assert sf.inner.winfo_height() > sf.canvas.winfo_height()


def _pump(spread, root, seconds: float = 3.0) -> None:
    import time
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            spread._flush_pending()
        except Exception:
            pass
        root.update()
        if "list" not in spread._jobs and "lesson" not in spread._jobs:
            if spread._data is not None or spread._rows:
                root.update()
                return
        time.sleep(0.04)
    try:
        spread._flush_pending()
    except Exception:
        pass
    root.update()


def test_grammar_left_bar_and_page_keys(root, tmp_path):
    """Немецкая грамматика: полоса списка видна; PgUp/PgDn/Home/End крутят урок, не поле ввода."""
    from stamina.languages.core.progress import LanguageProgress
    from stamina.languages.grammar_page import build_grammar_page
    from stamina.languages.plugins.de import GermanPlugin

    pilots.reset_root(tmp_path)
    pilot = pilots.create("Tester", accent="amber")
    pilots.activate(pilot["id"])
    try:
        page = build_grammar_page(root, GermanPlugin(), LanguageProgress(pilots.pilot_dir(pilot["id"]), "de"), None)
        root.update()
        page._show_lessons("A1")
        _pump(page.spread, root)
        assert page.level_lessons
        page._open_lesson(page.level_lessons[0])
        _pump(page.spread, root, 4.0)
        spread = page.spread
        left, right = spread._list_sf, spread._lesson_sf
        root.update()
        assert left.inner.winfo_height() > 1
        # 18 уроков A1 в низкой колонке — полоса должна быть на экране
        assert left.bar.winfo_manager() == "pack"
        assert left.bar.winfo_ismapped()
        assert left.bar.winfo_width() > 1
        assert right.inner.winfo_height() > right.canvas.winfo_height()

        _warp(right.canvas, 40, 80)
        right.canvas.focus_set()
        right.top()
        root.update()
        assert _frac(right) == 0
        right.canvas.event_generate("<Next>")
        root.update()
        assert _frac(right) > 0
        after_next = _frac(right)
        right.canvas.event_generate("<Prior>")
        root.update()
        assert _frac(right) < after_next
        right.canvas.event_generate("<End>")
        root.update()
        assert _frac(right) > 0.5
        right.canvas.event_generate("<Home>")
        root.update()
        assert _frac(right) == 0

        # фокус в Entry — Home/End не двигают урок
        entries = []

        def walk(w):
            try:
                if w.winfo_class() == "Entry":
                    entries.append(w)
                for ch in w.winfo_children():
                    walk(ch)
            except tk.TclError:
                pass

        walk(right.inner)
        if not entries:
            pytest.skip("в уроке нет поля ввода")
        field = entries[0]
        # прокрутить, чтобы поле точно можно было сфокусировать
        field.focus_set()
        root.update()
        _warp(right.canvas, 40, 80)
        field.event_generate("<End>")
        root.update()
        assert _frac(right) == 0
        page.destroy()
    finally:
        pilots.reset_root(None)


def test_english_lesson_page_keys_and_bar(root, tmp_path):
    from stamina.english.pages_grammar import GrammarPage
    from stamina.english.progress import Progress

    ctx = SimpleNamespace(progress=Progress(path=tmp_path / "english.json"),
                          status=lambda *a, **k: None, audio_button=None)
    page = GrammarPage(root, ctx)
    page.pack(fill=tk.BOTH, expand=True)
    page.refresh()
    _pump(page, root, 5.0)
    first = page.catalog.first_unit(page._level)
    assert first is not None
    page._open_unit(first)
    _pump(page, root, 5.0)
    left, right = page._list_sf, page._lesson_sf
    root.update()
    assert left.bar.winfo_ismapped() and left.bar.winfo_width() > 1
    assert right.inner.winfo_height() > right.canvas.winfo_height()
    _warp(right.canvas, 40, 80)
    right.canvas.focus_set()
    right.top()
    root.update()
    right.canvas.event_generate("<End>")
    root.update()
    assert _frac(right) > 0.5
    right.canvas.event_generate("<Home>")
    root.update()
    assert _frac(right) == 0
    page.destroy()
