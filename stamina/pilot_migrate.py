"""Миграция прежних данных в пилота №1 (SPEC_PILOTS §7). Без потерь и идемпотентно.

1. Нет pilots.json, но в корне есть данные → резервная копия корня (кроме backups/) с проверкой SHA-256.
2. Пилот №1 «George Orwell» / «1984», эмблема ★, cyan, кода нет, pin_setup_pending = true.
3. Файлы данных КОПИРУЮТСЯ в pilots/<id>/ с проверкой SHA-256.
4. pilots.json пишется последним — точка фиксации (до неё миграция повторяется с начала).
5. Старые файлы в корне переименовываются в *.migrated (если файл занят — остаётся, это пишется в лог;
   позже его подхватит late_sync()).
"""
from __future__ import annotations

from stamina.i18n import t

import shutil
import time
import traceback
from pathlib import Path

from stamina import pilots

FIRST_CALLSIGN = "George Orwell"
FIRST_NAME = "1984"


def legacy_items(root: Path) -> list[Path]:
    out = [root / f for f in pilots.DATA_FILES if (root / f).is_file()]
    out += [root / d for d in pilots.DATA_DIRS if (root / d).is_dir()]
    return out


def _all_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file())


def backup_root(root: Path) -> Path:
    """Копия корня (кроме backups/ и pilots/) с проверкой числа файлов и SHA-256."""
    dest = root / "backups" / f"pre-pilots-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.mkdir(parents=True, exist_ok=False)
    count = 0
    for item in sorted(root.iterdir()):
        if item.name in ("backups", "pilots"):
            continue
        for f in _all_files(item):
            rel = f.relative_to(root)
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            if pilots.sha256_file(f) != pilots.sha256_file(out):
                raise OSError(t("Копия не совпала: {0}").format(rel))
            count += 1
    copied = len([p for p in dest.rglob("*") if p.is_file()])
    if copied != count:
        raise OSError(t("Число файлов в резервной копии не совпало"))
    return dest


def copy_verified(src: Path, dst: Path) -> None:
    pairs = [(src, dst)] if src.is_file() else [(f, dst / f.relative_to(src)) for f in _all_files(src)]
    for f, out in pairs:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        if pilots.sha256_file(f) != pilots.sha256_file(out):
            raise OSError(t("Копия не совпала: {0}").format(f.name))


def migrate(root: Path | None = None) -> dict:
    """Выполнить миграцию, если нужно. → отчёт {"done": bool, ...}. Никогда не бросает исключений."""
    root = Path(root) if root else pilots.ROOT_DIR
    if pilots.load_registry() is not None:
        return {"done": False, "reason": "already"}
    items = legacy_items(root)
    if not items:
        return {"done": False, "reason": "fresh"}
    try:
        backup = backup_root(root)
        # незавершённая прошлая попытка: папки без реестра — убрать в backups, не удалять
        if pilots.pilots_dir().exists():
            stale = root / "backups" / f"incomplete-pilots-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.move(str(pilots.pilots_dir()), str(stale))
        pid = pilots.new_id()
        d = pilots.pilot_dir(pid)
        d.mkdir(parents=True)
        for it in items:
            copy_verified(it, d / it.name)
        settings = pilots.read_json(root / "settings.json") or {}
        app = pilots.load_app()
        app["geometry"] = settings.get("geometry", "") or app.get("geometry", "")
        pilots.save_app(app)
        entry = {"id": pid, "callsign": FIRST_CALLSIGN, "name": FIRST_NAME, "accent": "cyan",
                 "avatar": {"kind": "builtin", "glyph": "star"}, "locked": False,
                 "pin_setup_pending": True, "created": pilots.now_iso(), "last_seen": None,
                 "migrated_from": str(root)}
        pilots.save_profile(pid, dict(entry, pin_fail={"count": 0, "until": None, "level": 0}))
        migrated_at = time.time()
        # точка фиксации
        pilots.save_registry({"version": pilots.FORMAT_VERSION, "ask_on_start": True, "last_pilot": pid,
                              "migrated_at": migrated_at, "backup": str(backup), "pilots": [entry]})
    except Exception:  # noqa: BLE001
        pilots.log_error(t("Миграция отменена, данные не тронуты:\n") + traceback.format_exc())
        return {"done": False, "reason": "error"}
    busy = []
    for it in items:
        try:
            it.rename(it.with_name(it.name + ".migrated"))
        except OSError:
            busy.append(it.name)
    if busy:
        pilots.log_error(t("Файлы заняты, остались в корне (подхватит late_sync): ") + ", ".join(busy))
    return {"done": True, "id": pid, "backup": str(backup), "busy": busy}


def late_sync(root: Path | None = None) -> list[str]:
    """Если после миграции старая копия программы ещё писала в корень, перенести её свежие файлы
    в пилота №1 — только если файл пилота с тех пор не менялся. Иначе оставить оба и записать в лог."""
    root = Path(root) if root else pilots.ROOT_DIR
    reg = pilots.load_registry()
    if not reg or not reg.get("migrated_at") or not reg.get("pilots"):
        return []
    t0 = float(reg["migrated_at"])
    first = next((p for p in reg["pilots"] if p.get("migrated_from")), None)
    if first is None:
        return []
    d = pilots.pilot_dir(first["id"])
    moved = []
    for name in pilots.DATA_FILES:
        src = root / name
        if not src.is_file() or src.stat().st_mtime <= t0:
            continue
        dst = d / name
        try:
            if dst.exists() and dst.stat().st_mtime > t0 + 1:
                pilots.log_error(t("late_sync: {0} изменён и в корне, и у пилота — оставлены оба").format(name))
                continue
            bdir = root / "backups" / f"late-sync-{time.strftime('%Y%m%d-%H%M%S')}"
            bdir.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.copy2(dst, bdir / name)
            shutil.copy2(src, dst)
            if pilots.sha256_file(src) != pilots.sha256_file(dst):
                raise OSError("hash")
            src.rename(src.with_name(name + ".migrated-late"))
            moved.append(name)
        except OSError:
            pilots.log_error("late_sync:\n" + traceback.format_exc())
    return moved
