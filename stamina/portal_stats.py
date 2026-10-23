"""Свой прогресс «портала» (дзен-режим): каждый завершённый тест и счётчик начатых.

Хранится локально (DATA_DIR/portal_stats.json), никуда не отправляется. Сводка —
в том же виде, что и профиль с сайта (stamina/monkeytype.summarize), чтобы
одна и та же «страница аккаунта» (stamina/account_view.py) рисовала обе вкладки.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time
from pathlib import Path

MAX_RESULTS = 5000


def path() -> Path:
    from stamina import storage
    return storage.DATA_DIR / "portal_stats.json"


def load(p: Path | None = None) -> dict:
    try:
        d = json.loads((p or path()).read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("results", [])
            d.setdefault("started", len(d["results"]))
            return d
    except (OSError, ValueError):
        pass
    return {"joined": time.time(), "started": 0, "results": []}


def _save(d: dict, p: Path | None = None) -> None:
    from stamina.storage import write_json
    write_json(p or path(), d)


def mark_started(p: Path | None = None) -> None:
    d = load(p)
    d["started"] = int(d.get("started", 0)) + 1
    _save(d, p)


def add_result(res: dict, p: Path | None = None) -> dict:
    d = load(p)
    d["results"] = (d.get("results") or [])[-(MAX_RESULTS - 1):] + [res]
    d["started"] = max(int(d.get("started", 0)), len(d["results"]))
    _save(d, p)
    return d


def xp_for(res: dict) -> int:
    """Опыт за тест: секунды набора × точность (не меньше 1)."""
    return max(1, round(float(res.get("time", 0)) * float(res.get("acc", 0)) / 100))


def level_progress(xp: float) -> tuple[int, int, int]:
    """(уровень, опыт внутри уровня, нужно на уровень) по той же шкале, что у сайта."""
    from stamina.monkeytype import level
    lv = level(xp)
    base = lambda n: 24.5 * (n - 1) ** 2 + 75.5 * (n - 1)   # noqa: E731 — обратная к level()
    have, need = xp - base(lv), base(lv + 1) - base(lv)
    return lv, int(have), int(need)


def _day(ts: float) -> dt.date:
    return dt.date.fromtimestamp(ts)


def streak(days: set, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    d = today if today in days else today - dt.timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def summarize(d: dict | None = None, name: str = "", today: dt.date | None = None) -> dict:
    d = d if d is not None else load()
    res = [r for r in d.get("results") or [] if isinstance(r, dict)]
    today = today or dt.date.today()
    pbs = []
    for mode, keys in (("time", (15, 30, 60, 120)), ("words", (10, 25, 50, 100))):
        for k in keys:
            best = max((r for r in res if r.get("mode") == mode and int(r.get("mode2") or 0) == k),
                       key=lambda r: r.get("wpm", 0), default=None)
            pbs.append({"mode": mode, "mode2": str(k), "wpm": None if best is None else round(best["wpm"], 1),
                        "acc": None if best is None else round(best.get("acc", 0), 1), "language": ""})
    by_day: dict[dt.date, int] = {}
    for r in res:
        by_day[_day(r.get("ts", 0))] = by_day.get(_day(r.get("ts", 0)), 0) + 1
    first = today - dt.timedelta(days=364)
    act = [((first + dt.timedelta(days=i)).isoformat(), by_day.get(first + dt.timedelta(days=i), 0))
           for i in range(365)]
    xp = sum(xp_for(r) for r in res)
    lv, have, need = level_progress(xp)
    secs = sum(float(r.get("time", 0)) for r in res)
    return {"name": name, "joined": d.get("joined"), "tests": len(res), "started": int(d.get("started", 0)),
            "hours": round(secs / 3600, 4), "seconds": secs, "streak": streak(set(by_day), today),
            "max_streak": 0, "pbs": pbs, "lbs": [], "activity": act, "xp": xp, "level": lv,
            "level_have": have, "level_need": need,
            "recent": [round(r.get("wpm", 0), 1) for r in res[-10:]],
            "avg_acc": round(sum(r.get("acc", 0) for r in res[-10:]) / len(res[-10:]), 1) if res else None,
            "avg_cons": round(sum(r.get("consistency", 0) for r in res[-10:]) / len(res[-10:]), 1) if res else None}


def average_pace(d: dict | None = None, n: int = 10) -> int | None:
    res = (d if d is not None else load()).get("results") or []
    last = [r.get("wpm", 0) for r in res[-n:]]
    return round(sum(last) / len(last)) if last else None


def merge(ours: dict | None, mt: dict | None, today: dt.date | None = None) -> dict:
    """Общая таблица: наши данные в приоритете, сайт — где наших нет.

    Рекорд по слоту — наш, если есть, иначе с сайта (src "ST"/"MT"). День активности —
    наш счёт, если в этот день были наши тесты, иначе счёт сайта (оба — в "both").
    Итоги (начато / пройдено / время) — сумма сайта и наших. Серия — по общей активности.
    """
    ours = ours or summarize({"results": [], "started": 0}, today=today)
    mt = mt or {}
    today = today or dt.date.today()
    pbs = []
    mt_pbs = {(p["mode"], str(p["mode2"])): p for p in mt.get("pbs") or []}
    for p in ours.get("pbs") or []:
        key = (p["mode"], str(p["mode2"]))
        if p.get("wpm") is not None:
            pbs.append(dict(p, src="ST"))
        elif mt_pbs.get(key, {}).get("wpm") is not None:
            pbs.append(dict(mt_pbs[key], src="MT"))
        else:
            pbs.append(dict(p, src=""))
    o_act = dict(ours.get("activity") or [])
    m_act = dict(mt.get("activity") or [])
    first = today - dt.timedelta(days=364)
    act, both = [], {}
    for i in range(365):
        k = (first + dt.timedelta(days=i)).isoformat()
        o, m = int(o_act.get(k, 0)), int(m_act.get(k, 0))
        act.append((k, o if o else m))
        if o or m:
            both[k] = (o, m)
    days = {dt.date.fromisoformat(k) for k, v in act if v}
    mt_secs = float(mt.get("hours") or 0) * 3600
    xp = int(ours.get("xp") or 0) + int(mt.get("xp") or 0)
    lv, have, need = level_progress(xp)
    return {"name": mt.get("name") or ours.get("name") or "", "joined": ours.get("joined"),
            "tests": int(ours.get("tests") or 0) + int(mt.get("tests") or 0),
            "started": int(ours.get("started") or 0) + int(mt.get("started") or 0),
            "seconds": float(ours.get("seconds") or 0) + mt_secs,
            "hours": round((float(ours.get("seconds") or 0) + mt_secs) / 3600, 4),
            "streak": streak(days, today), "pbs": pbs, "lbs": mt.get("lbs") or [], "activity": act,
            "both": both, "xp": xp, "level": lv, "level_have": have, "level_need": need,
            "recent": ours.get("recent") or mt.get("recent") or []}
