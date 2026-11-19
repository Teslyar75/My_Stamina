"""Проверка и установка обновлений с GitHub Releases (десктоп)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
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
    "_orion",
    "graphify-out",
    ".st_upd_pending",
    "pending-update",
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


def dev_checkout_error(root: Path | None = None) -> str | None:
    """Программа запущена из рабочей копии git — кнопкой обновлять нельзя.

    Обновление кладёт файлы ZIP поверх установки, не спрашивая git: в рабочей
    копии это тихо затирает незакоммиченные правки и расходится с историей.
    Там обновляются слиянием, а кнопка нужна для обычной установки у пилота.
    """
    base = Path(root or PROJECT_DIR)
    inside = (base / ".git").exists() or (base / ".." / ".git").exists()
    if not inside:
        return None
    return (
        "Эта копия программы — рабочая: рядом лежит папка .git.\n\n"
        "Кнопка обновления затирает файлы поверх и потеряет незакоммиченные правки,\n"
        "поэтому здесь она не работает. Обновитесь через git (слияние с master),\n"
        "затем запустите программу заново.\n\n"
        "Кнопка нужна для обычной установки без git — как у пилота."
    )


def check_error_message(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "Релизов ещё нет на GitHub."
        return f"GitHub HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "Нет сети или GitHub недоступен."
    return str(exc) or exc.__class__.__name__



# --- Автообновление ---------------------------------------------------------

AUTO_UPDATE_KEY = "auto_update"
PENDING_DIR_NAME = "pending-update"
PENDING_TREE = "tree"
PENDING_MARKER = ".st_update_version"
NOTICE_FILE = "update_notice.json"
LOG_FILE = "updater.log"
LOG_MAX_BYTES = 512 * 1024
FF_BRANCHES = frozenset({"master", "main"})
# Только эти git-глаголы разрешены каналу автообновления.
_GIT_ALLOWED = frozenset({"status", "rev-parse", "fetch", "merge-base", "merge", "show"})
_GIT_FORBIDDEN = frozenset({"reset", "clean", "checkout", "stash", "rebase", "push"})


@dataclass
class GitState:
    """Снимок git-копии, из которой запущена программа."""

    is_repo: bool
    branch: str = ""
    dirty: bool = False
    head: str = ""
    reason: str = ""


@dataclass
class AutoUpdateResult:
    """Итог фонового автообновления (для лога и ненавязчивого уведомления)."""

    status: str  # disabled|current|staged|applied|ff|skipped|error
    version: str = ""
    reason: str = ""
    notice_kind: str = ""  # "" | staged | applied | ff


def _state_dir() -> Path:
    """Общий корень данных (%APPDATA%\\Stamina), не папка активного пилота."""
    from stamina.pilots import ROOT_DIR
    return Path(ROOT_DIR)


def _log(message: str) -> None:
    """Дописать строку в updater.log; ошибки записи глотаются."""
    import time
    try:
        path = _state_dir() / LOG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size > LOG_MAX_BYTES:
            tail = path.read_bytes()[-LOG_MAX_BYTES // 2:]
            path.write_bytes(tail)
        line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(message).replace("\n", " ") + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:  # noqa: BLE001
        pass


def is_auto_update_enabled(settings: dict | None = None) -> bool:
    """Тумблер автообновления; при отсутствии ключа — включено."""
    if settings is None:
        try:
            from stamina.storage import SETTINGS_PATH, _read_json
            settings = _read_json(SETTINGS_PATH) or {}
        except Exception:  # noqa: BLE001
            settings = {}
    return bool(settings.get(AUTO_UPDATE_KEY, True))


def is_git_checkout(root: Path | None = None) -> bool:
    """Рабочая копия git (в том числе worktree, где .git — файл)."""
    base = Path(root or PROJECT_DIR)
    if (base / ".git").exists() or (base.parent / ".git").exists():
        return True
    try:
        code, out, _err = _git(base, ["rev-parse", "--is-inside-work-tree"], timeout=8)
        return code == 0 and out.strip() == "true"
    except Exception:  # noqa: BLE001
        return False


def git_args_allowed(args: list[str]) -> bool:
    """Проверка, что набор аргументов git безопасен для автообновления."""
    if not args:
        return False
    verb = args[0].lstrip("-")
    if verb in _GIT_FORBIDDEN or any(a.lstrip("-") in _GIT_FORBIDDEN for a in args):
        return False
    if verb not in _GIT_ALLOWED:
        return False
    if verb == "merge" and "--ff-only" not in args:
        return False
    lowered = [a.lower() for a in args]
    if "--force" in lowered or "-f" in lowered or "--hard" in lowered:
        return False
    return True


def _git(root: Path, args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Запустить git списком аргументов. Запрещённые команды не вызываются."""
    if not git_args_allowed(args):
        raise RuntimeError(f"запрещённая git-команда: {' '.join(args)[:80]}")
    res = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()


