"""Адаптация текста для режима тренировки печати.

Каждая функция самостоятельна, чтобы её можно было привязать к отдельной
кнопке в окне редактора. :func:`adapt_for_typing` объединяет всё в один
проход — это «Применить все правки».

Главное правило удаления знаков: **знак между словами превращается в пробел,
а не исчезает в никуда.** Иначе слова срастаются: «слово—слово» → «словослово»,
«как/то» → «както». При этом то, что внутри слова является частью слова,
сохраняется: дефис и апостроф («что-то», «don't», «м'ясо»), точка и запятая
внутри числа («1.5», «1,5», «1990-1995»).

Сращивания, пришедшие из самого текста (в книге слова уже слиты), ищет
:func:`find_glued_words` и чинит :func:`repair_glued_words` — только там,
где уверенность высокая: «ивот» → «и вот», «непонял» → «не понял».
"""

from __future__ import annotations

import re
import string
from typing import NamedTuple


_PUNCTUATION = set(string.punctuation) | {
    "«", "»", "“", "”", "„", "‟", "‹", "›",
    "—", "–", "−", "…", "·", "•",
    "№", "§", "¶", "©", "®", "™",
}

#: Знаки, которые внутри слова — часть слова, а не разделитель.
_INNER_KEEP = {"'", "\u2019", "\u02bc", "\u2010", "\u2011", "-"}

#: Знаки внутри числа: «1.5», «1,5», «1990-1995», «1/2».
_NUMBER_SEP = {".", ",", "-", "/", ":", "\u2013", "\u2014"}

#: Буква или цифра (знак подчёркивания сюда не входит).
_WORDISH = re.compile(r"[^\W_]", re.UNICODE)

#: Слово из одних букв — для поиска сращиваний.
_LETTERS_ONLY = re.compile(r"[^\W\d_]+", re.UNICODE)


def normalize_spaces(text: str) -> str:
    """Между словами остаётся ровно один пробел; крайние пробелы убираются.

    Любые пробельные символы (табы, переводы строк, неразрывные пробелы)
    схлопываются в один обычный пробел.
    """
    return " ".join(text.split())


def remove_punctuation(text: str) -> str:
    """Убирает знаки препинания, не сращивая слова.

    Знак между двумя буквами или цифрами становится пробелом (так слова
    остаются раздельными), знак рядом с пробелом или на краю строки просто
    убирается. Дефис и апостроф внутри слова сохраняются, как и разделитель
    внутри числа.
    """
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch not in _PUNCTUATION:
            out.append(ch)
            continue
        prev = out[-1] if out else ""
        nxt = text[i + 1] if i + 1 < n else ""
        if ch in _INNER_KEEP and prev and _WORDISH.match(prev) and nxt and _WORDISH.match(nxt):
            out.append(ch)
            continue
        if ch in _NUMBER_SEP and prev.isdigit() and nxt.isdigit():
            out.append(ch)
            continue
        if prev and nxt and _WORDISH.match(prev) and _WORDISH.match(nxt):
            out.append(" ")
            continue
    return "".join(out)


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


# ===========================================================================
# Поиск и починка сращиваний слов («ивот», «непонял», «thebook»)
# ===========================================================================

class GluedWord(NamedTuple):
    """Найденное сращивание: слово, его границы и предложенное разделение."""

    token: str
    start: int
    end: int
    split: str
    confident: bool


#: Частые служебные и короткие слова: ими обычно и «прилипает» соседнее слово.
_RU_SHORT = frozenset("""
и а в во не ни но на по за из от до то же бы ли мы вы он она они оно
это этот эта эти что как так там тут уже ещё еще весь вся всё все
у о об обо с со к ко при для без под над про через между перед
если когда где чем тем кого чего кому чему нет да или либо тоже
""".split())

#: Очень частые короткие слова, которые могут стоять вплотную («ивот», «ивсё»).
#: Только они разрешены после однобуквенного слова — иначе «узнал» → «у знал».
_SHORT_TARGETS = frozenset({"вот", "все", "всё"})

