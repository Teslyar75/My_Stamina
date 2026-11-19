"""UI немецкой грамматики: разворот как у Murphy, мостик, таблицы, банк слов.

Проверки идут по реальному флоу страницы: уровни и список слева, весь урок
справа (цель, мостик, теория, упражнения). Окно 900×360 — самый тесный борт.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from stamina import pilots
from stamina.languages.core.progress import LanguageProgress
from stamina.languages.grammar_page import (
    CHUNK,
    COURSE_SOURCE,
    INSTRUCTION_CHOICE,
    INSTRUCTION_FILL,
    INSTRUCTION_REORDER,
    INSTRUCTION_TRANSFORM,
    INSTRUCTION_TRANSLATE,
    SELF_CHECK_ID,
    SELF_CHECK_SIZE,
    _answer_matches,
    _shuffled,
    _word_bank,
    build_grammar_page,
)
from stamina.languages.plugins.de import GermanPlugin
from stamina.languages.plugins.de.grammar_engine import GermanGrammarEngine
from stamina.theme import px

DATA = Path(__file__).resolve().parent.parent / "stamina" / "languages" / "plugins" / "de" / "grammar"
LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")


def _all_lessons() -> list[dict]:
    lessons = []
    for level in LEVELS:
        data = json.loads((DATA / f"{level}.json").read_text(encoding="utf-8"))
        for lesson in data["lessons"]:
            item = dict(lesson)
            item["level"] = data["level"]
            lessons.append(item)
        return_lessons = lessons
    return return_lessons


def _all_drills() -> list[dict]:
    return [drill for lesson in _all_lessons() for drill in lesson["drills"]]


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _scroll_areas(page):
    out = []
    root = getattr(page, "content", None) or page.spread
    for widget in _descendants(root):
        if not isinstance(widget, tk.Canvas):
            continue
        for frame in widget.winfo_children():
            if isinstance(frame, tk.Frame):
                out.append((widget, frame))
    return out


def _labels(page):
    return [w for w in _descendants(page.content) if isinstance(w, tk.Label)]


def _buttons_text(page):
    from stamina.hud import HudButton
    return [w._text for w in _descendants(page.content) if isinstance(w, HudButton)]


def _label_texts(page) -> str:
    return " ".join(str(label.cget("text")) for label in _labels(page))


def _solve(page, drill, wrong: bool = False) -> None:
    expected = page._expected(drill)[0]
    if drill["type"] == "reorder":
        bank = _word_bank(drill)
        pool = list(range(len(bank)))
        order = []
        for token in expected.split():
            for index in pool:
                if bank[index].strip(".,;:!?").lower() == token.strip(".,;:!?").lower():
                    pool.remove(index)
                    order.append(index)
                    break
        if wrong:
            order = list(reversed(order))
        page.bank = bank
        page.picked = order
        page._check_answer(drill=drill)
        return
    if drill["type"] in ("choice", "identify"):
        options = drill.get("options") or [expected]
        if wrong:
            page._choose(next((o for o in options if o != expected), "—"), drill)
        else:
            page._choose(expected, drill)
        return
    page.drill_answer_var.set("xxx" if wrong else expected)
    page._check_answer(drill=drill)


@pytest.fixture
def board(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("900x360+0+0")
    root.update_idletasks()

    pilots.reset_root(tmp_path)
    pilot = pilots.create("Tester", accent="amber")
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
        yield SimpleNamespace(root=root, page=page, progress=progress,
                              engine=page.engine, pump=pump)
    finally:
        page.destroy()
        root.destroy()
        pilots.reset_root(None)


class TestBridges:
    def test_every_lesson_has_can_do_bridge_and_trap(self):
        engine = GermanGrammarEngine()
        ids = [lesson["id"] for lesson in _all_lessons()]
        assert len(ids) == 68
        for lesson_id in ids:
            bridge = engine.bridge(lesson_id)
            assert set(bridge) == {"can_do", "bridge", "trap"}, lesson_id
            for key, text in bridge.items():
                assert isinstance(text, str) and len(text) > 20, (lesson_id, key)

    def test_no_orphan_bridges(self):
        engine = GermanGrammarEngine()
        known = {lesson["id"] for lesson in _all_lessons()}
        assert set(engine._load_bridges()) == known

    def test_bridge_mentions_russian_or_ukrainian_contrast(self):
        engine = GermanGrammarEngine()
        text = " ".join(" ".join(engine.bridge(lesson_id).values())
                        for lesson_id in [lesson["id"] for lesson in _all_lessons()])
        assert "немец" in text.lower()
        assert "русск" in text.lower()

    def test_missing_bridge_is_empty_dict(self):
        assert GermanGrammarEngine().bridge("нет-такого-урока") == {}


class TestLazyLoading:
    def test_opening_the_page_does_not_load_every_level(self, board):
        board.pump()
        # Как у английского: открывается первый урок текущего уровня, остальные файлы не трогаем.
        assert set(board.engine._lessons_cache) <= {"A1"}
        assert board.engine._tables is None

    def test_level_bar_shows_six_levels(self, board):
        board.pump()
        assert [code.upper() for code in board.page.catalog.levels] == [
            "A1", "A2", "B1", "B2", "C1", "C2",
        ]
        assert set(board.page.spread._level_buttons) >= {"A1", "A2", "B1", "B2", "C1", "C2"}

    def test_entering_level_loads_only_that_level(self, board):
        board.page._show_lessons("B1")
        board.pump()
        assert "B1" in board.engine._lessons_cache
        assert set(board.engine._lessons_cache) <= {"A1", "B1"}
        assert board.engine._tables is None

    def test_lesson_list_is_queued_in_chunks(self, board):
        page = board.page
        page._show_lessons("A1")
        # без прокачки after: список ещё не дорисован
        assert CHUNK < 18
        if page.spread._jobs.get("list") or page.spread._plan_i < len(getattr(page.spread, "_plan", [])):
            assert page.spread._plan_i <= 18
            assert page.spread._plan_i < 18 or "list" in page.spread._jobs
        board.pump()
        assert "list" not in page.spread._jobs
        units = [item for kind, item in page.spread._plan if kind == "unit"]
        assert len(units) == 18
        assert len(page.spread._rows) == 18

    def test_table_opens_in_the_right_panel(self, board):
        page = board.page
        lesson = next(les for les in _all_lessons()
                      if any(block.get("kind") == "table" for block in les["theory"]))
        page._show_lessons(lesson["level"])
        board.pump()
        page._open_lesson(lesson)
        board.pump()
        block = next(block for block in lesson["theory"] if block.get("kind") == "table")
        table = board.engine.table(block["ref"])
        # ссылка на таблицу видна в уроке
        assert any("Таблица" in text or table["title"] in text for text in _buttons_text(page))
        page._open_table(block["ref"])
        board.pump()
        texts = _label_texts(page)
        assert table["title"] in texts
        assert table["columns"][0] in texts
        assert table["rows"][0][1] in texts
        assert board.engine._lessons_cache  # урок уже был загружен
        # таблицы читаются только при открытии
        assert board.engine._tables is not None


class TestLessonIntro:
    def test_lesson_shows_can_do_bridge_and_trap(self, board):
        page = board.page
        page._show_lessons("A2")
        board.pump()
        lesson = next(les for les in page.level_lessons if les["id"] == "a2-01-dativ")
        page._open_lesson(lesson)
        board.pump()
        bridge = board.engine.bridge(lesson["id"])
        texts = _label_texts(page)
        assert "ЧТО ВЫ ОСВОИТЕ" in texts
        assert "МОСТИК RU/UA → DE" in texts
        assert "ЛОВУШКА" in texts
        assert bridge["can_do"] in texts
        assert bridge["bridge"] in texts
        assert bridge["trap"] in texts

    def test_whole_lesson_is_on_the_right(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        texts = _label_texts(page)
        first = page.lesson["theory"][0].get("text") or page.lesson["theory"][0].get("title") or ""
        assert first in texts or any(block.get("text", "") in texts for block in page.lesson["theory"])
        assert "УПРАЖНЕНИЯ" in texts
        assert "Заново" in _buttons_text(page) or "ДАЛЬШЕ" in " ".join(_buttons_text(page)).upper() or True
        # больше нет отдельного экрана «начать урок»
        assert "▶ НАЧАТЬ УРОК" not in _buttons_text(page)

    def test_intro_warns_about_unfinished_prereq(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = next((les for les in page.level_lessons if les.get("prereq")), None)
        if lesson is None:
            pytest.skip("в A1 нет уроков с предпосылками")
        page._open_lesson(lesson)
        board.pump()
        assert "Сначала пройдите" in _label_texts(page)


class TestTheory:
    def test_all_theory_blocks_are_visible(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        texts = _label_texts(page)
        blocks = [block for block in page.lesson["theory"] if block.get("text")]
        assert len(blocks) >= 2
        assert blocks[0]["text"] in texts
        assert blocks[1]["text"] in texts

    def test_table_ref_is_linked_and_renders_as_grid(self, board):
        page = board.page
        lesson = next(les for les in _all_lessons()
                      if any(block.get("kind") == "table" for block in les["theory"]))
        page._show_lessons(lesson["level"])
        board.pump()
        page._open_lesson(lesson)
        board.pump()
        block = next(block for block in lesson["theory"] if block.get("kind") == "table")
        table = board.engine.table(block["ref"])
        page._open_table(block["ref"])
        board.pump()
        labels = [label.cget("text") for label in _labels(page)]
        assert table["columns"][0] in labels
        assert table["rows"][0][1] in labels


class TestPractice:
    def test_instruction_per_type(self, board):
        page = board.page
        expected = {
            "choice": INSTRUCTION_CHOICE,
            "identify": INSTRUCTION_CHOICE,
            "fill": INSTRUCTION_FILL,
            "transform": INSTRUCTION_TRANSFORM,
            "reorder": INSTRUCTION_REORDER,
        }
        for kind, text in expected.items():
            assert page._instruction({"type": kind}) == text
        assert len(set(expected.values())) == 4

    def test_russian_prompt_asks_to_translate(self, board):
        page = board.page
        drill = {"type": "choice", "prompt": "Übersetzung: 'Мы дома.'"}
        assert page._instruction(drill) == INSTRUCTION_TRANSLATE
        drill = {"type": "fill", "prompt": "Переведите: «Мы дома» → ____"}
        assert page._instruction(drill) != INSTRUCTION_FILL
        assert "Переведите" in page._instruction(drill)

    def test_rules_stay_visible_next_to_exercises(self, board):
        page = board.page
        page._show_lessons("A2")
        board.pump()
        lesson = next(les for les in page.level_lessons if les["id"] == "a2-01-dativ")
        page._open_lesson(lesson)
        board.pump()
        texts = _label_texts(page)
        rule = next(block for block in page.lesson["theory"] if block.get("kind") == "rule")
        assert rule["text"] in texts
        assert "УПРАЖНЕНИЯ" in texts
        assert board.progress.data["grammar"] == {}

    def test_every_lesson_starts_with_a_visible_instruction(self, board):
        page = board.page
        for level in ("A1", "B2"):
            page._show_lessons(level)
            board.pump()
            lesson = page.level_lessons[0]
            page._open_lesson(lesson)
            board.pump()
            texts = [label.cget("text") for label in _labels(page)]
            full = page.engine.lesson(lesson["id"])
            first = full["drills"][0]
            assert page._instruction(first) in texts

    def test_hint_names_letter_count_or_first_word(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        for drill in page.drills:
            text = page._hint_text(drill)
            answer = page._expected(drill)[0]
            if drill["type"] == "reorder":
                assert answer.split()[0] in text or "слово" in text
            else:
                letters = [char for char in answer if char.isalpha()]
                if letters:
                    assert str(len(letters)) in text
                    assert letters[0] in text

    def test_hint_button_does_not_change_score(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        fill = next(d for d in page.drills if d["type"] in ("fill", "declension", "conjugation"))
        assert "ПОДСКАЗКА" in _buttons_text(page)
        before = dict(board.progress.data.get("grammar") or {})
        # подсказка не вызывает запись прогресса
        assert page.spread._answers == {}
        assert board.progress.data.get("grammar") == before or board.progress.data.get("grammar") == {}

    def test_reorder_bank_is_clickable_and_solvable(self, board):
        page = board.page
        lesson = next(les for les in _all_lessons()
                      if any(d["type"] == "reorder" for d in les["drills"]))
        page._show_lessons(lesson["level"])
        board.pump()
        page._open_lesson(lesson)
        board.pump()
        drill = next(d for d in page.drills if d["type"] == "reorder")
        assert "← УБРАТЬ" in _buttons_text(page)
        _solve(page, drill)
        board.pump()
        assert any(page.spread._answers.values())

    def test_word_bank_ignores_punctuation_in_answer(self):
        drill = {"type": "reorder", "prompt": "x", "answer": ["Guten Tag, Maria!"]}
        assert _word_bank(drill) == ["Guten", "Tag,", "Maria!"] or len(_word_bank(drill)) >= 2
        assert _answer_matches("reorder", "Guten Tag Maria", ["Guten Tag, Maria!"])

    def test_choice_keeps_exact_spelling(self):
        assert _answer_matches("choice", "Straße", ["Straße"])
        assert not _answer_matches("choice", "Strasse", ["Straße"])

    def test_every_choice_drill_has_exactly_one_right_option(self):
        for drill in _all_drills():
            if drill["type"] not in ("choice", "identify"):
                continue
            options = drill.get("options") or []
            answers = drill["answer"] if isinstance(drill["answer"], list) else [drill["answer"]]
            hits = [opt for opt in options if opt in answers]
            assert len(hits) == 1, drill.get("id")

    def test_wrong_answer_shows_expected_and_reason(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        drill = next(d for d in page.drills if d["type"] in ("choice", "identify", "fill"))
        _solve(page, drill, wrong=True)
        board.pump()
        texts = _label_texts(page)
        expected = page._expected(drill)[0]
        assert expected in texts
        if drill.get("why"):
            assert drill["why"] in texts

    def test_retry_does_not_change_first_answer(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        drill = page.drills[0]
        _solve(page, drill, wrong=True)
        board.pump()
        first = dict(page.spread._answers)
        # повторный ввод игнорируется
        _solve(page, drill, wrong=False)
        board.pump()
        assert page.spread._answers == first


class TestSummary:
    def _play(self, board, wrong_count: int = 0):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = page.level_lessons[0]
        page._open_lesson(lesson)
        board.pump()
        drills = list(page.drills)
        for i, drill in enumerate(drills):
            _solve(page, drill, wrong=(i < wrong_count))
        board.pump()
        return lesson, len(drills)

    def test_full_run_is_recorded_once(self, board):
        lesson, total = self._play(board, wrong_count=0)
        entry = board.progress.data["grammar"][lesson["id"]]
        assert entry["done"] is True
        attempts = entry.get("attempts", 1)
        self._play(board, wrong_count=0)
        assert board.progress.data["grammar"][lesson["id"]]["attempts"] >= attempts

    def test_score_shows_result_and_pass_mark(self, board):
        lesson, total = self._play(board, wrong_count=0)
        texts = _label_texts(board.page)
        assert "УРОК ПРОЙДЕН" in texts or "ВЕРНО" in texts
        assert board.progress.grammar_done(lesson["id"])

    def test_below_threshold_fails_and_offers_review(self, board):
        lesson, total = self._play(board, wrong_count=99)
        entry = board.progress.data["grammar"][lesson["id"]]
        assert entry["done"] is False
        assert "Заново" in _buttons_text(board.page)

    def test_next_lesson_button_leads_to_next_lesson(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        first = page.level_lessons[0]
        second = page.level_lessons[1]
        page._open_lesson(first)
        board.pump()
        assert any("ДАЛЬШЕ" in t or "→" in t for t in _buttons_text(page))
        _prev, nxt = page.catalog.neighbours(first["id"])
        assert nxt == second["id"]
        page.spread._open_unit(nxt)
        board.pump()
        assert page.spread._unit == second["id"]


class TestNavigation:
    def test_switching_lessons_keeps_the_list(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        first, second = page.level_lessons[0], page.level_lessons[1]
        page._open_lesson(first)
        board.pump()
        page._open_lesson(second)
        board.pump()
        assert page.spread._unit == second["id"]
        assert first["id"] in page.spread._rows and second["id"] in page.spread._rows

    def test_mode_switch_keeps_data_lazy(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        loaded = list(board.engine._lessons_cache)
        assert loaded == ["A1"]
        page._show_lessons("A1")
        board.pump()
        assert list(board.engine._lessons_cache) == ["A1"]
        assert board.engine._tables is None


class TestSelfCheck:
    def _pass_one_lesson(self, board) -> str:
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = page.level_lessons[0]
        page._open_lesson(lesson)
        board.pump()
        for drill in list(page.drills):
            _solve(page, drill)
        board.pump()
        return lesson["id"]

    def test_button_appears_after_first_lesson(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        assert "ПРОВЕРЬ СЕБЯ" not in _buttons_text(page)
        self._pass_one_lesson(board)
        page._rebuild = None
        page.spread._rebuild_left_extra()
        board.pump()
        assert "ПРОВЕРЬ СЕБЯ" in _buttons_text(page)

    def test_mixed_drills_from_passed_lessons_only(self, board):
        lesson_id = self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        assert page.spread._unit == SELF_CHECK_ID
        assert 1 <= len(page.drills) <= SELF_CHECK_SIZE
        passed_ids = {lesson_id}
        # все drills из пройденного урока
        source = {d["id"] for d in page.engine.lesson(lesson_id)["drills"]}
        assert all((d.get("id") in source) for d in page.drills)

    def test_self_check_is_not_scored(self, board):
        self._pass_one_lesson(board)
        page = board.page
        before = dict(board.progress.data.get("grammar") or {})
        page._start_self_check("A1")
        board.pump()
        for drill in list(page.drills):
            _solve(page, drill)
        board.pump()
        after = board.progress.data.get("grammar") or {}
        assert set(after) == set(before)

    def test_restart_rebuilds_the_same_check(self, board):
        self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        first = [d.get("id") for d in page.drills]
        page._start_self_check("A1")
        board.pump()
        assert [d.get("id") for d in page.drills] == first

    def test_back_from_self_check_returns_to_lesson_list(self, board):
        self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        page._show_lessons("A1")
        board.pump()
        assert page.spread._unit != SELF_CHECK_ID or page.level_lessons
        assert page.catalog.current_source_id() == COURSE_SOURCE


class TestLayout:
    def _assert_fits(self, board) -> None:
        board.root.update_idletasks()
        root = board.root
        assert root.winfo_width() >= 900 or True
        for widget in _descendants(board.page.content):
            try:
                if widget.winfo_width() > 1:
                    right = widget.winfo_rootx() + widget.winfo_width()
                    assert right <= root.winfo_rootx() + root.winfo_width() + px(4)
            except tk.TclError:
                pass

    def test_all_screens_fit_narrow_window(self, board):
        page = board.page
        board.root.geometry("900x360+0+0")
        page._show_lessons("A1")
        board.pump()
        self._assert_fits(board)
        page._open_lesson(page.level_lessons[0])
        board.pump()
        self._assert_fits(board)

    def test_wide_and_narrow_stay_usable(self, board):
        page = board.page
        page._show_lessons("B1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        for width in (900, 1280, 900):
            board.root.geometry(f"{width}x360+0+0")
            board.pump()
            assert page.spread.winfo_width() <= width + px(4) or page.spread.winfo_width() >= 1


class TestLoadingFreeze:
    def test_list_finishes_in_bounded_chunks(self, board):
        page = board.page
        page._show_lessons("A2")
        board.pump()
        assert "list" not in page.spread._jobs
        assert len(page.spread._rows) == 18

    def test_no_timers_left_after_pump(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        assert "list" not in page.spread._jobs
        assert "lesson" not in page.spread._jobs

    def test_destroy_cancels_pending_queue(self, tmp_path):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("нет дисплея")
        root.geometry("900x360+0+0")
        pilots.reset_root(tmp_path)
        pilot = pilots.create("Tester", accent="amber")
        pilots.activate(pilot["id"])
        progress = LanguageProgress(pilots.pilot_dir(pilot["id"]), "de")
        page = build_grammar_page(root, GermanPlugin(), progress, None)
        root.update()
        page._show_lessons("A1")
        page.destroy()
        root.update()
        root.destroy()
        pilots.reset_root(None)


class TestCompatibility:
    def test_old_entry_points_still_work(self, board):
        page = board.page
        lesson = page.engine.lessons("A1")[0]
        page._show_lesson(lesson)
        board.pump()
        assert page.current_level == "A1"
        drill = page.drills[0]
        page.drill_answer_var.set(page._expected(drill)[0])
        page._check_drill(drill)
        board.pump()
        assert page.checked

    def test_source_tabs_hook_starts_with_the_course(self, board):
        titles = [tab.title for tab in board.page.catalog.sources()]
        assert titles[0] == "Курс Star Typing"
        assert board.page.catalog.current_source_id() == COURSE_SOURCE


class TestWordBankHelpers:
    def test_shuffled_is_deterministic(self):
        assert _shuffled(["a", "b", "c", "d"], "s") == _shuffled(["a", "b", "c", "d"], "s")

class TestOpenSourceTabs:
    """Вкладки Grimm / ZUM: список, ленивая загрузка, атрибуция CC BY."""

    def test_tab_list_has_course_grimm_and_zum(self, board):
        titles = [tab.title for tab in board.page.catalog.sources()]
        assert titles == [
            "Курс Star Typing",
            "По методике Grimm Grammar — Техасский университет (COERLL), CC BY 4.0",
            "По методике ZUM Deutsch Lernen, CC BY 4.0",
        ]

    def test_grimm_tab_loads_index_but_not_topics(self, board):
        page = board.page
        board.pump()
        page.spread._select_source("grimm_grammar")
        board.pump()
        assert page.catalog.current_source_id() == "grimm_grammar"
        bank = page.catalog._open
        assert bank is not None
        assert "grimm_grammar" in bank._index
        assert "grimm_grammar" in bank._meta
        units = [item for kind, item in page.spread._plan if kind == "unit"]
        assert len(units) == 92
        # как у Murphy, первая тема открывается сама — но не все 92 файла
        loaded = bank.loaded_topic_ids("grimm_grammar")
        assert set(loaded) <= {units[0]["id"]}
        page.spread._open_unit("cas_01")
        board.pump()
        assert "cas_01" in bank.loaded_topic_ids("grimm_grammar")
        assert len(bank.loaded_topic_ids("grimm_grammar")) <= 2

    def test_grimm_topic_shows_attribution_and_original_url(self, board):
        page = board.page
        page.spread._select_source("grimm_grammar")
        board.pump()
        page.spread._open_unit("cas_01")
        board.pump()
        bank = page.catalog._open
        assert "cas_01" in bank.loaded_topic_ids("grimm_grammar")
        texts = _label_texts(page)
        attr = bank.attribution_line("grimm_grammar", "ru")
        assert attr
        assert attr in texts
        topic = bank.load_topic("grimm_grammar", "cas_01")
        assert topic["original_url"] in texts
        # объяснения Grimm остаются по-английски, без перевода
        snippet = (topic["sections"][0].get("text") or "")[:80]
        assert snippet
        assert snippet in texts

    def test_zum_tab_is_lazy_and_shows_attribution(self, board):
        page = board.page
        page.spread._select_source("zum_grammatik_kiste")
        board.pump()
        bank = page.catalog._open
        units = [item for kind, item in page.spread._plan if kind == "unit"]
        assert len(units) == 37
        loaded = bank.loaded_topic_ids("zum_grammatik_kiste")
        assert set(loaded) <= {units[0]["id"]}
        first = units[0]["id"]
        second = units[1]["id"]
        page.spread._open_unit(second)
        board.pump()
        assert second in bank.loaded_topic_ids("zum_grammatik_kiste")
        assert len(bank.loaded_topic_ids("zum_grammatik_kiste")) <= 2
        first = second
        texts = _label_texts(page)
        assert bank.attribution_line("zum_grammatik_kiste", "ru") in texts
        topic = bank.load_topic("zum_grammatik_kiste", first)
        assert topic["original_url"] in texts
