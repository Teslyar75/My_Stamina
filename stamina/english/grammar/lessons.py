"""Уроки грамматики «Английского»: индекс 115 юнитов и загрузка по одному.

Контент — учебный конспект по порядку тем Essential Grammar in Use (красный Мёрфи),
написанный заново по-русски. Данные лежат рядом: lessons/index.json (лёгкий, 22 КБ)
и lessons/uNNN.json (один урок, 2–4 КБ). Страница грузит индекс и уроки в фоне:
никаких тяжёлых чтений в главном потоке Tk.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DIR = Path(__file__).parent / "lessons"
INDEX_PATH = DIR / "index.json"
TOTAL_UNITS = 115
LEVELS = ("a1", "a2", "b1")

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
