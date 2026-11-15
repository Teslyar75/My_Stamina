"""Italian language plugin."""
from __future__ import annotations

from pathlib import Path

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry, ExampleSentence, MorphologyBundle, ItalianMorphology
)


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


class ItalianGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            ("gender_number", "Genere e numero dei sostantivi", ["choice", "transform"]),
            ("articles", "Articoli (il/lo/la/l'/i/gli/le, un/uno/una/un')", ["choice", "fill"]),
            ("adjectives", "Concordanza degli aggettivi", ["transform", "choice"]),
            ("present_regular", "Presente indicativo: verbi regolari (-are, -ere, -ire)", ["conjugation"]),
            ("present_irregular", "Presente: irregolari (essere, avere, fare, andare, venire, stare)", ["conjugation"]),
            ("present_irregular_2", "Presente: irregolari (potere, volere, dovere, sapere, dare)", ["conjugation"]),
            ("negation", "Negazione (non, neppure, neanche, niente, nessuno)", ["choice", "transform"]),
            ("questions", "Domande (intonazione, inversione, che cosa/chi/come)", ["reorder", "choice"]),
            ("prepositions_basic", "Preposizioni semplici (di, a, da, in, con, su, per, tra/fra)", ["choice", "fill"]),
            ("prepositions_articulate", "Preposizioni articolate (del, allo, nella, coi, sui, etc.)", ["choice", "fill"]),
            ("partitive", "Partitivo (del, dello, della, dei, degli, delle)", ["choice", "fill"]),
            ("possessives", "Possessivi (mio/tuo/suo/nostro/vostro/loro)", ["choice", "transform"]),
            ("demonstratives", "Dimostrativi (questo/quello/quel/quella/quei/quegli/quelle)", ["choice", "transform"]),
            ("numbers_time", "Numeri, ora, date", ["choice", "fill"]),
            ("future_prossimo", "Futuro prossimo (stare per + infinito)", ["conjugation", "transform"]),
            ("imperative", "Imperativo (tu/noi/voi)", ["conjugation", "transform"]),
        ],
        "A2": [
            ("passato_prossimo", "Passato prossimo (avere/essere + participio passato)", ["conjugation", "choice"]),
            ("imperfetto", "Imperfetto: forme e uso", ["conjugation", "choice"]),
            ("passato_prossimo_vs_imperfetto", "Passato prossimo vs Imperfetto", ["choice", "explain", "transform"]),
            ("futuro_semplice", "Futuro semplice (canterò)", ["conjugation", "choice"]),
            ("condizionale", "Condizionale presente (canterei)", ["conjugation", "choice"]),
            ("congiuntivo_presente", "Congiuntivo presente: regolari e principali irregolari", ["conjugation"]),
            ("congiuntivo_triggers", "Trigger del congiuntivo (bisogna che, voglio che, benché)", ["choice", "explain", "transform"]),
            ("relative_pronouns", "Pronomi relativi (che, cui, il quale)", ["choice", "transform"]),
            ("object_pronouns", "Pronomi complemento (lo/la/li/le, gli/le, ci, ne)", ["choice", "transform", "reorder"]),
            ("comparatives", "Comparativo (più/meno/quanto... di/che)", ["choice", "transform"]),
            ("superlatives", "Superlativo (il più/il meno... di)", ["choice", "transform"]),
            ("si_clauses_present", "Se + presente → futuro/presente (condizioni reali)", ["choice", "transform"]),
            ("recent_past", "Passato prossimo (venire di + infinito / appena + participio)", ["transform"]),
            ("da_per_from", "Da vs per vs da (tempo, causa, scopo)", ["choice", "explain"]),
        ],
        "B1": [
            ("congiuntivo_passato", "Congiuntivo passato (che io abbia fatto)", ["conjugation", "transform"]),
            ("si_clauses_past", "Se + imperfetto → condizionale (irreale)", ["choice", "transform", "explain"]),
            ("trapassato_prossimo", "Trapassato prossimo (avevo fatto)", ["conjugation", "choice"]),
            ("condizionale_passato", "Condizionale passato (avrei fatto)", ["conjugation", "choice"]),
            ("passive_voice", "Passivo (essere + participio, si passivante)", ["transform", "choice"]),
            ("indirect_speech", "Discorso indiretto (dice che / ha detto che)", ["transform"]),
            ("gerund", "Gerundio (facendo, avendo fatto)", ["transform", "choice"]),
            ("past_infinitive", "Infinito passato (avere fatto / essere partito)", ["transform"]),
            ("cause_consequence", "Causa e conseguenza (perché, poiché, siccome, quindi, perciò)", ["choice", "transform"]),
            ("concession", "Concessione (benché, sebbene, anche se + congiuntivo)", ["choice", "transform"]),
            ("purpose", "Scopo (perché, affinché + congiuntivo)", ["choice", "transform"]),
            ("hypothesis", "Ipotesi (periodi ipotetici di tutti i tipi)", ["choice", "transform"]),
        ],
        "B2": [
            ("congiuntivo_imperfetto", "Congiuntivo imperfetto (che io facessi)", ["conjugation", "choice"]),
            ("congiuntivo_trapassato", "Congiuntivo trapassato (che io avessi fatto)", ["conjugation", "choice"]),
            ("passive_advanced", "Passivo: costruzioni complesse", ["transform"]),
            ("congiuntivo_sequence", "Concordanze dei tempi nel congiuntivo", ["choice", "transform"]),
            ("congiuntivo_vs_indicativo", "Congiuntivo vs Indicativo dopo dubbio/emozione", ["choice", "explain", "transform"]),
            ("nominalization", "Nominalizzazione (il fatto che + congiuntivo, l'idea che...)", ["transform", "choice"]),
            ("cleft_sentences", "Frasi scisse (è... che...)", ["transform"]),
            ("discourse_markers", "Marcatori discorsivi (dunque, insomma, comunque, alla fine)", ["choice", "explain"]),
        ],
        "C1": [
            ("congiuntivo_nuances", "Sfumature del congiuntivo (dubitare che vs non dubitare che)", ["choice", "explain"]),
            ("literary_tenses", "Tempi letterari (passato remoto, trapassato remoto)", ["choice", "explain"]),
            ("register_style", "Registri e stili (formale/informale, italiano regionale)", ["choice", "explain"]),
        ],
        "C2": [
            ("native_idioms", "Idiomaticità e collocazioni", ["choice", "match"]),
            ("regional_variants", "Varianti regionali (tosco, romanesco, napoletano, siciliano, etc.)", ["choice", "explain"]),
        ],
    }

    REGIONAL_VARIANTS = {
        "standard": "Standard Italian",
        "tuscan": "Tuscan",
        "roman": "Romanesco",
        "neapolitan": "Neapolitan",
        "sicilian": "Sicilian",
        "swiss": "Swiss Italian",
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
            "prompt": f"Esercizio: {topic_id}",
            "expected_answer": "answer",
            "options": ["opt1", "opt2", "opt3", "opt4"],
        }

    def validate_answer(self, exercise: dict, answer: str):
        return {"correct": answer == exercise["expected_answer"], "score": 1.0 if answer == exercise["expected_answer"] else 0.0}

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        return f"Spiegazione per {topic_id} in {learner_lang}"


class ItalianPlugin(LanguagePlugin):
    code = "it"
    name_native = "Italiano"
    name_target = "Итальянский"
    flag_emoji = "🇮🇹"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("celi-a1", 600, "CELI A1", "CELI A1", "C-A1"),
        FreqSet("celi-a2", 1200, "CELI A2", "CELI A2", "C-A2"),
        FreqSet("celi-b1", 2500, "CELI B1", "CELI B1", "C-B1"),
        FreqSet("celi-b2", 5000, "CELI B2", "CELI B2", "C-B2"),
        FreqSet("celi-c1", 10000, "CELI C1", "CELI C1", "C-C1"),
        FreqSet("celi-c2", 20000, "CELI C2", "CELI C2", "C-C2"),
        FreqSet("rest", 50000, "Beyond 20K", "СВЕРХ 20К", "20K+"),
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

    def get_grammar_engine(self) -> GrammarEngine:
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