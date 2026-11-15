"""Kaikki sqlite sits under the curated A1 lists and does not replace them."""
from __future__ import annotations

import sqlite3

from stamina.languages.core.base import WordEntry
from stamina.languages.core.sqlite_vocab import attach_sqlite, word_line
from stamina.languages.plugins.de import GermanPlugin, GermanVocabSource


def _db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE words (
            slug TEXT NOT NULL,
            lemma TEXT,
            pos TEXT,
            lang TEXT,
            rank INTEGER,
            band TEXT,
            cefr TEXT,
            gender TEXT,
            gloss_en TEXT,
            gloss_ru TEXT,
            gloss_native TEXT,
            example TEXT,
            source TEXT,
            score INTEGER,
            PRIMARY KEY (lang, slug)
        )
        """
    )
    rows = [
        ("haus-noun", "Haus", "noun", "de", 10, "goethe-a1", "A1", "n", "house", "", "", "Das Haus.", "Kaikki", 3),
        ("baum-noun", "Baum", "noun", "de", 50, "goethe-a2", "A2", "m", "tree", "дерево", "", "", "Kaikki", 10),
        ("real-adj", "real", "adj", "de", 0, "rest", "", "", "real", "реальный", "", "", "Kaikki", 10),
        ("real-adj", "real", "adj", "es", 0, "rest", "", "", "royal", "королевский", "", "", "Kaikki", 10),
    ]
    conn.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_curated_word_wins_and_languages_stay_apart(tmp_path):
    path = tmp_path / "vocab.sqlite"
    _db(path)
    src = GermanVocabSource()
    src._words = {
        "haus-noun": WordEntry(
            slug="haus-noun",
            lemma="Haus",
            pos="noun",
            language="de",
            translations={"ru": ["дом"]},
            frequency_band="goethe-a1",
            frequency_rank=3,
        )
    }
    assert attach_sqlite(src, path, "de")
    assert src.get_word("haus-noun").translations["ru"][0] == "дом"
    baum = src.get_word("baum-noun")
    assert baum.translations["ru"][0] == "дерево"
    assert baum.morphology.german.article_sg == "der"
    assert word_line(baum).startswith("der Baum")
    assert "haus-noun" in src.get_slugs_by_freq_band("goethe-a1")
    assert "baum-noun" in src.get_slugs_by_freq_band("goethe-a2")
    assert src.get_word("real-adj").translations["ru"][0] == "реальный"
    assert "baum" in src.search("bau")[0].lemma.casefold()
    assert attach_sqlite(GermanVocabSource(), tmp_path / "missing.sqlite", "de") is False


def test_rest_band_is_a_freq_set():
    ids = [item.id for item in GermanPlugin.freq_sets]
    assert ids[0] == "goethe-a1"
    assert "rest" in ids
    screen = open(r"d:\My_New_Stamina\stamina\languages\screen.py", encoding="utf-8").read()
    assert "set_id, size, name_en, name_target, short = fs" not in screen
    assert "fs.id" in screen
