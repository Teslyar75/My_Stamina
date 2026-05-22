"""Тесты адаптации текста для тренажёра Stamina."""

import unittest

from stamina.text_processing import (
    adapt_for_typing,
    is_valid_practice_text,
    normalize_spaces,
    remove_punctuation,
    to_lowercase,
)


class NormalizeSpacesTests(unittest.TestCase):
    def test_trims_and_collapses(self):
        self.assertEqual(normalize_spaces("  hello   world  "), "hello world")

    def test_handles_tabs_and_newlines(self):
        self.assertEqual(normalize_spaces("a\tb\n\nc"), "a b c")

    def test_empty(self):
        self.assertEqual(normalize_spaces(""), "")
        self.assertEqual(normalize_spaces("   "), "")


class RemovePunctuationTests(unittest.TestCase):
    def test_english(self):
        self.assertEqual(remove_punctuation("Hi, world!"), "Hi world")

    def test_russian_punctuation(self):
        self.assertEqual(
            remove_punctuation("«Привет», — сказал он…"),
            "Привет  сказал он",
        )

    def test_keeps_digits_and_letters(self):
        self.assertEqual(remove_punctuation("ABC 123 абв"), "ABC 123 абв")

    def test_keeps_spaces(self):
        # Пробелы сохраняются; «двойные» пробелы возникают там, где знак
        # стоял между пробелами, — их потом схлопнет normalize_spaces.
        self.assertEqual(remove_punctuation("a ,b"), "a b")
        self.assertEqual(remove_punctuation("a , b"), "a  b")


class LowercaseTests(unittest.TestCase):
    def test_english(self):
        self.assertEqual(to_lowercase("AbC"), "abc")

    def test_russian(self):
        self.assertEqual(to_lowercase("ПрИвЕт ЁжИк"), "привет ёжик")


class AdaptForTypingTests(unittest.TestCase):
    def test_full_pipeline(self):
        self.assertEqual(adapt_for_typing("  Hello,   World!  "), "hello world")

    def test_russian_pipeline(self):
        self.assertEqual(
            adapt_for_typing("«Привет,   мир!»"),
            "привет мир",
        )

    def test_mixed_quotes_dashes(self):
        self.assertEqual(
            adapt_for_typing('Слово — "другое".'),
            "слово другое",
        )

    def test_empty(self):
        self.assertEqual(adapt_for_typing(""), "")
        self.assertEqual(adapt_for_typing("   ---  ,,, "), "")


class IsValidPracticeTextTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(is_valid_practice_text("Hello!"))

    def test_invalid(self):
        self.assertFalse(is_valid_practice_text(""))
        self.assertFalse(is_valid_practice_text("    "))
        self.assertFalse(is_valid_practice_text("!!!---"))


if __name__ == "__main__":
    unittest.main()
