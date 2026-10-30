"""Модели Vosk для диктовки: какие языки есть, что уже скачано, докачка по требованию.

Модели маленькие (40–80 МБ) и живут в той же папке, что ищет `stt.find_model`.
Скачивание — в фоне, с прогрессом и отменой; архив распаковывается во временную
папку и переименовывается только целиком, поэтому оборванная загрузка не оставит
«полумодель». Без tkinter — проверяется обычными тестами.
"""
from __future__ import annotations

import shutil
import threading
import urllib.request
import zipfile
from pathlib import Path

from stamina.voice import stt

BASE_URL = "https://alphacephei.com/vosk/models/"
# язык -> (имя модели, размер архива в МБ для подсказки)
MODELS: dict[str, tuple[str, int]] = {
    "ru": ("vosk-model-small-ru-0.22", 45),
    "uk": ("vosk-model-small-uk-v3-nano", 75),
    "en": ("vosk-model-small-en-us-0.15", 40),
}
LANGS = tuple(MODELS)          # порядок в переключателе: RU → UK → EN


def _lang_of(dirname: str) -> str:
    for lang in LANGS:
        if f"-{lang}-" in dirname:
            return lang
    return ""


def installed(root: Path | None = None) -> dict[str, Path]:
    """Скачанные модели: {язык: папка}. Берём первую подходящую для каждого языка."""
    root = root or stt.models_dir()
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.iterdir()):
        lang = _lang_of(p.name)
        if lang and lang not in out and p.is_dir() and p.name.startswith("vosk-model") and (p / "am").exists():
            out[lang] = p
    return out


def model_for(lang: str, root: Path | None = None) -> Path | None:
    """Папка модели именно этого языка (без подмены на другой) или None."""
    return installed(root).get(lang)


def url_for(lang: str) -> str:
    return BASE_URL + MODELS[lang][0] + ".zip"


def download(lang: str, *, root: Path | None = None, progress=None,
             cancel: threading.Event | None = None, opener=urllib.request.urlopen) -> Path:
    """Скачать и распаковать модель. progress(done_bytes, total_bytes). Ошибка — исключение."""
    if lang not in MODELS:
        raise ValueError(lang)
    root = Path(root or stt.models_dir())
    root.mkdir(parents=True, exist_ok=True)
    name = MODELS[lang][0]
    final = root / name
    if (final / "am").exists():
        return final
    part = root / f".{name}.zip.part"
    tmp_dir = root / f".{name}.unpack"
    try:
        with opener(url_for(lang), timeout=30) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise InterruptedError("cancelled")
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        with zipfile.ZipFile(part) as z:
            z.extractall(tmp_dir)
        inner = tmp_dir / name
        src = inner if inner.is_dir() else next((p for p in tmp_dir.iterdir() if p.is_dir()), tmp_dir)
        if not (src / "am").exists():
            raise ValueError("bad model archive")
        shutil.rmtree(final, ignore_errors=True)
        src.rename(final)
        return final
    finally:
        part.unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def download_in_background(lang: str, *, on_progress, on_done, root: Path | None = None,
                           cancel: threading.Event | None = None) -> threading.Thread:
    """Фон: on_progress(done, total) и on_done(path | None, error_text) — из потока загрузки.

    Экран сам переносит вызовы в главный поток (через `after`)."""
    def work() -> None:
        try:
            path = download(lang, root=root, progress=on_progress, cancel=cancel)
        except Exception as exc:  # noqa: BLE001
            on_done(None, str(exc) or exc.__class__.__name__)
            return
        on_done(path, "")

    th = threading.Thread(target=work, daemon=True, name=f"vosk-{lang}")
    th.start()
    return th
