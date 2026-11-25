"""Spanish language plugin."""
from __future__ import annotations

from stamina.i18n import t

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry,
)
from stamina.languages.plugins.es.grammar_engine import SpanishGrammarEngine


class SpanishVocabSource(VocabSource):
    def __init__(self):
        self._words: dict[str, WordEntry] = {}
        self._loaded = False

    def get_word(self, slug: str) -> WordEntry | None:
        return self._words.get(slug)

    def search(self, query: str, filters: dict | None = None) -> list[WordEntry]:
        query = query.lower()
        return [w for w in self._words.values() if query in w.lemma.lower()]

    def get_set(self, set_id: str) -> list[WordEntry]:
        return [w for w in self._words.values() if w.frequency_band == set_id]

    def get_all_slugs(self) -> list[str]:
        return list(self._words.keys())

    def get_slugs_by_cefr(self, level: str) -> list[str]:
        return [w.slug for w in self._words.values() if w.cefr_level == level]

    def get_slugs_by_freq_band(self, band: str) -> list[str]:
        return [w.slug for w in self._words.values() if w.frequency_band == band]


class SpanishPlugin(LanguagePlugin):
    code = "es"
    name_native = "Español"
    name_target = t("Испанский")
    flag_emoji = "🇪🇸"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("cervantes-a1", 600, "Cervantes A1", t("СЕРВАНТЕС A1"), "C-A1"),
        FreqSet("cervantes-a2", 1200, "Cervantes A2", t("СЕРВАНТЕС A2"), "C-A2"),
        FreqSet("cervantes-b1", 2500, "Cervantes B1", t("СЕРВАНТЕС B1"), "C-B1"),
        FreqSet("cervantes-b2", 5000, "Cervantes B2", t("СЕРВАНТЕС B2"), "C-B2"),
        FreqSet("cervantes-c1", 10000, "Cervantes C1", t("СЕРВАНТЕС C1"), "C-C1"),
        FreqSet("cervantes-c2", 20000, "Cervantes C2", t("СЕРВАНТЕС C2"), "C-C2"),
        FreqSet("rest", 50000, "Beyond 20K", t("СВЕРХ 20К"), "20K+"),
    ]
    thematic_sets = {
        "dele": ThematicSet("dele", "DELE Exams", "Vocab for DELE certification"),
        "siele": ThematicSet("siele", "SIELE", "Vocab for SIELE exam"),
        "business-es": ThematicSet("business-es", "Business Spanish", "Español de negocios"),
        "medical-es": ThematicSet("medical-es", "Medical Spanish", "Español médico"),
        "latam": ThematicSet("latam", "Latin American Spanish", "Español latinoamericano"),
    }

    def load_vocab(self) -> VocabSource:
        from stamina.languages.core.json_vocab import load_vocab_file
        from stamina.languages.core.sqlite_vocab import attach_sqlite, sqlite_path
        src = SpanishVocabSource()
        words = {}
        for level in ["a1", "a2", "b1", "b2", "c1", "c2"]:
            words.update(load_vocab_file(Path(__file__).parent / f"vocab_{level}.json"))
        src._words = words
        attach_sqlite(src, sqlite_path(), "es")
        src._loaded = True
        return src

    def get_grammar_engine(self):
        return SpanishGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        path = Path(__file__).parent / "best_practices.md"
        return BestPractices.from_file(path)

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig(
            tts={
                "piper": ["es_ES-sharvard-medium", "es_ES-marta-medium", "es_MX-ald-medium"],
                "azure": ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-DaliaNeural", "es-MX-JorgeNeural"],
            },
            asr={
                "vosk": "vosk-model-es-0.42",
                "whisper": "base",
            }
        )