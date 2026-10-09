"""Дебрифинг — проверка понимания прочитанного куска (без интернета)."""
from __future__ import annotations

from stamina.i18n import t

import random


from .rsvp import Word, core_span

_DECOYS = {
    "en": ["mountain", "silver", "engine", "harbour", "violin", "blanket", "garden", "planet", "captain",
           "pocket", "theatre", "carpet", "lantern", "bicycle", "orchard", "festival", "compass", "kitchen"],
    "ru": ["самовар", "крепость", "лестница", "пароход", "мельница", "колокол", "фонарик", "пустыня",
           "скрипка", "библиотека", "трамвай", "черника", "подсолнух", "маятник", "кораблик", "огород"],
    "uk": ["самовар", "фортеця", "драбина", "пароплав", "млинок", "дзвіниця", "ліхтарик", "пустеля",
           "скрипка", "бібліотека", "трамвай", "чорниця", "соняшник", "маятник", "кораблик", "городина"],
    "de": ["gebirge", "silber", "maschine", "hafenstadt", "geige", "decke", "garten", "planeten",
           "kapitän", "tasche", "theater", "teppich", "laterne", "fahrrad", "obstgarten", "kompass", "küche"],
}


def _core(w: str) -> str:
    a, b = core_span(w)
    return w[a:b].lower()


def make_quiz(words: list[Word], start: int, end: int, lang: str = "en", rng=None) -> list[dict]:
    """Задания по словам [start, end): «было ли слово» ×6 и «закончи фразу» ×2.

    Каждое задание: {kind, question, options, answer}."""
    rng = rng or random.Random()
    seg = words[start:end]
    if lang in ("", "auto", None) or lang not in _DECOYS:
        from stamina.langdetect import detect
        guess = detect(" ".join(w.text for w in seg[:800]))
        lang = guess if guess in _DECOYS else ("en" if lang in ("", "auto", None) else lang)
    if len(seg) < 40:
        return []
    seen = {_core(w.text) for w in seg}
    long_words = sorted({c for c in seen if len(c) >= 6 and c.isalpha()})
    rng.shuffle(long_words)
    yes = long_words[:3]
    later = {_core(w.text) for w in words[end:end + 3000]} - seen
    pool = [c for c in later if len(c) >= 6 and c.isalpha()] or []
    pool += [d for d in _DECOYS.get(lang, _DECOYS["en"]) if d not in seen]
    rng.shuffle(pool)
    no = pool[:3]
    items = [{"kind": "seen", "question": t("Было ли в тексте слово «{0}»?").format(w), "options": [t("ДА"), t("НЕТ")],
              "answer": 0} for w in yes]
    items += [{"kind": "seen", "question": t("Было ли в тексте слово «{0}»?").format(w), "options": [t("ДА"), t("НЕТ")],
               "answer": 1} for w in no]
    # предложения
    sentences: list[list[Word]] = []
    cur: list[Word] = []
    for w in seg:
        cur.append(w)
        if w.sent_end:
            if 6 <= len(cur) <= 30:
                sentences.append(cur)
            cur = []
    rng.shuffle(sentences)
    for sent in sentences[:2]:
        cand = [i for i, w in enumerate(sent) if len(_core(w.text)) >= 5 and _core(w.text).isalpha()]
        if not cand:
            continue
        k = cand[-1] if rng.random() < 0.6 else rng.choice(cand)
        ans = _core(sent[k].text)
        others = [c for c in long_words + list(seen) if c != ans and len(c) >= 4 and c.isalpha()]
        rng.shuffle(others)
        opts = list(dict.fromkeys([ans] + others))[:4]
        if len(opts) < 4:
            continue
        rng.shuffle(opts)
        shown = " ".join(w.text if i != k else "_____" for i, w in enumerate(sent))
        items.append({"kind": "gap", "question": t("Закончите фразу:\n{0}").format(shown), "options": opts,
                      "answer": opts.index(ans)})
    rng.shuffle(items)
    return items
