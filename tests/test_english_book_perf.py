"""«ИЗ КНИГИ»: открытие не вешает окно (тяжёлое — в фоне), кэш, доступ для продвинутых."""
import random
import time
import tkinter as tk

import pytest

from stamina import library as libmod
from stamina import pilots, portal_stats
from stamina.english import access
from stamina.english import book_sentences as bs
from stamina.english.progress import Progress
from stamina.speedread import rsvp

W = "the captain said that ship would sail across dark water before morning light".split()


def _text(n, seed=1):
    r = random.Random(seed)
    return " ".join(" ".join(r.choice(W) for _ in range(r.randint(6, 14))).capitalize() + "."
                    for _ in range(n))


def _lib(tmp_path, books=2, sents=6000):
    lib = libmod.Library(tmp_path / "library")
    for k in range(books):
        tid = lib.add(_text(sents, k), title=f"Book {k}")
        tid = tid if isinstance(tid, str) else tid["id"]
        m = lib.meta(tid)
        m["lang"] = "en"
        m.setdefault("positions", {})["reading"] = {"word": 10 ** 7}
        lib.save_meta(m)
    return lib


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    bs._SYNC_MEMO.clear()
    bs._EXTRACT.clear()
    bs._BG.clear()
    monkeypatch.setattr(portal_stats, "average_pace", lambda *a, **k: None)
    yield
    pilots._active = None


# --- корень проблемы: токенизация была O(n²) на длинной строке -----------------
def test_tokenize_is_linear_on_one_long_line():
    text = _text(20000)                          # ~200 тыс. слов в одну строку
    t0 = time.perf_counter()
    words = rsvp.tokenize(text)
    assert time.perf_counter() - t0 < 3.0
    assert words and words[0].text


def test_tokenize_keeps_chapter_and_sentence_marks():
    words = rsvp.tokenize("Chapter 1\nIt was cold. We left.\n\nPart Two\nEnd")
    marks = {w.text: (w.chapter, w.sent_end, w.para_end) for w in words}
    assert marks["Chapter"][0] and marks["Part"][0]
    assert not marks["It"][0]
    assert marks["cold."][1] and marks["left."][2]


# --- кэш между запусками -----------------------------------------------------
def test_sync_book_uses_persistent_cache(tmp_path, monkeypatch):
    lib = _lib(tmp_path, books=1, sents=300)
    p = Progress(tmp_path / "english.json")
    bs.sync_all(p, lib)
    n = sum(len(b["sentences"]) for b in bs.ensure_store(p)["books"].values())
    assert n > 0
    bs._SYNC_MEMO.clear()                        # «новый запуск»
    p2 = Progress(tmp_path / "english.json")
    monkeypatch.setattr(bs, "extract_sentences", lambda *a: pytest.fail("должно браться из кэша"))
    assert bs.sync_all(p2, lib)[1] == n


# --- фон: вызов возвращается сразу, результат приходит через after ------------
def _tk():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.withdraw()
    return root


def _pump(root, cond, timeout=60.0):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        root.update()
        time.sleep(0.01)
    assert cond()


def test_sync_in_background_returns_quickly(tmp_path):
    lib = _lib(tmp_path)
    p = Progress(tmp_path / "english.json")
    root = _tk()
    try:
        got = []
        t0 = time.perf_counter()
        assert bs.sync_in_background(root, p, lambda: lib, lambda b, s: got.append((b, s)))
        assert time.perf_counter() - t0 < 0.5
        assert bs.busy(p)
        assert not bs.sync_in_background(root, p, lambda: lib, lambda b, s: got.append((b, s)))
        _pump(root, lambda: len(got) == 2)
        assert got[0][0] == 2 and got[0][1] > 1000 and not bs.busy(p)
    finally:
        root.destroy()


class Ctx:
    def __init__(self, tmp_path):
        self.progress = Progress(tmp_path / "english.json")
        self.app = None
        self.shown, self.statuses = [], []
        self.page = None

    def status(self, text="", color=None, *a, **k):
        self.statuses.append(text)

    def show(self, name=None, *a, **k):
        self.shown.append(name)
        if self.page is not None:
            self.page.refresh()

    def changed(self):
        pass

    def sfx(self, *a, **k):
        pass


