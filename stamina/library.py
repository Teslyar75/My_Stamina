"""Общая библиотека текстов Star Typing: оригинал + подготовленная для печати версия.

Каждый текст хранится в двух версиях (docs/speedread/TEXT_LIBRARY.md):
* ``original.txt`` — как загружено (заглавные, пунктуация, абзацы) — для «СКОРОЧТЕНИЯ»;
* ``prepared.txt`` — ``text_processing.process_text(original, **opts)`` — для печати.

Папка: ``%APPDATA%\\Stamina\\library`` (рядом с остальными данными пилота). Файлы пишутся
атомарно. ``session.json`` и ``cargo*.txt`` библиотека не меняет без явной команды.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from stamina.text_processing import process_text
from stamina.textmap import TextMap, fragment_of

DEFAULT_OPTS = {"lower": True, "punct": True, "spaces": True, "translit": False, "yo": False}
PROCESSOR = "text_processing v1"
MAX_CANDIDATE_BYTES = 20 * 1024 * 1024
ORWELL_HEAD = "part one chapter 1 it was a bright cold day in april"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm_opts(opts: dict | None) -> dict:
    o = dict(DEFAULT_OPTS)
    o.update({k: bool(v) for k, v in (opts or {}).items() if k in DEFAULT_OPTS})
    return o


def processor(opts: dict | None) -> Callable[[str], str]:
    o = norm_opts(opts)
    return lambda t: process_text(t, lower=o["lower"], punct=o["punct"], spaces=o["spaces"],
                                  translit=o["translit"], yo=o["yo"])


def read_text_file(path: str | Path) -> tuple[str, str]:
    """Прочитать текстовый файл (utf-8 / cp1251, как «СВОЙ ТЕКСТ»). → (текст, кодировка)."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc).replace("\r\n", "\n").replace("\r", "\n"), enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, _t("неизвестная кодировка"))


