"""«Проверить ИИ»: поиск и починка сросшихся слов по частотному словарю.

Модель — языковая статистика (Zipf): частотные словари английского и русского
(``stamina/lexicon/*.txt.gz``, по данным wordfreq, Apache-2.0/CC-BY-SA). Слово,
которого нет ни в словаре, ни среди частых слов самой книги, режем динамикой
на 2–3 известных слова с наименьшей «стоимостью» — как это делают
сегментаторы wordninja/Norvig. Работает без сети и без ключей.

Чинятся: «distastethis» → «distaste this», «nineteenthcentury» → «nineteenth
century», «1984was» → «1984 was», «ивот» → «и вот».
"""
from __future__ import annotations

import gzip
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

LEX_DIR = Path(__file__).with_name("lexicon")
_TOKEN = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_CYR = re.compile(r"[а-яё]")
#: Части короче трёх букв разрешены только из этого списка (иначе «meagre|ness»-подобный мусор).
_SHORT_OK = {
    "en": frozenset("a i an as at be by do go he if in is it me my no of on or so to up us we am".split()),
    "ru": frozenset("а и в о у с к я ж б во во за из на не ни но об от по до же ли бы мы вы он то ко со да".split()),
}
#: Штраф за каждую часть (меньше частей — лучше) и за 1–2-буквенную часть.
_PART_PENALTY = 4.0
_SHORT_PENALTY = 2.5
#: Окончания и приставки: «pillow+ed», «re+edit», «bare+ness» — это одно слово, а не склейка.
_SUFFIXES = {
    "en": ("s", "es", "ed", "d", "ing", "er", "ers", "est", "ly", "ily", "ness", "ful", "fully",
           "less", "ish", "y", "ies", "ied", "ier", "iest", "ment", "able", "ably"),
    "ru": (),
}
_PREFIXES = {"en": ("re", "un", "mis", "in", "dis", "non", "pre", "im", "ir", "il"), "ru": ()}
#: До какого ранга часть считается «надёжным» словом.
_PART_RANK = 60_000


class Fix(NamedTuple):
    token: str
    split: str
    start: int
    end: int


@lru_cache(maxsize=2)
def lexicon(lang: str) -> dict[str, int]:
    """Слово → ранг (0 — самое частое)."""
    path = LEX_DIR / f"{lang}.txt.gz"
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            words = fh.read().split()
    except OSError:
        return {}
    return {w: i for i, w in enumerate(words)}


def _rank_limit(part: str) -> int:
    """Короткой части верим, только если она частая; длинной — и редкой."""
    return 20_000 if len(part) <= 3 else (_PART_RANK if len(part) < 6 else 150_000)


def _cost(rank: int, size: int) -> float:
    return math.log((rank + 1) * math.log(max(size, 3)))


def segment(low: str, lang: str) -> list[str] | None:
    """Лучший разрез слова на 2–3 известных слова или None."""
    lex = lexicon(lang)
    if not lex or low in lex:
        return None
    n, size = len(low), len(lex)
    short = _SHORT_OK.get(lang, frozenset())
    best: list[tuple[float, list[str]] | None] = [None] * (n + 1)
    best[0] = (0.0, [])
    for i in range(1, n + 1):
        for j in range(max(0, i - 24), i):
            if best[j] is None or len(best[j][1]) >= 3:
                continue
            part = low[j:i]
            r = lex.get(part)
            if r is None or r > _rank_limit(part) or (len(part) < 3 and part not in short):
                continue
            c = best[j][0] + _cost(r, size) + _PART_PENALTY + (_SHORT_PENALTY if len(part) < 3 else 0)
            if best[i] is None or c < best[i][0]:
                best[i] = (c, best[j][1] + [part])
    res = best[n]
    if res is None or len(res[1]) < 2:
        return None
    parts = res[1]
    # три части допускаем, только если хоть одна — короткое служебное (иначе часто ломает редкие слова)
    if len(parts) == 3 and not any(p in short for p in parts):
        return None
    return parts


def _lang_of(text: str) -> str:
    sample = text[:20000].lower()
    cyr = len(_CYR.findall(sample))
    lat = sum(1 for ch in sample if "a" <= ch <= "z")
    return "ru" if cyr > lat else "en"


def find(text: str, lang: str | None = None, *, book_trust: int = 3) -> list[Fix]:
    """Сросшиеся слова в тексте. Слово, встреченное в книге ``book_trust`` раз и чаще,
    считаем настоящим (имена, «newspeak», «doublethink»)."""
    lang = lang or _lang_of(text)
    if not lexicon(lang):
        return []
    counts = Counter(m.group(0).lower() for m in _TOKEN.finditer(text))
    cache: dict[str, str | None] = {}
    out: list[Fix] = []
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        low = tok.lower()
        if low not in cache:
            cache[low] = _split_token(low, lang, counts, book_trust)
        sp = cache[low]
        if sp is None:
            continue
        if tok != low:  # сохраняем регистр первой буквы
            sp = sp[:1].upper() + sp[1:] if tok[:1].isupper() else sp
        out.append(Fix(tok, sp, m.start(), m.end()))
    return out


