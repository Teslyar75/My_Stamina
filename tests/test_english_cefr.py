"""Наборы CEFR: загрузка, пять примеров на слово, слияние без дублей."""
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


@pytest.mark.parametrize("level", cefr.available())
def test_level_data_quality(level):
    words = cefr.entries(level)
    assert len(words) >= 20, level
    for w in words:
        assert w["word"] and w["ru"] and w["pos"]
        assert w.get("ipa"), (level, w["word"])
        assert len(w["sentences"]) >= cefr.MIN_SENTENCES, (level, w["word"])
        seen = set()
        for s in w["sentences"]:
            assert s["en"].strip() and s["ru"].strip()
            assert s["en"].lower() not in seen, (level, w["word"], s["en"])
            seen.add(s["en"].lower())
    data = cefr.load(level) or {}
    assert data["level"] == level
    assert data["source"]["license"].startswith("CC BY-SA")


def test_levels_do_not_share_words():
    seen: dict[str, str] = {}
    for level in cefr.available():
        for w in cefr.entries(level):
            key = w["word"].strip().lower()
            assert key not in seen, f"{key}: {seen.get(key)} и {level}"
            seen[key] = level



def test_prepared_has_everything_for_card():
    w = cefr.prepared("A1")[0]
    assert w["slug"] == "apple"
    assert len(w["sentences"]) == cefr.MAX_SENTENCES
    assert w["sets"] == ["cefr-a1"]
    assert w["level"] == "A1"
    assert w["definition"]


def test_merge_into_vocab():
    v = Vocab()
    assert cefr.merge_into(v, "A1") == len(cefr.entries("A1"))
    words = v.in_set("cefr-a1")
    assert len(words) == len(cefr.entries("A1"))
    assert words[0]["word"] == cefr.entries("A1")[0]["word"]   # порядок из файла
    # синтетический ранг: в частотные наборы такие слова не попадают
    assert all(w["rank"] > 20000 for w in words)
    assert v.in_set("top-1000") == []


def test_levels_live_side_by_side():
    v = Vocab()
    cefr.merge_into(v, "A1")
    cefr.merge_into(v, "A2")
    a1 = v.in_set("cefr-a1")
    a2 = v.in_set("cefr-a2")
    assert len(a1) == len(cefr.entries("A1"))
    assert len(a2) == len(cefr.entries("A2"))
    assert all("cefr-a2" in w["sets"] for w in a2)
    assert not {w["slug"] for w in a1} & {w["slug"] for w in a2}
    # второе слияние ничего не ломает
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
