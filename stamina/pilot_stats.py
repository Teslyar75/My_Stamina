"""Сводка по пилоту для «ВХОДА В КАБИНУ» и «ДОСКИ ПОЧЁТА».

Читает файлы пилота только на чтение и напрямую (без stamina.storage), поэтому подходит
для любого пилота экипажа, а не только активного.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import datetime as dt
import time

from stamina import pilots
from stamina.missions import RANKS, rank_for

WEEK = 7 * 86400


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _streak(days: set[str]) -> int:
    d = dt.date.today()
    if d.isoformat() not in days:
        d -= dt.timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def achievements(s: dict) -> list[tuple[str, bool]]:
    """Достижения пилота (вычисляются по данным; английские — из english.json)."""
    out = [
        (_t("Первая миссия"), s["missions_done"] >= 1),
        (_t("Ряд миссий на ★★★"), s["missions_3star"] >= 5),
        (_t("Все 20 миссий пройдены"), s["missions_done"] >= 20),
        (_t("Свой текст 25 %"), (s["book_pct"] or 0) >= 25),
        (_t("Свой текст 50 %"), (s["book_pct"] or 0) >= 50),
        (_t("Свой текст 100 %"), (s["book_pct"] or 0) >= 100),
        (_t("Печать 200 зн/мин"), s["best_cpm"] >= 200),
        (_t("Печать 300 зн/мин"), s["best_cpm"] >= 300),
        (_t("Точность 98 %"), s["best_acc"] >= 98),
        (_t("Чтение 500 сл/мин с пониманием"), (s["sr_eff"] or 0) >= 500),
        (_t("Шульте 5×5 быстрее 35 с"), s["schulte_5x5"] is not None and s["schulte_5x5"] < 35),
        (_t("100 английских слов"), s["en_known"] >= 100),
        (_t("1000 английских слов"), s["en_known"] >= 1000),
        (_t("Серия 7 дней"), s["streak"] >= 7),
        (_t("Серия 30 дней"), s["streak"] >= 30),
    ]
    for _thr, name in RANKS[1:]:
        out.append((_t("Звание «{0}»").format(name), s["xp"] >= _thr))
    for key in s.get("en_achievements", []):
        out.append((_t("Английский: {0}").format(key), True))
    return out


def pilot_stats(pid: str, period: str = "all", now: float | None = None) -> dict:
    """period: "all" | "week". Без исключений: отсутствующие файлы дают нули/None."""
    now = time.time() if now is None else now
    since = now - WEEK if period == "week" else 0
    d = pilots.pilot_dir(pid)
    rd = lambda n: pilots.read_json(d / n) or {}  # noqa: E731
    stats, eng, sr, sess = rd("stats.json"), rd("english.json"), rd("speedread.json"), rd("session.json")
    days: set[str] = set()
    # печать
    runs = [r for r in stats.get("runs", []) if isinstance(r, dict)]
    for r in runs:
        if r.get("ts"):
            days.add(_day(r["ts"]))
    pruns = [r for r in runs if r.get("ts", 0) >= since and r.get("chars", 0) >= 30]
    best = max(pruns, key=lambda r: r.get("cpm", 0), default=None)
    xp_total = int(stats.get("xp", 0))
    xp_week = sum(int(r.get("xp", 0)) for r in runs if r.get("ts", 0) >= now - WEEK)
    missions = stats.get("missions", {}) or {}
    # свой текст
    book_pct, book_title = None, ""
    text = sess.get("text") or ""
    if text:
        book_pct = round(min(1.0, int(sess.get("index", 0)) / max(1, len(text))) * 100, 1)
        lib = pilots.read_json(d / "library" / "library.json") or {}
        tid = lib.get("active_typing")
        for t in lib.get("texts", []):
            if t.get("id") == tid:
                book_title = t.get("title", "")
        book_title = book_title or _t("свой текст")
    # английский
    words = eng.get("words", {}) or {}
    cards = eng.get("cards", {}) or {}
    known = {s for s, w in words.items() if isinstance(w, dict) and w.get("known")}
    known |= {s for s, c in cards.items() if isinstance(c, dict) and c.get("interval", 0) >= 21}
    att = [a for a in eng.get("attempts", []) if isinstance(a, dict)]
    scores = [float(a["score"]) for a in att if a.get("mode") == "speaking" and a.get("score") is not None
              and a.get("ts", 0) >= since]
    if not scores and period == "all":
        scores = [float(v) for v in (eng.get("speech_best") or {}).values() if isinstance(v, (int, float))]
    ebd = (eng.get("xp") or {}).get("by_day", {}) or {}
    for day, n in ebd.items():
        if n:
            days.add(day)
    week_days = {_day(now - i * 86400) for i in range(7)}
    xp_week += sum(int(n) for day, n in ebd.items() if day in week_days)
    # скорочтение
    sess_sr = [s for s in sr.get("sessions", []) if isinstance(s, dict) and s.get("ts", 0) >= since]
    effs = [s["eff_wpm"] for s in sess_sr if s.get("eff_wpm")]
    sr_eff = max(effs) if effs else None
    sh = ((sr.get("exercises") or {}).get("E-SHL") or {})
    sh_runs = [(v, r["result"]) for v, rec in sh.items() for r in rec.get("runs", [])
               if r.get("ts", 0) >= since]
    schulte = None
    if sh_runs:
        five = [x for v, x in sh_runs if v.startswith("5x5")]
        if five:
            schulte = ("5×5", min(five))
        else:
            v, x = min(sh_runs, key=lambda t: t[1])
            schulte = (v.split("-")[0].replace("x", "×"), x)
    for day in sr.get("days", []):
        days.add(day)
    sbd = (sr.get("xp") or {}).get("by_day", {}) or {}
    xp_week += sum(int(n) for day, n in sbd.items() if day in week_days)
    rank, lo, hi = rank_for(xp_total)
    out = {
        "id": pid, "xp": xp_total, "xp_week": xp_week, "rank": rank, "rank_lo": lo, "rank_hi": hi,
        "rank_idx": next(i for i, (t, n) in enumerate(RANKS) if n == rank),
        "best_cpm": round(best.get("cpm", 0)) if best else 0,
        "best_acc": round(best.get("acc", 0), 1) if best else 0.0,
        "last_cpm": round(runs[-1].get("cpm", 0)) if runs else 0,
        "runs": len(pruns),
        "missions_done": sum(1 for m in missions.values() if m.get("stars", 0) > 0),
        "missions_3star": sum(1 for m in missions.values() if m.get("stars", 0) >= 3),
        "book_pct": book_pct, "book_title": book_title,
        "en_known": len(known), "en_pron": round(sum(scores) / len(scores)) if scores else None,
        "en_achievements": sorted((eng.get("achievements") or {}).keys()),
        "sr_eff": sr_eff, "sr_best": max((s.get("avg_wpm", 0) for s in sess_sr), default=0) or None,
        "schulte": schulte, "schulte_5x5": min((x for v, x in sh_runs if v.startswith("5x5")), default=None),
        "streak": _streak(days),
        "last_day": max(days) if days else None,
    }
    ach = achievements(out)
    out["ach_done"] = sum(1 for _n, ok in ach if ok)
    out["ach_total"] = len(ach)
    out["achievements"] = ach
    return out


def summary(pid: str) -> dict:
    s = pilot_stats(pid)
    return {k: s[k] for k in ("rank", "xp", "best_cpm", "last_cpm", "book_pct", "book_title", "en_known",
                              "sr_eff", "sr_best", "last_day", "ach_done", "ach_total", "rank_lo", "rank_hi")}