def _write_atomic(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def detect_lang(text: str) -> str:
    """Язык книги (ru, uk, en, de, fr …) — stamina.langdetect, без интернета."""
    from stamina.langdetect import detect
    return detect(text)


def guess_title(text: str, fallback: str = _t("Без названия")) -> tuple[str, str]:
    """(название, автор) по началу текста."""
    from stamina.text_processing import adapt_for_typing
    if adapt_for_typing(text[:400]).startswith(ORWELL_HEAD):
        return "1984", "George Orwell"
    heading = re.compile(r"^(part|chapter|book|часть|глава|книга|пролог|prologue)\b[\s\w.-]{0,12}$", re.I)
    for line in text.splitlines():
        line = line.strip()
        if not line or heading.match(line):
            continue
        if len(line) <= 60:
            return line, ""
        words = line.split()
        return " ".join(words[:6]).rstrip(",.;:—-") + "…", ""
    return fallback, ""


class Library:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            from stamina.storage import DATA_DIR
            root = DATA_DIR / "library"
        self.root = Path(root)
        self.index_path = self.root / "library.json"
        self.lock = threading.RLock()
        self.index = self._load_index()
        self._maps: dict[str, tuple[str, TextMap]] = {}

    # -- индекс -------------------------------------------------------------------
    def _load_index(self) -> dict:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("texts"), list):
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "migrated": False, "active_typing": None, "active_reading": None,
                "texts": []}

    def save_index(self) -> None:
        with self.lock:
            _write_atomic(self.index_path, json.dumps(self.index, ensure_ascii=False, indent=1))

    def _dir(self, tid: str) -> Path:
        return self.root / "texts" / tid

    def ids(self) -> list[str]:
        return [t["id"] for t in self.index["texts"]]

    def meta(self, tid: str) -> dict | None:
        try:
            return json.loads((self._dir(tid) / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save_meta(self, meta: dict) -> None:
        meta["updated"] = _now()
        _write_atomic(self._dir(meta["id"]) / "meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
        with self.lock:
            row = {"id": meta["id"], "title": meta["title"], "author": meta.get("author", ""),
                   "lang": meta.get("lang", ""), "updated": meta["updated"]}
            for i, t in enumerate(self.index["texts"]):
                if t["id"] == meta["id"]:
                    self.index["texts"][i] = row
                    break
            else:
                self.index["texts"].append(row)
            self.save_index()

    def all(self) -> list[dict]:
        out = []
        for tid in self.ids():
            m = self.meta(tid)
            if m:
                out.append(m)
        return out

    def original(self, tid: str) -> str:
        try:
            return (self._dir(tid) / "original.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def prepared(self, tid: str) -> str:
        try:
            return (self._dir(tid) / "prepared.txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def reading_text(self, tid: str) -> str:
        """Текст для гипердрайва: оригинал, если есть, иначе подготовленная версия."""
        return self.original(tid) or self.prepared(tid)

    # -- добавление -----------------------------------------------------------------
    def _new_id(self) -> str:
        return f"t-{time.strftime('%Y%m%d')}-{secrets.token_hex(2)}"

    def find_by_original(self, original: str) -> str | None:
        h = sha(original)
        for m in self.all():
            if m.get("original", {}).get("sha256") == h:
                return m["id"]
        return None

    def find_by_prepared(self, prepared: str) -> str | None:
        h = sha(prepared)
        for m in self.all():
            if m.get("prepared", {}).get("sha256") == h:
                return m["id"]
        return None

    def add(self, original: str, *, title: str = "", author: str = "", opts: dict | None = None,
            source: dict | None = None, prepared: str | None = None,
            status: str = "full", note: str = "") -> dict:
        """Добавить текст (или вернуть уже существующий с тем же оригиналом)."""
        original = (original or "").replace("\r\n", "\n")
        opts = norm_opts(opts)
        if original:
            dup = self.find_by_original(original)
            if dup:
                return self.meta(dup)  # type: ignore[return-value]
        if prepared is None:
            prepared = processor(opts)(original)
        if not title:
            title, guessed_author = guess_title(original or prepared)
            author = author or guessed_author
        tid = self._new_id()
        d = self._dir(tid)
        if original:
            _write_atomic(d / "original.txt", original)
        _write_atomic(d / "prepared.txt", prepared)
        base = original or prepared
        meta = {
            "id": tid, "title": title, "author": author, "lang": detect_lang(base),
            "source": source or {"kind": "paste"}, "created": _now(), "updated": _now(),
            "original": {"status": status if original else "missing", "chars": len(original),
                         "words": len(original.split()), "sha256": sha(original) if original else "",
                         "note": note},
            "prepared": {"opts": opts, "processor": PROCESSOR, "chars": len(prepared),
                         "sha256": sha(prepared), "generated": _now()},
            "positions": {"typing": {"char": 0, "updated": None}, "reading": {"word": 0, "updated": None}},
            "sync": "ask", "protected": False, "tags": [],
        }
        self.save_meta(meta)
        return meta

    def delete(self, tid: str) -> None:
        d = self._dir(tid)
        if d.exists():
            dest = self.root.parent / "backups" / "deleted-texts" / f"{tid}-{time.strftime('%Y%m%d-%H%M%S')}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(dest))
        with self.lock:
            self.index["texts"] = [t for t in self.index["texts"] if t["id"] != tid]
            for k in ("active_typing", "active_reading"):
                if self.index.get(k) == tid:
                    self.index[k] = None
            self.save_index()
        self._maps.pop(tid, None)

    def rename(self, tid: str, title: str, author: str | None = None) -> None:
        m = self.meta(tid)
        if m:
            m["title"] = title.strip() or m["title"]
            if author is not None:
                m["author"] = author.strip()
            self.save_meta(m)

    # -- оригинал / подготовка ----------------------------------------------------------
    def attach_original(self, tid: str, original: str, source: dict | None = None) -> str:
        """Привязать оригинал к тексту без оригинала. → новый статус или '' (не подходит)."""
        m = self.meta(tid)
        if not m:
            return ""
        original = original.replace("\r\n", "\n")
        prep = self.prepared(tid)
        proc = processor(m["prepared"]["opts"])
        if proc(original) == prep:
            text, status, note = original, "recovered", ""
        else:
            frag = fragment_of(original, prep, proc)
            if frag is None:
                return ""
            text, status = frag, "recovered"
            note = (_t("оригинал — начало файла {0} ({1} из {2} символов)").format(Path((source or {}).get('path', '')).name or 'источника', len(frag), len(original)))
        _write_atomic(self._dir(tid) / "original.txt", text)
        m["original"] = {"status": status, "chars": len(text), "words": len(text.split()),
                         "sha256": sha(text), "note": note}
        if source:
            m["source"] = {**m.get("source", {}), **source}
        self.save_meta(m)
        self._maps.pop(tid, None)
        return status

    def regenerate(self, tid: str, opts: dict) -> tuple[str, int] | None:
        """Пересоздать подготовленную версию по новым опциям. → (новый текст, перенесённая позиция)."""
        m = self.meta(tid)
        orig = self.original(tid)
        if not m or not orig:
            return None
        old_map = self.textmap(tid)
        old_pos = m["positions"]["typing"]["char"]
        word = old_map.prep_to_orig(old_pos) if old_map and old_pos else 0
        opts = norm_opts(opts)
        new = processor(opts)(orig)
        _write_atomic(self._dir(tid) / "prepared.txt", new)
        m["prepared"] = {"opts": opts, "processor": PROCESSOR, "chars": len(new), "sha256": sha(new),
                         "generated": _now()}
        self._maps.pop(tid, None)
        new_map = TextMap(orig, new, processor(opts))
        pos = new_map.orig_to_prep(word) if old_pos else 0
        m["positions"]["typing"] = {"char": pos, "updated": _now()}
        self.save_meta(m)
        return new, pos

    def textmap(self, tid: str) -> TextMap | None:
        m = self.meta(tid)
        if not m:
            return None
        orig, prep = self.original(tid), self.prepared(tid)
        key = sha(orig) + sha(prep)
        cached = self._maps.get(tid)
        if cached and cached[0] == key:
            return cached[1]
        if not orig:
            tm = TextMap(prep, prep, lambda s: s)
        else:
            tm = TextMap(orig, prep, processor(m["prepared"]["opts"]))
        self._maps[tid] = (key, tm)
        return tm

    # -- позиции ------------------------------------------------------------------------
    def set_position(self, tid: str, kind: str, value: int) -> None:
        m = self.meta(tid)
        if not m:
            return
        key = "char" if kind == "typing" else "word"
        m["positions"][kind] = {key: int(value), "updated": _now()}
        self.save_meta(m)

    def typing_position(self, tid: str) -> int:
        """Позиция печати: из session.json, если сейчас печатается этот текст, иначе из meta."""
        from stamina.session_storage import load_session
        m = self.meta(tid)
        if not m:
            return 0
        s = load_session()
        if s is not None and sha(s.text) == m["prepared"]["sha256"]:
            return s.index
        return int(m["positions"]["typing"].get("char", 0))

    def typing_word(self, tid: str) -> int | None:
        """Позиция печати в словах оригинала (None — по тексту не печатали)."""
        pos = self.typing_position(tid)
        if not pos:
            return None
        tm = self.textmap(tid)
        return tm.prep_to_orig(pos) if tm else None

    def set_active(self, kind: str, tid: str | None) -> None:
        with self.lock:
            self.index[f"active_{kind}"] = tid
            self.save_index()

    # -- связь со «СВОИМ ТЕКСТОМ» ---------------------------------------------------------
    def upsert_from_cargo(self, adapted: str, original: str, opts: dict | None,
                          source: dict | None = None) -> str | None:
        """Вызывается при «Сохранить на борт / Старт» в «СВОЁМ ТЕКСТЕ». → id текста."""
        if not adapted:
            return None
        tid = self.find_by_prepared(adapted)
        if tid:
            m = self.meta(tid)
            if m and m["original"]["status"] == "missing" and original and processor(opts)(original) == adapted:
                self.attach_original(tid, original, source or {"kind": "cargo"})
        else:
            if original and processor(opts)(original) == adapted:
                tid = self.add(original, opts=opts, source=source or {"kind": "cargo"})["id"]
            else:
                tid = self.add("", prepared=adapted, opts=opts, source=source or {"kind": "cargo"},
                               title=guess_title(adapted)[0], status="missing")["id"]
        self.set_active("typing", tid)
        return tid


# ---------------------------------------------------------------------------
# Миграция: перенос текущего «своего текста» в библиотеку + поиск оригинала
# ---------------------------------------------------------------------------

def _candidate_dirs() -> list[Path]:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    dirs = []
    for sub in ("OneDrive/Рабочий стол", "OneDrive/Desktop", "Desktop", "Рабочий стол",
                "OneDrive/Documents", "OneDrive/Документы", "Documents", "Downloads", "OneDrive"):
        p = home / sub
        if p.is_dir() and p not in dirs:
            dirs.append(p)
    try:
        from stamina.storage import PROJECT_DIR
        dirs.append(PROJECT_DIR)
    except Exception:  # noqa: BLE001
        pass
    extra = os.environ.get("STAMINA_TEXT_SEARCH")
    if extra:
        dirs = [Path(x) for x in extra.split(os.pathsep) if x] + dirs
    return dirs


def find_candidates(max_depth: int = 3, prefer: tuple[str, ...] = ("1984", "orwell")) -> list[Path]:
    """Файлы .txt ≤ 20 МБ в известных папках; сначала с «говорящими» именами."""
    found: list[Path] = []
    seen = set()
    for root in _candidate_dirs():
        base_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).parts) - base_depth
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "__")) and d not in
                           ("node_modules", "models", "cache", "AppData")] if depth < max_depth else []
            for fn in filenames:
                if not fn.lower().endswith(".txt"):
                    continue
                p = Path(dirpath) / fn
                try:
                    if p.stat().st_size > MAX_CANDIDATE_BYTES or p.resolve() in seen:
                        continue
                except OSError:
                    continue
                seen.add(p.resolve())
                found.append(p)
    found.sort(key=lambda p: (not any(k in p.name.lower() for k in prefer), -p.stat().st_size))
    return found


