"""UI немецкой грамматики: цель урока, мостик, порции, банк слов, итог, таблицы.

Проверки идут по реальному флоу страницы: уровни → уроки → цель и мостик →
теория по шагам → упражнения → итог. Окно 900×360, как самый тесный борт.
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
    INSTRUCTION_CHOICE,
    INSTRUCTION_FILL,
    INSTRUCTION_REORDER,
    INSTRUCTION_TRANSFORM,
    INSTRUCTION_TRANSLATE,
    PASS_SCORE,
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


# ---------------------------------------------------------------------------
# Данные и вспомогательные функции
# ---------------------------------------------------------------------------

def _all_lessons() -> list[dict]:
    lessons = []
    for level in LEVELS:
        data = json.loads((DATA / f"{level}.json").read_text(encoding="utf-8"))
        for lesson in data["lessons"]:
            item = dict(lesson)
            item["level"] = data["level"]
            lessons.append(item)
    return lessons


def _all_drills() -> list[dict]:
    return [drill for lesson in _all_lessons() for drill in lesson["drills"]]


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _scroll_areas(page):
    """Пары (холст, внутренний фрейм) — всё, что прокручивается на странице."""
    out = []
    for widget in _descendants(page.content):
        if not isinstance(widget, tk.Canvas):
            continue
        for frame in widget.winfo_children():
            if isinstance(frame, tk.Frame):
                out.append((widget, frame))
    return out


def _panels(page):
    from stamina.hud import HudPanel
    return [w for w in _descendants(page.content) if isinstance(w, HudPanel)]


def _labels(page):
    return [w for w in _descendants(page.content) if isinstance(w, tk.Label)]


def _buttons_text(page):
    from stamina.hud import HudButton
    return [w._text for w in _descendants(page.content) if isinstance(w, HudButton)]


def _solve(page, drill, wrong: bool = False) -> None:
    """Ответить на текущее упражнение — верно или заведомо неверно."""
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
        page._check_answer()
        return
    if drill["type"] in ("choice", "identify"):
        options = drill.get("options") or [expected]
        if wrong:
            page._choose(next((o for o in options if o != expected), "—"))
        else:
            page._choose(expected)
        return
    page.drill_answer_var.set("xxx" if wrong else expected)
    page._check_answer()


# ---------------------------------------------------------------------------
# Фикстура страницы
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Мостик RU/UA → DE
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Порции: что и когда читается с диска
# ---------------------------------------------------------------------------

class TestLazyLoading:
    def test_level_selector_reads_no_level_files(self, board):
        engine = board.engine
        assert engine._lessons_cache == {}
        assert engine._tables is None
        assert engine._bridges is None
        assert board.page.stage == "levels"

    def test_level_screen_shows_six_cards(self, board):
        board.pump()
        grid = next(w for w in _scroll_areas(board.page)[0][1].winfo_children()
                    if isinstance(w, tk.Frame))
        assert len(grid.winfo_children()) == 6
        codes = [w.winfo_children()[0].winfo_children()[0].cget("text")
                 for w in grid.winfo_children()]
        assert codes == ["A1", "A2", "B1", "B2", "C1", "C2"]

    def test_entering_level_loads_only_that_level(self, board):
        board.page._show_lessons("B1")
        board.pump()
        assert list(board.engine._lessons_cache) == ["B1"]
        assert board.engine._tables is None

    def test_lesson_list_is_queued_in_chunks(self, board):
        page = board.page
        page._show_lessons("A1")
        assert len(page._pending) == 18, "список уроков должен рисоваться порциями"
        assert CHUNK < 18
        board.pump()
        assert page._pending == []
        inner = _scroll_areas(page)[0][1]
        cards = [w for w in inner.winfo_children() if isinstance(w, tk.Frame)]
        assert len(cards) == 18

    def test_tables_are_listed_lazily_and_opened_one_by_one(self, board):
        page = board.page
        page._set_mode("tables")
        board.pump()
        assert board.engine._tables is not None
        assert board.engine._lessons_cache == {}
        inner = _scroll_areas(page)[0][1]
        cards = [w for w in inner.winfo_children() if isinstance(w, tk.Frame)]
        assert len(cards) == len(board.engine.tables(None)) == 45

        table = board.engine.tables(None)[0]
        page._open_table(table["id"])
        board.pump()
        assert page.stage == "table"
        labels = [label.cget("text") for label in _labels(page)]
        assert table["title"] in labels
        cells = (len(table["rows"]) + 1) * len(table["columns"])
        assert len([w for w in _descendants(page.content) if isinstance(w, tk.Label)]) >= cells


# ---------------------------------------------------------------------------
# Урок: цель, мостик, ловушка
# ---------------------------------------------------------------------------

class TestLessonIntro:
    def test_intro_shows_can_do_bridge_and_trap(self, board):
        page = board.page
        page._show_lessons("A2")
        board.pump()
        lesson = next(les for les in page.level_lessons if les["id"] == "a2-01-dativ")
        page._open_lesson(lesson)
        board.pump()

        bridge = board.engine.bridge(lesson["id"])
        titles = [panel.title for panel in _panels(page)]
        assert "ЧТО ВЫ ОСВОИТЕ" in titles
        assert "МОСТИК RU/UA → DE" in titles
        assert "ЛОВУШКА" in titles

        texts = " ".join(label.cget("text") for label in _labels(page))
        assert bridge["can_do"] in texts
        assert bridge["bridge"] in texts
        assert bridge["trap"] in texts

    def test_intro_offers_start_and_skip(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        buttons = _buttons_text(page)
        assert "▶ НАЧАТЬ УРОК" in buttons
        assert "К УПРАЖНЕНИЯМ" in buttons

    def test_intro_warns_about_unfinished_prereq(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = next((les for les in page.level_lessons if les.get("prereq")), None)
        if lesson is None:
            pytest.skip("в A1 нет уроков с предпосылками")
        page._open_lesson(lesson)
        board.pump()
        texts = " ".join(label.cget("text") for label in _labels(page))
        assert "Сначала пройдите" in texts


# ---------------------------------------------------------------------------
# Теория по шагам
# ---------------------------------------------------------------------------

class TestTheory:
    def test_one_block_per_screen(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_theory()
        board.pump()
        assert page.stage == "theory"
        assert page.theory_index == 0
        texts = [label.cget("text") for label in _labels(page)]
        first = page.theory[0].get("text", "")
        assert first in texts
        # текст второго блока на экране не показывается
        second = page.theory[1].get("text", "")
        if second and second != first:
            assert second not in texts

    def test_next_prev_and_skip(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_theory()
        board.pump()
        page._theory_next()
        board.pump()
        assert board.page.theory_index == 1
        page._theory_prev()
        board.pump()
        assert page.theory_index == 0
        assert "ПРОПУСТИТЬ ТЕОРИЮ" in _buttons_text(page)
        page._start_practice()
        board.pump()
        assert page.stage == "practice"

    def test_table_ref_renders_as_grid(self, board):
        page = board.page
        lesson = next(les for les in _all_lessons()
                      if any(block.get("kind") == "table" for block in les["theory"]))
        page._show_lessons(lesson["level"])
        board.pump()
        page._open_lesson(lesson)
        block = next(block for block in lesson["theory"] if block.get("kind") == "table")
        page.theory_index = lesson["theory"].index(block)
        page.stage = "theory"
        page._render()
        board.pump()
        table = board.engine.table(block["ref"])
        labels = [label.cget("text") for label in _labels(page)]
        assert table["columns"][0] in labels
        assert table["rows"][0][1] in labels


# ---------------------------------------------------------------------------
# Упражнения: инструкция, подсказка, банк слов, проверка
# ---------------------------------------------------------------------------

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
        assert len(set(expected.values())) == 4  # у каждого типа своя формулировка

    def test_russian_prompt_asks_to_translate(self, board):
        """Задание по-русски, ответ по-немецки — инструкция «переведите»."""
        page = board.page
        drill = {"type": "choice", "prompt": "Übersetzung: 'Мы дома.'"}
        assert page._instruction(drill) == INSTRUCTION_TRANSLATE
        drill = {"type": "fill", "prompt": "Переведите: «Мы дома» → ____"}
        assert page._instruction(drill) != INSTRUCTION_FILL
        assert "Переведите" in page._instruction(drill)

    def test_rule_peek_shows_rules_without_leaving_exercise(self, board):
        """Как в Grammatik aktiv: правило рядом с упражнением, а не вместо него."""
        page = board.page
        page._show_lessons("A2")
        board.pump()
        lesson = next(les for les in page.level_lessons if les["id"] == "a2-01-dativ")
        page._open_lesson(lesson)
        page._start_practice()
        board.pump()

        drill_id = page._current_drill()["id"]
        assert "ПРАВИЛО" in _buttons_text(page)
        page._toggle_rule()
        board.pump()

        assert page.stage == "practice"
        assert page._current_drill()["id"] == drill_id
        assert "СПРЯТАТЬ ПРАВИЛО" in _buttons_text(page)
        titles = [panel.title for panel in _panels(page)]
        assert "ПРАВИЛО" in titles
        texts = " ".join(label.cget("text") for label in _labels(page))
        rule = next(block for block in page.lesson["theory"] if block.get("kind") == "rule")
        assert rule["text"] in texts

        page._toggle_rule()
        board.pump()
        assert page.rule_shown is False

    def test_rule_peek_does_not_change_progress(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        board.pump()
        page._toggle_rule()
        board.pump()
        assert page.answers == {}
        assert board.progress.data["grammar"] == {}

    def test_every_lesson_starts_with_a_visible_instruction(self, board):
        page = board.page
        for level in ("A1", "B2"):
            page._show_lessons(level)
            board.pump()
            lesson = page.level_lessons[0]
            page._open_lesson(lesson)
            page._start_practice()
            board.pump()
            texts = [label.cget("text") for label in _labels(page)]
            assert page._instruction(page._current_drill()) in texts

    def test_hint_names_letter_count_or_first_word(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        for drill in page.drills:
            text = page._hint_text(drill)
            answer = page._expected(drill)[0]
            if drill["type"] == "reorder":
                assert answer.split(" ")[0] in text
            else:
                letters = [ch for ch in answer if ch.isalpha()]
                if not letters:
                    assert "цифры" in text
                    continue
                assert str(len(letters)) in text
                assert letters[0] in text

    def test_hint_button_does_not_change_score(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        board.pump()
        drill = page._current_drill()
        page._toggle_hint()
        board.pump()
        assert page.hint_shown
        assert page.drill_index == 0 and page.answers == {}
        assert page._hint_text(drill) in [l.cget("text") for l in _labels(page)]

    def test_reorder_bank_is_clickable_and_solvable(self, board):
        page = board.page
        lesson = next(les for les in _all_lessons()
                      if any(d["type"] == "reorder" for d in les["drills"]))
        page._show_lessons(lesson["level"])
        board.pump()
        page._open_lesson(lesson)
        page._start_practice()
        index = next(i for i, d in enumerate(page.drills) if d["type"] == "reorder")
        page.drill_index = index
        page._render()
        board.pump()
        drill = page._current_drill()
        assert page.bank, "банк слов должен заполниться при показе"
        assert sorted(page.bank) == sorted(_word_bank(drill))
        assert _buttons_text(page).count(page.bank[0]) >= 1

        _solve(page, drill)
        board.pump()
        assert page.checked and page.last_ok
        assert page.answers[drill["id"]] is True

    def test_word_bank_ignores_punctuation_in_answer(self):
        drills = [d for d in _all_drills() if d["type"] == "reorder"]
        assert len(drills) == 57
        for drill in drills:
            bank = _word_bank(drill)
            expected = drill["answer"][0]
            pool = list(range(len(bank)))
            order = []
            for token in expected.split():
                index = next((i for i in pool
                              if bank[i].strip(".,;:!?").lower()
                              == token.strip(".,;:!?").lower()), None)
                assert index is not None, drill["id"]
                pool.remove(index)
                order.append(index)
            sentence = " ".join(bank[i] for i in order)
            assert _answer_matches("reorder", sentence, [expected]), drill["id"]
            assert _shuffled(bank, drill["id"]) == _shuffled(bank, drill["id"])

    def test_choice_keeps_exact_spelling(self):
        """В вариантах «zu Hause» и «zu hause» — разные ответы, регистр важен."""
        assert _answer_matches("choice", "Wir sind zu Hause.", ["Wir sind zu Hause."])
        assert not _answer_matches("choice", "Wir sind zu hause.", ["Wir sind zu Hause."])
        assert not _answer_matches("choice", "Strasse", ["Straße"])
        assert not _answer_matches("choice", "Maenner", ["Männer"])
        # Вписанное слово — наоборот, умлаут можно набрать раскрыто.
        assert _answer_matches("fill", "gross", ["groß"])
        assert _answer_matches("fill", "Maenner", ["Männer"])
        # Порядок слов проверяем без знаков препинания.
        assert _answer_matches("reorder", "Der Mann isst einen Apfel",
                               ["Der Mann isst einen Apfel."])

    def test_every_choice_drill_has_exactly_one_right_option(self):
        """Клик по верному варианту всегда даёт ровно один правильный ответ."""
        drills = [d for d in _all_drills() if d["type"] in ("choice", "identify")]
        assert len(drills) == 432
        for drill in drills:
            options = drill.get("options") or []
            hits = [opt for opt in options
                    if _answer_matches("choice", opt, drill["answer"])]
            assert len(hits) == 1, (drill["id"], drill["prompt"], options)

    def test_wrong_answer_shows_expected_and_reason(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        board.pump()
        drill = page._current_drill()
        _solve(page, drill, wrong=True)
        board.pump()
        assert page.checked and not page.last_ok
        texts = " ".join(label.cget("text") for label in _labels(page))
        assert "НЕВЕРНО" in texts
        assert page._expected(drill)[0] in texts
        assert drill["why"] in texts

    def test_retry_does_not_change_first_answer(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_practice()
        board.pump()
        drill = page._current_drill()
        _solve(page, drill, wrong=True)
        board.pump()
        page._retry_drill()
        board.pump()
        assert page.checked is False
        _solve(page, drill)
        board.pump()
        assert page.last_ok is True
        assert page.answers[drill["id"]] is False, "в зачёт идёт первая попытка"


# ---------------------------------------------------------------------------
# Итог: порог 80%, запись прогресса один раз
# ---------------------------------------------------------------------------

class TestSummary:
    def _play(self, board, wrong_count: int = 0) -> tuple[dict, int]:
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = page.level_lessons[0]
        page._open_lesson(lesson)
        page._start_practice()
        total = len(page.drills)
        for index in range(total):
            board.pump()
            drill = page._current_drill()
            _solve(page, drill, wrong=index < wrong_count)
            page._next_drill()
        board.pump()
        assert page.stage == "summary"
        return lesson, total

    def test_full_run_is_recorded_once(self, board):
        lesson, total = self._play(board)
        entry = board.progress.data["grammar"][lesson["id"]]
        assert entry["score"] == 1.0 and entry["done"] is True
        assert entry["attempts"] == 1

        board.page._render()  # перерисовали итог — второй записи быть не должно
        board.pump()
        assert board.progress.data["grammar"][lesson["id"]]["attempts"] == 1

    def test_score_shows_result_and_pass_mark(self, board):
        lesson, total = self._play(board)
        texts = " ".join(label.cget("text") for label in _labels(board.page))
        assert f"{total} из {total}" in texts
        assert "100%" in texts
        assert "Урок засчитан" in texts

    def test_below_threshold_fails_and_offers_review(self, board):
        lesson, total = self._play(board, wrong_count=3)
        entry = board.progress.data["grammar"][lesson["id"]]
        assert entry["score"] < PASS_SCORE and entry["done"] is False
        texts = " ".join(label.cget("text") for label in _labels(board.page))
        assert "Нужно 80%" in texts
        assert "РАЗБОР ОШИБОК" in [panel.title for panel in _panels(board.page)]
        buttons = _buttons_text(board.page)
        assert "ПОВТОРИТЬ ОШИБКИ" in buttons
        mistakes = [d for d in board.page.drills if not board.page.answers.get(d["id"])]
        assert len(mistakes) == 3

    def test_mistake_repeat_does_not_change_lesson_score(self, board):
        lesson, total = self._play(board, wrong_count=3)
        before = dict(board.progress.data["grammar"][lesson["id"]])
        page = board.page
        page._retry_mistakes()
        board.pump()
        assert page.run_full is False and page.recorded is True
        assert len(page.drills) == 3
        for _ in range(3):
            board.pump()
            _solve(page, page._current_drill())
            page._next_drill()
        board.pump()
        after = board.progress.data["grammar"][lesson["id"]]
        assert after["score"] == before["score"]
        assert after["attempts"] == before["attempts"]

    def test_next_lesson_button_leads_to_next_lesson(self, board):
        lesson, total = self._play(board)
        buttons = _buttons_text(board.page)
        assert "СЛЕДУЮЩИЙ УРОК" in buttons
        board.page._open_next_lesson()
        board.pump()
        assert board.page.stage == "intro"
        assert board.page.lesson["id"] == "a1-02-personalpronomen-sein"


# ---------------------------------------------------------------------------
# Навигация и раскладка
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_back_walks_the_way_it_came(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        board.pump()
        assert page.stage == "intro"
        page._go_back()
        board.pump()
        assert page.stage == "lessons"
        page._go_back()
        board.pump()
        assert page.stage == "levels"

    def test_back_from_theory_steps_one_block_back(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        page._open_lesson(page.level_lessons[0])
        page._start_theory()
        page._theory_next()
        board.pump()
        page._go_back()
        board.pump()
        assert page.stage == "theory" and page.theory_index == 0
        page._go_back()
        board.pump()
        assert page.stage == "intro"

    def test_mode_switch_keeps_data_lazy(self, board):
        page = board.page
        page._set_mode("tables")
        board.pump()
        page._set_mode("lessons")
        board.pump()
        assert page.stage == "levels"
        assert board.engine._lessons_cache == {}


class TestSelfCheck:
    """«Teste dich!» из Grammatik aktiv: короткая смешанная проверка по пройденному."""

    def _pass_one_lesson(self, board) -> str:
        page = board.page
        page._show_lessons("A1")
        board.pump()
        lesson = page.level_lessons[0]
        page._open_lesson(lesson)
        page._start_practice()
        for _ in range(len(page.drills)):
            board.pump()
            _solve(page, page._current_drill())
            page._next_drill()
        board.pump()
        return lesson["id"]

    def test_button_appears_after_first_lesson(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        assert "ПРОВЕРЬ СЕБЯ" not in " ".join(_buttons_text(page))

        self._pass_one_lesson(board)
        page._show_lessons("A1")
        board.pump()
        assert any("ПРОВЕРЬ СЕБЯ" in text for text in _buttons_text(page))

    def test_mixed_drills_from_passed_lessons_only(self, board):
        lesson_id = self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        assert page.stage == "practice"
        assert 0 < len(page.drills) <= SELF_CHECK_SIZE
        passed_ids = {d["id"] for d in board.engine.lesson(lesson_id)["drills"]}
        assert {d["id"] for d in page.drills}.issubset(passed_ids)

    def test_self_check_is_not_scored(self, board):
        self._pass_one_lesson(board)
        page = board.page
        before = dict(board.progress.data["grammar"])
        page._start_self_check("A1")
        board.pump()
        for _ in range(len(page.drills)):
            board.pump()
            _solve(page, page._current_drill())
            page._next_drill()
        board.pump()
        assert page.stage == "summary"
        assert board.progress.data["grammar"] == before
        texts = " ".join(label.cget("text") for label in _labels(page))
        assert "Проверка себя" in texts
        assert "СЛЕДУЮЩИЙ УРОК" not in _buttons_text(page)

    def test_restart_rebuilds_the_same_check(self, board):
        self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        first = [d["id"] for d in page.drills]
        page.drill_index = len(page.drills)
        page.stage = "summary"
        page._render()
        board.pump()
        page._restart_lesson()
        board.pump()
        assert page.stage == "practice"
        assert [d["id"] for d in page.drills] == first

    def test_back_from_self_check_returns_to_lesson_list(self, board):
        self._pass_one_lesson(board)
        page = board.page
        page._start_self_check("A1")
        board.pump()
        page._go_back()
        board.pump()
        assert page.stage == "lessons"


class TestLayout:
    """900×360: ничего не выезжает вправо, всё помещается по ширине."""

    def _assert_fits(self, board) -> None:
        for canvas, inner in _scroll_areas(board.page):
            width = canvas.winfo_width()
            if width <= 1:
                continue
            assert inner.winfo_reqwidth() <= width + px(2), (
                f"{board.page.stage}: содержимое шире окна "
                f"({inner.winfo_reqwidth()} > {width})")

    def test_all_screens_fit_narrow_window(self, board):
        page = board.page
        board.pump()
        self._assert_fits(board)

        page._show_lessons("C1")
        board.pump()
        self._assert_fits(board)

        page._open_lesson(page.level_lessons[0])
        board.pump()
        self._assert_fits(board)

        page._start_theory()
        board.pump()
        self._assert_fits(board)

        page._start_practice()
        board.pump()
        self._assert_fits(board)

        page._set_mode("tables")
        board.pump()
        self._assert_fits(board)

        page._open_table(board.engine.tables(None)[0]["id"])
        board.pump()
        self._assert_fits(board)

    def test_wide_table_stays_inside(self, board):
        page = board.page
        table = max(board.engine.tables(None), key=lambda t: len(t["columns"]))
        page._set_mode("tables")
        board.pump()
        page._open_table(table["id"])
        board.pump()
        self._assert_fits(board)


class TestLoadingFreeze:
    """Материал грузится порциями, таймеры не копятся, окно не «штормит»."""

    def test_list_finishes_in_bounded_chunks(self, board):
        page = board.page
        page._show_lessons("A1")
        total = len(page.level_lessons)
        planned = len(page._pending)
        assert planned == total
        # Каждый шаг рисует не больше CHUNK карточек.
        steps = 0
        while page._pending:
            before = len(page._pending)
            page._cancel_timer()
            for _ in range(CHUNK):
                if not page._pending:
                    break
                page._pending.pop(0)()
            assert before - len(page._pending) <= CHUNK
            steps += 1
            assert steps <= -(-total // CHUNK)
        board.pump()
        assert page._pending == []

    def test_no_timers_left_after_each_screen(self, board):
        page = board.page
        screens = [
            ("уровни", lambda: page._set_mode("lessons")),
            ("список", lambda: page._show_lessons("A2")),
            ("интро", lambda: page._open_lesson(page.level_lessons[0])),
            ("теория", page._start_theory),
            ("упражнение", page._start_practice),
            ("таблицы", lambda: page._set_mode("tables")),
        ]
        for name, go in screens:
            go()
            board.pump()
            assert page._pump_job is None, f"остался таймер: {name}"
            assert page._pending == [], f"осталась очередь: {name}"

    def test_rapid_navigation_does_not_multiply_the_queue(self, board):
        page = board.page
        for _ in range(30):
            page._show_lessons("A1")
            page._show_lessons("A2")
        # Очередь — только от последнего экрана, таймер один.
        assert len(page._pending) <= len(page.engine.lessons("A2"))
        board.pump()
        assert page._pending == []
        assert page.stage == "lessons"

    def test_destroy_cancels_pending_queue(self, tmp_path):
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
        pilot = pilots.create("Tester", accent="amber")
        pilots.activate(pilot["id"])
        progress = LanguageProgress(pilots.pilot_dir(pilot["id"]), "de")
        page = build_grammar_page(root, GermanPlugin(), progress, None)
        root.update()
        page._show_lessons("A1")
        assert page._pending
        page.destroy()
        assert page._pending == []
        assert page._pump_job is None
        root.update()  # ни одного TclError из мёртвых виджетов
        root.destroy()
        pilots.reset_root(None)

    def test_short_lines_do_not_pay_for_wrapping(self, board):
        """wraplength только у длинных строк — иначе раскладка списка тормозит."""
        page = board.page
        page._show_lessons("A1")
        board.pump()
        checked = 0
        for label, size, bold, inset in list(page._wrapped):
            text = label.cget("text")
            width = page._wrap_px() - inset
            wrapped = int(label.cget("wraplength") or 0) > 0
            if wrapped:
                assert page._needs_wrap(text, width, size, bold), text
                checked += 1
            else:
                assert not page._needs_wrap(text, width, size, bold), text
        assert checked >= 0

    def test_narrow_window_adds_wrap_and_wide_removes_it(self, board):
        page = board.page
        page._show_lessons("A1")
        board.pump()
        long_text = "Строка средней длины: влезает в широкое окно, но не в узкое."
        long_label = page._label(page.content, long_text, 10)
        board.root.update()
        assert int(long_label.cget("wraplength") or 0) == 0

        original = page._wrap_px
        page._wrap_px = lambda: px(240)
        page._on_content_configure()
        assert int(long_label.cget("wraplength")) == px(240)

        page._wrap_px = original
        page._on_content_configure()
        assert int(long_label.cget("wraplength")) == 0

    def test_no_horizontal_overflow_after_resize(self, board):
        page = board.page
        page._show_lessons("B1")
        board.pump()
        for width in (700, 1200, 900):
            board.root.geometry(f"{width}x360+0+0")
            board.pump()
            for canvas, inner in _scroll_areas(page):
                if canvas.winfo_width() > 1:
                    assert inner.winfo_reqwidth() <= canvas.winfo_width() + px(2)


# ---------------------------------------------------------------------------
# Совместимость со старым API страницы
# ---------------------------------------------------------------------------

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

    def test_tables_container_points_to_list(self, board):
        page = board.page
        page._set_mode("tables")
        board.pump()
        assert page.tables_container is not None
        assert page.tables_container.winfo_exists()