def _split_token(low: str, lang: str, counts: Counter, trust: int) -> str | None:
    if "-" in low or "'" in low or "’" in low:
        return None  # «forty-five», «don't» — не склейки
    # цифры, прилипшие к буквам: «1984was», «chapter1»
    if any(ch.isdigit() for ch in low):
        if low.isdigit():
            return None
        parts = re.findall(r"\d+|[^\W\d_]+", low)
        if re.fullmatch(r"\d+(st|nd|rd|th|s|x|d|k|m|g|kg|km|cm|mm|ml|am|pm)", low):
            return None
        return " ".join(parts) if len(parts) > 1 else None
    if len(low) < 4:
        return None
    lex = lexicon(lang)
    if low in lex or counts.get(low, 0) >= trust:
        return None
    if _is_inflected(low, lang):
        return None
    parts = segment(low, lang)
    if not parts:
        return None
    # половинки должны быть «книжными» или частыми: в книге они встречаются чаще, чем склейка
    if any(counts.get(p, 0) == 0 and lex.get(p, 10**9) > 60_000 for p in parts):
        return None
    return " ".join(parts)


def repair(text: str, lang: str | None = None) -> tuple[str, list[Fix]]:
    """Текст с разделёнными склейками и список правок."""
    fixes = find(text, lang)
    if not fixes:
        return text, []
    pieces, last = [], 0
    for f in fixes:
        pieces.append(text[last:f.start])
        pieces.append(f.split)
        last = f.end
    pieces.append(text[last:])
    return "".join(pieces), fixes


def remap_index(text: str, fixes: list[Fix], index: int) -> int:
    """Позиция курсора в старом тексте → в исправленном (каждая правка добавляет пробелы)."""
    shift = 0
    for f in fixes:
        if f.start >= index:
            break
        if f.end <= index:
            shift += len(f.split) - len(f.token)
        else:  # курсор внутри склейки — ставим на её начало
            return f.start + shift
    return index + shift


def _is_inflected(low: str, lang: str) -> bool:
    """Слово = словарное слово + окончание/приставка («pillowed», «sleepiest», «reedit»)."""
    lex = lexicon(lang)

    def known(stem: str) -> bool:
        return len(stem) >= 3 and stem in lex

    for suf in _SUFFIXES.get(lang, ()):
        if low.endswith(suf) and len(low) > len(suf) + 2:
            stem = low[: -len(suf)]
            if known(stem) or known(stem + "e") or (stem.endswith("i") and known(stem[:-1] + "y")):
                return True
            if len(stem) > 3 and stem[-1] == stem[-2] and known(stem[:-1]):  # dinned, jollying
                return True
            if _is_inflected_once(stem, lang):
                return True
    for pre in _PREFIXES.get(lang, ()):
        if low.startswith(pre) and (known(low[len(pre):]) or _is_inflected_once(low[len(pre):], lang)):
            return True
    return False


def _is_inflected_once(stem: str, lang: str) -> bool:
    lex = lexicon(lang)
    for suf in _SUFFIXES.get(lang, ()):
        if stem.endswith(suf) and len(stem) > len(suf) + 2:
            st = stem[: -len(suf)]
            if st in lex or st + "e" in lex or (st.endswith("i") and st[:-1] + "y" in lex):
                return True
    return False


def join_hyphenated(left: str, right: str, raw: str = "") -> str:
    """Перенос «left-⏎right»: одно слово, слово через дефис или (мягкий перенос) слитно."""
    if "\u00ad" in raw:
        return left + right
    whole = (left + right).lower()
    lang = "ru" if _CYR.search(whole) else "en"
    lex = lexicon(lang)
    if whole in lex:
        return left + right
    if left.lower() in lex and right.lower() in lex:
        return left + "-" + right            # «forty-⏎five» → «forty-five»
    return left + right


class Report(NamedTuple):
    fixes: list[Fix]
    files: list[str]

    @property
    def count(self) -> int:
        return len(self.fixes)

    def examples(self, n: int = 6) -> list[str]:
        seen, out = set(), []
        for f in self.fixes:
            if f.token.lower() not in seen:
                seen.add(f.token.lower())
                out.append(f"{f.token} → {f.split}")
            if len(out) >= n:
                break
        return out


def fix_stored(store, lib=None) -> Report:
    """Кнопка «Проверить ИИ»: починить подготовленную книгу на борту и сохранить поверх.

    Чинит cargo.txt (текст слепой печати), сессию (с пересчётом места курсора)
    и prepared.txt этой книги в библиотеке — чтобы мостик загружал исправленную версию.
    """
    from stamina import library as _library
    from stamina.session_storage import load_session, save_session

    adapted, original = store.load_cargo()
    saved = load_session()
    base = adapted or (saved.text if saved else "")
    if not base.strip():
        return Report([], [])
    new, fixes = repair(base)
    if not fixes:
        return Report([], [])
    files = []
    store.save_cargo(new, original)
    files.append("cargo.txt")
    if saved is not None and saved.text == base:
        saved.index = remap_index(base, fixes, saved.index)
        saved.text = new
        save_session(saved)
        files.append("session.json")
    if lib is not None:
        try:
            tid = lib.find_by_prepared(base)
            if tid:
                path = lib._dir(tid) / "prepared.txt"
                path.write_text(new, encoding="utf-8")
                meta = lib.meta(tid)
                if meta is not None:
                    prep = meta.setdefault("prepared", {})
                    prep["sha256"] = _library.sha(new)
                    prep["words"] = len(new.split())
                    prep["chars"] = len(new)
                    prep["glue_fixed"] = len(fixes)
                    lib.save_meta(meta)
                files.append(f"library/{tid}/prepared.txt")
        except Exception:  # noqa: BLE001 - библиотека необязательна, книга на борту уже исправлена
            pass
    return Report(fixes, files)
