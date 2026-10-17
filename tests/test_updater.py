"""Тесты updater: semver, parse release, skip-list (без сети)."""
from __future__ import annotations

import json
from pathlib import Path

from stamina.updater import (
    apply_tree,
    is_newer,
    markdown_to_plain,
    normalize_version,
    parse_release_payload,
    parse_semver,
    should_skip,
)


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
