"""Чтение JSON, записанного PowerShell: BOM в начале файла не должен ломать доклад."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stamina import orion


class BomJsonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "orion" / "progress.json"
        self.path.parent.mkdir(parents=True)
        self.old = os.environ.get("STAR_TYPING_PROGRESS_FILE")
        os.environ["STAR_TYPING_PROGRESS_FILE"] = str(self.path)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STAR_TYPING_PROGRESS_FILE", None)
        else:
            os.environ["STAR_TYPING_PROGRESS_FILE"] = self.old
        self.tmp.cleanup()

    def test_bom_is_tolerated(self):
        data = {"version": 1, "task": "Проверка связи", "steps": ["шаг"], "done": 1,
                "state": "done", "updated": 1}
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")
        self.assertEqual(orion.read_progress()["task"], "Проверка связи")
        self.assertEqual(orion.progress_view()["percent"], 100)

    def test_plain_utf8_still_reads(self):
        self.path.write_text(json.dumps({"task": "Без BOM"}), encoding="utf-8")
        self.assertEqual(orion.read_progress()["task"], "Без BOM")


if __name__ == "__main__":
    unittest.main()
