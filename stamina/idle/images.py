"""Картинки слайдшоу: Wikimedia Commons (без ключа) + дисковый кэш; запасной — фото скина."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "StarTypingDesktop/1.0 (idle-slideshow; https://github.com/Teslyar75/My_Stamina)"
TTL = 7 * 24 * 3600
ROOT = Path(__file__).resolve().parents[2]


def _cache_dir(skin: str) -> Path:
    from stamina.storage import DATA_DIR
    d = DATA_DIR / "idle_cache" / skin
    d.mkdir(parents=True, exist_ok=True)
    return d


def _strip(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def skin_fallback(skin: str) -> list[dict]:
    folder = ROOT / "docs" / "skins" / "images" / skin
    return [{"path": str(p), "author": "Star Typing", "license": "", "source": "skin", "title": skin}
            for p in sorted(folder.glob("bg*.jpg"))]


def fetch_wikimedia(categories: list[str], per_cat: int = 6, timeout: float = 10.0) -> list[dict]:
    out: list[dict] = []
    for cat in categories:
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "categorymembers",
            "gcmtitle": cat, "gcmtype": "file", "gcmlimit": str(per_cat * 3),
            "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": "1600",
        })
        try:
            req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — фиксированный https-хост
                data = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        n = 0
        for pg in ((data.get("query") or {}).get("pages") or {}).values():
            info = (pg.get("imageinfo") or [{}])[0]
            if info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            w, h = info.get("width") or 0, info.get("height") or 0
            if w < 1200 or w < h:
                continue
            meta = info.get("extmetadata") or {}
            lic = _strip((meta.get("LicenseShortName") or {}).get("value", ""))
            if not lic:
                continue
            out.append({"url": info.get("thumburl") or info.get("url"),
                        "author": _strip((meta.get("Artist") or {}).get("value", ""))[:80] or "Wikimedia Commons",
                        "license": lic, "source": "Wikimedia Commons",
                        "title": str(pg.get("title", "")).removeprefix("File:")})
            n += 1
            if n >= per_cat:
                break
    return out


def load_images(skin: str, cfg: dict, limit: int = 18) -> list[dict]:
    """Список картинок с локальными путями (скачивает недостающие). Вызывать в потоке."""
    d = _cache_dir(skin)
    idx = d / "index.json"
    items: list[dict] = []
    try:
        j = json.loads(idx.read_text(encoding="utf-8"))
        if time.time() - j.get("ts", 0) < TTL:
            items = [i for i in j.get("items", []) if Path(i.get("path", "")).is_file()]
    except (OSError, ValueError):
        pass
    if not items:
        for it in fetch_wikimedia(list(cfg.get("wikimedia") or []))[:limit]:
            p = d / (hashlib.sha1(it["url"].encode()).hexdigest()[:16] + ".jpg")
            if not p.is_file():
                try:
                    req = urllib.request.Request(it["url"], headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
                        p.write_bytes(r.read())
                except Exception:  # noqa: BLE001
                    continue
            it["path"] = str(p)
            items.append(it)
        if items:
            try:
                idx.write_text(json.dumps({"ts": time.time(), "items": items}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
    return items or skin_fallback(skin)
