"""Каюта гостя: заселение, документ манер и обращение по имени в чате."""
import tempfile
import unittest
from pathlib import Path

from stamina import guests, orion, pilots


class GuestCabinTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    def test_ensure_settles_guest_once(self):
        rec = guests.ensure("grok-bot")
        self.assertEqual(rec["id"], "grok-bot")
        self.assertEqual(rec["access"], "crew")
        self.assertEqual(rec["profile"], "grok-bot")
        self.assertEqual([a["id"] for a in orion.agents()], ["orion", "grok-bot"])

        again = guests.ensure("grok-bot")
        self.assertEqual(again["id"], "grok-bot")
        self.assertEqual(len(orion.agents()), 2)          # второй раз не дублируется

    def test_character_document_written_and_kept(self):
        guests.ensure("grok-bot")
        path = orion.character_path("grok-bot")
        self.assertTrue(path.exists())
        self.assertIn("Grok Bot", orion.read_character("grok-bot"))

        orion.save_character("grok-bot", "мои правила")     # пилот правит сам
        guests.ensure("grok-bot")
        self.assertEqual(orion.read_character("grok-bot"), "мои правила")

    def test_unknown_guest(self):
        with self.assertRaises(KeyError):
            guests.ensure("никого")


class MentionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        guests.ensure("grok-bot")

    def tearDown(self):
        pilots.reset_root()

    def test_mention_by_short_name(self):
        who, rest = orion.split_mention("@grok, что думаешь про скины?")
        self.assertEqual(who, "grok-bot")
        self.assertEqual(rest, "что думаешь про скины?")

    def test_mention_by_id_and_full_name(self):
        self.assertEqual(orion.split_mention("@grok-bot привет")[0], "grok-bot")
        self.assertEqual(orion.split_mention("@Grok Bot привет")[0], "grok-bot")

    def test_no_mention_keeps_text(self):
        text = "просто сообщение командиру"
        self.assertEqual(orion.split_mention(text), ("", text))

    def test_unknown_mention_keeps_text(self):
        text = "@никто привет"
        self.assertEqual(orion.split_mention(text), ("", text))

    def test_mention_only_switches_channel(self):
        who, rest = orion.split_mention("@grok")
        self.assertEqual(who, "grok-bot")
        self.assertEqual(rest, "")


if __name__ == "__main__":
    unittest.main()
