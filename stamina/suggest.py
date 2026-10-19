"""Подсказки для пульта набора: окончание слова или продолжение фразы.

Здесь только чистая логика — «что дописать». Как показать подсказку и как её
принять (Tab, стрелки, Esc), решает пульт набора `stamina/prompt_box.py`.

Словарь копится из того, что пилот уже писал и говорил: история чата, журнал
диктовки, темы и команды борта. Ничего не уходит в сеть — подсказки локальные.

    words = Dictionary()
    words.add_text("найди сращивания слов в книге")
    s = Suggester(words)
    s.best("найди сращ")        # → Suggestion(kind='phrase', tail='ивания слов', …)
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, NamedTuple

# слово: буквы, цифры, дефис и апостроф внутри, точка внутри имени файла
# («voice_input.py» — одно слово, «конец.» — без точки)
WORD_RE = re.compile(r"[\w\u0400-\u04FF][\w\u0400-\u04FF'\u2019\-]*"
                     r"(?:\.[\w\u0400-\u04FF'\u2019\-]+)*", re.UNICODE)
# границы фраз: точка, вопросительные, перевод строки, тире-разделитель
SENT_SPLIT = re.compile(r"[.!?…\n;•]+")

MIN_WORD = 2          # короче — предлог или мусор распознавания, в словарь не берём
MAX_PHRASE = 4        # самая длинная подсказка-фраза, слов
DEFAULT_LIMIT = 6     # сколько подсказок держать в списке
DEFAULT_MIN_PREFIX = 2


class Suggestion(NamedTuple):
    """Что допишется, если пилот нажмёт Tab.

    `tail` — ровно те символы, что добавляются к тексту до курсора (вместе с
    пробелами), `label` — как это показать в строке подсказки.
    """

    kind: str          # "phrase" или "word"
    tail: str
    label: str

    @property
    def is_phrase(self) -> bool:
        return self.kind == "phrase"


def words_of(text: str) -> list[str]:
    """Слова текста в порядке появления (регистр сохраняется)."""
    return [m.group(0) for m in WORD_RE.finditer(text or "")]


def phrases_of(text: str, *, max_words: int = MAX_PHRASE) -> list[str]:
    """Куски фраз длиной 2…max_words слов — для подсказок «продолжи фразу».

    Считаются только внутри предложения: склейка через точку дала бы подсказки
    вроде «книге и потом» — в чате это выглядит случайным текстом.
    """
    out: list[str] = []
    for sentence in SENT_SPLIT.split(text or ""):
        ws = words_of(sentence)
        for n in range(2, max_words + 1):
            for i in range(len(ws) - n + 1):
                out.append(" ".join(ws[i:i + n]))
    return out


def match_case(prefix: str, candidate: str) -> str:
    """Подсказка повторяет регистр пилота: «Прив» + «ет» = «Привет»."""
    if prefix[:1].isupper() and candidate[:1].islower():
        return candidate[:1].upper() + candidate[1:]
    return candidate


class Dictionary:
    """Слова и фразы пилота с частотами. Чем чаще писали — тем выше подсказка."""

    def __init__(self, *, min_word: int = MIN_WORD, max_phrase: int = MAX_PHRASE,
                 limit: int = 20000) -> None:
        self.min_word = min_word
        self.max_phrase = max_phrase
        self.limit = limit
        self.words: Counter = Counter()
        self.phrases: Counter = Counter()

    # -- наполнение
    def add_word(self, word: str, times: int = 1) -> None:
        word = (word or "").strip()
        if len(word) >= self.min_word and WORD_RE.fullmatch(word):
            self.words[word] += times

    def add_text(self, text: str, times: int = 1) -> None:
        """Разобрать текст на слова и фразы."""
        if not text:
            return
        for w in words_of(text):
            self.add_word(w, times)
        for p in phrases_of(text, max_words=self.max_phrase):
            self.phrases[p] += times
        self._maybe_trim()

    def add_many(self, texts: Iterable[str]) -> None:
        for t in texts:
            self.add_text(t)

    def _maybe_trim(self) -> None:
        """Обрезка — редко и заметно позже предела: иначе новые слова не успевают
        набрать частоту и вылетают раньше, чем становятся полезными."""
        if self.size > max(self.limit * 2, max(50, self.limit) + 10):
            self.trim()

    def trim(self) -> None:
        """Много текста: редкое убрать, частое оставить (память не растёт бесконечно)."""
        keep = max(50, self.limit)
        if len(self.words) > keep:
            self.words = Counter(dict(self.words.most_common(keep)))
        if len(self.phrases) > keep:
            self.phrases = Counter(dict(self.phrases.most_common(keep)))

    @property
    def size(self) -> int:
        return len(self.words) + len(self.phrases)


class Suggester:
    """Предлагает, чем закончить набранное: слово, словосочетание или фразу."""

    def __init__(self, dictionary: Dictionary | None = None, *,
                 min_prefix: int = DEFAULT_MIN_PREFIX,
                 limit: int = DEFAULT_LIMIT, phrase_limit: int = 3) -> None:
        self.dictionary = dictionary if dictionary is not None else Dictionary()
        self.min_prefix = min_prefix
        self.limit = limit
        self.phrase_limit = phrase_limit

    # -- основной вход
    def suggestions(self, text: str, cursor: int | None = None) -> list[Suggestion]:
        """Подсказки для текста до курсора: сначала фразы, потом отдельные слова."""
        head = text if cursor is None else text[:max(0, cursor)]
        if not head or head[-1].isspace():
            return []          # слово уже закончено пробелом — досказывать нечего
        words = WORD_RE.findall(head)
        if not words:
            return []
        prefix = words[-1]
        if len(prefix) < self.min_prefix:
            return []
        out: list[Suggestion] = []
        out.extend(self._phrase_hints(words, prefix))
        out.extend(self._word_hints(prefix))
        seen: set[str] = set()
        unique: list[Suggestion] = []
        for item in out:
            if item.tail and item.tail not in seen:
                seen.add(item.tail)
                unique.append(item)
        return unique[:self.limit]

    def best(self, text: str, cursor: int | None = None) -> Suggestion | None:
        items = self.suggestions(text, cursor)
        return items[0] if items else None

    # -- внутреннее
    def _word_hints(self, prefix: str) -> list[Suggestion]:
        low = prefix.lower()
        found = [(count, w) for w, count in self.dictionary.words.items()
                 if w.lower().startswith(low) and w.lower() != low]
        found.sort(key=lambda pair: (-pair[0], pair[1].lower()))
        out: list[Suggestion] = []
        for _count, word in found:
            full = match_case(prefix, word)
            out.append(Suggestion("word", full[len(prefix):], full))
        return out

    def _phrase_hints(self, words: list[str], prefix: str) -> list[Suggestion]:
        """Контекст из предыдущих слов: «найди сращ» → «ивания слов».

        Две ступени: докончить начатое слово (в середине фразы) и — если слово уже
        набрано целиком — подсказать следующее («проверь» → « тесты»).
        """
        low_prefix = prefix.lower()
        out: list[Suggestion] = []
        context_len = min(3, len(words) - 1)
        for take in range(context_len, 0, -1):
            context = " ".join(w.lower() for w in words[-1 - take:-1])
            if not context:
                continue
            out.extend(self._match_phrases(context, prefix, low_prefix))
            if len(out) >= self.phrase_limit:
                return out[:self.phrase_limit]
        # слово набрано целиком — предложить продолжение фразы
        for take in range(min(3, len(words)), 0, -1):
            context = " ".join(w.lower() for w in words[-take:])
            rest = self._next_after(context)
            if rest:
                out.append(Suggestion("phrase", " " + rest, f"{context} {rest}"))
                if len(out) >= self.phrase_limit:
                    break
        return out[:self.phrase_limit]

    def _match_phrases(self, context: str, prefix: str, low_prefix: str) -> list[Suggestion]:
        """Фразы словаря, продолжающие `context` словом на `prefix`."""
        out: list[Suggestion] = []
        for phrase, _count in self.dictionary.phrases.most_common():
            low = phrase.lower()
            if not low.startswith(context + " "):
                continue
            rest = low[len(context) + 1:]
            if not rest.startswith(low_prefix) or rest == low_prefix:
                continue
            first = words_of(rest)[0]
            full = match_case(prefix, first) + rest[len(first):]
            out.append(Suggestion("phrase", full[len(prefix):], f"{context} {full}".strip()))
            if len(out) >= self.phrase_limit:
                break
        return out

    def _next_after(self, context: str) -> str:
        """Чем чаще всего продолжается `context` в словаре фраз («проверь» → «тесты»)."""
        for phrase, _count in self.dictionary.phrases.most_common():
            low = phrase.lower()
            if low.startswith(context + " ") and len(low) > len(context) + 1:
                return low[len(context) + 1:]
        return ""


def dictionary_from(texts: Iterable[str], *, min_word: int = MIN_WORD) -> Dictionary:
    """Собрать словарь из готовых текстов (история чата, журнал диктовки, темы)."""
    d = Dictionary(min_word=min_word)
    d.add_many(texts)
    return d
