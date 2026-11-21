"""Загрузка текстов справки Lounge / Орион из JSON (заглушки, потом подставят авторы)."""
from __future__ import annotations

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent

# game_id в GameShell → имя файла без .json
FILE_BY_GAME = {
    "docker_trainer": "docker_trainer",
    "vim_trainer": "vim_trainer",
    "trainer": "terraformer",
    "terraformer": "terraformer",
    "orion": "orion",
    "bridge": "orion",
    "snake": "snake",
    "tetris": "tetris",
    "breakout": "breakout",
}

_cache: dict[str, dict] = {}


def _path(game: str) -> Path:
    name = FILE_BY_GAME.get(game, game)
    return DIR / f"{name}.json"


def load_pack(game: str) -> dict:
    key = FILE_BY_GAME.get(game, game)
    if key not in _cache:
        path = DIR / f"{key}.json"
        if not path.is_file():
            _cache[key] = {}
        else:
            _cache[key] = json.loads(path.read_text(encoding="utf-8"))
    return _cache[key]


def clear_cache() -> None:
    _cache.clear()


def load_overview(game: str) -> dict | None:
    pack = load_pack(game)
    ov = pack.get("overview")
    return dict(ov) if isinstance(ov, dict) else None


def load_help(game: str, level_id: str | None) -> dict | None:
    """Справка уровня; если level_id пуст или не найден — обзор."""
    pack = load_pack(game)
    if not pack:
        return None
    if level_id and level_id != "overview":
        for item in pack.get("levels") or []:
            if isinstance(item, dict) and item.get("id") == level_id:
                return dict(item)
    ov = pack.get("overview")
    return dict(ov) if isinstance(ov, dict) else None


def level_ids(game: str) -> list[str]:
    pack = load_pack(game)
    return [item["id"] for item in (pack.get("levels") or []) if isinstance(item, dict) and item.get("id")]
