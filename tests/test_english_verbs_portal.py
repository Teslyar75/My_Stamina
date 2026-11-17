# -*- coding: utf-8 -*-
"""Портал спряжения: клавиша O в любой раскладке, таблица 12×5×3, проверка речи в плитке."""
import time
import tkinter as tk

import pytest

from stamina.english import conjugation as cj
from stamina.english import verbs
from stamina.english import verbs_portal as vp
from stamina.english.progress import Progress


class Key:
    """Событие клавиши без Tk: keysym/char/keycode — как у настоящего Event."""

    def __init__(self, keysym="", char="", keycode=0, widget=None, state=0):
        self.keysym, self.char, self.keycode = keysym, char, keycode
        self.widget, self.state = widget, state


# --- чистая часть: клавиша и таблица ----------------------------------------

def test_portal_key_opens_in_any_layout():
    # латиница в обе стороны, русская Щ на той же физической кнопке и голый код клавиши
    assert vp.is_portal_key(Key("o"))
    assert vp.is_portal_key(Key("O"))
    assert vp.is_portal_key(Key("Cyrillic_shcha"))
    assert vp.is_portal_key(Key("", "щ"))
    assert vp.is_portal_key(Key("", "", 79))            # та же кнопка при любой раскладке
    assert not vp.is_portal_key(Key("m"))
    assert not vp.is_portal_key(Key("", "", 77))


def test_fit_cols_never_squeezes_a_tile():
    # плитка английского времени просит ~440 px: в окно 1540 встают три, в 1920 — четыре
    assert vp.fit_cols(1540, 440) == 3
    assert vp.fit_cols(1920, 440) == 4
    assert vp.fit_cols(800, 440) == 1
    assert vp.fit_cols(3000, 440) == 4                  # больше четырёх в ряд не ставим
    assert vp.fit_cols(1600, 300) == 4                  # мелкая плитка — четыре в ряд


def test_plan_picks_comfort_that_fits_and_never_clips():
    sizes = [(440, 200), (400, 180), (380, 150), (340, 130)]
    # 1500×600: крупные в три колонки не влезают по высоте, а плотная встаёт в 4×3
    assert vp.plan(1500, 600, sizes) == (3, 4, 3)
    # широкий и высокий экран — самая крупная плотность и четыре колонки
    assert vp.plan(1920, 1000, sizes) == (0, 4, 3)
    # совсем маленькое окно — самая плотная и прокрутка, но все 12 на месте
    level, cols, rows = vp.plan(500, 200, sizes)
    assert level == 3 and cols * rows >= 12


def test_densities_go_from_comfort_to_dense():
    assert vp.DENSITIES[0]["cells"] > vp.DENSITIES[-1]["cells"]
    assert vp.DENSITIES[0]["btn"] > vp.DENSITIES[-1]["btn"]


def test_portal_table_has_all_tenses_persons_modes():
    data = vp.portal_cells(verbs.find("go"))
    assert [d["key"] for d in data] == [t[0] for t in verbs.TENSES]
    assert len(data) == 12
    for tile in data:
        assert set(tile["cells"]) == set(vp.MODE_KEYS) == {"question", "affirmative", "negative"}
        for mode, by_person in tile["cells"].items():
            assert list(by_person) == cj.PERSON_KEYS
            for text in by_person.values():
                assert text and text[0].isupper()       # ячейка — самостоятельная фраза
                if mode == "question":
                    assert text.endswith("?")
                if mode == "negative":
                    assert " not" in text or "n't" in text


def test_portal_uses_real_pack_forms():
    go = {d["key"]: d for d in vp.portal_cells(verbs.find("go"))}
    assert go["past_simple"]["cells"]["question"]["he"] == "Did he go?"
    assert go["present_perfect"]["cells"]["affirmative"]["I"] == "I have gone"
    write = {d["key"]: d for d in vp.portal_cells(verbs.find("write"))}
    assert write["past_simple"]["cells"]["affirmative"]["they"] == "They wrote"
    assert write["present_perfect"]["cells"]["negative"]["he"] == "He has not written"


def test_every_tile_keeps_tatoeba_example():
    for verb in verbs.entries()[:6]:
        for tile in vp.portal_cells(verb):
            ex = tile["example"]
            if ex:
                assert ex["en"] and ex["source"] == "tatoeba" and ex["source_id"]


# --- портал в живом Tk -------------------------------------------------------

