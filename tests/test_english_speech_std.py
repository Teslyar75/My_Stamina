"""Единый стандарт речи: пороги совпадают со складом, Space/M не крадут текст из полей."""
import tkinter as tk
from types import SimpleNamespace

import pytest

from stamina.english import speech_std as std
from stamina.english import warehouse as wh


def test_thresholds_match_warehouse():
    assert std.ITEM_OK == wh.FLIP_OK == 80
    assert std.RUN_OK == wh.PASS_QUALITY == 85
    assert std.passed(80) and not std.passed(79) and not std.passed(None)


def test_mic_keys_skip_text_inputs():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    try:
        entry, text, frame = tk.Entry(root), tk.Text(root), tk.Frame(root)
        assert std.is_mic_key(SimpleNamespace(keysym="space", widget=frame))
        assert std.is_mic_key(SimpleNamespace(keysym="M", widget=frame))
        assert not std.is_mic_key(SimpleNamespace(keysym="space", widget=entry))
        assert not std.is_mic_key(SimpleNamespace(keysym="m", widget=text))
        text.configure(state="disabled")
        assert std.is_mic_key(SimpleNamespace(keysym="space", widget=text))
        assert not std.is_mic_key(SimpleNamespace(keysym="a", widget=frame))
    finally:
        root.destroy()


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
