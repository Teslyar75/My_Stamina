"""Tests for German grammar: data integrity, engine, validation, UI smoke."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from stamina.languages.plugins.de.grammar_engine import GermanGrammarEngine
from stamina.languages.core.progress import LanguageProgress


class TestGermanGrammarData:
    """Tests for JSON data files integrity."""

    @pytest.fixture(scope="class")
    def engine(self):
        return GermanGrammarEngine()

    def test_courses_json_exists(self, engine):
        courses = engine._load_courses()
        assert courses["version"] == 1
        assert courses["language"] == "de"
        levels = courses["levels"]
        assert len(levels) == 6
        codes = [lvl["code"] for lvl in levels]
        assert codes == ["A1", "A2", "B1", "B2", "C1", "C2"]

    def test_tables_json_exists(self, engine):
        tables = engine._load_tables()
        assert tables["version"] == 1
        assert len(tables["tables"]) >= 44  # минимум 44 таблицы из ТЗ
        table_ids = [t["id"] for t in tables["tables"]]
        assert len(table_ids) == len(set(table_ids))  # уникальные id

    def test_each_level_file_matches_manifest(self, engine):
        courses = engine._load_courses()
        for lvl in courses["levels"]:
            data = engine._load_level(lvl["code"])
            assert data is not None, f"Level file {lvl['file']} not loaded"
            assert data["level"] == lvl["code"]
            assert len(data["lessons"]) == lvl["lessons"], (
                f"Level {lvl['code']}: manifest says {lvl['lessons']} lessons, "
                f"file has {len(data['lessons'])}"
            )

    def test_lesson_order_and_prereq(self, engine):
        """Порядок уроков 1..N без пропусков, prereq ссылается на существующие."""
        all_lesson_ids = set()
        for lvl in engine._load_courses()["levels"]:
            data = engine._load_level(lvl["code"])
            orders = [lesson["order"] for lesson in data["lessons"]]
            assert orders == list(range(1, len(orders) + 1)), f"Level {lvl['code']}: order not 1..N"
            for lesson in data["lessons"]:
                assert lesson["id"].startswith(lvl["code"].lower()), f"Lesson {lesson['id']} doesn't match level"
                all_lesson_ids.add(lesson["id"])
                for prereq in lesson.get("prereq", []):
                    assert prereq in all_lesson_ids or any(
                        p["id"] == prereq for lv in engine._load_courses()["levels"]
                        for p in engine._load_level(lv["code"])["lessons"]
                    ), f"Prereq {prereq} not found for {lesson['id']}"

    def test_table_refs_exist(self, engine):
        """Каждый ref таблицы в уроках существует в tables.json."""
        tables_data = engine._load_tables()
        table_ids = {t["id"] for t in tables_data["tables"]}
        for lvl in engine._load_courses()["levels"]:
            data = engine._load_level(lvl["code"])
            for lesson in data["lessons"]:
                for block in lesson.get("theory", []):
                    if block.get("kind") == "table":
                        ref = block.get("ref")
                        assert ref in table_ids, f"Table ref {ref} not found in tables.json"

    def test_table_structure(self, engine):
        """У каждой таблицы len(row) == len(columns), нет пустых ячеек."""
        tables_data = engine._load_tables()
        for table in tables_data["tables"]:
            cols = table["columns"]
            for row in table["rows"]:
                assert len(row) == len(cols), f"Table {table['id']}: row len {len(row)} != cols {len(cols)}"
                for cell in row:
                    assert cell != "", f"Table {table['id']}: empty cell"

    def test_hardcoded_facts(self, engine):
        """Точечные проверки фактов из раздела 6 ТЗ."""
        tables = engine._load_tables()
        table_dict = {t["id"]: t for t in tables["tables"]}

        # Определённый артикль
        art = table_dict["articles_definite"]
        assert art["rows"][0] == ["Nominativ", "der", "die", "das", "die"]
        assert art["rows"][1] == ["Akkusativ", "den", "die", "das", "die"]
        assert art["rows"][2] == ["Dativ", "dem", "der", "dem", "den + n"]
        assert art["rows"][3] == ["Genitiv", "des + s", "der", "des + s", "der"]

        # sein, haben, werden в Präsens
        shw = table_dict["sein_haben_werden"]
        sein_row = [r for r in shw["rows"] if r[0] == "ich"][0]
        assert sein_row[1] == "bin"
        haben_row = [r for r in shw["rows"] if r[0] == "ich"][0]
        assert haben_row[2] == "habe"
        werden_row = [r for r in shw["rows"] if r[0] == "ich"][0]
        assert werden_row[3] == "werde"

        # praesens_weak для machen
        pw = table_dict["praesens_weak"]
        machen_row = [r for r in pw["rows"] if r[0] == "ich"][0]
        # columns: Person, machen, lernen, spielen, arbeiten, Endung
        assert machen_row[1] == "mache"

        # adj_decl_definite: 16 клеток, -e ровно в 5 (слабое склонение: -e в Nom Sg всех родов, Akk Fem/Neut)
        adj = table_dict["adj_decl_definite"]
        # Прилагательное — второе слово в ячейке (после артикля)
        def adj_ends_with_e(cell: str) -> bool:
            parts = cell.split()
            if len(parts) >= 2:
                adj = parts[1]
                return adj.endswith("e") and not adj.endswith("en")
            return False
        e_count = sum(1 for row in adj["rows"] for cell in row[1:] if adj_ends_with_e(cell))
        assert e_count == 5, f"adj_decl_definite: -e count = {e_count}, expected 5"

        # wechselpraepositionen: 9 предлогов
        wp = table_dict["wechselpraepositionen"]
        preps = {row[0] for row in wp["rows"]}
        expected = {"an", "auf", "hinter", "in", "neben", "über", "unter", "vor", "zwischen"}
        assert preps == expected

        # praep_akkusativ содержит DOGFU
        pa = table_dict["praep_akkusativ"]
        prep_names = {row[0] for row in pa["rows"]}
        assert {"durch", "für", "gegen", "ohne", "um"}.issubset(prep_names)

    def test_drills_count_and_types(self, engine):
        """У каждого урока >= 10 упражнений, типы из разрешённого списка."""
        allowed_types = {"choice", "fill", "declension", "conjugation", "reorder",
                         "transform", "match", "identify"}
        for lvl in engine._load_courses()["levels"]:
            data = engine._load_level(lvl["code"])
            for lesson in data["lessons"]:
                drills = lesson.get("drills", [])
                assert len(drills) >= 10, f"Lesson {lesson['id']}: only {len(drills)} drills"
                for d in drills:
                    assert d["type"] in allowed_types, f"Lesson {lesson['id']}: bad type {d['type']}"
                    assert d["id"]
                    assert d["prompt"]
                    assert d["answer"]
                    assert d["why"]
                    assert isinstance(d["answer"], list), f"Lesson {lesson['id']}: answer not list"
                    if d["type"] == "choice":
                        opts = d.get("options", [])
                        assert 3 <= len(opts) <= 4, f"Lesson {lesson['id']}: choice options count"
                        assert len(opts) == len(set(opts)), f"Lesson {lesson['id']}: duplicate options"
                        assert d["answer"][0] in opts, f"Lesson {lesson['id']}: answer not in options"

    def test_no_placeholder_strings(self, engine):
        """Нет строк answer, opt1, TODO, lorem, xxx в данных."""
        forbidden = {"answer", "opt1", "opt2", "opt3", "opt4", "TODO", "lorem", "xxx", "placeholder"}
        for lvl in engine._load_courses()["levels"]:
            data = engine._load_level(lvl["code"])
            for lesson in data["lessons"]:
                for d in lesson.get("drills", []):
                    for field in ["prompt", "why"]:
                        val = d.get(field, "").lower()
                        for f in forbidden:
                            assert f not in val, f"Lesson {lesson['id']}: forbidden '{f}' in {field}"


class TestGermanGrammarEngine:
    """Tests for GermanGrammarEngine behavior."""

    @pytest.fixture
    def engine(self):
        return GermanGrammarEngine()

    def test_lazy_loading(self, engine):
        """Уровень читается при первом обращении."""
        assert engine._lessons_cache == {}
        lessons_a1 = engine.lessons("A1")
        assert "A1" in engine._lessons_cache
        assert len(lessons_a1) == 18

    def test_lesson_loads_only_own_level(self, engine, monkeypatch):
        """Поиск урока C2 не читает файлы A1–C1."""
        reads: list[str] = []
        orig = Path.read_text

        def wrapped(self, *args, **kwargs):
            reads.append(self.name)
            return orig(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", wrapped)
        lesson = engine.lesson("c2-01-nuancen")
        assert lesson is not None
        assert "c2.json" in reads
        for other in ("a1.json", "a2.json", "b1.json", "b2.json", "c1.json"):
            assert other not in reads

    def test_lesson_summaries_omit_theory(self, engine):
        cards = engine.lesson_summaries("A1")
        assert len(cards) == 18
        assert "theory" not in cards[0]
        assert "drills" not in cards[0]
        assert cards[0]["drill_count"] >= 1
        assert cards[0]["id"]

    def test_generate_exercise_deterministic(self, engine):
        """Один seed = один результат, не трогает глобальный random."""
        ex1 = engine.generate_exercise("a1-06-genus", "easy", 42)
        ex2 = engine.generate_exercise("a1-06-genus", "easy", 42)
        assert ex1.id == ex2.id
        assert ex1.prompt == ex2.prompt
        assert ex1.expected_answer == ex2.expected_answer
        assert ex1.options == ex2.options

    def test_validate_answer_tolerance(self, engine):
        """Валидация терпима: пробелы, регистр, ae/oe/ue, ss, точка."""
        ex = engine.generate_exercise("a1-06-genus", "easy", 42)
        # Правильный ответ
        assert engine.validate_answer(ex, ex.expected_answer[0]).correct
        # Пробелы
        assert engine.validate_answer(ex, " " + ex.expected_answer[0] + " ").correct
        # Регистр
        assert engine.validate_answer(ex, ex.expected_answer[0].upper()).correct
        # ae/oe/ue
        ans = ex.expected_answer[0].replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        assert engine.validate_answer(ex, ans).correct
        # ss вместо ß
        ans = ex.expected_answer[0].replace("ß", "ss")
        assert engine.validate_answer(ex, ans).correct
        # Точка в конце
        assert engine.validate_answer(ex, ex.expected_answer[0] + ".").correct
        # Неправильный ответ
        wrong = "der" if ex.expected_answer[0] != "der" else "die"
        assert not engine.validate_answer(ex, wrong).correct

    def test_get_topics_by_level(self, engine):
        """get_topics возвращает только темы до указанного уровня."""
        a1_topics = engine.get_topics("A1")
        b1_topics = engine.get_topics("B1")
        assert len(a1_topics) < len(b1_topics)
        for t in a1_topics:
            assert t.cefr_level == "A1"
        for t in b1_topics:
            assert t.cefr_level in ("A1", "A2", "B1")

    def test_get_explanation_not_empty(self, engine):
        """get_explanation непуст для каждого topic_id."""
        for lvl in engine._load_courses()["levels"]:
            data = engine._load_level(lvl["code"])
            for lesson in data["lessons"]:
                for topic_id in lesson.get("topics", []):
                    expl = engine.get_explanation(topic_id, "ru")
                    assert expl and len(expl) > 10, f"Empty explanation for {topic_id}"

    def test_missing_data_handling(self, engine):
        """Отсутствующий файл/битый JSON/неизвестный topic -> пустой результат."""
        # Несуществующий урок
        lesson = engine.lesson("nonexistent")
        assert lesson is None
        # Несуществующая таблица
        table = engine.table("nonexistent")
        assert table is None
        # Генерация упражнения для неизвестного топика
        ex = engine.generate_exercise("unknown_topic", "easy", 1)
        assert ex.topic_id == "unknown_topic"
        # Валидация не падает
        result = engine.validate_answer(ex, "anything")
        assert isinstance(result.correct, bool)


class TestGrammarProgress:
    """Tests for grammar progress tracking."""

    def test_record_grammar_and_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "de")

            # 7/10 = 0.7 -> не пройден
            progress.record_grammar("a1-06-genus", 7, 10)
            assert not progress.grammar_done("a1-06-genus")

            # 9/10 = 0.9 -> пройден
            progress.record_grammar("a1-06-genus", 9, 10)
            assert progress.grammar_done("a1-06-genus")

            # Проверка сохранения в файл
            data = json.loads((pilot_dir / "lang_de.json").read_text(encoding="utf-8"))
            assert "grammar" in data
            assert data["grammar"]["a1-06-genus"]["done"] is True
            assert data["grammar"]["a1-06-genus"]["score"] == 0.9

    def test_grammar_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "de")
            lesson_ids = ["a1-01-x", "a1-02-y", "a1-03-z"]
            progress.record_grammar("a1-01-x", 10, 10)
            progress.record_grammar("a1-02-y", 5, 10)
            done, total = progress.grammar_summary("A1", lesson_ids)
            assert done == 1
            assert total == 3

    def test_xp_awarded_once_per_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot_dir = Path(tmp)
            progress = LanguageProgress(pilot_dir, "de")
            progress.record_grammar("test-lesson", 10, 10)  # +10 XP
            progress.record_grammar("test-lesson", 10, 10)  # повторно - XP не должно добавиться
            assert progress.data["xp"]["total"] == 10


class TestGrammarUISmoke:
    """Дымовые проверки страницы грамматики (нужен дисплей)."""

    @pytest.fixture
    def board(self, tmp_path):
        import tkinter as tk

        from stamina import pilots
        from stamina.languages.grammar_page import build_grammar_page
        from stamina.languages.plugins.de import GermanPlugin

        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        root.geometry("900x360+0+0")
        root.update_idletasks()

        pilots.reset_root(tmp_path)
        pilot = pilots.create("Smoke", accent="amber")
        pilots.activate(pilot["id"])
        progress = LanguageProgress(pilots.pilot_dir(pilot["id"]), "de")
        page = build_grammar_page(root, GermanPlugin(), progress, None)
        root.update()

        def pump() -> None:
            page._flush_pending()
            root.update()
            page._flush_pending()
            root.update()

        try:
            yield page, progress, pump
        finally:
            page.destroy()
            root.destroy()
            pilots.reset_root(None)

    def test_page_builds_with_six_levels(self, board):
        page, progress, pump = board
        assert page.frame.winfo_exists()
        assert [code.upper() for code in page.catalog.levels] == ["A1", "A2", "B1", "B2", "C1", "C2"]
        pump()
        assert set(page.engine._lessons_cache) <= {"A1"}
        assert len(page.engine.lessons("A1")) == 18

    def test_lesson_list_opens_and_flushes_in_chunks(self, board):
        page, progress, pump = board
        page._show_lessons("A1")
        pump()
        assert "list" not in page.spread._jobs
        assert len(page.spread._rows) == 18
        assert page.stage in {"lesson", "list", "lessons"}

    def test_lesson_intro_explains_goal_and_traps(self, board):
        page, progress, pump = board
        page._show_lessons("A1")
        pump()
        page._open_lesson(page.level_lessons[0])
        pump()
        import tkinter as tk

        def walk(widget, acc):
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    acc.append(str(child.cget("text")))
                walk(child, acc)

        labels = []
        walk(page.content, labels)
        texts = " ".join(labels)
        assert "ЧТО ВЫ ОСВОИТЕ" in texts
        assert "МОСТИК RU/UA → НЕМЕЦКИЙ" in texts
        assert "ЛОВУШКА" in texts

    def test_correct_answer_is_marked_correct(self, board):
        page, progress, pump = board
        page._show_lessons("A1")
        pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        pump()
        drill = page._current_drill()
        expected = page._expected(drill)[0]
        if drill["type"] in ("choice", "identify"):
            page._choose(expected)
        else:
            page.drill_answer_var.set(expected)
            page._check_answer()
        pump()
        assert page.checked and page.last_ok
        assert page.answers[drill["id"]] is True

    def test_wrong_answer_is_marked_wrong(self, board):
        page, progress, pump = board
        page._show_lessons("A1")
        pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        pump()
        drill = page._current_drill()
        expected = page._expected(drill)[0]
        if drill["type"] in ("choice", "identify"):
            options = drill.get("options") or [expected]
            page._choose(next((o for o in options if o != expected), "—"))
        else:
            page.drill_answer_var.set("xxx")
            page._check_answer()
        pump()
        assert page.checked and not page.last_ok

    def test_next_drill_moves_forward(self, board):
        page, progress, pump = board
        page._show_lessons("A1")
        pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        pump()
        first = page._current_drill()["id"]
        expected = page._expected(page._current_drill())[0]
        drill = page._current_drill()
        if drill["type"] in ("choice", "identify"):
            page._choose(expected, drill)
        else:
            page.drill_answer_var.set(expected)
            page._check_answer(drill=drill)
        pump()
        assert page._current_drill()["id"] != first

    def test_tables_mode_renders_single_table(self, board):
        page, progress, pump = board
        page._set_mode("tables")
        pump()
        assert page.stage == "table"
        assert page.tables_container is not None
        assert page.tables_container.winfo_exists()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])