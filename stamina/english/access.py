"""Доступ к уровням английского: капитан и прогрессивное открытие.

Капитан — владелец программы (для проверки): ему открыты все уровни CEFR, все
порции внутри уровня и весь пак глаголов. Остальные пилоты открывают уровни по
мере прохождения курса.

Кто капитан (см. stamina.pilots.is_captain): у записи пилота в pilots.json
role == "captain"; если явной роли нет ни у кого, капитаном считается пилот,
перенесённый из исходных данных владельца при первой миграции (migrated_from).

Правило открытия уровня: следующий уровень открывается, когда в предыдущем
пройдено не меньше cefr_unlock_pct процентов слов (настройка, по умолчанию 80).
Задел на будущее: настройка cefr_start_level — уровень, с которого ученик
начинает; он и все уровни до него открыты сразу. Интерфейса выбора пока нет.
"""
from __future__ import annotations

from typing import Callable, Iterable

UNLOCK_PCT = 80          # % пройденных слов предыдущего уровня
START_LEVEL = "A1"


def is_captain(progress=None) -> bool:
    """Капитан ли активный пилот. Без реестра пилотов — нет."""
    try:
        from stamina import pilots
        return bool(pilots.is_captain())
    except Exception:  # noqa: BLE001
        return False


def unlock_pct(progress) -> int:
    try:
        v = int((progress.settings or {}).get("cefr_unlock_pct", UNLOCK_PCT))
    except (AttributeError, TypeError, ValueError):
        v = UNLOCK_PCT
    return max(1, min(100, v))


def start_level(progress, levels: list[str]) -> str:
    """Хук «с какого уровня начать»: настройка cefr_start_level (UI позже)."""
    try:
        lv = (progress.settings or {}).get("cefr_start_level") or START_LEVEL
    except AttributeError:
        lv = START_LEVEL
    return lv if lv in levels else (levels[0] if levels else START_LEVEL)


def level_pct(slugs: Iterable[str], done: Callable[[str], bool]) -> int:
    s = list(slugs)
    if not s:
        return 0
    return int(100 * sum(1 for x in s if done(x)) / len(s))


def level_open(progress, level: str, levels: list[str],
               slugs_of: Callable[[str], list[str]], done: Callable[[str], bool]) -> bool:
    """levels — доступные уровни по порядку; slugs_of(level) — слова уровня."""
    if level not in levels:
        return False
    if is_captain(progress):
        return True
    i = levels.index(level)
    if i <= levels.index(start_level(progress, levels)):
        return True
    return level_pct(slugs_of(levels[i - 1]), done) >= unlock_pct(progress)


def level_need(progress, level: str, levels: list[str],
               slugs_of: Callable[[str], list[str]], done: Callable[[str], bool]) -> tuple[str, int, int]:
    """(предыдущий уровень, нужно %, сейчас %) — для подсказки у закрытого уровня."""
    i = levels.index(level) if level in levels else 0
    prev = levels[i - 1] if i > 0 else level
    return prev, unlock_pct(progress), level_pct(slugs_of(prev), done)
