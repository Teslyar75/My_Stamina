"""Проверка книги у Ориона: нарезка, сборка правок, опрос агента."""
import json
import unittest

from stamina import book_check, orion


class SplitChunksTest(unittest.TestCase):
    def test_text_survives_splitting(self):
        text = "\n".join("строка {0} с несколькими словами".format(i) for i in range(300))
        chunks = book_check.split_chunks(text, size=500)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 500 for c in chunks))

    def test_long_line_is_cut_in_pieces(self):
        text = "а" * 1300
        chunks = book_check.split_chunks(text, size=500)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 500 for c in chunks))
        self.assertGreaterEqual(len(chunks), 3)

    def test_empty_chunks_dropped(self):
        text = "слово\n\n\n\nещё слово"
        chunks = book_check.split_chunks(text, size=500)
        self.assertTrue(all(c.strip() for c in chunks))
        self.assertEqual("".join(chunks), text)

    def test_empty_text(self):
        self.assertEqual(book_check.split_chunks("", size=500), [])
        self.assertEqual(book_check.split_chunks(None), [])


class CollectTest(unittest.TestCase):
    def test_first_wins_and_no_repeats(self):
        replies = [
            [("ивот", "живот"), ("тча", "тысяча")],
            [("Ивот", "живот"), ("бсолютно", "абсолютно")],
        ]
        self.assertEqual(book_check.collect(replies),
                         [("ивот", "живот"), ("тча", "тысяча"), ("бсолютно", "абсолютно")])

    def test_empty_replies(self):
        self.assertEqual(book_check.collect([]), [])
        self.assertEqual(book_check.collect([[], None]), [])


class RunCheckTest(unittest.TestCase):
    def test_asks_every_chunk_and_counts(self):
        asked = []
        seen = []

        def ask(prompt):
            asked.append(prompt)
            return json.dumps([{"bad": "ивот", "good": "живот"}])

        fixes = book_check.run_check("маленький текст для проверки", ask,
                                     chunks=["кусок один", "кусок два"],
                                     progress=lambda i, n: seen.append((i, n)))
        self.assertEqual(len(asked), 2)
        self.assertEqual(seen, [(1, 2), (2, 2)])
        self.assertEqual(fixes, [("ивот", "живот")])
        self.assertTrue(all("кусок" in p for p in asked))

    def test_empty_reply_gives_nothing(self):
        fixes = book_check.run_check("текст", lambda p: "", chunks=["а"])
        self.assertEqual(fixes, [])

    def test_parser_understands_arrow_lines(self):
        fixes = book_check.run_check("текст", lambda p: "ивот → живот", chunks=["а"])
        self.assertEqual(fixes, [("ивот", "живот")])


class BackgroundTest(unittest.TestCase):
    def test_result_comes_back_through_after(self):
        class FakeApp:
            def __init__(self):
                self.calls = []

            def after(self, _ms, fn):
                self.calls.append(fn())
                return "id"

        app = FakeApp()
        got = []
        thread = book_check.check_in_background(
            app, "текст", {}, on_done=got.append,
            ask=lambda p: json.dumps([{"bad": "ивот", "good": "живот"}]))
        thread.join(5)
        self.assertEqual(got, [[("ивот", "живот")]])
        self.assertEqual(len(app.calls), 2)          # прогресс по куску + готовый итог

    def test_agent_failure_is_swallowed(self):
        class FakeApp:
            def after(self, _ms, fn):
                return fn()

        def boom(_prompt):
            raise RuntimeError("нет связи")

        got = []
        book_check.check_in_background(FakeApp(), "текст", {}, on_done=got.append, ask=boom)
        self.assertEqual(got, [[]])

    def test_apply_fixes_from_window(self):
        text = "мой ивот болит, а тча уже далеко"
        fixed = orion.apply_fixes(text, [("ивот", "живот"), ("тча", "тысяча")])
        self.assertEqual(fixed, "мой живот болит, а тысяча уже далеко")


if __name__ == "__main__":
    unittest.main()
