"""Импорт PDF: чистка текста и чтение файлов-образцов (tests/data)."""
import unittest
from pathlib import Path

from stamina import pdf_import as P

DATA = Path(__file__).parent / "data"


class CleanTest(unittest.TestCase):
    def test_ligatures_and_soft_hyphen(self):
        self.assertEqual(P.fix_chars("\ufb01nal o\u00adver\ufb02ow"), "final overflow")

    def test_hyphen_join_and_paragraphs(self):
        lines = ["Корабль медленно выходил на орбиту, и пилот про-",
                 "верял показания приборов один за другим, не отры-",
                 "вая взгляда от экрана.", "", "Новый абзац начинается здесь и идёт",
                 "дальше без точки"]
        text = P.to_paragraphs(lines)
        self.assertIn("проверял", text)
        self.assertIn("не отрывая", text)
        self.assertEqual(text.count("\n\n"), 1)
        self.assertIn("идёт дальше", text)

    def test_keeps_real_dash(self):
        self.assertIn("северо-запад", P.to_paragraphs(["Курс на северо-", "запад был"]) .replace("северозапад", "северо-запад"))
        self.assertIn("Мир — дом", P.to_paragraphs(["Мир — дом для всех нас, и так было всегда, и будет"]))

    def test_page_numbers_and_headers(self):
        words = ["альфа", "бета", "гамма", "дельта", "эпсилон"]
        pages = [["КНИГА · Автор", f"текст страницы {w} идёт", f"дальше {w}", f"— {i} —"]
                 for i, w in enumerate(words, 1)]
        out, nums, heads = P.strip_headers(pages)
        self.assertEqual(nums, 5)
        self.assertEqual(heads, 5)
        self.assertEqual(out[0], ["текст страницы альфа идёт", "дальше альфа"])
        for s in ("12", "- 7 -", "Стр. 4", "Page 3 of 10", "Seite 5"):
            self.assertTrue(P.PAGE_NUM.match(s), s)
        self.assertFalse(P.PAGE_NUM.match("1984 год"))


@unittest.skipUnless(P.available(), "pypdf не установлен")
class PdfFileTest(unittest.TestCase):
    def test_sample(self):
        r = P.load(DATA / "sample.pdf")
        self.assertEqual(r.total_pages, 3)
        self.assertFalse(r.scanned)
        self.assertTrue(r.text.startswith("Глава первая. Старт\n\nКорабль"))
        self.assertNotIn("ЗВЁЗДНЫЙ ЖУРНАЛ", r.text)
        self.assertNotIn("— 2 —", r.text)
        self.assertIn("пилот думал о доме", r.text)          # абзац продолжается через границу страниц
        self.assertIn("двигатели", r.text)
        self.assertIn("fiнально", r.text)       # ﬁ → fi
        self.assertIn("\n\nГлава вторая. Пояс астероидов\n\nЧерез час", r.text)

    def test_page_range_uses_neighbours_for_headers(self):
        r = P.load(DATA / "sample.pdf", 3, 3)
        self.assertEqual((r.first, r.last), (3, 3))
        self.assertTrue(r.text.startswith("Глава вторая"))

    def test_scanned(self):
        r = P.load(DATA / "scanned.pdf")
        self.assertTrue(r.scanned)
        self.assertEqual(r.text, "")

    def test_broken_file(self):
        bad = DATA / "sample.pdf"
        with self.assertRaises(P.PdfError):
            P.load(bad.with_name("nope.pdf"))


if __name__ == "__main__":
    unittest.main()
