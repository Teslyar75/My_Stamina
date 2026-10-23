"""Движок «портала» (дзен-режим): поведение набора как на привычном сайте-тренажёре.

Слова, а не символы: пробел переходит к следующему слову (недобранное — «пропущено»),
лишние буквы остаются в слове (тёмно-красные), Backspace правит текущее слово,
Ctrl+Backspace стирает слово целиком, вернуться назад можно только в слово с ошибкой.
Таймер — с первого нажатия. Формулы:
  wpm  = (символы верных слов + верные пробелы) / 5 / минуты
  raw  = (все набранные символы + пробелы) / 5 / минуты
  acc  = верные нажатия / все нажатия
  consistency = 100·(1 − tanh(c + c³/3 + c⁵/5)), c = σ/μ посекундного raw
Чистая логика без Tk — тестируется отдельно (tests/test_zen_engine.py).
"""
from __future__ import annotations

import math
import re
import statistics
import time

MODES = ("time", "words", "quote", "zen", "custom")
COUNTS = {"time": (15, 30, 60, 120), "words": (10, 25, 50, 100)}
_PUNCT = re.compile(r"[^\w'’-]+", re.UNICODE)


def prepare_words(text: str, *, punctuation: bool = False, numbers: bool = False) -> list[str]:
    """Слова из текста мостика. Без «punctuation» — строчные и без знаков, как в базовом режиме."""
    out = []
    for w in (text or "").split():
        if not punctuation:
            w = _PUNCT.sub("", w).strip("'’-").lower()
        if not w:
            continue
        if not numbers and any(ch.isdigit() for ch in w):
            if not punctuation or w.strip(".,;:!?()\"«»").isdigit():
                w = "".join(ch for ch in w if not ch.isdigit()).strip("'’-")
                if not w:
                    continue
        out.append(w)
    return out


def quote_slice(text: str, start_word: int, *, min_words: int = 12, max_words: int = 80) -> int:
    """Сколько слов взять для «quote»: до конца предложения, от min до max слов."""
    words = (text or "").split()[start_word:]
    for i, w in enumerate(words[:max_words], 1):
        if i >= min_words and w.rstrip("»\"')").endswith((".", "!", "?", "…")):
            return i
    return min(len(words), max_words)


def kogasa(cov: float) -> float:
    return 100.0 * (1.0 - math.tanh(cov + cov ** 3 / 3 + cov ** 5 / 5))


