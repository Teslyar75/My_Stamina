# -*- coding: utf-8 -*-
"""conjugation.py: 12 времён × 5 лиц × утверждение/отрицание/вопрос и особые случаи."""
import pytest

from stamina.english import conjugation as cj


def test_full_grid_is_generated():
    assert len(cj.TENSE_KEYS) == 12 and len(cj.PERSON_KEYS) == 5 and len(cj.MODES) == 3
    for mode in cj.MODES:
        tab = cj.table("go", mode, "went", "gone")
        assert set(tab) == set(cj.TENSE_KEYS)
        for tense, row in tab.items():
            assert set(row) == set(cj.PERSON_KEYS)
            for person, text in row.items():
                assert text and "None" not in text, (tense, person, mode)
                if mode == "question":
                    assert text.endswith("?") and text[0].isupper()
                if mode == "negative":
                    assert " not " in f" {text} "


@pytest.mark.parametrize("tense,person,mode,expected", [
    ("present_simple", "he", "affirmative", "he goes"),
    ("present_simple", "he", "negative", "he does not go"),
    ("present_simple", "he", "question", "Does he go?"),
    ("present_simple", "they", "question", "Do they go?"),
    ("past_simple", "he", "affirmative", "he went"),
    ("past_simple", "he", "question", "Did he go?"),
    ("past_simple", "we", "negative", "we did not go"),
    ("present_perfect", "he", "question", "Has he gone?"),
    ("present_perfect", "I", "affirmative", "I have gone"),
    ("past_perfect", "they", "negative", "they had not gone"),
    ("present_continuous", "I", "affirmative", "I am going"),
    ("present_continuous", "you", "question", "Are you going?"),
    ("past_continuous", "he", "affirmative", "he was going"),
    ("future_simple", "I", "affirmative", "I will go"),
    ("future_simple", "he", "negative", "he will not go"),
    ("future_simple", "we", "question", "Will we go?"),
    ("future_continuous", "they", "affirmative", "they will be going"),
    ("future_perfect", "he", "question", "Will he have gone?"),
    ("future_perfect_continuous", "I", "affirmative", "I will have been going"),
    ("present_perfect_continuous", "he", "affirmative", "he has been going"),
    ("past_perfect_continuous", "we", "question", "Had we been going?"),
])
def test_go(tense, person, mode, expected):
    assert cj.conjugate("go", tense, person, mode, "went", "gone") == expected


def test_be():
    assert cj.conjugate("be", "present_simple", "I", "question") == "Am I?"
    assert cj.conjugate("be", "present_simple", "he", "affirmative") == "he is"
    assert cj.conjugate("be", "present_simple", "they", "negative") == "they are not"
    assert cj.conjugate("be", "past_simple", "we", "negative") == "we were not"
    assert cj.conjugate("be", "past_simple", "he", "question") == "Was he?"
    assert cj.conjugate("be", "present_perfect", "he", "affirmative") == "he has been"


def test_have_and_do_as_main_verbs():
    assert cj.conjugate("have", "present_simple", "he", "affirmative", "had", "had") == "he has"
    assert cj.conjugate("have", "present_simple", "he", "negative", "had", "had") == "he does not have"
    assert cj.conjugate("have", "past_simple", "you", "question", "had", "had") == "Did you have?"
    assert cj.conjugate("do", "present_simple", "he", "affirmative", "did", "done") == "he does"
    assert cj.conjugate("do", "present_simple", "he", "question", "did", "done") == "Does he do?"
    assert cj.conjugate("do", "present_perfect", "they", "affirmative", "did", "done") == "they have done"


@pytest.mark.parametrize("base,ing", [
    ("run", "running"), ("lie", "lying"), ("die", "dying"), ("visit", "visiting"),
    ("open", "opening"), ("begin", "beginning"), ("make", "making"), ("see", "seeing"),
    ("panic", "panicking"), ("fix", "fixing"), ("quit", "quitting"), ("study", "studying"),
])
def test_ing(base, ing):
    assert cj.ing_form(base) == ing


@pytest.mark.parametrize("base,past", [
    ("study", "studied"), ("prefer", "preferred"), ("play", "played"), ("stop", "stopped"),
    ("like", "liked"), ("visit", "visited"), ("panic", "panicked"),
])
def test_regular_past(base, past):
    assert cj.regular_past(base) == past


def test_third_person():
    assert [cj.third_person(v) for v in ("go", "watch", "study", "play", "fix", "have")] == \
        ["goes", "watches", "studies", "plays", "fixes", "has"]


def test_irregular_tokens_highlight():
    assert cj.irregular_tokens("go", "went", "gone") == {"went", "gone"}
    assert cj.irregular_tokens("work") == set()
    assert cj.is_irregular("go", "went", "gone")
    assert not cj.is_irregular("work", "worked", "worked")
