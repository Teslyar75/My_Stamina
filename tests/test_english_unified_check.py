# -*- coding: utf-8 -*-
"""Один стандарт проверки произношения: все экраны строят check.SpeechCheck (как сканер)."""
import ast
import pathlib
import time
import tkinter as tk

import pytest

import stamina.english as eng
from stamina.english import conjugation as cj, verbs
from stamina.english.check import SpeechCheck
from stamina.english.mic import MicPanel
from stamina.english.progress import Progress
from stamina.english.ui import MatchReadout

PKG = pathlib.Path(eng.__file__).parent
# сканер — эталонная раскладка (MicPanel справа, MatchReadout слева), его вёрстку
# ведёт отдельная ветка; check.SpeechCheck повторяет её один в один
REFERENCE = {"pages_main.py"}


def _calls(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return names


def _screens():
    out = []
    for p in sorted(PKG.glob("pages_*.py")):
        src = p.read_text(encoding="utf-8")
        if "def on_speech" in src:
            out.append(p)
    return out


def test_audit_every_check_screen_uses_shared_component():
    screens = _screens()
    names = {p.name for p in screens}
    assert {"pages_verbs.py", "pages_reference.py", "pages_book.py", "pages_warehouse.py",
            "pages_learn.py", "pages_main.py"} <= names
    for p in screens:
        calls = _calls(p)
        if p.name in REFERENCE:
            assert {"MicPanel", "MatchReadout"} <= calls
            continue
        assert "SpeechCheck" in calls, f"{p.name}: своя проверка вместо SpeechCheck"
        assert "MicPanel" not in calls and "MatchReadout" not in calls, f"{p.name}: ручная сборка блока"
        src = p.read_text(encoding="utf-8")
        if p.name in ("pages_verbs.py", "pages_reference.py"):   # таблицы времён — полностью на SpeechCheck
            assert "verdict(" not in src and "score_sentence(" not in src, p.name


class FakeASR:
    listening = False

    def available(self):
        return True

    def why_unavailable(self):
        return ""

    def stop(self):
        pass


class Ctx:
    def __init__(self, tmp_path, asr=False):
        self.progress = Progress(tmp_path / "english.json")
        self.vocab = None
        self.statuses, self.sounds = [], []
        if asr:
            self.asr = FakeASR()

    def status(self, *a, **k):
        self.statuses.append(a)

    def changed(self):
        pass

    def sfx(self, name):
        self.sounds.append(name)

    def audio_button(self, parent, label, text_fn, **kw):
        from stamina.hud import HudButton
        return HudButton(parent, label, lambda: None, **kw)


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.attributes("-alpha", 0.0)
    r.geometry("1400x900+30+30")
    yield r
    r.destroy()


def _wait(root, ms=1100):
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def test_component_layout_matches_scanner(root, tmp_path):
    ctx = Ctx(tmp_path, asr=True)
    c = SpeechCheck(root, ctx, lambda *a: None)
    c.pack(fill="both", expand=True)
    root.update()
    assert isinstance(c.mic, MicPanel) and isinstance(c.match, MatchReadout)
    assert c.mic.grid_info()["column"] == 1                     # микрофон — справа, на месте
    assert c.match.winfo_x() < c.mic.winfo_x()
    assert "M" in c.keys.cget("text") and "T" in c.keys.cget("text")
    assert c.evaluate("I go home", [], 90) == (90, None, "")
    assert c.match.data[0] == 90                                # то же «СОВПАДЕНИЕ: N%»
    c.hint_down("подсказка")
    assert c.hint.cget("text") == "подсказка"
    c.hint_up()
    assert c.hint.cget("text") == ""
    moved = []
    assert not c.judge(50, lambda: moved.append(1), lambda: True)
    assert c.judge(85, lambda: moved.append(1), lambda: True)
    _wait(root)
    assert moved == [1] and ctx.sounds == ["error", "click"]


class Key:
    def __init__(self, keysym, widget=None):
        self.keysym, self.widget = keysym, widget


def test_verbs_tab_uses_component_and_t_hint(root, tmp_path):
    from stamina.english.pages_verbs import VerbsTab
    tab = VerbsTab(root, Ctx(tmp_path))
    tab.pack(fill="both", expand=True)
    root.update()
    assert isinstance(tab.check, SpeechCheck)
    tab.on_key(Key("t"))
    assert tab._active_sent()["ru"] in tab.check.hint.cget("text")
    tab.on_key_up(Key("t"))
    assert tab.check.hint.cget("text") == ""
    tab.on_speech([], 40)
    assert tab.check.match.data[0] == 40
    _wait(root)
    assert tab.active_si == 0                                   # провал — остаёмся
    tab.on_speech([], 88)
    _wait(root)
    assert tab.active_si == 1                                   # ≥80% — следующее время


def test_reference_checks_form_then_tense(root, tmp_path):
    from stamina.english.pages_reference import ReferencePanel
    p = ReferencePanel(root, Ctx(tmp_path))
    p.pack(fill="both", expand=True)
    root.update()
    p.open_verb(verbs.pack_verb("go"))
    p.set_tense("past_simple")
    assert isinstance(p.check, SpeechCheck)
    p.on_speech([], 50)
    _wait(root)
    assert (p.tense, p.person_i) == ("past_simple", 0)
    p.on_speech([], 90)
    _wait(root)
    assert (p.tense, p.person_i) == ("past_simple", 1)          # следующая форма
    p.select_person(len(cj.PERSONS) - 1)
    p.on_speech([], 90)
    _wait(root)
    assert p.tense == cj.TENSE_KEYS[cj.TENSE_KEYS.index("past_simple") + 1] and p.person_i == 0
    p.on_key(Key("t"))
    assert "V2 went" in p.check.hint.cget("text")


# -- консолидация дублей ------------------------------------------------------------

def test_no_duplicate_hold_hint_or_timers():
    """Удержание подсказки — общий check.HoldGrab; авто-переход — общий advance_later."""
    for name in ("pages_book.py", "pages_warehouse.py"):
        src = (PKG / name).read_text(encoding="utf-8")
        calls = _calls(PKG / name)
        assert "HoldGrab" in calls, name
        assert "grab_set" not in calls and "_release_hint_grab" not in src, name
    book = (PKG / "pages_book.py").read_text(encoding="utf-8")
    assert "after(900" not in book and "advance_later(" in book


def test_practice_uses_unified_pass_rule():
    src = (PKG / "pages_learn.py").read_text(encoding="utf-8")
    assert "из 3" not in src and ">= (60" not in src
    assert "passed = std_passed(score)" in src


def test_hold_grab_press_release():
    root = tk.Tk()
    root.withdraw()
    try:
        log = []
        g = SpeechCheck.HoldGrab()
        b = tk.Button(root)
        b.command = "x"
        g.bind(b, lambda btn: (log.append("down"), g.take(btn)), lambda: (log.append("up"), g.release()))
        assert b.command is None
        assert b.bind("<ButtonPress-1>") and b.bind("<ButtonRelease-1>")

        class Fake:   # перехват обработчиков без реальных событий мыши
            command = "x"
            h = {}

            def bind(self, seq, fn, add=None):
                self.h[seq] = fn

            def grab_set(self):
                log.append("grab")

            def grab_release(self):
                log.append("free")
        fb = Fake()
        g.bind(fb, lambda btn: (log.append("down"), g.take(btn)), lambda: (log.append("up"), g.release()))
        fb.h["<ButtonPress-1>"](None)
        assert g.btn is fb
        fb.h["<ButtonRelease-1>"](None)
        assert log == ["down", "grab", "up", "free"] and g.btn is None
    finally:
        root.destroy()


def test_verbs_translation_follows_scanner_setting():
    src = (PKG / "pages_verbs.py").read_text(encoding="utf-8")
    assert 'settings.get("show_tr")' in src
