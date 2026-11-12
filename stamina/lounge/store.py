"""Рекорды комнаты отдыха: у каждого пилота свои (%APPDATA%\\Stamina\\pilots\\<id>\\lounge.json).

Путь считается при каждом обращении от активного пилота (``pilots.active_dir()``), поэтому
смена пилота и ``pilots.reset_root`` сразу видят нужный файл.

До версии с пилотами рекорды лежали в общем ``%APPDATA%\\Stamina\\lounge.json`` и смешивались
у всех пилотов. По решению экипажа они сброшены: старый файл один раз переименовывается
в ``lounge.json.shared-old`` (не удаляется) и никому не отдаётся.
"""
from __future__ import annotations

import json
from pathlib import Path

LEGACY_NAME = "lounge.json"
LEGACY_RENAMED = "lounge.json.shared-old"


def _retire_shared() -> None:
    """Убрать старый общий файл рекордов из корня (идемпотентно, без удаления)."""
    from stamina import pilots
    if pilots.active() is None:      # без пилотов (режим «по-старому») корень и есть папка данных
        return
    root = Path(pilots.ROOT_DIR)
    old = root / LEGACY_NAME
    if not old.is_file():
        return
    dest = root / LEGACY_RENAMED
    n = 1
    while dest.exists():
        dest = root / f"{LEGACY_RENAMED}.{n}"
        n += 1
    try:
        old.rename(dest)
    except OSError:
        pass                          # занят — попробуем при следующем обращении; читать его всё равно не будем


def _path() -> Path:
    from stamina import pilots
    _retire_shared()
    return Path(pilots.active_dir()) / LEGACY_NAME


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
