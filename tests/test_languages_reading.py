"""Отработка чтения и отсеки языкового прогресса."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from stamina.languages.core import LanguageProgress, MissionGenerator
from stamina.languages.core.base import ExampleSentence, FreqSet, WordEntry
from stamina.languages.core import reading


def _word(slug: str, lemma: str, rank: int, sentences: list[str]) -> WordEntry:
    return WordEntry(
        slug=slug,
        lemma=lemma,
        pos="noun",
        language="de",
        frequency_rank=rank,
        frequency_band="de-a1",
        translations={"ru": [f"перевод {lemma}"]},
        examples=[
            ExampleSentence(id=f"{slug}-{i}", text=text, translation=f"перевод {i}",
                            source="tatoeba")
            for i, text in enumerate(sentences)
        ],
    )


class FakeVocab:
    def __init__(self, words: list[WordEntry]) -> None:
        self._words = {w.slug: w for w in words}

    def get_word(self, slug: str) -> WordEntry | None:
        return self._words.get(slug)


@pytest.fixture()
def setup():
    tmp = tempfile.TemporaryDirectory()
    progress = LanguageProgress(Path(tmp.name), "de")
    vocab = FakeVocab([
        _word("haus", "Haus", 1, ["Das Haus ist groß.", "Ich gehe nach Hause."]),
        _word("wasser", "Wasser", 2, ["Das Wasser ist kalt.", ""]),
        _word("ohne-frasen", "ohne", 3, []),
    ])
    plugin = SimpleNamespace(freq_sets=[
        FreqSet(id="de-a1", size=50, name_en="A1", name_target="A1", short_code="A1"),
    ])
    yield progress, vocab, plugin
    tmp.cleanup()


class TestReadingCore:
    def test_sentences_skip_empty(self):
        vocab = FakeVocab([_word("wasser", "Wasser", 1, ["Das Wasser ist kalt.", "  "])])
        word = vocab.get_word("wasser")
        assert len(reading.sentences(word)) == 1
        assert reading.sentences(None) == []

    def test_card_slugs_only_words_with_phrases(self, setup):
        progress, vocab, plugin = setup
        progress.set_known("haus", True)
        progress.set_known("ohne-frasen", True)
        slugs = reading.card_slugs(progress, vocab, plugin)
        assert "haus" in slugs
        assert "ohne-frasen" not in slugs

    def test_queue_moves_started_cards_first(self, setup):
        progress, _vocab, _plugin = setup
        reading.record(progress, "haus", 90, 0, 2)
        queue = reading.queue(progress, ["wasser", "haus"])
        assert queue[0] == "haus"
        assert set(queue) == {"haus", "wasser"}

    def test_low_score_does_not_fill_slot(self, setup):
        progress, _vocab, _plugin = setup
        res, key = reading.record(progress, "haus", 60, 0, 2)
        assert res == "low"
        assert key is not None
        assert reading.counts(progress, "haus", 2)["filled"] == 0

    def test_pass_fills_slot_and_attempt(self, setup):
        progress, _vocab, _plugin = setup
        res, _key = reading.record(progress, "haus", 90, 0, 2)
        assert res == "ok"
        assert reading.counts(progress, "haus", 2)["filled"] == 1
        attempts = progress.recent_attempts(5)
        assert attempts and attempts[0]["mode"] == "reading" and attempts[0]["correct"]

    def test_self_rated_is_recorded_without_score(self, setup):
        progress, _vocab, _plugin = setup
        res, _key = reading.record(progress, "haus", 0, 0, 2, self_rated=True)
        assert res == "self"
        assert reading.counts(progress, "haus", 2)["filled"] == 1


class TestLanguageLists:
    def test_toggle_in_list_persists(self, setup):
        progress, _vocab, _plugin = setup
        item = progress.create_list("Повторить")
        assert progress.toggle_in_list(item["id"], "haus") is True
        assert "haus" in progress.list_by_id(item["id"])["slugs"]
        assert progress.lists_of("haus") == [item["id"]]

        again = LanguageProgress(progress.pilot_dir, "de")
        assert "haus" in again.list_by_id(item["id"])["slugs"]

        assert progress.toggle_in_list(item["id"], "haus") is False
        assert progress.lists_of("haus") == []


class TestMissionCards:
    def test_cards_session_respects_limit(self, setup):
        progress, vocab, _plugin = setup
        gen = MissionGenerator(vocab, progress, progress.settings)
        missions = gen.cards_session(["haus", "wasser"], limit=1)
        assert len(missions) == 1
        assert missions[0].slug in {"haus", "wasser"}
        assert missions[0].options
