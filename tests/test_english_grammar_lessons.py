"""Уроки грамматики: индекс, загрузка по одному, проверка ответов и прогресс."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stamina.english.grammar import lessons as gl
from stamina.english.progress import Progress


class LessonsIndexTest(unittest.TestCase):
    def test_index_has_all_units(self) -> None:
        units = gl.units()
        self.assertEqual(len(units), gl.TOTAL_UNITS)
        self.assertEqual([int(u["n"]) for u in units], list(range(1, gl.TOTAL_UNITS + 1)))

    def test_levels_split(self) -> None:
        for lv in gl.LEVELS:
            self.assertGreater(len(gl.by_level(lv)), 0, lv)
        self.assertEqual(len(gl.by_level("a1")) + len(gl.by_level("a2")) + len(gl.by_level("b1")),
                         gl.TOTAL_UNITS)

    def test_modules_cover_units(self) -> None:
        ids = {m["id"] for m in gl.modules()}
        for u in gl.units():
            self.assertIn(u["module"], ids, u["n"])
            self.assertTrue(str(u["title"]).strip(), u["n"])

    def test_neighbours(self) -> None:
        self.assertEqual(gl.neighbours(1)[0], None)
        self.assertEqual(gl.neighbours(1)[1], 2)
        self.assertEqual(gl.neighbours(gl.TOTAL_UNITS)[1], None)
        self.assertEqual(gl.neighbours(50), (49, 51))


class LessonsContentTest(unittest.TestCase):
    def test_every_unit_has_lesson(self) -> None:
        missing = [int(u["n"]) for u in gl.units() if not gl.lesson_exists(int(u["n"]))]
        self.assertEqual(missing, [], "не написаны уроки: {}".format(missing))

    def test_lesson_matches_index(self) -> None:
        for u in gl.units():
            n = int(u["n"])
            data = gl.load_lesson(n)
            self.assertEqual(data["n"], n)
            self.assertEqual(data["title"], u["title"], n)
            self.assertEqual(data["level"], u["level"], n)
            self.assertTrue(data["theory"], n)
            self.assertTrue(data["exercises"], n)

    def test_lesson_is_cached(self) -> None:
        gl.load_lesson.cache_clear()
        a = gl.load_lesson(1)
        b = gl.load_lesson(1)
        self.assertIs(a, b)

    def test_exercises_are_answerable(self) -> None:
        for u in gl.units():
            n = int(u["n"])
            for ex in gl.load_lesson(n)["exercises"]:
                answers = gl.lesson_answers(ex)
                self.assertTrue(answers, f"u{n:03d}: упражнение без ответа")
                for a in answers:
                    self.assertTrue(gl.answer_ok(a, answers), f"u{n:03d}: ответ {a!r} не проверяется")


class AnswerCheckTest(unittest.TestCase):
    def test_normalize_ignores_case_spaces_apostrophes(self) -> None:
        self.assertEqual(gl.normalize("  He  Doesn't   Work. "), "he doesn't work")
        self.assertEqual(gl.normalize("don\u2019t"), "don't")

    def test_answer_ok(self) -> None:
        variants = ["He works here", "he's working here"]
        self.assertTrue(gl.answer_ok(" he works here. ", variants))
        self.assertTrue(gl.answer_ok("HE'S WORKING HERE", variants))
        self.assertFalse(gl.answer_ok("he work here", variants))
        self.assertFalse(gl.answer_ok("   ", variants))

    def test_choice_answers_use_option_text(self) -> None:
        ex = {"type": "choice", "options": ["am", "is", "are"], "a": 1}
        self.assertEqual(gl.lesson_answers(ex), ["is"])

    def test_lesson_files_are_utf8_json(self) -> None:
        for u in gl.units()[:5]:
            raw = gl.lesson_path(int(u["n"])).read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            json.loads(raw.decode("utf-8"))


class GrammarProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.p = Progress(path=self.tmp / "english.json")

    def test_mark_counts_half_as_done(self) -> None:
        self.assertFalse(self.p.grammar_done(7))
        first = self.p.grammar_mark(7, 3, 6)
        self.assertTrue(first, "первый проход должен вернуть True")
        self.assertTrue(self.p.grammar_done(7))
        self.assertEqual(self.p.grammar_unit(7)["ok"], 3)
        self.assertFalse(self.p.grammar_mark(7, 6, 6), "повторный проход — не первый")

    def test_mark_below_half_is_not_done(self) -> None:
        self.p.grammar_mark(8, 2, 6)
        self.assertFalse(self.p.grammar_done(8))
        self.assertEqual(self.p.grammar_done_count(), 0)

    def test_survives_reload(self) -> None:
        self.p.grammar_mark(9, 5, 5)
        again = Progress(path=self.p.path)
        self.assertTrue(again.grammar_done(9))
        self.assertEqual(again.grammar_done_count(), 1)


if __name__ == "__main__":
    unittest.main()
