"""Резервные копии данных пилота: раз в сутки, с ротацией.

Ночь 20 октября показала цену ошибки: код возвращается из git за минуту, а потерянный
прогресс — нет. Копии лежат рядом с данными, в ``<root>/backups/<ГГГГ-ММ-ДД-ЧЧММ>``.
Копирование дешёвое (десятки килобайт), поэтому запускается при старте.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

#: Сколько копий хранить (по одной в сутки).
KEEP = 7

#: Файлы состояния. Отсутствующие просто пропускаются.
FILES = (
    "app.json",
    "pilots.json",
    "owner.json",
    "library.json",
    "speedread.json",
    "english.json",
    "settings.json",
)

#: Папки состояния (переписка Ориона и прочие журналы).
FOLDERS = ("orion",)

#: Метка времени в имени копии.
STAMP = "%Y-%m-%d-%H%M"


def _root() -> Path:
    from stamina import pilots

    return Path(pilots.ROOT_DIR)


def backups_dir() -> Path:
    return _root() / "backups"


def list_backups() -> list[Path]:
    """Список готовых копий, свежие первыми."""
    folder = backups_dir()
    if not folder.is_dir():
        return []
    items = [p for p in folder.iterdir() if p.is_dir()]
    return sorted(items, key=lambda p: p.name, reverse=True)


def _prune(keep: int = KEEP) -> None:
    for old in list_backups()[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def make_backup(*, keep: int = KEEP, force: bool = False, now: float | None = None) -> Path | None:
    """Сделать копию данных. Возвращает папку копии или None, если копия уже есть.

    Без ``force`` копия делается не чаще раза в сутки: имя содержит дату, и вторая
    копия за тот же день просто перезаписала бы первую.
    """
    root = _root()
    if not root.is_dir():
        return None
    stamp = time.strftime(STAMP, time.localtime(now))
    day = stamp[:10]
    existing = list_backups()
    if not force and any(p.name.startswith(day) for p in existing):
        return None

    target = backups_dir() / stamp
    suffix = 1
    while target.exists():
        suffix += 1
        target = backups_dir() / f"{stamp}-{suffix}"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    copied = False
    for name in FILES:
        src = root / name
        if src.is_file():
            try:
                shutil.copy2(src, target / name)
                copied = True
            except OSError:
                pass
    for name in FOLDERS:
        src = root / name
        if src.is_dir():
            try:
                shutil.copytree(src, target / name, dirs_exist_ok=True)
                copied = True
            except OSError:
                pass

    if not copied:
        shutil.rmtree(target, ignore_errors=True)
        return None
    _prune(keep)
    return target


def restore(name: str | Path, *, keep_current: bool = True) -> Path:
    """Вернуть данные из копии. Текущее состояние сначала сохраняется отдельной копией."""
    source = Path(name)
    if not source.is_absolute():
        source = backups_dir() / str(name)
    if not source.is_dir():
        raise FileNotFoundError(str(source))
    if keep_current:
        make_backup(force=True)
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        dest = root / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        except OSError:
            continue
    return source


def summary() -> str:
    """Короткая строка для интерфейса: когда делалась последняя копия."""
    items = list_backups()
    if not items:
        return ""
    return items[0].name
