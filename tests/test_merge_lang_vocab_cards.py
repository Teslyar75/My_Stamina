"""Слияние карточек: одна лемма, все уникальные примеры."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec_path = ROOT / "tools" / "merge_lang_vocab_cards.py"
spec = importlib.util.spec_from_file_location("merge_lang_vocab_cards", spec_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spec) if False else spec.loader.exec_module(mod)


def test_merge_combines_examples_and_pos():
    payload = {
        "words": [
            {
                "slug": "de-prep",
                "lemma": "de",
                "pos": "prep",
                "frequency_rank": 10,
                "translations": {"ru": ["iz"]},
                "examples": [
                    {"id": "1", "text": "Il vient de Paris.", "translation": "From Paris."},
                ],
            },
            {
                "slug": "de-noun",
                "lemma": "de",
                "pos": "noun",
                "frequency_rank": 5,
                "translations": {"ru": ["de"]},
                "examples": [
                    {"id": "2", "text": "Le DE est urgent.", "translation": "Urgent."},
                    {"id": "1", "text": "Il vient de Paris.", "translation": "From Paris."},
                ],
            },
        ]
    }
    merged, stats = mod.merge_vocab_payload(payload)
    assert stats["in"] == 2
    assert stats["out"] == 1
    w = merged["words"][0]
    assert w["slug"] == "de-noun"
    assert "prep" in w["pos_all"]
    assert len(w["examples"]) == 2
    assert stats["examples_before"] == 3
    assert stats["examples_after"] == 2
