"""Кнопка «ГОЛОС» — запись фразы пилота с микрофона (общая для зон корабля).

Корабль слушает в двух местах: в ЭФИРЕ (голосовое сообщение экипажу) и в ОРИОНЕ
(разговор с бортовым разумом). Логика записи одна — `stamina/voice/stt.py`, а эта
кнопка лишь показывает состояние и отдаёт распознанный текст тому, кто её поставил.

Пока идёт запись, видно время и громкость: «СЛУШАЮ 00:14 ▮▮▮▮». Заминка посреди
речи фразу не закрывает — после паузы подпись говорит «пауза 1,2 с — говорите»,
а запись рвётся только после тишины из настроек (`voice_silence_sec`, по умолчанию
2,5 с). Кнопка «ДЕРЖАТЬ» вообще отключает закрытие по тишине: фраза заканчивается
кнопкой СТОП — удобно, когда мысль длинная.

Экран сам вызывает `poll()` из своего таймера (например, раз в 0,15 с) — так Tk
не замирает, пока идёт распознавание.
"""

from __future__ import annotations

from stamina.i18n import t as _t

from stamina.hud import HudButton
from stamina.theme import AMBER, GREEN, MUTED, RED
from stamina.voice import stt

RESTING = "ГОЛОС"
STOP = "СТОП"
HOLD = "ДЕРЖАТЬ"

DEFAULT_SILENCE = 2.5
DEFAULT_MAX = 120.0
DEFAULT_IDLE = 12.0
DEFAULT_SOFT = 0.7


def level_bar(value: float) -> str:
    """Громкость голоса полоской: ▮▮▮ — пилот говорит уверенно."""
    filled = int(max(0.0, min(1.0, value / 0.05)) * 14)
    return "▮" * filled


def clock(seconds: float) -> str:
    """Время записи: 00:07, 01:12."""
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


class MicControl:
    """Кнопка записи + состояние. Текст распознанной фразы уходит в `on_text`."""

    def __init__(self, master, *, on_text, on_status=None, label: str = RESTING,
                 height: int = 36, font_size: int = 11, settings: dict | None = None,
                 save=None) -> None:
        self.button = HudButton(master, _t(label), self.toggle, height=height,
                                font_size=font_size, color=GREEN)
        # режим «не обрывать по тишине»: рядом с ГОЛОС, активен — значит держим микрофон
        self.hold_button = HudButton(master, _t(HOLD), self.toggle_hold, height=height,
                                     font_size=max(7, font_size - 3), width=94, color=AMBER)
        self._on_text = on_text
        self._on_status = on_status
        self._label = label
        self._settings = settings if settings is not None else {}
        self._save = save
        self._listener: stt.Listener | None = None
        self._partial = ""
        self._bar = ""
        self._elapsed = 0.0
        self._pause = 0.0
        self._reason = ""
        self.hold_button.set_active(self.hold)

    # -- настройки
    def cfg(self, key: str, default):
        value = self._settings.get(key, default)
        return default if value is None else value

    @property
    def hold(self) -> bool:
        """True — фразу не закрывает тишина (только СТОП или лимит времени)."""
        return bool(self._settings.get("voice_hold", False))

    def toggle_hold(self) -> None:
        on = not self.hold
        self._settings["voice_hold"] = on
        if self._save is not None:
            try:
                self._save()
            except Exception:  # noqa: BLE001
                pass
        self.hold_button.set_active(on)
        self._say(_t("Не обрывать по тишине: фразу закроет кнопка СТОП") if on
                  else _t("Фраза закрывается сама по тишине"), MUTED)

    def silence_sec(self) -> float:
        if self.hold:
            return 0.0
        try:
            return max(0.0, float(self.cfg("voice_silence_sec", DEFAULT_SILENCE)))
        except (TypeError, ValueError):
            return DEFAULT_SILENCE

    # -- состояние
    @property
    def busy(self) -> bool:
        return self._listener is not None and self._listener.running

    def start(self) -> bool:
        """Начать запись. False — не получилось (нет модели/микрофона)."""
        if self.busy:
            return True
        listener = stt.Listener(silence_sec=self.silence_sec(),
                                max_sec=float(self.cfg("voice_max_sec", DEFAULT_MAX)),
                                idle_sec=float(self.cfg("voice_idle_sec", DEFAULT_IDLE)),
                                soft_sec=float(self.cfg("voice_soft_sec", DEFAULT_SOFT)))
        self._partial = ""
        self._bar = ""
        self._elapsed = 0.0
        self._pause = 0.0
        self._reason = ""
        if not listener.start():
            self._say(_t("Микрофон недоступен: нужны библиотеки vosk и sounddevice"), RED)
            return False
        self._listener = listener
        self.button.set_text(_t(STOP))
        self.button.set_color(RED)
        self._say(_t("СЛУШАЮ… говорите спокойно, заминка фразу не закроет"), GREEN)
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
        self.hold_button.destroy()

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
                self._bar = level_bar(float(value))
                if not self._pause:
                    self._say(self._listen_line(), GREEN)
            elif kind == "elapsed":
                self._elapsed = float(value)
                self._say(self._listen_line(), GREEN)
            elif kind == "pause":
                self._pause = float(value)
                self._say(self._listen_line(), AMBER)
            elif kind == "partial":
                self._partial = str(value)
                self._pause = 0.0
                self._say(self._listen_line(), GREEN)
            elif kind == "stop":
                self._reason = str(value)
            elif kind == "final":
                text = str(value).strip()
                reason = self._reason_text()
                self._reset()
                if text:
                    self._say(_t("Распознано: {0}").format(text) + (f" ({reason})" if reason else ""),
                              MUTED)
                    self._on_text(text)
                else:
                    self._say(_t("Ничего не разобрал — повторите"), RED)
            elif kind == "error":
                self._reset()
                self._say(_t("Сбой записи: {0}").format(value), RED)
            elif kind == "done":
                self._reset()
        if self._listener is not None and not self._listener.running:
            self._reset()

    # -- вспомогательное
    def _listen_line(self) -> str:
        """Строка состояния: время, громкость, «пауза» или распознанное на лету."""
        line = _t("СЛУШАЮ {0} {1}").format(clock(self._elapsed), self._bar)
        if self._pause >= 0.1:
            return line + " · " + _t("пауза {0} с — говорите").format(f"{self._pause:.1f}")
        return line + ("  " + self._partial if self._partial else "")

    def _reason_text(self) -> str:
        """Почему фраза закрылась — пилоту видно прямо в строке состояния."""
        if self._reason == "silence":
            return _t("тишина {0}").format(f"{self.silence_sec():g} с")
        if self._reason == "max":
            return _t("лимит времени")
        if self._reason == "key":
            return _t("остановлено вручную")
        if self._reason == "idle":
            return _t("речи не было")
        return ""

    def _reset(self) -> None:
        self._listener = None
        self._partial = ""
        self._bar = ""
        self._elapsed = 0.0
        self._pause = 0.0
        self._reason = ""
        self.button.set_text(_t(self._label))
        self.button.set_color(GREEN)

    def _say(self, text: str, color=None) -> None:
        color = MUTED if color is None else color  # токен скина — в момент вызова, не при импорте
        if self._on_status is not None:
            self._on_status(text, color)
