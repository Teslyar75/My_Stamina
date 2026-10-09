"""Прогресс модуля «Английский»: %APPDATA%\\Stamina\\english.json (рядом с данными Star Typing)."""
from __future__ import annotations

from stamina.i18n import t as _t

import datetime as dt
import json
import math
import time
from pathlib import Path

from . import paths, sm2

DEFAULT_SETTINGS = {
    "rate": 0, "autoplay": True, "asr": True, "self_assess": True, "current_set": "top-1000",
    "daily_goal": 30, "new_per_day": 20, "reviews_per_day": 200, "session_len": 10,
    "reverse": False, "show_tr": False, "xp_to_rank": True,
}

ACHIEVEMENTS = [
    # id, название, условие (текст), бонус XP
    ("first_step", _t("Первый шаг"), _t("первое выполненное задание"), 10),
    ("known_10", _t("Словарный запас I"), _t("10 слов «знаю» или выучено"), 20),
    ("known_100", _t("Словарный запас II"), _t("100 слов"), 50),
    ("known_500", _t("Словарный запас III"), _t("500 слов"), 100),
    ("known_1000", _t("Словарный запас IV"), _t("1000 слов"), 200),
    ("streak_3", _t("Серия 3"), _t("3 дня подряд с дневной целью"), 20),
    ("streak_7", _t("Серия 7"), _t("7 дней подряд"), 50),
    ("streak_30", _t("Серия 30"), _t("30 дней подряд"), 200),
    ("perfect_session", _t("Без ошибок"), _t("миссия ≥ 10 заданий без ошибок"), 30),
    ("speaker", _t("Голос"), _t("50 ответов голосом с баллом ≥ 85"), 50),
    ("reviewer", _t("Без долгов"), _t("очередь проверки систем пройдена 7 дней подряд"), 50),
    ("set_1000", _t("Фундамент"), _t("все слова top-1000 «знаю» или выучены"), 300),
]


def _today() -> str:
    return dt.date.today().isoformat()


