"""Соответствие позиций между оригиналом текста и подготовленной для печати версией.

Оригинал режется на токены по пробельным символам; каждый токен прогоняется через ту же
функцию подготовки, что и весь текст (``text_processing.process_text``). Непустые результаты
по порядку = слова подготовленной версии. Так получаем якоря «слово оригинала ↔ символ
подготовленного текста».

Карта строится **порциями** и достраивается по ходу: при открытии книги считается только
начало, дальше она растёт со скоростью печати пилота плюс 100 слов в минуту запаса
(``PACE_EXTRA_WPM``). Так книга в 100 000 слов не блокирует окно: полное построение
карты занимало больше минуты и кабина «зависала».

Расхождение списков слов (склейки по словарю книги, другие опции подготовки) выравнивается
линейным проходом окнами (``align_words``), а не полным сравнением ``difflib`` — точность
та же (±1 слово), стоимость линейная. ``difflib`` остаётся только для коротких текстов.
"""
from __future__ import annotations

import bisect
import difflib
import re
import time
from typing import Callable

_WORD_RE = re.compile(r"\S+")

# До этого размера можно позволить точное выравнивание difflib: он квадратичен по
# времени и на книге в 100 000 слов занимает больше минуты, блокируя окно.
_DIFFLIB_LIMIT = 4000
# Окно поиска при линейном выравнивании: насколько далеко ищем совпадение, если
# соседние слова разошлись (склейки, вставки, пропуски).
_ALIGN_WINDOW = 16
# Сколько слов строим сразу при открытии книги: печатать можно начинать немедленно.
INITIAL_WORDS = 1500
# Сколько слов в минуту подгружаем сверх скорости набора пилота.
PACE_EXTRA_WPM = 100
# Нижняя граница: даже если пилот ещё не начал, текст понемногу подгружается вперёд.
MIN_PACE_WPM = 100
DEFAULT_PACE_WPM = 300
# Запас вперёд, чтобы карта всегда была готова раньше курсора.
MIN_AHEAD_WORDS = 600


def load_pace_wpm(typed_wpm: float = 0.0) -> float:
    """Скорость подгрузки книги: скорость набора пилота плюс 100 слов в минуту.

    Скорость набора берётся из его последней сессии, поэтому подгрузка сама растёт
    по мере того, как пилот печатает быстрее.
    """
    return max(float(MIN_PACE_WPM), float(typed_wpm) + PACE_EXTRA_WPM)


def tokens(text: str) -> list[tuple[int, int]]:
    """Позиции (start, end) всех токенов (слов с прилипшей пунктуацией)."""
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def align_words(owners: list[int], parts: list[str], prep_words: list[str],
                prep_spans: list[tuple[int, int]],
                window: int = _ALIGN_WINDOW) -> tuple[list[tuple[int, int]], int, int]:
    """Линейное выравнивание словами, окнами (малыми частями).

    Идём по обоим спискам двумя указателями; при расхождении ищем ближайшее
    совпадение в пределах ``window`` слов и перескакиваем пропуск. Стоимость
    линейная (на книге 100 000 слов — доли секунды), точность ±1 слово.

    Возвращает пары (индекс токена оригинала, начало слова в подготовленном тексте)
    и сколько элементов каждого списка израсходовано — чтобы продолжать с того же места.
    """
    pairs: list[tuple[int, int]] = []
    i = j = 0
    n, m = len(parts), len(prep_words)
    while i < n and j < m:
        if parts[i] == prep_words[j]:
            pairs.append((owners[i], prep_spans[j][0]))
            i += 1
            j += 1
            continue
        step_i = step_j = 0
        for d in range(1, window + 1):
            if i + d < n and parts[i + d] == prep_words[j]:
                step_i, step_j = d, 0
                break
            if j + d < m and parts[i] == prep_words[j + d]:
                step_i, step_j = 0, d
                break
        if not step_i and not step_j:
            step_i = step_j = 1      # расхождение: пропускаем по одному слову с обеих сторон
        i += step_i
        j += step_j
    return pairs, i, j


