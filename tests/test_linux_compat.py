"""Linux: озвучка через espeak-ng / spd-say, ключи без Secret Service, шрифты с кириллицей."""
import sys
import types

import pytest

from stamina import agent_connect, theme
from stamina.voice import tts

_ORIG_BACKEND = agent_connect._backend  # до подмены в conftest


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("STAR_TYPING_NO_LINUX_TTS", raising=False)


def test_linux_tool_prefers_espeak_ng(linux, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/" + n if n in ("espeak-ng", "spd-say") else None)
    assert tts.linux_tool() == "/usr/bin/espeak-ng"
    assert tts.available()


def test_no_tool_means_silent(linux, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert tts.linux_tool() == ""
    assert not tts.available()


def test_env_switch_disables(linux, monkeypatch):
    monkeypatch.setenv("STAR_TYPING_NO_LINUX_TTS", "1")
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/" + n)
    assert tts.linux_tool() == ""


def test_linux_cmd_espeak_and_spd():
    cmd = tts._linux_cmd("/usr/bin/espeak-ng", "привет", lang="ru-RU", rate=0, volume=100, out="/tmp/a.wav")
    assert cmd[0].endswith("espeak-ng") and "-v" in cmd and "ru" in cmd and cmd[-1] == "привет"
    assert "-w" in cmd and "/tmp/a.wav" in cmd
    spd = tts._linux_cmd("/usr/bin/spd-say", "hi", lang="en", rate=0, volume=50)
    assert spd[0].endswith("spd-say") and "-l" in spd and "en" in spd


def test_fail_keyring_means_no_store(linux, monkeypatch):
    fail = type("Keyring", (), {"priority": 0})()
    type(fail).__module__ = "keyring.backends.fail"
    monkeypatch.setitem(sys.modules, "keyring", types.SimpleNamespace(get_keyring=lambda: fail))
    assert _ORIG_BACKEND() is None          # Linux без Secret Service — хранилища нет
    monkeypatch.setattr(agent_connect, "_backend", lambda: None)
    with pytest.raises(RuntimeError, match="no_store"):
        agent_connect.store_key("x", "secret")


def test_cyrillic_filter(monkeypatch):
    monkeypatch.setattr(theme, "_CYR", {"DejaVu Sans", "DejaVu Sans Mono"})
    monkeypatch.setattr(theme, "_current", {})
    monkeypatch.setattr(theme, "HUD_FAMILY", theme.HUD_FAMILY)
    monkeypatch.setattr(theme, "MONO_FAMILY", theme.MONO_FAMILY)
    root = types.SimpleNamespace()
    monkeypatch.setattr(theme.tkfont, "families", lambda r=None: ("Segoe UI", "DejaVu Sans", "DejaVu Sans Mono"))
    theme._pick_fonts(root)
    assert theme.HUD_FAMILY == "DejaVu Sans" and theme.MONO_FAMILY == "DejaVu Sans Mono"


def test_tk_gc_collects_on_timer_and_restores(monkeypatch):
    import gc
    from stamina import tk_gc
    calls = []

    class Root:
        def after(self, ms, fn):
            calls.append(fn)

    monkeypatch.setattr(tk_gc, "_installed", False)
    assert not tk_gc.install(Root()) if sys.platform == "win32" else True
    monkeypatch.setattr(tk_gc, "_installed", False)
    try:
        assert tk_gc.install(Root(), force=True)
        assert not gc.isenabled()
        calls.pop()()                 # шаг таймера: собрал и перепоставился
        assert calls
    finally:
        tk_gc.uninstall()
    assert gc.isenabled()
