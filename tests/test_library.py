"""Тесты общей библиотеки текстов (две версии текста, карта позиций, миграция)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stamina import library as libmod
from stamina.text_processing import process_text
from stamina.textmap import TextMap, fragment_of

ORIGINAL = ("The Pilot's Log\n\nChapter 1\n\nIt was a calm, quiet night on board. The captain "
            "— tired, but happy — wrote: «All systems nominal!»\n\nNobody answered. Stars drifted by; "
            "the engines hummed.\n\nChapter 2\n\nMorning came. The crew woke up and started the day.")
OPTS = {"lower": True, "punct": True, "spaces": True}


def prep(text, opts=OPTS):
    return process_text(text, lower=opts["lower"], punct=opts["punct"], spaces=opts["spaces"])


class TextMapTests(unittest.TestCase):
    def test_exact_mapping_both_ways(self):
        p = prep(ORIGINAL)
        tm = TextMap(ORIGINAL, p, prep)
        self.assertTrue(tm.ok)
        i = p.index("captain")
        w = tm.prep_to_orig(i)
        a, b = tm.orig_tokens[w]
        self.assertEqual(ORIGINAL[a:b], "captain")
        self.assertEqual(p[tm.orig_to_prep(w):].split()[0], "captain")

    def test_fragment_of_prefix(self):
        p = prep(ORIGINAL)
        cut = p[: p.index("nobody")].strip()
        frag = fragment_of(ORIGINAL, cut, prep)
        self.assertIsNotNone(frag)
        self.assertEqual(prep(frag), cut)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.lib = libmod.Library(self.root / "library")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_keeps_two_versions_and_dedupes(self):
        m = self.lib.add(ORIGINAL, title="Log", opts=OPTS)
        self.assertEqual(self.lib.original(m["id"]), ORIGINAL)
        self.assertEqual(self.lib.prepared(m["id"]), prep(ORIGINAL))
        self.assertEqual(self.lib.add(ORIGINAL)["id"], m["id"])
        self.assertEqual(len(self.lib.all()), 1)

    def test_attach_original_and_regenerate_keep_position(self):
        p = prep(ORIGINAL)
        m = self.lib.add("", prepared=p, opts=OPTS, title="x", status="missing")
        self.assertEqual(self.lib.reading_text(m["id"]), p)
        pos = p.index("engines")
        self.lib.set_position(m["id"], "typing", pos)
        self.assertEqual(self.lib.attach_original(m["id"], ORIGINAL), "recovered")
        self.assertEqual(self.lib.reading_text(m["id"]), ORIGINAL)
        new, newpos = self.lib.regenerate(m["id"], {"lower": False, "punct": True, "spaces": True})
        self.assertTrue(new[newpos:].startswith("engines"))

    def test_attach_wrong_original_is_rejected(self):
        m = self.lib.add("", prepared=prep(ORIGINAL), opts=OPTS, title="x", status="missing")
        self.assertEqual(self.lib.attach_original(m["id"], "Completely different text here."), "")

    def test_delete_moves_to_backups(self):
        m = self.lib.add(ORIGINAL, opts=OPTS)
        self.lib.delete(m["id"])
        self.assertEqual(self.lib.all(), [])
        self.assertTrue(any((self.root / "backups" / "deleted-texts").iterdir()))

    def test_upsert_from_cargo(self):
        tid = self.lib.upsert_from_cargo(prep(ORIGINAL), ORIGINAL, OPTS)
        self.assertEqual(self.lib.original(tid), ORIGINAL)
        self.assertEqual(self.lib.upsert_from_cargo(prep(ORIGINAL), ORIGINAL, OPTS), tid)
        self.assertEqual(self.lib.index["active_typing"], tid)


class MigrationTests(unittest.TestCase):
    """Миграция: найти оригинал для текущего «своего текста», session.json не трогать."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.book = self.root / "book.txt"
        self.book.write_text(ORIGINAL, encoding="utf-8")
        self.prepared_file = self.root / "prepared_only.txt"
        part = prep(ORIGINAL)[: prep(ORIGINAL).index("nobody")].strip()
        self.prepared_file.write_text(part, encoding="utf-8")
        self.part = part
        self.session = self.root / "session.json"
        self.session.write_text(json.dumps({"text": part, "index": part.index("captain"), "typed": 10,
                                            "errors": 0, "elapsed": 5.0, "case_sensitive": False}),
                                encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_recovers_fragment_and_keeps_session(self):
        before = self.session.read_bytes()

        class FakeStore:
            settings = {"cargo_opts": OPTS}

            def load_cargo(self):
                return "", ""

        lib = libmod.Library(self.root / "library")
        with mock.patch("stamina.session_storage.SESSION_PATH", self.session):
            rep = libmod.migrate(lib, FakeStore(), candidates=[self.prepared_file, self.book])
        self.assertEqual(rep["original"], "recovered")
        self.assertTrue(rep["fragment"])
        tid = rep["id"]
        self.assertEqual(prep(lib.original(tid)), self.part)
        m = lib.meta(tid)
        self.assertEqual(m["positions"]["typing"]["char"], self.part.index("captain"))
        word = m["positions"]["reading"]["word"]
        a, b = lib.textmap(tid).orig_tokens[word]
        self.assertEqual(lib.original(tid)[a:b], "captain")
        self.assertIn("full_source_offer", m)
        self.assertEqual(self.session.read_bytes(), before)
        self.assertEqual(libmod.migrate(lib, FakeStore())["done"], False)  # однократно


if __name__ == "__main__":
    unittest.main()
