"""Monkeytype — импорт своего прогресса (только чтение).

Основной путь: публичный профиль GET /users/<name>/profile — ключ не нужен.
ApeKey (необязательно) — только для подробных последних результатов (/results),
у которых жёсткий лимит (~30 запросов в сутки), поэтому всё кэшируется локально
и обновляется только по кнопке. Ключ хранится в настройках пользователя
(settings.json в папке данных), в коде и репозитории его нет.

Отправка результатов на Monkeytype НЕ делается: их API это не разрешает.
"""
from __future__ import annotations

from stamina.i18n import t

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

API = "https://api.monkeytype.com"
TIMEOUT = 10
RESULTS_LIMIT = 10

# Ошибки ApeKey: 470 — неверный, 471 — выключен, 472 — истёк; 479 — лимит запросов
KEY_ERRORS = {470: t("Неверный ApeKey"), 471: t("ApeKey отключён"), 472: t("Срок ApeKey истёк")}


class MonkeytypeError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _default_fetch(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            body = {}
        return e.code, body


def describe_status(status: int, body: Any = None) -> str:
    if status in KEY_ERRORS:
        return KEY_ERRORS[status]
    if status == 479 or status == 429:
        return t("Лимит запросов Monkeytype — попробуйте позже")
    if status == 404:
        return t("Пилот Monkeytype не найден")
    msg = body.get("message") if isinstance(body, dict) else None
    return t("Monkeytype: ошибка {0}").format(status) + (f" ({msg})" if msg else "")


class Client:
    def __init__(self, username: str = "", ape_key: str = "",
                 fetch: Callable[[str, dict], tuple[int, Any]] | None = None) -> None:
        self.username = (username or "").strip()
        self.ape_key = (ape_key or "").strip()
        self._fetch = fetch or _default_fetch

    def _get(self, path: str, *, auth: bool = False) -> Any:
        headers = {"Accept": "application/json", "User-Agent": "StarTyping/desktop"}
        if auth:
            if not self.ape_key:
                raise MonkeytypeError(t("Нужен ApeKey"))
            headers["Authorization"] = f"ApeKey {self.ape_key}"
        try:
            status, body = self._fetch(API + path, headers)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise MonkeytypeError(t("Нет связи с Monkeytype (офлайн?)")) from e
        if status != 200:
            raise MonkeytypeError(describe_status(status, body), status)
        return body.get("data") if isinstance(body, dict) else None

    def profile(self) -> dict:
        if not self.username:
            raise MonkeytypeError(t("Укажите имя пользователя Monkeytype"))
        return self._get("/users/" + urllib.parse.quote(self.username, safe="") + "/profile") or {}

    def results(self, limit: int = RESULTS_LIMIT) -> list:
        return self._get(f"/results?limit={int(limit)}", auth=True) or []


def best_of(entries: list | None) -> dict | None:
    """Лучший результат режима (на Monkeytype — по одному на язык/настройки)."""
    entries = [e for e in (entries or []) if isinstance(e, dict) and "wpm" in e]
    return max(entries, key=lambda e: e.get("wpm", 0)) if entries else None


def summarize(profile: dict | None, results: list | None = None) -> dict:
    """Свести ответ API к тому, что показывает панель."""
    profile = profile or {}
    ts = profile.get("typingStats") or {}
    pbs = profile.get("personalBests") or {}
    out_pbs = []
    lbs = []
    for mode, by in ((profile.get("allTimeLbs") or {}).items()):
        for mode2, langs in (by or {}).items():
            for lang, r in (langs or {}).items():
                if isinstance(r, dict) and r.get("rank"):
                    lbs.append({"mode": mode, "mode2": mode2, "language": lang,
                                "rank": int(r["rank"]), "count": int(r.get("count") or 0)})
    for mode, keys in (("time", ("15", "30", "60", "120")), ("words", ("10", "25", "50", "100"))):
        for k in keys:
            b = best_of((pbs.get(mode) or {}).get(k))
            if not b:
                out_pbs.append({"mode": mode, "mode2": k, "wpm": None, "acc": None, "language": ""})
            else:
                out_pbs.append({"mode": mode, "mode2": k, "wpm": round(float(b["wpm"]), 1),
                                "acc": round(float(b.get("acc", 0)), 1),
                                "language": b.get("language", "")})
    recent = [round(float(r.get("wpm", 0)), 1) for r in (results or []) if isinstance(r, dict)]
    return {
        "name": profile.get("name", ""),
        "xp": int(profile.get("xp") or 0),
        "level": level(profile.get("xp") or 0),
        "tests": int(ts.get("completedTests") or 0),
        "started": int(ts.get("startedTests") or 0),
        "hours": round(float(ts.get("timeTyping") or 0) / 3600, 1),
        "streak": int(profile.get("streak") or 0),
        "max_streak": int(profile.get("maxStreak") or 0),
        "pbs": out_pbs,
        "lbs": lbs,
        "activity": activity(profile.get("testActivity")),
        "recent": recent,
    }


def activity(ta: dict | None, days: int = 365) -> list[tuple[str, int]]:
    """testActivity → [(«ГГГГ-ММ-ДД», тестов)] за последние ``days`` дней.

    testsByDays — по дню на элемент, последний соответствует lastDay (мс, UTC).
    """
    import datetime as dt
    if not isinstance(ta, dict) or not ta.get("testsByDays") or not ta.get("lastDay"):
        return []
    last = dt.datetime.fromtimestamp(int(ta["lastDay"]) / 1000, dt.timezone.utc).date()
    arr = list(ta["testsByDays"])[-days:]
    n = len(arr)
    return [((last - dt.timedelta(days=n - 1 - i)).isoformat(), int(v or 0)) for i, v in enumerate(arr)]


def cache_path() -> Path:
    from stamina import storage
    return storage.DATA_DIR / "monkeytype_cache.json"


def load_cache(path: Path | None = None) -> dict | None:
    try:
        data = json.loads((path or cache_path()).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def refresh(username: str, ape_key: str = "", *, fetch=None, path: Path | None = None,
            with_results: bool = True) -> dict:
    """Скачать профиль (и результаты, если есть ключ), сохранить кэш, вернуть сводку.

    Ошибка результатов по ключу не мешает профилю: она попадает в поле "warning".
    """
    cli = Client(username, ape_key, fetch)
    prof = cli.profile()
    old = load_cache(path) or {}
    results, warning = old.get("results_raw") or [], ""
    if ape_key and with_results:
        try:
            results = cli.results()
        except MonkeytypeError as e:
            warning = str(e)
    data = {"fetched_at": time.time(), "username": username, "profile": prof,
            "results_raw": results, "summary": summarize(prof, results), "warning": warning}
    from stamina.storage import write_json
    write_json(path or cache_path(), data)
    return data


def level(xp) -> int:
    """Уровень по опыту (та же шкала, что на сайте: 1 + (√(392·xp + 22801) − 151) / 98)."""
    import math
    try:
        return int(1 + (math.sqrt(392 * max(0.0, float(xp)) + 22801) - 151) / 98)
    except (TypeError, ValueError):
        return 0


def average_pace(data: dict | None, mode: str = "", mode2: str = "") -> int | None:
    """«average pace» для строки над текстом: последние результаты, иначе рекорды режима."""
    s = (data or {}).get("summary") or {}
    rec = [v for v in s.get("recent") or [] if v]
    if rec:
        return round(sum(rec) / len(rec))
    pbs = [p["wpm"] for p in s.get("pbs") or [] if p.get("wpm")
           and (not mode or p["mode"] == mode) and (not mode2 or p["mode2"] == str(mode2))]
    if not pbs:
        pbs = [p["wpm"] for p in s.get("pbs") or [] if p.get("wpm")]
    return round(sum(pbs) / len(pbs)) if pbs else None


# --- тихая фоновая синхронизация (только чтение) -----------------------------
SYNC_MIN_INTERVAL = 300        # не чаще раза в 5 минут
SYNC_BACKOFF = 900             # после 479/429 — пауза 15 минут
_sync = {"last": 0.0, "until": 0.0, "busy": False}


def backoff_left(now: float | None = None) -> int:
    """Секунд до конца паузы после настоящего 429 (0 — паузы нет)."""
    now = time.time() if now is None else now
    return max(0, int(_sync["until"] - now + 0.999))


def auto_sync(username: str, ape_key: str = "", *, fetch=None, path: Path | None = None,
              on_done=None, on_error=None, now: float | None = None, threaded: bool = True,
              force: bool = False) -> bool:
    """Обновить кэш профиля в фоне, если пора. True — запуск был.

    force (ручное ↻) обходит 5-минутный интервал, но не паузу после 429.
    on_error(str) получает текст ошибки; флаг busy сбрасывается всегда.
    """
    username = (username or "").strip()
    now = time.time() if now is None else now
    if not username or _sync["busy"] or now < _sync["until"]:
        return False
    if not force:
        old = load_cache(path) or {}
        same = str(old.get("username", "")).lower() == username.lower()
        last = max(_sync["last"], float(old.get("fetched_at") or 0) if same else 0)
        if now - last < SYNC_MIN_INTERVAL:
            return False
    _sync["last"] = now
    _sync["busy"] = True

    def work() -> None:
        data, err = None, ""
        try:
            data = refresh(username, ape_key, fetch=fetch, path=path)
        except MonkeytypeError as e:
            err = str(e)
            if err == t("Лимит запросов Monkeytype — попробуйте позже"):
                _sync["until"] = time.time() + SYNC_BACKOFF
        except Exception as e:  # noqa: BLE001
            err = f"Monkeytype: {e}"
        finally:
            _sync["busy"] = False
        cb, arg = (on_done, data) if data is not None else (on_error, err or t("ошибка"))
        if cb is not None:
            try:
                cb(arg)
            except Exception:  # noqa: BLE001
                pass

    if threaded:
        threading.Thread(target=work, daemon=True).start()
    else:
        work()
    return True