def inspect_git(root: Path | None = None) -> GitState:
    """Состояние рабочей копии: ветка, грязность, HEAD."""
    base = Path(root or PROJECT_DIR)
    if not is_git_checkout(base):
        return GitState(is_repo=False)
    try:
        code, head, err = _git(base, ["rev-parse", "HEAD"], timeout=8)
        if code != 0:
            return GitState(is_repo=True, reason=err or "не удалось прочитать HEAD")
        code, branch, err = _git(base, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=8)
        branch = branch if code == 0 else ""
        code, porcelain, err = _git(base, ["status", "--porcelain"], timeout=8)
        if code != 0:
            return GitState(is_repo=True, branch=branch, head=head, dirty=True,
                            reason=err or "не удалось прочитать git status")
        dirty = bool(porcelain)
        return GitState(is_repo=True, branch=branch, dirty=dirty, head=head)
    except Exception as exc:  # noqa: BLE001
        return GitState(is_repo=True, reason=str(exc) or exc.__class__.__name__)


def _ref_exists(root: Path, ref: str) -> bool:
    code, _out, _err = _git(root, ["rev-parse", "--verify", ref], timeout=8)
    return code == 0


def _version_at_ref(root: Path, ref: str) -> str:
    code, out, _err = _git(root, ["show", f"{ref}:stamina/__init__.py"], timeout=15)
    if code != 0:
        return ""
    m = re.search(r"""__version__\s*=\s*['"]([^'"]+)['"]""", out)
    return normalize_version(m.group(1)) if m else ""


def can_fast_forward(root: Path, target: str) -> tuple[bool, str]:
    """Можно ли сделать merge --ff-only на target (чистый master, HEAD — предок)."""
    state = inspect_git(root)
    if not state.is_repo:
        return False, "не git-копия"
    if state.reason:
        return False, state.reason
    if state.dirty:
        return False, "рабочая копия грязная или есть неотслеживаемые файлы"
    if state.branch not in FF_BRANCHES:
        return False, f"ветка {state.branch or 'DETACHED'}, нужен master"
    if not target:
        return False, "нет цели для fast-forward"
    try:
        if state.head and _git(root, ["rev-parse", "--verify", target], timeout=8)[1] == state.head:
            return False, "уже на цели"
        code, _out, err = _git(root, ["merge-base", "--is-ancestor", "HEAD", target], timeout=15)
        if code != 0:
            return False, err or "история разошлась или локально впереди"
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc) or exc.__class__.__name__


def try_git_fast_forward(
    root: Path,
    tag: str,
    progress: ProgressCb | None = None,
) -> AutoUpdateResult:
    """Fetch + merge --ff-only на тег релиза (или origin/master той же версии)."""
    log = progress or (lambda _m: None)
    ver = normalize_version(tag)
    tag_ref = tag if str(tag).startswith("v") else f"v{ver}"
    try:
        log("git fetch…")
        _git(root, ["fetch", "origin", "tag", tag_ref], timeout=120)
    except Exception as exc:  # noqa: BLE001
        _log(f"git fetch tag: {exc}")
    try:
        _git(root, ["fetch", "origin", "master"], timeout=120)
    except Exception as exc:  # noqa: BLE001
        _log(f"git fetch master: {exc}")
        # origin/main на всякий случай, если remote так назван
        try:
            _git(root, ["fetch", "origin", "main"], timeout=120)
        except Exception as exc2:  # noqa: BLE001
            _log(f"git fetch main: {exc2}")

    target = ""
    if _ref_exists(root, f"refs/tags/{tag_ref}"):
        target = f"refs/tags/{tag_ref}"
    else:
        for candidate in ("origin/master", "origin/main"):
            if _ref_exists(root, candidate) and _version_at_ref(root, candidate) == ver:
                target = candidate
                break
    if not target:
        _log(f"skip git: не найден тег {tag_ref} и origin/master версии {ver}")
        return AutoUpdateResult("skipped", ver, f"нет тега {tag_ref}")

    ok, reason = can_fast_forward(root, target)
    if reason == "уже на цели":
        return AutoUpdateResult("current", ver, reason)
    if not ok:
        _log(f"skip git ff: {reason}")
        return AutoUpdateResult("skipped", ver, reason)

    log("git merge --ff-only…")
    try:
        code, out, err = _git(root, ["merge", "--ff-only", target], timeout=60)
    except Exception as exc:  # noqa: BLE001
        _log(f"git merge failed: {exc}")
        return AutoUpdateResult("error", ver, str(exc))
    if code != 0:
        _log(f"git merge --ff-only failed: {err or out}")
        return AutoUpdateResult("error", ver, err or out or "merge --ff-only не удался")
    try:
        maybe_pip_install(root, progress=log)
    except Exception as exc:  # noqa: BLE001
        _log(f"pip after ff: {exc}")
    write_update_notice(ver, "ff")
    _log(f"git fast-forward to {target} ({ver})")
    return AutoUpdateResult("ff", ver, "ok", notice_kind="ff")


