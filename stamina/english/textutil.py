"""Нормализация текста, расстояние Левенштейна, оценка произнесённого предложения (SPEC §3.1)."""
from __future__ import annotations

from stamina.i18n import t as _t

import re

CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "can't": "can not", "cannot": "can not",
    "won't": "will not", "wouldn't": "would not", "shouldn't": "should not", "couldn't": "could not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not", "mustn't": "must not",
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are", "he's": "he is",
    "she's": "she is", "it's": "it is", "that's": "that is", "there's": "there is", "what's": "what is",
    "who's": "who is", "let's": "let us", "i've": "i have", "you've": "you have", "we've": "we have",
    "they've": "they have", "i'll": "i will", "you'll": "you will", "he'll": "he will", "she'll": "she will",
    "we'll": "we will", "they'll": "they will", "it'll": "it will", "i'd": "i would", "you'd": "you would",
    "he'd": "he would", "she'd": "she would", "we'd": "we would", "they'd": "they would",
}
NUMBERS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
           "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
           "nineteen", "twenty"]


def tokens(text: str) -> list[str]:
    t = text.lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    out: list[str] = []
    for w in t.split():
        w = w.strip("'")
        if not w:
            continue
        if w in CONTRACTIONS:
            out.extend(CONTRACTIONS[w].split())
        elif w.endswith("'s"):
            out.append(w[:-2])
        elif w.isdigit() and int(w) <= 20:
            out.append(NUMBERS[int(w)])
        else:
            out.append(w)
    return out


def lev(a, b) -> int:
    """Расстояние Левенштейна для строк или списков."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - lev(a, b) / max(len(a), len(b))


def word_forms(word: str) -> set[str]:
    """Грубые словоформы английского слова (для засчёта изучаемого слова)."""
    w = word.lower()
    forms = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing", w + "er", w + "ly"}
    if w.endswith("y") and len(w) > 2:
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    if w.endswith("e"):
        forms |= {w[:-1] + "ing"}
    if len(w) >= 3 and w[-1] not in "aeiouwxy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        forms |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    forms |= IRREGULAR.get(w, set())
    return forms


_IRR = """be am is are was were been being; have has had having; do does did done doing; go goes went gone going;
say said; make made; get got gotten; know knew known; think thought; take took taken; see saw seen; come came;
give gave given; find found; tell told; become became; leave left; feel felt; bring brought; begin began begun;
keep kept; hold held; write wrote written; stand stood; hear heard; let; mean meant; set; meet met; run ran;
pay paid; sit sat; speak spoke spoken; lie lay lain; lead led; read; grow grew grown; lose lost; fall fell fallen;
send sent; build built; understand understood; draw drew drawn; break broke broken; spend spent; cut; rise rose risen;
drive drove driven; buy bought; wear wore worn; choose chose chosen; seek sought; throw threw thrown; catch caught;
deal dealt; win won; forget forgot forgotten; sell sold; fight fought; teach taught; eat ate eaten; sing sang sung;
drink drank drunk; fly flew flown; sleep slept; swim swam swum; light lit; hit; put; child children; man men;
woman women; person people; foot feet; tooth teeth; mouse mice; good better best; bad worse worst"""
IRREGULAR: dict[str, set[str]] = {}
for _grp in _IRR.replace("\n", " ").split(";"):
    _ws = _grp.split()
    if _ws:
        IRREGULAR.setdefault(_ws[0], set()).update(_ws)


STRICTNESS_LEVELS = ("soft", "normal", "strict")


def strictness_level(value: str | None) -> str:
    """Нормализует настройку строгости; неизвестное значение — обычная проверка."""
    return value if value in STRICTNESS_LEVELS else "normal"


# --- фонетический слой -------------------------------------------------------
# Vosk часто слышит не слово, а его звучание: tea → t, a new → and you.
# Здесь сравниваем не буквы, а грубый фонетический ключ. Он не заменяет смысл:
# предложение всё равно должно содержать звучание изучаемого слова.
_VOWEL_GROUPS = (
    ("ew", "U"), ("oo", "U"), ("ou", "U"), ("ow", "O"),
    ("ay", "E"), ("ai", "E"), ("ea", "E"), ("ee", "E"),
    ("ie", "E"), ("oa", "O"), ("oi", "O"), ("oy", "O"),
)
_CONSONANT_GROUPS = (
    ("tch", "C"), ("ch", "C"), ("sh", "X"), ("ph", "F"),
    ("th", "0"), ("wh", "W"), ("ck", "K"), ("qu", "KW"), ("x", "KS"),
)
_SOUNDEX = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3", "l": "4", "m": "5", "n": "5", "r": "6",
}


def _soundex(word: str) -> str:
    """Soundex: tea и t дают T000, coffee — C100 (разные звуки)."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return ""
    first = w[0].upper()
    prev = _SOUNDEX.get(first, "")
    out: list[str] = []
    for ch in w[1:]:
        code = _SOUNDEX.get(ch, "")
        if code:
            if code != prev and len(out) < 3:
                out.append(code)
            prev = code
        elif ch not in "hw":  # гласные разделяют одинаковые согласные, h/w — нет
            prev = ""
    return (first + "".join(out) + "000")[:4]


