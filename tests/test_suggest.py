"""Подсказки пульта набора: слово-окончание и продолжение фразы (логика без Tk)."""

from __future__ import annotations

import unittest

from stamina.suggest import (Dictionary, Suggestion, Suggester, dictionary_from,
                             match_case, phrases_of, words_of)


class WordsAndPhrasesTest(unittest.TestCase):
    def test_words_of_keeps_order_and_case(self):
        self.assertEqual(words_of("Найди сращивания слов в «книге»!"),
                         ["Найди", "сращивания", "слов", "в", "книге"])

    def test_words_of_keeps_inner_punctuation(self):
        self.assertEqual(words_of("файл voice_input.py и год-два"),
                         ["файл", "voice_input.py", "и", "год-два"])

    def test_phrases_do_not_cross_sentences(self):
        got = phrases_of("найди сращивания. слов в книге")
        self.assertIn("найди сращивания", got)
        self.assertIn("слов в книге", got)
        self.assertNotIn("сращивания слов", got)

    def test_match_case(self):
        self.assertEqual(match_case("Прив", "привет"), "Привет")
        self.assertEqual(match_case("прив", "привет"), "привет")


class DictionaryTest(unittest.TestCase):
    def test_short_words_are_ignored(self):
        d = Dictionary()
        d.add_text("я и он мы привет")
        self.assertIn("привет", d.words)
        self.assertNotIn("я", d.words)

    def test_counts_grow(self):
        d = Dictionary()
        d.add_text("проверь тесты")
        d.add_text("проверь тесты")
        self.assertEqual(d.words["проверь"], 2)
        self.assertEqual(d.phrases["проверь тесты"], 2)

    def test_trim_keeps_frequent(self):
        d = Dictionary(limit=20)
        for i in range(200):
            d.add_text(f"слово{i:03d}")
        for _ in range(50):
            d.add_text("проверь тесты")
        d.trim()
        self.assertLessEqual(len(d.words), 50)
        self.assertIn("проверь", d.words)

    def test_dictionary_from_texts(self):
        d = dictionary_from(["найди сращивания", "проверь тесты"])
        self.assertIn("сращивания", d.words)
        self.assertIn("проверь тесты", d.phrases)


class SuggesterTest(unittest.TestCase):
    def setUp(self):
        self.d = dictionary_from([
            "проверь тесты и покажи отчёт",
            "проверь тесты ещё раз",
            "привет корабль",
            "приветствую пилот",
        ])
        self.s = Suggester(self.d)

    def test_completes_word(self):
        best = self.s.best("прив")
        self.assertIsNotNone(best)
        self.assertEqual(best.tail, "ет")
        self.assertEqual(best.kind, "word")

    def test_frequent_word_comes_first(self):
        best = self.s.best("пров")
        self.assertEqual(best.tail, "ерь")

    def test_prefix_case_is_kept(self):
        best = self.s.best("Прив")
        self.assertEqual(best.tail, "ет")

    def test_short_prefix_gives_nothing(self):
        self.assertEqual(self.s.suggestions("п"), [])

    def test_finished_word_gives_nothing(self):
        self.assertEqual(self.s.suggestions("привет "), [])

    def test_empty_text_gives_nothing(self):
        self.assertEqual(self.s.suggestions(""), [])

    def test_phrase_hint_continues_context(self):
        items = self.s.suggestions("проверь тес")
        self.assertTrue(any(i.is_phrase and i.tail == "ты" for i in items),
                        [tuple(i) for i in items])

    def test_phrase_hint_adds_whole_continuation(self):
        items = self.s.suggestions("проверь")
        self.assertTrue(any(i.tail == " тесты" for i in items),
                        [tuple(i) for i in items])

    def test_phrases_come_before_words(self):
        items = self.s.suggestions("проверь")
        self.assertTrue(items[0].is_phrase)

    def test_limit_is_respected(self):
        s = Suggester(self.d, limit=2)
        self.assertLessEqual(len(s.suggestions("проверь")), 2)

    def test_cursor_position_matters(self):
        text = "проверь тесты"
        # курсор в середине слова — доканчиваем слово
        self.assertEqual(self.s.suggestions(text, cursor=6)[0].kind, "word")
        # курсор после целого слова — предлагаем продолжение фразы
        items = self.s.suggestions(text, cursor=7)
        self.assertEqual(items[0].kind, "phrase")
        self.assertEqual(items[0].tail, " тесты")

    def test_no_dictionary_no_hints(self):
        self.assertEqual(Suggester(Dictionary()).suggestions("проверь"), [])

    def test_duplicates_are_dropped(self):
        items = self.s.suggestions("проверь")
        tails = [i.tail for i in items]
        self.assertEqual(len(tails), len(set(tails)))


class SuggestionShapeTest(unittest.TestCase):
    def test_suggestion_fields(self):
        s = Suggestion("word", "ет", "привет")
        self.assertFalse(s.is_phrase)
        self.assertTrue(Suggestion("phrase", "ь тесты", "проверь тесты").is_phrase)


if __name__ == "__main__":
    unittest.main()
