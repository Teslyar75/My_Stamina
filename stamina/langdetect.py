"""Определение языка текста без интернета: буквы алфавита + частые слова.

Возвращает ISO-код: ru, uk, be, en, de, fr, es, it, pt, pl, cs, nl, sv … («und», если букв нет).
Точности хватает для книг и абзацев; для фраз из 2–3 слов — примерно.
"""
from __future__ import annotations

import re
from collections import Counter

NAMES = {"ru": "русский", "uk": "украинский", "be": "белорусский", "en": "английский", "de": "немецкий",
         "fr": "французский", "es": "испанский", "it": "итальянский", "pt": "португальский",
         "pl": "польский", "cs": "чешский", "nl": "нидерландский", "sv": "шведский", "und": "?"}

STOP = {
    "en": "the and of to in is that it was for on with as he his be at by i you not this had are but from or have",
    "de": "der die und das ist nicht ich zu den sie es ein mit sich auf dem des eine für auch als war wie im "
          "nach aus bei noch wird hat sind über",
    "fr": "le la les de des et est un une que qui dans pas pour sur il elle au du ne se ce avec",
    "es": "el la los las de y que en un una es por con para no se su al lo como pero más",
    "it": "il lo la gli le di e che un una è per non con si del della sono come ma anche",
    "pt": "o a os as de e que em um uma é para com não se do da no na por mais",
    "pl": "i w na nie się z że do to jest jak ale o co po tak za od jego",
    "cs": "a v se na je že s to z do o jak ale by jsem pro jako",
    "nl": "de het een en van is dat in op te zijn niet met voor die er aan",
    "sv": "och i att det som en på är av för med till den har inte om ett",
    "ru": "и в не на что я с он как это по но к из у же так за от",
    "uk": "і в не на що я з він як це по але до та й від за у так",
    "be": "і ў не на што я з ён як гэта па але да ад за",
}
_STOP = {k: set(v.split()) for k, v in STOP.items()}
_WORD = re.compile(r"[^\W\d_]+", re.U)
CYR = re.compile("[\u0400-\u04FF]")
UK_LETTERS = set("іїєґ")
BE_LETTERS = set("ўі")


def detect(text: str, sample: int = 6000) -> str:
    s = text[:sample].lower()
    words = _WORD.findall(s)
    if not words:
        return "und"
    cyr = sum(1 for w in words if CYR.search(w))
    if cyr > len(words) / 2:
        letters = Counter(ch for w in words for ch in w)
        if letters["ў"] > 0 and letters["ў"] >= letters["ї"]:
            return "be"
        uk = sum(letters[c] for c in UK_LETTERS)
        rus = letters["ы"] + letters["э"] + letters["ъ"] + letters["ё"]
        if uk > rus:
            return "uk"
        if rus or not uk:
            return "ru"
        return "uk"
    cnt = Counter(words)
    scores = {}
    for lang, stops in _STOP.items():
        if lang in ("ru", "uk", "be"):
            continue
        scores[lang] = sum(n for w, n in cnt.items() if w in stops)
    if any(ch in s for ch in "äöüß"):
        scores["de"] = scores.get("de", 0) * 1.3 + 2
    if any(ch in s for ch in "ąęłńśźż"):
        scores["pl"] = scores.get("pl", 0) + 5
    if any(ch in s for ch in "ěřůčš"):
        scores["cs"] = scores.get("cs", 0) + 5
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "en"


def name(code: str) -> str:
    from stamina.i18n import t
    return t(NAMES.get(code, code))


# --- Подготовка текста: немецкие и другие буквы с диакритикой -----------------

UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ẞ": "SS"}


def transliterate_latin(text: str) -> str:
    """ä → ae, ß → ss; прочие буквы с диакритикой (é, ñ, ł …) → без значков. Кириллица не трогается."""
    import unicodedata
    out = []
    for ch in text:
        if ch in UMLAUTS:
            out.append(UMLAUTS[ch])
        elif ch == "ł":
            out.append("l")
        elif ch == "Ł":
            out.append("L")
        elif ord(ch) > 127 and not CYR.match(ch):
            base = unicodedata.normalize("NFKD", ch)
            stripped = "".join(c for c in base if not unicodedata.combining(c))
            out.append(stripped if stripped.isascii() and stripped else ch)
        else:
            out.append(ch)
    return "".join(out)
