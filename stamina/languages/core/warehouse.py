"""Flashcard warehouse engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import VocabSource, WordEntry


@dataclass
class FlashCard:
    slug: str
    front: str
    back: str
    audio_url: str | None = None
    morphology: dict[str, Any] = None
    examples: list[dict] = None
    tags: list[str] = None


class WarehouseEngine:
    def __init__(self, vocab: VocabSource, progress, learner_lang: str = "ru"):
        self.vocab = vocab
        self.progress = progress
        self.learner_lang = learner_lang

    def get_cards(self, slugs: list[str]) -> list[FlashCard]:
        cards = []
        for slug in slugs:
            word = self.vocab.get_word(slug)
            if word:
                cards.append(self._make_card(word))
        return cards

    def _make_card(self, word: WordEntry) -> FlashCard:
        translations = word.translations.get(self.learner_lang, [word.lemma])

        morphology_data = {}
        if word.morphology.german:
            m = word.morphology.german
            morphology_data = {
                "type": "german_noun" if word.pos == "noun" else "german_verb" if word.pos == "verb" else "german_adj",
                "cases": {
                    "sg": {"nom": m.nominative_sg, "gen": m.genitive_sg, "dat": m.dative_sg, "acc": m.accusative_sg},
                    "pl": {"nom": m.nominative_pl, "gen": m.genitive_pl, "dat": m.dative_pl, "acc": m.accusative_pl},
                },
                "article_sg": m.article_sg,
                "article_pl": m.article_pl,
                "plural_rule": m.plural_rule,
            }
            if word.pos == "verb":
                morphology_data.update({
                    "praesens": {"ich": m.praesens_ich, "du": m.praesens_du, "er": m.praesens_er,
                                "wir": m.praesens_wir, "ihr": m.praesens_ihr, "sie": m.praesens_sie},
                    "prateritum_ich": m.prateritum_ich,
                    "partizip_ii": m.partizip_ii,
                    "aux": m.aux_verb,
                    "separable": m.is_separable,
                    "prefix": m.prefix,
                })
        elif word.morphology.spanish:
            m = word.morphology.spanish
            morphology_data = {
                "type": "spanish_noun" if word.pos == "noun" else "spanish_verb" if word.pos == "verb" else "spanish_adj",
                "gender": m.gender,
                "singular": m.singular,
                "plural": m.plural,
            }
            if word.pos == "verb":
                morphology_data.update({
                    "infinitive": m.infinitive,
                    "gerundio": m.gerundio,
                    "participio": m.participio,
                    "presente": {"yo": m.pres_yo, "tu": m.pres_tu, "el": m.pres_el,
                               "nosotros": m.pres_nosotros, "vosotros": m.pres_vosotros, "ellos": m.pres_ellos},
                    "preterito": {"yo": m.pret_yo, "tu": m.pret_tu, "el": m.pret_el,
                                "nosotros": m.pret_nosotros, "vosotros": m.pret_vosotros, "ellos": m.pret_ellos},
                    "imperfecto": {"yo": m.imperf_yo, "tu": m.imperf_tu, "el": m.imperf_el,
                                   "nosotros": m.imperf_nosotros, "vosotros": m.imperf_vosotros, "ellos": m.imperf_ellos},
                    "subj_presente": {"yo": m.subj_pres_yo, "tu": m.subj_pres_tu, "el": m.subj_pres_el,
                                    "nosotros": m.subj_pres_nosotros, "vosotros": m.subj_pres_vosotros, "ellos": m.subj_pres_ellos},
                    "conjugation_group": m.conjugation_group,
                    "irregular": m.is_irregular,
                    "reflexive": m.is_reflexive,
                    "stem_changing": m.is_stem_changing,
                    "stem_change_type": m.stem_change_type,
                })
        elif word.morphology.english:
            m = word.morphology.english
            morphology_data = {
                "type": "english_verb" if word.pos == "verb" else "english_noun" if word.pos == "noun" else "english_adj",
            }
            if word.pos == "verb":
                morphology_data.update({
                    "base": m.base,
                    "past": m.past,
                    "past_participle": m.past_participle,
                    "gerund": m.gerund,
                    "third_person_sg": m.third_person_sg,
                    "irregular": m.is_irregular,
                    "phrasal": m.is_phrasal,
                    "phrasal_particles": m.phrasal_particles,
                })

        examples = []
        for ex in word.examples[:3]:
            examples.append({
                "text": ex.text,
                "translation": ex.translation,
                "cefr": ex.cefr_level,
            })

        return FlashCard(
            slug=word.slug,
            front=word.lemma,
            back="; ".join(translations),
            audio_url=word.audio_urls.get("piper") or word.audio_urls.get("azure"),
            morphology=morphology_data,
            examples=examples,
            tags=list(word.tags),
        )

    def flip_card(self, card: FlashCard) -> dict[str, Any]:
        return {
            "front": card.front,
            "back": card.back,
            "morphology": card.morphology,
            "examples": card.examples,
            "tags": card.tags,
            "audio": card.audio_url,
        }