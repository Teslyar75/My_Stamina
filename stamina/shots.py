"""Снимки экрана для чата ОРИОНА: взять, сохранить, почистить, показать.

Пилот присылает Ориону картинку тремя способами:

* **из буфера обмена** — `Win+Shift+S`, затем `Ctrl+V` в поле сообщения;
* **весь экран** — кнопка «📷 СКРИНШОТ»;
* **активное окно** — та же кнопка с зажатым `Shift`.

Файлы ложатся в ``_orion/shots/`` рядом с кораблём: папка локальная (в ``.gitignore``),
наружу ничего не уходит. Чтобы чат не превратился в свалку, снимки старше ``KEEP_DAYS``
дней убираются сами, а файл тяжелее ``MAX_BYTES`` уменьшается, пока не войдёт.

Агент видит картинку так: путь уходит в запрос строкой «СНИМОК ПИЛОТА: <путь>», и агент
читает файл своим инструментом чтения. Ничего передавать по сети не нужно.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SHOTS_SUBDIR = ("_orion", "shots")
KEEP_DAYS = 30
MAX_BYTES = 10 * 1024 * 1024          # 10 МБ на файл — дальше это уже не снимок экрана
THUMB_PX = 120                        # миниатюра в пузыре сообщения
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


def shots_dir() -> Path:
    """Папка снимков корабля (переопределяется `STAR_TYPING_SHOTS_DIR` — для тестов)."""
    custom = os.environ.get("STAR_TYPING_SHOTS_DIR")
    return Path(custom) if custom else PROJECT_DIR.joinpath(*SHOTS_SUBDIR)


def available() -> bool:
    """Есть ли Pillow: без него ни снимка взять, ни миниатюру показать нечем."""
    try:
        import PIL  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def new_filename(now: float | None = None) -> str:
    """Имя файла снимка: дата-время, чтобы сортировалось само."""
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now else time.time())) + ".png"


def save_image(image, *, folder: Path | None = None, limit: int = MAX_BYTES) -> Path:
    """Сохранить снимок в папку чата и вернуть путь к файлу.

    Тяжёлый снимок уменьшается вдвое, пока не войдёт в лимит: лучше потерять немного
    резкости, чем таскать по кораблю десятимегабайтные полотна.
    """
    folder = Path(folder) if folder else shots_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = _free_path(folder / new_filename())
    image.save(path, "PNG")

    scale = 1.0
    while limit and path.stat().st_size > limit and scale > 0.2:
        scale /= 2
        small = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
        small.save(path, "PNG")
    if limit and path.stat().st_size > limit:
        path.unlink(missing_ok=True)
        raise ValueError(f"снимок не входит в лимит {limit} байт")
    return path


def cleanup(*, folder: Path | None = None, days: int = KEEP_DAYS, now: float | None = None) -> int:
    """Убрать старые снимки. → сколько файлов удалено."""
    folder = Path(folder) if folder else shots_dir()
    if not folder.is_dir():
        return 0
    edge = (now if now else time.time()) - days * 86400
    gone = 0
    for item in folder.glob("*.png"):
        try:
            if item.stat().st_mtime < edge:
                item.unlink()
                gone += 1
        except OSError:
            continue
    return gone


def grab_clipboard():
    """Картинка из буфера обмена (или None).

    `Win+Shift+S` кладёт снимок в буфер как изображение; Проводник — как список путей.
    Понимаем оба случая: во втором берём первый файл-картинку.
    """
    if not available():
        return None
    try:
        from PIL import Image, ImageGrab
    except Exception:  # noqa: BLE001
        return None
    try:
        got = ImageGrab.grabclipboard()
    except Exception:  # noqa: BLE001
        return None
    if got is None:
        return None
    if isinstance(got, list):
        for name in got:
            path = Path(str(name))
            if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file():
                try:
                    return Image.open(path).convert("RGBA")
                except Exception:  # noqa: BLE001
                    return None
        return None
    return got


def grab_screen():
    """Снимок всего экрана (все мониторы) или None."""
    if sys.platform != "win32" or not available():
        return None
    try:
        from PIL import ImageGrab
        return ImageGrab.grab(all_screens=True)
    except Exception:  # noqa: BLE001
        return None


def grab_active_window():
    """Снимок активного окна по его рамке. Не вышло — None (экран снимет вызывающий)."""
    if sys.platform != "win32" or not available():
        return None
    try:
        import ctypes
        from ctypes import wintypes

        from PIL import ImageGrab

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        box = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        if box[2] - box[0] < 16 or box[3] - box[1] < 16:
            return None
        return ImageGrab.grab(bbox=box, all_screens=True)
    except Exception:  # noqa: BLE001
        return None


def thumbnail(path: Path, size: int = THUMB_PX):
    """Миниатюра для пузыря сообщения — PIL-картинка с сохранением пропорций."""
    if not available():
        return None
    try:
        from PIL import Image
        with Image.open(path) as src:
            pic = src.convert("RGBA")
    except Exception:  # noqa: BLE001
        return None
    pic.thumbnail((size, size))
    return pic


def open_file(path: Path) -> bool:
    """Открыть снимок как есть — системной программой просмотра."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))                      # noqa: S606 — открывает пилот, не мы
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])    # noqa: S603,S607
        return True
    except OSError:
        return False


START_RE = re.compile(r"[A-Za-z]:[\\/]")


def image_paths_in(text: str) -> list[Path]:
    """Пути к картинкам, которые пилот просто написал в сообщении.

    Пилот часто не вставляет снимок, а пишет путь словами: «Снимок экрана 2026-10-19.png»
    с рабочего стола или из OneDrive. Ищем такие пути сами, чтобы не переспрашивать.
    Пробелы внутри пути не мешают: берём ближайшее существующее окончание файла.
    """
    text = text or ""
    found: list[Path] = []
    seen: set[str] = set()
    for match in START_RE.finditer(text):
        tail = text[match.start():]
        low = tail.lower()
        ends: list[int] = []
        for suffix in IMAGE_SUFFIXES:
            idx = low.find(suffix)
            while idx >= 0:
                ends.append(idx + len(suffix))
                idx = low.find(suffix, idx + 1)
        for end in sorted(ends):                     # ближайшее окончание — оно и путь
            candidate = Path(tail[:end].strip().strip("\"'«»"))
            key = str(candidate).lower()
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            found.append(candidate)
            break
    return found


def adopt(paths, *, folder: Path | None = None) -> list[Path]:
    """Перенести чужие снимки внутрь корабля. → новые пути.

    Файл с рабочего стола или из OneDrive корабль читать не вправе: доступ есть только
    к своей папке. Копия в `_orion/shots/` решает это — и заодно хранит снимок рядом с
    перепиской, даже если пилот потом уберёт оригинал.
    """
    folder = Path(folder) if folder else shots_dir()
    adopted: list[Path] = []
    for src in paths:
        src = Path(src)
        if not src.is_file():
            continue
        try:
            inside = src.resolve().parent == folder.resolve()
        except OSError:
            inside = False
        if inside:                                   # файл уже на борту — не копируем
            adopted.append(src)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        target = _free_path(folder / src.name)
        try:
            shutil.copy2(src, target)
        except OSError:
            continue
        adopted.append(target)
    return adopted


def _free_path(path: Path) -> Path:
    """Не затирать односекундные снимки: `…-201530.png`, `…-201530-2.png` и так далее."""
    if not path.exists():
        return path
    for n in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path
