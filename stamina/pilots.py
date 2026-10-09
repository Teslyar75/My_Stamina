"""Экипаж: реестр пилотов и папка данных активного пилота.

Модуль не импортирует остальной Star Typing и должен вызываться ДО импорта
``stamina.storage``: ``session_storage._session_dir()`` берёт папку из ``active_dir()``.

Корень данных — ``%APPDATA%\\Stamina`` (``~/.stamina`` вне Windows) = ``ROOT_DIR``.
  pilots.json            реестр экипажа
  app.json               общие настройки окна (geometry, ask_on_start, last_pilot)
  pilots/<id>/           данные пилота (settings.json, stats.json, session.json, english.json, …)
  backups/               копия до миграции, списанные пилоты
"""
from __future__ import annotations

from stamina.i18n import t

import hashlib
import json
import os
import re
import secrets
import shutil
import time
import zipfile
from pathlib import Path

FORMAT_VERSION = 1
ACCENTS = ("cyan", "amber", "green", "red", "purple")
CALLSIGN_RE = re.compile(r"^[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё \-]{1,15}$")
# файлы данных пилота (форматы как раньше; меняется только место)
DATA_FILES = ("settings.json", "stats.json", "session.json", "cargo.txt", "cargo_original.txt",
              "english.json", "speedread.json", "translations.json", "achievements.json")
DATA_DIRS = ("library",)


