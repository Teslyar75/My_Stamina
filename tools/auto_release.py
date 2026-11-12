#!/usr/bin/env python3
"""Выпуск новой версии на GitHub: версия, тег, Release — без ручных шагов.

Зачем это нужно. Программа узнаёт об обновлениях только по GitHub Releases
(``stamina/updater.py``). Пока релиз не выпущен, «Обновить сейчас» честно
отвечает «обновлений нет», хотя в ``master`` давно лежит новая работа: с версии
3.7.0 так накопилось 283 коммита, и обновиться можно было только вручную
скачав код. Тег раньше ставили руками — и забывали.

Что делает (вызывается из CI на каждый push в ``master``):

1. смотрит ``__version__`` в ``stamina/__init__.py`` и последний тег ``vX.Y.Z``;
2. если с прошлого релиза есть коммиты — поднимает патч-версию, а раздел
   «## Не выпущено» в ``CHANGELOG.md`` становится «## X.Y.Z — дата»; сверху
   появляется новый пустой раздел для будущих записей;
3. коммитит ``chore(release): X.Y.Z``, ставит тег и пушит в ``master``;
4. создаёт GitHub Release с notes из changelog (если notes пустые — из коммитов).

Версию вручную двигать не обязательно. Если поставить в ``__version__`` число
больше последнего релиза (например 3.9.0 вместо 3.8.7), выпуск возьмёт её как
есть — так делается минорный релиз с новыми возможностями.

Запуск::

    python tools/auto_release.py            # только показать план (ничего не меняет)
    python tools/auto_release.py --push     # выпустить: коммит, тег, Release
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "stamina" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
DEFAULT_REPO = "Teslyar75/My_Stamina"

VERSION_RE = re.compile(r"""__version__\s*=\s*['"]([^'"]+)['"]""")
UNRELEASED_RE = re.compile(r"^##\s+Не выпущено\s*$", re.MULTILINE | re.IGNORECASE)
TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

EMPTY_SECTION = "## Не выпущено\n\n"


# ------------------------------------------------------------------ версии
def parse_version(text: str) -> tuple[int, int, int] | None:
    """``3.8.0`` / ``v3.8.0`` -> ``(3, 8, 0)``; всё остальное -> ``None``."""
    m = TAG_RE.match((text or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_patch(version: str) -> str:
    major, minor, patch = parse_version(version) or (0, 0, 0)
    return f"{major}.{minor}.{patch + 1}"


def read_version(root: Path = ROOT) -> str:
    text = (root / "stamina" / "__init__.py").read_text(encoding="utf-8")
    m = VERSION_RE.search(text)
    if not m:
        raise RuntimeError("в stamina/__init__.py нет __version__")
    return m.group(1)


def write_version(version: str, root: Path = ROOT) -> None:
    path = root / "stamina" / "__init__.py"
    text = path.read_text(encoding="utf-8")
    new, n = VERSION_RE.subn(f'__version__ = "{version}"', text, count=1)
    if not n:
        raise RuntimeError("в stamina/__init__.py нет __version__")
    path.write_text(new, encoding="utf-8", newline="\n")


def released_versions(tags: list[str]) -> list[str]:
    """Только версии-теги (``v3.8.0``), без ``snap-*`` и прочего мусора."""
    return [t[1:] if t.startswith("v") else t for t in tags if parse_version(t)]


def decide(current: str, released: list[str], commits_since: int) -> str | None:
    """Какой версией выпускать. ``None`` — выпускать нечего.

    * ручная версия выше последнего релиза побеждает всегда (минорный релиз);
    * ровно та же версия и нет новых коммитов — это повторный запуск, молчим
      (так CI не зацикливается на собственном коммите);
    * та же версия, но есть коммиты — поднимаем патч.
    """
    cur = parse_version(current)
    if cur is None:
        return None
    if not released:
        return current if cur > (0, 0, 0) else None
    last = max(released, key=lambda v: parse_version(v) or (0, 0, 0))
    last_t = parse_version(last) or (0, 0, 0)
    if cur > last_t:
        return current
    if commits_since <= 0:
        return None
    return bump_patch(last)


def release_changelog(text: str, version: str, date: str) -> str:
    """«## Не выпущено» -> «## X.Y.Z — дата», сверху новый пустой раздел."""
    m = UNRELEASED_RE.search(text)
    if not m:
        return text
    heading = f"## {version} — {date}"
    rest = text[m.end():]
    rest = rest.lstrip("\n")
    return text[: m.start()] + EMPTY_SECTION + heading + "\n\n" + rest


# ------------------------------------------------------------------ git
def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def commits_since(tag: str | None) -> int:
    rng = f"{tag}..HEAD" if tag else "HEAD"
    out = git("rev-list", "--count", rng)
    return int(out or 0)


