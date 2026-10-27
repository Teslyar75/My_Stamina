"""Глаголы: 12 времён, примеры и русский перевод.

Данные держим отдельно от Tk: страница «ГЛАГОЛЫ» только показывает то, что
собрано здесь. Каждый глагол даёт ровно 12 предложений — по одному на время.
"""
from __future__ import annotations

TENSES = [
    ("present_simple", "Present Simple", "Настоящее простое", "регулярное действие"),
    ("present_continuous", "Present Continuous", "Настоящее длительное", "прямо сейчас"),
    ("present_perfect", "Present Perfect", "Настоящее совершенное", "результат к настоящему"),
    ("present_perfect_continuous", "Present Perfect Continuous", "Настоящее совершенное длительное",
     "длится до настоящего"),
    ("past_simple", "Past Simple", "Прошедшее простое", "завершённое действие"),
    ("past_continuous", "Past Continuous", "Прошедшее длительное", "процесс в прошлом"),
    ("past_perfect", "Past Perfect", "Прошедшее совершенное", "завершено до другого прошлого"),
    ("past_perfect_continuous", "Past Perfect Continuous", "Прошедшее совершенное длительное",
     "длилось до другого прошлого"),
    ("future_simple", "Future Simple", "Будущее простое", "решение или прогноз"),
    ("future_continuous", "Future Continuous", "Будущее длительное", "процесс в будущем"),
    ("future_perfect", "Future Perfect", "Будущее совершенное", "завершится к сроку"),
    ("future_perfect_continuous", "Future Perfect Continuous", "Будущее совершенное длительное",
     "будет длиться к сроку"),
]

_VERBS = [
    {
        "slug": "work", "word": "work", "ru": "работать",
        "forms": {"base": "work", "past": "worked", "pp": "worked", "ing": "working"},
        "obj": "at the office", "ru_obj": "в офисе",
        "ru_pres": "работаю", "ru_past": "работал", "ru_inf": "работать", "ru_fut": "поработаю",
    },
    {
        "slug": "read", "word": "read", "ru": "читать",
        "forms": {"base": "read", "past": "read", "pp": "read", "ing": "reading"},
        "obj": "a book", "ru_obj": "книгу",
        "ru_pres": "читаю", "ru_past": "читал", "ru_inf": "читать", "ru_fut": "прочитаю",
    },
    {
        "slug": "write", "word": "write", "ru": "писать",
        "forms": {"base": "write", "past": "wrote", "pp": "written", "ing": "writing"},
        "obj": "a letter", "ru_obj": "письмо",
        "ru_pres": "пишу", "ru_past": "писал", "ru_inf": "писать", "ru_fut": "напишу",
    },
    {
        "slug": "speak", "word": "speak", "ru": "говорить",
        "forms": {"base": "speak", "past": "spoke", "pp": "spoken", "ing": "speaking"},
        "obj": "English", "ru_obj": "по-английски",
        "ru_pres": "говорю", "ru_past": "говорил", "ru_inf": "говорить", "ru_fut": "скажу",
    },
    {
        "slug": "play", "word": "play", "ru": "играть",
        "forms": {"base": "play", "past": "played", "pp": "played", "ing": "playing"},
        "obj": "football", "ru_obj": "в футбол",
        "ru_pres": "играю", "ru_past": "играл", "ru_inf": "играть", "ru_fut": "поиграю",
    },
    {
        "slug": "study", "word": "study", "ru": "изучать",
        "forms": {"base": "study", "past": "studied", "pp": "studied", "ing": "studying"},
        "obj": "English", "ru_obj": "английский",
        "ru_pres": "изучаю", "ru_past": "изучал", "ru_inf": "изучать", "ru_fut": "изучу",
    },
    {
        "slug": "eat", "word": "eat", "ru": "есть",
        "forms": {"base": "eat", "past": "ate", "pp": "eaten", "ing": "eating"},
        "obj": "an apple", "ru_obj": "яблоко",
        "ru_pres": "ем", "ru_past": "ел", "ru_inf": "есть", "ru_fut": "съем",
    },
    {
        "slug": "cook", "word": "cook", "ru": "готовить",
        "forms": {"base": "cook", "past": "cooked", "pp": "cooked", "ing": "cooking"},
        "obj": "dinner", "ru_obj": "ужин",
        "ru_pres": "готовлю", "ru_past": "готовил", "ru_inf": "готовить", "ru_fut": "приготовлю",
    },
    {
        "slug": "travel", "word": "travel", "ru": "путешествовать",
        "forms": {"base": "travel", "past": "traveled", "pp": "traveled", "ing": "traveling"},
        "obj": "around the world", "ru_obj": "по миру",
        "ru_pres": "путешествую", "ru_past": "путешествовал", "ru_inf": "путешествовать",
        "ru_fut": "попутешествую",
    },
    {
        "slug": "learn", "word": "learn", "ru": "учить",
        "forms": {"base": "learn", "past": "learned", "pp": "learned", "ing": "learning"},
        "obj": "new words", "ru_obj": "новые слова",
        "ru_pres": "учу", "ru_past": "учил", "ru_inf": "учить", "ru_fut": "выучу",
    },
    {
        "slug": "build", "word": "build", "ru": "строить",
        "forms": {"base": "build", "past": "built", "pp": "built", "ing": "building"},
        "obj": "a house", "ru_obj": "дом",
        "ru_pres": "строю", "ru_past": "строил", "ru_inf": "строить", "ru_fut": "построю",
    },
    {
        "slug": "paint", "word": "paint", "ru": "рисовать",
        "forms": {"base": "paint", "past": "painted", "pp": "painted", "ing": "painting"},
        "obj": "a picture", "ru_obj": "картину",
        "ru_pres": "рисую", "ru_past": "рисовал", "ru_inf": "рисовать", "ru_fut": "нарисую",
    },
]