#: Частые русские слова (от 4 букв), которые могут стоять после прилипшего слова.
_RU_COMMON = frozenset("""
вот понял поняла поняли знаю знаешь знает знал знала знали помню помнишь
думал думаю думаешь сказал сказала сказали говорит говорю говорят
понимаю понимаешь понимает понимал понимала понимали понимать
сделал сделала сделали вижу видишь видел видела видели слышал слышала
хочу хочешь хочет хотел хотела могу может можем можно надо нужно
пришли пошли ушли вошли вышли здесь сейчас потом очень просто всегда
никогда конечно нельзя сказать говорить спросить ответить
дай давай живой новый старый большой маленький хороший плохой
первый последний другой каждый самый опять снова назад вперёд
домой дома год года годы раз время человек человека люди людей
слово слова жизнь жизни мир мира свет света рука руки руку
глаза глаз голос голоса ночь ночи утро вечер вода огонь земля
город страна народ бог бога богу царь царя храм храма
книга книги книгу письмо письма путь пути дорога дороге конец конца
начало начал часть части друг жена жену сын сына дочь
отец отца мать матери брат брата сестра сестры
один одна одно два три пять сто тысяча
него неё нее тебе
""".split())

#: Слова, которые нельзя разделять: они сами выглядят как «прилипшее к служебному».
_RU_SAFE = frozenset("""
погода погоды погоде погоду погодой
подруг подруга подруги подругу подруге подругам
узнал узнала узнали узнаю узнаешь узнает узнаёт
познал познаю познаешь познает познаёт сознаю сознает сознаёт
признал признала признали признаю признаешь признает признаёт
задумал задумаю придумал придумала придумали придумаю выдумал
подумал подумала подумали подумаю подумаешь
захотел захочу захочешь захочет захотим захотят
помогу поможешь поможет поможем помогут
подсказал подсказала подскажи
загород загородом заутро поруки зараз заразу
""".split())

#: Частые английские служебные слова.
_EN_SHORT = frozenset("""
the of to in is it and or for that this you we he she at on by a an as be do
so no if up out my his her its us them they was were are not but with from have
has had will can all one two did does who what when where how why there their
then than some any our your
""".split())

#: Английские слова-содержание (от 4 букв) — то, что может стоять после служебного.
_EN_COMMON = frozenset("""
time world woman women people night life light water word words house home
year years hand hands eyes eye voice book books city land lord god king temple
road way beginning part thing things place heart mind name father mother son
""".split())

#: Английские слова без пробела, которые сами выглядят как слияние.
_EN_SAFE = frozenset("""
another nothing sometime sometimes anytime tonight
within without upon into onto also
""".split())

_VOWELS = set("аеёиоуыэюяaeiouy")


def _has_vowel(word: str) -> bool:
    return any(ch in _VOWELS for ch in word.lower())


def _dict_split(low: str, known) -> tuple[str, str] | None:
    """Разрез, где обе половины — слова книги: «nineteenth» + «century».

    Именно этого не хватало: старые правила искали разрез только после короткого
    служебного слова (не длиннее четырёх букв), поэтому «nineteenthcentury» для
    них не существовало. Берём самый ровный из подходящих разрезов.
    """
    if not known:
        return None
    best: tuple[str, str] | None = None
    for i in range(3, len(low) - 2):
        left, right = low[:i], low[i:]
        if left in known and right in known:
            if best is None or min(len(left), len(right)) > min(len(best[0]), len(best[1])):
                best = (left, right)
    return best


def _best_split(low: str, known=frozenset(), counts=None,
                own: int | None = None) -> tuple[str, str, bool] | None:
    """Где разделить слипшееся слово. → (левая часть, правая часть, уверенно).

    ``counts`` — счётчики слов книги (слово → сколько раз). Склейку узнаём по ним:
    её половинки встречаются чаще, чем она сама.
    """
    if low in _RU_SAFE or low in _EN_SAFE:
        return None
    by_dict = _dict_split(low, known)          # обе половины — слова книги: верим
    if by_dict is not None:
        left, right = by_dict
        if counts is None or own is None or own < min(counts.get(left, 0), counts.get(right, 0)):
            return left, right, True
    fallback: tuple[str, str, bool] | None = None
    for i in range(1, min(4, len(low) - 3) + 1):
        prefix, rest = low[:i], low[i:]
        if prefix not in _RU_SHORT and prefix not in _EN_SHORT:
            continue
        if rest in _SHORT_TARGETS:
            return prefix, rest, True
        if len(prefix) < 2 or len(rest) < 4 or not _has_vowel(rest):
            continue
        if rest in _RU_COMMON or rest in _EN_COMMON:
            return prefix, rest, True
        if fallback is None and len(low) >= 8:
            fallback = (prefix, rest, False)
    return fallback


def _counts_of(known_words) -> dict | None:
    """Счётчики слов книги (или None, если передан просто набор слов)."""
    if not hasattr(known_words, "items"):
        return None
    return {str(w).lower(): int(c) for w, c in known_words.items() if str(w).strip()}