def test_open_book_screen_is_fast_and_heavy_work_deferred(tmp_path, monkeypatch):
    from stamina.english.pages_book import BookCardsPage
    lib = _lib(tmp_path)
    monkeypatch.setattr(access, "book_access", lambda *a, **k: (True, ""))
    root = _tk()
    try:
        ctx = Ctx(tmp_path)
        page = BookCardsPage(root, ctx)
        ctx.page = page
        page._lib = lambda: lib
        root.update()
        t0 = time.perf_counter()
        page.focus_book(None)
        dt = time.perf_counter() - t0
        assert dt < 0.5, f"открытие {dt:.2f} c"
        assert ctx.shown[-1] == "book" and bs.busy(ctx.progress)
        _pump(root, lambda: not bs.busy(ctx.progress))
        assert bs.list_books(ctx.progress)
    finally:
        root.destroy()


# --- доступ: только продвинутым, капитану всегда ------------------------------
class App:
    def __init__(self, cpms):
        self.store = type("S", (), {"stats": {"runs": [{"cpm": c} for c in cpms]}})()


def test_typing_wpm_from_runs_and_portal(monkeypatch):
    assert access.typing_wpm(None) == 0
    assert access.typing_wpm(App([200, 300])) == 50          # 250 cpm / 5
    monkeypatch.setattr(portal_stats, "average_pace", lambda *a, **k: 70)
    assert access.typing_wpm(App([200])) == 70


def test_book_access_needs_speed_and_level(tmp_path, monkeypatch):
    p = Progress(tmp_path / "english.json")
    lvl = {"ok": False}
    monkeypatch.setattr(access, "level_reached", lambda pr, lv: lvl["ok"])
    ok, hint = access.book_access(p, App([100]))               # 20 сл/мин, уровня нет
    assert not ok and "🔒" in hint and "35" in hint and "B1.1" in hint
    ok, _ = access.book_access(p, App([250]))                  # скорость есть, уровня нет
    assert not ok
    lvl["ok"] = True
    assert access.book_access(p, App([250]))[0]
    assert not access.book_access(p, App([100]))[0]            # уровень есть, скорости нет
    p.settings["book_min_wpm"] = 15                            # пороги — настройки
    assert access.book_access(p, App([100]))[0]


def test_book_level_setting_and_real_rule(tmp_path):
    p = Progress(tmp_path / "english.json")
    assert access.book_min_level(p) == "B1.1"
    assert not access.level_reached(p, "B1.1")                  # новичок: B1 закрыт
    p.settings["book_min_level"] = "A1"
    assert access.level_reached(p, access.book_min_level(p))


def test_captain_always_has_book(tmp_path, monkeypatch):
    pilots.reset_root(tmp_path / "pilots")
    try:
        cap = pilots.create("Captain")
        pilots.set_role(cap["id"], pilots.CAPTAIN)
        pilots._active = pilots.get(cap["id"])
        p = Progress(tmp_path / "english.json")
        assert access.book_access(p, None) == (True, "")
    finally:
        pilots._active = None
        pilots.reset_root()


def test_locked_page_shows_lock_and_starts_nothing(tmp_path, monkeypatch):
    from stamina.english.pages_book import BookCardsPage
    monkeypatch.setattr(access, "book_access", lambda *a, **k: (False, "🔒 hint"))
    root = _tk()
    try:
        ctx = Ctx(tmp_path)
        page = BookCardsPage(root, ctx)
        ctx.page = page
        page._lib = lambda: pytest.fail("закрытый раздел не должен читать библиотеку")
        page.focus_book(None)
        root.update()
        texts = [w.cget("text") for w in page.body.winfo_children() if isinstance(w, tk.Label)]
        assert any("🔒" in t for t in texts) and "🔒 hint" in ctx.statuses
        assert not bs.busy(ctx.progress)
    finally:
        root.destroy()
