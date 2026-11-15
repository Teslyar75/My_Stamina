"""French language plugin."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry, ExampleSentence, MorphologyBundle, FrenchMorphology
)


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


class FrenchGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            ("gender_number", "Род и число существительных", ["choice", "transform"]),
            ("articles", "Артикли (le/la/les, un/une/des)", ["choice", "fill"]),
            ("adjectives", "Согласование прилагательных", ["transform", "choice"]),
            ("present_regular", "Présent de l'indicatif: регулярные глаголы (-er, -ir, -re)", ["conjugation"]),
            ("present_irregular", "Présent: неправильные (être, avoir, aller, faire, venir)", ["conjugation"]),
            ("present_irregular_2", "Présent: неправильные (pouvoir, vouloir, savoir, devoir, falloir)", ["conjugation"]),
            ("negation", "Отрицание (ne...pas, ne...jamais, ne...rien)", ["choice", "transform"]),
            ("questions", "Вопросы (est-ce que, inversion, intonation)", ["reorder", "choice"]),
            ("prepositions_basic", "Prepositions à, de, en, dans, sur, sous, avec, sans", ["choice", "fill"]),
            ("partitive", "Частичный артикль (du, de la, des)", ["choice", "fill"]),
            ("possessives", "Притяжательные (mon/ton/son/notre/votre/leur)", ["choice", "transform"]),
            ("demonstratives", "Указательные (ce/cet/cette/ces)", ["choice", "transform"]),
            ("numbers_time", "Числа, время, даты", ["choice", "fill"]),
            ("near_future", "Futur proche (aller + infinitif)", ["conjugation", "transform"]),
            ("imperative", "Impératif (tu/nous/vous)", ["conjugation", "transform"]),
        ],
        "A2": [
            ("passe_compose", "Passé composé (avoir/être + participe passé)", ["conjugation", "choice"]),
            ("imparfait", "Imparfait: формы и употребление", ["conjugation", "choice"]),
            ("passe_compose_vs_imparfait", "Passé composé vs Imparfait", ["choice", "explain", "transform"]),
            ("futur_simple", "Futur simple (chanterai)", ["conjugation", "choice"]),
            ("conditionnel", "Conditionnel présent (chanterais)", ["conjugation", "choice"]),
            ("subjunctive_present", "Subjonctif présent: регулярные и основные неправильные", ["conjugation"]),
            ("subjunctive_triggers", "Триггеры субъюнктива (il faut que, je veux que, bien que)", ["choice", "explain", "transform"]),
            ("relative_pronouns", "Относительные местоимения (qui, que, où, dont)", ["choice", "transform"]),
            ("object_pronouns", "Местоимения-дополнения (le/la/les, lui/leur, y, en)", ["choice", "transform", "reorder"]),
            ("comparatives", "Сравнительная конструкция (plus/moins/aussi...que)", ["choice", "transform"]),
            ("superlatives", "Превосходная степень (le plus/le moins... de)", ["choice", "transform"]),
            ("si_clauses_present", "Si + présent → futur/présent (real conditions)", ["choice", "transform"]),
            ("recent_past", "Passé récent (venir de + infinitif)", ["transform"]),
            ("depuis_pendant", "Depuis vs pendant vs il y a", ["choice", "explain"]),
        ],
        "B1": [
            ("subjunctive_past", "Subjonctif passé (que j'aie fait)", ["conjugation", "transform"]),
            ("si_clauses_past", "Si + imparfait → conditionnel (unreal)", ["choice", "transform", "explain"]),
            ("plus_que_parfait", "Plus-que-parfait (j'avais fait)", ["conjugation", "choice"]),
            ("conditionnel_past", "Conditionnel passé (j'aurais fait)", ["conjugation", "choice"]),
            ("passive_voice", "Пассив (être + participe, on + verbe)", ["transform", "choice"]),
            ("indirect_speech", "Косвенная речь (il dit que / il a dit que)", ["transform"]),
            ("gerund", "Герундий (en faisant)", ["transform", "choice"]),
            ("past_infinitive", "Инфинитив прошедшего (avoir fait / être parti)", ["transform"]),
            ("cause_consequence", "Причина и следствие (parce que, comme, puisque, donc, par conséquent)", ["choice", "transform"]),
            ("concession", "Уступка (bien que, quoique, même si + subjonctif)", ["choice", "transform"]),
            ("purpose", "Цель (pour que, afin que + subjonctif)", ["choice", "transform"]),
            ("hypothesis", "Гипотезы (si clauses всех типов)", ["choice", "transform"]),
        ],
        "B2": [
            ("subjunctive_imperfect", "Subjonctif imparfait (que je fisse)", ["conjugation", "choice"]),
            ("subjunctive_plus_que_parfait", "Subjonctif plus-que-parfait (que j'eusse fait)", ["conjugation", "choice"]),
            ("passive_advanced", "Пассив: сложные конструкции", ["transform"]),
            ("subjunctive_sequence", "Последовательность времен в subjonctif", ["choice", "transform"]),
            ("subjunctive_vs_indicative", "Subjonctif vs Indicatif после выражений сомнения/эмоций", ["choice", "explain", "transform"]),
            ("nominalization", "Номинализация (le fait de + subjonctif, l'idée que...)", ["transform", "choice"]),
            ("cleft_sentences", "Раздельные предложения (c'est... qui/que)", ["transform"]),
            ("discourse_markers", "Маркеры дискурса (du coup, en fait, bref, enfin)", ["choice", "explain"]),
        ],
        "C1": [
            ("subjunctive_nuances", "Нюансы subjonctif (douter que vs ne pas douter que)", ["choice", "explain"]),
            ("literary_tenses", "Литературные времена (passé simple, passé antérieur)", ["choice", "explain"]),
            ("register_style", "Регистры и стиль (soutenu/familier, québécois/французский)", ["choice", "explain"]),
        ],
        "C2": [
            ("native_idioms", "Идиоматичность и коллокации", ["choice", "match"]),
            ("regional_variants", "Региональные варианты (Квебек, Бельгия, Швейцария, Африка)", ["choice", "explain"]),
        ],
    }

    REGIONAL_VARIANTS = {
        "france": "French (France)",
        "quebec": "Quebec French",
        "belgium": "Belgian French",
        "switzerland": "Swiss French",
        "africa": "African French",
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
            "prompt": f"Exercice: {topic_id}",
            "expected_answer": "answer",
            "options": ["opt1", "opt2", "opt3", "opt4"],
        }

    def validate_answer(self, exercise: dict, answer: str):
        return {"correct": answer == exercise["expected_answer"], "score": 1.0 if answer == exercise["expected_answer"] else 0.0}

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        return f"Explication pour {topic_id} en {learner_lang}"


class FrenchPlugin(LanguagePlugin):
    code = "fr"
    name_native = "Français"
    name_target = "Французский"
    flag_emoji = "🇫🇷"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("delf-a1", 600, "DELF A1", "DELF A1", "D-A1"),
        FreqSet("delf-a2", 1200, "DELF A2", "DELF A2", "D-A2"),
        FreqSet("delf-b1", 2500, "DELF B1", "DELF B1", "D-B1"),
        FreqSet("delf-b2", 5000, "DELF B2", "DELF B2", "D-B2"),
        FreqSet("delf-c1", 10000, "DELF C1", "DELF C1", "D-C1"),
        FreqSet("delf-c2", 20000, "DELF C2", "DELF C2", "D-C2"),
        FreqSet("rest", 50000, "Beyond 20K", "СВЕРХ 20К", "20K+"),
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

    def get_grammar_engine(self) -> GrammarEngine:
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