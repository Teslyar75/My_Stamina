"""Эфир — общая лента сообщений экипажа (фундамент будущего сетевого чата).

Сейчас это прототип на одном компьютере: сообщения лежат в общем файле
``<корень данных>/comm.json`` и видны всем пилотам этого экипажа. Так проверяется
сам механизм «пилоты переписываются» без сервера.

Интерфейс модуля намеренно повторяет будущее серверное API (``messages``, ``send``,
``unread``, ``mark_read``). Когда появится онлайн (I-001 «эфир флота»), эти функции
заменит сетевой клиент с тем же набором вызовов, а экран останется прежним.

Модуль не импортирует Tk — его проверяют тесты.

Формат ``comm.json``::

    {"version": 1,
     "messages": [{"id", "author", "callsign", "ts", "text"}],
     "read": {"<id пилота>": <время последнего прочтения>}}
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

MAX_TEXT = 500        # знаков в одном сообщении
MAX_MESSAGES = 500    # сколько последних сообщений храним
FILE_NAME = "comm.json"


def _root() -> Path:
    # ROOT_DIR меняется в tests/pilots.reset_root, поэтому берём его в момент вызова
    from stamina import pilots
    return Path(pilots.ROOT_DIR)


def path() -> Path:
    """Файл эфира (общий для всего экипажа)."""
    return _root() / FILE_NAME


def _empty() -> dict:
    return {"version": 1, "messages": [], "read": {}}


def load() -> dict:
    """Содержимое эфира; при отсутствии/порче файла — пустая лента (без исключений)."""
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("version", 1)
    if not isinstance(data.get("messages"), list):
        data["messages"] = []
    if not isinstance(data.get("read"), dict):
        data["read"] = {}
    return data


def save(data: dict) -> None:
    """Записать эфир: сначала во временный файл, потом замена (данные не бьются)."""
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.parent / (p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def messages() -> list[dict]:
    """Сообщения по порядку отправки (старые → новые)."""
    return load()["messages"]


def _clean(text: str) -> str:
    return " ".join((text or "").split())[:MAX_TEXT]


def send(author: str, callsign: str, text: str, *, ts: float | None = None) -> dict | None:
    """Добавить сообщение. Пустое — отбрасывается (возвращает None)."""
    body = _clean(text)
    if not body:
        return None
    msg = {
        "id": uuid.uuid4().hex[:12],
        "author": author or "",
        "callsign": (callsign or "").strip(),
        "ts": float(ts if ts is not None else time.time()),
        "text": body,
    }
    data = load()
    data["messages"].append(msg)
    if len(data["messages"]) > MAX_MESSAGES:
        data["messages"] = data["messages"][-MAX_MESSAGES:]
    data["read"][author or ""] = msg["ts"]      # своё сообщение сразу «прочитано»
    save(data)
    return msg


def unread(pid: str) -> int:
    """Сколько сообщений экипажа пилот ещё не видел (свои не считаются)."""
    if not pid:
        return 0
    data = load()
    last = float(data["read"].get(pid, 0.0))
    return sum(1 for m in data["messages"]
               if float(m.get("ts", 0.0)) > last and m.get("author") != pid)


def mark_read(pid: str, ts: float | None = None) -> None:
    """Отметить эфир прочитанным (по умолчанию — до последнего сообщения)."""
    if not pid:
        return
    data = load()
    if ts is None:
        ts = max((float(m.get("ts", 0.0)) for m in data["messages"]), default=0.0)
    if ts > float(data["read"].get(pid, 0.0)):
        data["read"][pid] = float(ts)
        save(data)
