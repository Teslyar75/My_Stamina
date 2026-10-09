"""Адаптация текста для режима тренировки печати.

Каждая функция самостоятельна, чтобы её можно было привязать к отдельной
кнопке в окне редактора. :func:`adapt_for_typing` объединяет всё в один
проход — это «Применить все правки».
"""

from __future__ import annotations

import re
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


_UK_APOS = re.compile(r"(?<=[А-Яа-яЁёІіЇїЄєҐґ])['’ʼ](?=[А-Яа-яЁёІіЇїЄєҐґ])")


def remove_punctuation(text: str) -> str:
    """Удаляет знаки препинания, сохраняя буквы, цифры и пробельные символы.

    Апостроф внутри украинского слова (м'ясо, сім'я) — часть слова: остаётся как «'»."""
    text = _UK_APOS.sub("\x01", text)
    out = "".join("" if ch in _PUNCTUATION else ch for ch in text)
    return out.replace("\x01", "'")


def to_lowercase(text: str) -> str:
    """Преобразует все буквы в строчные (работает и для кириллицы)."""
    return text.lower()


def adapt_for_typing(text: str) -> str:
    """Полная адаптация: убираем пунктуацию, нижний регистр, один пробел."""
    return normalize_spaces(to_lowercase(remove_punctuation(text)))


def is_valid_practice_text(text: str) -> bool:
    """Текст пригоден для тренировки, если после адаптации есть символы."""
    return bool(adapt_for_typing(text).strip())


_TYPOGRAPHY = {
    "«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "‹": "'", "›": "'",
    "—": "-", "–": "-", "−": "-", "…": "...", "\u00a0": " ", "\u202f": " ",
}


def normalize_typography(text: str) -> str:
    """Типографские символы, которых нет на клавиатуре, → обычные (« » → ", — → -).

    Переводы строк и табуляции становятся пробелами: строка набора одна.
    """
    out = "".join(_TYPOGRAPHY.get(ch, ch) for ch in text)
    return "".join(" " if ch in "\r\n\t\v\f" else ch for ch in out)


def process_text(text: str, *, lower: bool = True, punct: bool = True,
                 spaces: bool = True, translit: bool = False, yo: bool = False) -> str:
    """Подготовка текста по выбранным опциям.

    * ``lower``  — убрать заглавные буквы;
    * ``punct``  — убрать знаки препинания;
    * ``spaces`` — один пробел между словами.

    * ``yo``       — «ё» → «е» (многие печатают без ё);
    * ``translit`` — немецкие ä ö ü ß → ae oe ue ss, прочие é ñ ł … → без значков (если нет
      немецкой раскладки); по умолчанию буквы остаются как в книге.

    Со всеми тремя опциями результат в точности равен :func:`adapt_for_typing`.
    """
    if yo:
        text = text.replace("ё", "е").replace("Ё", "Е")
    if translit:
        from stamina.langdetect import transliterate_latin
        text = transliterate_latin(text)
    if lower and punct and spaces:
        return adapt_for_typing(text)
    if punct:
        text = remove_punctuation(text)
    text = normalize_typography(text)
    if lower:
        text = to_lowercase(text)
    if spaces:
        return normalize_spaces(text)
    return text.strip()
