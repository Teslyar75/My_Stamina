"""Соответствие позиций между оригиналом текста и подготовленной для печати версией.

Оригинал режется на токены по пробельным символам; каждый токен прогоняется через ту же
функцию подготовки, что и весь текст (``text_processing.process_text``). Непустые результаты
по порядку = слова подготовленной версии. Так получаем якоря «слово оригинала ↔ символ
подготовленного текста». Если быстрая проверка не сходится (другие опции, редкие символы),
используется выравнивание слов через ``difflib`` (точность ±1 слово).
"""
from __future__ import annotations

import bisect
import difflib
import re
from typing import Callable

_WORD_RE = re.compile(r"\S+")


def tokens(text: str) -> list[tuple[int, int]]:
    """Позиции (start, end) всех токенов (слов с прилипшей пунктуацией)."""
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


class TextMap:
    """Якоря между словами оригинала (индекс токена) и символами подготовленного текста."""

    def __init__(self, original: str, prepared: str, process: Callable[[str], str]) -> None:
        self.orig_tokens = tokens(original)
        prep_spans = tokens(prepared)
        self.prep_starts_all = [s for s, _e in prep_spans]
        parts: list[str] = []
        owners: list[int] = []
        for k, (s, e) in enumerate(self.orig_tokens):
            w = process(original[s:e])
            if not w:
                continue
            for sub in w.split():
                parts.append(sub)
                owners.append(k)
        prep_words = [prepared[s:e] for s, e in prep_spans]
        self.exact = parts == prep_words
        self.prefix = False
        # пары (индекс токена оригинала, начало слова в подготовленном тексте), по возрастанию
        pairs: list[tuple[int, int]] = []
        if self.exact:
            pairs = [(owners[i], prep_spans[i][0]) for i in range(len(parts))]
        elif len(parts) >= len(prep_words) and parts[:len(prep_words)] == prep_words:
            self.prefix = True  # оригинал длиннее (подготовлен фрагмент)
            pairs = [(owners[i], prep_spans[i][0]) for i in range(len(prep_words))]
        else:
            sm = difflib.SequenceMatcher(None, parts, prep_words, autojunk=False)
            for a, b, n in sm.get_matching_blocks():
                for j in range(n):
                    pairs.append((owners[a + j], prep_spans[b + j][0]))
        self.ok = bool(pairs) or (not parts and not prep_words)
        self.coverage = (len(pairs) / len(prep_words)) if prep_words else 1.0
        self._orig_idx = [p[0] for p in pairs]
        self._prep_pos = [p[1] for p in pairs]

    # ------------------------------------------------------------------
    def prep_to_orig(self, char: int) -> int:
        """Символ подготовленного текста → индекс слова (токена) оригинала."""
        if not self._prep_pos:
            return 0
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
