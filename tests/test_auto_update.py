"""Тесты автообновления: тумблер, git FF, staging ZIP, без сети и без опасных git-команд."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
import pytest

from stamina.storage import DEFAULT_SETTINGS
from stamina.updater import (
    AutoUpdateResult,
    GitState,
    ReleaseInfo,
    apply_pending_update,
    apply_tree,
    can_fast_forward,
    git_args_allowed,
    inspect_git,
    is_auto_update_enabled,
    is_git_checkout,
    run_auto_update,
    should_skip,
    stage_release,
    try_git_fast_forward,
)


def _info(version: str = "9.9.9", url: str = "https://example.com/rel.zip") -> ReleaseInfo:
    return ReleaseInfo(
        tag=f"v{version}",
        version=version,
        name=f"Star Typing {version}",
        body="",
        html_url=f"https://github.com/Teslyar75/My_Stamina/releases/tag/v{version}",
        zipball_url=url,
    )


def _tree(root: Path, version: str) -> Path:
    src = root / "My_Stamina-abc"
    (src / "stamina").mkdir(parents=True)
    (src / "stamina" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (src / "stamina" / "app.py").write_text("ok", encoding="utf-8")
    (src / "main.py").write_text("main", encoding="utf-8")
    return src


def _zip_of_tree(src: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in src.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(src.parent).as_posix())
    return buf.getvalue()


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            out, self._data = self._data, b""
            return out
        out, self._data = self._data[:n], self._data[n:]
        return out

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_default_settings_has_auto_update():
    assert DEFAULT_SETTINGS["auto_update"] is True


def test_is_auto_update_enabled_defaults_true():
    assert is_auto_update_enabled(None) is True
    assert is_auto_update_enabled({}) is True
    assert is_auto_update_enabled({"auto_update": True}) is True
    assert is_auto_update_enabled({"auto_update": False}) is False


def test_skip_names_protect_orion_and_graphify():
    assert should_skip(Path("_orion") / "x")
    assert should_skip(Path("graphify-out") / "graph.json")
    assert not should_skip(Path("stamina") / "updater.py")


def test_git_args_allowed_whitelist():
    assert git_args_allowed(["status", "--porcelain"])
    assert git_args_allowed(["fetch", "origin", "master"])
    assert git_args_allowed(["merge", "--ff-only", "refs/tags/v3.9.3"])
    assert git_args_allowed(["merge-base", "--is-ancestor", "HEAD", "origin/master"])
    assert not git_args_allowed(["reset", "--hard"])
    assert not git_args_allowed(["clean", "-fd"])
    assert not git_args_allowed(["checkout", "--", "."])
    assert not git_args_allowed(["stash", "drop"])
    assert not git_args_allowed(["merge", "origin/master"])  # без --ff-only
    assert not git_args_allowed(["fetch", "origin", "--force"])
    assert not git_args_allowed(["pull", "--ff-only"])


def test_inspect_git_plain_folder(tmp_path: Path):
    state = inspect_git(tmp_path)
    assert state.is_repo is False
    assert is_git_checkout(tmp_path) is False


def test_inspect_git_detects_dot_git(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    assert is_git_checkout(tmp_path) is True

    def fake_git(_root, args, timeout=30):
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return 0, "master", ""
        if args[:1] == ["rev-parse"] and "HEAD" in args:
            return 0, "abc123", ""
        if args[:1] == ["status"]:
            return 0, " M stamina/updater.py", ""
        return 1, "", "unexpected"

    monkeypatch.setattr("stamina.updater._git", fake_git)
    state = inspect_git(tmp_path)
    assert state.is_repo is True
    assert state.dirty is True
    assert state.branch == "master"


def test_can_fast_forward_rejects_dirty_and_other_branch(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()

    def state_like(branch="master", dirty=False, head="aaa"):
        def fake_inspect(_root=None):
            return GitState(is_repo=True, branch=branch, dirty=dirty, head=head)
        return fake_inspect

    monkeypatch.setattr("stamina.updater.inspect_git", state_like(dirty=True))
    ok, reason = can_fast_forward(tmp_path, "refs/tags/v9.9.9")
    assert ok is False
    assert "грязн" in reason

    monkeypatch.setattr("stamina.updater.inspect_git", state_like(branch="agent/orion/english-grammar"))
    ok, reason = can_fast_forward(tmp_path, "refs/tags/v9.9.9")
    assert ok is False
    assert "master" in reason


def test_try_git_fast_forward_uses_only_ff_only(tmp_path: Path, monkeypatch):
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []

    def fake_git(_root, args, timeout=30):
        calls.append(list(args))
        if not git_args_allowed(args):
            raise RuntimeError("forbidden " + " ".join(args))
        if args[:1] == ["fetch"]:
            return 0, "", ""
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return 0, "master", ""
        if args[:2] == ["rev-parse", "--verify"]:
            if args[-1] in {"refs/tags/v9.9.9", "HEAD"}:
                return 0, {"refs/tags/v9.9.9": "def456", "HEAD": "abc123"}[args[-1]], ""
            return 0, args[-1], ""
        if args[0] == "rev-parse" and "HEAD" in args:
            return 0, "abc123", ""
        if args[:1] == ["status"]:
            return 0, "", ""
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return 0, "", ""
        if args[:2] == ["merge", "--ff-only"]:
            return 0, "Fast-forward", ""
        if args[:1] == ["show"]:
            return 0, '__version__ = "9.9.9"\n', ""
        return 1, "", "unexpected " + " ".join(args)

    monkeypatch.setattr("stamina.updater._git", fake_git)
    monkeypatch.setattr("stamina.updater.maybe_pip_install", lambda *a, **k: None)
    monkeypatch.setattr("stamina.updater.write_update_notice", lambda *a, **k: None)
    monkeypatch.setattr("stamina.updater._log", lambda *_a, **_k: None)
    result = try_git_fast_forward(tmp_path, "v9.9.9")
    assert result.status == "ff"
    assert any(c[:2] == ["merge", "--ff-only"] for c in calls)
    assert all(git_args_allowed(c) for c in calls)
    verbs = {c[0] for c in calls}
    assert not (verbs & {"reset", "clean", "checkout", "stash", "pull"})


def test_run_auto_update_disabled_does_not_fetch(monkeypatch):
    called = {"fetch": False}

    def boom():
        called["fetch"] = True
        raise AssertionError("fetch_latest must not be called")

    monkeypatch.setattr("stamina.updater.fetch_latest", boom)
    result = run_auto_update(settings={"auto_update": False}, dest_root=Path("."))
    assert result.status == "disabled"
    assert called["fetch"] is False


def test_run_auto_update_current_when_not_newer(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("stamina.updater.fetch_latest", lambda: _info("0.0.1"))
    monkeypatch.setattr("stamina.updater._log", lambda *_a, **_k: None)
    result = run_auto_update(settings={"auto_update": True}, dest_root=tmp_path)
    assert result.status == "current"


def test_run_auto_update_skips_dirty_git_and_does_not_stage(monkeypatch, tmp_path: Path):
    (tmp_path / ".git").mkdir()
    staged = {"n": 0}
    fetched = {"n": 0}

    monkeypatch.setattr("stamina.updater.fetch_latest", lambda: _info("9.9.9"))
    monkeypatch.setattr("stamina.updater._log", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "stamina.updater.try_git_fast_forward",
        lambda *a, **k: AutoUpdateResult("skipped", "9.9.9", "рабочая копия грязная или есть неотслеживаемые файлы"),
    )

    def no_stage(*a, **k):
        staged["n"] += 1
        raise AssertionError("ZIP must not be staged on a git checkout")

    monkeypatch.setattr("stamina.updater.stage_release", no_stage)
    result = run_auto_update(settings={"auto_update": True}, dest_root=tmp_path)
    assert result.status == "skipped"
    assert staged["n"] == 0
    assert "грязн" in result.reason


def test_run_auto_update_offline_is_error_not_exception(monkeypatch, tmp_path: Path):
    import urllib.error

    def fail():
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("stamina.updater.fetch_latest", fail)
    monkeypatch.setattr("stamina.updater._log", lambda *_a, **_k: None)
    result = run_auto_update(settings={"auto_update": True}, dest_root=tmp_path)
    assert result.status == "error"
    assert "сети" in result.reason or "GitHub" in result.reason


def test_stage_and_apply_pending(monkeypatch, tmp_path: Path):
    src = _tree(tmp_path, "9.9.9")
    blob = _zip_of_tree(src)
    dest = tmp_path / "install"
    dest.mkdir()
    (dest / "old.txt").write_text("keep", encoding="utf-8")
    staging = tmp_path / "pending-update"
    state = tmp_path / "state"
    state.mkdir()

    monkeypatch.setattr("stamina.updater._state_dir", lambda: state)

    def fake_urlopen(_req, timeout=120):
        return _Resp(blob)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("stamina.updater.maybe_pip_install", lambda *a, **k: None)

    staged = stage_release(_info("9.9.9"), staging_dir=staging)
    assert (staged / ".st_update_version").read_text(encoding="utf-8") == "9.9.9"
    assert (staged / "tree" / "stamina" / "app.py").read_text(encoding="utf-8") == "ok"

    result = apply_pending_update(dest_root=dest, staging_dir=staging)
    assert result.status == "applied"
    assert (dest / "stamina" / "app.py").read_text(encoding="utf-8") == "ok"
    assert (dest / "old.txt").read_text(encoding="utf-8") == "keep"
    assert not staging.exists()
    notice = json.loads((state / "update_notice.json").read_text(encoding="utf-8"))
    assert notice["version"] == "9.9.9"
    assert notice["kind"] == "applied"


def test_stage_release_refuses_http(tmp_path: Path):
    with pytest.raises(RuntimeError, match="HTTPS"):
        stage_release(_info("9.9.9", url="http://example.com/x.zip"), staging_dir=tmp_path / "p")
    assert not list(tmp_path.iterdir()) or not (tmp_path / "p").exists()


def test_apply_tree_skips_orion(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    (src / "stamina").mkdir(parents=True)
    (src / "stamina" / "updater.py").write_text("new", encoding="utf-8")
    (src / "_orion").mkdir()
    (src / "_orion" / "secret.txt").write_text("no", encoding="utf-8")
    (dest / "_orion").mkdir(parents=True)
    (dest / "_orion" / "secret.txt").write_text("keep", encoding="utf-8")
    apply_tree(src, dest)
    assert (dest / "stamina" / "updater.py").read_text(encoding="utf-8") == "new"
    assert (dest / "_orion" / "secret.txt").read_text(encoding="utf-8") == "keep"


def test_run_auto_update_stages_plain_install(monkeypatch, tmp_path: Path):
    src = _tree(tmp_path, "9.9.9")
    blob = _zip_of_tree(src)
    install = tmp_path / "install"
    install.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr("stamina.updater._state_dir", lambda: state)
    monkeypatch.setattr("stamina.updater.fetch_latest", lambda: _info("9.9.9"))
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: _Resp(blob))
    monkeypatch.setattr("stamina.updater._log", lambda *_a, **_k: None)
    result = run_auto_update(settings={"auto_update": True}, dest_root=install)
    assert result.status == "staged"
    assert result.notice_kind == "staged"
    assert (state / "pending-update" / "tree" / "main.py").is_file()
    # mid-session: файлы установки ещё не перезаписаны
    assert not (install / "main.py").exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
