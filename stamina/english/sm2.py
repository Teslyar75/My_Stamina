"""Алгоритм интервального повторения SM-2 (SPEC §6)."""
from __future__ import annotations

import datetime as dt


def today() -> str:
    return dt.date.today().isoformat()


def add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def new_card(slug: str) -> dict:
    return {"slug": slug, "ef": 2.5, "interval": 0, "reps": 0, "due": today(), "last": None,
            "lapses": 0, "created": today()}


def next_state(card: dict, q: int, day: str | None = None) -> dict:
    """Новое состояние карточки после ответа с качеством q (0–5)."""
    day = day or today()
    c = dict(card)
    first_today = c.get("last") != day
    if first_today:
        ef = c["ef"] + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        c["ef"] = max(1.3, round(ef, 3))
    if q < 3:
        c["reps"] = 0
        c["interval"] = 1
        if first_today:
            c["lapses"] = c.get("lapses", 0) + 1
    else:
        if c["reps"] == 0:
            c["interval"] = 1
        elif c["reps"] == 1:
            c["interval"] = 6
        else:
            c["interval"] = max(1, round(c["interval"] * c["ef"]))
        c["reps"] += 1
    c["due"] = add_days(day, c["interval"])
    c["last"] = day
    return c


def preview(card: dict, q: int) -> str:
    """Подпись интервала для кнопки оценки."""
    if q < 3:
        return "<10 мин"
    n = next_state(card, q)["interval"]
    return f"{n} дн"
