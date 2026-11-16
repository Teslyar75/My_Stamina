"""Язык перевода в карточках: «учу испанский по-английски».

Пилот-англичанин ставит интерфейс на English — и перевод испанских слов идёт
на английский, а не на русский. Проверяем выбор языка и запасные варианты.
"""
from __future__ import annotations

import pytest

from stamina import i18n
from stamina.languages.core.base import WordEntry
from stamina.languages.core.sqlite_vocab import gloss_lang, glosses, word_line


def word(**kw) -> WordEntry:
    base = dict(slug="la-casa", lemma="casa", pos="noun", language="es",
                translations={"ru": ["дом"], "en": ["house", "home"]})
    base.update(kw)
    return WordEntry(**base)


def test_gloss_uses_requested_language() -> None:
    assert glosses(word(), "en") == ["house", "home"]


def test_gloss_falls_back_to_russian() -> None:
    entry = word(translations={"ru": ["дом"]})
    assert glosses(entry, "en") == ["дом"]


def test_gloss_falls_back_to_english() -> None:
    entry = word(translations={"en": ["house"]})
    assert glosses(entry, "de") == ["house"]


def test_gloss_limits_to_three() -> None:
    entry = word(translations={"en": ["a", "b", "c", "d"]})
    assert glosses(entry, "en") == ["a", "b", "c"]


def test_gloss_empty_when_nothing_known() -> None:
    assert glosses(word(translations={}), "en") == []


def test_gloss_lang_follows_interface() -> None:
    old = i18n.language()
    try:
        i18n.set_language("en")
        assert gloss_lang({"gloss_lang": "ui"}) == "en"
        assert gloss_lang({}) == "en"
    finally:
        i18n.set_language(old)


def test_gloss_lang_explicit_setting_wins() -> None:
    assert gloss_lang({"gloss_lang": "ru"}) == "ru"


def test_gloss_lang_unknown_code_is_russian() -> None:
    assert gloss_lang({"gloss_lang": "ja"}) == "ru"


def test_word_line_translates_to_requested_language() -> None:
    assert word_line(word(), "en") == "casa — house, home"
    assert word_line(word(), "ru") == "casa — дом"
