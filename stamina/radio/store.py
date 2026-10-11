"""Настройки радиорубки пилота: избранное, громкость, последняя станция."""
from __future__ import annotations

import json
from pathlib import Path

from stamina.pilots import ROOT_DIR, active_dir

DEFAULT = {
    "favorites": [],          # list[station card]
    "last": None,             # station card | None
    "volume": 70,
    "autoplay": False,
    "duck_typing": False,     # приглушать при наборе
}


def _path() -> Path:
    base = active_dir()
    if base is None:
        return Path(ROOT_DIR) / "radio.json"
    return Path(base) / "radio.json"


def load() -> dict:
    p = _path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT)
    out = dict(DEFAULT)
    out.update({k: data[k] for k in DEFAULT if k in data})
    if not isinstance(out["favorites"], list):
        out["favorites"] = []
    out["volume"] = max(0, min(100, int(out.get("volume") or 70)))
    return out


def save(data: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def is_favorite(data: dict, uuid: str) -> bool:
    return any(f.get("uuid") == uuid for f in data.get("favorites") or [])


def toggle_favorite(data: dict, station: dict) -> bool:
    """True — добавлено, False — убрано."""
    uuid = station.get("uuid") or ""
    favs = list(data.get("favorites") or [])
    for i, f in enumerate(favs):
        if f.get("uuid") == uuid:
            favs.pop(i)
            data["favorites"] = favs
            save(data)
            return False
    favs.insert(0, {k: station.get(k) for k in
                    ("uuid", "name", "url", "favicon", "country", "tags", "bitrate", "codec")})
    data["favorites"] = favs[:80]
    save(data)
    return True
