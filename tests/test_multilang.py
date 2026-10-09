"""Книги на разных языках: определение языка, подготовка текста, раскладки, статистика, UPLINK, скорочтение."""
import random
import unittest

from stamina import langdetect, layouts, translator
from stamina.text_processing import adapt_for_typing, process_text


class LangDetectTest(unittest.TestCase):
    def test_detect(self):
        cases = {
            "ru": "Корабль вышел на орбиту, и пилот проверил приборы. Это был первый полёт.",
            "uk": "Корабель вийшов на орбіту, і пілот перевірив прилади. Це був перший політ, їжа є.",
            "en": "The ship reached orbit and the pilot checked the instruments. It was the first flight.",
            "de": "Das Schiff erreichte die Umlaufbahn und der Pilot prüfte die Instrumente. Es war ein großer Flug.",
            "fr": "Le vaisseau est sur orbite et le pilote vérifie les instruments pour la mission.",
        }
        for lang, text in cases.items():
            self.assertEqual(langdetect.detect(text), lang, text)
        self.assertEqual(langdetect.detect("123 456"), "und")


class PrepTest(unittest.TestCase):
    def test_umlauts_kept_by_default(self):
        self.assertEqual(adapt_for_typing("Größe, Übermut!"), "größe übermut")

    def test_translit(self):
        self.assertEqual(process_text("Größe, Übermut, café", translit=True), "groesse uebermut cafe")
        self.assertEqual(process_text("Größe", translit=True, lower=False, punct=False), "Groesse")
        self.assertEqual(process_text("Їжак і ґанок", translit=True), "їжак і ґанок")   # кириллица не трогается

    def test_ukrainian_apostrophe(self):
        self.assertEqual(adapt_for_typing("М’ясо, сім'я — «їжа»!"), "м'ясо сім'я їжа")
        self.assertEqual(adapt_for_typing("don't"), "dont")                   # английский — как раньше

    def test_yo(self):
        self.assertEqual(process_text("Ёлка, ещё", yo=True), "елка еще")
        self.assertEqual(process_text("Ёлка, ещё"), "ёлка ещё")


class LayoutTest(unittest.TestCase):
    def test_cyrillic(self):
        for ch in "абвёяіїєґ":
            self.assertTrue(layouts.is_cyrillic(ch), ch)
        self.assertFalse(layouts.is_cyrillic("a"))
        self.assertFalse(layouts.is_cyrillic("'"))

    def test_ukrainian_keys(self):
        k = layouts.key_for_char
        self.assertEqual(k("і", "uk"), "s")
        self.assertEqual(k("ї", "uk"), "]")
        self.assertEqual(k("є", "uk"), "'")
        self.assertEqual(k("ґ", "uk"), "\\")
        self.assertEqual(k("'", "uk"), "`")
        self.assertEqual(k("ф", "uk"), "a")
        self.assertEqual(k("і", "ru"), "s")                 # и в русской подсказке не теряется
        self.assertEqual(layouts.label("s", "uk")[0], "І")
        self.assertTrue(layouts.needs_shift("Ї", "uk"))

    def test_german_keys(self):
        k = layouts.key_for_char
        self.assertEqual(k("z", "de"), "y")
        self.assertEqual(k("y", "de"), "z")
        self.assertEqual(k("ä", "de"), "'")
        self.assertEqual(k("ö", "de"), ";")
        self.assertEqual(k("ü", "de"), "[")
        self.assertEqual(k("ß", "de"), "-")
        self.assertEqual(k("Ä", "de"), "'")
        self.assertTrue(layouts.needs_shift("Ä", "de"))
        self.assertTrue(layouts.needs_shift("?", "de"))
        self.assertFalse(layouts.needs_shift("ß", "de"))
        self.assertEqual(layouts.label("y", "de")[0], "Z")
        self.assertEqual(layouts.keyboard_for("de"), "de")
        self.assertEqual(layouts.keyboard_for("uk"), "ru")
        self.assertEqual(layouts.keyboard_for("fr"), "en")
        self.assertIsNotNone(layouts.finger_for_char("ß", "de"))
        self.assertIsNotNone(layouts.finger_for_char("ї", "uk"))


