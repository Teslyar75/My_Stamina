"""French language plugin."""
from __future__ import annotations

from stamina.i18n import t

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry,
)
from stamina.languages.plugins.fr.grammar_engine import FrenchGrammarEngine


class FrenchVocabSource(VocabSource):
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


class FrenchPlugin(LanguagePlugin):
    code = "fr"
    name_native = "Français"
    name_target = t("Французский")
    flag_emoji = "🇫🇷"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("delf-a1", 600, "DELF A1", "DELF A1", "D-A1"),
        FreqSet("delf-a2", 1200, "DELF A2", "DELF A2", "D-A2"),
        FreqSet("delf-b1", 2500, "DELF B1", "DELF B1", "D-B1"),
        FreqSet("delf-b2", 5000, "DELF B2", "DELF B2", "D-B2"),
        FreqSet("delf-c1", 10000, "DELF C1", "DELF C1", "D-C1"),
        FreqSet("delf-c2", 20000, "DELF C2", "DELF C2", "D-C2"),
        FreqSet("rest", 50000, "Beyond 20K", t("СВЕРХ 20К"), "20K+"),
    ]
    thematic_sets = {
        "delf": ThematicSet("delf", "DELF/DALF Exams", "Vocab for DELF/DALF certification"),
        "tcf": ThematicSet("tcf", "TCF", "Vocab for TCF exam"),
        "business-fr": ThematicSet("business-fr", "Business French", "Français des affaires"),
        "medical-fr": ThematicSet("medical-fr", "Medical French", "Français médical"),
        "quebec-fr": ThematicSet("quebec-fr", "Quebec French", "Français québécois"),
    }

    def load_vocab(self) -> VocabSource:
        from stamina.languages.core.json_vocab import load_vocab_file
        from stamina.languages.core.sqlite_vocab import attach_sqlite, sqlite_path
        src = FrenchVocabSource()
        words = {}
        for level in ["a1", "a2", "b1", "b2", "c1", "c2"]:
            words.update(load_vocab_file(Path(__file__).parent / f"vocab_{level}.json"))
        src._words = words
        attach_sqlite(src, sqlite_path(), "fr")
        src._loaded = True
        return src

    def get_grammar_engine(self):
        return FrenchGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        path = Path(__file__).parent / "best_practices.md"
        return BestPractices.from_file(path)

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig(
            tts={
                "piper": ["fr_FR-siwis-medium", "fr_FR-upmc-medium", "fr_CA-denis-medium"],
                "azure": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural", "fr-CA-SylvieNeural", "fr-CA-JeanNeural"],
            },
            asr={
                "vosk": "vosk-model-fr-0.22",
                "whisper": "base",
            }
        )