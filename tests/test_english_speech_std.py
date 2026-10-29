"""Единый стандарт речи: пороги совпадают со складом, M — микрофон, T — подсказка (удержание), пробел свободен; в полях ввода это текст."""
import tkinter as tk
from types import SimpleNamespace

import pytest

from stamina.english import speech_std as std
from stamina.english import warehouse as wh


def test_thresholds_match_warehouse():
    assert std.ITEM_OK == wh.FLIP_OK == 80
    assert std.RUN_OK == wh.PASS_QUALITY == 85
    assert std.passed(80) and not std.passed(79) and not std.passed(None)


def test_mic_m_only_hint_t_space_free():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        entry, text, frame = tk.Entry(root), tk.Text(root), tk.Frame(root)
        ev = lambda k, w: SimpleNamespace(keysym=k, widget=w)
        assert std.is_mic_key(ev("M", frame)) and std.is_mic_key(ev("m", frame))
        assert std.is_mic_key(ev("Cyrillic_softsign", frame))      # та же клавиша в RU/UK
        assert std.is_hint_key(ev("t", frame)) and std.is_hint_key(ev("Cyrillic_ie", frame))
        assert not std.is_mic_key(ev("space", frame)) and not std.is_hint_key(ev("space", frame))
        for k in ("m", "t", "n", "space"):                          # в полях ввода — это текст
            assert not std.is_mic_key(ev(k, entry)) and not std.is_hint_key(ev(k, entry))
            assert not std.is_mic_key(ev(k, text)) and not std.is_hint_key(ev(k, text))
        text.configure(state="disabled")
        assert std.is_mic_key(ev("m", text))
        assert not std.is_mic_key(ev("a", frame))
    finally:
        root.destroy()


def _fake_cockpit(current):
    from stamina import cockpit
    from stamina import english_hook
    calls = []
    scr = lambda name: SimpleNamespace(on_key=lambda e: calls.append((name, "down", e.keysym)),
                                       on_key_up=lambda e: calls.append((name, "up", e.keysym)),
                                       state="run")
    screens = {"bridge": scr("bridge"), english_hook.KEY: scr("english")}
    fake = SimpleNamespace(zen=None, _fullscreen=False, current=current, screens=screens,
                           focus_get=lambda: None, focus_set=lambda: None,
                           _chrome_hotkey=lambda e: False)
    return cockpit, fake, calls, english_hook


def test_typing_trainer_gets_t_m_n_space_untouched():
    cockpit, fake, calls, _ = _fake_cockpit("bridge")
    for k in ("t", "m", "n", "space", "T", "M"):
        e = SimpleNamespace(keysym=k, state=0, keycode=0, char=k)
        cockpit.Cockpit._on_key(fake, e)
        cockpit.Cockpit._on_key_up(fake, e)
    assert [c for c in calls if c[0] != "bridge"] == []
    assert [c[2] for c in calls] == ["t", "m", "n", "space", "T", "M"]   # все — в тренажёр, только нажатия


def test_key_release_reaches_english_only():
    cockpit, fake, calls, ek = _fake_cockpit(None)
    fake.current = ek.KEY
    cockpit.Cockpit._on_key_up(fake, SimpleNamespace(keysym="t", state=0))
    assert calls == [("english", "up", "t")]


def test_advance_later_respects_user_switch():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        calls = []
        std.advance_later(root, lambda: calls.append(1), lambda: True)
        std.advance_later(root, lambda: calls.append(2), lambda: False)
        root.after(std.ADVANCE_MS + 200, root.quit)
        root.mainloop()
        assert calls == [1]
    finally:
        root.destroy()
