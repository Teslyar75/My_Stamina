from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except Exception:  # noqa: BLE001
    Image = None


def cache_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        return Path(base) / "StarTyping" / "earth-backgrounds"
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else (Path.home() / ".cache")
    return root / "StarTyping" / "earth-backgrounds"


class EarthDownloader:
    """Download NASA manifest images into local cache. No UI blocking."""

    def __init__(self, manifest_path: Path, *, on_ready=None, max_long_side: int = 1920):
        self.manifest_path = Path(manifest_path)
        self.on_ready = on_ready  # callback(path: Path)
        self.max_long_side = max_long_side
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready: list[Path] = []
        self._lock = threading.Lock()

    def cached_files(self) -> list[Path]:
        root = cache_root()
        if not root.exists():
            return []
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        files.sort(key=lambda p: str(p).lower())
        return files

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="earth-downloader")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def ready_files(self) -> list[Path]:
        with self._lock:
            return list(self._ready)

    def _emit_ready(self, path: Path) -> None:
        with self._lock:
            if path not in self._ready:
                self._ready.append(path)
        cb = self.on_ready
        if cb:
            try:
                cb(path)
            except Exception:
                pass

    def _load_manifest(self) -> list[dict]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        items = data.get("items") or []
        out = []
        for it in items:
            url = (it or {}).get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            cat = str((it or {}).get("category") or "misc")
            iid = str((it or {}).get("id") or "").strip()
            if not iid:
                continue
            out.append({"id": iid, "category": cat, "url": url, "priority": bool((it or {}).get("priority"))})
        # priority first, then stable order
        out.sort(key=lambda x: (0 if x["priority"] else 1, x["category"], x["id"]))
        return out

    def _target_path(self, item: dict) -> Path:
        cat = "".join(ch for ch in item["category"] if ch.isalnum() or ch in ("-", "_")) or "misc"
        iid = "".join(ch for ch in item["id"] if ch.isalnum() or ch in ("-", "_"))
        ext = os.path.splitext(item["url"].split("?")[0])[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        return cache_root() / cat / f"{iid}{ext}"

    def _download(self, url: str, dest: Path) -> bool:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "StarTyping/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            tmp.write_bytes(data)
            self._postprocess(tmp, dest)
            if tmp.exists():
                tmp.replace(dest)
            return True
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return False

    def _postprocess(self, src: Path, dest: Path) -> None:
        if Image is None:
            if dest != src:
                src.replace(dest)
            return
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                w, h = im.size
                m = max(w, h)
                if self.max_long_side and m > self.max_long_side:
                    scale = self.max_long_side / float(m)
                    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
                # Save as JPEG for size/cache uniformity unless original was png/webp and small? keep simple jpg.
                out = dest.with_suffix(".jpg")
                im.save(out, format="JPEG", quality=88, optimize=True)
                if out != src and src.exists():
                    src.unlink(missing_ok=True)
                # if dest had different suffix, caller handles; ensure dest points to out
                if dest != out:
                    try:
                        if dest.exists():
                            dest.unlink()
                    except Exception:
                        pass
                    # move out to expected dest? easier: replace dest with out
                    out.replace(dest.with_suffix('.jpg'))
        except Exception:
            try:
                if dest != src and src.exists():
                    src.replace(dest)
            except Exception:
                pass

    def _run(self) -> None:
        for p in self.cached_files():
            if self._stop.is_set():
                return
            self._emit_ready(p)
        items = self._load_manifest()
        for item in items:
            if self._stop.is_set():
                return
            dest = self._target_path(item)
            # postprocess may normalize to .jpg
            jpg_dest = dest.with_suffix('.jpg')
            if jpg_dest.exists() and jpg_dest.stat().st_size > 0:
                self._emit_ready(jpg_dest)
                continue
            if dest.exists() and dest.stat().st_size > 0:
                self._emit_ready(dest)
                continue
            ok = self._download(item['url'], dest)
            if ok:
                final = jpg_dest if jpg_dest.exists() else dest
                if final.exists():
                    self._emit_ready(final)
