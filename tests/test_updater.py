"""Тесты updater: semver, parse release, skip-list, защита путей и состава архива (без сети)."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from stamina.updater import (
    ReleaseInfo,
    apply_tree,
    assert_release_matches,
    dev_checkout_error,
    download_and_apply,
    is_newer,
    markdown_to_plain,
    normalize_version,
    parse_release_payload,
    parse_semver,
    safe_extract,
    should_skip,
    tree_version,
)


def test_dev_checkout_blocks_button_update(tmp_path):
    """Рабочая копия git: кнопка обновления затёрла бы незакоммиченные правки."""
    (tmp_path / ".git").mkdir()
    assert dev_checkout_error(tmp_path) is not None


def test_plain_install_allows_button_update(tmp_path):
    """У пилота обычная установка без git — кнопка работает."""
    assert dev_checkout_error(tmp_path) is None


def test_nested_checkout_is_recognised(tmp_path):
    """Программа лежит внутри репозитория (например .venv рядом с .git выше)."""
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "My_Stamina-master"
    nested.mkdir()
    assert dev_checkout_error(nested) is not None


def test_normalize_version():
    assert normalize_version("v3.7.0") == "3.7.0"
    assert normalize_version("3.7.0") == "3.7.0"


def test_parse_semver():
    assert parse_semver("v1.2.3")[:3] == (1, 2, 3)
    assert parse_semver("10.0.1")[:3] == (10, 0, 1)


def test_is_newer():
    assert is_newer("3.7.0", "3.6.0")
    assert is_newer("v4.0.0", "3.9.9")
    assert not is_newer("3.6.0", "3.7.0")
    assert not is_newer("3.7.0", "3.7.0")


def test_parse_release_payload():
    raw = {
        "tag_name": "v3.7.0",
        "name": "Star Typing v3.7.0",
        "body": "### Added\n- updates",
        "html_url": "https://github.com/Teslyar75/My_Stamina/releases/tag/v3.7.0",
        "zipball_url": "https://api.github.com/repos/Teslyar75/My_Stamina/zipball/v3.7.0",
    }
    info = parse_release_payload(raw)
    assert info.version == "3.7.0"
    assert info.tag == "v3.7.0"
    assert "updates" in info.body
    assert info.zipball_url.endswith("v3.7.0")


def test_markdown_to_plain():
    md = "## Title\n\n- **bold** item\n- [link](http://x)\n"
    plain = markdown_to_plain(md)
    assert "bold" in plain
    assert "link" in plain
    assert "http" not in plain


def test_should_skip():
    assert should_skip(Path(".venv") / "Lib" / "x.py")
    assert should_skip(Path("models") / "vosk" / "a")
    assert should_skip(Path("cache") / "t.json")
    assert should_skip(Path("stamina") / "__pycache__" / "x.pyc")
    assert not should_skip(Path("stamina") / "updater.py")
    assert not should_skip(Path("requirements.txt"))


def test_apply_tree_respects_skip(tmp_path: Path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    (src / "stamina").mkdir(parents=True)
    (src / "stamina" / "updater.py").write_text("ok", encoding="utf-8")
    (src / ".venv" / "x").mkdir(parents=True)
    (src / ".venv" / "x" / "keep.py").write_text("no", encoding="utf-8")
    (src / "models").mkdir()
    (src / "models" / "m.bin").write_bytes(b"\x00")
    (dest / ".venv" / "x").mkdir(parents=True)
    (dest / ".venv" / "x" / "keep.py").write_text("old", encoding="utf-8")

    n = apply_tree(src, dest)
    assert n >= 1
    assert (dest / "stamina" / "updater.py").read_text(encoding="utf-8") == "ok"
    assert (dest / ".venv" / "x" / "keep.py").read_text(encoding="utf-8") == "old"
    assert not (dest / "models" / "m.bin").exists()


def test_changelog_notes_tool():
    from tools.changelog_notes import extract_notes

    md = "# H\n\n## 3.7.0 — day\n\n### Added\n- foo\n\n## 3.6.0 — old\n\n- bar\n"
    notes = extract_notes(md, "v3.7.0")
    assert "foo" in notes
    assert "bar" not in notes


def _zip_with(names: list[str]) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, "payload")
    return zipfile.ZipFile(io.BytesIO(buf.getvalue()))


def test_safe_extract_keeps_normal_release_tree(tmp_path: Path):
    with _zip_with(["repo-abc123/main.py", "repo-abc123/stamina/app.py"]) as zf:
        safe_extract(zf, tmp_path)
    assert (tmp_path / "repo-abc123" / "main.py").is_file()


@pytest.mark.parametrize(
    "evil",
    [
        "../escape.py",
        "../../escape.py",
        "repo/../../escape.py",
        "/absolute/escape.py",
        "C:/Windows/escape.py",
        "repo\\..\\..\\escape.py",
    ],
)
def test_safe_extract_rejects_paths_outside_target(tmp_path: Path, evil: str):
    with _zip_with([evil]) as zf:
        with pytest.raises(RuntimeError, match="пути вне папки"):
            safe_extract(zf, tmp_path)
    assert not (tmp_path.parent / "escape.py").exists()
    assert not list(tmp_path.rglob("escape.py"))


def _tree_with_version(tmp_path: Path, body: str | None) -> Path:
    src = tmp_path / "My_Stamina-abc123"
    (src / "stamina").mkdir(parents=True, exist_ok=True)
    if body is not None:
        (src / "stamina" / "__init__.py").write_text(body, encoding="utf-8")
    return src


def test_tree_version_reads_downloaded_release(tmp_path: Path):
    src = _tree_with_version(tmp_path, '__version__ = "3.7.1"\nAPP_NAME = "Star Typing"\n')
    assert tree_version(src) == "3.7.1"


def test_assert_release_matches_accepts_tag_and_v_prefix(tmp_path: Path):
    src = _tree_with_version(tmp_path, '__version__ = "3.7.1"\n')
    assert assert_release_matches(src, "3.7.1") == "3.7.1"
    assert assert_release_matches(src, "v3.7.1") == "3.7.1"


def test_assert_release_matches_rejects_wrong_content(tmp_path: Path):
    src = _tree_with_version(tmp_path, '__version__ = "3.6.9"\n')
    with pytest.raises(RuntimeError, match="архив не соответствует релизу"):
        assert_release_matches(src, "v3.7.1")


def test_assert_release_matches_needs_a_tree(tmp_path: Path):
    with pytest.raises(RuntimeError, match="нет stamina/__init__.py"):
        assert_release_matches(_tree_with_version(tmp_path, None), "3.7.1")
    with pytest.raises(RuntimeError, match="нет __version__"):
        assert_release_matches(_tree_with_version(tmp_path, "APP_NAME = 'x'\n"), "3.7.1")
    with pytest.raises(RuntimeError, match="пустой тег"):
        assert_release_matches(_tree_with_version(tmp_path, '__version__ = "3.7.1"\n'), "")


@pytest.mark.parametrize("url", ["", "http://github.com/x.zip", "ftp://zip/x"])
def test_download_refuses_untrusted_channel(tmp_path: Path, url: str):
    info = ReleaseInfo(
        tag="v3.7.1", version="3.7.1", name="x", body="",
        html_url="https://github.com/Teslyar75/My_Stamina/releases/tag/v3.7.1",
        zipball_url=url,
    )
    # отказ должен случиться до обращения в сеть
    with pytest.raises(RuntimeError, match="HTTPS"):
        download_and_apply(info, dest_root=tmp_path)
    assert not list(tmp_path.iterdir())
