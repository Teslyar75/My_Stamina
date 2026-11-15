"""Abstract base classes for language plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class MorphologyBundle:
    """Language-specific morphology data."""
    gender: str | None = None
    number: str | None = None
    german: "GermanMorphology | None" = None
    spanish: "SpanishMorphology | None" = None
    french: "FrenchMorphology | None" = None
    italian: "ItalianMorphology | None" = None
    english: "EnglishMorphology | None" = None


@dataclass
class GermanMorphology:
    nominative_sg: str = ""
    genitive_sg: str = ""
    dative_sg: str = ""
    accusative_sg: str = ""
    nominative_pl: str = ""
    genitive_pl: str = ""
    dative_pl: str = ""
    accusative_pl: str = ""
    article_sg: str = ""
    article_pl: str = ""
    plural_rule: str = ""
    infinitive: str = ""
    praesens_ich: str = ""
    praesens_du: str = ""
    praesens_er: str = ""
    praesens_wir: str = ""
    praesens_ihr: str = ""
    praesens_sie: str = ""
    prateritum_ich: str = ""
    partizip_ii: str = ""
    aux_verb: str = "haben"
    is_separable: bool = False
    prefix: str | None = None
    is_strong: bool = False
    is_modal: bool = False
    is_reflexive: bool = False
    comparative: str = ""
    superlative: str = ""


@dataclass
class SpanishMorphology:
    gender: str = ""
    singular: str = ""
    plural: str = ""
    infinitive: str = ""
    gerundio: str = ""
    participio: str = ""
    pres_yo: str = ""
    pres_tu: str = ""
    pres_el: str = ""
    pres_nosotros: str = ""
    pres_vosotros: str = ""
    pres_ellos: str = ""
    pret_yo: str = ""
    pret_tu: str = ""
    pret_el: str = ""
    pret_nosotros: str = ""
    pret_vosotros: str = ""
    pret_ellos: str = ""
    imperf_yo: str = ""
    imperf_tu: str = ""
    imperf_el: str = ""
    imperf_nosotros: str = ""
    imperf_vosotros: str = ""
    imperf_ellos: str = ""
    subj_pres_yo: str = ""
    subj_pres_tu: str = ""
    subj_pres_el: str = ""
    subj_pres_nosotros: str = ""
    subj_pres_vosotros: str = ""
    subj_pres_ellos: str = ""
    subj_imperf_yo: str = ""
    subj_imperf_tu: str = ""
    subj_imperf_el: str = ""
    subj_imperf_nosotros: str = ""
    subj_imperf_vosotros: str = ""
    subj_imperf_ellos: str = ""
    imper_tu: str = ""
    imper_el: str = ""
    imper_nosotros: str = ""
    imper_vosotros: str = ""
    imper_ellos: str = ""
    conjugation_group: int = 0
    is_irregular: bool = False
    is_reflexive: bool = False
    is_stem_changing: bool = False
    stem_change_type: str | None = None


@dataclass
class FrenchMorphology:
    gender: str = ""
    singular: str = ""
    plural: str = ""
    infinitive: str = ""
    participe_passe: str = ""
    gerondif: str = ""
    pres_je: str = ""
    pres_tu: str = ""
    pres_il: str = ""
    pres_nous: str = ""
    pres_vous: str = ""
    pres_ils: str = ""
    imparf_je: str = ""
    imparf_tu: str = ""
    imparf_il: str = ""
    imparf_nous: str = ""
    imparf_vous: str = ""
    imparf_ils: str = ""
    passe_je: str = ""
    passe_tu: str = ""
    passe_il: str = ""
    passe_nous: str = ""
    passe_vous: str = ""
    passe_ils: str = ""
    futur_je: str = ""
    futur_tu: str = ""
    futur_il: str = ""
    futur_nous: str = ""
    futur_vous: str = ""
    futur_ils: str = ""
    cond_je: str = ""
    cond_tu: str = ""
    cond_il: str = ""
    cond_nous: str = ""
    cond_vous: str = ""
    cond_ils: str = ""
    subj_pres_je: str = ""
    subj_pres_tu: str = ""
    subj_pres_il: str = ""
    subj_pres_nous: str = ""
    subj_pres_vous: str = ""
    subj_pres_ils: str = ""
    subj_imparf_je: str = ""
    subj_imparf_tu: str = ""
    subj_imparf_il: str = ""
    subj_imparf_nous: str = ""
    subj_imparf_vous: str = ""
    subj_imparf_ils: str = ""
    imper_tu: str = ""
    imper_nous: str = ""
    imper_vous: str = ""
    conjugation_group: int = 0
    is_irregular: bool = False
    is_reflexive: bool = False
    auxiliary: str = "avoir"
    past_participle_agreement: bool = False


@dataclass
class ItalianMorphology:
    gender: str = ""
    singular: str = ""
    plural: str = ""
    infinitive: str = ""
    gerundio: str = ""
    participio: str = ""
    pres_io: str = ""
    pres_tu: str = ""
    pres_lui: str = ""
    pres_noi: str = ""
    pres_voi: str = ""
    pres_loro: str = ""
    imperf_io: str = ""
    imperf_tu: str = ""
    imperf_lui: str = ""
    imperf_noi: str = ""
    imperf_voi: str = ""
    imperf_loro: str = ""
    passato_io: str = ""
    passato_tu: str = ""
    passato_lui: str = ""
    passato_noi: str = ""
    passato_voi: str = ""
    passato_loro: str = ""
    trapass_io: str = ""
    trapass_tu: str = ""
    trapass_lui: str = ""
    trapass_noi: str = ""
    trapass_voi: str = ""
    trapass_loro: str = ""
    futuro_io: str = ""
    futuro_tu: str = ""
    futuro_lui: str = ""
    futuro_noi: str = ""
    futuro_voi: str = ""
    futuro_loro: str = ""
    cond_io: str = ""
    cond_tu: str = ""
    cond_lui: str = ""
    cond_noi: str = ""
    cond_voi: str = ""
    cond_loro: str = ""
    congiuntivo_pres_io: str = ""
    congiuntivo_pres_tu: str = ""
    congiuntivo_pres_lui: str = ""
    congiuntivo_pres_noi: str = ""
    congiuntivo_pres_voi: str = ""
    congiuntivo_pres_loro: str = ""
    congiuntivo_imperf_io: str = ""
    congiuntivo_imperf_tu: str = ""
    congiuntivo_imperf_lui: str = ""
    congiuntivo_imperf_noi: str = ""
    congiuntivo_imperf_voi: str = ""
    congiuntivo_imperf_loro: str = ""
    imper_tu: str = ""
    imper_lui: str = ""
    imper_noi: str = ""
    imper_voi: str = ""
    imper_loro: str = ""
    conjugation_group: int = 0
    is_irregular: bool = False
    is_reflexive: bool = False
    auxiliary: str = "avere"
    past_participle_agreement: bool = False


@dataclass
class EnglishMorphology:
    base: str = ""
    past: str = ""
    past_participle: str = ""
    gerund: str = ""
    third_person_sg: str = ""
    is_irregular: bool = False
    is_phrasal: bool = False
    phrasal_particles: list[str] = field(default_factory=list)
    singular: str = ""
    plural: str = ""
    is_countable: bool = True
    comparative: str = ""
    superlative: str = ""


@dataclass
class WordEntry:
    slug: str
    lemma: str
    pos: str
    language: str
    cefr_level: str = "A1"
    frequency_rank: int = 0
    frequency_band: str = ""
    translations: dict[str, list[str]] = field(default_factory=dict)
    morphology: MorphologyBundle = field(default_factory=MorphologyBundle)
    examples: list["ExampleSentence"] = field(default_factory=list)
    audio_urls: dict[str, str] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    source: str = ""
    verified: bool = False


@dataclass
class ExampleSentence:
    id: str
    text: str
    translation: str
    source: str
    cefr_level: str = "A1"
    audio_url: str | None = None
    tags: set[str] = field(default_factory=set)
    word_slugs: list[str] = field(default_factory=list)


@dataclass
class FreqSet:
    id: str
    size: int
    name_en: str
    name_target: str
    short_code: str


@dataclass
class ThematicSet:
    id: str
    name: str
    description: str
    word_slugs: list[str] = field(default_factory=list)


@dataclass
class GrammarTopic:
    id: str
    name: str
    cefr_level: str
    description: str
    exercise_types: list[str] = field(default_factory=list)


@dataclass
class Exercise:
    id: str
    topic_id: str
    type: str
    prompt: str
    expected_answer: str | list[str]
    options: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    correct: bool
    score: float
    feedback: str = ""
    correct_answer: str | None = None


@dataclass
class VoicesConfig:
    tts: dict[str, list[str]] = field(default_factory=dict)
    asr: dict[str, str] = field(default_factory=dict)


@dataclass
class BestPractices:
    content: str = ""
    sections: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "BestPractices":
        try:
            text = path.read_text(encoding="utf-8")
            return cls(content=text)
        except Exception:
            return cls()


class VocabSource(ABC):
    @abstractmethod
    def get_word(self, slug: str) -> WordEntry | None:
        pass

    @abstractmethod
    def search(self, query: str, filters: dict | None = None) -> list[WordEntry]:
        pass

    @abstractmethod
    def get_set(self, set_id: str) -> list[WordEntry]:
        pass

    @abstractmethod
    def get_all_slugs(self) -> list[str]:
        pass

    @abstractmethod
    def get_slugs_by_cefr(self, level: str) -> list[str]:
        pass

    @abstractmethod
    def get_slugs_by_freq_band(self, band: str) -> list[str]:
        pass


class GrammarEngine(ABC):
    @abstractmethod
    def get_topics(self, cefr: str) -> list[GrammarTopic]:
        pass

    @abstractmethod
    def generate_exercise(self, topic_id: str, difficulty: str, seed: int) -> Exercise:
        pass

    @abstractmethod
    def validate_answer(self, exercise: Exercise, answer: str) -> ValidationResult:
        pass

    @abstractmethod
    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        pass


class LanguagePlugin(ABC):
    code: str
    name_native: str
    name_target: str
    flag_emoji: str
    cefr_levels: list[str]
    freq_sets: list[FreqSet]
    thematic_sets: dict[str, ThematicSet]

    @abstractmethod
    def load_vocab(self) -> VocabSource:
        pass

    @abstractmethod
    def get_grammar_engine(self) -> GrammarEngine:
        pass

    @abstractmethod
    def get_best_practices(self) -> BestPractices:
        pass

    @abstractmethod
    def get_voices(self) -> VoicesConfig:
        pass