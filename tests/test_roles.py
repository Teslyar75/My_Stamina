"""Роли: капитан = разработчик с подтверждённым доступом к GitHub."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from stamina import pilots, roles
from stamina.english import access
from stamina.english.progress import Progress


def _repo(private=False, **perms):
    return 200, {"private": private, "permissions": perms}


class RolesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._force = roles._FORCE_FILE_STORE
        roles._FORCE_FILE_STORE = True
        pilots.reset_root(self.root)
        self.pilot = pilots.create("Tester")
        pilots.activate(self.pilot["id"])
        self.pid = self.pilot["id"]

    def tearDown(self) -> None:
        roles._FORCE_FILE_STORE = self._force
        pilots.reset_root()
        self.tmp.cleanup()

    def test_migrated_from_alone_is_not_captain(self) -> None:
        pilots.update_pilot(self.pid, migrated_from=r"C:\old")
        p = pilots.get(self.pid)
        self.assertTrue(p.get("migrated_from"))
        self.assertFalse(roles.is_captain(p))
        self.assertFalse(roles.is_developer(p))
        self.assertFalse(pilots.is_captain(p))
        self.assertFalse(access.is_captain())
        self.assertEqual(roles.role_of(p), roles.PILOT)

    def test_role_field_alone_is_not_captain(self) -> None:
        pilots.set_role(self.pid, pilots.CAPTAIN)
        p = pilots.get(self.pid)
        self.assertEqual(p.get("role"), "captain")
        self.assertFalse(roles.is_captain(p))
        self.assertEqual(roles.role_of(p), roles.PILOT)

    def test_developer_with_github_push_is_captain(self) -> None:
        calls = []

        def fake_http(url, token, timeout):
            calls.append(url)
            if url.endswith("/user"):
                return 200, {"login": "Teslyar75"}
            if url.rstrip("/").endswith("My_Stamina"):
                return _repo(admin=False, push=True, pull=True)
            return 404, {}

        with mock.patch.object(roles, "_http_json", side_effect=fake_http):
            ok, msg = roles.link_github(self.pid, "Teslyar75", "ghp_test_token")
        self.assertTrue(ok, msg)
        p = pilots.get(self.pid)
        self.assertTrue(roles.is_developer(p))
        self.assertTrue(roles.is_captain(p))
        self.assertEqual(roles.is_captain(p), roles.is_developer(p))
        self.assertTrue(pilots.is_captain(p))
        self.assertEqual(roles.role_of(p), roles.CAPTAIN)
        # токен не в реестре и не в кэше
        raw = (pilots.ROOT_DIR / "pilots.json").read_text(encoding="utf-8")
        self.assertNotIn("ghp_test_token", raw)
        cache = json.loads(roles.cache_path(self.pid).read_text(encoding="utf-8"))
        self.assertNotIn("ghp_test_token", json.dumps(cache))
        self.assertTrue(roles.token_path(self.pid).is_file())
        self.assertIn("ghp_test_token", roles.token_path(self.pid).read_text(encoding="utf-8"))
        self.assertGreater(len(calls), 0)

    def test_fresh_cache_skips_network(self) -> None:
        roles.write_access_cache(self.pid, ok=True, login="dev")
        with mock.patch.object(roles, "_http_json", side_effect=AssertionError("no network")):
            self.assertTrue(roles.is_captain(pilots.get(self.pid)))
            self.assertTrue(roles.verify_github(pilots.get(self.pid), force=False))

    def test_offline_uses_cache(self) -> None:
        roles.write_access_cache(self.pid, ok=True, login="dev")
        # просрочить кэш, оставив результат
        path = roles.cache_path(self.pid)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["checked_at"] = time.time() - roles.CACHE_TTL_SEC - 10
        path.write_text(json.dumps(data), encoding="utf-8")
        roles._store_token(self.pid, "ghp_old")
        with mock.patch.object(roles, "_http_json", side_effect=urllib.error.URLError("offline")):
            self.assertTrue(roles.verify_github(pilots.get(self.pid), force=True))
        # кэш не переписан в отказ
        self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["ok"])

    def test_offline_without_cache_is_not_developer(self) -> None:
        roles._store_token(self.pid, "ghp_old")
        with mock.patch.object(roles, "_http_json", side_effect=urllib.error.URLError("offline")):
            self.assertFalse(roles.verify_github(pilots.get(self.pid), force=True))
        self.assertFalse(roles.is_developer(pilots.get(self.pid)))

    def test_public_pull_only_is_not_developer(self) -> None:
        def fake_http(url, token, timeout):
            if url.endswith("/user"):
                return 200, {"login": "someone"}
            if "/collaborators/" in url:
                return 404, {}
            return _repo(private=False, push=False, pull=True)

        with mock.patch.object(roles, "_http_json", side_effect=fake_http):
            ok, _ = roles.link_github(self.pid, "someone", "ghp_x")
        self.assertFalse(ok)
        self.assertFalse(roles.is_captain(pilots.get(self.pid)))

    def test_private_pull_is_developer(self) -> None:
        def fake_http(url, token, timeout):
            if url.endswith("/user"):
                return 200, {"login": "collab"}
            return _repo(private=True, push=False, pull=True)

        with mock.patch.object(roles, "_http_json", side_effect=fake_http):
            ok, _ = roles.link_github(self.pid, "collab", "ghp_x")
        self.assertTrue(ok)
        self.assertTrue(roles.is_captain(pilots.get(self.pid)))


class SequentialUnlockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._force = roles._FORCE_FILE_STORE
        roles._FORCE_FILE_STORE = True
        pilots.reset_root(self.root)
        self.progress = Progress(self.root / "english.json")

    def tearDown(self) -> None:
        roles._FORCE_FILE_STORE = self._force
        pilots.reset_root()
        self.tmp.cleanup()

    def _open(self, done):
        levels = ["A1", "A2", "B1.1"]
        words = {"A1": list("abcde"), "A2": list("fg"), "B1.1": list("h")}
        return lambda lv: access.level_open(
            self.progress, lv, levels, words.get, lambda s: s in done)

    def test_a1_open_a2_closed_until_threshold(self) -> None:
        done = set()
        is_open = self._open(done)
        self.assertTrue(is_open("A1"))
        self.assertFalse(is_open("A2"))
        done.update(set("abc"))  # 60%
        self.assertFalse(is_open("A2"))
        done.add("d")  # 80%
        self.assertTrue(is_open("A2"))
        self.assertFalse(is_open("B1.1"))

    def test_start_level_cannot_open_higher(self) -> None:
        self.progress.settings["cefr_start_level"] = "C2"
        is_open = self._open(set())
        self.assertTrue(is_open("A1"))
        self.assertFalse(is_open("A2"))
        self.assertFalse(is_open("B1.1"))
        self.assertEqual(access.start_level(self.progress, ["A1", "A2", "C2"]), "C2")
        self.assertEqual(access.start_level(self.progress, ["A1", "A2", "B1.1"]), "A1")

    def test_s1000_open_s3000_closed_until_threshold(self) -> None:
        from stamina import terraformer_bay as tb
        prog = self.progress
        with mock.patch.object(tb.access, "is_captain", return_value=False), \
             mock.patch.object(tb.access, "unlock_pct", return_value=80), \
             mock.patch.object(tb, "_freq_slugs", return_value=[f"w{i}" for i in range(10)]), \
             mock.patch.object(tb, "_done", side_effect=lambda p, s: int(s[1:]) < 7):
            self.assertTrue(tb.robot_open(prog, "s1000"))
            self.assertFalse(tb.robot_open(prog, "s3000"))
        with mock.patch.object(tb.access, "is_captain", return_value=False), \
             mock.patch.object(tb.access, "unlock_pct", return_value=80), \
             mock.patch.object(tb, "_freq_slugs", return_value=[f"w{i}" for i in range(10)]), \
             mock.patch.object(tb, "_done", side_effect=lambda p, s: int(s[1:]) < 8):
            self.assertTrue(tb.robot_open(prog, "s3000"))


if __name__ == "__main__":
    unittest.main()


class DedupePasteTest(unittest.TestCase):
    def test_repeated_paste_collapses(self) -> None:
        from stamina import roles
        tok = "github_pat_ABC123"
        self.assertEqual(roles._dedupe_paste(tok * 3), tok)
        self.assertEqual(roles._dedupe_paste(tok), tok)
