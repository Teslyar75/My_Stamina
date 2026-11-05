"""Рекорды комнаты отдыха — у каждого пилота свои; старый общий файл сброшен. Только временная папка."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from stamina import pilot_migrate, pilots
from stamina.lounge import store


class LoungePerPilot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Stamina"
        self.root.mkdir()
        pilots.reset_root(self.root)
        self.a = pilots.create("ALPHA")["id"]
        self.b = pilots.create("BRAVO")["id"]

    def tearDown(self):
        pilots.reset_root()
        self.tmp.cleanup()

    def test_records_are_per_pilot(self):
        pilots.activate(self.a)
        store.set_best("tetris", 5000)
        store.set_best("breakout", 300)
        pilots.activate(self.b)
        self.assertEqual(store.best("tetris"), 0)
        self.assertEqual(store.best("breakout"), 0)
        store.set_best("tetris", 70)
        store.set_best("snake", 12)
        pilots.activate(self.a)
        self.assertEqual(store.best("tetris"), 5000)
        self.assertEqual(store.best("breakout"), 300)
        self.assertEqual(store.best("snake"), 0)
        pilots.activate(self.b)
        self.assertEqual(store.best("tetris"), 70)
        self.assertTrue((pilots.pilot_dir(self.a) / "lounge.json").is_file())
        self.assertFalse((self.root / "lounge.json").exists())

    def test_old_shared_file_is_retired_not_shown(self):
        old = self.root / "lounge.json"
        old.write_text(json.dumps({"best": {"tetris": 9999, "breakout": 888}}), encoding="utf-8")
        pilots.activate(self.a)
        self.assertEqual(store.best("tetris"), 0)
        self.assertFalse(old.exists())
        kept = self.root / "lounge.json.shared-old"
        self.assertEqual(json.loads(kept.read_text(encoding="utf-8"))["best"]["tetris"], 9999)
        pilots.activate(self.b)
        self.assertEqual(store.best("breakout"), 0)
        store.best("tetris")          # повторно — ничего не ломается и не переименовывается
        self.assertTrue(kept.is_file())
        self.assertFalse((self.root / "lounge.json.shared-old.1").exists())

    def test_late_sync_does_not_copy_root_lounge(self):
        reg = pilots.load_registry()
        reg["migrated_at"] = time.time() - 100
        reg["pilots"][0]["migrated_from"] = str(self.root)
        pilots.save_registry(reg)
        (self.root / "lounge.json").write_text(json.dumps({"best": {"tetris": 1}}), encoding="utf-8")
        moved = pilot_migrate.late_sync()
        self.assertNotIn("lounge.json", moved or [])
        self.assertFalse((pilots.pilot_dir(self.a) / "lounge.json").exists())

    def test_legacy_migration_skips_root_lounge(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "Stamina"
        root.mkdir()
        try:
            pilots.reset_root(root)
            (root / "stats.json").write_text(json.dumps({"xp": 1, "runs": []}), encoding="utf-8")
            (root / "lounge.json").write_text(json.dumps({"best": {"tetris": 5}}), encoding="utf-8")
            self.assertNotIn("lounge.json", [p.name for p in pilot_migrate.legacy_items(root)])
            rep = pilot_migrate.migrate()
            self.assertTrue(rep["done"])
            self.assertFalse((pilots.pilot_dir(rep["id"]) / "lounge.json").exists())
        finally:
            pilots.reset_root(self.root)
            tmp.cleanup()

    def test_export_import_carries_lounge(self):
        self.assertIn("lounge.json", pilots.DATA_FILES)
        pilots.activate(self.a)
        store.set_best("tetris", 4321)
        pkg = Path(self.tmp.name) / "a.stpilot"
        pilots.export(self.a, pkg)
        self.assertIn("lounge.json", pilots.read_package(pkg)["files"])
        new = pilots.import_package(pkg)["id"]
        pilots.activate(new)
        self.assertEqual(store.best("tetris"), 4321)
        pilots.activate(self.b)
        self.assertEqual(store.best("tetris"), 0)


if __name__ == "__main__":
    unittest.main()