class Progress:
    def __init__(self, path: Path | None = None, app=None) -> None:
        self.path = path or paths.PROGRESS_PATH
        self.app = app  # Cockpit Star Typing (для общего XP и званий)
        self.data = self._load()
        self.on_change = []  # колбэки (уведомления о достижениях и т.п.)

    # -- файл ----------------------------------------------------------------
    def _load(self) -> dict:
        d = {}
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        base = {"version": 1, "settings": dict(DEFAULT_SETTINGS), "words": {}, "lists": [], "cards": {},
                "xp": {"total": 0, "by_day": {}, "best_streak": 0, "awarded": {}},
                "achievements": {}, "attempts": [], "review_done_days": [], "speech_best": {}}
        for k, v in base.items():
            d.setdefault(k, v)
        for k, v in DEFAULT_SETTINGS.items():
            d["settings"].setdefault(k, v)
        if not any(l.get("id") == "favorites" for l in d["lists"]):
            d["lists"].insert(0, {"id": "favorites", "name": _t("Избранное"), "slugs": [], "created": _today()})
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

    # -- слова ---------------------------------------------------------------
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
        """Только собственный перевод пользователя (как сохранён)."""
        return self.data["words"].get(slug, {}).get("tr", "")

    # словарный перевод из vocab.json (поле "ru"); подключается в EnglishScreen
    dict_tr = staticmethod(lambda slug: "")

    def tr(self, slug: str) -> str:
        """Перевод для показа: свой (если введён) важнее словарного."""
        return self.my_tr(slug) or (self.dict_tr(slug) or "")

    def set_my_tr(self, slug: str, text: str) -> None:
        self._w(slug)["tr"] = text.strip()
        self.save()

    def is_learned(self, slug: str) -> bool:
        c = self.data["cards"].get(slug)
        return bool(c and c["interval"] >= 21)

    def known_or_learned(self, slugs) -> int:
        return sum(1 for s in slugs if self.is_known(s) or self.is_learned(s))

    # -- списки (отсеки) -----------------------------------------------------
    @property
    def lists(self) -> list[dict]:
        return self.data["lists"]

    def list_by_id(self, lid: str) -> dict | None:
        return next((l for l in self.lists if l["id"] == lid), None)

    def create_list(self, name: str) -> dict:
        l = {"id": f"l{int(time.time() * 1000)}", "name": name.strip() or _t("Новый отсек"), "slugs": [],
             "created": _today()}
        self.lists.append(l)
        self.save()
        return l

    def rename_list(self, lid: str, name: str) -> None:
        l = self.list_by_id(lid)
        if l and name.strip():
            l["name"] = name.strip()
            self.save()

    def delete_list(self, lid: str) -> None:
        if lid != "favorites":
            self.data["lists"] = [l for l in self.lists if l["id"] != lid]
            self.save()

    def toggle_in_list(self, lid: str, slug: str) -> bool:
        l = self.list_by_id(lid)
        if not l:
            return False
        if slug in l["slugs"]:
            l["slugs"].remove(slug)
            res = False
        else:
            l["slugs"].append(slug)
            res = True
        self.save()
        return res

    def lists_of(self, slug: str) -> list[str]:
        return [l["id"] for l in self.lists if slug in l["slugs"]]

    # -- карточки SM-2 -------------------------------------------------------
    def has_card(self, slug: str) -> bool:
        return slug in self.data["cards"]

    def card(self, slug: str) -> dict | None:
        return self.data["cards"].get(slug)

    def add_card(self, slug: str) -> dict:
        c = self.data["cards"].get(slug)
        if not c:
            c = sm2.new_card(slug)
            self.data["cards"][slug] = c
            self.save()
        return c

    def grade(self, slug: str, q: int) -> dict:
        c = self.data["cards"].get(slug) or sm2.new_card(slug)
        c = sm2.next_state(c, q)
        self.data["cards"][slug] = c
        self.save()
        return c

    def due_cards(self, limit: int | None = None) -> list[str]:
        t = _today()
        due = [s for s, c in self.data["cards"].items() if c["due"] <= t and c.get("reps", 0) > 0
               and not self.is_known(s)]
        due.sort(key=lambda s: self.data["cards"][s]["due"])
        return due[:limit] if limit else due

    def new_today_count(self) -> int:
        t = _today()
        return sum(1 for c in self.data["cards"].values() if c.get("created") == t)

    # -- XP, серия, уровень ---------------------------------------------------
    def add_xp(self, n: int, reason: str = "") -> None:
        if n <= 0:
            return
        x = self.data["xp"]
        x["total"] += n
        day = _today()
        x["by_day"][day] = x["by_day"].get(day, 0) + n
        x["best_streak"] = max(x.get("best_streak", 0), self.streak())
        if self.app is not None and self.settings.get("xp_to_rank", True):
            try:  # общий XP Star Typing → те же звания
                self.app.store.stats["xp"] += n
                self.app.store.save_stats()
                self.app.update_rank()
            except Exception:
                pass
        self.save()

    def award_once(self, key: str, n: int) -> bool:
        aw = self.data["xp"]["awarded"]
        if key in aw:
            return False
        aw[key] = True
        self.add_xp(n)
        return True

    @property
    def xp_total(self) -> int:
        return self.data["xp"]["total"]

    def xp_today(self) -> int:
        return self.data["xp"]["by_day"].get(_today(), 0)

    def level(self) -> tuple[int, int, int]:
        """(уровень, XP начала уровня, XP следующего уровня) — SPEC §7."""
        xp = self.xp_total
        lvl = int(math.floor(math.sqrt(xp / 50))) + 1
        return lvl, 50 * (lvl - 1) ** 2, 50 * lvl ** 2

    def streak(self) -> int:
        goal = self.settings["daily_goal"]
        by = self.data["xp"]["by_day"]
        d = dt.date.today()
        if by.get(d.isoformat(), 0) < goal:
            d -= dt.timedelta(days=1)
        n = 0
        while by.get(d.isoformat(), 0) >= goal:
            n += 1
            d -= dt.timedelta(days=1)
        return n

    def day_flags(self, days: int = 14) -> list[bool]:
        goal = self.settings["daily_goal"]
        by = self.data["xp"]["by_day"]
        d0 = dt.date.today()
        return [by.get((d0 - dt.timedelta(days=i)).isoformat(), 0) >= goal for i in range(days - 1, -1, -1)]

    # -- журнал ответов ------------------------------------------------------
    def record_attempt(self, slug: str, mode: str, task: str, correct: bool, q: int, score=None) -> None:
        a = {"ts": time.time(), "day": _today(), "slug": slug, "mode": mode, "task": task, "ok": bool(correct), "q": q}
        if score is not None:
            a["score"] = score
        self.data["attempts"].append(a)
        self.check_achievements()
        self.save()

    def mistakes(self, days: int = 7) -> list[str]:
        cutoff = time.time() - days * 86400
        seen, out = set(), []
        for a in reversed(self.data["attempts"]):
            if a["ts"] >= cutoff and not a["ok"] and a["slug"] not in seen:
                seen.add(a["slug"])
                out.append(a["slug"])
        return out

    def accuracy_by_mode(self) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for a in self.data["attempts"]:
            r = out.setdefault(a["mode"], [0, 0])
            r[0] += 1 if a["ok"] else 0
            r[1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}

    def mark_review_done(self) -> None:
        t = _today()
        days = self.data["review_done_days"]
        if t not in days:
            days.append(t)
            self.award_once(f"review_done:{t}", 10)
        self.check_achievements()
        self.save()

    # -- достижения -----------------------------------------------------------
    def check_achievements(self, vocab=None) -> list[tuple]:
        got = self.data["achievements"]
        new = []
        att = self.data["attempts"]
        known_cnt = sum(1 for s, w in self.data["words"].items() if w.get("known")) + \
            sum(1 for s, c in self.data["cards"].items() if c["interval"] >= 21 and not self.is_known(s))
        st = max(self.streak(), self.data["xp"].get("best_streak", 0))
        speak_ok = sum(1 for a in att if a["mode"] == "speaking" and a.get("score", 0) >= 85)
        days = sorted(self.data["review_done_days"])
        rev7 = False
        if len(days) >= 7:
            last7 = [dt.date.fromisoformat(d) for d in days[-7:]]
            rev7 = (last7[-1] - last7[0]).days == 6
        cond = {
            "first_step": len(att) >= 1,
            "known_10": known_cnt >= 10, "known_100": known_cnt >= 100,
            "known_500": known_cnt >= 500, "known_1000": known_cnt >= 1000,
            "streak_3": st >= 3, "streak_7": st >= 7, "streak_30": st >= 30,
            "perfect_session": bool(self.data.get("perfect_session")),
            "speaker": speak_ok >= 50, "reviewer": rev7,
            "set_1000": bool(self.data.get("set_1000_done")),
        }
        for aid, name, desc, bonus in ACHIEVEMENTS:
            if aid not in got and cond.get(aid):
                got[aid] = _today()
                new.append((aid, name, desc, bonus))
        for aid, name, desc, bonus in new:
            self.add_xp(bonus)
            for cb in self.on_change:
                try:
                    cb("achievement", name, bonus)
                except Exception:
                    pass
        return new

    # -- экспорт / сброс -------------------------------------------------------
    def export_to(self, path: str) -> None:
        Path(path).write_text(json.dumps({"app": "my-english", "exported": _today(), "state": self.data},
                                         ensure_ascii=False, indent=1), encoding="utf-8")

    def import_from(self, path: str) -> str:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("app") != "my-english" or "state" not in d:
            raise ValueError(_t("это не файл прогресса «Английского»"))
        self.data = d["state"]
        self.save()
        self.data = self._load()
        self.save()
        return _t("слов: {0}, карточек: {1}, XP: {2}").format(len(self.data['words']), len(self.data['cards']), self.xp_total)

    def reset(self) -> None:
        keep = dict(self.settings)
        try:
            self.path.unlink()
        except OSError:
            pass
        self.data = self._load()
        self.data["settings"].update(keep)
        self.save()
