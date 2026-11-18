"""Словари A1, которые собирает tools/build_lang_vocab_a1.py."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core import get_registry
from stamina.languages.core.json_vocab import load_vocab_file

ROOT = Path(__file__).resolve().parents[1]


def _words(code: str):
    return load_vocab_file(ROOT / "stamina" / "languages" / "plugins" / code / "vocab_a1.json")


def test_german_a1_file():
    words = _words("de")
    assert len(words) >= 300
    nouns = [w for w in words.values() if w.pos == "noun"]
    assert len(nouns) > 80
    for word in words.values():
        assert word.language == "de"
        assert word.cefr_level == "A1"
        assert word.frequency_band == "goethe-a1"
        assert word.frequency_rank > 0
        assert word.translations["ru"]
        assert word.examples
        assert word.examples[0].text
        assert word.examples[0].translation
        assert "Tatoeba #" in word.examples[0].source
        assert "CC BY 2.0 FR" in word.examples[0].source
    for word in nouns:
        assert word.morphology.german is not None
        assert word.morphology.german.article_sg in {"der", "die", "das"}


def test_spanish_a1_file():
    words = _words("es")
    assert len(words) >= 300
    nouns = [w for w in words.values() if w.pos == "noun"]
    assert len(nouns) > 80
    for word in words.values():
        assert word.language == "es"
        assert word.cefr_level == "A1"
        assert word.frequency_band == "cervantes-a1"
        assert word.frequency_rank > 0
        assert word.translations["ru"]
        assert word.examples
        assert "Tatoeba #" in word.examples[0].source
    for word in nouns:
        shown = word.morphology.spanish.singular or word.morphology.spanish.plural
        assert shown.split()[0] in {"el", "la", "los", "las"}


def _band_slug_count(code: str, band: str) -> int:
    return sum(1 for w in _words(code).values() if w.frequency_band == band)


def test_plugins_load_a1_sets():
    reg = get_registry()
    reg.discover()
    assert _band_slug_count("de", "goethe-a1") >= 300
    assert _band_slug_count("es", "cervantes-a1") >= 300
    german = reg.get("de").load_vocab()
    haus = german.get_word("haus-noun")
    assert haus is not None
    assert haus.morphology.german.article_sg == "das"
    assert haus.translations["ru"][0] == "дом"
