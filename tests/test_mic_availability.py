"""Микрофон не исчезает из интерфейса и говорит, почему молчит.

Раньше «Сканер» и «Чтение» прятали кнопку 🎤, если распознавание недоступно,
а «ГОЛОС» в ЭФИРЕ на любую причину отказа отвечал «нужны библиотеки vosk и
sounddevice» — даже когда библиотеки стояли, а не было модели.
"""
from __future__ import annotations

import tkinter as tk

import pytest

from stamina.english.mic import MicPanel
from stamina.voice import stt
from stamina.voice.mic import MicControl


class FakeASR:
    """Распознавание, которому можно «починить» модель прямо в тесте."""

    def __init__(self, why: str = "") -> None:
        self.why = why
        self.refreshed = 0
        self.listening = False

    def available(self) -> bool:
        return not self.why

    def why_unavailable(self) -> str:
        return self.why

    def refresh_libs(self) -> bool:
        self.refreshed += 1
        return not self.why

    def stop(self) -> None:
        pass

    def poll(self):
        return []

    def listen(self) -> bool:
        return False


class FakeTTS:
    def stop(self) -> None:
        pass

    def poll(self):
        return []


class FakeCtx:
    def __init__(self, why: str = "", **settings) -> None:
        self.asr = FakeASR(why)
        self.progress = type("P", (), {"settings": {"asr": True, "self_assess": True, **settings}})()
        self.tts = FakeTTS()
        self.statuses: list[str] = []

    def status(self, text, color=None) -> None:
        self.statuses.append(text)


@pytest.fixture()
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    r.attributes("-alpha", 0.0)
    yield r
    r.destroy()


def test_button_stays_visible_when_speech_unavailable(root):
    ctx = FakeCtx("нет модели Vosk в D:/models")
    panel = MicPanel(root, ctx, lambda *a: None)
    panel.pack()
    root.update()

    assert panel.btn.winfo_manager() == "pack", "кнопка микрофона пропала из сканера"
    assert "нет модели Vosk" in panel.live.cget("text")
    assert panel.selfbox.winfo_manager() == "pack", "самооценка должна остаться запасным путём"


def test_button_returns_when_model_appears(root):
    ctx = FakeCtx("нет модели Vosk")
    panel = MicPanel(root, ctx, lambda *a: None)
    panel.pack()
    root.update()

    ctx.asr.why = ""
    panel.refresh_mode()
    root.update()

    assert panel.btn.winfo_manager() == "pack"
    assert "Нажми и прочитай" in panel.live.cget("text")
    assert panel.selfbox.winfo_manager() == ""


def test_toggle_rechecks_libs_and_names_the_reason(root):
    ctx = FakeCtx("нет библиотек vosk / sounddevice")
    panel = MicPanel(root, ctx, lambda *a: None)
    panel.pack()
    root.update()

    panel.toggle()

    assert ctx.asr.refreshed == 1, "библиотеки не перепроверены перед отказом"
    assert ctx.statuses and "нет библиотек" in ctx.statuses[-1]


def test_miccontrol_shows_real_reason(root, monkeypatch):
    monkeypatch.setattr(stt, "ready", lambda path=None: (False, "нет модели Vosk в C:/models"))
    said: list[str] = []
    ctrl = MicControl(root, on_text=lambda *_: None,
                      on_status=lambda text, color=None: said.append(text))

    assert ctrl.start() is False
    assert said and "нет модели Vosk" in said[-1]
    assert "библиотеки" not in said[-1], "причина подменена общим текстом про библиотеки"


def test_listener_keeps_failure_reason(monkeypatch):
    monkeypatch.setattr(stt, "ready", lambda path=None: (False, "нет модели Vosk в C:/models"))
    listener = stt.Listener()

    assert listener.start() is False
    assert listener.fail_reason == "нет модели Vosk в C:/models"
    kinds = [kind for kind, _ in listener.poll()]
    assert kinds == ["error", "done"]


def test_models_dir_falls_back_to_shared_library(monkeypatch, tmp_path):
    """Модель в %APPDATA%/Stamina/models годится для любой копии корабля."""
    project = tmp_path / "project"
    shared = tmp_path / "shared"
    shared_models = shared / "models"
    (shared_models / "vosk-model-small-ru-0.22" / "am").mkdir(parents=True)

    monkeypatch.delenv("STAR_TYPING_MODELS", raising=False)
    monkeypatch.setattr(stt, "PROJECT_DIR", project)
    monkeypatch.setattr(stt, "shared_models_dir", lambda: shared_models)

    assert stt.models_dir() == shared_models


def test_models_dir_keeps_local_copy_first(monkeypatch, tmp_path):
    project = tmp_path / "project"
    shared_models = tmp_path / "shared" / "models"
    (project / "models" / "vosk-model-small-ru-0.22" / "am").mkdir(parents=True)
    (shared_models / "vosk-model-small-ru-0.22" / "am").mkdir(parents=True)

    monkeypatch.delenv("STAR_TYPING_MODELS", raising=False)
    monkeypatch.setattr(stt, "PROJECT_DIR", project)
    monkeypatch.setattr(stt, "shared_models_dir", lambda: shared_models)

    assert stt.models_dir() == project / "models"
