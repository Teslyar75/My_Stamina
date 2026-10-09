"""Нормализация текста, расстояние Левенштейна, оценка произнесённого предложения (SPEC §3.1)."""
from __future__ import annotations

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


def score_sentence(expected: str, heard: str, target: str | None = None) -> tuple[int, list[tuple[str, bool]]]:
    """Оценка 0–100 по словам и разметка слов образца (слово, засчитано)."""
    exp, got = tokens(expected), tokens(heard)
    if not exp:
        return 0, []
    # выравнивание по словам (DP), слово засчитано при сходстве ≥ 0.8
    forms = word_forms(target) if target else set()

    def same(e: str, g: str) -> bool:
        if e in forms or len(e) <= 3:  # изучаемое слово и короткие слова — только точно
            return e == g or (e in forms and g in forms)
        return similarity(e, g) >= 0.8

    n, m = len(exp), len(got)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            ok = same(exp[i - 1], got[j - 1])
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + (1 if ok else 0))
    matched = [False] * n
    i, j = n, m
    while i > 0 and j > 0:
        if same(exp[i - 1], got[j - 1]) and dp[i][j] == dp[i - 1][j - 1] + 1:
            matched[i - 1] = True
            i, j = i - 1, j - 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    score = round(100 * sum(matched) / n)
    if target:
        has_target = any(t in forms for t in exp)
        if has_target and not any(matched[k] and exp[k] in forms for k in range(n)):
            score = min(score, 59)
    return score, list(zip(exp, matched))


def score_word(target: str, alternatives: list[str], sounds_like: list[str] | None = None) -> int:
    forms = word_forms(target) | {s.lower() for s in (sounds_like or [])}
    best = 0.0
    for alt in alternatives:
        for t in tokens(alt) or [""]:
            if t in forms:
                return 100
            best = max(best, similarity(t, target.lower()))
    return round(100 * best)


def verdict(score: int) -> tuple[str, str]:
    """(текст, ключ цвета)."""
    if score >= 85:
        return "ОТЛИЧНО", "green"
    if score >= 60:
        return "ХОРОШО", "amber"
    return "ЕЩЁ РАЗ", "red"
