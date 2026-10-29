"""Качественные повторения карточки: до 20 слотов, цель настраивается.

Слот — это одно зачтённое действие: произнести слово, прочитать предложение,
перевести с русского, понять на слух, составить своё. Слот загорается по
результату распознавания; вручную отмечается только «своё» (E) и режим без
микрофона — такая галочка считается самооценкой.

Хранится в %APPDATA%\\Stamina\\english.json → data["quality"][slug].
Модуль ничего не знает про Tk: только прогресс и правила.
"""
from __future__ import annotations

import datetime as dt

MAX_SLOTS = 20
DEFAULT_GOAL = 20
GOAL_CHOICES = (5, 10, 15, 20)
# Интервальное повторение: не больше 4 слотов одной карточки в день — остальное завтра.
# 0 в настройках «quality_daily_cap» снимает ограничение. Пороги оценки это не меняет.
DAILY_CAP = 4

# Пороги по порядку прохода внутри группы (A: 4 повтора, B: 2 прохода и т.д.)
THRESHOLDS = {
    "A": (80, 80, 85, 90),
    "B": (80, 85),
    "C": (85, 88, 90),
    "D": (80, 85),
    "E": (0,),
}

# Сколько слотов каждого блока нужно для 20. Для слова B = 5 предложений × 2.
KINDS = {
    "word": {"A": 4, "B": 10, "C": 3, "D": 2, "E": 1},
    "verb": {"A": 6, "B": 6, "C": 4, "D": 3, "E": 1},
    "sentence": {"A": 2, "B": 6, "C": 8, "D": 3, "E": 1},
}
KIND_TITLES = {"word": "слово", "verb": "глагол", "sentence": "предложение"}

GROUP_TITLES = {
    "A": "СЛОВО",
    "B": "ЧТЕНИЕ",
    "C": "ПЕРЕВОД",
    "D": "АУДИО",
    "E": "СВОЁ",
}
GROUP_HINTS = {
    "A": "сказать слово по-английски",
    "B": "прочитать предложение вслух (EN виден)",
    "C": "перевести с русского (EN скрыт)",
    "D": "услышать и повторить",
    "E": "составить своё предложение",
}


def _today() -> str:
    return dt.date.today().isoformat()


# ---------------------------------------------------------------------------
# Профиль карточки
# ---------------------------------------------------------------------------

