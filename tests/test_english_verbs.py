# -*- coding: utf-8 -*-
"""Данные вкладки ГЛАГОЛЫ: 12 времён и корректные формы."""
from stamina.english import verbs
from stamina.english.textutil import tokens, word_forms


def test_every_verb_has_twelve_unique_tenses():
    assert len(verbs.entries()) >= 10
    keys = [t[0] for t in verbs.tenses()]
    assert len(keys) == 12
    for verb in verbs.entries():
        sents = verbs.sentences(verb)
        assert len(sents) == 12
        assert [s["key"] for s in sents] == keys
        assert len({s["en"] for s in sents}) == 12
        assert all(s["en"] and s["ru"] for s in sents)


def test_sentences_contain_the_verb_form():
    for verb in verbs.entries():
        forms = word_forms(verb["word"])
        for sent in verbs.sentences(verb):
            assert any(t in forms for t in tokens(sent["en"])), (verb["word"], sent["en"])


def test_irregular_forms_are_used():
    write = verbs.find("write")
    sents = {s["key"]: s["en"] for s in verbs.sentences(write)}
    assert "written" in sents["present_perfect"]
    assert "wrote" in sents["past_simple"]
    assert "writing" in sents["present_continuous"]

    speak = verbs.find("speak")
    sents = {s["key"]: s["en"] for s in verbs.sentences(speak)}
    assert "spoke" in sents["past_simple"]
    assert "spoken" in sents["present_perfect"]

    build = verbs.find("build")
    sents = {s["key"]: s["en"] for s in verbs.sentences(build)}
    assert "built" in sents["future_perfect"]


def test_russian_translations_have_no_placeholders():
    for verb in verbs.entries():
        for sent in verbs.sentences(verb):
            assert "None" not in sent["ru"]
            assert "{" not in sent["ru"]
            assert "}" not in sent["ru"]
