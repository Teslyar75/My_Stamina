"""Universal CEFR unlock rules for all languages."""
from __future__ import annotations

from typing import Callable, Iterable



UNLOCK_PCT = 80
START_LEVEL = "A1"


def is_captain() -> bool:
    try:
        from stamina import pilots
        return bool(pilots.is_captain())
    except Exception:
        return False


def unlock_pct(progress) -> int:
    try:
        v = int((progress.settings or {}).get("cefr_unlock_pct", UNLOCK_PCT))
    except (AttributeError, TypeError, ValueError):
        v = UNLOCK_PCT
    return max(1, min(100, v))


def start_level(progress, levels: list[str]) -> str:
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
    if level not in levels:
        return False
    if is_captain():
        return True
    i = levels.index(level)
    if i == 0:
        return True
    return level_pct(slugs_of(levels[i - 1]), done) >= unlock_pct(progress)


def cross_pair_unlocked(pilot_dir, l1: str, l2: str) -> bool:
    if is_captain():
        return True
    l1_progress_file = pilot_dir / f"lang_{l1}.json"
    if not l1_progress_file.exists():
        return False
    try:
        import json
        data = json.loads(l1_progress_file.read_text(encoding="utf-8"))
        xp_total = data.get("xp", {}).get("total", 0)
        return xp_total >= 1500
    except Exception:
        return False