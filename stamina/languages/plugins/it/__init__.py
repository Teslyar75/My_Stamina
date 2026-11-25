"""Italian language plugin."""
from __future__ import annotations

from stamina.i18n import t

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry,
)
from stamina.languages.plugins.it.grammar_engine import ItalianGrammarEngine


class ItalianVocabSource(VocabSource):
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


class ItalianPlugin(LanguagePlugin):
    code = "it"
    name_native = "Italiano"
    name_target = t("Итальянский")
    flag_emoji = "🇮🇹"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("celi-a1", 600, "CELI A1", "CELI A1", "C-A1"),
        FreqSet("celi-a2", 1200, "CELI A2", "CELI A2", "C-A2"),
        FreqSet("celi-b1", 2500, "CELI B1", "CELI B1", "C-B1"),
        FreqSet("celi-b2", 5000, "CELI B2", "CELI B2", "C-B2"),
        FreqSet("celi-c1", 10000, "CELI C1", "CELI C1", "C-C1"),
        FreqSet("celi-c2", 20000, "CELI C2", "CELI C2", "C-C2"),
        FreqSet("rest", 50000, "Beyond 20K", t("СВЕРХ 20К"), "20K+"),
    ]
    thematic_sets = {
        "celi": ThematicSet("celi", "CELI/CILS Exams", "Vocab for CELI/CILS certification"),
        "plida": ThematicSet("plida", "PLIDA", "Vocab for PLIDA exam"),
        "business-it": ThematicSet("business-it", "Business Italian", "Italiano degli affari"),
        "medical-it": ThematicSet("medical-it", "Medical Italian", "Italiano medico"),
        "travel-it": ThematicSet("travel-it", "Travel Italian", "Italiano per viaggi"),
    }

    def load_vocab(self) -> VocabSource:
        from stamina.languages.core.json_vocab import load_vocab_file
        from stamina.languages.core.sqlite_vocab import attach_sqlite, sqlite_path
        src = ItalianVocabSource()
        words = {}
        for level in ["a1", "a2", "b1", "b2", "c1", "c2"]:
            words.update(load_vocab_file(Path(__file__).parent / f"vocab_{level}.json"))
        src._words = words
        attach_sqlite(src, sqlite_path(), "it")
        src._loaded = True
        return src

    def get_grammar_engine(self):
        return ItalianGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        path = Path(__file__).parent / "best_practices.md"
        return BestPractices.from_file(path)

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig(
            tts={
                "piper": ["it_IT-riccardo-federico-medium"],
                "azure": ["it-IT-DiegoNeural", "it-IT-ElsaNeural", "it-IT-FabrizioNeural", "it-IT-GiuliaNeural"],
            },
            asr={
                "vosk": "vosk-model-it-0.22",
                "whisper": "base",
            }
        )