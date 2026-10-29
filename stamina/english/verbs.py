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


# ---------------------------------------------------------------------------
# Паки глаголов из настоящих данных (tools/build_verbs_pack.py):
#   data/verbs/irregular.json      — ~200 неправильных глаголов, формы/IPA/RU из Kaikki (Wiktionary),
#                                    примеры из Tatoeba (у каждого source_id);
#   data/verbs/frequent_1000.json  — 1000 частых глаголов, открываются постепенно.
# Приложение в сеть за глаголами не ходит: только читает эти файлы.
# ---------------------------------------------------------------------------
import json as _json
from pathlib import Path as _Path

PACK_DIR = _Path(__file__).resolve().parent / "data" / "verbs"

# Разблокировка пака 1000: сразу открыто UNLOCK_START глаголов; каждый следующий шаг
# в UNLOCK_STEP глаголов открывается, когда освоено UNLOCK_NEED глаголов на шаг
# (освоен = «знаю» или карточка SM-2 с интервалом ≥ 21 дня).
UNLOCK_START = 50
UNLOCK_STEP = 50
UNLOCK_NEED = 30

_PACKS: dict[str, dict] = {}


def load_pack(name: str) -> dict:
    """Пак целиком (meta + verbs). name: "irregular" | "frequent_1000"."""
    if name not in _PACKS:
        path = PACK_DIR / f"{name}.json"
        try:
            _PACKS[name] = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _PACKS[name] = {"verbs": []}
    return _PACKS[name]


def irregular() -> list[dict]:
    return load_pack("irregular")["verbs"]


def frequent() -> list[dict]:
    return load_pack("frequent_1000")["verbs"]


def pack_verb(lemma: str) -> dict | None:
    """Запись глагола из паков (сначала неправильные)."""
    lemma = (lemma or "").strip().lower()
    for v in irregular():
        if v["lemma"] == lemma:
            return v
    for v in frequent():
        if v["lemma"] == lemma:
            return v
    return None


def all_pack_verbs() -> list[dict]:
    """Неправильные + частые без повторов, в порядке частотности."""
    seen, out = set(), []
    for v in irregular() + frequent():
        if v["lemma"] not in seen:
            seen.add(v["lemma"])
            out.append(v)
    return out


def search(query: str, pool: list[dict] | None = None, limit: int = 60) -> list[dict]:
    """Поиск с первого символа: сначала по началу лемм и форм, потом по вхождению и по-русски."""
    pool = all_pack_verbs() if pool is None else pool
    q = (query or "").strip().lower()
    if not q:
        return pool[:limit]
    first, second = [], []
    for v in pool:
        forms_ = [v["lemma"], *v.get("v2", "").split("/"), *v.get("v3", "").split("/")]
        if any(f.startswith(q) for f in forms_):
            first.append(v)
        elif q in v["lemma"] or q in (v.get("ru") or "").lower():
            second.append(v)
    first.sort(key=lambda v: (not v["lemma"].startswith(q), v.get("rank") or 10 ** 6))
    return (first + second)[:limit]


def _mastered(progress, lemma: str) -> bool:
    return bool(progress.is_known(lemma) or progress.is_learned(lemma))


def unlock_need(progress) -> int:
    getter = getattr(progress, "verbs_unlock_need", None)
    return int(getter()) if callable(getter) else UNLOCK_NEED


def unlocked_count(progress, pack: list[dict] | None = None) -> int:
    """Сколько глаголов пака 1000 открыто при этом прогрессе."""
    pack = frequent() if pack is None else pack
    need = unlock_need(progress)
    n = min(len(pack), UNLOCK_START)
    while n < len(pack):
        steps = (n - UNLOCK_START) // UNLOCK_STEP + 1
        done = sum(1 for v in pack[:n] if _mastered(progress, v["lemma"]))
        if done < steps * need:
            break
        n = min(len(pack), n + UNLOCK_STEP)
    return n


def is_locked(progress, lemma: str) -> bool:
    """Неправильные глаголы открыты всегда; частые — по прогрессу."""
    if any(v["lemma"] == lemma for v in irregular()):
        return False
    pack = frequent()
    idx = next((i for i, v in enumerate(pack) if v["lemma"] == lemma), None)
    return idx is not None and idx >= unlocked_count(progress, pack)


def locked_lemmas(progress) -> set[str]:
    """Все закрытые сейчас леммы пака 1000 (неправильные не закрываются)."""
    pack = frequent()
    irr = {v["lemma"] for v in irregular()}
    return {v["lemma"] for v in pack[unlocked_count(progress, pack):]} - irr


def unlock_hint(progress, pack: list[dict] | None = None) -> tuple[int, int]:
    """(сколько ещё освоить, сколько глаголов откроется) до следующего шага."""
    pack = frequent() if pack is None else pack
    n = unlocked_count(progress, pack)
    if n >= len(pack):
        return 0, 0
    steps = (n - UNLOCK_START) // UNLOCK_STEP + 1
    done = sum(1 for v in pack[:n] if _mastered(progress, v["lemma"]))
    return max(0, steps * unlock_need(progress) - done), min(UNLOCK_STEP, len(pack) - n)


TENSE_FORM = {  # какая форма глагола видна во времени → какой реальный пример показать
    "present_simple": ("v1", "s"), "future_simple": ("v1",),
    "past_simple": ("v2",),
    "present_continuous": ("ing",), "past_continuous": ("ing",), "future_continuous": ("ing",),
    "present_perfect_continuous": ("ing",), "past_perfect_continuous": ("ing",),
    "future_perfect_continuous": ("ing",),
    "present_perfect": ("v3",), "past_perfect": ("v3",), "future_perfect": ("v3",),
}


def example_for(verb: dict, tense: str) -> dict | None:
    """Настоящий пример (Tatoeba) с формой, которая используется в этом времени."""
    want = set()
    for k in TENSE_FORM.get(tense, ("v1",)):
        val = verb["lemma"] if k == "v1" else verb.get(k) or ""
        want |= {x.strip() for x in val.split("/") if x.strip()}
    exs = verb.get("examples") or []
    return next((e for e in exs if e.get("form") in want), exs[0] if exs else None)


def add_to_card(progress, vocab, verb: dict, tense: str, person: str, mode: str, text: str) -> bool:
    """«→ в карточку»: запоминаем форму с примером и отправляем глагол на склад.

    Склад (warehouse.candidate_slugs/is_ready) берёт слова «знаю» с примерами из словаря,
    поэтому отмечаем лемму как известную, если она есть в словаре. Возвращает True,
    если карточка видна на складе.
    """
    from . import warehouse
    lemma = verb["lemma"]
    ex = example_for(verb, tense)
    rec = {"tense": tense, "person": person, "mode": mode, "text": text,
           "example": ex.get("en") if ex else "", "example_ru": ex.get("ru") if ex else "",
           "source_id": ex.get("source_id") if ex else None}
    saved = progress.data.setdefault("verb_forms", {}).setdefault(lemma, [])
    if not any(r["tense"] == tense and r["person"] == person and r["mode"] == mode for r in saved):
        saved.append(rec)
    w = vocab.get(lemma) if vocab is not None else None
    if w and not progress.is_known(lemma):
        progress.set_known(lemma, True)
    else:
        progress.save()
    return bool(w) and warehouse.is_ready(progress, vocab, lemma)
