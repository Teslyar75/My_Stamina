"""Логика сессии набора — без интерфейса, чтобы её было легко тестировать.

Время считается «честно»: таймер стартует с первого нажатия, а паузы
длиннее :data:`IDLE_CAP` секунд (отошли от клавиатуры) не засчитываются.
"""

from __future__ import annotations

import statistics
from collections import deque

IDLE_CAP = 4.0          # максимальный учитываемый интервал между нажатиями, с
RHYTHM_WINDOW = 30      # сколько последних интервалов учитывать для «ритма»
SPEED_WINDOW = 25       # окно для мгновенной скорости

OK, ERROR, DONE = "ok", "error", "done"


class TypingEngine:
    def __init__(
        self,
        text: str,
        *,
        index: int = 0,
        typed: int = 0,
        errors: int = 0,
        elapsed: float = 0.0,
        case_sensitive: bool = False,
    ) -> None:
        self.text = text
        self.case_sensitive = case_sensitive
        self.index = max(0, min(index, len(text)))
        self.typed = typed
        self.errors = errors
        self._elapsed = elapsed
        self._last: float | None = None
        self.paused = False
        self.streak = 0
        self.best_streak = 0
        self._intervals: deque[float] = deque(maxlen=max(RHYTHM_WINDOW, SPEED_WINDOW))
        # Статистика по клавишам только за эту сессию: символ → [верно, ошибки]
        self.key_stats: dict[str, list[int]] = {}
        # Значения на старте — чтобы посчитать результат именно этого захода.
        self.start_index = self.index
        self.start_typed = typed
        self.start_errors = errors
        self.start_elapsed = elapsed

    # -- Состояние -----------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.index >= len(self.text)

    @property
    def started(self) -> bool:
        return self._last is not None or self.typed > self.start_typed

    @property
    def current(self) -> str | None:
        return None if self.finished else self.text[self.index]

    @property
    def progress(self) -> float:
        return self.index / len(self.text) if self.text else 0.0

    def elapsed(self, now: float) -> float:
        if self._last is None or self.paused:
            return self._elapsed
        return self._elapsed + min(now - self._last, IDLE_CAP)

    def cpm(self, now: float) -> float:
        """Средняя скорость (знаков в минуту) за всё упражнение."""
        el = self.elapsed(now)
        return self.index * 60.0 / el if el > 0.5 else 0.0

    def instant_cpm(self) -> float:
        """Скорость по последним нажатиям — живая стрелка спидометра."""
        iv = list(self._intervals)[-SPEED_WINDOW:]
        if len(iv) < 3:
            return 0.0
        total = sum(iv)
        return len(iv) * 60.0 / total if total > 0 else 0.0

    @property
    def accuracy(self) -> float | None:
        if self.typed == 0:
            return None
        return max(0.0, (self.typed - self.errors) / self.typed * 100.0)

    @property
    def rhythm(self) -> float | None:
        """Стабильность ритма 0–100 %: чем ровнее интервалы, тем выше."""
        iv = list(self._intervals)[-RHYTHM_WINDOW:]
        if len(iv) < 6:
            return None
        mean = statistics.fmean(iv)
        if mean <= 0:
            return None
        cv = statistics.pstdev(iv) / mean
        return max(0.0, min(100.0, 100.0 - cv * 100.0))

    # -- Управление ----------------------------------------------------

    def pause(self, now: float) -> None:
        if self.paused:
            return
        self._elapsed = self.elapsed(now)
        self._last = None
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._last = None  # следующий интервал начнётся с нового нажатия

    def press(self, char: str, now: float) -> str | None:
        """Обработать символ. Возвращает OK / ERROR / DONE или None."""
        if self.finished or not char:
            return None
        if self.paused:
            self.resume()
        expected = self.text[self.index]
        if self._last is not None:
            dt = now - self._last
            self._elapsed += min(dt, IDLE_CAP)
        else:
            dt = None
        self._last = now
        self.typed += 1
        stat = self.key_stats.setdefault(expected.lower(), [0, 0])
        same = char == expected if self.case_sensitive else char.lower() == expected.lower()
        if same:
            stat[0] += 1
            self.index += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            if dt is not None and dt < IDLE_CAP:
                self._intervals.append(dt)
            return DONE if self.finished else OK
        stat[1] += 1
        self.errors += 1
        self.streak = 0
        return ERROR

    # -- Итоги захода --------------------------------------------------

    def segment(self, now: float) -> dict:
        """Результат с момента создания движка (для журнала полётов)."""
        chars = self.index - self.start_index
        typed = self.typed - self.start_typed
        errors = self.errors - self.start_errors
        el = self.elapsed(now) - self.start_elapsed
        return {
            "chars": chars,
            "typed": typed,
            "errors": errors,
            "elapsed": round(el, 2),
            "cpm": round(chars * 60.0 / el, 1) if el > 0.5 else 0.0,
            "acc": round((typed - errors) / typed * 100.0, 1) if typed else 0.0,
            "rhythm": round(self.rhythm or 0.0, 1),
            "best_streak": self.best_streak,
        }

    def mark_segment_saved(self, now: float) -> None:
        self.start_index = self.index
        self.start_typed = self.typed
        self.start_errors = self.errors
        self.start_elapsed = self.elapsed(now)
        self.key_stats = {}
