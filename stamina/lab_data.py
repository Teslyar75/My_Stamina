"""«Лаборатория»: граф знаний пилота из его реальных файлов (только чтение).

Узел — то, что пилот действительно освоил: английское слово, неправильный глагол
(и его формы), книга, упражнение/рубеж скорочтения, миссия/рубеж слепой печати.
Рёбра — реальные связи: глагол↔формы, слово↔книга (слово встречалось в
отработанных предложениях книги), цепочки рубежей. Созвездие (``group``) — набор
CEFR и тема слова, книга, цепочка рубежей.

Модуль без Tk и без записи: файлы пилота читаются через ``pilots.read_json``.
Единственный собственный файл Лаборатории (``lab.json``, кто из звёзд уже
показан) пишет экран, а не этот модуль.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from pathlib import Path

from stamina import pilots

DAY = 86400.0
FLOOR = 0.28            # знание не гаснет ниже этой яркости — его не отнимают
SKILLS = ("en", "read", "type")
KNOWN_INTERVAL = 21     # SM-2: интервал ≥ 21 дня — слово выучено (как в pilot_stats)
VERB_OK = 80            # = speech_std.ITEM_OK
CPM_STEPS = (100, 150, 200, 250, 300, 350, 400, 500)
ACC_STEPS = (90, 95, 97, 98, 99)
WPM_STEPS = (150, 200, 250, 300, 400, 500, 600, 800)
BOOK_WORD_EDGES = 40    # не больше рёбер слово↔книга на одну книгу

_SETS_DIR = Path(__file__).resolve().parent / "english" / "data" / "sets"
_VERBS_PATH = Path(__file__).resolve().parent / "english" / "data" / "verbs" / "irregular.json"
_cefr_cache: dict[str, tuple[str, str, str]] | None = None
_verbs_cache: dict[str, dict] | None = None


# -- справочники приложения (не данные пилота) ----------------------------------
def cefr_index() -> dict[str, tuple[str, str, str]]:
    """slug → (уровень, тема ru, тема en) по data/sets/cefr_*.json; кэш на процесс."""
    global _cefr_cache
    if _cefr_cache is None:
        idx: dict[str, tuple[str, str, str]] = {}
        for p in sorted(_SETS_DIR.glob("cefr_*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            lvl = str(d.get("level") or "")
            for w in d.get("words") or []:
                if isinstance(w, dict) and w.get("slug") and lvl:
                    idx.setdefault(w["slug"], (lvl, w.get("topic") or "", w.get("topic_en") or ""))
        _cefr_cache = idx
    return _cefr_cache


def irregular_verbs() -> dict[str, dict]:
    global _verbs_cache
    if _verbs_cache is None:
        try:
            d = json.loads(_VERBS_PATH.read_text(encoding="utf-8"))
            _verbs_cache = {v["lemma"]: v for v in d.get("verbs") or [] if isinstance(v, dict) and v.get("lemma")}
        except (OSError, ValueError, KeyError):
            _verbs_cache = {}
    return _verbs_cache


# -- свежесть и «существо» ----------------------------------------------------------
def _day_ts(day: str | None) -> float | None:
    if not day or not isinstance(day, str):
        return None
    try:
        d = dt.date.fromisoformat(day[:10])
    except ValueError:
        return None
    return time.mktime(d.timetuple()) + 12 * 3600


def stability_days(strength: float) -> float:
    """Чем крепче знание, тем медленнее оно тускнеет: 3 дня … ~60 дней."""
    return 3.0 * (1.0 + max(0.0, strength)) ** 1.3


def freshness(last: float | None, strength: float, now: float) -> float:
    """Яркость 0..1: FLOOR + (1-FLOOR)·exp(-Δt/S). Нет даты — середина шкалы."""
    if last is None:
        return 0.55
    days = max(0.0, (now - last) / DAY)
    return FLOOR + (1 - FLOOR) * math.exp(-days / stability_days(strength))


def entity_state(active_days: set[str], total_stars: int, now: float) -> dict:
    """Существо в центре: vitality — регулярность за 14 дней, quiet — дней без практики."""
    today = dt.date.fromtimestamp(now)
    recent = sum(1 for i in range(14) if (today - dt.timedelta(days=i)).isoformat() in active_days)
    quiet = 0
    while quiet < 365 and (today - dt.timedelta(days=quiet)).isoformat() not in active_days:
        quiet += 1
    if not active_days:
        quiet = -1
    vitality = recent / 14.0
    if quiet > 2:
        vitality *= 0.5 ** ((quiet - 2) / 4)     # после перерыва тише, но не исчезает
    return {"vitality": round(max(0.08, min(1.0, vitality)), 3), "quiet_days": quiet,
            "recent_days": recent, "growth": round(math.log1p(total_stars), 3)}


# -- граф ---------------------------------------------------------------------------
class Graph:
    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[tuple[int, int]] = []
        self.active_days: set[str] = set()
        self.gaps: list[str] = []
        self.demo = False
        self._ix: dict[str, int] = {}

    def add(self, nid: str, kind: str, skill: str, label: str, group: str, *, last: float | None = None,
            strength: float = 0.0, detail: str = "") -> int:
        if nid in self._ix:
            return self._ix[nid]
        self._ix[nid] = len(self.nodes)
        self.nodes.append({"id": nid, "kind": kind, "skill": skill, "label": label, "group": group,
                           "last": last, "strength": float(strength), "detail": detail})
        return self._ix[nid]

    def link(self, a: str, b: str) -> None:
        ia, ib = self._ix.get(a), self._ix.get(b)
        if ia is not None and ib is not None and ia != ib:
            self.edges.append((ia, ib))

    def index(self, nid: str) -> int | None:
        return self._ix.get(nid)

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in SKILLS}
        for n in self.nodes:
            out[n["skill"]] = out.get(n["skill"], 0) + 1
        return out

    def entity(self, now: float | None = None) -> dict:
        return entity_state(self.active_days, len(self.nodes), time.time() if now is None else now)


def _lang() -> str:
    try:
        from stamina.i18n import language
        return language()
    except Exception:  # noqa: BLE001
        return "ru"


def _qlast(rec: dict | None) -> float | None:
    days = [v[1] for v in ((rec or {}).get("slots") or {}).values() if isinstance(v, (list, tuple)) and len(v) > 1]
    return _day_ts(max(days)) if days else None


def _qcomplete(rec: dict | None) -> bool:
    if not isinstance(rec, dict):
        return False
    goal = rec.get("goal") or 20
    return len(rec.get("slots") or {}) >= max(1, int(goal))


_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def _english(g: Graph, eng: dict, lib: dict) -> None:
    words = eng.get("words") or {}
    cards = eng.get("cards") or {}
    quality = eng.get("quality") or {}
    learned: dict[str, tuple[float | None, float]] = {}
    for slug in set(words) | set(cards) | {k for k in quality if ":" not in k}:
        w = words.get(slug) if isinstance(words.get(slug), dict) else {}
        c = cards.get(slug) if isinstance(cards.get(slug), dict) else {}
        q = quality.get(slug)
        if not (w.get("known") or int(c.get("interval", 0) or 0) >= KNOWN_INTERVAL or _qcomplete(q)):
            continue
        lasts = [x for x in (_day_ts(c.get("last")), _qlast(q), _day_ts(w.get("known_at"))) if x]
        strength = int(c.get("reps", 0) or 0) + len((q or {}).get("slots") or {}) / 5
        if w.get("known") and not c:
            strength = max(strength, 3)     # «уже знаю» — отмечено пилотом
        learned[slug] = (max(lasts) if lasts else None, strength)
    idx = cefr_index()
    for slug, (last, strength) in sorted(learned.items()):
        lvl, topic, topic_en = idx.get(slug, ("", "", ""))
        group = f"cefr:{lvl}:{topic_en or topic}" if lvl else "en:other"
        detail = f"{lvl} · {topic if _lang() == 'ru' else (topic_en or topic)}" if lvl else ""
        g.add("w:" + slug, "word", "en", slug, group, last=last, strength=strength, detail=detail)
    # неправильные глаголы и их формы
    verbs = irregular_verbs()
    passed: dict[str, int] = {}
    for key, score in (eng.get("verb_scores") or {}).items():
        slug = str(key).split(":")[0]
        if isinstance(score, (int, float)) and score >= VERB_OK:
            passed[slug] = passed.get(slug, 0) + 1
    for k, rec in quality.items():
        if k.startswith("verb:") and _qcomplete(rec):
            passed.setdefault(k[5:], 1)
    for slug in sorted(passed):
        v = verbs.get(slug)
        if v is None:
            continue
        last = _qlast(quality.get("verb:" + slug))
        n = passed[slug]
        g.add("v:" + slug, "verb", "en", slug, "verbs", last=last, strength=n,
              detail=f"{v.get('v2', '')} · {v.get('v3', '')}")
        for form in ("v2", "v3"):
            f = str(v.get(form) or "")
            if f and f != slug:
                g.add(f"vf:{slug}:{form}", "form", "en", f, "verbs", last=last, strength=n, detail=slug)
                g.link("v:" + slug, f"vf:{slug}:{form}")
    # слово ↔ книга: слово из выученных встречалось в отработанных предложениях книги
    bs = eng.get("book_sentences") or {}
    bcards = bs.get("cards") or {}
    for tid, book in (bs.get("books") or {}).items():
        if not isinstance(book, dict):
            continue
        practised = [s for s in book.get("sentences") or []
                     if isinstance(s, dict) and int((bcards.get(s.get("id")) or {}).get("reps", 0) or 0) > 0]
        if not practised:
            continue
        lasts = [_day_ts((bcards.get(s.get("id")) or {}).get("last")) for s in practised]
        lasts = [x for x in lasts if x]
        bid = "b:" + str(tid)
        g.add(bid, "book", "read", book.get("title") or str(tid), "book:" + str(tid),
              last=max(lasts) if lasts else None, strength=len(practised) / 5, detail=book.get("author") or "")
        seen = 0
        for s in practised:
            for tok in _WORD_RE.findall(str(s.get("en", "")).lower()):
                if tok in learned and seen < BOOK_WORD_EDGES:
                    g.link("w:" + tok, bid)
                    seen += 1


def _reading(g: Graph, sr: dict, lib: dict) -> None:
    sess = [s for s in sr.get("sessions") or [] if isinstance(s, dict)]
    titles = {str(t.get("title") or ""): t for t in lib.get("texts") or [] if isinstance(t, dict)}
    by_title: dict[str, list[dict]] = {}
    for s in sess:
        by_title.setdefault(str(s.get("title") or ""), []).append(s)
    for title, rows in by_title.items():
        meta = titles.get(title)
        if meta is None:           # книгу удалили или это вставленный текст — не выдумываем
            continue
        bid = "b:" + str(meta.get("id"))
        words = sum(int(r.get("words", 0) or 0) for r in rows)
        idx = g.add(bid, "book", "read", title, "book:" + str(meta.get("id")),
                    last=max(float(r.get("ts", 0) or 0) for r in rows) or None,
                    strength=words / 2000, detail=meta.get("author") or "")
        n = g.nodes[idx]
        n["last"] = max(n["last"] or 0, max(float(r.get("ts", 0) or 0) for r in rows)) or None
    prev = None
    for thr in WPM_STEPS:
        hit = [s for s in sess if (s.get("eff_wpm") or 0) >= thr]
        if not hit:
            break
        nid = f"sr:wpm:{thr}"
        g.add(nid, "milestone", "read", f"{thr}", "sr:speed", last=max(float(s.get("ts", 0) or 0) for s in hit),
              strength=len(hit), detail="eff_wpm")
        if prev:
            g.link(prev, nid)
        prev = nid
    for ex, variants in (sr.get("exercises") or {}).items():
        if not isinstance(variants, dict):
            continue
        runs = [r for rec in variants.values() if isinstance(rec, dict) for r in rec.get("runs") or []
                if isinstance(r, dict)]
        if runs:
            g.add(f"sr:ex:{ex}", "exercise", "read", str(ex), "sr:exercises",
                  last=max(float(r.get("ts", 0) or 0) for r in runs) or None, strength=len(runs) / 3)
    for day in sr.get("days") or []:
        g.active_days.add(str(day))


def _typing(g: Graph, stats: dict) -> None:
    runs = [r for r in stats.get("runs") or [] if isinstance(r, dict) and (r.get("chars", 0) or 0) >= 30]
    for r in runs:
        if r.get("ts"):
            g.active_days.add(time.strftime("%Y-%m-%d", time.localtime(float(r["ts"]))))
    for kind, steps, key in (("cpm", CPM_STEPS, "cpm"), ("acc", ACC_STEPS, "acc")):
        prev = None
        for thr in steps:
            hit = [r for r in runs if (r.get(key) or 0) >= thr]
            if not hit:
                break
            nid = f"ty:{kind}:{thr}"
            g.add(nid, "milestone", "type", f"{thr}{' %' if kind == 'acc' else ''}", f"type:{kind}",
                  last=max(float(r.get("ts", 0) or 0) for r in hit) or None, strength=len(hit) / 2, detail=kind)
            if prev:
                g.link(prev, nid)
            prev = nid
    missions = stats.get("missions") or {}
    last_by_m: dict[str, float] = {}
    for r in runs:
        if r.get("mission"):
            last_by_m[r["mission"]] = max(last_by_m.get(r["mission"], 0.0), float(r.get("ts", 0) or 0))
    chains: dict[str, list[tuple[int, str]]] = {}
    for mid, rec in missions.items():
        if not isinstance(rec, dict) or int(rec.get("stars", 0) or 0) <= 0:
            continue
        lang, _, num = str(mid).rpartition("-")
        nid = "ty:m:" + mid
        g.add(nid, "mission", "type", mid, f"type:missions:{lang}", last=last_by_m.get(mid) or None,
              strength=int(rec.get("stars", 0)) * 2, detail=f"{rec.get('best_cpm', 0)} · {rec.get('best_acc', 0)} %")
        chains.setdefault(lang, []).append((int(num) if num.isdigit() else 0, nid))
    for items in chains.values():
        items.sort()
        for (_, a), (_, b) in zip(items, items[1:]):
            g.link(a, b)


def collect(root: Path | None, now: float | None = None) -> Graph:
    """Граф по папке пилота ``root``. Без исключений: нет файлов — пустой граф."""
    g = Graph()
    if root is None:
        return g
    root = Path(root)
    rd = lambda n: pilots.read_json(root / n) or {}  # noqa: E731
    eng, sr, stats = rd("english.json"), rd("speedread.json"), rd("stats.json")
    lib = pilots.read_json(root / "library" / "library.json") or {}
    try:
        _typing(g, stats)
        _english(g, eng, lib)
        _reading(g, sr, lib)
    except Exception:  # noqa: BLE001 — битый файл не должен ронять отсек
        g.gaps.append("parse")
    for day, n in ((eng.get("xp") or {}).get("by_day") or {}).items():
        if n:
            g.active_days.add(str(day))
    return g


def pilot_root(app) -> Path | None:
    """Папка активного пилота (или общая папка данных в режиме без экипажа)."""
    pilot = getattr(app, "pilot", None)
    if pilot and pilot.get("id"):
        return pilots.pilot_dir(pilot["id"])
    try:
        from stamina import storage
        return Path(storage.DATA_DIR)
    except Exception:  # noqa: BLE001
        return None
