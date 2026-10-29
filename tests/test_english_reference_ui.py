# -*- coding: utf-8 -*-
"""Справочник глаголов: строится и работает в обоих скинах (классика и alt-вид)."""
import tkinter as tk

import pytest

from stamina.english.pages_reference import ReferencePanel
from stamina.english.progress import Progress
from stamina.english import conjugation as cj, verbs


class Ctx:
    def __init__(self, tmp_path) -> None:
        self.progress = Progress(tmp_path / "english.json")
        self.vocab = None
        self.statuses = []

    def status(self, text="", color=None, *a, **k):
        self.statuses.append((text, color))

    def changed(self):
        pass

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
    r.geometry("1400x860+30+30")
    yield r
    r.destroy()


def _cell_texts(panel):
    out = []
    for row in panel.cells.winfo_children()[1:]:
        line = [w for w in row.winfo_children() if isinstance(w, tk.Frame)][0]
        out.append("".join(w.cget("text") for w in line.winfo_children()))
    return out


@pytest.mark.parametrize("alt", [False, True])
def test_reference_builds_and_navigates(root, tmp_path, alt):
    if alt:
        root._alt_view = object()   # так скин «alt» помечает окно
    back = []
    panel = ReferencePanel(root, Ctx(tmp_path), on_back=lambda: back.append(1))
    panel.pack(fill="both", expand=True)
    root.update()
    assert panel.winfo_ismapped() and panel.results
    # поиск с первой буквы, Enter открывает первый результат
    panel.q.set("w")
    root.update()
    assert panel.results and panel.results[0]["lemma"].startswith("w")
    panel.q.set("went")
    root.update()
    panel._open_selected()
    assert panel.verb["lemma"] == "go"
    # 12 времён × 5 лиц, режимы
    assert len(panel.tense_btns) == 12 and len(panel.mode_btns) == 3
    panel.set_tense("past_simple")
    panel.set_mode("question")
    root.update()
    assert any("Did" in t and "go?" in t for t in _cell_texts(panel))
    panel._step_tense(1)
    assert panel.tense == cj.TENSE_KEYS[cj.TENSE_KEYS.index("past_simple") + 1]
    panel._move_person(1)
    assert panel.person_i == 1
    panel.add_selected()
    assert panel.ctx.progress.data["verb_forms"]["go"]


def test_locked_verb_shows_hint(root, tmp_path):
    panel = ReferencePanel(root, Ctx(tmp_path))
    panel.pack(fill="both", expand=True)
    root.update()
    irr = {v["lemma"] for v in verbs.irregular()}
    locked = next(v for v in verbs.frequent()[verbs.UNLOCK_START:] if v["lemma"] not in irr)
    before = panel.verb
    panel.open_verb(locked)
    assert panel.verb is before
    assert "🔒" in panel.status.cget("text")
