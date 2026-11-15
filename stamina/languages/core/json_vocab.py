"""Загрузка словаря языка из vocab_a1.json в WordEntry."""
from __future__ import annotations

import json
from pathlib import Path

from stamina.languages.core.base import (
    ExampleSentence,
    GermanMorphology,
    MorphologyBundle,
    SpanishMorphology,
    WordEntry,
)


def load_vocab_file(path: Path) -> dict[str, WordEntry]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    words = data.get("words") if isinstance(data, dict) else data
    out: dict[str, WordEntry] = {}
    for obj in words or []:
        entry = _word_from_obj(obj)
        out[entry.slug] = entry
    return out


def _word_from_obj(obj: dict) -> WordEntry:
    examples = [
        ExampleSentence(
            id=str(ex.get("id") or ""),
            text=ex.get("text") or "",
            translation=ex.get("translation") or "",
            source=ex.get("source") or "",
            cefr_level=ex.get("cefr_level") or "A1",
            word_slugs=list(ex.get("word_slugs") or []),
        )
        for ex in (obj.get("examples") or [])
    ]
    german = None
    raw_de = obj.get("german") or None
    if raw_de:
        german = GermanMorphology(
            article_sg=raw_de.get("article") or "",
            nominative_sg=raw_de.get("nominative_sg") or "",
            nominative_pl=raw_de.get("nominative_pl") or "",
        )
    spanish = None
    raw_es = obj.get("spanish") or None
    if raw_es:
        spanish = SpanishMorphology(
            gender=raw_es.get("gender") or "",
            singular=raw_es.get("singular") or "",
            plural=raw_es.get("plural") or "",
            infinitive=raw_es.get("infinitive") or "",
        )
    return WordEntry(
        slug=obj["slug"],
        lemma=obj["lemma"],
        pos=obj["pos"],
        language=obj["language"],
        cefr_level=obj.get("cefr_level") or "A1",
        frequency_rank=int(obj.get("frequency_rank") or 0),
        frequency_band=obj.get("frequency_band") or "",
        translations={k: list(v) for k, v in (obj.get("translations") or {}).items()},
        morphology=MorphologyBundle(gender=obj.get("gender") or None, german=german, spanish=spanish),
        examples=examples,
        tags=set(obj.get("tags") or []),
        source=obj.get("source") or "",
        verified=bool(obj.get("verified")),
    )