def commit_subjects(limit: int = 40) -> list[str]:
    out = git("log", "--no-merges", "--pretty=- %s", "-n", str(limit))
    return [line for line in out.splitlines() if line.strip()]


# ------------------------------------------------------------------ notes
def _extract_notes(version: str) -> str:
    """Notes из CHANGELOG тем же кодом, что и ручной выпуск (tools/changelog_notes.py)."""
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from changelog_notes import extract_notes  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return extract_notes(CHANGELOG.read_text(encoding="utf-8"), version)


def release_notes(version: str) -> str:
    body = _extract_notes(version).strip()
    if body and body != f"Release {version}":
        return body + "\n"
    # Раздела в changelog нет (или он пуст) — не оставляем релиз без описания.
    lines = commit_subjects()
    head = f"Что изменилось с прошлой версии ({len(lines)} коммитов):\n\n"
    return head + "\n".join(lines) + "\n" if lines else f"Star Typing {version}\n"


# ------------------------------------------------------------------ выпуск
def ensure_release(tag: str, title: str, notes: str, repo: str) -> str:
    """Создать Release, если его ещё нет. Повторный запуск ничего не ломает."""
    gh = shutil.which("gh")
    if gh:
        view = subprocess.run([gh, "release", "view", tag, "--repo", repo],
                              capture_output=True, text=True)
        if view.returncode == 0:
            return f"Release {tag} уже есть — не трогаю"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(notes)
            notes_file = fh.name
        try:
            proc = subprocess.run(
                [gh, "release", "create", tag, "--repo", repo, "--title", title,
                 "--notes-file", notes_file],
                capture_output=True, text=True,
            )
        finally:
            os.unlink(notes_file)
        if proc.returncode != 0:
            raise RuntimeError(f"gh release create: {proc.stderr.strip()}")
        return f"Release {tag} создан"

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return "Release не создан: нет ни gh, ни GH_TOKEN"
    api = f"https://api.github.com/repos/{repo}/releases"
    payload = {"tag_name": tag, "name": title, "body": notes, "draft": False,
               "prerelease": False}
    req = urllib.request.Request(api, data=json.dumps(payload).encode("utf-8"),
                                 method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "StarTyping-AutoRelease")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 422:               # уже существует
            return f"Release {tag} уже есть — не трогаю"
        raise
    return f"Release {tag} создан"


def publish(version: str, date: str, repo: str, *, push: bool) -> str:
    """Записать версию и changelog, затем (если push) коммит, тег и Release."""
    tag = f"v{version}"
    title = f"Star Typing {version}"
    if not push:
        # Пробный прогон ничего не меняет в репозитории: только показывает, что будет.
        text = CHANGELOG.read_text(encoding="utf-8")
        after = release_changelog(text, version, date)
        renamed = "## Не выпущено" in text and after != text
        return (f"план: {tag}; раздел changelog "
                f"{'переименуется' if renamed else 'не найден — notes из коммитов'}")
    write_version(version)
    text = CHANGELOG.read_text(encoding="utf-8")
    CHANGELOG.write_text(release_changelog(text, version, date), encoding="utf-8", newline="\n")
    notes = release_notes(version)
    git("add", "stamina/__init__.py", "CHANGELOG.md")
    git("commit", "-m", f"chore(release): {version}")
    for attempt in range(2):
        try:
            git("push", "origin", "HEAD:master")
            break
        except RuntimeError:
            if attempt:
                raise
            git("pull", "--rebase", "--no-edit", "origin", "master")
    git("tag", "-a", tag, "-m", title)
    git("push", "origin", tag)
    return ensure_release(tag, title, notes, repo)


def plan(root: Path = ROOT) -> tuple[str | None, str, int, str]:
    """(версия к выпуску | None, текущая версия, коммитов с релиза, последний тег)."""
    tags = [t for t in git("tag", "--list").splitlines() if t.strip()]
    released = released_versions(tags)
    last = max(released, key=lambda v: parse_version(v) or (0, 0, 0)) if released else ""
    last_tag = f"v{last}" if last else ""
    ahead = commits_since(last_tag or None)
    current = read_version(root)
    return decide(current, released, ahead), current, ahead, last_tag


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Выпуск версии на GitHub из master")
    ap.add_argument("--push", action="store_true",
                    help="действительно выпустить (по умолчанию только показать план)")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO)
    ap.add_argument("--date", default=_dt.date.today().strftime("%d.%m.%Y"))
    args = ap.parse_args(argv)

    version, current, ahead, last_tag = plan()
    print(f"сейчас: {current}; последний релиз: {last_tag or 'нет'}; коммитов с него: {ahead}")
    if not version:
        print("выпускать нечего: новых коммитов с прошлого релиза нет")
        return 0
    print(f"к выпуску: v{version}")
    print(publish(version, args.date, args.repo, push=args.push))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
