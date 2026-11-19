"""Verbatim open-licence German grammar sources: schema and integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "stamina" / "languages" / "plugins" / "de" / "grammar" / "sources"
SOURCE_IDS = ("grimm_grammar", "zum_grammatik_kiste")
LICENSE_FIELDS = ("name", "publisher", "author", "url", "license", "license_url")


def _source_dirs() -> list[Path]:
    found = [SOURCES / sid for sid in SOURCE_IDS if (SOURCES / sid).is_dir()]
    assert found, f"No imported sources under {SOURCES}"
    return found


def _topic_files(source_dir: Path) -> list[Path]:
    reserved = {"source.json", "index.json", "skipped.json"}
    return sorted(p for p in source_dir.glob("*.json") if p.name not in reserved)


def test_expected_source_folders_exist() -> None:
    for sid in SOURCE_IDS:
        assert (SOURCES / sid / "source.json").is_file(), f"missing source.json for {sid}"
        assert (SOURCES / sid / "index.json").is_file(), f"missing index.json for {sid}"


@pytest.mark.parametrize("source_dir", _source_dirs(), ids=lambda p: p.name)
def test_source_json_has_license_fields(source_dir: Path) -> None:
    data = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
    for field in LICENSE_FIELDS:
        value = data.get(field)
        assert isinstance(value, str) and value.strip(), f"{source_dir.name}: missing {field}"
    assert data["license"] == "CC BY 4.0"
    assert "creativecommons.org/licenses/by/4.0" in data["license_url"]
    attribution = data.get("attribution")
    assert isinstance(attribution, dict)
    for lang in ("ru", "en", "de"):
        assert isinstance(attribution.get(lang), str) and attribution[lang].strip()


@pytest.mark.parametrize("source_dir", _source_dirs(), ids=lambda p: p.name)
def test_every_topic_file_is_valid(source_dir: Path) -> None:
    files = _topic_files(source_dir)
    assert files, f"{source_dir.name}: no topic files"
    ids: set[str] = set()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path.name
        assert isinstance(data.get("id"), str) and data["id"].strip(), path.name
        assert data["id"] not in ids, f"duplicate id {data['id']}"
        ids.add(data["id"])
        url = data.get("original_url")
        assert isinstance(url, str) and url.startswith("http"), f"{path.name}: original_url"
        sections = data.get("sections")
        assert isinstance(sections, list) and len(sections) > 0, f"{path.name}: sections"
        for section in sections:
            assert isinstance(section, dict), path.name
            assert "heading" in section and "text" in section, path.name
            assert isinstance(section["text"], str) and section["text"].strip(), path.name
        assert isinstance(data.get("examples"), list), path.name
        assert isinstance(data.get("exercises"), list), path.name
        assert data.get("explanation_lang") in {"en", "de"}, path.name
