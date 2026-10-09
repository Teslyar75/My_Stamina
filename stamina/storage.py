"""Хранение настроек, статистики и «груза» (своего текста).

Файлы лежат там же, где и раньше: ``%APPDATA%\\Stamina`` (на Linux —
``~/.stamina``). Файл ``session.json`` остался в прежнем формате, поэтому
незаконченный текст из старой версии продолжится с того же места.
Кэш переводов — в папке программы (``cache``), чтобы не занимать диск C:.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from stamina.session_storage import SESSION_PATH

DATA_DIR = SESSION_PATH.parent
SETTINGS_PATH = DATA_DIR / "settings.json"
STATS_PATH = DATA_DIR / "stats.json"
CARGO_PATH = DATA_DIR / "cargo.txt"
CARGO_RAW_PATH = DATA_DIR / "cargo_original.txt"

PROJECT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_DIR / "cache"

DEFAULT_SETTINGS = {
    "sound": True,
    "volume": 3,
    "stars": True,
    "keyboard": True,
    "zones": True,
    "font": "M",
    "lang": "en",
    "translator": True,
    # Подготовка своего текста: убрать заглавные, знаки препинания, лишние пробелы
    "cargo_opts": {"lower": True, "punct": True, "spaces": True},
    "geometry": "",
    "living_space": "full",   # «Живой космос» на мостике: off | light | full (прототип)
}

MAX_RUNS = 500


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def write_json(path: Path, data: dict) -> None:
    """Атомарная запись: сначала *.tmp, потом замена."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


class Store:
    def __init__(self) -> None:
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update(_read_json(SETTINGS_PATH) or {})
        stats = _read_json(STATS_PATH) or {}
        self.stats = {
            "version": 1,
            "runs": list(stats.get("runs", [])),
            "keys": dict(stats.get("keys", {})),
            "missions": dict(stats.get("missions", {})),
            "xp": int(stats.get("xp", 0)),
            "total_time": float(stats.get("total_time", 0.0)),
            "total_chars": int(stats.get("total_chars", 0)),
        }
        self._dirty = False

    # -- Настройки ----------------------------------------------------
    def save_settings(self) -> None:
        write_json(SETTINGS_PATH, self.settings)

    # -- Статистика ---------------------------------------------------
    def record_key(self, char: str, ok: bool) -> None:
        if not char or char == " ":
            return
        rec = self.stats["keys"].setdefault(char.lower(), [0, 0])
        rec[0 if ok else 1] += 1
        self._dirty = True

    def key_error_rates(self, min_total: int = 8) -> dict[str, float]:
        out = {}
        for ch, (hits, misses) in self.stats["keys"].items():
            total = hits + misses
            if total >= min_total:
                out[ch] = misses / total
        return out

    def weakest_keys(self, lang: str | None = None, count: int = 5) -> list[tuple[str, float]]:
        from stamina.layouts import is_cyrillic
        rates = self.key_error_rates()
        items = [(ch, r) for ch, r in rates.items() if r > 0 and ch.isalnum()]
        if lang == "ru":
            items = [x for x in items if is_cyrillic(x[0])]
        elif lang == "en":
            items = [x for x in items if not is_cyrillic(x[0])]
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:count]

    def add_run(self, run: dict) -> None:
        run = dict(run)
        run.setdefault("ts", time.time())
        self.stats["runs"].append(run)
        self.stats["runs"] = self.stats["runs"][-MAX_RUNS:]
        self.stats["total_time"] += run.get("elapsed", 0.0)
        self.stats["total_chars"] += run.get("chars", 0)
        self.stats["xp"] += run.get("xp", 0)
        self.save_stats()

    def mission_record(self, mid: str) -> dict:
        return self.stats["missions"].get(mid, {})

    def update_mission(self, mid: str, stars: int, cpm: float, acc: float) -> None:
        rec = self.stats["missions"].setdefault(mid, {"stars": 0, "best_cpm": 0, "best_acc": 0})
        rec["stars"] = max(rec.get("stars", 0), stars)
        rec["best_cpm"] = max(rec.get("best_cpm", 0), round(cpm, 1))
        rec["best_acc"] = max(rec.get("best_acc", 0), round(acc, 1))

    def is_unlocked(self, mission: dict) -> bool:
        if mission["num"] == 1:
            return True
        prev = f"{mission['lang']}-{mission['num'] - 1:02d}"
        return self.mission_record(prev).get("stars", 0) > 0

    def save_stats(self, force: bool = True) -> None:
        if force or self._dirty:
            write_json(STATS_PATH, self.stats)
            self._dirty = False

    def reset_stats(self) -> None:
        self.stats.update(runs=[], keys={}, missions={}, xp=0, total_time=0.0, total_chars=0)
        self.save_stats()

    # -- Груз (свой текст) --------------------------------------------
    def load_cargo(self) -> tuple[str, str]:
        return _read_text(CARGO_PATH), _read_text(CARGO_RAW_PATH)

    def save_cargo(self, adapted: str, original: str) -> None:
        _write_text(CARGO_PATH, adapted)
        _write_text(CARGO_RAW_PATH, original)
