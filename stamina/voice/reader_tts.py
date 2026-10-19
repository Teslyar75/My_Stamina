"""Очередь чтения вслух: текст книги → предложения → движок озвучки.

Движок (`stamina/voice/engine.py`) умеет произнести одну фразу. Книгу читает этот слой:

* режет текст на предложения и держит их границы **в символах** — по ним читалка рисует
  подсветку и переворачивает страницу;
* отправляет предложения по одному, следующее — сразу после `DONE` предыдущего
  (пауза между фразами остаётся только на время отклика движка);
* умеет `play / pause / resume / stop`, шаг вперёд-назад, прыжок «читать с этого места»,
  скорость и голос;
* события для интерфейса отдаёт через `poll()`, поэтому tkinter не замирает.

Пример:

    q = ReaderQueue(make_engine("sapi"))
    q.load(text, start=char_of_page)
    q.play()
    while True:
        for kind, seg in q.poll():
            if kind == "segment":
                highlight(seg.start, seg.end)
        ...
        root.update()
"""

from __future__ import annotations

import re
from typing import NamedTuple


#: Конец предложения: точка/!/?/… (в том числе «ёлочки» после них), затем пробел.
_SENT_END = re.compile(r"(?<=[.!?…])[\"'»”)]*\s+")
#: Внутри длинного предложения — где можно разрезать: по ; : , или по пробелу.
_SOFT_CUT = re.compile(r"(?<=[;:,])\s+")
_PARAGRAPH = re.compile(r"\n\s*\n")

#: Предложение короче — приклеиваем к следующему («— Да.» читать отдельно нечего).
MIN_CHARS = 24
#: Предложение длиннее — режем по запятым: длинную фразу движок тянет долго и подсветка мертва.
MAX_CHARS = 320


class Segment(NamedTuple):
    """Кусок текста для одной фразы: границы в символах исходного текста."""

    index: int
    start: int
    end: int
    text: str

    @property
    def length(self) -> int:
        return self.end - self.start


def speech_ready(text: str) -> str:
    """Почистить фразу перед озвучкой: сноски-звёздочки, лишние пробелы, дефис-тире в начале."""
    t = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^\s*[*•·—–-]\s*", "", t)       # маркер списка в начале
    t = re.sub(r"\[\d+\]", "", t)               # сноски [12]
    return t.strip()


