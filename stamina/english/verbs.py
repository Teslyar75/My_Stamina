"""Глаголы: 12 времён по настоящим пакам (Wiktionary + Tatoeba), разблокировка, поиск."""
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

# Вкладка «ГЛАГОЛЫ» берёт глаголы только из настоящих паков (data/verbs/*.json):
# формы и перевод — Kaikki/Wiktionary, пример — Tatoeba. Фраза для произношения в
# каждом времени строится правилами conjugation.py (это грамматика, а не данные).
TAB_LIMIT = 60  # сколько частых неправильных глаголов показывать в списке вкладки


def _first(form: str) -> str:
    return (form or "").split("/")[0].strip()


def _entry(v: dict) -> dict:
    from . import conjugation as cj
    base = v["lemma"]
    past, pp = _first(v.get("v2")) or cj.regular_past(base), _first(v.get("v3")) or cj.regular_past(base)
    return {"slug": base, "word": base, "ru": v.get("ru") or "", "pack": v,
            "forms": {"base": base, "past": past, "pp": pp, "ing": v.get("ing") or cj.ing_form(base)}}


def entries() -> list[dict]:
    """Глаголы вкладки: частые неправильные из пака, по частотности."""
    pool = sorted(irregular(), key=lambda v: v.get("rank") or 10 ** 6)[:TAB_LIMIT]
    return [_entry(v) for v in pool]


def find(slug: str) -> dict | None:
    for v in entries():
        if v["slug"] == slug:
            return v
    pv = pack_verb(slug)
    return _entry(pv) if pv else None


def tenses() -> list[tuple[str, str, str, str]]:
    return list(TENSES)


def sentences(verb: dict) -> list[dict]:
    """12 строк: время, фраза (conjugation.py, лицо I) и настоящий пример Tatoeba под ней."""
    from . import conjugation as cj
    pv = verb.get("pack") or pack_verb(verb["slug"]) or {"lemma": verb["slug"]}
    out = []
    for key, en_name, ru_name, hint in TENSES:
        en = cj.conjugate(verb["slug"], key, "I", v2=pv.get("v2"), v3=pv.get("v3"))
        ex = example_for(pv, key) if pv.get("examples") else None
        ru = f"{ex['en']} — {ex.get('ru') or ''} (tatoeba.org #{ex['source_id']})" if ex else ""
        out.append({"key": key, "tense": en_name, "tense_ru": ru_name, "hint": hint,
                    "en": en, "ru": ru, "example": ex})
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