def phone_key(text: str) -> str:
    """Грубый фонетический ключ фразы: tea→T, t→T, a new→ANU, and you→ANTIU."""
    s = text.lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z]", "", s)
    for a, b in _VOWEL_GROUPS:
        s = s.replace(a, b)
    for a, b in _CONSONANT_GROUPS:
        s = s.replace(a, b)
    out: list[str] = []
    for i, c in enumerate(s):
        if c in "aeiou":
            if not out or out[-1] not in "AEIOU":
                out.append(c.upper())
        elif c == "y":
            out.append("J" if i == 0 or (i > 0 and s[i - 1] in "aeiou") else "I")
        elif c == "c":
            out.append("S" if i + 1 < len(s) and s[i + 1] in "eiy" else "K")
        elif c == "g":
            out.append("J" if i + 1 < len(s) and s[i + 1] in "eiy" else "G")
        elif c in "bp":
            out.append("B")
        elif c == "f":
            out.append("F")
        elif c == "v":
            out.append("V")
        elif c in "dt":
            out.append("T")
        elif c in "kq":
            out.append("K")
        elif c in "sz":
            out.append("S")
        elif c == "m":
            out.append("M")
        elif c == "n":
            out.append("N")
        elif c == "l":
            out.append("L")
        elif c == "r":
            out.append("R")
        elif c == "j":
            out.append("J")
        elif c == "w":
            out.append("W")
        elif c == "h":
            pass
        else:
            out.append(c.upper())
    if len(out) > 1 and out[-1] == "E":  # немое конечное e: tea→T
        out.pop()
    clean: list[str] = []
    for p in out:
        if not clean or clean[-1] != p:
            clean.append(p)
    return "".join(clean)


def _phone_sim(a: str, b: str) -> float:
    return similarity(phone_key(a), phone_key(b))


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def _match_kind(e: str, g: str, forms: set[str], level: str) -> int:
    """2 — точное слово/форма, 1 — фонетически похоже, 0 — не засчитано."""
    if e == g or (e in forms and g in forms):
        return 2
    if level == "strict":
        return 0
    # Изучаемое слово: к нему мягче — это опора карточки.
    if e in forms:
        if len(e) >= 3 and _phone_sim(e, g) >= (0.52 if level == "soft" else 0.60):
            return 1
        if len(e) >= 3 and g and e.startswith(g):
            return 1
        if level == "soft" and len(e) >= 2 and similarity(e, g) >= 0.66:
            return 1
        return 0
    if len(e) <= 2 or len(g) <= 2:  # короткие служебные слова — только точно
        return 0
    if similarity(e, g) >= (0.70 if level == "soft" else 0.80):
        return 1
    if len(e) >= 3 and len(g) >= 3 and _soundex(e) == _soundex(g):
        return 1
    if _phone_sim(e, g) >= (0.62 if level == "soft" else 0.72):
        return 1
    return 0


