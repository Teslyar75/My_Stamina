"""Tests for stamina.languages.core modules."""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from stamina.languages.core import (
    LanguageRegistry, SM2Scheduler, SM2Card, LanguageProgress,
    get_registry, TerraformerRewards, calculate_terraformer_energy
)
from stamina.languages.core.base import (
    WordEntry, ExampleSentence, MorphologyBundle, EnglishMorphology,
    GermanMorphology, SpanishMorphology, FreqSet, ThematicSet,
    VoicesConfig, BestPractices
)
from stamina.languages.migrate import migrate_english_progress


class TestSM2Scheduler:
    def test_initial_card(self):
        card = SM2Scheduler.initial_card()
        assert card.interval == 0
        assert card.repetitions == 0
        assert card.ease_factor == 2.5
        assert card.due_date == date.today()

    def test_next_interval_again(self):
        card = SM2Scheduler.initial_card()
        new_card = SM2Scheduler.next_interval(card, 0)
        assert new_card.interval == 1
        assert new_card.repetitions == 0
        assert new_card.ease_factor < 2.5

    def test_next_interval_hard(self):
        card = SM2Scheduler.initial_card()
        new_card = SM2Scheduler.next_interval(card, 1)
        assert new_card.interval == 1
        assert new_card.repetitions == 0  # reset on hard/again
        assert new_card.ease_factor < 2.5

    def test_next_interval_good(self):
        card = SM2Scheduler.initial_card()
        new_card = SM2Scheduler.next_interval(card, 3)  # quality 3 = Good
        assert new_card.interval == 1  # first review: interval = 1
        assert new_card.repetitions == 1
        # ef decreases slightly for quality 3

    def test_next_interval_easy(self):
        card = SM2Scheduler.initial_card()
        # Need two good reviews to get interval >= 4
        new_card = SM2Scheduler.next_interval(card, 3)
        new_card = SM2Scheduler.next_interval(new_card, 4)  # second review, quality 4 = Easy
        assert new_card.interval >= 4  # second review: interval = 6
        assert new_card.repetitions == 2

    def test_is_due(self):
        card = SM2Scheduler.initial_card()
        assert SM2Scheduler.is_due(card) is True
        card.due_date = date.today() + timedelta(days=10)
        assert SM2Scheduler.is_due(card) is False
        card.due_date = date.today() - timedelta(days=1)
        assert SM2Scheduler.is_due(card) is True