def pending_dir() -> Path:
    return _state_dir() / PENDING_DIR_NAME


def write_update_notice(version: str, kind: str) -> None:
    try:
        path = _state_dir() / NOTICE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": version, "kind": kind}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        pass


def consume_update_notice() -> dict | None:
    """Прочитать и удалить уведомление о прошедшем обновлении."""
    path = _state_dir() / NOTICE_FILE
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink(missing_ok=True)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def stage_release(
    info: ReleaseInfo,
    staging_dir: Path | None = None,
    progress: ProgressCb | None = None,
) -> Path:
    """Скачать zipball, проверить и сложить дерево в staging_dir/tree."""
    dest = Path(staging_dir or pending_dir())
    url = info.zipball_url
    if not url.startswith("https://"):
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
        if dest.exists():
            shutil.rmtree(dest)
        tree = dest / PENDING_TREE
        tree.mkdir(parents=True)
        apply_tree(src, tree, progress=log)
        (dest / PENDING_MARKER).write_text(normalize_version(info.version), encoding="utf-8")
    log("staged")
    return dest


def apply_pending_update(
    dest_root: Path | None = None,
    staging_dir: Path | None = None,
    progress: ProgressCb | None = None,
) -> AutoUpdateResult:
    """Применить ранее застадированный релиз. Вызывать до запуска окна."""
    base = Path(dest_root or PROJECT_DIR)
    pending = Path(staging_dir or pending_dir())
    marker = pending / PENDING_MARKER
    tree = pending / PENDING_TREE
    if not marker.is_file() or not tree.is_dir():
        return AutoUpdateResult("current", reason="нет застадированного обновления")
    version = marker.read_text(encoding="utf-8").strip()
    log = progress or (lambda _m: None)
    log("applying staged update…")
    try:
        apply_tree(tree, base, progress=log)
        maybe_pip_install(base, progress=log)
    except Exception as exc:  # noqa: BLE001
        _log(f"apply pending failed: {exc}")
        return AutoUpdateResult("error", version, str(exc))
    try:
        shutil.rmtree(pending)
    except Exception as exc:  # noqa: BLE001
        _log(f"pending cleanup: {exc}")
    write_update_notice(version, "applied")
    _log(f"applied pending {version}")
    return AutoUpdateResult("applied", version, "ok", notice_kind="applied")


def run_auto_update(
    settings: dict | None = None,
    dest_root: Path | None = None,
    progress: ProgressCb | None = None,
) -> AutoUpdateResult:
    """Проверить релиз и подготовить установку. Не бросает наружу. ZIP не кладёт на git-копию."""
    base = Path(dest_root or PROJECT_DIR)
    try:
        if not is_auto_update_enabled(settings):
            return AutoUpdateResult("disabled", reason="автообновление выключено")
        try:
            info = fetch_latest()
        except Exception as exc:  # noqa: BLE001
            msg = check_error_message(exc)
            _log(f"fetch_latest: {msg}")
            return AutoUpdateResult("error", reason=msg)
        if not info.is_newer:
            _log(f"current {info.version}")
            return AutoUpdateResult("current", info.version, "уже актуальная версия")

        if is_git_checkout(base):
            result = try_git_fast_forward(base, info.tag or info.version, progress=progress)
            return result

        try:
            stage_release(info, pending_dir(), progress=progress)
        except Exception as exc:  # noqa: BLE001
            _log(f"stage_release: {exc}")
            return AutoUpdateResult("error", info.version, str(exc))
        write_update_notice(info.version, "staged")
        _log(f"staged {info.version}")
        return AutoUpdateResult("staged", info.version, "ok", notice_kind="staged")
    except Exception as exc:  # noqa: BLE001
        _log(f"run_auto_update: {exc}")
        return AutoUpdateResult("error", reason=str(exc) or exc.__class__.__name__)
