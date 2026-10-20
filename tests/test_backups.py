"""Резервные копии данных пилота: суточная копия, ротация, восстановление."""
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stamina import backups, pilots


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        pilots.reset_root(Path(self.tmp.name))
        (pilots.ROOT_DIR / "app.json").write_text(json.dumps({"skin": "nebula"}), encoding="utf-8")
        (pilots.ROOT_DIR / "pilots.json").write_text(json.dumps([]), encoding="utf-8")
        (pilots.ROOT_DIR / "orion").mkdir()
        (pilots.ROOT_DIR / "orion" / "history.json").write_text("[]", encoding="utf-8")

    def tearDown(self):
        pilots.reset_root(None)
        self.tmp.cleanup()

    def test_backup_copies_state(self):
        folder = backups.make_backup(force=True)
        self.assertIsNotNone(folder)
        self.assertTrue((folder / "app.json").is_file())
        self.assertTrue((folder / "orion" / "history.json").is_file())

    def test_once_a_day(self):
        self.assertIsNotNone(backups.make_backup())
        self.assertIsNone(backups.make_backup())

    def test_force_twice_and_rotation(self):
        first = backups.make_backup(force=True)
        second = backups.make_backup(force=True)
        self.assertNotEqual(first, second)
        backups.make_backup(force=True, keep=1)
        self.assertEqual(len(backups.list_backups()), 1)

    def test_list_is_newest_first(self):
        old = backups.make_backup(force=True, now=time.time() - 86400 * 3)
        new = backups.make_backup(force=True)
        items = backups.list_backups()
        self.assertEqual(items[0], new)
        self.assertIn(old, items)

    def test_restore_returns_files(self):
        folder = backups.make_backup(force=True)
        (pilots.ROOT_DIR / "app.json").write_text(json.dumps({"skin": "broken"}), encoding="utf-8")
        backups.restore(folder)
        data = json.loads((pilots.ROOT_DIR / "app.json").read_text(encoding="utf-8"))
        self.assertEqual(data["skin"], "nebula")

    def test_restore_keeps_current_state(self):
        folder = backups.make_backup(force=True)
        backups.restore(folder)
        # страховочная копия перед восстановлением: копий стало две
        self.assertGreaterEqual(len(backups.list_backups()), 2)

    def test_summary_names_last_backup(self):
        self.assertEqual(backups.summary(), "")
        folder = backups.make_backup(force=True)
        self.assertEqual(backups.summary(), folder.name)

    def test_missing_root_gives_none(self):
        pilots.reset_root(Path(self.tmp.name) / "нет-такой-папки")
        self.assertIsNone(backups.make_backup(force=True))


if __name__ == "__main__":
    unittest.main()
