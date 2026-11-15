"""Проверка произношения слова и фразы теми же функциями, что у английского сканера."""
from pathlib import Path

from stamina.english.asr import ASR
from stamina.english.textutil import score_sentence, score_word
from stamina.languages.speech import MODELS_DIR, culture_for, expected_dir


def test_word_and_sentence_use_english_scoring():
    assert score_word("Haus", ["haus"]) == 100
    score, marks = score_sentence("das haus ist alt", "das haus ist alt", "Haus")
    assert score >= 85
    assert any(ok for _tok, ok in marks)


def test_language_models_stay_out_of_the_english_folder():
    de = expected_dir("de")
    es = expected_dir("es")
    assert de == MODELS_DIR / "lang" / "vosk-model-small-de-0.15"
    assert es == MODELS_DIR / "lang" / "vosk-model-small-es-0.42"
    assert de.parent.name == "lang"


def test_english_asr_default_is_unchanged():
    engine = ASR()
    assert engine._model_dir is None
    missing = ASR(model_dir=Path("models") / "lang" / "no-such-model")
    assert missing._dir() is None
    assert missing.available() is False


def test_voice_culture():
    assert culture_for("de") == "de-*"
    assert culture_for("es") == "es-*"
    assert culture_for("en") == ""
