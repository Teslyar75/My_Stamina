"""Spanish language plugin."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry,
)


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


class SpanishGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            ("ser_estar", "Ser vs Estar", ["choice", "transform", "explain"]),
            ("gender_number", "Род и число существительных", ["choice", "transform"]),
            ("articles", "Артикли (el/la/los/las, un/una)", ["choice", "fill"]),
            ("adjectives", "Согласование прилагательных", ["transform", "choice"]),
            ("present_regular", "Presente de indicativo: регулярные", ["conjugation"]),
            ("present_irregular", "Presente: неправильные (ser, estar, tener, ir, hacer)", ["conjugation"]),
            ("present_stem_changing", "Stem-changing verbs (e→ie, o→ue, e→i)", ["conjugation", "choice"]),
            ("gustar", "Gustar и подобные (me/te/le/nos/os/les gusta)", ["choice", "reorder", "transform"]),
            ("present_progressive", "Estar + gerundio (continuo)", ["conjugation", "transform"]),
            ("reflexive", "Reflexive verbs (llamarse, lavarse)", ["conjugation", "choice"]),
            ("prepositions_basic", "Preposiciones básicas (a, de, en, con, por, para)", ["choice", "fill"]),
            ("por_para", "Por vs Para (базовые случаи)", ["choice", "explain"]),
            ("question_formation", "Вопросы (инверсия, ¿qué? ¿quién?)", ["reorder", "choice"]),
            ("negation", "Отрицание (no, nunca, nada, nadie)", ["choice", "transform"]),
            ("demonstratives", "Указательные (este/ese/aquel)", ["choice", "transform"]),
            ("possessives", "Притяжательные (mi/tu/su/nuestro)", ["choice", "transform"]),
            ("numbers_time", "Числа, время, даты", ["choice", "fill"]),
        ],
        "A2": [
            ("preterito_indefinido", "Pretérito indefinido: регулярные", ["conjugation"]),
            ("preterito_irregular", "Pretérito indefinido: неправильные (ir/ser, tener, hacer, estar, poder, poner, saber, venir, decir, traer, ver, dar)", ["conjugation", "choice"]),
            ("imperfecto", "Pretérito imperfecto: формы и употребление", ["conjugation", "choice"]),
            ("preterito_vs_imperfecto", "Indefinido vs Imperfecto (aspect)", ["choice", "explain", "transform"]),
            ("future_simple", "Futuro simple (cantaré)", ["conjugation", "choice"]),
            ("conditional", "Condicional simple (cantaría)", ["conjugation", "choice"]),
            ("present_perfect", "Pretérito perfecto compuesto (he cantado)", ["conjugation", "choice"]),
            ("subjunctive_present_regular", "Presente de subjuntivo: регулярные", ["conjugation"]),
            ("subjunctive_present_irregular", "Presente de subjuntivo: неправильные", ["conjugation"]),
            ("weirdo_triggers", "WEIRDO триггеры (Wishes, Emotions, Impersonal, Recommendations, Doubt, Ojalá)", ["choice", "explain", "transform"]),
            ("si_clauses_present", "Si + presente → presente/futuro (real conditions)", ["choice", "transform"]),
            ("commands_affirmative", "Imperativo afirmativo (tú/usted/nosotros/vosotros)", ["conjugation", "transform"]),
            ("commands_negative", "Imperativo negativo (no cantes)", ["conjugation", "transform"]),
            ("direct_object", "Прямое дополнение (lo/la/los/las)", ["choice", "transform"]),
            ("indirect_object", "Косвенное дополнение (le/les)", ["choice", "transform"]),
            ("double_object", "Два дополнения (se lo doy)", ["choice", "transform"]),
            ("comparatives", "Сравнительная конструкция (más/menos/tan...como)", ["choice", "transform"]),
            ("superlatives", "Превосходная степень (el más... de)", ["choice", "transform"]),
        ],
        "B1": [
            ("subjunctive_noun_clauses", "Subjuntivo в существительных придаточных (que)", ["choice", "transform"]),
            ("subjunctive_adj_clauses", "Subjuntivo в определительных придаточных (antecedente indefinido)", ["choice", "transform"]),
            ("subjunctive_adv_clauses", "Subjuntivo в обстоятельственных (para que, sin que, antes de que, hasta que)", ["choice", "transform"]),
            ("si_clauses_past", "Si + imperfecto de subjuntivo → condicional (unreal)", ["choice", "transform", "explain"]),
            ("pluperfect_subjunctive", "Pluscuamperfecto de subjuntivo (hubiera cantado)", ["conjugation", "choice"]),
            ("si_clauses_pluperfect", "Si + pluscuamperfecto de subjuntivo → condicional perfecto", ["choice", "transform"]),
            ("passive_voice", "Пассив (ser + participio, se pasiva)", ["transform", "choice"]),
            ("passive_reflexive", "Рефлексивный пассив (se vende, se habla)", ["choice", "transform"]),
            ("reported_speech", "Косвенная речь (dice que... / dijo que...)", ["transform"]),
            ("relative_clauses", "Определительные придаточные (que, quien, cuyo, donde)", ["choice", "transform"]),
            ("por_para_advanced", "Por vs Para (продвинутые случаи: причина/цель, движение/направление)", ["choice", "explain", "transform"]),
            ("ser_estar_advanced", "Ser vs Estar (смысловые нюансы: ser aburrido vs estar aburrido)", ["choice", "explain"]),
            ("se_aspectual", "Аспекуальное se (se comió, se bebió)", ["choice", "explain"]),
            ("se_impersonal", "Безличное se (se vive bien aquí)", ["choice", "explain"]),
            ("future_perfect", "Futuro perfecto (habré cantado)", ["conjugation", "choice"]),
            ("conditional_perfect", "Condicional perfecto (habría cantado)", ["conjugation", "choice"]),
            ("subjunctive_imperfect", "Imperfecto de subjuntivo (cantara/cantase)", ["conjugation", "choice"]),
        ],
        "B2": [
            ("subjunctive_sequence", "Последовательность времен в subjuntivo (tense concordance)", ["choice", "transform"]),
            ("subjunctive_vs_indicative", "Subjuntivo vs Indicativo в придаточных (creo que / no creo que)", ["choice", "explain", "transform"]),
            ("subjunctive_adverbial", "Обстоятельственные с subjuntivo (aunque, cuando, donde, como)", ["choice", "transform"]),
            ("passive_alternatives", "Альтернативы пассиву (se + verbo, ellos + verbo)", ["transform"]),
            ("nominalization", "Номинализация (el hecho de que + subjuntivo)", ["transform", "choice"]),
            ("cleft_sentences", "Раздельные предложения (fue Juan quien...)", ["transform"]),
            ("discourse_markers", "Маркеры дискурса (pues, entonces, en fin, o sea)", ["choice", "explain"]),
        ],
        "C1": [
            ("subjunctive_nuances", "Нюансы subjuntivo (dudo que vs no dudo que)", ["choice", "explain"]),
            ("literary_tenses", "Литературные времена (pretérito anterior, futuro de subjuntivo)", ["choice", "explain"]),
            ("register_style", "Регистры и стиль (formal/informal, latino/peninsular)", ["choice", "explain"]),
        ],
        "C2": [
            ("native_idioms", "Идиоматичность и коллокации", ["choice", "match"]),
            ("regional_variants", "Региональные варианты (Rioplatense, Caribe, Norte)", ["choice", "explain"]),
        ],
    }

    REGIONAL_VARIANTS = {
        "peninsular": "Peninsular Spanish (Spain)",
        "mexican": "Mexican Spanish",
        "rioplatense": "Rioplatense (Argentina/Uruguay)",
        "caribbean": "Caribbean",
        "andean": "Andean",
        "central_american": "Central American",
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
            "prompt": f"Ejercicio: {topic_id}",
            "expected_answer": "answer",
            "options": ["opt1", "opt2", "opt3", "opt4"],
        }

    def validate_answer(self, exercise: dict, answer: str):
        return {"correct": answer == exercise["expected_answer"], "score": 1.0 if answer == exercise["expected_answer"] else 0.0}

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        return f"Explicación para {topic_id} en {learner_lang}"


class SpanishPlugin(LanguagePlugin):
    code = "es"
    name_native = "Español"
    name_target = "Испанский"
    flag_emoji = "🇪🇸"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("cervantes-a1", 600, "Cervantes A1", "СЕРВАНТЕС A1", "C-A1"),
        FreqSet("cervantes-a2", 1200, "Cervantes A2", "СЕРВАНТЕС A2", "C-A2"),
        FreqSet("cervantes-b1", 2500, "Cervantes B1", "СЕРВАНТЕС B1", "C-B1"),
        FreqSet("cervantes-b2", 5000, "Cervantes B2", "СЕРВАНТЕС B2", "C-B2"),
        FreqSet("cervantes-c1", 10000, "Cervantes C1", "СЕРВАНТЕС C1", "C-C1"),
        FreqSet("cervantes-c2", 20000, "Cervantes C2", "СЕРВАНТЕС C2", "C-C2"),
        FreqSet("rest", 50000, "Beyond 20K", "СВЕРХ 20К", "20K+"),
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

    def get_grammar_engine(self) -> GrammarEngine:
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