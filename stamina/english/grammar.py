"""Справочник правил: data/grammar/<уровень>.json.

Правило привязано к уровню и имеет стабильный id (a1-to-be). Уроки ссылаются
на эти id, поэтому справочник и уроки не расходятся.
"""
from __future__ import annotations

import json

from . import paths

# порядок уровней — как в CEFR
LEVEL_ORDER = ["A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"]


def path(level: str):
    return paths.DATA_DIR / "grammar" / f"{level.lower().replace('.', '_')}.json"


def available() -> list[str]:
    return [lv for lv in LEVEL_ORDER if path(lv).exists()]


def load(level: str) -> dict | None:
    try:
        return json.loads(path(level).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def rules(level: str) -> list[dict]:
    data = load(level) or {}
    out = []
    for r in data.get("rules") or []:
        if not r.get("id") or not r.get("title"):
            continue
        r = dict(r)
        r.setdefault("level", level)
        r.setdefault("sections", [])
        out.append(r)
    return out


def find(rule_id: str) -> tuple[str, dict] | None:
    """Найти правило по id на любом загруженном уровне."""
    for lv in available():
        for r in rules(lv):
            if r["id"] == rule_id:
                return lv, r
    return None


def lesson_rules(rule_ids: list[str]) -> list[dict]:
    out = []
    for rid in rule_ids or []:
        found = find(rid)
        if found:
            out.append(found[1])
    return out


def count(level: str) -> int:
    return len(rules(level))
