"""Грамматика: загрузка уровней и кэш движка."""
from __future__ import annotations

import unittest

from stamina.english.grammar import grammar_engine as ge


class GrammarEngineTest(unittest.TestCase):
    def test_all_levels_have_topics(self) -> None:
        for lv in ge.list_available_levels():
            data = ge.load_grammar(lv)
            self.assertIn("topics", data)
            self.assertGreater(len(data["topics"]), 0, lv)

    def test_load_is_cached(self) -> None:
        ge.load_grammar.cache_clear()
        a = ge.load_grammar("a1")
        b = ge.load_grammar("a1")
        self.assertIs(a, b)

    def test_generate_exercise(self) -> None:
        ex = ge.generate_exercise("a1", "Present Simple")
        self.assertEqual(ex["topic"], "Present Simple")
        self.assertIn(ex["type"], {"fill_gap", "transform", "choose_right", "make_question"})


if __name__ == "__main__":
    unittest.main()