def score_sentence(expected: str, heard: str, target: str | None = None,
                   strictness: str | None = "normal") -> tuple[int, list[tuple[str, bool]]]:
    """Оценка 0–100 по словам и разметка слов образца (слово, засчитано).

    ``strictness``: soft — больше вариантов распознавания, normal — разумный
    баланс, strict — только точные слова. Смысл защищён отдельно: без звучания
    изучаемого слова предложение не может получить больше 59.
    """
    exp, got = tokens(expected), tokens(heard)
    if not exp:
        return 0, []
    level = strictness_level(strictness)
    target = (target or "").lower()
    forms = word_forms(target) if target else set()

    n, m = len(exp), len(got)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            kind = _match_kind(exp[i - 1], got[j - 1], forms, level)
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + (1 if kind else 0))
    matched = [False] * n
    heard_for: list[str] = [""] * n
    i, j = n, m
    while i > 0 and j > 0:
        kind = _match_kind(exp[i - 1], got[j - 1], forms, level)
        if kind and dp[i][j] == dp[i - 1][j - 1] + 1:
            matched[i - 1] = True
            heard_for[i - 1] = got[j - 1]
            i, j = i - 1, j - 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    score = round(100 * sum(matched) / n)

    has_target = bool(target) and any(e in forms for e in exp)
    target_exact = any(matched[k] and exp[k] in forms and heard_for[k] in forms
                       for k in range(n))
    # Слово могло быть узнано по звучанию, но не точной формой (tea → t).
    target_phonetic = any(matched[k] and exp[k] in forms and heard_for[k] not in forms
                          for k in range(n))
    target_ok = target_exact or target_phonetic
    target_phone = phone_key(target)
    if has_target and not target_ok and len(target_phone) >= 2:
        # Звучание слова могло слиться с соседними: a new → and you.
        target_ok = _is_subsequence(target_phone, phone_key(heard))
    if has_target and target_ok:
        # Для разметки: слово узнано, даже если ASR слил его с соседним.
        for k, e in enumerate(exp):
            if e in forms:
                matched[k] = True

    if has_target:
        if not target_ok:
            score = min(score, 59)  # другое слово/смысл — не засчитываем
        elif not target_exact:
            # Не 100: слово узнано по звучанию, а не точной формой.
            score = min(score, 88 if level == "normal" else 92 if level == "soft" else 80)

    whole = _phone_sim(expected, heard)
    if level != "strict":
        if has_target:
            rescue = 0.70 if level == "normal" else 0.62
            floor = 84 if level == "normal" else 88
            if target_ok and whole >= rescue:
                score = max(score, floor)
        else:
            rescue = 0.86 if level == "normal" else 0.78
            floor = 84 if level == "normal" else 88
            if whole >= rescue:
                score = max(score, floor)
    return score, list(zip(exp, matched))


def score_word(target: str, alternatives: list[str], sounds_like: list[str] | None = None,
               strictness: str | None = "normal") -> int:
    """Оценка слова; при soft/normal допускает фонетические варианты распознавания."""
    level = strictness_level(strictness)
    target_l = target.lower().strip()
    forms = word_forms(target_l) | {s.lower() for s in (sounds_like or [])}
    best = 0
    for alt in alternatives:
        for t in tokens(alt) or [""]:
            if t in forms:
                return 100
            score = round(100 * similarity(t, target_l))
            if level == "strict":
                # Строгий режим: только точная форма; длинное слово — почти точное.
                if len(target_l) >= 5 and similarity(t, target_l) >= 0.90:
                    score = max(score, 80)
            elif len(target_l) >= 3:
                if _soundex(t) == _soundex(target_l):
                    score = max(score, 86 if level == "normal" else 90)
                ps = _phone_sim(t, target_l)
                if ps >= (0.55 if level == "soft" else 0.60):
                    score = max(score, min(88 if level == "normal" else 92,
                                           round(60 + 40 * ps)))
                if t and target_l.startswith(t):  # tea → t (ASR потерял гласную)
                    score = max(score, 82 if level == "normal" else 86)
            best = max(best, score)
    return best


def verdict(score: int) -> tuple[str, str]:
    """(текст, ключ цвета)."""
    if score >= 85:
        return _t("ОТЛИЧНО"), "green"
    if score >= 60:
        return _t("ХОРОШО"), "amber"
    return _t("ЕЩЁ РАЗ"), "red"