def _cut_long(start: int, text: str, out: list[Segment], limit: int) -> None:
    """Разрезать длинный кусок по мягким границам (запятая, двоеточие), иначе по пробелу."""
    pos = 0
    n = len(text)
    while pos < n:
        rest = n - pos
        if rest <= limit:
            piece = text[pos:]
        else:
            window = text[pos:pos + limit]
            cuts = [m.end() for m in _SOFT_CUT.finditer(window)]
            cut = next((c for c in reversed(cuts) if c >= limit // 2), 0)
            if not cut:
                cut = window.rfind(" ")
            if cut < limit // 3:
                cut = limit
            piece = text[pos:pos + cut]
        piece_len = len(piece)
        head = piece.lstrip()
        lead = piece_len - len(head)
        body = head.rstrip()
        if body:
            out.append(Segment(len(out), start + pos + lead, start + pos + lead + len(body), body))
        pos += piece_len


def split_segments(text: str, *, min_chars: int = MIN_CHARS, max_chars: int = MAX_CHARS) -> list[Segment]:
    """Разбить текст на фразы с границами в символах.

    Абзацы не склеиваем: конец абзаца — всегда конец фразы (так подсветка не «перепрыгивает»
    через пустую строку). Слишком короткие обрывки приклеиваем к следующей фразе.
    """
    text = text or ""
    pieces: list[tuple[int, str]] = []
    for para in _PARAGRAPH.split(text):
        para_start = _offset_of(text, para, pieces)
        pos = 0
        for m in _SENT_END.finditer(para):
            chunk = para[pos:m.start()]
            if chunk.strip():
                pieces.append((para_start + pos, chunk))
            pos = m.end()
        tail = para[pos:]
        if tail.strip():
            pieces.append((para_start + pos, tail))

    merged: list[tuple[int, str]] = []
    for start, chunk in pieces:
        stripped = chunk.strip()
        lead = len(chunk) - len(chunk.lstrip())
        if not stripped:
            continue
        if merged and len(merged[-1][1]) < min_chars:
            prev_start, prev = merged.pop()
            merged.append((prev_start, (prev + " " + stripped).strip()))
        else:
            merged.append((start + lead, stripped))
    if len(merged) >= 2 and len(merged[-1][1]) < min_chars:
        last_start, last = merged.pop()
        prev_start, prev = merged.pop()
        merged.append((prev_start, (prev + " " + last).strip()))

    out: list[Segment] = []
    for start, chunk in merged:
        if len(chunk) <= max_chars:
            out.append(Segment(len(out), start, start + len(chunk), chunk))
        else:
            _cut_long(start, chunk, out, max_chars)
    return [s._replace(index=i) for i, s in enumerate(out)]


def _offset_of(text: str, para: str, taken: list[tuple[int, str]]) -> int:
    """Где абзац начинается в исходном тексте (абзацы уникальны — ищем по порядку от прошлого)."""
    from_pos = taken[-1][0] + len(taken[-1][1]) if taken else 0
    found = text.find(para, from_pos)
    return found if found >= 0 else from_pos


class ReaderQueue:
    """Читает текст вслух фразами. Состояние: `idle` / `playing` / `paused`."""

    def __init__(self, engine, text: str = "", *, rate: int = 0, lang: str = "",
                 duck_radio: bool = True, voice: str = "") -> None:
        self.engine = engine
        self.rate = int(rate)
        self.lang = lang
        self.voice = voice          # голос, выбранный пилотом (пусто — по языку текста)
        self.duck_radio = duck_radio
        self.segments: list[Segment] = []
        self.index = 0                # какая фраза сейчас / следующая к отправке
        self.state = "idle"
        self.last_error = ""
        self.text = ""
        self._sid_to_index: dict[int, int] = {}
        self._events: list[tuple] = []
        if text:
            self.load(text)

    # -- загрузка ----------------------------------------------------------------------
    def load(self, text: str, start: int = 0) -> None:
        """Загрузить текст (и, если нужно, встать на символ `start`)."""
        self.stop()
        self.text = text or ""
        self.segments = split_segments(self.text)
        self.index = self.index_of_char(start) if start else 0
        self.state = "idle"

    def index_of_char(self, char: int) -> int:
        """Номер фразы, накрывающей символ (для «читать с этого места»)."""
        for seg in self.segments:
            if seg.end > char:
                return seg.index
        return max(0, len(self.segments) - 1)

    # -- управление --------------------------------------------------------------------
    def play(self, from_char: int | None = None) -> None:
        """Читать: с начала, с места в тексте или с текущей фразы."""
        if not self.segments:
            return
        if from_char is not None:
            self.index = self.index_of_char(from_char)
        self.index = max(0, min(self.index, len(self.segments) - 1))
        self.state = "playing"
        self._duck()
        self._send_current()

    def pause(self) -> None:
        """Пауза: оборвать текущую фразу. Продолжение — с её начала."""
        if self.state != "playing":
            return
        self.state = "paused"
        self.engine.stop()
        self._unduck()

    def resume(self) -> None:
        if self.state == "paused":
            self.play()

    def toggle(self) -> None:
        if self.state == "playing":
            self.pause()
        else:
            self.play() if self.state == "paused" else self.play(from_char=self.current_char())

    def stop(self) -> None:
        """Полная остановка: движок молчит, состояние сброшено (позиция остаётся)."""
        if self.state != "idle":
            try:
                self.engine.stop()
            except Exception:  # noqa: BLE001
                pass
        self.state = "idle"
        self._sid_to_index.clear()
        self._unduck()

    def step(self, delta: int) -> None:
        """Шаг на фразу вперёд/назад. На ходу — сразу переключиться на новую."""
        if not self.segments:
            return
        self.index = max(0, min(self.index + int(delta), len(self.segments) - 1))
        if self.state == "playing":
            self._send_current()

    def jump_to(self, char: int) -> None:
        self.index = self.index_of_char(char)
        if self.state == "playing":
            self._send_current()

    def set_rate(self, rate: int) -> None:
        self.rate = max(-10, min(10, int(rate)))

    def set_lang(self, lang: str) -> None:
        self.lang = lang or ""

    def set_voice(self, voice: str) -> None:
        """Сменить голос на ходу: следующая фраза пойдёт уже им."""
        self.voice = voice or ""

    # -- состояние ---------------------------------------------------------------------
    @property
    def current(self) -> Segment | None:
        if not self.segments:
            return None
        return self.segments[max(0, min(self.index, len(self.segments) - 1))]

    @property
    def current_char(self) -> int:
        seg = self.current
        return seg.start if seg else 0

    def progress(self) -> tuple[int, int]:
        """(прочитано знаков, всего знаков) — для полосы прогресса."""
        total = len(self.text)
        done = self.segments[0].start if self.segments else 0
        if self.state == "playing" and self.current:
            done = self.current.start
        elif self.state == "paused" and self.current:
            done = self.current.start
        return done, total

    def poll(self) -> list[tuple]:
        """События для интерфейса: (`segment`, Segment) / (`finished`, None) / (`error`, str)."""
        if self.engine is not None:
            for kind, sid, extra in self.engine.poll():
                self._on_engine(kind, sid, extra)
        out, self._events = self._events, []
        return out

    # -- внутреннее --------------------------------------------------------------------
    def _send_current(self) -> None:
        seg = self.current
        if seg is None:
            self.state = "idle"
            return
        self.index = seg.index
        text = speech_ready(seg.text)
        if not text:
            self._advance()
            return
        sid = self.engine.speak(text, rate=self.rate, lang=self.lang,
                                voice=self.voice)
        if not sid:
            self.last_error = getattr(self.engine, "last_error", "") or "движок озвучки не ответил"
            self.state = "idle"
            self._events.append(("error", self.last_error))
            self._unduck()
            return
        self._sid_to_index[sid] = seg.index
        self._events.append(("segment", seg))

    def _advance(self) -> None:
        if self.index + 1 >= len(self.segments):
            self.state = "idle"
            self._events.append(("finished", None))
            self._unduck()
            return
        self.index += 1

    def _on_engine(self, kind: str, sid: int, extra: str) -> None:
        if kind == "done":
            if self.state != "playing":
                return
            self._sid_to_index.pop(sid, None)
            self._advance()
            if self.state == "playing":
                self._send_current()
        elif kind == "cancel":
            self._sid_to_index.pop(sid, None)
        elif kind in ("error", "dead"):
            self.last_error = extra or self.last_error
            idx = self._sid_to_index.pop(sid, None)
            if idx is not None or kind == "dead":
                self.state = "idle"
                self._events.append(("error", self.last_error))
                self._unduck()

    def _duck(self) -> None:
        """Приглушить радио: книгу читаем вслух, музыка мешает."""
        if not self.duck_radio:
            return
        try:
            from stamina.radio.engine import get_engine
            get_engine().duck(10)
        except Exception:  # noqa: BLE001
            pass

    def _unduck(self) -> None:
        if not self.duck_radio:
            return
        try:
            from stamina.radio.engine import get_engine
            get_engine().unduck()
        except Exception:  # noqa: BLE001
            pass
