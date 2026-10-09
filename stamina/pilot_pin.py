"""Код доступа пилота (необязательный): только солёный хэш PBKDF2, никаких кодов по умолчанию.

Это защита от случайного входа в чужой профиль, не шифрование данных.
"""
from __future__ import annotations

from stamina.i18n import t

import hashlib
import hmac
import secrets
import time

from stamina import pilots

ALGO = "pbkdf2_sha256"
ITERATIONS = 200_000
MAX_TRIES = 5
LOCK_STEPS = (30, 60, 120, 240, 480, 900)   # секунды, дальше — 15 минут


def valid_code(code: str) -> bool:
    return code.isdigit() and 4 <= len(code) <= 8


def make_hash(code: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> dict:
    if not valid_code(code):
        raise ValueError(t("Код — от 4 до 8 цифр"))
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), salt, iterations)
    return {"algo": ALGO, "iter": iterations, "salt": salt.hex(), "hash": h.hex(), "set": pilots.now_iso()}


def check_hash(rec: dict, code: str) -> bool:
    try:
        salt = bytes.fromhex(rec["salt"])
        h = hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), salt, int(rec["iter"]))
        return hmac.compare_digest(h.hex(), rec["hash"])
    except (KeyError, ValueError, UnicodeEncodeError):
        return False


def has_pin(pid: str) -> bool:
    return bool(pilots.profile(pid).get("pin"))


def set_pin(pid: str, code: str) -> None:
    prof = pilots.profile(pid)
    prof["pin"] = make_hash(code)
    prof["pin_fail"] = {"count": 0, "until": None, "level": 0}
    prof["pin_setup_pending"] = False
    pilots.save_profile(pid, prof)
    pilots.update_pilot(pid, locked=True, pin_setup_pending=False)


def clear_pin(pid: str, *, reason: str = "") -> None:
    prof = pilots.profile(pid)
    prof.pop("pin", None)
    prof["pin_fail"] = {"count": 0, "until": None, "level": 0}
    pilots.save_profile(pid, prof)
    pilots.update_pilot(pid, locked=False, pin_setup_pending=False)
    if reason:
        p = pilots.get(pid) or {}
        pilots.log_error(f"{reason}: {p.get('callsign', pid)} ({pid})", name="pilots_audit.log")


def postpone_setup(pid: str) -> None:
    """«ПОЗЖЕ»: окно задания кода появится при следующем запуске."""


def no_pin_wanted(pid: str) -> None:
    """Пилот явно выбрал «Без кода»."""
    pilots.update_pilot(pid, pin_setup_pending=False)


def lock_left(pid: str, now: float | None = None) -> int:
    """Сколько секунд ещё заблокирован ввод (0 — можно)."""
    until = (pilots.profile(pid).get("pin_fail") or {}).get("until")
    now = time.time() if now is None else now
    return max(0, int(round(until - now))) if until else 0


def verify(pid: str, code: str, now: float | None = None) -> tuple[bool, str]:
    """→ (верно?, сообщение). Считает ошибки и блокирует после MAX_TRIES подряд."""
    now = time.time() if now is None else now
    prof = pilots.profile(pid)
    rec = prof.get("pin")
    if not rec:
        return True, ""
    fail = prof.setdefault("pin_fail", {"count": 0, "until": None, "level": 0})
    if fail.get("until") and now < fail["until"]:
        return False, t("ВВОД ЗАБЛОКИРОВАН · {0} С").format(int(fail['until'] - now) + 1)
    if check_hash(rec, code):
        prof["pin_fail"] = {"count": 0, "until": None, "level": 0}
        pilots.save_profile(pid, prof)
        return True, ""
    fail["count"] = int(fail.get("count", 0)) + 1
    if fail["count"] >= MAX_TRIES:
        lvl = int(fail.get("level", 0))
        fail["until"] = now + LOCK_STEPS[min(lvl, len(LOCK_STEPS) - 1)]
        fail["level"] = lvl + 1
        fail["count"] = 0
        pilots.save_profile(pid, prof)
        return False, t("КОД НЕВЕРЕН · ВВОД ЗАБЛОКИРОВАН НА {0} С").format(LOCK_STEPS[min(lvl, len(LOCK_STEPS) - 1)])
    fail["until"] = None
    pilots.save_profile(pid, prof)
    return False, t("КОД НЕВЕРЕН · ОСТАЛОСЬ ПОПЫТОК: {0}").format(MAX_TRIES - fail['count'])
