"""Ленивый словарь: лёгкий индекс + чанки по первой букве slug.

Исходный `data/vocab.json` не трогаем. При первом чтении рядом с данными пилота
собирается кэш `vocab_lazy_v1/` (индекс + чанки). Повторные запуски читают только
индекс (~лёгкие поля); полные карточки (предложения, определения…) — по запросу.
"""
from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path

CACHE_VERSION = 1
CACHE_NAME = "vocab_lazy_v1"

# Поля, которые держим в RAM для списков / поиска / наборов.
LIGHT_KEYS = (
    "id", "word", "slug", "rank", "level", "sets", "pos", "pos_all",
    "difficulty", "ru", "ru_src", "tags", "ipa", "n_sentences",
)

# Тяжёлые поля — в чанках на диске, подтягиваются в LazyWord по доступу.
HEAVY_KEYS = (
    "sentences", "definition", "definition_source", "example", "example_ru",
    "example_source", "guide", "notes", "common_mistakes", "sounds_like",
    "respelling", "syllables", "syllable_breakdown",
)


def cache_root(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir) / CACHE_NAME
    from . import paths
    return paths.stamina_data_dir() / CACHE_NAME


def _meta_path(root: Path) -> Path:
    return root / "meta.json"


def _index_path(root: Path) -> Path:
    return root / "index.json.gz"


def _chunk_path(root: Path, letter: str) -> Path:
    safe = letter if letter.isascii() and letter.isalpha() else "_"
    return root / "chunks" / f"{safe}.json.gz"


def chunk_letter(slug: str) -> str:
    if not slug:
        return "_"
    ch = slug[0].lower()
    return ch if ch.isascii() and ch.isalpha() else "_"


def source_stamp(vocab_path: Path, extra_paths: list[Path] | None = None) -> dict:
    paths = [vocab_path] + list(extra_paths or [])
    parts = []
    for p in paths:
        if p.exists():
            st = p.stat()
            parts.append({"path": str(p.resolve()), "mtime_ns": st.st_mtime_ns, "size": st.st_size})
        else:
            parts.append({"path": str(p), "mtime_ns": 0, "size": 0})
    return {"version": CACHE_VERSION, "sources": parts}


def cache_valid(root: Path, stamp: dict) -> bool:
    meta_p = _meta_path(root)
    idx = _index_path(root)
    if not meta_p.is_file() or not idx.is_file():
        return False
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except Exception:
        return False
    return meta.get("version") == stamp["version"] and meta.get("sources") == stamp["sources"]


def light_record(rec: dict) -> dict:
    out = {k: rec.get(k) for k in LIGHT_KEYS if k != "n_sentences"}
    sents = rec.get("sentences") or []
    if not sents and rec.get("example"):
        n = 1
    else:
        n = sum(1 for x in sents if isinstance(x, dict) and x.get("en"))
    out["n_sentences"] = n
    out.setdefault("slug", (rec.get("word") or "").lower())
    return out


def heavy_record(rec: dict) -> dict:
    return {k: rec.get(k) for k in HEAVY_KEYS}


def _write_json_gz(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # атомарно: во временный файл рядом, потом replace
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        with gzip.open(tmp_path, "wb", compresslevel=6) as f:
            f.write(raw)
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _read_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def build_cache(words: list[dict], stamp: dict, root: Path | None = None) -> Path:
    """Построить индекс + чанки. Исходный vocab.json не изменяет и не удаляет."""
    root = root or cache_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "chunks").mkdir(parents=True, exist_ok=True)
    light = [light_record(w) for w in words]
    chunks: dict[str, dict[str, dict]] = {}
    for w in words:
        slug = w.get("slug") or (w.get("word") or "").lower()
        letter = chunk_letter(slug)
        chunks.setdefault(letter, {})[slug] = heavy_record(w)
    _write_json_gz(_index_path(root), light)
    # удалить устаревшие чанки, затем записать новые
    for old in (root / "chunks").glob("*.json.gz"):
        old.unlink(missing_ok=True)
    for letter, payload in chunks.items():
        _write_json_gz(_chunk_path(root, letter), payload)
    meta = dict(stamp)
    meta["word_count"] = len(light)
    meta["letters"] = sorted(chunks.keys())
    _meta_path(root).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def load_index(root: Path) -> list[dict]:
    return _read_json_gz(_index_path(root))


class ChunkStore:
    """Кэш чанков в памяти процесса (один letter — один файл)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._loaded: dict[str, dict[str, dict]] = {}

    def get(self, slug: str) -> dict | None:
        letter = chunk_letter(slug)
        if letter not in self._loaded:
            path = _chunk_path(self.root, letter)
            if not path.is_file():
                self._loaded[letter] = {}
            else:
                try:
                    self._loaded[letter] = _read_json_gz(path)
                except Exception:
                    self._loaded[letter] = {}
        return self._loaded[letter].get(slug)


class LazyWord(dict):
    """dict с лёгкими полями; тяжёлые ключи подгружаются из ChunkStore."""

    __slots__ = ("_store", "_hydrated")

    def __init__(self, light: dict, store: ChunkStore | None) -> None:
        super().__init__(light)
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_hydrated", store is None)

    def hydrate(self) -> None:
        if object.__getattribute__(self, "_hydrated"):
            return
        store = object.__getattribute__(self, "_store")
        object.__setattr__(self, "_hydrated", True)
        if store is None:
            return
        slug = super().get("slug") or ""
        heavy = store.get(slug)
        if heavy:
            super().update(heavy)

    def __getitem__(self, key):
        if key in HEAVY_KEYS:
            self.hydrate()
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in HEAVY_KEYS:
            self.hydrate()
        return super().get(key, default)

    def __contains__(self, key):
        if key in HEAVY_KEYS:
            return True
        return super().__contains__(key)

    def setdefault(self, key, default=None):
        if key in HEAVY_KEYS:
            self.hydrate()
        return super().setdefault(key, default)
