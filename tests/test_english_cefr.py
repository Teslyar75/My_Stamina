"""Наборы CEFR (CEFR-J/Octanove + Tatoeba + Wiktionary): честные данные, слияние без дублей."""
import json

import pytest

from stamina.english import cefr, paths
from stamina.english.vocab import Vocab


def test_a1_available():
    assert "A1" in cefr.available()
    assert cefr.SET_ID["A1"] == "cefr-a1"


def test_a2_available():
    assert "A2" in cefr.available()
    assert cefr.SET_ID["A2"] == "cefr-a2"


LEVELS_ALL = ["A1", "A2", "B1.1", "B1.2", "B2.1", "B2.2", "C1", "C2"]
REAL_LICENSES = ("CC BY 2.0 FR", "CC BY-SA 4.0")


def test_all_eight_levels_present():
    assert cefr.available() == LEVELS_ALL


def test_blocks_are_fifty_word_portions():
    """Порция = 50 слов, порядок файла сохраняется, последняя может быть короче."""
    assert 40 <= cefr.BLOCK_SIZE <= 60
    words = cefr.prepared("A1")
    blocks = cefr.blocks("A1")
    assert blocks, "A1 должен делиться на порции"
    assert all(len(b) == cefr.BLOCK_SIZE for b in blocks[:-1])
    assert 0 < len(blocks[-1]) <= cefr.BLOCK_SIZE
    assert sum(len(b) for b in blocks) == len(words)
    flat = [w["slug"] for b in blocks for w in b]
    assert flat == [w["slug"] for w in words]


@pytest.mark.parametrize("level", cefr.available())
def test_level_data_is_honest(level):
    """Реальные данные: у каждого примера источник и лицензия, пробелы помечены."""
    data = cefr.load(level) or {}
    assert data["level"] == level and data.get("schema") == 2
    assert data["source"]["license"] != cefr.UNKNOWN_LICENSE
    assert {"tatoeba", "wiktionary"} <= set(data.get("sources") or {})
    words = cefr.entries(level)
    assert len(words) >= 500, level
    for w in words:
        gaps = w.get("gaps") or []
        assert w["word"] and w["pos"] and w.get("topic")
        assert w.get("ru") or "ru" in gaps, (level, w["word"])
        assert w.get("ipa") or "ipa" in gaps, (level, w["word"])
        n = len(w["sentences"])
        assert n <= cefr.MAX_SENTENCES
        if n < cefr.MAX_SENTENCES:
            assert f"examples:{n}/5" in gaps, (level, w["word"])
        seen = set()
        for s in w["sentences"]:
            assert s["en"].strip()
            assert s["source"] in ("tatoeba", "wiktionary")
            assert s["license"] in REAL_LICENSES
            assert s["ru"].strip() or "examples_ru" in gaps
            assert s["en"].lower() not in seen, (level, w["word"], s["en"])
            seen.add(s["en"].lower())


def test_no_generated_sentences():
    for level in cefr.available():
        for w in cefr.entries(level):
            assert all(s["source"] != "generated" for s in w["sentences"])


def test_levels_do_not_share_words():
    seen: dict[str, str] = {}
    for level in cefr.available():
        for w in cefr.entries(level):
            key = w["word"].strip().lower()
            assert key not in seen, f"{key}: {seen.get(key)} и {level}"
            seen[key] = level


def test_prepared_has_everything_for_card():
    w = cefr.prepared("A1")[0]
    assert w["slug"] and w["sentences"]
    assert len(w["sentences"]) <= cefr.MAX_SENTENCES
    assert w["sets"] == ["cefr-a1"]
    assert w["level"] == "A1"
    assert w["topic"] and w["freq_rank"] > 0
    assert all(len(x["sentences"]) >= cefr.MIN_SENTENCES for x in cefr.prepared("C2"))


def test_merge_into_vocab():
    v = Vocab()
    prepared = cefr.prepared("A1")
    assert cefr.merge_into(v, "A1") == len(prepared)
    words = v.in_set("cefr-a1")
    assert len(words) == len(prepared)
    assert words[0]["word"] == prepared[0]["word"]   # порядок из файла
    # синтетический ранг: в частотные наборы такие слова не попадают
    assert all(w["rank"] > 20000 for w in words)
    assert v.in_set("top-1000") == []


def test_levels_live_side_by_side():
    v = Vocab()
    cefr.merge_into(v, "A1")
    cefr.merge_into(v, "A2")
    a1 = v.in_set("cefr-a1")
    a2 = v.in_set("cefr-a2")
    assert len(a1) == len(cefr.prepared("A1"))
    assert len(a2) == len(cefr.prepared("A2"))
    assert all("cefr-a2" in w["sets"] for w in a2)
    assert not {w["slug"] for w in a1} & {w["slug"] for w in a2}
    cefr.merge_into(v, "A2")
    assert len(v.in_set("cefr-a2")) == len(a2)


def test_merge_is_idempotent_and_keeps_existing():
    v = Vocab()
    v.add_record({"word": "apple", "ru": "яблоко", "rank": 120, "pos": "noun",
                  "sentences": [{"en": "An apple a day.", "ru": "Яблоко в день."}]})
    cefr.merge_into(v, "A1")
    again = cefr.merge_into(v, "A1")
    assert again == 0                     # второй раз новых слов нет
    apple = v.get("apple")
    assert "cefr-a1" in apple["sets"]     # метка набора добавлена
    assert apple["rank"] == 120           # частотный ранг сохранён
    assert len(v.sentences(apple)) >= 5   # примеры добраны до пяти
    assert len([w for w in v.words if w["word"] == "apple"]) == 1


def test_sets_file_matches_loader():
    raw = json.loads((paths.DATA_DIR / "sets" / "cefr_a1.json").read_text(encoding="utf-8"))
    assert raw["id"] == "cefr-a1"
    assert len(raw["words"]) == len(cefr.entries("A1"))
