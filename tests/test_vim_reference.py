# -*- coding: utf-8 -*-
"""Учебник VIM: данные, честность пометок и панель F2.

Главное здесь — проверка честности: если клавиша помечена «работает в
тренажёре», движок обязан её выполнить, и наоборот — всё, что движок не умеет,
обязано быть помечено «только в настоящем VIM».
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from stamina import pilots
from stamina.lounge import vim_reference as ref
from stamina.lounge.vim_engine import (
    get_cursor_pos,
    get_grid_text,
    get_mode,
    init_from_grid,
    process_key,
    process_special_key,
)
from stamina.lounge.vim_trainer import LESSONS

#: Стенд для проверки клавиш: три строки, курсор в середине второй.
GRID = [
    "hello world",
    "  second line",
    "third line",
]
START = (4, 1)


def _state():
    state = init_from_grid([row[:] for row in GRID])
    state.cursor_x, state.cursor_y = START
    state.mode = "NORMAL"
    return state


def _feed(state, seq) -> None:
    """Прогнать последовательность токенов так же, как это делает тренажёр."""
    for token in seq:
        if token == "esc":
            process_special_key(state, "escape")
        elif token == "ctrl_r":
            process_key(state, "r", ctrl=True)
        elif token == "enter":
            process_special_key(state, "return")
        elif len(token) == 1:
            process_key(state, token)
        else:                                   # pragma: no cover - защита данных
            raise AssertionError(f"неизвестный токен {token!r}")


def _snapshot(state):
    return (get_grid_text(state), get_cursor_pos(state), get_mode(state),
            len(state.undo_stack), state.visual_start)


class TestData:
    """Структура учебника: темы, клавиши, обязательные поля."""

    def test_enough_material(self):
        assert len(ref.topics()) >= 12, "учебник должен покрывать VIM, а не два экрана"
        assert ref.total() >= 90

    def test_topics_are_well_formed(self):
        ids = [t["id"] for t in ref.topics()]
        assert len(ids) == len(set(ids))
        for topic in ref.topics():
            assert topic["title"].strip(), topic["id"]
            assert topic["blurb"].strip(), topic["id"]
            theory = topic.get("theory") or []
            assert len(theory) >= 2, f"{topic['id']}: теории меньше двух тезисов"
            assert len(topic["commands"]) >= 5, f"{topic['id']}: мало клавиш"

    def test_commands_have_all_fields(self):
        for topic in ref.topics():
            seen = set()
            for item in topic["commands"]:
                assert item["cmd"].strip(), topic["id"]
                assert item["desc"].strip(), item["cmd"]
                assert item.get("example", "").strip(), item["cmd"]
                assert item["sim"] in (True, False, "partial"), item["cmd"]
                assert item["cmd"] not in seen, f"{topic['id']}: дубль {item['cmd']}"
                seen.add(item["cmd"])

    def test_sim_entries_describe_their_effect(self):
        for item in ref.supported():
            assert item.get("seq"), f"{item['cmd']}: нет последовательности клавиш"
            assert item.get("probe") in ("cursor", "text", "mode"), item["cmd"]

    def test_partial_entries_have_sequence(self):
        for item in ref.simplified():
            assert item.get("seq"), f"{item['cmd']}: нет последовательности клавиш"

    def test_lessons_exist_in_trainer(self):
        known = {lesson["id"] for lesson in LESSONS}
        for item in ref.commands():
            lesson = item.get("lesson")
            if lesson:
                assert lesson in known, f"{item['cmd']}: урока {lesson} нет в тренажёре"
        assert len(ref.lessons()) >= 8, "учебник должен ссылаться на большинство уроков"

    def test_search_finds_by_text(self):
        assert ref.search("") == ref.commands()
        assert not ref.search("нет-такой-клавиши-никогда")
        hits = ref.search("слово")
        assert hits, "по слову «слово» должны найтись клавиши"
        assert all("слов" in (c["cmd"] + " " + c["desc"]).lower() for c in hits)

    def test_search_stays_inside_topic(self):
        items = ref.search("", topic_id="search")
        assert items and items == ref.commands("search")


class TestEngineHonesty:
    """Пометка «работает в тренажёре» проверяется движком, а не обещанием."""

    def test_supported_keys_really_work(self):
        for item in ref.supported():
            state = _state()
            for token in item.get("needs") or []:
                _feed(state, [token])
            before = _snapshot(state)
            _feed(state, item["seq"])
            after = _snapshot(state)
            probe = item["probe"]
            if probe == "cursor":
                ok = before[1] != after[1]
            elif probe == "text":
                ok = before[0] != after[0]
            else:
                ok = before[2] != after[2]
            assert ok, f"{item['cmd']}: помечено «работает», а состояние не изменилось"

    def test_simplified_keys_do_not_pretend(self):
        """«Упрощено» — значит движок не обязан менять текст: он просто знает клавишу."""
        for item in ref.simplified():
            state = _state()
            _feed(state, item["seq"])          # не должно упасть

    def test_unknown_command_cannot_be_marked_supported(self):
        """Обратная сторона: то, чего движок не знает, не должно быть в supported."""
        supported = {item["cmd"] for item in ref.supported()}
        for cmd in ("gg", "G", "ciw", "/pattern", ":%s/old/new/g", ":w", "ma"):
            assert cmd not in supported, f"{cmd}: движок этого не умеет — нельзя обещать"


def _key(sym: str, char: str = "", state: int = 0):
    return SimpleNamespace(keysym=sym, char=char, state=state, widget=None)


@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("1000x560")
    root.update()
    yield root
    root.destroy()


@pytest.fixture
def game():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("нет дисплея")
    root.geometry("1000x560")
    root.update()
    tmp = tempfile.TemporaryDirectory()
    pilots.reset_root(Path(tmp.name) / "Stamina")
    from stamina.lounge.vim_trainer import VimTrainerGame

    try:
        g = VimTrainerGame(root, on_back=lambda: None, app=None)
        g.pack(fill="both", expand=True)
        g.start()
        root.update()
        yield g
        g.stop()
    finally:
        pilots.reset_root()
        tmp.cleanup()
        root.destroy()


class TestPanel:
    """Панель F2: темы, клавиши, теория, статусы и переход к уроку."""

    def _panel(self, root, on_lesson=None):
        from stamina.lounge.vim_ref_panel import VimReferencePanel

        panel = VimReferencePanel(root, on_lesson=on_lesson or (lambda _l: None),
                                  on_close=lambda: None)
        panel.pack(fill="both", expand=True)
        root.update()
        return panel

    def test_theory_matches_selected_topic(self, tk_root):
        panel = self._panel(tk_root)
        try:
            assert panel.topics.keys() == [t["id"] for t in ref.topics()]
            for topic in ref.topics():
                panel.select_topic(topic["id"])
                tk_root.update()
                text = panel.visible_theory()
                assert topic["blurb"] in text, topic["id"]
                for line in topic["theory"]:
                    assert line in text, f"{topic['id']}: нет тезиса «{line}»"
        finally:
            panel.destroy()

    def test_keys_of_topic_are_listed(self, tk_root):
        panel = self._panel(tk_root)
        try:
            for topic in ref.topics():
                panel.select_topic(topic["id"])
                tk_root.update()
                assert panel.visible_commands() == [c["cmd"] for c in topic["commands"]]
        finally:
            panel.destroy()

    def test_search_filters_keys(self, tk_root):
        panel = self._panel(tk_root)
        try:
            panel.set_query("слово")
            tk_root.update()
            shown = panel.visible_commands()
            assert shown and len(shown) < ref.total()
            assert "dw" in shown
            panel.set_query("нет-такой-клавиши")
            tk_root.update()
            assert panel.visible_commands() == []
        finally:
            panel.destroy()

    def test_topic_switch_resets_query(self, tk_root):
        panel = self._panel(tk_root)
        try:
            panel.set_query("слово")
            panel.select_topic("search")
            tk_root.update()
            assert panel.var_query.get() == ""
            assert panel.visible_commands()
        finally:
            panel.destroy()

    def test_status_matches_sim_flag(self, tk_root):
        panel = self._panel(tk_root)
        try:
            panel.select_topic("delete")
            panel.select_command("dd")
            tk_root.update()
            assert panel.lbl_sim.cget("text") == ref.SIM_HINT
            panel.select_topic("files")
            panel.select_command(":w / :wq / :q!")
            tk_root.update()
            assert panel.lbl_sim.cget("text") == ref.REAL_HINT
            panel.select_topic("yank_put")
            panel.select_command("p")
            tk_root.update()
            assert panel.lbl_sim.cget("text") == ref.PARTIAL_HINT
        finally:
            panel.destroy()

    def test_lesson_button_knows_where_to_go(self, tk_root):
        panel = self._panel(tk_root)
        try:
            panel.select_topic("delete")
            panel.select_command("dw")
            tk_root.update()
            assert panel.selected_lesson() == "delete_word"
            panel.select_topic("files")
            panel.select_command(":w / :wq / :q!")
            tk_root.update()
            assert panel.selected_lesson() == ""
        finally:
            panel.destroy()

    def test_goto_lesson_calls_back(self, tk_root):
        seen = []
        panel = self._panel(tk_root, on_lesson=seen.append)
        try:
            panel.select_topic("undo")
            panel.select_command("u")
            panel.goto_lesson()
            assert seen == ["undo_redo"]
            panel.select_topic("files")
            panel.select_command(":show");
            panel.goto_lesson()
            assert seen == ["undo_redo"], "без урока кнопка ничего не делает"
        finally:
            panel.destroy()


class TestGameIntegration:
    """Учебник внутри игры: F2 открывает, клавиши не мешают, «К УРОКУ» ведёт в урок."""

    def test_f2_opens_and_closes(self, game):
        assert not game.reference_open()
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        assert game.reference_open()
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        assert not game.reference_open()

    def test_escape_closes_without_touching_the_grid(self, game):
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        before = get_grid_text(game.state)
        game.on_key(_key("Escape", "\x1b"))
        game.winfo_toplevel().update()
        assert not game.reference_open()
        assert get_grid_text(game.state) == before

    def test_keys_do_not_leak_into_the_editor(self, game):
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        before = (get_grid_text(game.state), get_cursor_pos(game.state))
        for sym in ("x", "d", "w", "l"):
            game.on_key(_key(sym, sym))
        after = (get_grid_text(game.state), get_cursor_pos(game.state))
        assert after == before, "пока открыт учебник, поле не должно меняться"

    def test_button_lives_in_the_tools_row(self, game):
        assert game.tools is not None
        assert game.tools_row is True

    def test_lesson_jump_loads_the_lesson(self, game):
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        panel = game.ref_panel
        panel.select_topic("delete")
        panel.select_command("dw")
        panel.goto_lesson()
        game.winfo_toplevel().update()
        assert not game.reference_open()
        assert LESSONS[game.lesson_idx]["id"] == "delete_word"

    def test_panel_marks_what_the_trainer_can_do(self, game):
        game.on_key(_key("F2"))
        game.winfo_toplevel().update()
        panel = game.ref_panel
        assert panel.lbl_sim.cget("text") in (ref.SIM_HINT, ref.PARTIAL_HINT, ref.REAL_HINT)
