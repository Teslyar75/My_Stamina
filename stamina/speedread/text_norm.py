"""Нормализация текста книги для читалки (Gutenberg hard-wrap → абзацы)."""
from __future__ import annotations

import re


_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SINGLE_NL = re.compile(r"(?<!\n)\n(?!\n)")
_MULTI_NL = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]+")


def normalize_book_text(raw: str) -> str:
    """Склеить жёсткие переносы Gutenberg; абзац = пустая строка.

    - ``exam-\\nple`` → ``example``
    - одиночный ``\\n`` → пробел
    - ``\\n\\n`` (и больше) → один разделитель абзацев ``\\n\\n``
    """
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # убрать BOM / лишние пробелы в конце строк
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # дефис на конце строки + продолжение слова
    prev = None
    while prev != text:
        prev = text
        text = _HYPHEN_BREAK.sub(r"\1\2", text)
    # одиночные переносы → пробел (абзацы \n\n сохраняются)
    text = _SINGLE_NL.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    text = _SPACES.sub(" ", text)
    # пробелы у границ абзаца
    text = re.sub(r" *\n\n *", "\n\n", text)
    return text.strip()


def paragraphs(text: str) -> list[str]:
    """Список абзацев (непустых)."""
    if not text:
        return []
    return [p.strip() for p in text.split("\n\n") if p.strip()]
