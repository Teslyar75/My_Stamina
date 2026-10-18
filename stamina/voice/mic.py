"""Кнопка «ГОЛОС» — запись фразы пилота с микрофона (общая для зон корабля).

Корабль слушает в двух местах: в ЭФИРЕ (голосовое сообщение экипажу) и в ОРИОНЕ
(разговор с бортовым разумом). Логика записи одна — `stamina/voice/stt.py`, а эта
кнопка лишь показывает состояние и отдаёт распознанный текст тому, кто её поставил.

Экран сам вызывает `poll()` из своего таймера (например, раз в 0,15 с) — так Tk
не замирает, пока идёт распознавание.
"""

from __future__ import annotations

from stamina.i18n import t as _t

from stamina.hud import HudButton
from stamina.theme import GREEN, MUTED, RED
from stamina.voice import stt

RESTING = "ГОЛОС"
STOP = "СТОП"


def level_bar(value: float) -> str:
    """Громкость голоса полоской: ▮▮▮ — пилот говорит уверенно."""
    filled = int(max(0.0, min(1.0, value / 0.05)) * 14)
    return "▮" * filled


class MicControl:
    """Кнопка записи + состояние. Текст распознанной фразы уходит в `on_text`."""

    def __init__(self, master, *, on_text, on_status=None, label: str = RESTING,
                 height: int = 36, font_size: int = 11) -> None:
        self.button = HudButton(master, _t(label), self.toggle, height=height,
                                font_size=font_size, color=GREEN)
        self._on_text = on_text
        self._on_status = on_status
        self._label = label
        self._listener: stt.Listener | None = None
        self._partial = ""

    # -- состояние
    @property
    def busy(self) -> bool:
        return self._listener is not None and self._listener.running

    def start(self) -> bool:
        """Начать запись. False — не получилось (нет модели/микрофона)."""
        if self.busy:
            return True
        listener = stt.Listener()
        self._partial = ""
        if not listener.start():
            self._say(_t("Микрофон недоступен: нужны библиотеки vosk и sounddevice"), RED)
            return False
        self._listener = listener
        self.button.set_text(_t(STOP))
        self.button.set_color(RED)
        self._say(_t("Готовлю распознавание…"), MUTED)
        return True

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def toggle(self) -> None:
        if self.busy or self._listener is not None:
            self.stop()
        else:
            self.start()

    def destroy(self) -> None:
        self.stop()
        self.button.destroy()

    # -- события от потока записи
    def poll(self) -> None:
        listener = self._listener
        if listener is None:
            return
        for kind, value in listener.poll():
            if kind == "status":
                self._say(_t("Готовлю распознавание…") if value == "loading"
                          else _t("СЛУШАЮ… говорите"), GREEN)
            elif kind == "level":
                bar = level_bar(float(value))
                self._say(_t("СЛУШАЮ… {0} {1}").format(bar, self._partial), GREEN)
            elif kind == "partial":
                self._partial = str(value)
                self._say(_t("СЛУШАЮ… {0}").format(self._partial), GREEN)
            elif kind == "final":
                text = str(value).strip()
                self._reset()
                self._say(_t("Распознано: {0}").format(text) if text
                          else _t("Ничего не разобрал — повторите"), MUTED if text else RED)
                if text:
                    self._on_text(text)
            elif kind == "error":
                self._reset()
                self._say(_t("Сбой записи: {0}").format(value), RED)
            elif kind == "done":
                self._reset()
        if self._listener is not None and not self._listener.running:
            self._reset()

    # -- вспомогательное
    def _reset(self) -> None:
        self._listener = None
        self._partial = ""
        self.button.set_text(_t(self._label))
        self.button.set_color(GREEN)

    def _say(self, text: str, color=MUTED) -> None:
        if self._on_status is not None:
            self._on_status(text, color)
