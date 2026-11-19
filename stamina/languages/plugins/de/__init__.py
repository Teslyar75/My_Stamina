"""German language plugin."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry,
)
# Тематика по уходу (Pflege) для отсека: живёт отдельно от уроков A1–C2.
PFLEGE_TOPICS = {
    "partizipialattribute_pflege": {
        "source": "https://pflege.jaeckels.net/partizipialattribute",
        "exercises": ["choose_partizip", "identify_partizip", "transform_pflegebericht"],
        "vocab": ["der Bewohner", "die Pflegekraft", "stürzen", "versorgen", "mobilisieren",
                  "die Vitalzeichen", "der Sturzsensor", "neurologische наблюдение"],
    },
    "pflegebericht_schreiben": {
        "template": "Sturzbericht, Wundversorgung, Übergabe",
        "exercises": ["fill_report", "convert_to_partizip"],
    },
}


class GermanVocabSource(VocabSource):
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


class GermanPlugin(LanguagePlugin):
    code = "de"
    name_native = "Deutsch"
    name_target = "Немецкий"
    flag_emoji = "🇩🇪"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("goethe-a1", 600, "Goethe A1", "ГЕТЕ A1", "G-A1"),
        FreqSet("goethe-a2", 1200, "Goethe A2", "ГЕТЕ A2", "G-A2"),
        FreqSet("goethe-b1", 2500, "Goethe B1", "ГЕТЕ B1", "G-B1"),
        FreqSet("goethe-b2", 5000, "Goethe B2", "ГЕТЕ B2", "G-B2"),
        FreqSet("goethe-c1", 10000, "Goethe C1", "ГЕТЕ C1", "G-C1"),
        FreqSet("goethe-c2", 20000, "Goethe C2", "ГЕТЕ C2", "G-C2"),
        FreqSet("rest", 50000, "Beyond 20K", "СВЕРХ 20К", "20K+"),
    ]
    thematic_sets = {
        "dtz": ThematicSet("dtz", "DTZ (Deutsch-Test für Zuwanderer)", "Vocab for DTZ exam"),
        "testdaf": ThematicSet("testdaf", "TestDaF", "Vocab for TestDaF exam"),
        "business-de": ThematicSet("business-de", "Business German", "Wirtschaftsdeutsch"),
        "medical-de": ThematicSet("medical-de", "Medical German", "Fachsprache Medizin"),
        "pflege-de": ThematicSet("pflege-de", "Pflege-Deutsch B1-B2", "German for nursing care"),
    }

    def load_vocab(self) -> VocabSource:
        from stamina.languages.core.json_vocab import load_vocab_file
        from stamina.languages.core.sqlite_vocab import attach_sqlite, sqlite_path
        src = GermanVocabSource()
        words = {}
        for level in ["a1", "a2", "b1", "b2", "c1", "c2"]:
            words.update(load_vocab_file(Path(__file__).parent / f"vocab_{level}.json"))
        src._words = words
        attach_sqlite(src, sqlite_path(), "de")
        src._loaded = True
        return src

    def get_grammar_engine(self) -> GrammarEngine:
        from stamina.languages.plugins.de.grammar_engine import GermanGrammarEngine
        return GermanGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        path = Path(__file__).parent / "best_practices.md"
        return BestPractices.from_file(path)

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig(
            tts={
                "piper": ["thorsten", "eva_k", "karlsson", "kerstin", "mls"],
                "azure": ["de-DE-Conrad", "de-DE-Katja", "de-DE-Florian", "de-DE-Seraphina"],
            },
            asr={
                "vosk": "vosk-model-de-0.21",
                "vosk_small": "vosk-model-de-tuda-0.6-900k",
                "whisper": "base",
            }
        )