class Ctx:
    def __init__(self, tmp_path):
        self.progress = Progress(tmp_path / "english.json")
        self.vocab = None
        self.spoken, self.sounds = [], []

    def status(self, *a, **k):
        pass

    def changed(self):
        pass

    def sfx(self, name):
        self.sounds.append(name)

    def say(self, text, slow=False, btn=None):
        self.spoken.append(text)

    def audio_button(self, parent, label, text_fn, **kw):
        from stamina.hud import HudButton
        return HudButton(parent, label, lambda: self.spoken.append(text_fn()), **kw)


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    from stamina import theme
    theme.init(r)                       # те же шрифты и масштаб, что в живом приложении
    r.attributes("-alpha", 0.0)
    r.geometry("1400x900+30+30")
    yield r
    r.destroy()


def _wait(root, ms=900):
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def test_portal_opens_on_o_and_closes_back(root, tmp_path):
    from stamina.english.pages_verbs import VerbsTab
    ctx = Ctx(tmp_path)
    tab = VerbsTab(root, ctx)
    tab.pack(fill="both", expand=True)
    root.update()
    assert not tab.portal_open()
    tab.on_key(Key("o"))
    _wait(root, 400)
    assert tab.portal_open()
    portal = tab.portal
    assert len(portal._tiles) == 12 and len(portal._cells) == 12
    assert portal.word_lbl.cget("text") == tab.slug
    portal.on_key(Key("Escape"))                        # Esc — назад
    _wait(root, 300)
    assert not tab.portal_open()


def test_portal_tile_speaks_and_checks_same_sentence(root, tmp_path):
    from stamina.english.pages_verbs import VerbsTab
    ctx = Ctx(tmp_path)
    tab = VerbsTab(root, ctx)
    tab.pack(fill="both", expand=True)
    root.update()
    tab.on_key(Key("o"))
    _wait(root, 400)
    portal = tab.portal
    portal.set_verb("go")                               # понятный глагол для проверки форм
    assert portal.sentence(4) == "I went"                # по умолчанию — I, утверждение
    portal.choose(4, "he", "question")                  # клик по ячейке выбирает фразу
    assert portal.sentence(4) == "Did he go?"
    assert "Did he go?" in portal.target_lbl.cget("text")
    portal.on_speech([], 85)                            # проверка качества чтения
    assert ctx.progress.data["verb_scores"][f"{portal.slug}:4"] == 85
    assert portal._badges[4].cget("text") == "85%"
    _wait(root, 1200)                                   # ≥80% — через паузу следующее время
    assert portal.active == 5
    tab.close_portal()                                  # оценка портала видна на вкладке
    assert tab._best(4) == 85


def test_portal_keys_move_person_and_mode(root, tmp_path):
    from stamina.english.pages_verbs import VerbsTab
    ctx = Ctx(tmp_path)
    tab = VerbsTab(root, ctx)
    tab.pack(fill="both", expand=True)
    root.update()
    tab.on_key(Key("o"))
    _wait(root, 400)
    portal = tab.portal
    portal.on_key(Key("down"))
    assert portal.pick[0] == ("you", "affirmative")
    portal.on_key(Key("right"))
    assert portal.pick[0] == ("you", "negative")
    portal.on_key(Key("up"))
    assert portal.pick[0] == ("I", "negative")
    portal.on_key(Key("Return"))
    assert ctx.spoken and ctx.spoken[-1] == portal.sentence(0)


def test_portal_is_elastic_and_never_hides_tiles(root, tmp_path):
    """Резиновая вёрстка: колонки по ширине, плотность по высоте; если не влезает — прокрутка."""
    from stamina.english.pages_verbs import VerbsTab
    ctx = Ctx(tmp_path)
    tab = VerbsTab(root, ctx)
    tab.pack(fill="both", expand=True)
    root.update()
    tab.on_key(Key("o"))
    _wait(root, 400)
    portal = tab.portal
    portal._fit(force=True)                             # пересчёт по фактическому размеру окна
    _wait(root, 400)
    cols, rows = portal._shape
    assert cols * rows >= 12                            # все 12 плиток в сетке
    assert len(portal._tiles) == 12
    need, have = portal.sf.inner.winfo_reqheight(), portal.sf.canvas.winfo_height()
    if need > have + 4:                                 # окно мало — обязана быть прокрутка
        assert portal.sf.bar.winfo_manager(), f"низ обрезан без прокрутки: {need} > {have}"
    else:
        assert not portal.sf.bar.winfo_manager()        # влезло — полоса не нужна
    # замер идёт от крупной плотности к плотной: чем плотнее, тем плитка ниже
    sizes = portal._probe_sizes()
    assert [h for _w, h in sizes] == sorted([h for _w, h in sizes], reverse=True)
    # окно поуже — портал пересобирается сам, плиток по-прежнему 12
    root.geometry("1000x700+0+0")
    _wait(root, 600)
    portal._fit(force=True)
    _wait(root, 400)
    assert len(portal._tiles) == 12
    assert portal._shape[0] <= cols