def _known_words(known_words, trust: int | None = None) -> frozenset:
    """Словарь книги → множество доверенных слов.

    Со счётчиками: в большой книге верим слову, встреченному дважды; в коротком
    тексте статистики нет — верим любому слову словаря.
    """
    if not known_words:
        return frozenset()
    if hasattr(known_words, "items"):
        counts = _counts_of(known_words) or {}
        need = (2 if len(counts) >= 40 else 1) if trust is None else max(1, int(trust))
        return frozenset(w for w, c in counts.items() if c >= need)
    return frozenset(str(w).lower() for w in known_words)


def book_words(text: str, limit: int = 200_000) -> dict:
    """Словарь самой книги: слово → сколько раз встретилось.

    Нужен, чтобы отличать настоящие слова от склеек: «nineteenth» и «century»
    встречаются много раз, а «nineteenthcentury» — один. Считаем по первым
    ``limit`` знакам: для частот этого хватает, а превью в редакторе не тормозит.
    """
    from stamina.suggest import dictionary_from
    return dict(dictionary_from([text[:limit]]).words)


def find_glued_words(text: str, *, known_words=None, confident_only: bool = False,
                     max_report: int = 100, min_len: int = 7,
                     trust: int | None = None) -> list[GluedWord]:
    """Ищет слова, слипшиеся без пробела.

    * ``known_words``   — словарь известных слов: если слово в нём, оно не проверяется;
                          можно передать счётчики (см. :func:`book_words`), тогда слово,
                          встреченное в книге дважды и чаще, считается настоящим;
    * ``confident_only``— вернуть только уверенные находки (их можно чинить молча);
    * ``min_len``       — с какой длины проверять неуверенные находки (уверенные — с 4 букв);
    * ``trust``         — сколько раз слово должно встретиться, чтобы ему верить.
    """
    known = _known_words(known_words, trust)
    counts = _counts_of(known_words)
    found: list[GluedWord] = []
    for m in _LETTERS_ONLY.finditer(text):
        token = m.group(0)
        low = token.lower()
        if len(low) < 4:
            continue
        own = counts.get(low, 0) if counts is not None else 0
        if counts is not None:
            if own >= 2:              # встретилось дважды — это настоящее слово
                continue
        elif low in known:
            continue
        cand = _best_split(low, known, counts, own if counts is not None else None)
        if cand is None:
            continue
        prefix, rest, confident = cand
        if confident_only and not confident:
            continue
        if not confident and len(low) < min_len:
            continue
        found.append(GluedWord(token, m.start(), m.end(), f"{prefix} {rest}", confident))
        if len(found) >= max_report:
            break
    return found


def repair_glued_words(text: str, *, known_words=None, max_fix: int = 500) -> str:
    """Разделяет пробелом только уверенные сращивания, остальное оставляет как есть."""
    pieces: list[str] = []
    last = 0
    for g in find_glued_words(text, known_words=known_words, confident_only=True, max_report=max_fix):
        pieces.append(text[last:g.start])
        pieces.append(g.split)
        last = g.end
    pieces.append(text[last:])
    return "".join(pieces)


def process_text(text: str, *, lower: bool = True, punct: bool = True,
                 spaces: bool = True, translit: bool = False, yo: bool = False,
                 glue: bool = False) -> str:
    """Подготовка текста по выбранным опциям.

    * ``lower``  — убрать заглавные буквы;
    * ``punct``  — убрать знаки препинания (знак между словами становится пробелом);
    * ``spaces`` — один пробел между словами;
    * ``glue``   — разделять сращивания слов, пришедшие из самого текста («ивот» → «и вот»).

    * ``yo``       — «ё» → «е» (многие печатают без ё);
    * ``translit`` — немецкие ä ö ü ß → ae oe ue ss, прочие é ñ ł … → без значков (если нет
      немецкой раскладки); по умолчанию буквы остаются как в книге.

    С тремя первыми опциями и без ``glue`` результат в точности равен
    :func:`adapt_for_typing`.
    """
    if yo:
        text = text.replace("ё", "е").replace("Ё", "Е")
    if translit:
        from stamina.langdetect import transliterate_latin
        text = transliterate_latin(text)
    if lower and punct and spaces and not glue:
        return adapt_for_typing(text)
    if punct:
        text = remove_punctuation(text)
    text = normalize_typography(text)
    if lower:
        text = to_lowercase(text)
    if spaces:
        text = normalize_spaces(text)
    if glue:
        # Словарь берём из самого текста: склейка — редкое слово, её половины — частые.
        text = normalize_spaces(repair_glued_words(text, known_words=book_words(text)))
    return text.strip()
