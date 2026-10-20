"""Тесты адаптации текста для тренажёра Stamina."""

import unittest

from stamina.text_processing import (
    adapt_for_typing,
    book_words,
    find_glued_words,
    is_valid_practice_text,
    normalize_spaces,
    process_text,
    remove_punctuation,
    repair_glued_words,
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

    def test_sign_between_words_becomes_space(self):
        # Главное правило: знак между словами не сращивает их.
        self.assertEqual(remove_punctuation("слово—слово"), "слово слово")
        self.assertEqual(remove_punctuation("как/то"), "как то")
        self.assertEqual(remove_punctuation("текст…дальше"), "текст дальше")
        self.assertEqual(remove_punctuation("Привет,мир"), "Привет мир")

    def test_hyphen_and_apostrophe_inside_word_stay(self):
        self.assertEqual(remove_punctuation("что-то и don't"), "что-то и don't")
        self.assertEqual(remove_punctuation("м'ясо, п'ять"), "м'ясо п'ять")
        self.assertEqual(remove_punctuation("по-моему"), "по-моему")

    def test_numbers_keep_separators(self):
        self.assertEqual(remove_punctuation("1.5 и 1,5"), "1.5 и 1,5")
        self.assertEqual(remove_punctuation("1990-1995"), "1990-1995")
        self.assertEqual(remove_punctuation("1/2 стакана"), "1/2 стакана")

    def test_no_gluing_in_adapted_text(self):
        # Ни одно слово не должно слипнуться: пробелов столько же, сколько было разделителей.
        self.assertEqual(adapt_for_typing("Он сказал: «не могу — некогда»."), "он сказал не могу некогда")


class GluedWordsTests(unittest.TestCase):
    """Сращивания, пришедшие из самого текста: «ивот» → «и вот»."""

    def test_confident_finds(self):
        found = {g.token: (g.split, g.confident)
                 for g in find_glued_words("Мыпришли и вот некто ивот")}
        self.assertEqual(found.get("Мыпришли"), ("мы пришли", True))
        self.assertEqual(found.get("ивот"), ("и вот", True))
        self.assertEqual(found.get("вот"), None)

    def test_short_targets_after_one_letter(self):
        # Однобуквенное слово расщепляем только перед «вот / все / всё».
        self.assertEqual([g.token for g in find_glued_words("ивот ивсё")], ["ивот", "ивсё"])
        self.assertEqual(find_glued_words("узнал услышал увидел увижу"), [])

    def test_real_words_are_not_touched(self):
        for word in ("дорога", "человек", "погода", "подруга", "забыл", "поможет",
                     "придумал", "задел", "послов", "вконец"):
            self.assertEqual(find_glued_words(word), [], word)

    def test_word_is_not_touched_without_reason(self):
        self.assertEqual(find_glued_words("город книга время"), [])

    def test_known_words_are_skipped(self):
        self.assertEqual(find_glued_words("ивот", known_words=["ивот"]), [])

    def test_confident_only(self):
        found = find_glued_words("дорогадомой", confident_only=True)
        self.assertEqual(found, [])
        lazy = find_glued_words("дорогадомой", confident_only=False)
        self.assertEqual(len(lazy), 1)
        self.assertFalse(lazy[0].confident)

    def test_repair_only_confident(self):
        self.assertEqual(repair_glued_words("мыпришли ивот домой"), "мы пришли и вот домой")
        self.assertEqual(repair_glued_words("дорогадомой"), "дорогадомой")
        self.assertEqual(repair_glued_words("придумал всё сам"), "придумал всё сам")

    def test_repair_keeps_offsets_and_text(self):
        # Обычный текст с пробелами не должен портиться.
        src = "ивот так и живём"
        self.assertEqual(repair_glued_words(src), "и вот так и живём")

    def test_english(self):
        self.assertEqual(repair_glued_words("thebook is here"), "the book is here")
        for word in ("nothing", "into", "another", "tonight", "sometime"):
            self.assertEqual(find_glued_words(word), [], word)

    def test_dictionary_split_of_two_content_words(self):
        # «nineteenthcentury» старыми правилами не находилось: разрез на 10-м знаке,
        # а правила смотрели только после короткого служебного слова.
        book = {"nineteenth": 5, "century": 8, "the": 40, "and": 30}
        found = find_glued_words("в nineteenthcentury веке", known_words=book)
        self.assertEqual([(g.token, g.split, g.confident) for g in found],
                         [("nineteenthcentury", "nineteenth century", True)])

    def test_rare_word_is_not_trusted_in_a_book(self):
        # Половины встретились по разу в большой книге — статистики нет, не трогаем.
        book = {f"word{i}": 3 for i in range(50)}
        book.update({"nineteenth": 1, "century": 1})
        self.assertEqual(find_glued_words("nineteenthcentury", known_words=book), [])

    def test_word_seen_twice_is_real(self):
        book = {"nineteenth": 5, "century": 8, "waterfall": 2, "water": 9, "fall": 7}
        self.assertEqual(find_glued_words("waterfall", known_words=book), [])

    def test_merge_rarer_than_its_halves(self):
        book = {f"word{i}": 3 for i in range(50)}
        book.update({"nineteenth": 4, "century": 6, "nineteenthcentury": 1})
        found = find_glued_words("текст nineteenthcentury здесь", known_words=book)
        self.assertEqual([g.split for g in found], ["nineteenth century"])

    def test_book_words_counts(self):
        words = book_words("nineteenth century and nineteenth century")
        self.assertEqual(words.get("nineteenth"), 2)
        self.assertEqual(words.get("century"), 2)


class ProcessTextGlueTests(unittest.TestCase):
    def test_glue_off_by_default(self):
        self.assertEqual(process_text("ивот"), "ивот")

    def test_glue_on_splits(self):
        self.assertEqual(process_text("ивот", glue=True), "и вот")
        self.assertEqual(process_text("Мыпришли домой!", glue=True), "мы пришли домой")

    def test_three_basic_options_match_adapt(self):
        src = "«Привет,   мир!»"
        self.assertEqual(process_text(src), adapt_for_typing(src))
        self.assertEqual(process_text(src, glue=True), adapt_for_typing(src))

    def test_glue_on_splits_two_content_words_from_the_book(self):
        # Ровно случай пилота: книга сама даёт частоты, склейка — редкая.
        src = "nineteenth century and nineteenth century and nineteenthcentury"
        self.assertEqual(process_text(src, glue=True),
                         "nineteenth century and nineteenth century and nineteenth century")


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
