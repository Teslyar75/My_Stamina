"""Уроки грамматики «Английского»: индекс 115 + 136 юнитов и загрузка по одному.

Контент — учебный конспект по порядку тем Essential Grammar in Use (красный Мёрфи,
115 юнитов, A1–B1) и English Grammar in Use (синий Мёрфи, 136 юнитов, B2).
Тексты написаны заново по-русски. Данные лежат рядом: lessons/index.json и
lessons/uNNN.json (один урок, 2–4 КБ). Страница грузит индекс и уроки в фоне:
никаких тяжёлых чтений в главном потоке Tk.

Внутри курса нумерация сквозная: красная книга — 1–115, синяя — 116–251.
Поле `unit` хранит номер юнита внутри книги (1–115 и 1–136): его и видит пилот.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DIR = Path(__file__).parent / "lessons"
INDEX_PATH = DIR / "index.json"
RED_UNITS = 115
BLUE_UNITS = 136
TOTAL_UNITS = RED_UNITS + BLUE_UNITS
LEVELS = ("a1", "a2", "b1", "b2")

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "`": "'"})
_SPACES = re.compile(r"\s+")


def lesson_path(n: int) -> Path:
    return DIR / f"u{int(n):03d}.json"


@lru_cache(maxsize=1)
def load_index() -> dict[str, Any]:
    """Индекс курса: модули и список юнитов. Читается один раз за запуск."""
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def modules() -> list[dict]:
    return list(load_index().get("modules") or [])


def units() -> list[dict]:
    return list(load_index().get("units") or [])


def unit_info(n: int) -> dict | None:
    return next((u for u in units() if int(u.get("n", 0)) == int(n)), None)


def units_of_module(module_id: str) -> list[dict]:
    return [u for u in units() if u.get("module") == module_id]


def by_level(level: str) -> list[dict]:
    level = (level or "").lower()
    return [u for u in units() if (u.get("level") or "").lower() == level]


def books() -> list[dict]:
    return list(load_index().get("books") or [])


def book_of(n: int) -> dict:
    """Книга, к которой относится юнит: `red` (A1–B1) или `blue` (B2)."""
    info = unit_info(n) or {}
    bid = info.get("book") or ("blue" if str(info.get("level", "")).lower() == "b2" else "red")
    return next((b for b in books() if b.get("id") == bid), {"id": bid, "units": 0, "levels": []})


def unit_number(n: int) -> int:
    """Номер юнита внутри книги — то, что видит пилот (1–115 или 1–136)."""
    info = unit_info(n) or {}
    return int(info.get("unit") or n)


def of_book(book_id: str) -> list[dict]:
    return [u for u in units() if (u.get("book") or "red") == book_id]


def lesson_exists(n: int) -> bool:
    return lesson_path(n).exists()


@lru_cache(maxsize=32)
def load_lesson(n: int) -> dict[str, Any]:
    """Один урок с диска. Кэш на 32 штуки: листание туда-обратно без чтений."""
    path = lesson_path(n)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["n"] = int(data.get("n") or n)
    return data


def neighbours(n: int) -> tuple[int | None, int | None]:
    """(предыдущий, следующий) юнит по порядку индекса."""
    nums = [int(u["n"]) for u in units()]
    try:
        i = nums.index(int(n))
    except ValueError:
        return None, None
    prev_n = nums[i - 1] if i > 0 else None
    next_n = nums[i + 1] if i + 1 < len(nums) else None
    return prev_n, next_n


def first_unit() -> int:
    u = units()
    return int(u[0]["n"]) if u else 1


def total() -> int:
    return len(units()) or TOTAL_UNITS


def available() -> int:
    """Сколько уроков уже написано (для честного «готово N из 115»)."""
    return sum(1 for u in units() if lesson_exists(int(u["n"])))


def normalize(text: str) -> str:
    """Сравнение ответов: регистр, лишние пробелы, апострофы, конечная точка."""
    s = (text or "").translate(_APOSTROPHES).strip().lower()
    s = _SPACES.sub(" ", s)
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)
    return s.rstrip(" .!?")


def answer_ok(given: str, variants) -> bool:
    """Ответ верен, если совпал с любым вариантом после normalize."""
    if isinstance(variants, str):
        variants = [variants]
    g = normalize(given)
    return bool(g) and any(g == normalize(v) for v in (variants or []))


def lesson_answers(ex: dict) -> list[str]:
    """Правильные варианты упражнения: у choice — текст верного пункта."""
    if ex.get("type") == "choice":
        try:
            return [str(ex["options"][int(ex.get("a", 0))])]
        except (KeyError, IndexError, TypeError, ValueError):
            return []
    a = ex.get("a")
    if isinstance(a, str):
        return [a]
    return [str(x) for x in (a or [])]
