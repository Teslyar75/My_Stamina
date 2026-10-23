"""Сквозной сеанс ВСЕХ режимов проверки английского: оба вида × оба скина.

Запускает tools/english_cards_check.py отдельным процессом (реальное окно, временный
APPDATA): ПРОВЕРКА СИСТЕМ (SM-2), миссии СЛУЧАЙНАЯ/ГОВОРЕНИЕ/ЧТЕНИЕ/ВОПРОСЫ со всеми
типами задач до отчёта, Esc-выход, карточки ИЗ КНИГИ, журнал и прочие страницы.
На каждом рабочем шаге карточка должна быть сверху (не под обоями/затемнением/прокруткой),
прогресс — сохранён, в журнале — без исключений. Долгий: STAMINA_SLOW_TESTS=1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_STEPS = ("review_front", "review_back", "review_after", "mission_task", "mission_skip", "book",
              "mission_random_answered", "mission_questions_report", "book_drill_back")


@unittest.skipUnless(os.environ.get("STAMINA_SLOW_TESTS") and sys.platform == "win32",
                     "сквозной тест окна: STAMINA_SLOW_TESTS=1 (Windows)")
class CardSessionTest(unittest.TestCase):
    def run_check(self, layout: str, skin: str) -> dict:
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, str(ROOT / "tools" / "english_cards_check.py"), layout, skin, out],
                           cwd=ROOT, timeout=240, capture_output=True)
            files = list(Path(out).glob("*.json"))
            self.assertTrue(files, "проверка не записала отчёт")
            return json.loads(files[0].read_text(encoding="utf-8"))

    def check(self, layout: str, skin: str) -> None:
        rep = self.run_check(layout, skin)
        self.assertEqual(rep["current"], "english")
        steps = {s["step"]: s for s in rep["steps"]}
        for name in WORK_STEPS:
            self.assertTrue(steps[name]["on_top"], f"{layout}/{skin}: {name} не на виду")
        self.assertGreater(rep.get("cards_in_progress") or 0, 0, "прогресс не сохранён")
        self.assertEqual(rep.get("debug_tracebacks", 0), 0, "исключения в debug.log")
        self.assertEqual(rep["errors"], [], "исключения в обработчиках Tk")
        self.check_modes(rep, f"{layout}/{skin}")

    def check_modes(self, rep: dict, tag: str) -> None:
        """Каждый режим проверки: пройден вводом, отклик на каждый ответ, отчёт, Esc, всё на виду."""
        modes = rep["modes"]
        self.assertGreater(modes["review"]["graded"], 0, tag)
        types: set[str] = set()
        for m in ("random", "speaking", "reading", "questions"):
            info = modes["mission_" + m]
            self.assertTrue(info["active"], f"{tag}: миссия {m} не стартовала")
            self.assertGreater(info["answered"], 0, f"{tag}: {m}")
            self.assertEqual(info["feedback"], info["answered"], f"{tag}: {m} — ответ без отклика")
            self.assertTrue(info["report"], f"{tag}: {m} — нет отчёта о полёте")
            types |= set(info["types"])
        self.assertEqual(types, {"S1", "S2", "S3", "R1", "R2", "R3", "Q1", "Q2", "Q3", "Q4"}, tag)
        self.assertFalse(modes["mission_esc"]["active_after_esc"], f"{tag}: Esc не завершил миссию")
        self.assertTrue(modes["book_drill"]["started"], f"{tag}: карточки из книги")
        self.assertGreater(modes["book_drill"].get("graded", 0), 0, f"{tag}: оценка карточки из книги")
        hidden = [s["step"] for s in rep["steps"] if not (s["mapped"] and s["on_top"]) or s["mean_luma"] < 12]
        self.assertEqual(hidden, [], f"{tag}: не на виду")

    def test_classic_spaceship(self):
        self.check("classic", "spaceship")

    def test_alt_spaceship(self):
        self.check("alt", "spaceship")

    def test_classic_steampunk(self):
        self.check("classic", "steampunk")

    def test_alt_steampunk(self):
        self.check("alt", "steampunk")


if __name__ == "__main__":
    unittest.main()
