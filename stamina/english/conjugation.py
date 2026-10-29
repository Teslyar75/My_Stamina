"""Генератор спряжения английского глагола: 12 времён × 5 лиц × 3 формы.

Чистые функции без UI. Таблицы не хранятся, а строятся на лету из трёх форм
(V1, V2, V3). Для неправильных глаголов V2/V3 передаются явно (из пака
`data/verbs/irregular.json`), для правильных выводятся по правилам орфографии.
"""
from __future__ import annotations

import re

TENSES = [
    ("present_simple", "Present Simple", "Настоящее простое"),
    ("present_continuous", "Present Continuous", "Настоящее длительное"),
    ("present_perfect", "Present Perfect", "Настоящее совершенное"),
    ("present_perfect_continuous", "Present Perfect Continuous", "Настоящее совершенное длительное"),
    ("past_simple", "Past Simple", "Прошедшее простое"),
    ("past_continuous", "Past Continuous", "Прошедшее длительное"),
    ("past_perfect", "Past Perfect", "Прошедшее совершенное"),
    ("past_perfect_continuous", "Past Perfect Continuous", "Прошедшее совершенное длительное"),
    ("future_simple", "Future Simple", "Будущее простое"),
    ("future_continuous", "Future Continuous", "Будущее длительное"),
    ("future_perfect", "Future Perfect", "Будущее совершенное"),
    ("future_perfect_continuous", "Future Perfect Continuous", "Будущее совершенное длительное"),
]
TENSE_KEYS = [t[0] for t in TENSES]

# (ключ, местоимение в предложении, подпись в таблице)
PERSONS = [
    ("I", "I", "I"),
    ("you", "you", "you"),
    ("he", "he", "he / she / it"),
    ("we", "we", "we"),
    ("they", "they", "they"),
]
PERSON_KEYS = [p[0] for p in PERSONS]
MODES = ("affirmative", "negative", "question")

VOWELS = "aeiou"

# Многосложные глаголы с ударением на последнем слоге: конечная согласная удваивается
# (begin → beginning, prefer → preferred). Остальные многосложные не удваивают
# (visit → visiting, open → opening, listen → listened).
STRESSED_FINAL = frozenset("""
admit allot abet acquit appal annul begin befit beget commit compel concur confer control
corral defer deter distil dispel embed enrol equip excel expel extol forget forbid format
gossip handicap incur infer instil kidnap occur omit outbid outrun overlap patrol permit
prefer propel rebel recur refer regret remit repel retrofit submit transfer transmit unpin
unzip upset worship
""".split())
# Удвоение не нужно, хотя слово выглядит как CVC (односложные на -w/-x/-y уже исключены).
NO_DOUBLE = frozenset("""
fix mix box tax wax sew row bow vex
""".split())
# Глаголы на -c: добавляем k (panic → panicking, panicked).
C_TO_CK = frozenset("panic picnic mimic traffic frolic bivouac".split())
# Исключения для -ing
ING_EXCEPTIONS = {
    "be": "being", "see": "seeing", "flee": "fleeing", "agree": "agreeing", "free": "freeing",
    "dye": "dyeing", "eye": "eyeing", "hoe": "hoeing", "toe": "toeing", "canoe": "canoeing",
    "shoe": "shoeing", "singe": "singeing", "age": "ageing", "queue": "queuing",
    "die": "dying", "lie": "lying", "tie": "tying", "vie": "vying",
}


def _syllables(word: str) -> int:
    w = word.lower()
    w = re.sub(r"qu", "q", w)
    if w.endswith("e") and not w.endswith(("ee", "le")) and len(w) > 2:
        w = w[:-1]
    return max(1, len(re.findall(r"[aeiouy]+", w)))


def _is_cvc(word: str) -> bool:
    """Оканчивается на согласная-гласная-согласная (одна гласная перед последней буквой)."""
    w = re.sub(r"qu", "q", word.lower())
    if len(w) < 3:
        return False
    c1, v, c2 = w[-3], w[-2], w[-1]
    return c2 not in VOWELS + "wxy" and v in VOWELS and c1 not in VOWELS


def doubles_final(word: str) -> bool:
    """Нужно ли удваивать конечную согласную перед -ing/-ed."""
    w = word.lower()
    if w in NO_DOUBLE or not _is_cvc(w):
        return False
    if _syllables(w) == 1:
        return True
    if w in STRESSED_FINAL:
        return True
    # приставочные: overrun, outrun, upset — по последнему компоненту
    for pref in ("over", "under", "out", "re", "up", "mis", "be", "for", "with"):
        if w.startswith(pref) and len(w) - len(pref) >= 3 and _syllables(w[len(pref):]) == 1 \
                and _is_cvc(w[len(pref):]) and w[len(pref):] not in NO_DOUBLE:
            return True
    return False


def ing_form(base: str) -> str:
    b = base.lower().strip()
    if b in ING_EXCEPTIONS:
        return ING_EXCEPTIONS[b]
    if b in C_TO_CK:
        return b + "king"
    if b.endswith("ie"):
        return b[:-2] + "ying"
    if b.endswith("e") and not b.endswith(("ee", "oe", "ye")) and len(b) > 2:
        return b[:-1] + "ing"
    if doubles_final(b):
        return b + b[-1] + "ing"
    return b + "ing"


