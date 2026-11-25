"""French Grammar Engine: loads JSON data, generates exercises, validates answers."""
from __future__ import annotations

from stamina.i18n import t as _t

import json
import random
from collections import OrderedDict
from pathlib import Path

from stamina.languages.core.base import (
    GrammarEngine, GrammarTopic, Exercise, ValidationResult
)


class FrenchGrammarEngine(GrammarEngine):
    """Grammar engine for French: loads courses/tables/lessons from JSON."""

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder or Path(__file__).parent / "grammar"
        self._courses: dict | None = None
        self._tables: dict | None = None
        self._bridges: dict[str, dict] | None = None
        self._lessons_cache: OrderedDict[str, dict] = OrderedDict()
        self._summaries_cache: dict[str, list[dict]] = {}
        self._lesson_lru: OrderedDict[str, dict] = OrderedDict()
        self._levels_cache: list[dict] | None = None
        self._level_lru_size = 2
        self._lesson_lru_size = 8

    # ---------- Lazy loading helpers ----------

    def _load_courses(self) -> dict:
        if self._courses is None:
            path = self.folder / "courses.json"
            try:
                self._courses = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._courses = {"version": 1, "language": "fr", "levels": [], "tables_file": "tables.json"}
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

    def _load_bridges(self) -> dict[str, dict]:
        """Load bridges.json once: мостик RU/UA → FR для каждого урока."""
        if self._bridges is None:
            path = self.folder / "bridges.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            bridges = data.get("bridges", {}) if isinstance(data, dict) else {}
            self._bridges = bridges if isinstance(bridges, dict) else {}
        return self._bridges

    def _load_level(self, cefr: str) -> dict | None:
        """Load a single level file (a1.json, b2.json, etc.)."""
        if cefr in self._lessons_cache:
            self._lessons_cache.move_to_end(cefr)
            return self._lessons_cache[cefr]
        courses = self._load_courses()
        level_info = next((lvl for lvl in courses.get("levels", []) if lvl["code"] == cefr), None)
        if not level_info:
            return None
        path = self.folder / level_info["file"]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        self._lessons_cache[cefr] = data
        self._lessons_cache.move_to_end(cefr)
        while len(self._lessons_cache) > self._level_lru_size:
            self._lessons_cache.popitem(last=False)
        self._summaries_cache[cefr] = [
            self._summarize(lesson, cefr) for lesson in data.get("lessons", [])
        ]
        return data

    def _summarize(self, lesson: dict, cefr: str) -> dict:
        """Карточка списка: без theory/drills, чтобы список не тащил весь уровень в виджеты."""
        return {
            "id": lesson.get("id"),
            "order": lesson.get("order"),
            "title": lesson.get("title"),
            "subtitle": lesson.get("subtitle", ""),
            "topics": list(lesson.get("topics") or []),
            "prereq": list(lesson.get("prereq") or []),
            "minutes": lesson.get("minutes", 10),
            "level": lesson.get("level") or cefr,
            "drill_count": len(lesson.get("drills") or []),
        }

    def _cefr_of(self, lesson_id: str) -> str | None:
        """'a1-01-…' → 'A1'. Неизвестный префикс не сканирует все уровни."""
        prefix = (lesson_id or "").split("-", 1)[0].upper()
        known = {lvl["code"] for lvl in self._load_courses().get("levels", [])}
        return prefix if prefix in known else None

    def _remember_lesson(self, lesson_id: str, lesson: dict) -> dict:
        self._lesson_lru[lesson_id] = lesson
        self._lesson_lru.move_to_end(lesson_id)
        while len(self._lesson_lru) > self._lesson_lru_size:
            self._lesson_lru.popitem(last=False)
        return lesson

    def lesson_summaries(self, cefr: str) -> list[dict]:
        """Краткий список уроков уровня: при первом заходе читается только его файл."""
        if cefr in self._summaries_cache:
            return list(self._summaries_cache[cefr])
        data = self._load_level(cefr)
        if not data:
            return []
        return list(self._summaries_cache.get(cefr) or [])

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
        lesson = self._find_lesson_by_topic(topic_id)
        if not lesson:
            return Exercise(
                id=f"{topic_id}_{seed}",
                topic_id=topic_id,
                type="choice",
                prompt=_t("Упражнение для {0} не найдено").format(topic_id),
                expected_answer=[""],
                options=[""]
            )

        drills = lesson.get("drills", [])
        if not drills:
            return Exercise(
                id=f"{topic_id}_{seed}",
                topic_id=topic_id,
                type="choice",
                prompt=_t("Нет упражнений для этой темы"),
                expected_answer=[""],
                options=[""]
            )

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
        """Validate answer with tolerance for case, spaces, accents (é=ee, à=a, etc.)."""
        expected = exercise.expected_answer
        if isinstance(expected, str):
            expected = [expected]

        def normalize(s: str) -> str:
            s = s.strip().lower()
            s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
            s = s.replace("à", "a").replace("â", "a").replace("ä", "a")
            s = s.replace("ô", "o").replace("ö", "o")
            s = s.replace("î", "i").replace("ï", "i")
            s = s.replace("ù", "u").replace("û", "u").replace("ü", "u")
            s = s.replace("ç", "c")
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
            return _t("Пояснение для {0} не найдено.").format(topic_id)

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
                    parts.append(_t("Таблица: {0}").format(table.get('title', '')))
            elif kind == "example":
                parts.append(_t("Пример: {0} — {1}").format(block.get('fr', ''), block.get('ru', '')))
        return "\n\n".join(parts) if parts else _t("Пояснение отсутствует.")

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
        """Return a single lesson by its id. Читает только файл своего уровня."""
        if not lesson_id:
            return None
        cached = self._lesson_lru.get(lesson_id)
        if cached is not None:
            self._lesson_lru.move_to_end(lesson_id)
            return cached
        cefr = self._cefr_of(lesson_id)
        if not cefr:
            return None
        data = self._load_level(cefr)
        if not data:
            return None
        for item in data.get("lessons", []):
            if item.get("id") == lesson_id:
                lesson_copy = dict(item)
                lesson_copy["level"] = cefr
                return self._remember_lesson(lesson_id, lesson_copy)
        return None

    def bridge(self, lesson_id: str) -> dict:
        """Мостик RU/UA → FR для урока: can_do / bridge / trap (пусто, если нет данных)."""
        return self._load_bridges().get(lesson_id, {})

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
        hinted = self._cefr_of(topic_id)
        codes = [hinted] if hinted else [lvl["code"] for lvl in self._load_courses().get("levels", [])]
        for code in codes:
            data = self._load_level(code)
            if not data:
                continue
            for lesson in data.get("lessons", []):
                if topic_id in lesson.get("topics", []) or lesson.get("id") == topic_id:
                    lesson_copy = dict(lesson)
                    lesson_copy["level"] = code
                    return lesson_copy
        return None


def get_grammar_engine() -> GrammarEngine:
    """Factory function for the plugin."""
    return FrenchGrammarEngine()