def default_root() -> Path:
    """Корень данных: Windows — %APPDATA%\\Stamina; Linux — ~/.local/share/StarTyping
    (или $XDG_DATA_HOME/StarTyping; прежняя папка ~/.stamina, если уже есть, остаётся)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Stamina"
    old = Path.home() / ".stamina"
    if old.exists():
        return old
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "StarTyping"


def _root() -> Path:
    return default_root()


ROOT_DIR = _root()
_active: dict | None = None


def reset_root(root: Path | None = None) -> None:
    """Для тестов: перечитать корень (после подмены APPDATA)."""
    global ROOT_DIR, _active
    ROOT_DIR = Path(root) if root else _root()
    _active = None


def registry_path() -> Path:
    return ROOT_DIR / "pilots.json"


def app_path() -> Path:
    return ROOT_DIR / "app.json"


def pilots_dir() -> Path:
    return ROOT_DIR / "pilots"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log_error(text: str, name: str = "pilots_error.log") -> None:
    try:
        ROOT_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROOT_DIR / name, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------- реестр
def load_registry() -> dict | None:
    """pilots.json или None (миграция ещё не выполнялась)."""
    d = read_json(registry_path())
    if d is None or not isinstance(d.get("pilots"), list):
        return None
    d.setdefault("ask_on_start", True)
    return d


def save_registry(reg: dict) -> None:
    write_json(registry_path(), reg)


def load_app() -> dict:
    d = read_json(app_path()) or {}
    d.setdefault("geometry", "")
    return d


def save_app(d: dict) -> None:
    write_json(app_path(), d)


def pilots() -> list[dict]:
    reg = load_registry()
    return list(reg["pilots"]) if reg else []


def get(pid: str) -> dict | None:
    for p in pilots():
        if p["id"] == pid:
            return p
    return None


def find(key: str) -> dict | None:
    """Пилот по id или позывному (без учёта регистра)."""
    k = (key or "").strip().casefold()
    for p in pilots():
        if p["id"].casefold() == k or p["callsign"].casefold() == k:
            return p
    return None


def pilot_dir(pid: str) -> Path:
    return pilots_dir() / pid


def profile(pid: str) -> dict:
    return read_json(pilot_dir(pid) / "profile.json") or {"id": pid}


def save_profile(pid: str, prof: dict) -> None:
    write_json(pilot_dir(pid) / "profile.json", prof)


def update_pilot(pid: str, **fields) -> dict | None:
    """Изменить запись пилота в реестре и в profile.json."""
    reg = load_registry()
    if not reg:
        return None
    for p in reg["pilots"]:
        if p["id"] == pid:
            p.update(fields)
            save_registry(reg)
            prof = profile(pid)
            prof.update({k: v for k, v in fields.items() if k not in ("summary",)})
            save_profile(pid, prof)
            return p
    return None


def new_id() -> str:
    while True:
        pid = f"p-{time.strftime('%Y%m%d')}-{secrets.token_hex(2)}"
        if not pilot_dir(pid).exists():
            return pid


def validate_callsign(callsign: str, exclude: str | None = None) -> str:
    """'' — можно, иначе текст ошибки."""
    c = (callsign or "").strip()
    if len(c) < 2:
        return t("Слишком короткий позывной (от 2 символов)")
    if len(c) > 16:
        return t("Слишком длинный позывной (до 16 символов)")
    if not CALLSIGN_RE.match(c):
        return t("Недопустимые символы: только буквы, цифры, пробел и дефис")
    for p in pilots():
        if p["id"] != exclude and p["callsign"].casefold() == c.casefold():
            return t("Позывной занят")
    return ""


def free_callsign(base: str) -> str:
    base = base.strip()[:13] or t("Пилот")
    if not validate_callsign(base):
        return base
    for i in range(2, 100):
        c = f"{base}-{i}"
        if not validate_callsign(c):
            return c
    return f"{base[:8]}-{secrets.token_hex(2)}"


def create(callsign: str, *, name: str = "", accent: str = "cyan", avatar: dict | None = None,
           copy_settings_from: str | None = None, pid: str | None = None) -> dict:
    err = validate_callsign(callsign)
    if err:
        raise ValueError(err)
    reg = load_registry() or {"version": FORMAT_VERSION, "ask_on_start": True, "last_pilot": None,
                                "pilots": []}
    pid = pid or new_id()
    d = pilot_dir(pid)
    d.mkdir(parents=True, exist_ok=True)
    if copy_settings_from:
        src = pilot_dir(copy_settings_from) / "settings.json"
        if src.exists():
            s = read_json(src) or {}
            s.pop("geometry", None)
            write_json(d / "settings.json", s)
    entry = {"id": pid, "callsign": callsign.strip(), "name": name.strip(),
             "accent": accent if accent in ACCENTS else "cyan",
             "avatar": avatar or {"kind": "builtin", "glyph": "star"},
             "locked": False, "pin_setup_pending": False, "created": now_iso(), "last_seen": None}
    reg["pilots"].append(entry)
    save_registry(reg)
    save_profile(pid, dict(entry, pin_fail={"count": 0, "until": None, "level": 0}))
    return entry


def delete(pid: str, active: str | None = None) -> Path:
    """Списать пилота: папка → backups/deleted/<позывной>-<время>. Не активного и не последнего."""
    reg = load_registry()
    if not reg:
        raise ValueError(t("Экипаж пуст"))
    if pid == active:
        raise ValueError(t("Нельзя списать пилота, который сейчас в кабине"))
    if len(reg["pilots"]) <= 1:
        raise ValueError(t("Нельзя списать последнего пилота"))
    p = next((x for x in reg["pilots"] if x["id"] == pid), None)
    if p is None:
        raise ValueError(t("Пилот не найден"))
    safe = re.sub(r"[^0-9A-Za-zА-Яа-яЁё\-]+", "_", p["callsign"])
    dest = ROOT_DIR / "backups" / "deleted" / f"{safe}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if pilot_dir(pid).exists():
        shutil.move(str(pilot_dir(pid)), str(dest))
    reg["pilots"] = [x for x in reg["pilots"] if x["id"] != pid]
    if reg.get("last_pilot") == pid:
        reg["last_pilot"] = reg["pilots"][0]["id"]
    save_registry(reg)
    return dest


# ---------------------------------------------------------------------------- активный пилот
def activate(pid: str) -> Path:
    """Сделать пилота активным в этом процессе (до импорта stamina.storage)."""
    global _active
    reg = load_registry()
    if not reg:
        raise ValueError(t("Реестр пилотов не найден"))
    p = next((x for x in reg["pilots"] if x["id"] == pid), None)
    if p is None:
        raise ValueError(t("Пилот не найден"))
    pilot_dir(pid).mkdir(parents=True, exist_ok=True)
    p["last_seen"] = now_iso()
    reg["last_pilot"] = pid
    save_registry(reg)
    _active = dict(p)
    return pilot_dir(pid)


def active() -> dict | None:
    return _active


def active_dir() -> Path:
    """Папка данных: активного пилота, иначе (без реестра) — прежний корень."""
    if _active is not None:
        return pilot_dir(_active["id"])
    env = os.environ.get("STAMINA_PILOT_DIR")
    if env:
        return Path(env)
    return ROOT_DIR


# ---------------------------------------------------------------------------- экспорт / импорт
def _pilot_files(pid: str) -> list[Path]:
    d = pilot_dir(pid)
    out = []
    for p in sorted(d.rglob("*")):
        if p.is_file() and not p.name.endswith((".tmp", ".log")):
            out.append(p)
    return out


def export(pid: str, dest: Path, app_version: str = "") -> Path:
    p = get(pid)
    if p is None:
        raise ValueError(t("Пилот не найден"))
    d = pilot_dir(pid)
    files = _pilot_files(pid)
    manifest = {"format": "stpilot", "version": FORMAT_VERSION, "app": app_version, "exported": now_iso(),
                "pilot": {k: v for k, v in p.items() if k != "summary"},
                "files": {f.relative_to(d).as_posix(): sha256_file(f) for f in files}}
    dest = Path(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for f in files:
            z.write(f, "data/" + f.relative_to(d).as_posix())
    return dest


def read_package(path: Path) -> dict:
    """Проверить .stpilot → manifest (исключение, если файл повреждён)."""
    with zipfile.ZipFile(path) as z:
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        if man.get("format") != "stpilot":
            raise ValueError(t("Это не файл пилота Star Typing"))
        for rel, h in man.get("files", {}).items():
            if ".." in rel.split("/"):
                raise ValueError(t("Недопустимый путь в архиве"))
            if hashlib.sha256(z.read("data/" + rel)).hexdigest() != h:
                raise ValueError(t("Файл повреждён: {0}").format(rel))
    return man


def import_package(path: Path, callsign: str | None = None) -> dict:
    """Импорт: всегда новый id; позывной — свободный (или указанный)."""
    man = read_package(path)
    src = man["pilot"]
    cs = callsign or free_callsign(src.get("callsign", t("Пилот")))
    err = validate_callsign(cs)
    if err:
        raise ValueError(err)
    pid = new_id()
    d = pilot_dir(pid)
    d.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        for rel in man["files"]:
            out = d / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(z.read("data/" + rel))
    reg = load_registry() or {"version": FORMAT_VERSION, "ask_on_start": True, "last_pilot": None,
                                "pilots": []}
    entry = {k: v for k, v in src.items() if k in ("name", "accent", "avatar", "locked", "pin_setup_pending")}
    entry.update(id=pid, callsign=cs, created=now_iso(), last_seen=None, imported=now_iso())
    reg["pilots"].append(entry)
    save_registry(reg)
    prof = read_json(d / "profile.json") or {}
    prof.update(entry)
    save_profile(pid, prof)
    return entry
