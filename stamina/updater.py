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
from pathlib import Path
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


def download_and_apply(
    info: ReleaseInfo,
    dest_root: Path | None = None,
    progress: ProgressCb | None = None,
) -> Path:
    """Скачать ZIP релиза и наложить на dest_root (по умолчанию PROJECT_DIR)."""
    dest = Path(dest_root or PROJECT_DIR)
    if not info.zipball_url:
        raise RuntimeError("no zipball_url in release")
    log = progress or (lambda _m: None)
    log("downloading…")
    req = urllib.request.Request(info.zipball_url, headers={"User-Agent": USER_AGENT})
    with tempfile.TemporaryDirectory(prefix="st-upd-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "release.zip"
        with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        log("extracting…")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path / "unz")
        roots = [p for p in (tmp_path / "unz").iterdir() if p.is_dir()]
        if not roots:
            raise RuntimeError("empty archive")
        src = roots[0]
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