def slots(kind: str = "word", n_sents: int = 5) -> list[dict]:
    """Список слотов в каноническом порядке: A, B, C, D, E."""
    spec = KINDS.get(kind, KINDS["word"])
    n_sents = max(1, int(n_sents or 1))
    b_max = min(int(spec["B"]), 2 * n_sents)
    out: list[dict] = []

    for i in range(int(spec["A"])):
        out.append({"key": f"a{i}", "group": "A", "n": i,
                    "threshold": THRESHOLDS["A"][min(i, len(THRESHOLDS["A"]) - 1)],
                    "label": f"слово {i + 1}"})
    pairs = min(n_sents, max(1, b_max // 2))
    b_added = 0
    for si in range(pairs):
        for part in (0, 1):
            if b_added >= b_max:
                break
            out.append({"key": f"b{si}{part}", "group": "B", "n": si, "part": part,
                        "threshold": THRESHOLDS["B"][part],
                        "label": f"предл. {si + 1}{'.2' if part else '.1'}"})
            b_added += 1
    for i in range(int(spec["C"])):
        out.append({"key": f"c{i}", "group": "C", "n": i,
                    "threshold": THRESHOLDS["C"][min(i, len(THRESHOLDS["C"]) - 1)],
                    "label": "перевод"})
    for i in range(int(spec["D"])):
        out.append({"key": f"d{i}", "group": "D", "n": i,
                    "threshold": THRESHOLDS["D"][min(i, len(THRESHOLDS["D"]) - 1)],
                    "label": "аудио"})
    for i in range(int(spec["E"])):
        out.append({"key": f"e{i}", "group": "E", "n": i, "threshold": 0,
                    "label": "своё"})
    return out


def slot_map(kind: str = "word", n_sents: int = 5) -> dict[str, dict]:
    return {s["key"]: s for s in slots(kind, n_sents)}


def effective_goal(goal: int, total: int) -> int:
    """Цель не может быть больше, чем слотов у карточки."""
    try:
        g = int(goal)
    except (TypeError, ValueError):
        g = DEFAULT_GOAL
    return max(1, min(g, max(1, total)))


# ---------------------------------------------------------------------------
# Хранилище (progress.data["quality"])
# ---------------------------------------------------------------------------

def _store(progress) -> dict:
    q = progress.data.setdefault("quality", {})
    return q


def ensure(progress, slug: str, kind: str = "word", n_sents: int = 5,
           goal: int | None = None) -> dict:
    """Запись карточки. Цель фиксируется при первом открытии."""
    rec = _store(progress).get(slug)
    total = len(slots(kind, n_sents))
    if not isinstance(rec, dict):
        g = effective_goal(goal if goal is not None else
                           progress.settings.get("quality_goal", DEFAULT_GOAL), total)
        rec = {"kind": kind, "n_sents": int(n_sents), "goal": g, "slots": {}, "self": 0}
        _store(progress)[slug] = rec
        progress.save()
    rec.setdefault("kind", kind)
    rec.setdefault("n_sents", int(n_sents))
    rec.setdefault("slots", {})
    rec.setdefault("self", 0)
    rec["goal"] = effective_goal(rec.get("goal", DEFAULT_GOAL), total)
    return rec


def get(progress, slug: str) -> dict | None:
    rec = _store(progress).get(slug)
    return rec if isinstance(rec, dict) else None


def goal(progress, slug: str, kind: str = "word", n_sents: int = 5) -> int:
    return int(ensure(progress, slug, kind, n_sents).get("goal") or DEFAULT_GOAL)


def set_goal(progress, slug: str, n: int, kind: str = "word", n_sents: int = 5) -> int:
    rec = ensure(progress, slug, kind, n_sents)
    rec["goal"] = effective_goal(n, len(slots(kind, n_sents)))
    progress.save()
    return rec["goal"]


def filled(progress, slug: str) -> int:
    rec = get(progress, slug)
    return len((rec or {}).get("slots") or {})


def filled_keys(progress, slug: str) -> set[str]:
    rec = get(progress, slug)
    return set(((rec or {}).get("slots") or {}).keys())


def is_complete(progress, slug: str, kind: str = "word", n_sents: int = 5) -> bool:
    rec = get(progress, slug)
    if not rec:
        return False
    total = len(slots(rec.get("kind", kind), rec.get("n_sents", n_sents)))
    g = effective_goal(rec.get("goal", DEFAULT_GOAL), total)
    return len(rec.get("slots") or {}) >= g


def record(progress, slug: str, key: str, score: int | None = None, *,
           self_rated: bool = False, kind: str = "word", n_sents: int = 5) -> str:
    """Зачесть слот. Возвращает: "ok" | "filled" | "low" | "unknown" | "self" | "cap"."""
    rec = ensure(progress, slug, kind, n_sents)
    sm = slot_map(rec.get("kind", kind), rec.get("n_sents", n_sents))
    slot = sm.get(key)
    if slot is None:
        return "unknown"
    if key in (rec.get("slots") or {}):
        return "filled"
    cap = daily_cap(progress)
    if cap and today_count(progress, slug) >= cap:
        return "cap"                        # на сегодня карточке хватит — вернётся завтра
    if not self_rated:
        need = int(slot.get("threshold", 0) or 0)
        if int(score or 0) < need:
            return "low"
    rec.setdefault("slots", {})[key] = [None if (self_rated or score is None) else int(score), _today()]
    if self_rated:
        rec["self"] = int(rec.get("self", 0) or 0) + 1
    progress.save()
    return "self" if self_rated else "ok"


def daily_cap(progress) -> int:
    try:
        return max(0, int(progress.settings.get("quality_daily_cap", DAILY_CAP)))
    except (TypeError, ValueError):
        return DAILY_CAP


def today_count(progress, slug: str) -> int:
    """Сколько слотов карточки зачтено сегодня."""
    today = _today()
    rec = get(progress, slug) or {}
    return sum(1 for v in (rec.get("slots") or {}).values()
               if isinstance(v, (list, tuple)) and len(v) > 1 and v[1] == today)


def left_today(progress, slug: str) -> int:
    cap = daily_cap(progress)
    return 10 ** 6 if not cap else max(0, cap - today_count(progress, slug))


def due_today(progress, slugs=None) -> list[str]:
    """«Сегодня повторить»: начатые незакрытые карточки, у которых не исчерпан дневной лимит.
    Сначала давно не тронутые (по дате последнего слота)."""
    store = _store(progress)
    pool = list(store) if slugs is None else [s for s in slugs if s in store]
    out = []
    for slug in pool:
        rec = get(progress, slug)
        if not rec or not rec.get("slots") or is_complete(progress, slug):
            continue
        if left_today(progress, slug) <= 0:
            continue
        last = max((v[1] for v in rec["slots"].values()
                    if isinstance(v, (list, tuple)) and len(v) > 1 and v[1]), default="")
        out.append((last, slug))
    return [s for _l, s in sorted(out)]


def next_slot(progress, slug: str, group: str, score: int | None = None,
              *, si: int | None = None, kind: str = "word", n_sents: int = 5) -> str | None:
    """Следующий незакрытый слот группы (для B — сначала пара нужного предложения)."""
    rec = ensure(progress, slug, kind, n_sents)
    sm = slot_map(rec.get("kind", kind), rec.get("n_sents", n_sents))
    done = set(rec.get("slots") or {})
    cand = [s for s in sm.values() if s["group"] == group and s["key"] not in done]
    if group == "B" and si is not None:
        own = [s for s in cand if s.get("n") == si]
        cand = own or cand
    if not cand:
        return None
    if score is not None:
        ok = [s for s in cand if s.get("threshold", 0) <= int(score)]
        if not ok:
            return cand[0]["key"]          # UI покажет, сколько не хватило
        return ok[0]["key"]
    return cand[0]["key"]


def auto(progress, slug: str, group: str, score: int, *, si: int | None = None,
         self_rated: bool = False, kind: str = "word", n_sents: int = 5) -> tuple[str, str | None]:
    """Зачесть лучший подходящий слот группы. (итог, ключ)."""
    key = next_slot(progress, slug, group, score, si=si, kind=kind, n_sents=n_sents)
    if key is None:
        return "full", None
    res = record(progress, slug, key, score, self_rated=self_rated, kind=kind, n_sents=n_sents)
    return res, key


def counts(progress, slug: str, kind: str = "word", n_sents: int = 5) -> dict:
    """Сводка для интерфейса: всего, цель, закрыто, по группам. Ничего не пишет."""
    rec = get(progress, slug) or {}
    k = rec.get("kind", kind)
    n = int(rec.get("n_sents", n_sents) or n_sents)
    sm = slot_map(k, n)
    done = set(rec.get("slots") or {})
    total = len(sm)
    raw_goal = rec.get("goal") or progress.settings.get("quality_goal", DEFAULT_GOAL)
    g = effective_goal(raw_goal, total)
    by: dict[str, list[int]] = {k2: [0, 0] for k2 in GROUP_TITLES}
    for s in sm.values():
        by.setdefault(s["group"], [0, 0])[1] += 1
        if s["key"] in done:
            by[s["group"]][0] += 1
    return {"total": total, "goal": g, "filled": len(done & set(sm)),
            "self": int(rec.get("self", 0) or 0), "by": by,
            "done_keys": done & set(sm), "slots": list(sm.values())}


def remaining(progress, slug: str, kind: str = "word", n_sents: int = 5) -> int:
    c = counts(progress, slug, kind, n_sents)
    return max(0, c["goal"] - c["filled"])


def average_score(progress, slug: str) -> float:
    """Средняя по зачтённым слотам (самооценка без балла не учитывается)."""
    rec = get(progress, slug) or {}
    vals = [int(v[0]) for v in (rec.get("slots") or {}).values()
            if isinstance(v, (list, tuple)) and v and v[0] is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def hint(progress, slug: str, kind: str = "word", n_sents: int = 5) -> str:
    """Короткая подсказка «что делать дальше»."""
    c = counts(progress, slug, kind, n_sents)
    if c["filled"] >= c["goal"]:
        return "готово"
    for gkey in ("A", "B", "C", "D", "E"):
        f, n = c["by"].get(gkey, (0, 0))
        if f < n:
            return f"{GROUP_TITLES[gkey].lower()} · {f}/{n}"
    return ""


def reset(progress, slug: str) -> None:
    rec = get(progress, slug)
    if rec:
        rec["slots"] = {}
        rec["self"] = 0
        progress.save()


# ---------------------------------------------------------------------------
# Миграция
# ---------------------------------------------------------------------------

def migrate(progress) -> None:
    """v1 → v2: добавить quality и цель. Старые «прогоны» не пересчитываем."""
    d = progress.data
    d.setdefault("quality", {})
    st = d.setdefault("settings", {})
    st.setdefault("quality_goal", DEFAULT_GOAL)
    if int(d.get("version", 1) or 1) < 2:
        d["version"] = 2
        progress.save()
