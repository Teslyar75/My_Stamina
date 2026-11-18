"""Общий контекст для экранов речи: сканер и отработка чтения.

Сканер и страница чтения пользуются одним и тем же набором: прогресс языка,
распознавание, заглушка озвучки (у языка свой голос, он живёт в speech.py)
и ссылка на приложение для строки статуса и звуков.
"""
from __future__ import annotations

from stamina.languages.speech import stop_speak


class TTSStub:
    """Озвучка уже умеет говорить; MicPanel ждёт stop()/poll() — отдаём их."""

    def stop(self) -> None:
        stop_speak()

    def poll(self):
        return []


class LangCtx:
    def __init__(self, progress, asr, app) -> None:
        self.progress = progress
        self.asr = asr
        self.tts = TTSStub()
        self.app = app

    def status(self, text: str, color=None) -> None:
        fn = getattr(self.app, "status", None)
        if callable(fn):
            fn(text, color)

    def sfx(self, name: str) -> None:
        fn = getattr(self.app, "sfx", None)
        if callable(fn):
            fn(name)


# Старое имя, чтобы не ломать чужие импорты внутри пакета.
_Ctx = LangCtx
