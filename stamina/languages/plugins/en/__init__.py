"""English language plugin."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from stamina.languages.core.base import (
    LanguagePlugin, VocabSource, GrammarEngine, FreqSet, ThematicSet,
    VoicesConfig, BestPractices, WordEntry, ExampleSentence, MorphologyBundle, EnglishMorphology
)


class EnglishVocabSource(VocabSource):
    def __init__(self):
        self._words: dict[str, WordEntry] = {}
        self._loaded = False
        self._load()

    def _load(self):
        try:
            from stamina.english.vocab import Vocab as OldVocab
            old_vocab = OldVocab()
            if old_vocab.ready and old_vocab.words:
                for w in old_vocab.words:
                    entry = self._convert_word(w)
                    self._words[entry.slug] = entry
        except Exception:
            pass
        self._loaded = True

    def _convert_word(self, w: dict) -> WordEntry:
        slug = w.get("slug", w.get("word", ""))
        lemma = w.get("word", w.get("lemma", ""))
        pos = w.get("pos", "").lower()
        cefr = w.get("cefr", "A1")
        rank = w.get("rank", 0)
        band = w.get("set", "top-1000")

        translations = {}
        if w.get("ru"):
            translations["ru"] = [w["ru"]]

        morphology = MorphologyBundle(english=EnglishMorphology(
            base=lemma,
            past=w.get("past", ""),
            past_participle=w.get("past_participle", ""),
            gerund=w.get("gerund", ""),
            third_person_sg=w.get("third_person_sg", ""),
            is_irregular=w.get("irregular", False),
            is_phrasal=w.get("phrasal", False),
            phrasal_particles=w.get("phrasal_particles", []),
        ))

        examples = []
        for ex in w.get("examples", [])[:3]:
            examples.append(ExampleSentence(
                id=f"{slug}_ex{len(examples)}",
                text=ex.get("en", ""),
                translation=ex.get("ru", ""),
                source="legacy",
                cefr_level=cefr,
            ))

        return WordEntry(
            slug=slug,
            lemma=lemma,
            pos=pos,
            language="en",
            cefr_level=cefr,
            frequency_rank=rank,
            frequency_band=band,
            translations=translations,
            morphology=morphology,
            examples=examples,
            tags=set(w.get("tags", [])),
            source="legacy",
            verified=True,
        )

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


class EnglishGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            ("present_simple", "Present Simple", ["conjugation", "choice"]),
            ("present_continuous", "Present Continuous", ["conjugation", "choice"]),
            ("past_simple", "Past Simple", ["conjugation", "choice"]),
            ("future_will_going_to", "Future: will / going to", ["choice"]),
            ("present_perfect", "Present Perfect", ["conjugation", "choice"]),
            ("articles", "Articles (a/an/the)", ["choice", "fill"]),
            ("prepositions_time_place", "Prepositions of time/place", ["choice"]),
            ("modal_can_must", "Modals: can/must", ["choice"]),
            ("comparatives", "Comparatives", ["choice", "transform"]),
            ("question_formation", "Question formation", ["reorder", "choice"]),
            ("phrasal_verbs_basic", "Basic phrasal verbs", ["choice", "match"]),
        ],
        "A2": [
            ("past_continuous", "Past Continuous", ["conjugation"]),
            ("present_perfect_continuous", "Present Perfect Continuous", ["conjugation"]),
            ("past_perfect", "Past Perfect", ["conjugation"]),
            ("future_continuous", "Future Continuous", ["conjugation"]),
            ("modal_should_might", "Modals: should/might", ["choice"]),
            ("passive_voice", "Passive voice", ["transform"]),
            ("reported_speech", "Reported speech", ["transform"]),
            ("relative_clauses", "Relative clauses", ["choice", "fill"]),
            ("conditionals_0_1", "Conditionals 0 & 1", ["choice", "transform"]),
            ("phrasal_verbs_intermediate", "Phrasal verbs (intermediate)", ["choice", "match"]),
        ],
        "B1": [
            ("perfect_tenses_review", "Perfect tenses review", ["choice"]),
            ("conditionals_2_3", "Conditionals 2 & 3", ["choice", "transform"]),
            ("wish_if_only", "Wish / If only", ["transform"]),
            ("modal_perfect", "Modal perfect (should have, etc.)", ["choice"]),
            ("passive_all_tenses", "Passive all tenses", ["transform"]),
            ("reported_speech_advanced", "Advanced reported speech", ["transform"]),
            ("gerund_infinitive", "Gerund vs Infinitive", ["choice"]),
            ("causative", "Causative (have/get something done)", ["transform"]),
            ("phrasal_verbs_advanced", "Advanced phrasal verbs", ["choice", "match"]),
            ("collocations", "Collocations", ["match", "fill"]),
        ],
        "B2": [
            ("mixed_conditionals", "Mixed conditionals", ["transform"]),
            ("inversion", "Inversion", ["transform"]),
            ("subjunctive", "Subjunctive", ["choice"]),
            ("ellipsis_substitution", "Ellipsis & substitution", ["choice"]),
            ("advanced_modals", "Advanced modals", ["choice"]),
            ("cohesion_devices", "Cohesion devices", ["match"]),
            ("academic_vocab", "Academic vocabulary", ["choice", "fill"]),
        ],
        "C1": [
            ("nuanced_modals", "Nuanced modals", ["choice"]),
            ("complex_sentence_structure", "Complex sentence structure", ["transform"]),
            ("register_style", "Register & style", ["choice"]),
        ],
        "C2": [
            ("near_native_precision", "Near-native precision", ["choice"]),
            ("idiomatic_density", "Idiomatic density", ["match"]),
        ],
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
            "prompt": f"Exercise for {topic_id}",
            "expected_answer": "answer",
            "options": ["opt1", "opt2", "opt3", "opt4"],
        }

    def validate_answer(self, exercise: dict, answer: str):
        return {"correct": answer == exercise["expected_answer"], "score": 1.0 if answer == exercise["expected_answer"] else 0.0}

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        return f"Explanation for {topic_id} in {learner_lang}"


class EnglishPlugin(LanguagePlugin):
    code = "en"
    name_native = "English"
    name_target = "Английский"
    flag_emoji = "🇬🇧"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [
        FreqSet("top-1000", 1000, "Essential 1000", "ФУНДАМЕНТ", "S-1000"),
        FreqSet("top-3000", 3000, "Core 3000", "РАЗГОВОРНЫЙ", "S-3000"),
        FreqSet("top-10000", 10000, "Advanced 10K", "СВОБОДНЫЙ", "S-10K"),
        FreqSet("top-20000", 20000, "Master 20K", "КАК НОСИТЕЛЬ", "S-20K"),
        FreqSet("dev-interview", 0, "IT Interview", "СОБЕСЕДОВАНИЕ", "S-DEV"),
    ]
    thematic_sets = {
        "dev-interview": ThematicSet("dev-interview", "IT Interview", "Technical interview vocabulary"),
    }

    def load_vocab(self) -> VocabSource:
        return EnglishVocabSource()

    def get_grammar_engine(self) -> GrammarEngine:
        return EnglishGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        path = Path(__file__).parent / "best_practices.md"
        return BestPractices.from_file(path)

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig(
            tts={
                "piper": ["en_US-lessac-medium", "en_US-libritts-high"],
                "azure": ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-JennyNeural"],
            },
            asr={
                "vosk": "vosk-model-en-us-0.22",
                "whisper": "base.en",
            }
        )