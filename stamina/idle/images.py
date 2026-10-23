"""Картинки слайдшоу: Wikimedia Commons (без ключа) + дисковый кэш; запасной — фото скина."""

from __future__ import annotations

import hashlib
import json
import random
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


ASSETS = ROOT / "stamina" / "assets"


def _local_credits(skin: str) -> list[dict]:
    """Офлайн-набор: stamina/assets/idle_photos/<skin>/credits.json (пути — от stamina/assets)."""
    try:
        rows = json.loads((ASSETS / "idle_photos" / skin / "credits.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        p = ASSETS / str(r.get("file", ""))
        if r.get("file") and p.is_file():
            out.append({"path": str(p), "author": _strip(str(r.get("author", ""))),
                        "license": str(r.get("license", "")), "source": "skin",
                        "title": str(r.get("title", skin))})
    return out


def skin_fallback(skin: str) -> list[dict]:
    folder = ROOT / "docs" / "skins" / "images" / skin
    own = [{"path": str(p), "author": "Star Typing", "license": "", "source": "skin", "title": skin}
           for p in sorted(folder.glob("bg*.jpg"))]
    return own + _local_credits(skin)


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


GIF_MAX_BYTES = 6 * 1024 * 1024
POOL_MAX = 90
FRESH_TOPICS = 3


def _api(params: dict, timeout: float) -> dict:
    base = {"action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime", "iiurlwidth": "1600"}
    q = urllib.parse.urlencode({**base, **params})
    req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — фиксированный https-хост
        return json.loads(r.read().decode("utf-8"))


def _item(pg: dict, *, gif: bool = False) -> dict | None:
    info = (pg.get("imageinfo") or [{}])[0]
    mime = info.get("mime")
    w, h = info.get("width") or 0, info.get("height") or 0
    if gif:
        if mime != "image/gif" or (info.get("size") or 0) > GIF_MAX_BYTES or w < 480:
            return None
        url = info.get("url")  # у GIF превью неанимированное — берём оригинал
    else:
        if mime not in ("image/jpeg", "image/png") or w < 1200 or w < h:
            return None
        url = info.get("thumburl") or info.get("url")
    meta = info.get("extmetadata") or {}
    lic = _strip((meta.get("LicenseShortName") or {}).get("value", ""))
    if not lic or not url:
        return None
    return {"url": url, "author": _strip((meta.get("Artist") or {}).get("value", ""))[:80] or "Wikimedia Commons",
            "license": lic, "source": "Wikimedia Commons",
            "title": str(pg.get("title", "")).removeprefix("File:")}


def fetch_topic(topic: str, n: int, timeout: float = 10.0, rng: random.Random | None = None) -> list[dict]:
    """Поиск по Commons: случайная страница выдачи, n случайных подходящих снимков."""
    rng = rng or random
    try:
        data = _api({"generator": "search", "gsrsearch": f"filetype:bitmap {topic}", "gsrnamespace": "6",
                     "gsrlimit": "30", "gsroffset": str(rng.choice((0, 0, 10, 20)))}, timeout)
    except Exception:  # noqa: BLE001
        return []
    found = [it for pg in ((data.get("query") or {}).get("pages") or {}).values() if (it := _item(pg))]
    rng.shuffle(found)
    for it in found[:n]:
        it["topic"] = topic
    return found[:n]


def fetch_gifs(titles: list[str], timeout: float = 10.0) -> list[dict]:
    if not titles:
        return []
    try:
        data = _api({"titles": "|".join(titles)}, timeout)
    except Exception:  # noqa: BLE001
        return []
    out = [it for pg in ((data.get("query") or {}).get("pages") or {}).values() if (it := _item(pg, gif=True))]
    for it in out:
        it["topic"] = "gif"
    return out


def plan_topics(cfg: dict) -> list[tuple[str, int]]:
    """Темы и сколько снимков брать: поровну, «минорные» (автобусы) — по одному."""
    per = int(cfg.get("per_topic") or 3)
    minor = set(cfg.get("minor") or [])
    topics = list(cfg.get("topics") or [])
    return [(tp, 1 if tp in minor else per) for tp in topics]


def _download(it: dict, d: Path) -> bool:
    ext = ".gif" if it.get("topic") == "gif" else ".jpg"
    p = d / (hashlib.sha1(it["url"].encode()).hexdigest()[:16] + ext)
    if not p.is_file():
        try:
            req = urllib.request.Request(it["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
                data = r.read(GIF_MAX_BYTES + 1)
            if len(data) > GIF_MAX_BYTES:
                return False
            p.write_bytes(data)
        except Exception:  # noqa: BLE001
            return False
    it["path"] = str(p)
    return True


def _read_index(d: Path) -> tuple[float, list[dict]]:
    try:
        j = json.loads((d / "index.json").read_text(encoding="utf-8"))
        return float(j.get("ts", 0)), [i for i in j.get("items", []) if Path(i.get("path", "")).is_file()]
    except (OSError, ValueError):
        return 0.0, []


def _write_index(d: Path, items: list[dict]) -> None:
    try:
        (d / "index.json").write_text(json.dumps({"ts": time.time(), "items": items}, ensure_ascii=False),
                                      encoding="utf-8")
    except OSError:
        pass


def merge_pool(cached: list[dict], fresh: list[dict], cap: int = POOL_MAX) -> list[dict]:
    """Свежие + кэш без дублей по url; при переполнении выкидываем самые старые из кэша."""
    seen, out = set(), []
    for it in fresh + cached:
        key = it.get("url") or it.get("path")
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:cap]


def load_images(skin: str, cfg: dict, limit: int = POOL_MAX, rng: random.Random | None = None,
                on_add=None) -> list[dict]:
    """Пул картинок с локальными путями. Вызывать в потоке.

    Есть кэш — сразу отдаём его (on_add) и дотягиваем пару свежих тем; кэша нет — все темы поровну,
    в случайном порядке, каждую порцию сразу отдаём в on_add. Без сети и кэша — фото скина.
    """
    rng = rng or random
    d = _cache_dir(skin)
    ts, cached = _read_index(d)
    if cached and on_add:
        on_add(list(cached))
    local: list[dict] | None = None
    if not cached and on_add:  # первый показ без кэша: сразу офлайн-набор скина, пока качается сеть
        local = skin_fallback(skin)
        if local:
            on_add(list(local))
    plan = plan_topics(cfg)
    rng.shuffle(plan)
    full = not (cached and time.time() - ts < TTL)
    if not full:
        plan = plan[:FRESH_TOPICS]
    fresh: list[dict] = []

    def take(batch: list[dict]) -> None:
        got = [it for it in batch if _download(it, d)]
        if got:
            fresh.extend(got)
            if on_add:
                on_add(got)

    if not plan and cfg.get("wikimedia"):  # старый формат темы
        take(fetch_wikimedia(list(cfg.get("wikimedia") or [])))
    misses = 0
    for tp, n in plan:
        before = len(fresh)
        take(fetch_topic(tp, n, rng=rng))
        misses = 0 if len(fresh) > before else misses + 1
        if misses >= 3 and not fresh:  # похоже, нет сети — не ждём таймаутов по всем темам
            break
    if full:
        take(fetch_gifs(list(cfg.get("gifs") or [])))
    items = merge_pool(cached, fresh, limit)
    if fresh:
        _write_index(d, items)
    if not items:
        if local is None:
            items = skin_fallback(skin)
            if on_add:
                on_add(items)
        else:
            items = local
    return items


class ShuffleBag:
    """Случайный порядок без повторов, пока пул не исчерпан; соседние кадры — по возможности разных тем.

    Новые картинки можно подкладывать на ходу (add) — они попадут в текущий круг.
    """

    def __init__(self, items: list[dict], rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.items = list(items)
        self.bag: list[int] = []
        self.last: dict | None = None

    def add(self, items: list[dict]) -> None:
        known = {i.get("path") for i in self.items}
        for it in items:
            if it.get("path") not in known:
                self.items.append(it)
                self.bag.append(len(self.items) - 1)
        self.rng.shuffle(self.bag)

    def _refill(self) -> None:
        self.bag = list(range(len(self.items)))
        self.rng.shuffle(self.bag)

    def next(self) -> dict | None:
        if not self.items:
            return None
        if not self.bag:
            self._refill()
        last_t = (self.last or {}).get("topic")
        pick = 0
        for k, i in enumerate(self.bag):
            it = self.items[i]
            if it is not self.last and (last_t is None or it.get("topic") != last_t):
                pick = k
                break
        else:
            for k, i in enumerate(self.bag):
                if self.items[i] is not self.last:
                    pick = k
                    break
        self.last = self.items[self.bag.pop(pick)]
        return self.last
