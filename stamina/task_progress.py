"""Ход параллельных задач агента: план из взвешенных шагов → процент → цвет.

Протокол (v2). Каждая задача агента — свой файл ``_orion/tasks/<id>.json``::

    {"version": 2, "id": "fix-glue", "title": "Починка склейки",
     "state": "working",            # planning | working | done | failed | stopped
     "steps": [{"name": "найти причину", "weight": 2, "done": true},
               {"name": "правило словаря", "weight": 3, "done": false},
               {"name": "тесты", "weight": 1, "done": false}],
     "updated": 1761200000.0}

Процент = вес закрытых шагов / вес всех шагов. Агент, получив задачу, оценивает
объём и пишет план (``plan``); закрывает шаги (``step``); пересматривает план тем
же ``plan`` — отметки «сделано» у шагов с тем же именем сохраняются, шкала
пересчитывается. В конце — ``finish``. Из консоли::

    python -m stamina.task_progress plan fix-glue "Починка склейки" "найти причину:2" "правило:3" "тесты"
    python -m stamina.task_progress step fix-glue "найти причину"      # или номер шага с 1
    python -m stamina.task_progress finish fix-glue [done|failed|stopped]

Старый одиночный доклад ``_orion/progress.json`` (v1) читается как ещё одна задача.
Модуль без Tk: его проверяют юнит-тесты.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
STATES = ("planning", "working", "done", "failed", "stopped")
FINAL = ("done", "failed", "stopped")
#: Сколько секунд без обновления — доклад устарел (как у v1).
STALE = 120
#: Сколько секунд закрытая задача ещё висит на панели.
KEEP = 900
MAX_TASKS = 8

# Мягкие опорные цвета шкалы: красный → оранжевый → жёлтый → жёлто-зелёный → зелёный.
STOPS = ((0, (0xD9, 0x6A, 0x5F)), (25, (0xE3, 0x93, 0x55)), (50, (0xE6, 0xC4, 0x5C)),
         (75, (0xAE, 0xC9, 0x5E)), (100, (0x6F, 0xBF, 0x73)))


def color_for(pct: float) -> str:
    """Цвет шкалы для процента: непрерывная (не ступенчатая) смесь опорных цветов."""
    try:
        p = float(pct)
    except (TypeError, ValueError):
        p = 0.0
    p = max(0.0, min(100.0, p))
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if p <= b:
            k = (p - a) / (b - a)
            rgb = [round(x + (y - x) * k) for x, y in zip(ca, cb)]
            return "#%02x%02x%02x" % tuple(rgb)
    return "#%02x%02x%02x" % STOPS[-1][1]


def tasks_dir() -> Path:
    override = os.environ.get("STAR_TYPING_TASKS_DIR", "").strip()
    if override:
        return Path(override)
    return PROJECT_DIR / "_orion" / "tasks"


def _safe_id(task_id) -> str:
    s = re.sub(r"[^\w\-]+", "-", str(task_id or "").strip(), flags=re.UNICODE).strip("-")
    return s[:60] or "task"


def _path(task_id) -> Path:
    return tasks_dir() / f"{_safe_id(task_id)}.json"


def _weight(value) -> float:
    try:
        w = float(value)
    except (TypeError, ValueError):
        return 1.0
    return w if w > 0 else 1.0


def parse_step(item) -> dict:
    """Шаг из строки ``"имя:вес"``, словаря или пары (имя, вес)."""
    if isinstance(item, dict):
        return {"name": str(item.get("name") or item.get("step") or "").strip(),
                "weight": _weight(item.get("weight", item.get("w", 1))),
                "done": bool(item.get("done"))}
    if isinstance(item, (tuple, list)):
        name, w = (list(item) + [1])[:2]
        return {"name": str(name).strip(), "weight": _weight(w), "done": False}
    text = str(item).strip()
    m = re.match(r"^(.*?):\s*(\d+(?:[.,]\d+)?)$", text)
    if m:
        return {"name": m.group(1).strip(), "weight": _weight(m.group(2).replace(",", ".")),
                "done": False}
    return {"name": text, "weight": 1.0, "done": False}


def _read(task_id) -> dict:
    try:
        data = json.loads(_path(task_id).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> dict:
    data["updated"] = time.time()
    path = _path(data["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return data


def plan(task_id, title: str = "", steps=(), state: str = "") -> dict:
    """Записать или пересмотреть план. Отметки «сделано» сохраняются по имени шага."""
    old = _read(task_id)
    was = {s.get("name"): bool(s.get("done")) for s in old.get("steps") or []
           if isinstance(s, dict)}
    new = []
    for item in steps:
        st = parse_step(item)
        if st["name"]:
            st["done"] = st["done"] or was.get(st["name"], False)
            new.append(st)
    st = state if state in STATES else ("working" if new else (old.get("state") or "planning"))
    data = {"version": 2, "id": _safe_id(task_id),
            "title": (str(title).strip() or str(old.get("title") or task_id))[:200],
            "state": st, "steps": new}
    return _write(data)


def step(task_id, which, done: bool = True) -> dict:
    """Закрыть шаг по имени или номеру (с 1)."""
    data = _read(task_id)
    steps = [s for s in data.get("steps") or [] if isinstance(s, dict)]
    if not steps:
        return data
    idx = None
    if isinstance(which, int) or str(which).strip().isdigit():
        n = int(which) - 1
        idx = n if 0 <= n < len(steps) else None
    else:
        for i, s in enumerate(steps):
            if s.get("name") == str(which).strip():
                idx = i
                break
    if idx is None:
        return data
    steps[idx]["done"] = bool(done)
    data["steps"] = steps
    if data.get("state") == "planning":
        data["state"] = "working"
    return _write(data)


def finish(task_id, state: str = "done") -> dict:
    data = _read(task_id) or {"version": 2, "id": _safe_id(task_id), "title": str(task_id),
                              "steps": []}
    data["state"] = state if state in FINAL else "done"
    return _write(data)


def remove(task_id) -> None:
    try:
        _path(task_id).unlink()
    except OSError:
        pass


def view(data: dict, now: float | None = None) -> dict:
    """Задача плюс вычисленное: процент по весам, шаги, возраст, устаревание."""
    now = time.time() if now is None else now
    steps = [s for s in data.get("steps") or [] if isinstance(s, dict)]
    total_w = sum(_weight(s.get("weight", 1)) for s in steps)
    done_w = sum(_weight(s.get("weight", 1)) for s in steps if s.get("done"))
    state = str(data.get("state") or "working")
    if state == "done":
        pct = 100.0
    else:
        pct = 100.0 * done_w / total_w if total_w else 0.0
    age = max(0.0, now - float(data.get("updated") or 0.0))
    return {"id": str(data.get("id") or ""), "title": str(data.get("title") or ""),
            "state": state, "percent": pct, "total": len(steps),
            "done": sum(1 for s in steps if s.get("done")),
            "age": age, "stale": state not in FINAL and age > STALE,
            "updated": float(data.get("updated") or 0.0)}


def from_legacy(v1: dict) -> dict:
    """Доклад v1 (`progress.json`: task/steps/done) → задача v2 с весами 1."""
    names = [str(s) for s in v1.get("steps") or []]
    try:
        closed = int(v1.get("done") or 0)
    except (TypeError, ValueError):
        closed = 0
    return {"id": "progress", "title": str(v1.get("task") or ""),
            "state": str(v1.get("state") or "working"),
            "steps": [{"name": n, "weight": 1, "done": i < closed} for i, n in enumerate(names)],
            "updated": v1.get("updated") or 0.0}


def active(now: float | None = None, legacy: dict | None = None) -> list[dict]:
    """Все задачи для панели: идущие и недавно закрытые, по времени постановки."""
    now = time.time() if now is None else now
    rows = []
    try:
        files = sorted(tasks_dir().glob("*.json"))
    except OSError:
        files = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and str(data.get("title") or "").strip():
            rows.append(view(data, now))
    if legacy and str(legacy.get("task") or "").strip():
        rows.append(view(from_legacy(legacy), now))
    rows = [r for r in rows if r["state"] not in FINAL or r["age"] <= KEEP]
    rows.sort(key=lambda r: (r["state"] in FINAL, -r["updated"]))
    return rows[:MAX_TASKS]


def brief_block(task_id) -> str:
    """Кусок ТЗ для агента: как докладывать план и ход (панель задач на пульте)."""
    tid = _safe_id(task_id)
    return "\n".join([
        "",
        "6. ДОКЛАД О ХОДЕ (полоска задачи на пульте Ориона)",
        f"— id задачи: {tid}. Сначала оцени объём и запиши план шагов с весами:",
        f'  python -m stamina.task_progress plan {tid} "<суть задачи>" "шаг 1:2" "шаг 2:3" "тесты:1"',
        f'— закрыл шаг: python -m stamina.task_progress step {tid} "шаг 1"',
        "— план изменился: снова plan с новым списком (закрытые шаги сохраняются);",
        f"— в конце: python -m stamina.task_progress finish {tid} (или failed/stopped).",
    ])


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(__doc__)
        return 2
    cmd, tid, rest = args[0], args[1], args[2:]
    if cmd == "plan":
        data = plan(tid, rest[0] if rest else "", rest[1:])
    elif cmd == "step":
        data = step(tid, rest[0] if rest else "1")
    elif cmd == "finish":
        data = finish(tid, rest[0] if rest else "done")
    else:
        print(__doc__)
        return 2
    print(f"{data.get('id')}: {round(view(data)['percent'])}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
