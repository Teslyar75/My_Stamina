"""Уроки: последовательный план по уровням + отметки о прохождении.

Правила урока — id из справочника (grammar.py), слова — slug из набора CEFR.
Урок открывается только после предыдущего: так порядок не перескакивает.
"""
from __future__ import annotations

import datetime as dt

from . import cefr

# План A1. Каждый урок: правило(а) + слова + шаги.
# Слова берутся из data/sets/cefr_a1.json (slug).
PLANS: dict[str, list[dict]] = {
    "A1": [
        {
            "id": "a1-01", "n": 1, "title": "Я и ты",
            "goal": "Рассказать о себе и других через to be.",
            "rules": ["a1-to-be", "a1-pronouns"],
            "words": ["good", "happy", "friend", "family", "mother", "father"],
            "steps": ["Прочитать правило to be и местоимения",
                      "Карточки: 6 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Сказать о себе: I am…"],
        },
        {
            "id": "a1-02", "n": 2, "title": "Предметы вокруг",
            "goal": "Называть предметы и считать их: a / an, множественное число.",
            "rules": ["a1-articles", "a1-plural"],
            "words": ["apple", "water", "bread", "book", "house", "car"],
            "steps": ["Прочитать правило артиклей и множественного числа",
                      "Карточки: 6 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: This is a…"],
        },
        {
            "id": "a1-03", "n": 3, "title": "Мой день",
            "goal": "Говорить о привычках в Present Simple.",
            "rules": ["a1-present-simple"],
            "words": ["day", "morning", "evening", "time", "work", "school"],
            "steps": ["Прочитать правило Present Simple",
                      "Карточки: 6 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: I … every day"],
        },
        {
            "id": "a1-04", "n": 4, "title": "Что я делаю",
            "goal": "Спросить и ответить: do / does, короткие ответы.",
            "rules": ["a1-do-does", "a1-present-simple"],
            "words": ["go", "come", "eat", "drink"],
            "steps": ["Прочитать правило do / does",
                      "Карточки: 4 глагола", "Вопросы и короткие ответы",
                      "Прочитать примеры вслух", "Составить свой вопрос"],
        },
        {
            "id": "a1-05", "n": 5, "title": "Я вижу и люблю",
            "goal": "Сказать, что вижу и что люблю, без ошибки в -s.",
            "rules": ["a1-present-simple", "a1-do-does"],
            "words": ["see", "like", "help", "city"],
            "steps": ["Повторить Present Simple и do / does",
                      "Карточки: 4 слова", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: I like…"],
        },
        {
            "id": "a1-06", "n": 6, "title": "Мир вокруг",
            "goal": "Сказать, что где находится: there is / there are, предлоги.",
            "rules": ["a1-there-is", "a1-prepositions"],
            "words": ["house", "city", "school", "book", "water"],
            "steps": ["Прочитать правила there is/are и предлогов",
                      "Карточки: 5 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Описать свою комнату"],
        },
        {
            "id": "a1-07", "n": 7, "title": "Могу и хочу",
            "goal": "Говорить о возможности: can + начальная форма.",
            "rules": ["a1-can", "a1-pronouns"],
            "words": ["go", "come", "help", "see", "friend"],
            "steps": ["Прочитать правило can",
                      "Карточки: 5 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: I can…"],
        },
        {
            "id": "a1-08", "n": 8, "title": "Своё и чужое",
            "goal": "Сказать, чей предмет: my / her / 's.",
            "rules": ["a1-possessive", "a1-articles"],
            "words": ["family", "mother", "father", "friend", "car"],
            "steps": ["Прочитать правило притяжательных",
                      "Карточки: 5 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: my …'s …"],
        },
        {
            "id": "a1-09", "n": 9, "title": "Большой и маленький",
            "goal": "Описать предмет: прилагательное + существительное.",
            "rules": ["a1-plural", "a1-articles"],
            "words": ["big", "small", "new", "old", "good", "happy"],
            "steps": ["Повторить артикли и множественное число",
                      "Карточки: 6 прилагательных", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Описать два предмета"],
        },
        {
            "id": "a1-10", "n": 10, "title": "Вчера",
            "goal": "Рассказать о прошлом: was/were и вторая форма глагола.",
            "rules": ["a1-past-simple", "a1-pronouns"],
            "words": ["go", "come", "eat", "drink", "see", "work"],
            "steps": ["Прочитать правило Past Simple",
                      "Карточки: 6 слов", "Перевод RU → EN",
                      "Прочитать примеры вслух", "Составить своё: Yesterday I…"],
        },
    ]
}


def _today() -> str:
    return dt.date.today().isoformat()


def ensure_store(progress) -> dict:
    st = progress.data.setdefault("lessons", {})
    st.setdefault("done", {})
    st.setdefault("current", None)
    return st


def plan(level: str = "A1") -> list[dict]:
    return [dict(x, level=level) for x in PLANS.get(level, [])]


def levels() -> list[str]:
    return [lv for lv in PLANS if lv in cefr.available()]


def get(lid: str) -> dict | None:
    for lv, items in PLANS.items():
        for lesson in items:
            if lesson["id"] == lid:
                return dict(lesson, level=lv)
    return None


def words(lesson: dict) -> list[str]:
    return list(lesson.get("words") or [])


def done(progress, lid: str) -> bool:
    return lid in (ensure_store(progress).get("done") or {})


def unlocked(progress, lesson: dict) -> bool:
    n = int(lesson.get("n") or 1)
    if n <= 1:
        return True
    for other in PLANS.get(lesson.get("level") or "A1", []):
        if int(other.get("n") or 0) == n - 1:
            return done(progress, other["id"])
    return True


def complete(progress, lid: str) -> None:
    st = ensure_store(progress)
    st["done"][lid] = {"day": _today()}
    nxt = next_lesson(progress)
    st["current"] = nxt["id"] if nxt else None
    progress.save()


def uncomplete(progress, lid: str) -> None:
    st = ensure_store(progress)
    st["done"].pop(lid, None)
    st["current"] = lid
    progress.save()


def set_current(progress, lid: str | None) -> None:
    ensure_store(progress)["current"] = lid
    progress.save()


def next_lesson(progress, level: str | None = None) -> dict | None:
    """Первый открытый и ещё не пройденный урок (по порядку)."""
    for lesson in plan(level or "A1"):
        if not done(progress, lesson["id"]) and unlocked(progress, lesson):
            return lesson
    return None


def summary(progress, level: str = "A1") -> dict:
    items = plan(level)
    passed = sum(1 for x in items if done(progress, x["id"]))
    return {"total": len(items), "done": passed, "next": next_lesson(progress, level)}
