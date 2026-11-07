#!/usr/bin/env python3
"""Целевые тесты автономного каталога (без import stamina)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import quota  # noqa: E402


class CursorQuotaTest(unittest.TestCase):
    def test_parse_usage_payload_direct(self):
        payload = {
            "used_tokens": 1234,
            "limit_tokens": 5000,
            "period": "2026-11",
            "models": {
                "gpt-5.3-codex": {"used_tokens": 1000, "limit_tokens": 4000},
                "gpt-5.3-codex-fast": {"used_tokens": 234, "limit_tokens": 1000},
            },
        }
        snap = quota.parse_usage_payload(payload)
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["used"], 1234)
        self.assertEqual(snap["limit"], 5000)
        self.assertEqual(snap["remaining"], 3766)
        self.assertAlmostEqual(snap["percent"], 24.68, delta=0.05)
        self.assertEqual(len(snap["models"]), 2)

    def test_parse_usage_payload_nested(self):
        payload = {
            "data": {"usage": "2500", "quota": "10000", "billing_period": "month"},
            "result": {
                "by_model": [
                    {"model": "gpt-5.3-codex", "used": 2000, "limit": 8000},
                    {"model": "gpt-5.3-codex-fast", "used": 500, "limit": 2000},
                ]
            },
        }
        snap = quota.parse_usage_payload(payload, limit=0, period="")
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["used"], 2500)
        self.assertEqual(snap["limit"], 10000)
        self.assertEqual(snap["period"], "month")
        self.assertEqual(len(snap["models"]), 2)

    def test_parse_usage_payload_uses_fallback_limit(self):
        payload = {"usage": 700}
        snap = quota.parse_usage_payload(payload, limit=1000, period="week")
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["used"], 700)
        self.assertEqual(snap["limit"], 1000)
        self.assertEqual(snap["remaining"], 300)
        self.assertEqual(snap["period"], "week")

    def test_parse_usage_payload_reports_missing_fields(self):
        snap = quota.parse_usage_payload({"meta": {"hello": "world"}})
        self.assertFalse(snap["ok"])
        self.assertEqual(snap["error"], "format")

    def test_load_save_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cfg.json"
            saved = quota.save_settings(
                url="https://api.example.com/usage",
                token="tok_123",
                period="month",
                limit=9000,
                refresh=45,
                path=path,
            )
            self.assertEqual(saved["refresh"], 45)
            loaded = quota.load_settings(path)
            self.assertEqual(loaded["url"], "https://api.example.com/usage")
            self.assertEqual(loaded["token"], "tok_123")
            self.assertEqual(loaded["period"], "month")
            self.assertEqual(loaded["limit"], 9000)
            self.assertEqual(loaded["refresh"], 45)

    def test_load_settings_sanitizes_values(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cfg.json"
            path.write_text(
                json.dumps({"url": "x", "token": "y", "period": "z", "limit": -1, "refresh": 2}),
                encoding="utf-8",
            )
            loaded = quota.load_settings(path)
            self.assertEqual(loaded["limit"], 0)
            self.assertEqual(loaded["refresh"], 10)

    def test_catalog_does_not_import_stamina(self):
        src = (HERE / "widget.py").read_text(encoding="utf-8") + (HERE / "quota.py").read_text(encoding="utf-8")
        self.assertNotIn("import stamina", src)
        self.assertNotIn("from stamina", src)


if __name__ == "__main__":
    unittest.main()
