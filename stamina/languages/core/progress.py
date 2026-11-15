"""Per-language progress tracking with SM-2, XP, achievements, streaks."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .scheduler import SM2Scheduler, SM2Card


DEFAULT_SETTINGS = {
    "rate": 0,
    "autoplay": True,
    "asr": True,
    "self_assess": True,
    "current_set": "top-1000",
    "speech_strictness": "normal",
    "daily_goal": 30,
    "new_per_day": 20,
    "reviews_per_day": 200,
    "session_len": 10,
    "reverse": False,
    "show_tr": False,
    "xp_to_rank": True,
    "warehouse_passes": 2,
    "quality_goal": 20,
    "cefr_unlock_pct": 80,
}


ACHIEVEMENTS = [
    ("first_step", "Первый шаг", "первое выполненное задание", 10),
    ("known_10", "Словарный запас I", "10 слов «знаю» или выучено", 20),
    ("known_100", "Словарный запас II", "100 слов", 50),
    ("known_500", "Словарный запас III", "500 слов", 100),
    ("known_1000", "Словарный запас IV", "1000 слов", 200),
    ("streak_3", "Серия 3", "3 дня подряд с дневной целью", 20),
    ("streak_7", "Серия 7", "7 дней подряд", 50),
    ("streak_30", "Серия 30", "30 дней подряд", 200),
    ("perfect_session", "Без ошибок", "миссия ≥ 10 заданий без ошибок", 30),
    ("speaker", "Голос", "50 ответов голосом с баллом ≥ 85", 50),
    ("reviewer", "Без долгов", "очередь проверки пройдена 7 дней подряд", 50),
    ("set_1000", "Фундамент", "все слова top-1000 «знаю» или выучены", 300),
]


def _today() -> str:
    return date.today().isoformat()


class LanguageProgress:
    def __init__(self, pilot_dir: Path, lang_code: str) -> None:
        self.lang_code = lang_code
        self.path = pilot_dir / f"lang_{lang_code}.json"
        self.pilot_dir = pilot_dir
        self.data = self._load()
        self.on_change = []

    def _load(self) -> dict[str, Any]:
        try:
            if self.path.exists():
                d = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                d = {}
        except (OSError, ValueError):
            d = {}

        base = {
            "version": 2,
            "lang_code": self.lang_code,
            "settings": dict(DEFAULT_SETTINGS),
            "words": {},
            "lists": [],
            "cards": {},
            "quality": {},
            "xp": {"total": 0, "by_day": {}, "best_streak": 0, "awarded": {}},
            "achievements": {},
            "attempts": [],
            "review_done_days": [],
            "speech_best": {},
            "warehouse": {"flips": 0, "ok": 0, "by_day": {}, "best": {}},
            "verb_scores": {},
            "book_sentences": {"books": {}, "cards": {}, "stats": {"flips": 0, "ok": 0, "by_day": {}}},
        }
        for k, v in base.items():
            d.setdefault(k, v)
        for k, v in DEFAULT_SETTINGS.items():
            d["settings"].setdefault(k, v)
        if not any(l.get("id") == "favorites" for l in d["lists"]):
            d["lists"].insert(0, {"id": "favorites", "name": "Избранное", "slugs": [], "created": _today()})
        cutoff = time.time() - 90 * 86400
        d["attempts"] = [a for a in d["attempts"] if a.get("ts", 0) >= cutoff]
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

    def _w(self, slug: str) -> dict:
        return self.data["words"].setdefault(slug, {})

    def is_known(self, slug: str) -> bool:
        return bool(self.data["words"].get(slug, {}).get("known"))

    def set_known(self, slug: str, value: bool) -> None:
        w = self._w(slug)
        w["known"] = value
        if value:
            w["known_at"] = _today()
            self.award_once(f"known:{slug}", 2)
        self.check_achievements()
        self.save()

    def my_tr(self, slug: str) -> str:
        return self.data["words"].get(slug, {}).get("tr", "")

    def set_my_tr(self, slug: str, text: str) -> None:
        self._w(slug)["tr"] = text.strip()
        self.save()

    def is_learned(self, slug: str) -> bool:
        c = self.data["cards"].get(slug)
        return bool(c and c["interval"] >= 21)

    def known_or_learned(self, slugs: list[str]) -> int:
        return sum(1 for s in slugs if self.is_known(s) or self.is_learned(s))

    def get_card(self, slug: str) -> SM2Card:
        c = self.data["cards"].get(slug)
        if not c:
            return SM2Scheduler.initial_card()
        return SM2Card(
            interval=c.get("interval", 0),
            ease_factor=c.get("ease_factor", 2.5),
            repetitions=c.get("repetitions", 0),
            due_date=date.fromisoformat(c["due_date"]) if c.get("due_date") else None,
            last_review=date.fromisoformat(c["last_review"]) if c.get("last_review") else None,
        )

    def update_card(self, slug: str, card: SM2Card) -> None:
        self.data["cards"][slug] = {
            "interval": card.interval,
            "ease_factor": card.ease_factor,
            "repetitions": card.repetitions,
            "due_date": card.due_date.isoformat() if card.due_date else None,
            "last_review": card.last_review.isoformat() if card.last_review else None,
        }
        self.save()

    def add_xp(self, amount: int, reason: str = "") -> None:
        self.data["xp"]["total"] += amount
        today = _today()
        self.data["xp"]["by_day"][today] = self.data["xp"]["by_day"].get(today, 0) + amount
        self._check_streak()
        self._notify("xp_gained", {"amount": amount, "reason": reason})
        self.save()

    def _check_streak(self) -> None:
        by_day = self.data["xp"]["by_day"]
        streak = 0
        d = date.today()
        while True:
            if by_day.get(d.isoformat(), 0) > 0:
                streak += 1
                d -= timedelta(days=1)
            else:
                break
        if streak > self.data["xp"]["best_streak"]:
            self.data["xp"]["best_streak"] = streak

    def current_streak(self) -> int:
        by_day = self.data["xp"]["by_day"]
        streak = 0
        d = date.today()
        while by_day.get(d.isoformat(), 0) > 0:
            streak += 1
            d -= timedelta(days=1)
        return streak

    def daily_goal_met_today(self) -> bool:
        today = _today()
        goal = self.settings.get("daily_goal", 30)
        return self.data["xp"]["by_day"].get(today, 0) >= goal

    def award_once(self, key: str, xp: int) -> bool:
        awarded = self.data["xp"]["awarded"]
        if key not in awarded:
            awarded[key] = True
            self.add_xp(xp, key)
            return True
        return False

    def check_achievements(self) -> None:
        known_count = sum(1 for w in self.data["words"].values() if w.get("known") or self.is_learned(w))
        for aid, name, desc, xp in ACHIEVEMENTS:
            if aid in self.data["achievements"]:
                continue
            unlocked = False
            if aid == "first_step" and self.data["attempts"]:
                unlocked = True
            elif aid.startswith("known_") and known_count >= int(aid.split("_")[1]):
                unlocked = True
            elif aid == "streak_3" and self.current_streak() >= 3:
                unlocked = True
            elif aid == "streak_7" and self.current_streak() >= 7:
                unlocked = True
            elif aid == "streak_30" and self.current_streak() >= 30:
                unlocked = True
            elif aid == "set_1000" and known_count >= 1000:
                unlocked = True
            if unlocked:
                self.data["achievements"][aid] = {"name": name, "desc": desc, "unlocked_at": _today(), "xp": xp}
                self.add_xp(xp, f"achievement:{aid}")
                self._notify("achievement", {"id": aid, "name": name, "xp": xp})

    def _notify(self, event: str, data: dict) -> None:
        for cb in self.on_change:
            try:
                cb(event, data)
            except Exception:
                pass

    def record_attempt(self, slug: str, correct: bool, mode: str, latency_ms: int = 0, quality: int | None = None) -> None:
        self.data["attempts"].append({
            "ts": time.time(),
            "slug": slug,
            "correct": correct,
            "mode": mode,
            "latency_ms": latency_ms,
            "quality": quality,
        })
        if correct:
            self.add_xp(1, f"attempt:{mode}")
        self.save()

    def get_due_cards(self, slugs: list[str], limit: int = 200) -> list[str]:
        due = []
        for slug in slugs:
            card = self.get_card(slug)
            if SM2Scheduler.is_due(card):
                due.append(slug)
        due.sort(key=lambda s: self.get_card(s).due_date or date.max)
        return due[:limit]

    def get_new_cards(self, slugs: list[str], limit: int = 20) -> list[str]:
        new = [s for s in slugs if s not in self.data["cards"]]
        return new[:limit]