class StatsTest(unittest.TestCase):
    def test_weak_keys_cyrillic_and_german(self):
        from stamina.storage import Store
        store = Store.__new__(Store)
        store.stats = {"keys": {"ї": [5, 5], "є": [8, 2], "ы": [9, 1], "ä": [4, 6], "ß": [7, 3], "a": [10, 0]}}
        ru = [c for c, _ in store.weakest_keys("ru", count=10)]
        uk = [c for c, _ in store.weakest_keys("uk", count=10)]
        en = [c for c, _ in store.weakest_keys("en", count=10)]
        self.assertEqual(ru[:3], ["ї", "є", "ы"])
        self.assertEqual(ru, uk)
        self.assertEqual(en, ["ä", "ß"])
        self.assertEqual(store.key_error_rates()["ї"], 0.5)


class UplinkTest(unittest.TestCase):
    def test_direction(self):
        d = translator.direction
        self.assertEqual(d("uk", "ru"), ("uk", "ru"))
        self.assertEqual(d("ru", "en"), ("ru", "en"))
        self.assertEqual(d("de", "uk"), ("de", "uk"))
        self.assertEqual(d("en", "en"), ("en", "ru"))      # книга на языке перевода → на русский
        self.assertEqual(d("ru", "ru"), ("ru", "en"))
        self.assertEqual(d("uk", "uk"), ("uk", "en"))
        self.assertEqual(d("und", "ru"), ("auto", "ru"))
        self.assertEqual(d("fr", None), ("fr", "ru"))       # тесты — интерфейс ru
        self.assertEqual(translator.Translator.key("Hallo", "de", "ru"), "de|ru|Hallo")


class SpeedReadTest(unittest.TestCase):
    def test_orp(self):
        from stamina.speedread.rsvp import core_span, orp_index
        self.assertEqual(core_span("«Größe»,"), (1, 6))
        self.assertEqual(core_span("„їжак“"), (1, 5))
        self.assertEqual("Größe"[orp_index("Größe")], "r")

    def test_sentences_and_chapters(self):
        from stamina.speedread.rsvp import tokenize
        w = tokenize("Er sagte: „Gut.“ Dann ging er.\n\nKapitel 2\n\nРозділ третій")
        self.assertTrue(w[2].sent_end)          # „Gut.“
        self.assertTrue(any(x.chapter and x.text == "Kapitel" for x in w))
        self.assertTrue(any(x.chapter and x.text == "Розділ" for x in w))

    def _words(self, text):
        from stamina.speedread.rsvp import tokenize
        return tokenize((text + " ") * 12)

    def test_quiz_languages(self):
        from stamina.speedread.quiz import _DECOYS, make_quiz
        texts = {
            "uk": "Пілот уважно перевіряв прилади корабля, поки зірки повільно пропливали за ілюмінатором.",
            "de": "Der Pilot überprüfte sorgfältig die Instrumente, während die Sterne langsam vorbeizogen.",
        }
        for lang, text in texts.items():
            items = make_quiz(self._words(text), 0, 120, "", rng=random.Random(1))
            self.assertTrue(items, lang)
            decoys = [i["question"] for i in items if i["kind"] == "seen" and i["answer"] == 1]
            for q in decoys:
                word = q.split("«")[1].split("»")[0]
                self.assertIn(word, _DECOYS[lang], (lang, q))

    def test_schulte_alphabets(self):
        from stamina.speedread.exercises import ALPHABETS
        self.assertIn("Ї", ALPHABETS["uk"])
        self.assertIn("Ü", ALPHABETS["de"])
        for abc in ALPHABETS.values():
            self.assertGreaterEqual(len(set(abc)), 25)


if __name__ == "__main__":
    unittest.main()
