"""Дебрифинг — проверка понимания прочитанного куска (без интернета)."""
from __future__ import annotations

import random


from .rsvp import Word, core_span

_DECOYS = {
    "en": ["mountain", "silver", "engine", "harbour", "violin", "blanket", "garden", "planet", "captain",
           "pocket", "theatre", "carpet", "lantern", "bicycle", "orchard", "festival", "compass", "kitchen"],
    "ru": ["самовар", "крепость", "лестница", "пароход", "мельница", "колокол", "фонарик", "пустыня",
           "скрипка", "библиотека", "трамвай", "черника", "подсолнух", "маятник", "кораблик", "огород"],
}


def _core(w: str) -> str:
    a, b = core_span(w)
    return w[a:b].lower()


def make_quiz(words: list[Word], start: int, end: int, lang: str = "en", rng=None) -> list[dict]:
    """Задания по словам [start, end): «было ли слово» ×6 и «закончи фразу» ×2.

    Каждое задание: {kind, question, options, answer}."""
    rng = rng or random.Random()
    seg = words[start:end]
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
    items = [{"kind": "seen", "question": f"Было ли в тексте слово «{w}»?", "options": ["ДА", "НЕТ"],
              "answer": 0} for w in yes]
    items += [{"kind": "seen", "question": f"Было ли в тексте слово «{w}»?", "options": ["ДА", "НЕТ"],
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
        items.append({"kind": "gap", "question": f"Закончите фразу:\n{shown}", "options": opts,
                      "answer": opts.index(ans)})
    rng.shuffle(items)
    return items
