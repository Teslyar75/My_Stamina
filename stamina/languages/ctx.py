"""Общий контекст для экранов речи: сканер и отработка чтения.

Сканер и страница чтения пользуются одним и тем же набором: прогресс языка,
распознавание, озвучка (у языка свой голос, он живёт в speech.py) и ссылка на
приложение для строки статуса и звуков. Кнопки озвучки делаются здесь же, как
`audio_button` в английском отсеке: светятся, пока звучит фраза.
"""
from __future__ import annotations

from stamina.hud import HudButton
from stamina.languages.speech import speak, stop_speak, tts


class TTSStub:
    """Озвучка уже умеет говорить; MicPanel ждёт stop()/poll() — отдаём их."""

    def stop(self) -> None:
        stop_speak()
        tts().stop()

    def poll(self):
        return []


class LangCtx:
    def __init__(self, progress, asr, app, lang: str = "", voice_error=None) -> None:
        self.progress = progress
        self.asr = asr
        self.tts = TTSStub()
        self.app = app
        self.lang = lang
        self.voice_error = voice_error     # куда сказать, если голоса нет

    def status(self, text: str, color=None) -> None:
        fn = getattr(self.app, "status", None)
        if callable(fn):
            fn(text, color)

    def sfx(self, name: str) -> None:
        fn = getattr(self.app, "sfx", None)
        if callable(fn):
            fn(name)

    def say(self, text: str, slow: bool = False, btn: HudButton | None = None) -> None:
        """Озвучить слово или фразу голосом языка карточки."""
        text = (text or "").strip()
        if not text:
            return
        done = None
        if btn is not None:
            btn.set_active(True)

            def restore() -> None:
                try:
                    if btn.winfo_exists():
                        btn.set_active(False)
                except Exception:  # noqa: BLE001
                    pass

            def done() -> None:
                try:
                    btn.after(0, restore)
                except Exception:  # noqa: BLE001
                    pass
        speak(text, self.lang, slow=slow, on_error=self.voice_error, on_done=done)

    def audio_button(self, parent, label: str, text_fn, slow: bool = False, **kw) -> HudButton:
        """Кнопка озвучки: на нажатие светится и читает то, что вернёт text_fn."""
        b = HudButton(parent, label, None, **kw)
        b.command = lambda: self.say(text_fn(), slow=slow, btn=b)
        return b


# Старое имя, чтобы не ломать чужие импорты внутри пакета.
_Ctx = LangCtx
