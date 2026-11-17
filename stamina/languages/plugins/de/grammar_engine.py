"""German Grammar Engine: loads JSON data, generates exercises, validates answers."""
from __future__ import annotations

import json
import random
from pathlib import Path

from stamina.languages.core.base import (
    GrammarEngine, GrammarTopic, Exercise, ValidationResult
)


class GermanGrammarEngine(GrammarEngine):
    """Grammar engine for German: loads courses/tables/lessons from JSON."""

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder or Path(__file__).parent / "grammar"
        self._courses: dict | None = None
        self._tables: dict | None = None
        self._lessons_cache: dict[str, dict] = {}
        self._levels_cache: list[dict] | None = None

    # ---------- Lazy loading helpers ----------

    def _load_courses(self) -> dict:
        if self._courses is None:
            path = self.folder / "courses.json"
            try:
                self._courses = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._courses = {"version": 1, "language": "de", "levels": [], "tables_file": "tables.json"}
        return self._courses

    def _load_tables(self) -> dict:
        if self._tables is None:
            courses = self._load_courses()
            tables_file = courses.get("tables_file", "tables.json")
            path = self.folder / tables_file
            try:
                self._tables = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._tables = {"version": 1, "tables": []}
        return self._tables

    def _load_level(self, cefr: str) -> dict | None:
        """Load a single level file (a1.json, b2.json, etc.)."""
        if cefr in self._lessons_cache:
            return self._lessons_cache[cefr]
        courses = self._load_courses()
        level_info = next((lvl for lvl in courses.get("levels", []) if lvl["code"] == cefr), None)
        if not level_info:
            return None
        path = self.folder / level_info["file"]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._lessons_cache[cefr] = data
            return data
        except (OSError, json.JSONDecodeError):
            return None

    # ---------- Public API (contract) ----------

    def get_topics(self, cefr: str) -> list[GrammarTopic]:
        """Return all topics up to and including the given CEFR level."""
        courses = self._load_courses()
        level_order = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
        target_order = level_order.get(cefr, 5)
        topics: list[GrammarTopic] = []
        for lvl in courses.get("levels", []):
            if level_order.get(lvl["code"], 0) <= target_order:
                data = self._load_level(lvl["code"])
                if data:
                    for lesson in data.get("lessons", []):
                        for topic_id in lesson.get("topics", []):
                            topics.append(GrammarTopic(
                                id=topic_id,
                                name=lesson["title"],
                                cefr_level=lvl["code"],
                                description=lesson.get("subtitle", ""),
                                exercise_types=[]
                            ))
        return topics

    def generate_exercise(self, topic_id: str, difficulty: str, seed: int) -> Exercise:
        """Generate a deterministic exercise for a topic."""
        rng = random.Random(seed)
        # Find the lesson containing this topic
        lesson = self._find_lesson_by_topic(topic_id)
        if not lesson:
            return Exercise(
                id=f"{topic_id}_{seed}",
                topic_id=topic_id,
                type="choice",
                prompt=f"Упражнение для {topic_id} не найдено",
                expected_answer=[""],
                options=[""]
            )

        drills = lesson.get("drills", [])
        if not drills:
            return Exercise(
                id=f"{topic_id}_{seed}",
                topic_id=topic_id,
                type="choice",
                prompt="Нет упражнений для этой темы",
                expected_answer=[""],
                options=[""]
            )

        # Select drill based on difficulty (easy=first, medium=middle, hard=last)
        idx_map = {"easy": 0, "medium": len(drills) // 2, "hard": -1}
        idx = idx_map.get(difficulty, 0)
        if idx == -1:
            idx = len(drills) - 1
        idx = max(0, min(idx, len(drills) - 1))

        drill = drills[idx]
        return Exercise(
            id=drill["id"],
            topic_id=topic_id,
            type=drill["type"],
            prompt=drill["prompt"],
            expected_answer=drill["answer"] if isinstance(drill["answer"], list) else [drill["answer"]],
            options=drill.get("options", []),
            metadata={"why": drill.get("why", ""), "lesson_id": lesson["id"]}
        )

    def validate_answer(self, exercise: Exercise, answer: str) -> ValidationResult:
        """Validate answer with tolerance for case, spaces, ä/ae, ö/oe, ü/ue, ß/ss."""
        expected = exercise.expected_answer
        if isinstance(expected, str):
            expected = [expected]

        def normalize(s: str) -> str:
            s = s.strip().lower()
            s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            s = s.rstrip(".")
            return s

        norm_answer = normalize(answer)
        norm_expected = [normalize(e) for e in expected]

        correct = norm_answer in norm_expected
        return ValidationResult(
            correct=correct,
            score=1.0 if correct else 0.0,
            feedback=exercise.metadata.get("why", "") if not correct else "",
            correct_answer=expected[0] if expected else None
        )

    def get_explanation(self, topic_id: str, learner_lang: str) -> str:
        """Return theory text for a topic (in Russian)."""
        lesson = self._find_lesson_by_topic(topic_id)
        if not lesson:
            return f"Пояснение для {topic_id} не найдено."

        parts = []
        for block in lesson.get("theory", []):
            kind = block.get("kind")
            if kind == "text":
                parts.append(block.get("text", ""))
            elif kind == "rule":
                parts.append(f"{block.get('title', '')}: {block.get('text', '')}")
            elif kind == "table":
                table = self.table(block.get("ref", ""))
                if table:
                    parts.append(f"Таблица: {table.get('title', '')}")
            elif kind == "example":
                parts.append(f"Пример: {block.get('de', '')} — {block.get('ru', '')}")
        return "\n\n".join(parts) if parts else "Пояснение отсутствует."

    # ---------- New methods for the page ----------

    def levels(self) -> list[dict]:
        """Return level manifest from courses.json."""
        courses = self._load_courses()
        return courses.get("levels", [])

    def lessons(self, cefr: str | None = None) -> list[dict]:
        """Return all lessons, optionally filtered by CEFR level."""
        courses = self._load_courses()
        result = []
        for lvl in courses.get("levels", []):
            if cefr and lvl["code"] != cefr:
                continue
            data = self._load_level(lvl["code"])
            if data:
                for lesson in data.get("lessons", []):
                    lesson_copy = dict(lesson)
                    lesson_copy["level"] = lvl["code"]
                    result.append(lesson_copy)
        return result

    def lesson(self, lesson_id: str) -> dict | None:
        """Return a single lesson by its id."""
        for lvl in self._load_courses().get("levels", []):
            data = self._load_level(lvl["code"])
            if data:
                for lesson in data.get("lessons", []):
                    if lesson["id"] == lesson_id:
                        lesson_copy = dict(lesson)
                        lesson_copy["level"] = lvl["code"]
                        return lesson_copy
        return None

    def table(self, table_id: str) -> dict | None:
        """Return a single table by its id."""
        tables = self._load_tables()
        for t in tables.get("tables", []):
            if t["id"] == table_id:
                return t
        return None

    def tables(self, level: str | None = None) -> list[dict]:
        """Return all tables, optionally filtered by level."""
        tables = self._load_tables()
        result = []
        for t in tables.get("tables", []):
            if level is None or t.get("level") == level:
                result.append(t)
        return result

    # ---------- Internal helpers ----------

    def _find_lesson_by_topic(self, topic_id: str) -> dict | None:
        """Find the lesson that contains the given topic_id."""
        for lvl in self._load_courses().get("levels", []):
            data = self._load_level(lvl["code"])
            if data:
                for lesson in data.get("lessons", []):
                    if topic_id in lesson.get("topics", []):
                        lesson_copy = dict(lesson)
                        lesson_copy["level"] = lvl["code"]
                        return lesson_copy
        return None


def get_grammar_engine() -> GrammarEngine:
    """Factory function for the plugin."""
    return GermanGrammarEngine()