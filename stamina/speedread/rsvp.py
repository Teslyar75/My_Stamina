"""Ядро гипердрайва (RSVP) без GUI: слова, точка фиксации (ORP), кадры, тайминги, разгон."""
from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"\S+")
_CORE_RE = re.compile(r"[\w\u00C0-\u024F\u0400-\u04FF]", re.UNICODE)
SENT_END = (".", "!", "?", "…")
CLAUSE = (",", ";", ":", "—", "–")
CHAPTER_RE = re.compile(r"^\s*(глава|часть|chapter|part|book|книга)\b", re.IGNORECASE)


@dataclass
class Word:
    text: str
    start: int
    end: int
    para_end: bool = False     # после слова — конец абзаца
    sent_end: bool = False     # слово заканчивает предложение
    chapter: bool = False      # слово начинает строку-заголовок главы


def tokenize(text: str) -> list[Word]:
    """Слова оригинала с отметками конца предложения/абзаца и начала глав."""
    words: list[Word] = []
    matches = list(_WORD_RE.finditer(text))
    for i, m in enumerate(matches):
        w = Word(m.group(), m.start(), m.end())
        nxt = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        gap = text[m.end():nxt]
        w.para_end = gap.count("\n") >= 2 or (i + 1 == len(matches))
        core = w.text.rstrip("\"'»”’)]")
        w.sent_end = core.endswith(SENT_END) or w.para_end
        line_start = text.rfind("\n", 0, m.start()) + 1
        if line_start == m.start() or i == 0:
            line_end = text.find("\n", m.start())
            line = text[m.start(): line_end if line_end >= 0 else len(text)]
            w.chapter = bool(CHAPTER_RE.match(line)) and len(line) < 60
        words.append(w)
    return words


def core_span(word: str) -> tuple[int, int]:
    """Границы «буквенной» части слова (без кавычек/скобок/пунктуации по краям)."""
    letters = [i for i, ch in enumerate(word) if _CORE_RE.match(ch)]
    if not letters:
        return 0, len(word)
    return letters[0], letters[-1] + 1


def orp_offset(length: int) -> int:
    """Индекс точки фиксации по длине слова (SPEC §3.2)."""
    if length <= 1:
        return 0
    if length <= 5:
        return 1
    if length <= 9:
        return 2
    if length <= 13:
        return 3
    return 4


def orp_index(word: str) -> int:
    """Индекс красной буквы внутри токена (с учётом пунктуации по краям)."""
    a, b = core_span(word)
    return a + min(orp_offset(b - a), max(0, b - a - 1))


def frame_at(words: list[Word], start: int, n: int, max_chars: int = 24) -> list[int]:
    """Индексы слов одного кадра: до n слов, не через конец предложения, не длиннее max_chars."""
    if start >= len(words):
        return []
    out = [start]
    length = len(words[start].text)
    i = start
    while len(out) < n and not words[i].sent_end and i + 1 < len(words):
        nxt = words[i + 1]
        if length + 1 + len(nxt.text) > max_chars or nxt.chapter:
            break
        i += 1
        out.append(i)
        length += 1 + len(nxt.text)
    return out


def frame_text(words: list[Word], frame: list[int]) -> tuple[str, int]:
    """Текст кадра и индекс красной буквы в нём (ORP центрального слова)."""
    parts = [words[i].text for i in frame]
    mid = (len(frame) - 1) // 2
    pos = sum(len(p) + 1 for p in parts[:mid]) + orp_index(parts[mid])
    return " ".join(parts), pos


def multiplier(words: list[Word], frame: list[int], punct: bool = True) -> float:
    """Множитель времени кадра (SPEC §3.5) — берётся наибольший."""
    if not punct:
        return 1.0
    m = 1.0
    for i in frame:
        w = words[i]
        a, b = core_span(w.text)
        letters = b - a
        if letters > 12:
            m = max(m, 1.6)
        elif letters > 8:
            m = max(m, 1.3)
        if any(ch.isdigit() for ch in w.text):
            m = max(m, 1.4)
        if w.text[:1] in "«\"“(„[":
            m = max(m, 1.2)
    last = words[frame[-1]]
    tail = last.text.rstrip("\"'»”’)]")
    if last.para_end:
        m = max(m, 3.0)
    elif last.sent_end:
        m = max(m, 2.2)
    elif tail.endswith(CLAUSE) or last.text in ("—", "–"):
        m = max(m, 1.5)
    return m


def frame_ms(words: list[Word], frame: list[int], wpm: float, punct: bool = True) -> float:
    """Длительность показа кадра в миллисекундах."""
    base = 60000.0 / max(30.0, wpm)
    return base * len(frame) * multiplier(words, frame, punct)


class Ramp:
    """Плавный разгон: +step слов/мин каждые every_s секунд чтения до цели."""

    def __init__(self, start: float, target: float, step: float = 10, every_s: float = 30,
                 mode: str = "smooth") -> None:
        self.wpm = float(start)
        self.target = float(target)
        self.step = float(step)
        self.every_s = float(every_s)
        self.mode = mode           # smooth | steps | off
        self._acc = 0.0
        self._words = 0
        self._downs: list[float] = []
        self._plateau_until = 0.0
        self._clock = 0.0

    def tick(self, dt: float, words: int = 0) -> None:
        """Учесть dt секунд чтения (паузы не передавать) и прочитанные слова."""
        self._clock += dt
        if self.mode == "off" or self.wpm >= self.target or self._clock < self._plateau_until:
            return
        if self.mode == "steps":
            self._words += words
            while self._words >= 500 and self.wpm < self.target:
                self._words -= 500
                self.wpm = min(self.target, self.wpm + 50)
            return
        self._acc += dt
        while self._acc >= self.every_s and self.wpm < self.target:
            self._acc -= self.every_s
            self.wpm = min(self.target, self.wpm + self.step)

    def manual(self, delta: float) -> None:
        """Пилот сам изменил скорость; два снижения за минуту — плато на 2 минуты."""
        self.wpm = max(100.0, min(1500.0, self.wpm + delta))
        self._acc = 0.0
        if delta < 0:
            self._downs = [t for t in self._downs if self._clock - t < 60] + [self._clock]
            if len(self._downs) >= 2:
                self._plateau_until = self._clock + 120
                self._downs.clear()

    @property
    def ramping(self) -> bool:
        return self.mode != "off" and self.wpm < self.target and self._clock >= self._plateau_until


def sentence_start(words: list[Word], i: int) -> int:
    """Начало предложения, в котором слово i (для «назад на предложение»)."""
    i = max(0, min(i, len(words) - 1))
    j = i - 1
    while j >= 0 and not words[j].sent_end:
        j -= 1
    return j + 1


def prev_sentence(words: list[Word], i: int) -> int:
    s = sentence_start(words, i)
    if s == i and s > 0:
        s = sentence_start(words, s - 1)
    return s


def next_sentence(words: list[Word], i: int) -> int:
    j = i
    while j < len(words) - 1 and not words[j].sent_end:
        j += 1
    return min(len(words) - 1, j + 1)


def paragraph_start(words: list[Word], i: int) -> int:
    j = max(0, min(i, len(words) - 1)) - 1
    while j >= 0 and not words[j].para_end:
        j -= 1
    return j + 1


def chapter_start(words: list[Word], i: int) -> int:
    for j in range(min(i, len(words) - 1), -1, -1):
        if words[j].chapter:
            return j
    return 0
