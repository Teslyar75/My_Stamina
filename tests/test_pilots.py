"""Экипаж: реестр, миграция, код доступа, экспорт/импорт, сводка. Всё на временной папке.

Коды доступа в тестах только случайные — фиксированных значений нет.
"""
import json
import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path

from stamina import pilot_migrate, pilot_pin, pilots
from stamina.pilot_stats import pilot_stats


def rnd_code() -> str:
    n = 4 + secrets.randbelow(5)
    return "".join(str(secrets.randbelow(10)) for _ in range(n))


LEGACY = {
    "settings.json": {"sound": True, "geometry": "1200x800+10+10"},
    "stats.json": {"version": 1, "runs": [{"chars": 300, "cpm": 210.5, "acc": 97.2, "xp": 30,
                                            "ts": time.time() - 3600}],
                   "keys": {}, "missions": {"en-01": {"stars": 3}}, "xp": 404},
    "session.json": {"text": "a" * 1000, "index": 190, "typed": 200, "errors": 3, "elapsed": 61.5},
    "english.json": {"version": 1, "words": {"cat": {"known": True}, "dog": {"known": True}},
                     "cards": {"sun": {"interval": 30}}, "attempts": [
                         {"ts": time.time(), "mode": "speaking", "score": 80},
                         {"ts": time.time(), "mode": "speaking", "score": 90}],
                     "xp": {"total": 10, "by_day": {time.strftime("%Y-%m-%d"): 10}}, "achievements": {"first_step": "x"}},
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Stamina"
        self.root.mkdir()
        pilots.reset_root(self.root)

    def tearDown(self):
        pilots.reset_root()
        self.tmp.cleanup()

    def write_legacy(self):
        for name, data in LEGACY.items():
            (self.root / name).write_text(json.dumps(data), encoding="utf-8")
        (self.root / "cargo.txt").write_text("свой текст", encoding="utf-8")
        lib = self.root / "library" / "texts" / "t-1"
        lib.mkdir(parents=True)
        (lib / "original.txt").write_text("Original", encoding="utf-8")


class MigrationTest(Base):
    def test_fresh_install_does_nothing(self):
        self.assertEqual(pilot_migrate.migrate()["reason"], "fresh")
        self.assertIsNone(pilots.load_registry())

    def test_migration_preserves_bytes(self):
        self.write_legacy()
        before = {n: pilots.sha256_file(self.root / n) for n in list(LEGACY) + ["cargo.txt"]}
        rep = pilot_migrate.migrate()
        self.assertTrue(rep["done"])
        reg = pilots.load_registry()
        p = reg["pilots"][0]
        self.assertEqual((p["callsign"], p["name"]), ("George Orwell", "1984"))
        self.assertTrue(p["pin_setup_pending"])
        prof = pilots.profile(p["id"])
        self.assertNotIn("pin", prof)
        self.assertTrue(prof["pin_setup_pending"])
        d = pilots.pilot_dir(p["id"])
        for n, h in before.items():
            self.assertEqual(pilots.sha256_file(d / n), h, n)
            self.assertFalse((self.root / n).exists())
            self.assertTrue((self.root / (n + ".migrated")).exists())
        self.assertTrue((d / "library" / "texts" / "t-1" / "original.txt").exists())
        self.assertEqual(pilots.load_app()["geometry"], "1200x800+10+10")
        backups = list((self.root / "backups").glob("pre-pilots-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(pilots.sha256_file(backups[0] / "session.json"), before["session.json"])

    def test_idempotent(self):
        self.write_legacy()
        pilot_migrate.migrate()
        self.assertEqual(pilot_migrate.migrate()["reason"], "already")
        self.assertEqual(len(pilots.pilots()), 1)

    def test_retry_after_crash_before_commit(self):
        self.write_legacy()
        # сбой: папка пилота создана, реестр не записан
        (self.root / "pilots" / "p-half").mkdir(parents=True)
        rep = pilot_migrate.migrate()
        self.assertTrue(rep["done"])
        self.assertEqual(len(pilots.pilots()), 1)
        self.assertTrue(list((self.root / "backups").glob("incomplete-pilots-*")))

    def test_failure_leaves_data(self):
        self.write_legacy()
        orig = pilot_migrate.copy_verified
        pilot_migrate.copy_verified = lambda *a: (_ for _ in ()).throw(OSError("disk"))
        try:
            rep = pilot_migrate.migrate()
        finally:
            pilot_migrate.copy_verified = orig
        self.assertEqual(rep["reason"], "error")
        self.assertIsNone(pilots.load_registry())
        self.assertTrue((self.root / "session.json").exists())
        self.assertTrue((self.root / "pilots_error.log").exists())

    def test_late_sync(self):
        self.write_legacy()
        pilot_migrate.migrate()
        reg = pilots.load_registry()
        reg["migrated_at"] = time.time() - 100
        pilots.save_registry(reg)
        pid = reg["pilots"][0]["id"]
        os.utime(pilots.pilot_dir(pid) / "session.json", (time.time() - 200, time.time() - 200))
        (self.root / "session.json").write_text('{"text": "x", "index": 999}', encoding="utf-8")
        self.assertEqual(pilot_migrate.late_sync(), ["session.json"])
        self.assertEqual(json.loads((pilots.pilot_dir(pid) / "session.json").read_text())["index"], 999)


class RegistryTest(Base):
    def test_create_validate_activate(self):
        a = pilots.create("Комета", accent="amber")
        self.assertEqual(pilots.validate_callsign("комета"), "Позывной занят")
        self.assertTrue(pilots.validate_callsign("x"))
        self.assertTrue(pilots.validate_callsign("bad/name"))
        b = pilots.create("Vega-2")
        self.assertEqual(pilots.find("vega-2")["id"], b["id"])
        pilots.activate(a["id"])
        self.assertEqual(pilots.active_dir(), pilots.pilot_dir(a["id"]))
        self.assertNotEqual(pilots.pilot_dir(a["id"]), pilots.pilot_dir(b["id"]))

    def test_delete_rules(self):
        a = pilots.create("Alpha")
        with self.assertRaises(ValueError):
            pilots.delete(a["id"])          # последний
        b = pilots.create("Bravo")
        with self.assertRaises(ValueError):
            pilots.delete(a["id"], active=a["id"])
        dest = pilots.delete(b["id"], active=a["id"])
        self.assertTrue(dest.exists())
        self.assertIn("deleted", str(dest))
        self.assertIsNone(pilots.get(b["id"]))

    def test_export_import_roundtrip(self):
        a = pilots.create("Orion")
        d = pilots.pilot_dir(a["id"])
        (d / "stats.json").write_text(json.dumps(LEGACY["stats.json"]), encoding="utf-8")
        code = rnd_code()
        pilot_pin.set_pin(a["id"], code)
        pkg = Path(self.tmp.name) / "o.stpilot"
        pilots.export(a["id"], pkg)
        imp = pilots.import_package(pkg)
        self.assertNotEqual(imp["id"], a["id"])
        self.assertEqual(imp["callsign"], "Orion-2")
        self.assertEqual(pilots.sha256_file(pilots.pilot_dir(imp["id"]) / "stats.json"),
                         pilots.sha256_file(d / "stats.json"))
        self.assertTrue(pilot_pin.verify(imp["id"], code)[0])


class PinTest(Base):
    def test_pin_lifecycle(self):
        p = pilots.create("Lyra")
        code = rnd_code()
        pilot_pin.set_pin(p["id"], code)
        self.assertTrue(pilots.get(p["id"])["locked"])
        self.assertTrue(pilot_pin.verify(p["id"], code)[0])
        wrong = code[:-1] + str((int(code[-1]) + 1) % 10)
        ok, msg = pilot_pin.verify(p["id"], wrong)
        self.assertFalse(ok)
        self.assertIn("4", msg)
        for _ in range(4):
            pilot_pin.verify(p["id"], wrong)
        self.assertGreater(pilot_pin.lock_left(p["id"]), 0)
        self.assertFalse(pilot_pin.verify(p["id"], code)[0])      # заблокировано
        self.assertTrue(pilot_pin.verify(p["id"], code, now=time.time() + 31)[0])
        # код нигде не лежит открытым текстом
        for f in self.root.rglob("*"):
            if f.is_file():
                self.assertNotIn(f'"{code}"', f.read_text(encoding="utf-8", errors="ignore"))
        pilot_pin.clear_pin(p["id"], reason="test")
        self.assertFalse(pilots.get(p["id"])["locked"])
        self.assertTrue((self.root / "pilots_audit.log").exists())

    def test_salts_differ(self):
        code = rnd_code()
        a, b = pilot_pin.make_hash(code), pilot_pin.make_hash(code)
        self.assertNotEqual(a["salt"], b["salt"])
        self.assertNotEqual(a["hash"], b["hash"])
        self.assertEqual(a["iter"], 200_000)
        with self.assertRaises(ValueError):
            pilot_pin.make_hash("12a4")


class StatsTest(Base):
    def test_summary(self):
        self.write_legacy()
        pilot_migrate.migrate()
        pid = pilots.pilots()[0]["id"]
        s = pilot_stats(pid)
        self.assertEqual(s["xp"], 404)
        self.assertEqual(s["rank"], "Мичман")
        self.assertEqual(s["best_cpm"], 210)
        self.assertEqual(s["book_pct"], 19.0)
        self.assertEqual(s["en_known"], 3)
        self.assertEqual(s["en_pron"], 85)
        self.assertGreaterEqual(s["streak"], 1)
        self.assertGreater(s["ach_done"], 0)
        w = pilot_stats(pid, "week")
        self.assertEqual(w["xp_week"], 40)

    def test_empty_pilot(self):
        p = pilots.create("Nova")
        s = pilot_stats(p["id"])
        self.assertEqual((s["xp"], s["best_cpm"], s["en_known"], s["book_pct"]), (0, 0, 0, None))
        self.assertEqual(s["rank"], "Кадет")


if __name__ == "__main__":
    unittest.main()
