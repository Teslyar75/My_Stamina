"""Архив Ориона: фрагменты вокруг совпадений и подсветка найденных слов.

Чистые функции без Tk: их зовёт и фоновый поиск, и экран. Регистр не важен,
пересекающиеся совпадения склеиваются в одно.
"""
from __future__ import annotations

#: Сколько знаков показывать вокруг совпадения в списке находок.
SNIPPET_WIDTH = 80


def hit_spans(text: str, words) -> list[tuple[int, int]]:
    """Все места, где в тексте стоят искомые слова: [(начало, конец), ...] по порядку."""
    low = (text or "").lower()
    spans: list[tuple[int, int]] = []
    for word in words or ():
        word = str(word or "").lower()
        if not word:
            continue
        start = low.find(word)
        while start >= 0:
            spans.append((start, start + len(word)))
            start = low.find(word, start + len(word))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def snippet(text: str, words, width: int = SNIPPET_WIDTH) -> tuple[str, list[tuple[int, int]]]:
    """Фрагмент вокруг первого совпадения и места совпадений внутри фрагмента.

    Нет совпадения в тексте (нашлось по дате или имени агента) — начало реплики.
    Режем по пробелу, чтобы не рвать слова; обрезанные края помечаем «…».
    """
    flat = " ".join(str(text or "").split())
    spans = hit_spans(flat, words)
    if len(flat) <= width:
        return flat, spans
    if spans:
        first_a, first_b = spans[0]
        side = max(0, (width - (first_b - first_a)) // 2)
        start = max(0, first_a - side)
        end = min(len(flat), max(first_b, start + width))
        start = max(0, min(start, end - width))
    else:
        start, end = 0, width
    if start > 0:
        cut = flat.find(" ", start, first_a if spans else end)
        if cut >= 0:
            start = cut + 1
    if end < len(flat):
        cut = flat.rfind(" ", spans[0][1] if spans else start, end)
        if cut > start:
            end = cut
    lead = "…" if start > 0 else ""
    tail = "…" if end < len(flat) else ""
    body = flat[start:end]
    shift = len(lead) - start
    inner = [(max(a, start) + shift, min(b, end) + shift) for a, b in spans
             if b > start and a < end]
    return lead + body + tail, inner


def prepare(rows: list[dict], words) -> list[tuple[str, list[tuple[int, int]]]]:
    """Фрагменты для всех находок разом — считается в фоновом потоке."""
    return [snippet(str(m.get("text") or ""), words) for m in rows]


def context(messages: list[dict], msg_id: str, around: int = 2) -> tuple[list[dict], int]:
    """Соседи реплики в разговоре: (окно сообщений, позиция самой реплики в окне)."""
    for pos, msg in enumerate(messages):
        if str(msg.get("id") or "") == msg_id:
            lo = max(0, pos - around)
            return messages[lo:pos + around + 1], pos - lo
    return [], -1