class TextMap:
    """Якоря между словами оригинала (индекс токена) и символами подготовленного текста.

    ``limit_words`` — сколько слов подготовленного текста сопоставить сразу; остальное
    достраивается методом :meth:`ensure` порциями.
    """

    def __init__(self, original: str, prepared: str, process: Callable[[str], str],
                 limit_words: int | None = None) -> None:
        self._original = original
        self._process = process
        self.orig_tokens = tokens(original)
        self.prep_spans = tokens(prepared)
        self.prep_starts_all = [s for s, _e in self.prep_spans]
        self._prep_words = [prepared[s:e] for s, e in self.prep_spans]

        self._parts: list[str] = []        # слова, полученные из токенов оригинала
        self._owners: list[int] = []       # индекс токена оригинала для каждого слова
        self._k = 0                        # сколько токенов оригинала обработано
        self._parts_i = 0                  # сколько слов уже выровнено
        self._pairs: list[tuple[int, int]] = []
        self._orig_idx: list[int] = []
        self._prep_pos: list[int] = []
        self._built = 0                    # сколько слов подготовленного текста покрыто
        self._ahead = 0.0                  # накопленный запас вперёд (в словах)
        self._last = time.monotonic()

        total = len(self._prep_words)
        if limit_words is None:
            target = total
        else:
            target = min(max(1, int(limit_words)), total)
        self._grow_to(target)

        self.exact = self._complete() and self._parts == self._prep_words
        self.prefix = (not self.exact and self._complete()
                       and len(self._parts) >= len(self._prep_words)
                       and self._parts[:len(self._prep_words)] == self._prep_words)
        self.ok = bool(self._pairs) or (not self._parts and not self._prep_words)

    # -- построение порциями ----------------------------------------------------
    def _complete(self) -> bool:
        return self._built >= len(self._prep_words)

    def _grow_to(self, target_words: int) -> None:
        """Достроить карту до указанного слова подготовленного текста."""
        total = len(self._prep_words)
        target = min(max(int(target_words), 0), total)
        if target <= self._built:
            return
        want_parts = target + _ALIGN_WINDOW
        while self._k < len(self.orig_tokens) and len(self._parts) < want_parts:
            s, e = self.orig_tokens[self._k]
            w = self._process(self._original[s:e])
            if w:
                for sub in w.split():
                    self._parts.append(sub)
                    self._owners.append(self._k)
            self._k += 1
        stop = min(total, target + _ALIGN_WINDOW)
        while self._built < target and self._parts_i < len(self._parts):
            pairs, used_p, used_w = align_words(
                self._owners[self._parts_i:], self._parts[self._parts_i:],
                self._prep_words[self._built:stop], self.prep_spans[self._built:stop],
            )
            if used_p <= 0 and used_w <= 0:
                break
            self._pairs.extend(pairs)
            self._orig_idx.extend(p[0] for p in pairs)
            self._prep_pos.extend(p[1] for p in pairs)
            self._parts_i += used_p
            self._built += used_w
            if self._k >= len(self.orig_tokens) and self._parts_i >= len(self._parts):
                break

    def ensure(self, prep_char: int = 0, pace_wpm: float = DEFAULT_PACE_WPM,
               now: float | None = None) -> None:
        """Достроить карту под текущую позицию и подгрузить запас порциями.

        Прыжок по тексту (позиция дальше построенного) добирается сразу, порциями;
        обычный ход — со скоростью ``pace_wpm`` слов в минуту (см. ``load_pace_wpm``).
        """
        total = len(self._prep_words)
        if self._complete():
            return
        moment = time.monotonic() if now is None else now
        dt = max(0.0, moment - self._last)
        self._last = moment
        self._ahead += max(0.0, float(pace_wpm)) / 60.0 * dt

        need = 0
        if prep_char > 0:
            need = bisect.bisect_right(self.prep_starts_all, int(prep_char))
        target = int(need + MIN_AHEAD_WORDS + self._ahead)
        if target <= self._built:
            return
        step = 512
        while self._built < target:
            self._grow_to(min(total, self._built + step))
            if self._complete():
                break
            if self._k >= len(self.orig_tokens) and self._parts_i >= len(self._parts):
                break

    # -- поиск ------------------------------------------------------------------
    def prep_to_orig(self, char: int) -> int:
        """Символ подготовленного текста → индекс слова (токена) оригинала."""
        if not self._prep_pos:
            return 0
        self.ensure(char)
        i = bisect.bisect_right(self._prep_pos, max(0, char)) - 1
        return self._orig_idx[max(0, i)]

    def orig_to_prep(self, word: int) -> int:
        """Индекс слова оригинала → символ начала соответствующего слова подготовленного текста."""
        if not self._orig_idx:
            return 0
        i = bisect.bisect_left(self._orig_idx, max(0, word))
        if i >= len(self._orig_idx):
            i = len(self._orig_idx) - 1
        return self._prep_pos[i]

    def orig_char_of_word(self, word: int) -> int:
        if not self.orig_tokens:
            return 0
        word = max(0, min(word, len(self.orig_tokens) - 1))
        return self.orig_tokens[word][0]

    def prepared_word_count(self) -> int:
        return len(self.prep_starts_all)

    # -- состояние --------------------------------------------------------------
    @property
    def coverage(self) -> float:
        return (len(self._pairs) / len(self._prep_words)) if self._prep_words else 1.0

    @property
    def built_words(self) -> int:
        """Сколько слов подготовленного текста уже сопоставлено."""
        return self._built


def fragment_of(original: str, prepared: str, process: Callable[[str], str]) -> str | None:
    """Если ``prepared`` — начало подготовленного ``original``, вернуть соответствующий кусок
    оригинала (до конца последнего слова + хвостовая пунктуация/переводы строк до следующего слова)."""
    tm = TextMap(original, prepared, process)
    if tm.exact:
        return original
    if not tm.prefix or not tm._orig_idx:
        return None
    last_tok = tm._orig_idx[-1]
    nxt = last_tok + 1
    # подтягиваем «пустые» токены (тире, многоточия) сразу после последнего слова
    while nxt < len(tm.orig_tokens):
        s, e = tm.orig_tokens[nxt]
        if process(original[s:e]):
            break
        nxt += 1
    end = tm.orig_tokens[nxt - 1][1]
    frag = original[:end].rstrip() + "\n"
    if process(frag) != prepared:
        return None
    return frag
