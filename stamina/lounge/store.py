"""Рекорды комнаты отдыха (%APPDATA%\\Stamina\\lounge.json)."""
from __future__ import annotations

import json
from pathlib import Path


def _path() -> Path:
    from stamina.pilots import ROOT_DIR
    return Path(ROOT_DIR) / "lounge.json"


def load() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def best(game: str) -> int:
    return int(load().get("best", {}).get(game, 0) or 0)


def set_best(game: str, score: int) -> int:
    data = load()
    bests = data.setdefault("best", {})
    prev = int(bests.get(game, 0) or 0)
    if score > prev:
        bests[game] = int(score)
        save(data)
        return int(score)
    return prev
