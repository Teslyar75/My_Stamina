"""Read-only Kaikki database on top of the curated A1 dictionary.

Curated entries win when the slug matches. The database lives in
data/vocab_sources/ and is not part of the git tree.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from stamina.languages.core.base import (
    ExampleSentence,
    GermanMorphology,
    MorphologyBundle,
    SpanishMorphology,
    WordEntry,
)

_CACHE: dict[tuple, list] = {}

_DE_ARTICLE = {"m": "der", "f": "die", "n": "das"}
_ES_ARTICLE = {"m": "el", "f": "la"}


def sqlite_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "vocab_sources" / "kaikki" / "vocab.sqlite"


def word_line(word: WordEntry) -> str:
    ru = ", ".join((word.translations.get("ru") or [])[:3])
    german = word.morphology.german if word.morphology else None
    spanish = word.morphology.spanish if word.morphology else None
    if spanish and spanish.singular:
        head = spanish.singular
    elif german and german.article_sg:
        head = f"{german.article_sg} {word.lemma}"
    else:
        head = word.lemma
    return f"{head} — {ru}" if ru else head


def _split(text: str) -> list[str]:
    return [part for part in (text or "").split(" | ") if part]


def entry_from_row(row: sqlite3.Row) -> WordEntry:
    ru = _split(row["gloss_ru"])
    en = _split(row["gloss_en"])
    native = _split(row["gloss_native"])
    if not ru:
        ru = en or native
    translations: dict[str, list[str]] = {}
    if ru:
        translations["ru"] = ru
    if en:
        translations["en"] = en
    gender = row["gender"] or ""
    lang = row["lang"]
    pos = row["pos"] or ""
    lemma = row["lemma"] or ""
    german = None
    spanish = None
    if lang == "de" and pos == "noun" and gender in _DE_ARTICLE:
        article = _DE_ARTICLE[gender]
        german = GermanMorphology(article_sg=article, nominative_sg=f"{article} {lemma}")
    if lang == "es" and pos == "noun" and gender in _ES_ARTICLE:
        article = _ES_ARTICLE[gender]
        spanish = SpanishMorphology(gender=gender, singular=f"{article} {lemma}")
    examples: list[ExampleSentence] = []
    if row["example"]:
        examples.append(
            ExampleSentence(
                id="kaikki",
                text=row["example"],
                translation=ru[0] if ru else "",
                source=row["source"] or "Kaikki, CC BY-SA 4.0",
                cefr_level=row["cefr"] or "",
            )
        )
    return WordEntry(
        slug=row["slug"],
        lemma=lemma,
        pos=pos,
        language=lang,
        cefr_level=row["cefr"] or "",
        frequency_rank=int(row["rank"] or 0),
        frequency_band=row["band"] or "",
        translations=translations,
        morphology=MorphologyBundle(gender=gender or None, german=german, spanish=spanish),
        examples=examples,
        tags={"kaikki"},
        source=row["source"] or "",
    )


def attach_sqlite(source, path: Path, lang: str) -> bool:
    """Override lookups. Curated source._words stay first. Missing file is a no-op."""
    if not path.is_file():
        return False
    try:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("SELECT slug FROM words WHERE lang=? LIMIT 1", (lang,)).fetchone()
    except (sqlite3.Error, OSError):
        return False

    original_band = source.get_slugs_by_freq_band
    original_cefr = source.get_slugs_by_cefr
    original_all = source.get_all_slugs
    original_search = source.search
    original_set = source.get_set
    words = source._words
    stamp = path.stat().st_mtime_ns

    def cached(kind: str, extra: str, loader):
        key = (str(path), stamp, lang, kind, extra)
        hit = _CACHE.get(key)
        if hit is None:
            hit = loader()
            _CACHE[key] = hit
        return list(hit)

    def get_word(slug: str):
        found = words.get(slug)
        if found is not None:
            return found
        try:
            row = conn.execute(
                "SELECT * FROM words WHERE lang=? AND slug=?",
                (lang, slug),
            ).fetchone()
        except sqlite3.Error:
            return None
        return entry_from_row(row) if row else None

    def get_all_slugs() -> list[str]:
        def load():
            try:
                rows = conn.execute("SELECT slug FROM words WHERE lang=?", (lang,)).fetchall()
            except sqlite3.Error:
                return original_all()
            seen = {row[0] for row in rows}
            seen.update(words)
            return sorted(seen)

        return cached("all", "", load)

    def get_slugs_by_freq_band(band: str) -> list[str]:
        def load():
            try:
                rows = conn.execute(
                    "SELECT slug, rank FROM words WHERE lang=? AND band=?",
                    (lang, band),
                ).fetchall()
            except sqlite3.Error:
                return original_band(band)
            ranked = []
            seen = set()
            for slug, rank in rows:
                word = words.get(slug)
                if word is not None and word.frequency_band != band:
                    continue
                ranked.append((int(rank or 0) or 10**9, slug))
                seen.add(slug)
            for slug, word in words.items():
                if word.frequency_band == band and slug not in seen:
                    ranked.append((word.frequency_rank or 10**9, slug))
            ranked.sort()
            return [slug for _rank, slug in ranked]

        return cached("band", band, load)

    def get_slugs_by_cefr(level: str) -> list[str]:
        def load():
            try:
                rows = conn.execute(
                    "SELECT slug FROM words WHERE lang=? AND cefr=?",
                    (lang, level),
                ).fetchall()
            except sqlite3.Error:
                return original_cefr(level)
            seen = {row[0] for row in rows}
            for slug, word in words.items():
                if word.cefr_level == level:
                    seen.add(slug)
            return sorted(seen)

        return cached("cefr", level, load)

    def search(query: str, filters: dict | None = None):
        needle = (query or "").casefold()
        if not needle:
            return []
        found = original_search(query, filters)
        have = {word.slug for word in found}
        try:
            rows = conn.execute(
                "SELECT * FROM words WHERE lang=? AND lower(lemma) LIKE ? LIMIT 40",
                (lang, f"%{needle}%"),
            ).fetchall()
        except sqlite3.Error:
            return found
        for row in rows:
            if row["slug"] in have or row["slug"] in words:
                continue
            found.append(entry_from_row(row))
            if len(found) >= 40:
                break
        return found

    def get_set(set_id: str):
        slugs = get_slugs_by_freq_band(set_id)[:500]
        out = []
        for slug in slugs:
            word = get_word(slug)
            if word is not None:
                out.append(word)
        if out:
            return out
        return original_set(set_id)

    source.get_word = get_word
    source.get_all_slugs = get_all_slugs
    source.get_slugs_by_freq_band = get_slugs_by_freq_band
    source.get_slugs_by_cefr = get_slugs_by_cefr
    source.search = search
    source.get_set = get_set
    source._sqlite = conn
    return True