get_ing = ing_form  # совместимость с черновиком


def regular_past(base: str) -> str:
    b = base.lower().strip()
    if b in C_TO_CK:
        return b + "ked"
    if b.endswith("e"):
        return b + "d"
    if len(b) > 1 and b.endswith("y") and b[-2] not in VOWELS:
        return b[:-1] + "ied"
    if doubles_final(b):
        return b + b[-1] + "ed"
    return b + "ed"


def third_person(base: str) -> str:
    b = base.lower().strip()
    special = {"be": "is", "have": "has", "do": "does", "go": "goes"}
    if b in special:
        return special[b]
    if len(b) > 1 and b.endswith("y") and b[-2] not in VOWELS:
        return b[:-1] + "ies"
    if b.endswith(("s", "x", "z", "ch", "sh", "o")):
        return b + "es"
    return b + "s"


def forms(base: str, v2: str | None = None, v3: str | None = None) -> dict:
    """Пять форм глагола. V2/V3 по умолчанию правильные."""
    b = base.lower().strip()
    if b == "be":
        return {"v1": "be", "s": "is", "v2": "was/were", "v3": "been", "ing": "being"}
    return {"v1": b, "s": third_person(b), "v2": v2 or regular_past(b), "v3": v3 or regular_past(b),
            "ing": ing_form(b)}


def is_irregular(base: str, v2: str, v3: str) -> bool:
    rp = regular_past(base)
    return v2.split("/")[0] != rp or v3.split("/")[0] != rp


def _first(form: str) -> str:
    """Из вариантов «learned/learnt» берём первый."""
    return form.split("/")[0].strip()


def _be_present(person: str) -> str:
    return {"I": "am", "he": "is"}.get(person, "are")


def _be_past(person: str) -> str:
    return "was" if person in ("I", "he") else "were"


def _subj(person: str) -> str:
    return dict((p[0], p[1]) for p in PERSONS)[person]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def conjugate(base: str, tense: str, person: str, mode: str = "affirmative",
              v2: str | None = None, v3: str | None = None) -> str:
    """Одна ячейка таблицы, например: conjugate('go','past_simple','he','question') → 'Did he go?'"""
    if tense not in TENSE_KEYS:
        raise ValueError(f"unknown tense: {tense}")
    if person not in PERSON_KEYS:
        raise ValueError(f"unknown person: {person}")
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    f = forms(base, v2, v3)
    b, ing, pp = f["v1"], f["ing"], _first(f["v3"])
    past = _first(f["v2"])
    subj = _subj(person)
    he = person == "he"
    have = "has" if he else "have"

    # [вспомогательный, остаток] — для отрицания/вопроса ставим not / меняем порядок
    if tense == "present_simple":
        if b == "be":
            aux, rest = _be_present(person), ""
        else:
            if mode == "affirmative":
                return f"{subj} {f['s'] if he else b}"
            aux, rest = ("does" if he else "do"), b
    elif tense == "past_simple":
        if b == "be":
            aux, rest = _be_past(person), ""
        else:
            if mode == "affirmative":
                return f"{subj} {past}"
            aux, rest = "did", b
    elif tense == "present_continuous":
        aux, rest = _be_present(person), ing
    elif tense == "past_continuous":
        aux, rest = _be_past(person), ing
    elif tense == "present_perfect":
        aux, rest = have, pp
    elif tense == "past_perfect":
        aux, rest = "had", pp
    elif tense == "present_perfect_continuous":
        aux, rest = have, f"been {ing}"
    elif tense == "past_perfect_continuous":
        aux, rest = "had", f"been {ing}"
    elif tense == "future_simple":
        aux, rest = "will", b
    elif tense == "future_continuous":
        aux, rest = "will", f"be {ing}"
    elif tense == "future_perfect":
        aux, rest = "will", f"have {pp}"
    else:  # future_perfect_continuous
        aux, rest = "will", f"have been {ing}"

    tail = f" {rest}" if rest else ""
    if mode == "affirmative":
        return f"{subj} {aux}{tail}"
    if mode == "negative":
        return f"{subj} {aux} not{tail}"
    return f"{_cap(aux)} {subj}{tail}?"


def table(base: str, mode: str = "affirmative", v2: str | None = None,
          v3: str | None = None) -> dict[str, dict[str, str]]:
    """{время: {лицо: строка}} — 12 × 5 ячеек."""
    return {t: {p: conjugate(base, t, p, mode, v2, v3) for p in PERSON_KEYS} for t in TENSE_KEYS}


def irregular_tokens(base: str, v2: str | None = None, v3: str | None = None) -> set[str]:
    """Неправильные формы глагола (для подсветки в таблице)."""
    if not v2 and not v3:
        return set()
    rp = regular_past(base)
    out = set()
    for x in (v2 or "", v3 or ""):
        for part in x.split("/"):
            part = part.strip().lower()
            if part and part != rp:
                out.add(part)
    if base.lower() == "be":
        out |= {"am", "is", "are", "was", "were", "been"}
    return out
