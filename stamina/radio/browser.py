"""Клиент radio-browser.info: поиск станций + локальный кэш."""
from __future__ import annotations

import json
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from stamina import __version__
from stamina.pilots import ROOT_DIR

UA = f"StarTyping/{__version__} (radio-cabin; +https://github.com/Teslyar75/My_Stamina)"
CACHE = Path(ROOT_DIR) / "radio_cache.json"
CACHE_TTL = 6 * 3600  # 6 ч
KNOWN = (
    "de1.api.radio-browser.info",
    "de2.api.radio-browser.info",
    "nl1.api.radio-browser.info",
    "at1.api.radio-browser.info",
)


def _servers() -> list[str]:
    hosts: list[str] = []
    try:
        infos = socket.getaddrinfo("all.api.radio-browser.info", 443, type=socket.SOCK_STREAM)
        seen = set()
        for info in infos:
            ip = info[4][0]
            if ip in seen:
                continue
            seen.add(ip)
            try:
                name = socket.getnameinfo((ip, 0), 0)[0]
                if name and name not in hosts:
                    hosts.append(name)
            except OSError:
                pass
    except OSError:
        pass
    for h in KNOWN:
        if h not in hosts:
            hosts.append(h)
    random.shuffle(hosts)
    return hosts or list(KNOWN)


def _get_json(path: str, params: dict | None = None, timeout: float = 12.0):
    q = ("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})) if params else ""
    last_err = None
    for host in _servers():
        url = f"https://{host}{path}{q}"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last_err = e
            continue
    raise ConnectionError(str(last_err or "no server"))


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(data: dict) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE)
    except OSError:
        pass


def station_card(raw: dict) -> dict:
    tags = (raw.get("tags") or "").replace(",", " · ")
    return {
        "uuid": raw.get("stationuuid") or "",
        "name": (raw.get("name") or "—").strip() or "—",
        "url": raw.get("url_resolved") or raw.get("url") or "",
        "favicon": raw.get("favicon") or "",
        "country": raw.get("country") or raw.get("countrycode") or "",
        "countrycode": (raw.get("countrycode") or "")[:2].upper(),
        "language": raw.get("language") or "",
        "tags": tags[:80],
        "bitrate": int(raw.get("bitrate") or 0),
        "votes": int(raw.get("votes") or raw.get("clickcount") or 0),
        "codec": raw.get("codec") or "",
    }


def top_stations(limit: int = 60) -> tuple[list[dict], str | None]:
    """Популярные станции; при ошибке — кэш или сообщение."""
    cache = _load_cache()
    try:
        data = _get_json("/json/stations/topvote/" + str(limit))
        cards = [station_card(r) for r in data if r.get("url") or r.get("url_resolved")]
        cache["top"] = {"ts": time.time(), "items": cards}
        _save_cache(cache)
        return cards, None
    except (ConnectionError, OSError, ValueError) as e:
        items = (cache.get("top") or {}).get("items") or []
        if items:
            return items, "cache"
        return [], str(e)


def search_stations(*, name: str = "", country: str = "", language: str = "",
                    tag: str = "", limit: int = 80) -> tuple[list[dict], str | None]:
    params = {
        "name": name.strip(),
        "countrycode": country.strip().upper() if len(country.strip()) == 2 else "",
        "country": country.strip() if len(country.strip()) != 2 else "",
        "language": language.strip(),
        "tag": tag.strip(),
        "order": "clickcount",
        "reverse": "true",
        "limit": str(limit),
        "hidebroken": "true",
    }
    try:
        data = _get_json("/json/stations/search", params)
        return [station_card(r) for r in data if r.get("url") or r.get("url_resolved")], None
    except (ConnectionError, OSError, ValueError) as e:
        return [], str(e)


def countries() -> list[tuple[str, str]]:
    cache = _load_cache()
    block = cache.get("countries") or {}
    if block.get("ts") and time.time() - block["ts"] < CACHE_TTL and block.get("items"):
        return [tuple(x) for x in block["items"]]
    try:
        data = _get_json("/json/countries", {"order": "stationcount", "reverse": "true"})
        items = [(d.get("name") or "", d.get("iso_3166_1") or "") for d in data if d.get("name")]
        items = [(n, c) for n, c in items if c][:120]
        cache["countries"] = {"ts": time.time(), "items": items}
        _save_cache(cache)
        return items
    except (ConnectionError, OSError, ValueError):
        return [tuple(x) for x in (block.get("items") or [])]


def languages() -> list[str]:
    cache = _load_cache()
    block = cache.get("languages") or {}
    if block.get("ts") and time.time() - block["ts"] < CACHE_TTL and block.get("items"):
        return list(block["items"])
    try:
        data = _get_json("/json/languages", {"order": "stationcount", "reverse": "true", "limit": "80"})
        items = [d.get("name") for d in data if d.get("name")]
        cache["languages"] = {"ts": time.time(), "items": items}
        _save_cache(cache)
        return items
    except (ConnectionError, OSError, ValueError):
        return list(block.get("items") or [])


def tags() -> list[str]:
    cache = _load_cache()
    block = cache.get("tags") or {}
    if block.get("ts") and time.time() - block["ts"] < CACHE_TTL and block.get("items"):
        return list(block["items"])
    try:
        data = _get_json("/json/tags", {"order": "stationcount", "reverse": "true", "limit": "100"})
        items = [d.get("name") for d in data if d.get("name") and (d.get("stationcount") or 0) > 5]
        cache["tags"] = {"ts": time.time(), "items": items}
        _save_cache(cache)
        return items
    except (ConnectionError, OSError, ValueError):
        return list(block.get("items") or [])


def register_click(uuid: str) -> str | None:
    """Сообщить клик (популярность) и получить актуальный URL потока."""
    if not uuid:
        return None
    try:
        data = _get_json(f"/json/url/{uuid}")
        if isinstance(data, dict):
            return data.get("url") or None
    except (ConnectionError, OSError, ValueError):
        pass
    return None


def skin_stations(cfg: dict, limit: int = 40) -> tuple[list[dict], str | None]:
    """Волны скина (theme.radio): закреплённые по имени — первыми, затем по жанрам и стране."""
    seen: set[str] = set()
    out: list[dict] = []
    err: str | None = None
    country = str(cfg.get("country") or "")
    for tag in list(cfg.get("tags") or [])[:4]:
        items, e = search_stations(tag=tag, country=country, limit=25)
        err = err or e
        for s in items:
            key = s.get("uuid") or s.get("url")
            if key and key not in seen:
                seen.add(key)
                out.append(s)
    pinned = [p.lower() for p in cfg.get("pinned") or []]

    def rank(s: dict) -> int:
        n = str(s.get("name", "")).lower()
        return next((i for i, p in enumerate(pinned) if p in n), len(pinned))

    out.sort(key=rank)
    return out[:limit], (err if not out else None)
