"""Голосовой вызов агента с мостика: заглушки, поток вызова, отмена, Home в полях."""
import random
import tkinter as tk
from types import SimpleNamespace

import pytest

from stamina import voice_call as vc


def test_filler_pools_big_and_unique():
    for lang in ("ru", "uk", "en", "de"):
        pool = vc.FILLERS[lang]
        assert len(pool) >= 30
        assert len(set(pool)) == len(pool)


def test_filler_never_repeats():
    rng = random.Random(1)
    prev = None
    for _ in range(300):
        cur = vc.pick_filler("ru", prev, rng)
        assert cur != prev
        prev = cur
    assert vc.pick_filler("xx") in vc.FILLERS["en"]


class FakeRoot:
    def __init__(self):
        self.calls = []

    def after(self, ms, fn, *args):
        self.calls.append((fn, args))

    def run(self, limit=50):
        for _ in range(limit):
            if not self.calls:
                return
            fn, args = self.calls.pop(0)
            fn(*args)


class FakeListener:
    def __init__(self, events, ok=True):
        self.events, self.ok, self.stopped = list(events), ok, False

    def start(self):
        return self.ok

    def stop(self):
        self.stopped = True

    def poll(self):
        out, self.events = self.events, []
        return out


class FakeTTS:
    def __init__(self):
        self.said, self.stops = [], 0

    def speak(self, text, **kw):
        self.said.append(text)

    def stop(self):
        self.stops += 1

    def speaking(self):
        return False


def make(events, reply="Ответ агента", ok=True, error="", where=""):
    root, tts, hist, states = FakeRoot(), FakeTTS(), [], []
    asked, ctxs = [], []

    def ask(rec, text, context=""):
        asked.append(text)
        ctxs.append(context)
        return SimpleNamespace(reply=reply, error=error, detail="", session="s1")

    call = vc.VoiceCall(root, lambda s, t="": states.append(s),
                        listener_factory=lambda lang: FakeListener(events, ok), ask=ask, tts=tts,
                        remember=lambda aid, role, text, session=None: hist.append((aid, role, text)),
                        agent=lambda: {"id": "orion", "tts_voice": "Irina"}, lang=lambda: "ru",
                        where=lambda: where)
    call.ctxs = ctxs
    return call, root, tts, hist, states, asked


def _drain(call, root):
    import time
    for _ in range(100):
        root.run()
        if call._q.qsize() or not root.calls:
            if call._q.qsize():
                call._poll_answer()
                root.run()
            if call.state in ("idle", "error"):
                return
        time.sleep(0.02)
        root.run()


def test_flow_question_filler_answer_history():
    call, root, tts, hist, states, asked = make([("partial", "как"), ("stop", "silence"), ("final", "как дела"), ("done", None)])
    assert call.start()
    _drain(call, root)
    assert asked == ["как дела"]
    assert tts.said[0] in vc.FILLERS["ru"]          # сразу заглушка
    assert tts.said[-1] == "Ответ агента"           # потом настоящий ответ
    assert hist == [("orion", "pilot", "🎙 как дела"), ("orion", "orion", "Ответ агента")]
    assert states[:2] == ["listening", "thinking"] and "speaking" in states and states[-1] == "idle"


def test_cancel_while_listening_discards_text():
    call, root, tts, hist, states, asked = make([("final", "не надо"), ("done", None)])
    call.start()
    call.toggle()                                   # второе нажатие — отмена
    root.run()
    assert call.state == "idle" and not asked and not hist


def test_cancel_while_thinking_keeps_history_silent():
    call, root, tts, hist, states, asked = make([("final", "вопрос")])
    call.start()
    root.run(limit=1)                               # микрофон отдал фразу
    assert call.state == "thinking"
    call.cancel()
    _drain(call, root)
    assert ("orion", "orion", "Ответ агента") in hist
    assert "Ответ агента" not in tts.said


def test_error_is_voiced_and_saved():
    call, root, tts, hist, states, asked = make([("final", "вопрос")], reply="", error="timeout")
    call.start()
    _drain(call, root)
    assert hist[-1][1] == "system"
    assert tts.said[-1] == hist[-1][2]
    assert "error" in states


def test_no_model_reports_error():
    call, root, tts, hist, states, asked = make([], ok=False)
    assert not call.start()
    assert "error" in states and tts.said


def test_home_ignored_in_text_fields():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет Tk")
    root.withdraw()
    try:
        from stamina.hotkeys import typing_in
        assert typing_in(tk.Entry(root))
        assert not typing_in(tk.Frame(root))
    finally:
        root.destroy()


class _Btn:
    def set_text(self, t):
        self.text = t

    def set_color(self, c):
        self.color = c


def _fake_cockpit(current):
    from stamina.cockpit import Cockpit
    calls = []
    app = SimpleNamespace(current=current, voice_call=None, btn_orion=_Btn(),
                          show=lambda *a: calls.append(("show", a)),
                          _voice_call_toggle=lambda: calls.append(("call",)))
    return Cockpit, app, calls


@pytest.mark.parametrize("screen", ["bridge", "missions", "docs", "english"])
def test_orion_button_calls_in_place_on_every_screen(monkeypatch, screen):
    from stamina.voice import tts
    monkeypatch.setattr(tts, "speaking", lambda: False)
    Cockpit, app, calls = _fake_cockpit(screen)
    Cockpit._call_orion(app)
    assert calls == [("call",)]                    # без перехода в раздел Ориона


def test_orion_button_stops_speech(monkeypatch):
    from stamina.voice import tts
    stopped = []
    monkeypatch.setattr(tts, "speaking", lambda: True)
    monkeypatch.setattr(tts, "stop", lambda: stopped.append(1))
    Cockpit, app, calls = _fake_cockpit("missions")
    Cockpit._call_orion(app)
    assert stopped and calls == []


def test_context_goes_to_prompt_and_history():
    call, root, tts, hist, states, asked = make([("final", "что это за слово")],
                                               where="Английский › Слова (word: apple)")
    call.start()
    _drain(call, root)
    assert "Английский › Слова (word: apple)" in call.ctxs[0]
    assert hist[0][2] == "🎙 [Английский › Слова (word: apple)] что это за слово"
    assert asked == ["что это за слово"]           # сам вопрос — без метки


def test_cockpit_voice_context_path_tab_brief():
    from stamina import cockpit
    scr = SimpleNamespace(current_tab="words", word="apple", title=lambda: "x")
    app = SimpleNamespace(current="english", screens={"english": scr}, BRIEF_ATTRS=cockpit.Cockpit.BRIEF_ATTRS)
    line = cockpit.Cockpit.voice_context(app)
    assert "words" in line and "word: apple" in line and "x" not in line.split("(")[-1]
    scr2 = SimpleNamespace(voice_brief=lambda: "книга «Дюна», стр. 12")
    app2 = SimpleNamespace(current="english", screens={"english": scr2}, BRIEF_ATTRS=cockpit.Cockpit.BRIEF_ATTRS)
    assert "книга «Дюна», стр. 12" in cockpit.Cockpit.voice_context(app2)
