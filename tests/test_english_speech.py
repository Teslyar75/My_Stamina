# -*- coding: utf-8 -*-
"""Проверка речи: похожие звуки от ASR принимаем, другой смысл — нет."""
from stamina.english.progress import Progress
from stamina.english.textutil import score_sentence, score_word, strictness_level
from stamina.english.ui import target_missed


def test_default_strictness_is_normal(tmp_path):
    p = Progress(tmp_path / "english.json")
    assert p.settings["speech_strictness"] == "normal"


def test_level_normalizes_unknown_value():
    assert strictness_level("soft") == "soft"
    assert strictness_level("strict") == "strict"
    assert strictness_level("") == "normal"
    assert strictness_level("что-то") == "normal"


def test_word_accepts_lost_vowel():
    # Vosk часто слышит tea как t — звук тот же, смысл не изменился.
    assert score_word("tea", ["t"]) >= 80
    assert score_word("tea", ["tee"]) >= 80


def test_word_rejects_other_meaning():
    assert score_word("tea", ["coffee"]) < 60
    assert score_word("tea", ["key"]) < 80


def test_strict_level_does_not_guess():
    assert score_word("tea", ["t"], strictness="strict") < 80
    assert score_word("tea", ["t"], strictness="soft") >= 80
    assert score_word("tea", ["coffee"], strictness="soft") < 60


def test_sentence_accepts_lost_vowel_and_keeps_target():
    score, marks = score_sentence("I drink a cup of tea.", "I drink a cup of t.", "tea")
    assert score >= 80
    assert not target_missed(marks, "tea")


def test_sentence_rejects_wrong_drink():
    score, marks = score_sentence("I drink a cup of tea.", "I drink a cup of coffee.", "tea")
    assert score < 60
    assert target_missed(marks, "tea")


def test_sentence_accepts_merged_phrase():
    # a new → and you: ASR слил границу слов, но звучание и смысл сохранились.
    score, marks = score_sentence("This is a new car.", "This is and you car.", "new")
    assert score >= 80
    assert not target_missed(marks, "new")


def test_sentence_rejects_changed_adjective():
    score, marks = score_sentence("This is a new car.", "This is a blue car.", "new")
    assert score < 60
    assert target_missed(marks, "new")


def test_sentence_exact_is_still_hundred():
    score, marks = score_sentence("This is a new car.", "This is a new car.", "new")
    assert score == 100
    assert not target_missed(marks, "new")


def test_strict_rejects_merged_phrase():
    score, _marks = score_sentence("This is a new car.", "This is and you car.", "new",
                                   strictness="strict")
    assert score < 80


def test_soft_accepts_merged_phrase():
    score, marks = score_sentence("This is a new car.", "This is and you car.", "new",
                                  strictness="soft")
    assert score >= 80
    assert not target_missed(marks, "new")
