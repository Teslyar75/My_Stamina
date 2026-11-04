"""Автоотправка голосового обращения.

Пилот нажал «ОРИОН», сказал фразу — и не хочет искать Enter. Правило простое:
распознанный текст лёг в поле, полторы-две секунды тишины — сообщение уходит само.

Отправляем **только** если:

* автоотправка включена (настройка ``orion_auto_send``);
* в поле есть текст;
* текст не менялся с момента диктовки (пилот не начал править руками —
  иначе он ещё думает, и мешать ему нельзя);
* Орион свободен (``busy`` — уже отвечает или выполняет задание); если занят,
  отправка откладывается до конца ответа, а не теряется.

Таймер подставляется снаружи (``after``/``after_cancel``), поэтому правило и обвязка
проверяются тестом без tkinter.
"""

from __future__ import annotations

from typing import Callable

#: Пауза после последней распознанной фразы, мс. Новая фраза перезапускает отсчёт.
AUTO_SEND_MS = 1800


def normalize(text: str) -> str:
    """Текст без лишних пробелов и переводов строк — для сравнения «правил ли пилот»."""
    return " ".join((text or "").split())


def should_send(*, text: str, baseline: str = "", busy: bool = False,
                enabled: bool = True) -> bool:
    """Отправлять ли сейчас: голос замолчал, поле не пустое, пилот ничего не правил."""
    if not enabled or busy:
        return False
    now = normalize(text)
    if not now:
        return False
    return now == normalize(baseline)


def delay_ms() -> int:
    """Сколько ждать тишины. Одна точка правды для экрана и тестов."""
    return AUTO_SEND_MS


class AutoSender:
    """Таймер «пилот замолчал → отправь».

    Экран отдаёт свои ``after``/``after_cancel``, добытчик текста и саму отправку;
    тест подставляет фейковый планировщик и зовёт :meth:`fire` руками.
    """

    def __init__(self, *, after: Callable[[int, Callable[[], None]], object],
                 after_cancel: Callable[[object], None],
                 text: Callable[[], str], sender: Callable[[], None],
                 enabled: Callable[[], bool] | None = None,
                 busy: Callable[[], bool] | None = None,
                 delay: Callable[[], int] | None = None) -> None:
        self._after = after
        self._after_cancel = after_cancel
        self._text = text
        self._send = sender
        self._enabled = enabled or (lambda: True)
        self._busy = busy or (lambda: False)
        self._delay = delay or delay_ms
        self._job = None
        self._base = ""

    @property
    def armed(self) -> bool:
        return self._job is not None

    def arm(self) -> bool:
        """Взвести отсчёт. Новая фраза перезапускает его; выключенная настройка — не взводит."""
        self.cancel()
        if not self._enabled():
            return False
        self._base = self._text()
        self._job = self._after(self._delay(), self.fire)
        return True

    def cancel(self) -> None:
        job, self._job = self._job, None
        if job is not None:
            try:
                self._after_cancel(job)
            except Exception:  # noqa: BLE001 — таймер мог уже отработать
                pass

    def fire(self) -> bool:
        """Сработал таймер: отправить, если пилот молчит и не правил текст."""
        self._job = None
        ready = should_send(text=self._text(), baseline=self._base, enabled=self._enabled())
        if ready and self._busy():
            # Орион ещё отвечает (поток OpenCode, отправка в мост) — фраза не теряется:
            # ждём, пока он освободится, и уходим, если пилот за это время ничего не правил.
            self._job = self._after(self._delay(), self.fire)
            return False
        if not ready:
            return False
        self._send()
        return True
