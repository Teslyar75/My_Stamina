"""Адаптация текста для режима тренировки печати.

Каждая функция самостоятельна, чтобы её можно было привязать к отдельной
кнопке в окне редактора. :func:`adapt_for_typing` объединяет всё в один
проход — это «Применить все правки».
"""

from __future__ import annotations

import string


_PUNCTUATION = set(string.punctuation) | {
    "«", "»", "“", "”", "„", "‟", "‹", "›",
    "—", "–", "−", "…", "·", "•",
    "№", "§", "¶", "©", "®", "™",
}


def normalize_spaces(text: str) -> str:
    """Между словами остаётся ровно один пробел; крайние пробелы убираются.

    Любые пробельные символы (табы, переводы строк, неразрывные пробелы)
    схлопываются в один обычный пробел.
    """
    return " ".join(text.split())


def remove_punctuation(text: str) -> str:
    """Удаляет знаки препинания, сохраняя буквы, цифры и пробельные символы."""
    return "".join("" if ch in _PUNCTUATION else ch for ch in text)


def to_lowercase(text: str) -> str:
    """Преобразует все буквы в строчные (работает и для кириллицы)."""
    return text.lower()


def adapt_for_typing(text: str) -> str:
    """Полная адаптация: убираем пунктуацию, нижний регистр, один пробел."""
    return normalize_spaces(to_lowercase(remove_punctuation(text)))


def is_valid_practice_text(text: str) -> bool:
    """Текст пригоден для тренировки, если после адаптации есть символы."""
    return bool(adapt_for_typing(text).strip())
