"""Код владельца корабля — единственный способ выдать агенту права Командира.

Зачем: уровень «Командир» даёт агенту право менять корабль, поэтому обычный пилот
не может выдать его «просто так». Код задаёт владелец корабля один раз; дальше
корабль спрашивает код каждый раз, когда агенту выдают права Командира.

Хранится только солёный хэш PBKDF2 (как код пилота — `stamina/pilot_pin.py`),
никаких кодов по умолчанию. Это защита от «выдал себе полные права», а не шифрование.

Файл (в корне данных экипажа, рядом с `agents.json`)::

    owner.json   {"code": {algo, iter, salt, hash}, "fail": {count, until, level}}
"""
from __future__ import annotations

from stamina.i18n import t

import time
from pathlib import Path

from stamina import pilot_pin, pilots

FILE = "owner.json"
MAX_TRIES = 5
LOCK_STEPS = (60, 120, 300, 900, 1800)      # секунды, дальше — 30 минут


def path() -> Path:
    return Path(pilots.ROOT_DIR) / FILE


def _read() -> dict:
    return pilots.read_json(path()) or {}


def _write(data: dict) -> None:
    pilots.write_json(path(), data)


def is_set() -> bool:
    """Задан ли код владельца (если нет — права Командира выдать нельзя)."""
    return bool(_read().get("code"))


def set_code(code: str) -> None:
    """Задать код владельца: первый, кто задал, — владелец корабля.

    Бросает ValueError с понятным текстом, если код не 4–8 цифр.
    """
    data = _read()
    data["code"] = pilot_pin.make_hash(code)
    data["fail"] = {"count": 0, "until": None, "level": 0}
    _write(data)


def clear_code() -> None:
    """Забыть код владельца (права Командира больше никому не выдаются)."""
    data = _read()
    data.pop("code", None)
    data["fail"] = {"count": 0, "until": None, "level": 0}
    _write(data)


def lock_left(now: float | None = None) -> int:
    """Сколько секунд ещё заблокирован ввод (0 — можно)."""
    until = (_read().get("fail") or {}).get("until")
    now = time.time() if now is None else now
    return max(0, int(round(until - now))) if until else 0


def verify(code: str, now: float | None = None) -> tuple[bool, str]:
    """→ (верно?, сообщение для пилота). После MAX_TRIES подряд — блокировка."""
    now = time.time() if now is None else now
    data = _read()
    rec = data.get("code")
    if not rec:
        return False, t("Кода владельца ещё нет: задайте его — он останется у владельца корабля.")
    fail = data.setdefault("fail", {"count": 0, "until": None, "level": 0})
    if fail.get("until") and now < fail["until"]:
        return False, t("ВВОД ЗАБЛОКИРОВАН · {0} С").format(int(fail["until"] - now) + 1)
    if pilot_pin.check_hash(rec, code):
        data["fail"] = {"count": 0, "until": None, "level": 0}
        _write(data)
        return True, ""
    fail["count"] = int(fail.get("count", 0)) + 1
    if fail["count"] >= MAX_TRIES:
        level = int(fail.get("level", 0))
        wait = LOCK_STEPS[min(level, len(LOCK_STEPS) - 1)]
        fail["until"] = now + wait
        fail["level"] = level + 1
        fail["count"] = 0
        _write(data)
        return False, t("ВВОД ЗАБЛОКИРОВАН · {0} С").format(wait)
    fail["until"] = None
    _write(data)
    return False, t("КОД НЕВЕРЕН · ОСТАЛОСЬ ПОПЫТОК: {0}").format(MAX_TRIES - fail["count"])