def entries() -> list[dict]:
    """Все глаголы в порядке показа."""
    return _VERBS


def find(slug: str) -> dict | None:
    return next((v for v in _VERBS if v["slug"] == slug), None)


def tenses() -> list[tuple[str, str, str, str]]:
    return list(TENSES)


def sentences(verb: dict) -> list[dict]:
    """12 примеров: ключ, английское название времени, русское, подсказка, EN, RU."""
    f = verb["forms"]
    base, past, pp, ing = f["base"], f["past"], f["pp"], f["ing"]
    obj, ru_obj = verb["obj"], verb["ru_obj"]
    pres, ru_past, inf, fut = verb["ru_pres"], verb["ru_past"], verb["ru_inf"], verb["ru_fut"]
    en = {
        "present_simple": f"I {base} {obj} every day.",
        "present_continuous": f"I am {ing} {obj} now.",
        "present_perfect": f"I have {pp} {obj} already.",
        "present_perfect_continuous": f"I have been {ing} {obj} for an hour.",
        "past_simple": f"I {past} {obj} yesterday.",
        "past_continuous": f"I was {ing} {obj} at five.",
        "past_perfect": f"I had {pp} {obj} before you came.",
        "past_perfect_continuous": f"I had been {ing} {obj} for an hour before you came.",
        "future_simple": f"I will {base} {obj} tomorrow.",
        "future_continuous": f"I will be {ing} {obj} at five tomorrow.",
        "future_perfect": f"I will have {pp} {obj} by tomorrow.",
        "future_perfect_continuous": f"I will have been {ing} {obj} for an hour by then.",
    }
    ru = {
        "present_simple": f"Я {pres} {ru_obj} каждый день.",
        "present_continuous": f"Я {pres} {ru_obj} сейчас.",
        "present_perfect": f"Я уже {ru_past} {ru_obj}.",
        "present_perfect_continuous": f"Я {pres} {ru_obj} уже час.",
        "past_simple": f"Я {ru_past} {ru_obj} вчера.",
        "past_continuous": f"Я {ru_past} {ru_obj} в пять.",
        "past_perfect": f"Я {ru_past} {ru_obj} до твоего прихода.",
        "past_perfect_continuous": f"Я {ru_past} {ru_obj} час до твоего прихода.",
        "future_simple": f"Я {fut} {ru_obj} завтра.",
        "future_continuous": f"Я буду {inf} {ru_obj} в пять завтра.",
        "future_perfect": f"Я {fut} {ru_obj} к завтрашнему дню.",
        "future_perfect_continuous": f"Я буду {inf} {ru_obj} уже час к тому времени.",
    }
    out = []
    for key, en_name, ru_name, hint in TENSES:
        out.append({"key": key, "tense": en_name, "tense_ru": ru_name, "hint": hint,
                    "en": en[key], "ru": ru[key]})
    return out