def recover_original(prepared: str, opts: dict | None,
                     candidates: list[Path] | None = None) -> tuple[str, Path, bool] | None:
    """Найти оригинал для подготовленного текста. → (оригинал, файл, это_фрагмент)."""
    proc = processor(opts)
    head = prepared[:200]
    for p in candidates if candidates is not None else find_candidates():
        try:
            text, _enc = read_text_file(p)
        except (OSError, UnicodeDecodeError):
            continue
        if not proc(text[:max(2000, len(head) * 8)]).startswith(head[:80]):
            continue
        full = proc(text)
        if full == text.strip() or " ".join(text.split()) == full:
            continue  # файл сам уже подготовлен (без заглавных и пунктуации) — это не оригинал
        if full == prepared:
            return text, p, False
        if full.startswith(prepared):
            frag = fragment_of(text, prepared, proc)
            if frag:
                return frag, p, True
    return None


def migrate(lib: Library, store, *, search: bool = True,
            candidates: list[Path] | None = None) -> dict:
    """Однократный перенос текущего «своего текста» (и прогресса печати) в библиотеку.

    session.json не меняется. Возвращает отчёт для журнала/статуса."""
    from stamina.session_storage import load_session
    report: dict = {"done": False}
    if lib.index.get("migrated"):
        return report
    opts = norm_opts(store.settings.get("cargo_opts"))
    proc = processor(opts)
    adapted, original = store.load_cargo()
    saved = load_session()
    prepared = saved.text if saved is not None else adapted
    tid = None
    if prepared:
        if original and proc(original) == prepared:
            tid = lib.add(original, opts=opts, source={"kind": "migrated", "path": "cargo_original.txt"},
                          prepared=prepared)["id"]
            report["original"] = "full"
        else:
            found = recover_original(prepared, opts, candidates) if search else None
            title, author = guess_title(prepared)
            if found:
                text, path, is_frag = found
                note = (_t("оригинал — начало файла {0} ({1} из {2} байт)").format(path.name, len(text), path.stat().st_size)) if is_frag else ""
                src = {"kind": "migrated", "path": str(path), "filename": path.name,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                tid = lib.add(text, title=title, author=author, opts=opts, source=src,
                              prepared=prepared, status="recovered", note=note)["id"]
                report.update(original="recovered", path=str(path), fragment=is_frag)
                if is_frag:
                    m = lib.meta(tid)
                    m["full_source_offer"] = {"path": str(path), "asked": False}
                    lib.save_meta(m)
            else:
                tid = lib.add("", prepared=prepared, title=title, author=author, opts=opts,
                              source={"kind": "migrated"}, status="missing")["id"]
                report["original"] = "missing"
        if saved is not None:
            lib.set_position(tid, "typing", saved.index)
            tm = lib.textmap(tid)
            if tm is not None:
                lib.set_position(tid, "reading", tm.prep_to_orig(saved.index))
        lib.set_active("typing", tid)
        lib.set_active("reading", tid)
    lib.index["migrated"] = True
    lib.index["migrated_at"] = _now()
    lib.save_index()
    report.update(done=True, id=tid)
    return report


def split_paragraph_words(text: str) -> list[str]:
    return re.findall(r"\S+", text)
