"""P0: ленивый словарь — паритет с полной загрузкой, миграция неразрушающая."""
from __future__ import annotations

import json

import pytest

from stamina.english import paths, vocab_lazy as vlazy
from stamina.english.vocab import Vocab


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # сбросить кэш DATA_DIR, если модуль уже импортирован с другим путём
    import stamina.storage as storage
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "Stamina", raising=False)
    (tmp_path / "Stamina").mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("STAR_TYPING_VOCAB_FULL", raising=False)
    return tmp_path / "Stamina"


def _sample_words():
    """Мини-словарь для быстрых тестов (не 28 МБ)."""
    return [
        {
            "id": "w1", "word": "the", "slug": "the", "rank": 1, "level": "top-1000",
            "sets": ["top-1000", "top-3000"], "pos": "determiner", "pos_all": ["determiner"],
            "difficulty": "easy", "ru": "определённый артикль", "ru_src": "test",
            "tags": [], "ipa": "/ðə/", "definition": "article", "definition_source": "t",
            "sentences": [{"en": "The cat sleeps.", "ru": "Кот спит.", "context": None, "context_ru": None}],
            "example": "The cat sleeps.", "example_ru": "Кот спит.", "example_source": "t",
            "guide": "g", "notes": [], "common_mistakes": None, "sounds_like": None,
            "respelling": "THUH", "syllables": 1, "syllable_breakdown": "thuh",
        },
        {
            "id": "w2", "word": "and", "slug": "and", "rank": 2, "level": "top-1000",
            "sets": ["top-1000"], "pos": "conjunction", "pos_all": ["conjunction"],
            "difficulty": "easy", "ru": "и", "ru_src": "test",
            "tags": [], "ipa": "/ænd/", "definition": "conj", "definition_source": "t",
            "sentences": [{"en": "Tea and coffee.", "ru": "Чай и кофе.", "context": None, "context_ru": None}],
            "example": "Tea and coffee.", "example_ru": "Чай и кофе.", "example_source": "t",
            "guide": "", "notes": [], "common_mistakes": None, "sounds_like": None,
            "respelling": "AND", "syllables": 1, "syllable_breakdown": "and",
        },
        {
            "id": "w3", "word": "zebra", "slug": "zebra", "rank": 9000, "level": "top-10000",
            "sets": ["top-10000"], "pos": "noun", "pos_all": ["noun"],
            "difficulty": "medium", "ru": "зебра", "ru_src": "test",
            "tags": [], "ipa": "", "definition": "animal", "definition_source": "t",
            "sentences": [],
            "example": "A zebra ran.", "example_ru": "Зебра бежала.", "example_source": "t",
            "guide": "", "notes": [], "common_mistakes": None, "sounds_like": None,
            "respelling": "", "syllables": 2, "syllable_breakdown": "ze-bra",
        },
    ]


def test_lazy_cache_roundtrip(isolated_cache, tmp_path):
    words = _sample_words()
    src = tmp_path / "vocab.json"
    src.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    stamp = vlazy.source_stamp(src)
    root = vlazy.cache_root(isolated_cache)
    vlazy.build_cache(words, stamp, root)
    assert vlazy.cache_valid(root, stamp)
    # исходник на месте
    assert src.is_file() and json.loads(src.read_text(encoding="utf-8")) == words
    light = vlazy.load_index(root)
    assert len(light) == 3
    assert light[0]["slug"] == "the"
    assert light[0]["n_sentences"] == 1
    assert "sentences" not in light[0]
    store = vlazy.ChunkStore(root)
    heavy = store.get("the")
    assert heavy and len(heavy["sentences"]) == 1
    assert store.get("zebra")["example"] == "A zebra ran."


def test_lookups_match_full_load(isolated_cache, monkeypatch, tmp_path):
    words = _sample_words()
    data_dir = tmp_path / "edata"
    data_dir.mkdir()
    (data_dir / "vocab.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths, "VOCAB_PATH", data_dir / "vocab.json")
    monkeypatch.setattr(paths, "VOCAB_GZ_PATH", data_dir / "vocab.json.gz")
    monkeypatch.setattr(paths, "SAMPLE_PATH", data_dir / "missing_sample.json")

    monkeypatch.setenv("STAR_TYPING_VOCAB_FULL", "1")
    full = Vocab()
    full.load()
    assert full.ready and not full.lazy and len(full.words) == 3

    monkeypatch.delenv("STAR_TYPING_VOCAB_FULL", raising=False)
    lazy = Vocab()
    lazy.load()
    assert lazy.ready and lazy.lazy and len(lazy.words) == 3

    for slug in ("the", "and", "zebra"):
        a, b = lazy.get(slug), full.get(slug)
        assert a is not None and b is not None
        assert a["word"] == b["word"]
        assert a["rank"] == b["rank"]
        assert a.get("ru") == b.get("ru")
        assert a.get("pos") == b.get("pos")
        assert lazy.sentences(a) == full.sentences(b)
        assert lazy.sentence_count(a) == len(full.sentences(b))

    assert [w["slug"] for w in lazy.in_set("top-1000")] == [w["slug"] for w in full.in_set("top-1000")]
    assert [w["slug"] for w in lazy.search("ze")] == [w["slug"] for w in full.search("ze")]
    # исходный файл не тронут
    assert json.loads((data_dir / "vocab.json").read_text(encoding="utf-8")) == words


def test_real_vocab_lazy_parity_sample(isolated_cache, monkeypatch):
    """На настоящем vocab.json: выборка slug даёт те же поля, что и full load."""
    if not paths.VOCAB_PATH.is_file():
        pytest.skip("нет data/vocab.json")
    monkeypatch.setenv("STAR_TYPING_VOCAB_FULL", "1")
    full = Vocab()
    full.load()
    monkeypatch.delenv("STAR_TYPING_VOCAB_FULL", raising=False)
    lazy = Vocab()
    lazy.load()
    assert lazy.lazy and len(lazy.words) == len(full.words)
    sample = ["the", "and", "of", "computer", "algorithm", full.words[-1]["slug"]]
    for slug in sample:
        a, b = lazy.get(slug), full.get(slug)
        assert a and b
        assert a["word"] == b["word"] and a["rank"] == b["rank"]
        assert (a.get("ru") or "") == (b.get("ru") or "")
        assert lazy.sentences(a) == full.sentences(b)
    # миграция неразрушающая
    assert paths.VOCAB_PATH.stat().st_size > 1_000_000
