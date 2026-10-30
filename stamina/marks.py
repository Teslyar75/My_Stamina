"""Геолокация курсора: правая кнопка мыши ставит пометку на борту.

Пилот называет место словами («вот эта кнопка», «тут не влезает») и щёлкает
правой клавишей. Орион запоминает точку: отсек, подвкладку, виджет под курсором,
координаты в пикселях и долю окна — доля нужна, чтобы пометка не «уехала», если
окно потом перетащили или развернули.

Дальше эти пометки уходят подчинённому агенту вместе с пожеланием пилота:
у него на руках не «где-то в интерфейсе», а конкретный отсек и конкретное место.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from stamina import pilots

REL = Path("orion") / "marks.json"
LIMIT = 200          # сколько пометок храним
KEEP_FOR_TASK = 3    # сколько последних отдаём агенту в задании


def marks_path() -> Path:
    return pilots.ROOT_DIR / REL


def load() -> list[dict]:
    path = marks_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save(items: list[dict]) -> None:
    path = marks_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def add(x: int, y: int, zone: str, subtab: str = "", widget: str = "",
        root: tuple[int, int] | None = None, note: str = "") -> dict:
    """Записать точку. Координаты — относительно окна корабля."""
    w, h = root or (0, 0)
    items = load()
    mark = {
        "id": max(int(time.time() * 1000), last_id() + 1),   # строго растёт, даже в одну мс
        "ts": int(time.time()),
        "x": int(x),
        "y": int(y),
        "nx": round(x / w, 4) if w else 0.0,
        "ny": round(y / h, 4) if h else 0.0,
        "root": [int(w), int(h)],
        "zone": zone or "",
        "subtab": subtab or "",
        "widget": widget or "",
        "note": note or "",
    }
    items.append(mark)
    if len(items) > LIMIT:
        items = items[-LIMIT:]
    _save(items)
    return mark


def last_id() -> int:
    items = load()
    return items[-1]["id"] if items else 0


def recent(n: int = KEEP_FOR_TASK) -> list[dict]:
    return load()[-n:] if n > 0 else []


def since(mark_id: int, n: int = KEEP_FOR_TASK) -> list[dict]:
    """Пометки новее указанной (то есть поставленные после прошлого задания)."""
    items = [m for m in load() if m.get("id", 0) > int(mark_id or 0)]
    return items[-n:] if n > 0 else items


def describe(mark: dict) -> str:
    """Короткая подпись для строки состояния: «МОСТИК · кнопка ПЕЧАТЬ · 312, 640»."""
    parts = [mark.get("zone") or "?"]
    if mark.get("subtab"):
        parts[0] = f"{parts[0]} / {mark['subtab']}"
    if mark.get("widget"):
        parts.append(mark["widget"])
    parts.append(f"{mark.get('x', 0)}, {mark.get('y', 0)}")
    return " · ".join(parts)


def place_line(mark: dict) -> str:
    """Адрес точки одной строкой — его пилот вставляет в окно задания.

    Формат совпадает со строкой из блока для агента, чтобы ТЗ и пометка
    на борту говорили об одном и том же месте одинаковыми словами.
    """
    when = time.strftime("%H:%M:%S", time.localtime(mark.get("ts", 0)))
    w, h = (mark.get("root") or [0, 0])[:2]
    parts = [mark.get("zone") or "?"]
    if mark.get("subtab"):
        parts.append(mark["subtab"])
    if mark.get("widget"):
        parts.append(mark["widget"])
    return (
        " / ".join(parts)
        + f" — окно {w}x{h}, точка {mark.get('x')},{mark.get('y')}"
        + f" (доля {mark.get('nx')}, {mark.get('ny')}), {when}"
    )


def context_block(mark_id: int = 0, n: int = KEEP_FOR_TASK) -> str:
    """Блок для агента: куда именно указывал пилот. Пусто — если пометок нет."""
    items = since(mark_id, n) if mark_id else recent(n)
    if not items:
        return ""
    lines = ["МЕСТА, КОТОРЫЕ ПОКАЗАЛ ПИЛОТ (правая кнопка мыши):"]
    for i, m in enumerate(items, 1):
        lines.append(f"{i}. {place_line(m)}")
        if m.get("note"):
            lines.append(f"   слова пилота: {m['note']}")
    return "\n".join(lines)


def clear() -> None:
    _save([])
