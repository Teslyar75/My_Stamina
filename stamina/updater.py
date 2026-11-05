"""Проверка и установка обновлений с GitHub Releases (десктоп)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from stamina import __version__
from stamina.storage import PROJECT_DIR

REPO = "Teslyar75/My_Stamina"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = f"StarTyping-Updater/{__version__}"

# Не перезаписывать при распаковке релиза
SKIP_NAMES = frozenset({
    ".venv",
    ".git",
    "cache",
    "models",
    "pilots",
    "pilots.json",
    ".pytest_cache",
    "node_modules",
    "web_star_typing",
    "_local_shots",
    "screenshots",
    "screenshots_cursor_audit_step2",
    "screenshots_web_port_step1",
    "screenshots_web_port_step2",
    "debug.log",
})
SKIP_SUFFIXES = (".log", ".pyc")

ProgressCb = Callable[[str], None]


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    body: str
    html_url: str
    zipball_url: str

    @property
    def is_newer(self) -> bool:
        return is_newer(self.version, __version__)


def normalize_version(v: str) -> str:
    t = (v or "").strip()
    if t.lower().startswith("v"):
        t = t[1:]
    # отрезать пре-релизный хвост для сравнения основных чисел, но хранить полностью
    return t


def parse_semver(v: str) -> tuple[int, int, int, str]:
    t = normalize_version(v)
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", t)
    if not m:
        return (0, 0, 0, t)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or "")


def is_newer(remote: str, local: str) -> bool:
    """True если remote строго новее local (semver)."""
    a, b = parse_semver(remote), parse_semver(local)
    return a[:3] > b[:3]


def markdown_to_plain(md: str, limit: int = 1200) -> str:
    text = md or ""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _http_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_release_payload(data: dict) -> ReleaseInfo:
    tag = str(data.get("tag_name") or "")
    ver = normalize_version(tag)
    zip_url = str(data.get("zipball_url") or "")
    if not zip_url and tag:
        zip_url = f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip"
    return ReleaseInfo(
        tag=tag,
        version=ver,
        name=str(data.get("name") or tag),
        body=str(data.get("body") or ""),
        html_url=str(data.get("html_url") or f"https://github.com/{REPO}/releases"),
        zipball_url=zip_url,
    )


def fetch_latest(timeout: float = 20.0) -> ReleaseInfo:
    data = _http_json(API_LATEST, timeout=timeout)
    return parse_release_payload(data)


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return True
    if parts[0] in SKIP_NAMES:
        return True
    if any(p in SKIP_NAMES for p in parts):
        return True
    name = parts[-1]
    if name.endswith(SKIP_SUFFIXES):
        return True
    if name == "__pycache__" or "__pycache__" in parts:
        return True
    return False


def apply_tree(src_root: Path, dest_root: Path, progress: ProgressCb | None = None) -> int:
    """Скопировать файлы из src_root в dest_root с учётом SKIP_*. Возвращает число файлов."""
    n = 0
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root)
        if should_skip(rel):
            continue
        target = dest_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
        if progress and n % 40 == 0:
            progress(f"copied {n} files…")
    return n


def safe_extract(zf: zipfile.ZipFile, target: Path) -> None:
    """Распаковать только то, что остаётся внутри target.

    Канал обновлений перезаписывает собственный код программы, поэтому путь
    элемента архива проверяется, а не предполагается: tarball GitHub обычно чист,
    но замена источника загрузки (редирект, зеркало, битый ассет) не должна
    означать запись за пределы папки программы.
    """
    root = target.resolve()
    dangerous = []
    for member in zf.infolist():
        name = member.filename.replace("\\", "/")
        pure = PurePosixPath(name)
        if not name or pure.is_absolute() or name[1:2] == ":" or ".." in pure.parts:
            dangerous.append(member.filename)
            continue
        dest = (root / name).resolve()
        if dest != root and root not in dest.parents:
            dangerous.append(member.filename)
            continue
        zf.extract(member, target)
    if dangerous:
        shown = ", ".join(dangerous[:3])
        raise RuntimeError(f"архив содержит пути вне папки обновления: {shown}")


def tree_version(src: Path) -> str:
    """Версия, объявленная внутри скачанного дерева (stamina/__init__.py)."""
    init = src / "stamina" / "__init__.py"
    if not init.is_file():
        raise RuntimeError("в архиве нет stamina/__init__.py — это не дерево программы")
    text = init.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"""__version__\s*=\s*['"]([^'"]+)['"]""", text)
    if not m:
        raise RuntimeError("в скачанном stamina/__init__.py нет __version__")
    return normalize_version(m.group(1))


def assert_release_matches(src: Path, expected: str) -> str:
    """Проверить, что скачанное дерево — тот же релиз, который объявлен тегом.

    Без этой проверки канал обновлений принимает содержимое на веру: редирект,
    зеркало или архив, собранный не с того refs, молча легли бы поверх рабочего
    кода, а пилот увидел бы на экране одну версию и ставил бы другую.
    """
    want = normalize_version(expected)
    if not want:
        raise RuntimeError("у релиза пустой тег — непонятно, какую версию ждать")
    got = tree_version(src)
    if got != want:
        raise RuntimeError(f"архив не соответствует релизу: тег обещает {want}, внутри {got}")
    return got


def download_and_apply(
    info: ReleaseInfo,
    dest_root: Path | None = None,
    progress: ProgressCb | None = None,
) -> Path:
    """Скачать ZIP релиза и наложить на dest_root (по умолчанию PROJECT_DIR)."""
    dest = Path(dest_root or PROJECT_DIR)
    url = info.zipball_url
    if not url.startswith("https://"):
        # Обновление перезаписывает код программы: канал обязан быть шифрованным,
        # иначе подмену содержимого в сети нельзя отличить от нормального релиза.
        raise RuntimeError(f"ссылка релиза не по HTTPS: {url[:60]}")
    log = progress or (lambda _m: None)
    log("downloading…")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with tempfile.TemporaryDirectory(prefix="st-upd-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "release.zip"
        with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        log("extracting…")
        with zipfile.ZipFile(zip_path, "r") as zf:
            safe_extract(zf, tmp_path / "unz")
        roots = [p for p in (tmp_path / "unz").iterdir() if p.is_dir()]
        if not roots:
            raise RuntimeError("empty archive")
        src = roots[0]
        log("проверка релиза…")
        assert_release_matches(src, info.version)
        log("applying…")
        apply_tree(src, dest, progress=log)
    log("done")
    return dest


def maybe_pip_install(dest_root: Path | None = None, progress: ProgressCb | None = None) -> None:
    """Если есть .venv — обновить зависимости из requirements.txt."""
    root = Path(dest_root or PROJECT_DIR)
    req = root / "requirements.txt"
    if not req.is_file():
        return
    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = root / ".venv" / "bin" / "python"
    if not py.is_file():
        return
    log = progress or (lambda _m: None)
    log("pip install -r requirements.txt…")
    subprocess.run(
        [str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req)],
        cwd=str(root),
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def open_releases_page(info: ReleaseInfo | None = None) -> None:
    import webbrowser
    url = info.html_url if info else f"https://github.com/{REPO}/releases"
    webbrowser.open(url)


def check_error_message(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "Релизов ещё нет на GitHub."
        return f"GitHub HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "Нет сети или GitHub недоступен."
    return str(exc) or exc.__class__.__name__
