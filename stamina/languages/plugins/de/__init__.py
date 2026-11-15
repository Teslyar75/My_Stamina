"""German language plugin."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry, ExampleSentence, MorphologyBundle, GermanMorphology
)


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


class GermanGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            ("gender_patterns", "Роды существительных: паттерны суффиксов", ["choice", "color_code"]),
            ("nominative_accusative", "Именительный и винительный падежи", ["declension", "choice"]),
            ("present_weak", "Настоящее время: слабые глаголы", ["conjugation"]),
            ("present_strong", "Настоящее время: сильные глаголы (аблаут)", ["conjugation"]),
            ("separable_verbs", "Разделимые глаголы (trennbare Verben)", ["split", "conjugation"]),
            ("modal_verbs", "Модальные глаголы", ["conjugation", "choice"]),
            ("perfekt_haben_sein", "Perfekt: выбор вспомогательного (haben/sein)", ["choice", "conjugation"]),
            ("prepositions_acc", "Предлоги с винительным (DOGFU)", ["choice", "fill"]),
            ("prepositions_dat", "Предлоги с дательным (ABMSVZ)", ["choice", "fill"]),
            ("wechselfral_prep", "Wechselpräpositionen (в Akk/Dat)", ["choice", "transform"]),
            ("word_order_v2", "Порядок слов V2 в главных", ["reorder"]),
            ("questions", "Вопросы (да/нет и W-вопросы)", ["reorder", "choice"]),
            ("negation", "Отрицание (kein/nicht)", ["choice", "transform"]),
            ("possessive_articles", "Притяжательные артикли", ["declension"]),
            ("plural_nouns", "Множественное число существительных", ["choice", "transform"]),
            ("adjective_declination_weak", "Склонение прилагательных (слабое)", ["declension"]),
        ],
        "A2": [
            ("dative_case", "Дательный падеж: артикли, местоимения, предлоги", ["declension", "choice"]),
            ("genitive_case", "Родительный падеж: артикли, предлоги", ["declension", "choice"]),
            ("prateritum", "Präteritum (простое прошлое)", ["conjugation", "choice"]),
            ("perfekt_vs_prateritum", "Perfekt vs Präteritum (устная/письменная)", ["choice"]),
            ("reflexive_verbs", "Возвратные глаголы", ["conjugation", "choice"]),
            ("adjective_declination_strong_mixed", "Склонение прилагательных (сильное/смешанное)", ["declension"]),
            ("comparative", "Сравнительная и превосходная степень", ["transform", "choice"]),
            ("subordinate_clauses", "Придаточные предложения (dass, weil, wenn, als)", ["reorder", "choice"]),
            ("tekamolo", "Порядок слов Tekamolo", ["reorder"]),
            ("prepositions_gen", "Предлоги с родительным (WWST)", ["choice"]),
            ("relative_clauses", "Определительные придаточные (Relativsätze)", ["reorder", "choice"]),
            ("infinitive_zu", "Инфинитив с zu (um...zu, ohne...zu)", ["transform", "choice"]),
            ("passive_present", "Пассив настоящее (werden + Partizip II)", ["transform"]),
            ("n_declension", "N-деклинация (der Herr, des Herrn)", ["declension"]),
            ("partizip_ii_adjective", "Partizip II как прилагательное", ["choice", "transform"]),
            ("prepositional_verbs", "Глаголы с предлогом (warten auf, denken an)", ["choice", "fill"]),
        ],
        "B1": [
            ("konjunktiv_ii_present", "Konjunktiv II настоящего (würde + Infinitiv)", ["conjugation", "transform"]),
            ("konjunktiv_ii_past", "Konjunktiv II прошедшего (wäre gewesen)", ["conjugation", "transform"]),
            ("passive_alternatives", "Альтернативы пассиву (sich lassen, man)", ["transform", "choice"]),
            ("partizip_i_adjective", "Partizip I как прилагатие (der schlafende Hund)", ["choice", "transform"]),
            ("partizip_ii_adjective", "Partizip II как прилагатие (das gebrochene Bein)", ["choice", "transform"]),
            ("partizipialattribute", "Partizipialattribute (причастные определения)", ["identify", "transform"]),
            ("partizipialattribute_extended", "Расширенные Partizipialattribute (der auf dem Boden liegende)", ["identify", "transform"]),
            ("prepositional_objects", "Предложные дополнения (Verben mit Präposition)", ["choice", "fill"]),
            ("da_wo_compounds", "Da-/Wo-компOUNDS (darauf, woran)", ["choice", "transform"]),
            ("conditional", "Условные предложения (Wenn-Sätze)", ["transform", "choice"]),
            ("indirect_questions", "Косвенные вопросы", ["reorder", "choice"]),
            ("modal_particles", "Модальные частицы (ja, doch, mal, schon, eben, halt)", ["choice", "explain"]),
        ],
        "B2": [
            ("konjunktiv_i", "Konjunktiv I (косвенная речь)", ["transform", "choice"]),
            ("passive_prateritum", "Пассив Präteritum (wurde + Partizip II)", ["transform"]),
            ("participle_clauses", "Причастные обороты (verkürzte Nebensätze)", ["transform", "identify"]),
            ("nominalization", "Номинализация (das Lesen, das Gelesene)", ["transform"]),
            ("prepositional_adverbs", "Предложные наречия", ["choice"]),
            ("concessive", "Уступительные предложения (obwohl, selbst wenn)", ["transform"]),
            ("final", "Целевые предложения (damit, um...zu)", ["transform"]),
        ],
        "C1": [
            ("sophisticated_syntax", "Сложный синтаксис", ["transform"]),
            ("academic_register", "Научный стиль", ["choice"]),
        ],
        "C2": [
            ("near_native_nuance", "Близкое к носителю нюансирование", ["choice", "explain"]),
        ],
    }

    PFLEGE_TOPICS = {
        "partizipialattribute_pflege": {
            "source": "https://pflege.jaeckels.net/partizipialattribute",
            "exercises": ["choose_partizip", "identify_partizip", "transform_pflegebericht"],
            "vocab": ["der Bewohner", "die Pflegekraft", "stürzen", "versorgen", "mobilisieren",
                      "die Vitalzeichen", "der Sturzsensor", "neurologische Beobachtung"],
        },
        "pflegebericht_schreiben": {
            "template": "Sturzbericht, Wundversorgung, Übergabe",
            "exercises": ["fill_report", "convert_to_partizip"],
        },
    }

    def get_topics(self, cefr: str) -> list:
        topics = []
        for level, items in self.TOPICS.items():
            if self._cefr_order(level) <= self._cefr_order(cefr):
                for tid, name, types in items:
                    topics.append({"id": tid, "name": name, "cefr": level, "types": types})
        return topics

    def _cefr_order(self, level: str) -> int:
        return {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}.get(level, 0)

    def generate_exercise(self, topic_id: str, difficulty: str, seed: int):
        import random
        random.seed(seed)
        return {
            "id": f"{topic_id}_{seed}",
            "topic_id": topic_id,
            "type": "choice",
            "prompt": f"Übung: {topic_id}",
            "expected_answer": "answer",
            "options": ["opt1", "opt2", "opt3", "opt4"],
        }

    def validate_answer(self, exercise: dict, answer: str):
        return {"correct": answer == exercise["expected_answer"], "score": 1.0 if answer == exercise["expected_answer"] else 0.0}

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        return f"Erklärung für {topic_id} auf {learner_lang}"


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
        src._words = load_vocab_file(Path(__file__).parent / "vocab_a1.json")
        attach_sqlite(src, sqlite_path(), "de")
        src._loaded = True
        return src

    def get_grammar_engine(self) -> GrammarEngine:
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