class TestLanguageProgress:
    def test_new_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            assert progress.lang_code == "en"
            assert progress.data["xp"]["total"] == 0
            assert progress.current_streak() == 0

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            progress.add_xp(100, "test")
            progress.save()

            progress2 = LanguageProgress(pilot_dir, "en")
            assert progress2.data["xp"]["total"] == 100

    def test_add_xp(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            progress.add_xp(500, "test")
            assert progress.data["xp"]["total"] == 500

    def test_record_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            progress.record_attempt("test-word", True, "choice")
            assert len(progress.data["attempts"]) == 1
            assert progress.data["xp"]["total"] == 1

    def test_get_due_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            slugs = [f"word-{i}" for i in range(10)]
            for s in slugs:
                card = SM2Scheduler.initial_card()
                card.due_date = date.today()
                progress.update_card(s, card)
            due = progress.get_due_cards(slugs, limit=5)
            assert len(due) <= 5

    def test_known_or_learned(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            slugs = ["a", "b", "c"]
            progress.set_known("a", True)
            card = SM2Scheduler.initial_card()
            card.interval = 21
            progress.update_card("b", card)
            known = progress.known_or_learned(slugs)
            assert known == 2

    def test_current_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            progress.data["xp"]["by_day"][date.today().isoformat()] = 50
            progress.data["xp"]["by_day"][(date.today() - timedelta(days=1)).isoformat()] = 50
            assert progress.current_streak() == 2

    def test_update_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "en")
            progress.settings["new_per_day"] = 30
            progress.save()
            
            progress2 = LanguageProgress(pilot_dir, "en")
            assert progress2.settings["new_per_day"] == 30


class TestLanguageRegistry:
    def test_singleton(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_discover_plugins(self):
        reg = get_registry()
        reg.discover()
        plugins = reg.all()
        codes = {p.code for p in plugins}
        assert "en" in codes
        assert "de" in codes
        assert "es" in codes

    def test_get_plugin(self):
        reg = get_registry()
        reg.discover()
        en = reg.get("en")
        assert en is not None
        assert en.code == "en"

        de = reg.get("de")
        assert de is not None
        assert de.code == "de"

        es = reg.get("es")
        assert es is not None
        assert es.code == "es"

    def test_plugin_structure(self):
        reg = get_registry()
        reg.discover()
        for plugin in reg.all():
            assert plugin.code in ("en", "de", "es", "fr", "it")
            assert plugin.name_native
            assert plugin.name_target
            assert plugin.flag_emoji
            assert plugin.cefr_levels
            assert plugin.freq_sets
            assert hasattr(plugin, "load_vocab")
            assert hasattr(plugin, "get_grammar_engine")
            assert hasattr(plugin, "get_best_practices")
            assert hasattr(plugin, "get_voices")


class TestTerraformerRewards:
    def test_calculate_energy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            # Create mock language progress files
            for lang in ["en", "de"]:
                prog_file = pilot_dir / f"lang_{lang}.json"
                prog_file.write_text(json.dumps({
                    "xp": {"total": 1000, "by_day": {date.today().isoformat(): 50}},
                    "version": 2,
                }), encoding="utf-8")

            energy = calculate_terraformer_energy(pilot_dir)
            assert energy > 0

    def test_grant_blueprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            rewards = TerraformerRewards(pilot_dir)
            bp = rewards.grant("level_up_B1", "de")
            assert bp is not None
            assert bp["lang"] == "de"
            assert "blueprint" in bp

    def test_grant_skin(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            rewards = TerraformerRewards(pilot_dir)
            skin = rewards.grant("level_up_C2", "en")
            assert skin is not None
            assert skin["lang"] == "en"
            assert "skin" in skin

    def test_unlock_cefr(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            rewards = TerraformerRewards(pilot_dir)
            unlock = rewards.grant("level_up_B2", "es")
            assert unlock is not None
            assert unlock["lang"] == "es"
            assert "unlock" in unlock

    def test_spend_energy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            rewards = TerraformerRewards(pilot_dir)
            rewards.grant("level_up_C2", "en")  # grants 2000 energy
            assert rewards.spend_energy(1000) is True
            assert rewards.spend_energy(1500) is False
            assert rewards.get_energy() == 1000


class TestMigration:
    def test_migrate_english_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            old_file = pilot_dir / "english.json"
            old_file.write_text(json.dumps({
                "xp": {"total": 1500, "history": []},
                "streak": {"current": 10, "longest": 15, "last_date": "2026-11-15"},
                "cards": {"test": {"interval": 5, "repetitions": 3, "ef": 2.5, "due": 0}},
                "settings": {"new_per_day": 20},
            }), encoding="utf-8")

            result = migrate_english_progress(pilot_dir)
            assert result is True

            new_file = pilot_dir / "lang_en.json"
            assert new_file.exists()

            data = json.loads(new_file.read_text(encoding="utf-8"))
            assert data["_lang"] == "en"
            assert data["xp"]["total"] == 1500

            backup = pilot_dir / "english.json.migrated"
            assert backup.exists()

    def test_migrate_no_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            result = migrate_english_progress(pilot_dir)
            assert result is False

    def test_migrate_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            new_file = pilot_dir / "lang_en.json"
            new_file.write_text("{}", encoding="utf-8")

            old_file = pilot_dir / "english.json"
            old_file.write_text(json.dumps({"xp": {"total": 100}}), encoding="utf-8")

            result = migrate_english_progress(pilot_dir)
            assert result is False


class TestDataClasses:
    def test_word_entry(self):
        word = WordEntry(
            slug="test-word",
            lemma="test",
            pos="noun",
            language="en",
            cefr_level="A1",
            frequency_rank=100,
            frequency_band="top-1000",
            translations={"ru": ["тест"]},
            morphology=MorphologyBundle(english=EnglishMorphology(base="test")),
            examples=[ExampleSentence(id="1", text="Test sentence", translation="Тест", source="test", cefr_level="A1")],
            tags={"test"},
        )
        assert word.slug == "test-word"
        assert word.translations["ru"][0] == "тест"

    def test_german_morphology(self):
        morph = GermanMorphology(
            nominative_sg="der Mann",
            genitive_sg="des Mannes",
            dative_sg="dem Mann",
            accusative_sg="den Mann",
            nominative_pl="die Männer",
            genitive_pl="der Männer",
            dative_pl="den Männern",
            accusative_pl="die Männer",
            article_sg="der",
            article_pl="die",
            plural_rule="umlaut+n",
            praesens_ich="habe",
            partizip_ii="gehabt",
            aux_verb="haben",
        )
        assert morph.nominative_sg == "der Mann"
        assert morph.plural_rule == "umlaut+n"

    def test_spanish_morphology(self):
        morph = SpanishMorphology(
            gender="m",
            singular="libro",
            plural="libros",
            infinitive="hablar",
            pres_yo="hablo",
            subj_pres_yo="hable",
        )
        assert morph.gender == "m"
        assert morph.infinitive == "hablar"

    def test_freq_set(self):
        fs = FreqSet("top-1000", 1000, "Core 1000", "ФУНДАМЕНТ", "S-1000")
        assert fs.id == "top-1000"
        assert fs.size == 1000

    def test_thematic_set(self):
        ts = ThematicSet("business", "Business English", "Vocab for business")
        assert ts.id == "business"

    def test_voices_config(self):
        vc = VoicesConfig(
            tts={"piper": ["voice1"], "azure": ["voice2"]},
            asr={"vosk": "model1", "whisper": "base"},
        )
        assert "piper" in vc.tts
        assert "vosk" in vc.asr

    def test_best_practices_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "practices.md"
            path.write_text("# Test\n\nContent here", encoding="utf-8")
            bp = BestPractices.from_file(path)
            assert "Test" in bp.content
            assert "Content here" in bp.content