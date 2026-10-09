"""Прогресс отсека «СКОРОЧТЕНИЕ»: %APPDATA%\\Stamina\\speedread.json (атомарная запись)."""
from __future__ import annotations

import json
import time
from pathlib import Path

DEFAULT_SETTINGS = {
    "wpm_start": 300, "wpm_target": 600, "ramp": "smooth", "ramp_step": 10, "ramp_every_s": 30,
    "chunk": 1, "chunk_max_chars": 24, "font_pt": 54, "orp": True, "punct_pauses": True,
    "guides": True, "quiz": "always", "quiz_words": 1000, "sync": "ask",
}

MAX_SESSIONS = 500
XP_DAILY_EX_LIMIT = 5


def _today() -> str:
    return time.strftime("%Y-%m-%d")


class SpeedStore:
    def __init__(self, path: Path | None = None, app=None) -> None:
        if path is None:
            from stamina.storage import DATA_DIR
            path = DATA_DIR / "speedread.json"
        self.path = Path(path)
        self.app = app
        self.data = self._load()

    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                raise ValueError
        except (OSError, ValueError):
            d = {}
        d.setdefault("version", 1)
        st = dict(DEFAULT_SETTINGS)
        st.update(d.get("settings") or {})
        d["settings"] = st
        d.setdefault("sessions", [])
        d.setdefault("exercises", {})
        d.setdefault("xp", {"total": 0, "by_day": {}, "ex_runs": {}})
        d.setdefault("days", [])
        return d

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    # -- дни / серия -------------------------------------------------------------
    def _mark_day(self) -> None:
        d = _today()
        if d not in self.data["days"]:
            self.data["days"].append(d)
            self.data["days"] = self.data["days"][-400:]

    def streak(self) -> int:
        days = set(self.data["days"])
        n = 0
        t = time.time()
        if time.strftime("%Y-%m-%d", time.localtime(t)) not in days:
            t -= 86400
        while time.strftime("%Y-%m-%d", time.localtime(t)) in days:
            n += 1
            t -= 86400
        return n

    # -- XP в общее звание Star Typing ----------------------------------------------
    def add_xp(self, n: int) -> int:
        n = max(0, int(n))
        if not n:
            return 0
        x = self.data["xp"]
        x["total"] = x.get("total", 0) + n
        x["by_day"][_today()] = x["by_day"].get(_today(), 0) + n
        if self.app is not None:
            try:
                self.app.store.stats["xp"] += n
                self.app.store.save_stats()
                self.app.update_rank()
            except Exception:  # noqa: BLE001
                pass
        return n

    # -- чтение -----------------------------------------------------------------
    def add_session(self, rec: dict) -> int:
        """rec: text, title, words, secs, avg_wpm, max_wpm, comp (0..1 или None)."""
        comp = rec.get("comp")
        eff = round(rec["avg_wpm"] * comp) if comp is not None else None
        stars = 0
        if comp is not None:
            stars = 3 if comp >= 0.9 else 2 if comp >= 0.75 else 1 if comp >= 0.6 else 0
        k = comp if comp is not None else 0.6
        xp = int(round(rec["words"] / 50 * k * k)) + stars * 15
        best = self.best_wpm()
        if rec["avg_wpm"] > best and rec["words"] >= 200 and best > 0:
            xp += 25
        rec = dict(rec, ts=time.time(), day=_today(), eff_wpm=eff, stars=stars, xp=xp)
        self.data["sessions"].append(rec)
        self.data["sessions"] = self.data["sessions"][-MAX_SESSIONS:]
        self._mark_day()
        self.add_xp(xp)
        self.save()
        return xp

    def best_wpm(self) -> int:
        vals = [s["avg_wpm"] for s in self.data["sessions"] if s.get("words", 0) >= 200]
        return int(max(vals)) if vals else 0

    def last_sessions(self, n: int = 30) -> list[dict]:
        return self.data["sessions"][-n:]

    def avg_comp(self) -> float | None:
        vals = [s["comp"] for s in self.data["sessions"][-20:] if s.get("comp") is not None]
        return sum(vals) / len(vals) if vals else None

    # -- тренажёры -----------------------------------------------------------------
    def add_exercise(self, code: str, variant: str, result: float, stars: int,
                     lower_is_better: bool = True, extra: dict | None = None) -> tuple[int, bool]:
        """Сохранить заход тренажёра. → (XP, новый рекорд?)."""
        ex = self.data["exercises"].setdefault(code, {})
        rec = ex.setdefault(variant, {"best": None, "stars": 0, "runs": []})
        better = rec["best"] is None or (result < rec["best"] if lower_is_better else result > rec["best"])
        if better:
            rec["best"] = result
        rec["stars"] = max(rec.get("stars", 0), stars)
        rec["runs"].append({"ts": time.time(), "result": result, "stars": stars, **(extra or {})})
        rec["runs"] = rec["runs"][-100:]
        self._mark_day()
        key = f"{_today()}:{code}"
        runs = self.data["xp"]["ex_runs"]
        runs[key] = runs.get(key, 0) + 1
        for k in [k for k in runs if not k.startswith(_today())]:
            runs.pop(k, None)
        xp = 0
        if runs[key] <= XP_DAILY_EX_LIMIT:
            xp = 10 + stars * 10 + (25 if better and len(rec["runs"]) > 1 else 0)
        self.add_xp(xp)
        self.save()
        return xp, better and len(rec["runs"]) > 1

    def exercise_best(self, code: str) -> tuple[str, dict] | None:
        ex = self.data["exercises"].get(code) or {}
        if not ex:
            return None
        variant = max(ex, key=lambda v: len(ex[v]["runs"]))
        return variant, ex[variant]