class PortalTest:
    """Один тест: список слов, ввод по словам, счётчики и посекундные отсчёты."""

    def __init__(self, words: list[str], *, mode: str = "words", limit: int = 0) -> None:
        self.words = list(words) or ["…"]
        self.mode = mode
        self.limit = limit              # секунд для time, слов для words; 0 — без ограничения
        self.inputs: list[str] = [""]
        self.wi = 0
        self.t0: float | None = None
        self.t_end: float | None = None
        self.correct_keys = 0
        self.total_keys = 0
        self.samples: list[tuple[float, float, int]] = []   # (wpm, raw, ошибок) за секунду
        self._sec_keys = 0
        self._sec_err = 0
        self._sec_next = 0.0
        self.bursts: list[float] = []

    # -- состояние -----------------------------------------------------
    @property
    def started(self) -> bool:
        return self.t0 is not None

    @property
    def finished(self) -> bool:
        return self.t_end is not None

    def elapsed(self, now: float | None = None) -> float:
        if self.t0 is None:
            return 0.0
        end = self.t_end if self.t_end is not None else (time.perf_counter() if now is None else now)
        return max(0.0, end - self.t0)

    def word_ok(self, i: int) -> bool:
        return i < len(self.inputs) and self.inputs[i] == self.words[i]

    # -- ввод ----------------------------------------------------------
    def _begin(self, now: float) -> None:
        if self.t0 is None:
            self.t0 = now
            self._sec_next = now + 1.0

    def _key(self, ok: bool, now: float) -> None:
        self.total_keys += 1
        self.correct_keys += 1 if ok else 0
        self._sec_keys += 1
        self._sec_err += 0 if ok else 1
        self.tick(now)

    def type_char(self, ch: str, now: float | None = None) -> None:
        if self.finished or not ch:
            return
        now = time.perf_counter() if now is None else now
        if ch == " ":
            cur = self.inputs[self.wi]
            if not cur:
                return                       # пробел в начале слова ничего не делает
            self._begin(now)
            self._key(cur == self.words[self.wi], now)
            if self.wi + 1 >= len(self.words):
                self.finish(now)
                return
            self.wi += 1
            if len(self.inputs) <= self.wi:
                self.inputs.append("")
            self._check_end(now)
            return
        self._begin(now)
        cur = self.inputs[self.wi]
        target = self.words[self.wi]
        ok = len(cur) < len(target) and target[len(cur)] == ch
        if len(cur) >= len(target) + 20:     # не больше 20 лишних букв
            return
        self.inputs[self.wi] = cur + ch
        self._key(ok, now)
        if self.wi == len(self.words) - 1 and self.inputs[self.wi] == target:
            self.finish(now)

    def backspace(self, word: bool = False) -> None:
        if self.finished:
            return
        cur = self.inputs[self.wi]
        if cur:
            self.inputs[self.wi] = "" if word else cur[:-1]
            return
        # назад — только в слово с ошибкой (верное слово «заперто»)
        if self.wi > 0 and not self.word_ok(self.wi - 1):
            self.inputs.pop()
            self.wi -= 1
            if word:
                self.inputs[self.wi] = ""

    def tick(self, now: float | None = None) -> None:
        """Посекундные отсчёты и конец по времени (вызывается часто)."""
        if self.t0 is None or self.finished:
            return
        now = time.perf_counter() if now is None else now
        while now >= self._sec_next:
            el = self._sec_next - self.t0
            self.samples.append((self.wpm(el), self._sec_keys * 60 / 5, self._sec_err))
            self._sec_keys = self._sec_err = 0
            self._sec_next += 1.0
        self._check_end(now)

    def _check_end(self, now: float) -> None:
        if self.mode == "time" and self.limit and self.t0 is not None and now - self.t0 >= self.limit:
            self.finish(self.t0 + self.limit)

    def finish(self, now: float | None = None) -> None:
        if self.finished:
            return
        now = time.perf_counter() if now is None else now
        if self.t0 is None:
            self.t0 = now
        self.t_end = now

    # -- подсчёт -------------------------------------------------------
    def chars(self) -> dict:
        """correct / incorrect / extra / missed — как в итогах сайта."""
        c = i = x = m = 0
        last = self.wi
        for k in range(min(len(self.inputs), len(self.words))):
            inp, w = self.inputs[k], self.words[k]
            for j, ch in enumerate(inp):
                if j >= len(w):
                    x += 1
                elif ch == w[j]:
                    c += 1
                else:
                    i += 1
            if k < last or (k == last and self.finished and self.mode != "time"):
                m += max(0, len(w) - len(inp))
            if k < last:
                c += 1 if inp == w else 0     # пробел после слова
        return {"correct": c, "incorrect": i, "extra": x, "missed": m}

    def _wpm_chars(self) -> int:
        n = 0
        for k in range(min(self.wi, len(self.words))):
            if self.inputs[k] == self.words[k]:
                n += len(self.words[k]) + 1      # слово и пробел после него
        if self.wi < len(self.inputs):
            inp, w = self.inputs[self.wi], self.words[self.wi]
            if inp == w or (self.mode == "time" and w.startswith(inp)):
                n += len(inp)
        return n

    def wpm(self, el: float | None = None) -> float:
        el = self.elapsed() if el is None else el
        return self._wpm_chars() / 5 / (el / 60) if el > 0 else 0.0

    def raw(self, el: float | None = None) -> float:
        el = self.elapsed() if el is None else el
        typed = sum(len(s) for s in self.inputs) + self.wi
        return typed / 5 / (el / 60) if el > 0 else 0.0

    def acc(self) -> float:
        return 100.0 * self.correct_keys / self.total_keys if self.total_keys else 100.0

    def consistency(self) -> float:
        raws = [r for _w, r, _e in self.samples]
        if len(raws) < 2 or statistics.fmean(raws) <= 0:
            return 100.0 if raws else 0.0
        return max(0.0, kogasa(statistics.pstdev(raws) / statistics.fmean(raws)))

    def progress_label(self) -> str:
        """Жёлтый счётчик над текстом: «3/10» или оставшиеся секунды."""
        if self.mode == "time" and self.limit:
            return str(max(0, math.ceil(self.limit - self.elapsed())))
        total = len(self.words)
        return f"{self.wi}/{total}"

    def result(self) -> dict:
        el = self.elapsed()
        return {"ts": time.time(), "mode": self.mode, "mode2": self.limit,
                "wpm": round(self.wpm(el), 2), "raw": round(self.raw(el), 2), "acc": round(self.acc(), 2),
                "consistency": round(self.consistency(), 2), "time": round(el, 2),
                "chars": self.chars(), "words": self.wi + (1 if self.finished and self.mode != "time" else 0)}
