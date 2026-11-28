"""Tests for VIM Engine and VIM Trainer lessons."""

import unittest

import pytest

from stamina.lounge.vim_engine import (
    init_from_grid,
    get_cursor_pos,
    get_grid_text,
    get_mode,
    process_key,
    process_insert_char,
    process_special_key,
    _undo,
    _redo,
)
from stamina.lounge.vim_trainer import LESSONS, VimTrainerGame


class VimEngineTests(unittest.TestCase):
    """Test core VIM engine functionality."""

    def test_init_from_grid_finds_at_marker(self):
        grid = [
            "....@....",
            "..........",
        ]
        state = init_from_grid(grid)
        self.assertEqual(get_cursor_pos(state), (4, 0))
        self.assertEqual(get_grid_text(state)[0], ".... ....")  # @ replaced with space

    def test_basic_motions_hjkl(self):
        grid = [
            "hello world",
            "foo bar",
        ]
        state = init_from_grid(grid)
        # Move right
        process_key(state, "l")
        self.assertEqual(get_cursor_pos(state), (1, 0))
        # Move down
        process_key(state, "j")
        self.assertEqual(get_cursor_pos(state), (1, 1))
        # Move left
        process_key(state, "h")
        self.assertEqual(get_cursor_pos(state), (0, 1))
        # Move up
        process_key(state, "k")
        self.assertEqual(get_cursor_pos(state), (0, 0))

    def test_word_motions_wbe(self):
        grid = ["the quick brown fox"]
        state = init_from_grid(grid)
        # w - forward to next word start
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (4, 0))  # 'q' of quick
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (10, 0))  # 'b' of brown
        # e - end of word
        process_key(state, "e")
        self.assertEqual(get_cursor_pos(state), (14, 0))  # 'n' of brown
        # b - backward to word start
        process_key(state, "b")
        self.assertEqual(get_cursor_pos(state), (10, 0))  # 'b' of brown
        process_key(state, "b")
        self.assertEqual(get_cursor_pos(state), (4, 0))  # 'q' of quick

    def test_line_motions_0_caret_dollar(self):
        grid = ["   indented line"]
        state = init_from_grid(grid)
        process_key(state, "$")
        self.assertEqual(get_cursor_pos(state), (15, 0))  # end (last char)
        process_key(state, "0")
        self.assertEqual(get_cursor_pos(state), (0, 0))  # absolute start
        process_key(state, "^")
        self.assertEqual(get_cursor_pos(state), (3, 0))  # first non-blank 'i'

    def test_counts(self):
        grid = [
            "line 0",
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5 @",
        ]
        state = init_from_grid(grid)
        # Cursor starts at @ position (6, 5)
        # 5k - up 5 lines, column preserved (clamped to line length)
        process_key(state, "5")
        process_key(state, "k")
        self.assertEqual(get_cursor_pos(state)[1], 0)  # line 0
        # Column should be preserved (6), clamped to line length - 1 (5) in NORMAL mode
        self.assertEqual(get_cursor_pos(state)[0], 5)
        # 3l - right 3 (but at end of line, so no movement)
        process_key(state, "3")
        process_key(state, "l")
        self.assertEqual(get_cursor_pos(state)[0], 5)

    def test_delete_char_x(self):
        grid = ["delete_me"]
        state = init_from_grid(grid)
        process_key(state, "x")  # delete 'd'
        self.assertEqual(get_grid_text(state)[0], "elete_me")
        process_key(state, "x")  # delete 'e'
        self.assertEqual(get_grid_text(state)[0], "lete_me")

    def test_delete_before_char_X(self):
        grid = ["hello"]
        state = init_from_grid(grid)
        # Move to second 'l' (index 3): h(0) e(1) l(2) l(3) o(4)
        process_key(state, "l")  # e
        process_key(state, "l")  # first l
        process_key(state, "l")  # second l
        process_key(state, "X")  # delete before cursor (first l at index 2)
        self.assertEqual(get_grid_text(state)[0], "helo")

    def test_delete_word_dw(self):
        grid = ["remove these words please"]
        state = init_from_grid(grid)
        process_key(state, "d")
        process_key(state, "w")
        # dw deletes "remove " (word + trailing space)
        self.assertEqual(get_grid_text(state)[0], "these words please")

    def test_delete_line_dd(self):
        grid = [
            "line one",
            "line two",
            "line three",
            "line four",
        ]
        state = init_from_grid(grid)
        process_key(state, "j")  # line 1 (line two)
        process_key(state, "d")
        process_key(state, "d")
        # After dd, cursor on next line (was line three, now line 1)
        self.assertEqual(len(get_grid_text(state)), 3)
        self.assertEqual(get_grid_text(state)[1], "line three")
        process_key(state, "d")
        process_key(state, "d")
        # After second dd, cursor on next line (was line four, now line 1)
        self.assertEqual(len(get_grid_text(state)), 2)
        self.assertEqual(get_grid_text(state)[0], "line one")
        self.assertEqual(get_grid_text(state)[1], "line four")

    def test_change_word_cw(self):
        grid = ["replace this word"]
        state = init_from_grid(grid)
        # Move to 't' of 'this'
        for _ in range(8):
            process_key(state, "l")
        process_key(state, "c")
        process_key(state, "w")
        # Now in INSERT mode, type 'it'
        process_insert_char(state, "i")
        process_insert_char(state, "t")
        process_special_key(state, "escape")
        self.assertIn("it", get_grid_text(state)[0])

    def test_change_line_cc(self):
        grid = [
            "line one",
            "change whole line",
        ]
        state = init_from_grid(grid)
        process_key(state, "j")  # line 1
        process_key(state, "c")
        process_key(state, "c")
        process_insert_char(state, "n")
        process_insert_char(state, "e")
        process_insert_char(state, "w")
        process_special_key(state, "escape")
        self.assertEqual(get_grid_text(state)[1], "new")

    def test_yank_line_yy(self):
        state = init_from_grid(["yank this line"])
        process_key(state, "y")
        process_key(state, "y")
        self.assertEqual(state.registers['"'], ["yank this line"])
        self.assertEqual(get_grid_text(state), ["yank this line"])

    def test_yank_line_Y_and_named_register(self):
        state = init_from_grid(["yank this line"])
        for key in ('"', "a", "Y"):
            process_key(state, key)
        self.assertEqual(state.registers["a"], ["yank this line"])
        self.assertEqual(state.registers['"'], ["yank this line"])

    def test_put_p_on_empty_line(self):
        state = init_from_grid(["copy me", ""])
        process_key(state, "y")
        process_key(state, "y")
        process_key(state, "j")
        process_key(state, "p")
        self.assertEqual(get_grid_text(state)[:2], ["copy me", "copy me"])

    def test_undo_redo(self):
        grid = ["hello world"]
        state = init_from_grid(grid)
        process_key(state, "x")  # delete 'h'
        self.assertEqual(get_grid_text(state)[0], "ello world")
        _undo(state)
        self.assertEqual(get_grid_text(state)[0], "hello world")
        _redo(state)
        self.assertEqual(get_grid_text(state)[0], "ello world")

    def test_insert_mode_i_a_o_O(self):
        grid = ["hello world"]
        state = init_from_grid(grid)
        # i - insert before cursor
        process_key(state, "i")
        process_insert_char(state, "X")
        process_special_key(state, "escape")
        self.assertEqual(get_grid_text(state)[0], "Xhello world")

        # a - insert after cursor
        process_key(state, "$")  # end of line
        process_key(state, "a")
        process_insert_char(state, "!")
        process_special_key(state, "escape")
        self.assertEqual(get_grid_text(state)[0], "Xhello world!")

        # o - open line below
        process_key(state, "o")
        process_insert_char(state, "n")
        process_insert_char(state, "e")
        process_insert_char(state, "w")
        process_special_key(state, "escape")
        self.assertEqual(len(get_grid_text(state)), 2)
        self.assertEqual(get_grid_text(state)[1], "new")

    def test_visual_mode_v(self):
        grid = ["select this text"]
        state = init_from_grid(grid)
        process_key(state, "v")  # enter visual
        for _ in range(10):
            process_key(state, "l")  # select 'select thi'
        process_key(state, "d")  # delete selection
        self.assertNotIn("select", get_grid_text(state)[0])

    def test_visual_line_V(self):
        grid = ["line one", "line two", "line three"]
        state = init_from_grid(grid)
        process_key(state, "j")  # line 1
        process_key(state, "V")  # visual line
        process_key(state, "j")  # extend to line 2
        process_key(state, "d")  # delete both lines
        self.assertEqual(len(get_grid_text(state)), 1)
        self.assertEqual(get_grid_text(state)[0], "line one")

    def test_search_forward(self):
        grid = ["find the word vim here", "vim is powerful vim"]
        state = init_from_grid(grid)
        # Search not directly testable without command mode, but we can test motion

    def test_repeat_count_with_operators(self):
        grid = [
            "........",
            "........",
            "........",
            "........",
            "........",
            "........",
            "@.......",
        ]
        state = init_from_grid(grid)
        # @ is at (0, 6)
        process_key(state, "5")
        process_key(state, "k")
        self.assertEqual(get_cursor_pos(state)[1], 1)  # line 1 (6-5=1)
        process_key(state, "3")
        process_key(state, "l")
        self.assertEqual(get_cursor_pos(state)[0], 3)


class VimTrainerLessonTests(unittest.TestCase):
    """Test each of the 12 lessons can be completed."""

    def test_lesson_1_motion_basic(self):
        """Lesson 1: Basic h/j/k/l motion to reach goal."""
        grid = [
            "........",
            ".@......",
            "........",
        ]
        state = init_from_grid(grid)
        # @ at position 1, goal at position 7 (0-indexed, 8 chars total)
        # Move right 6 times to reach position 7 (last char)
        for _ in range(6):
            process_key(state, "l")
        self.assertEqual(get_cursor_pos(state), (7, 1))

    def test_lesson_2_motion_word(self):
        """Lesson 2: Word motions w/b/e."""
        grid = [
            "the quick brown fox",
            " jumps over the lazy",
            " dog...............",
        ]
        state = init_from_grid(grid)
        # w from start (0) -> 'q' (4)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (4, 0))
        # w -> 'b' (10)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (10, 0))
        # w -> 'f' (16)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (16, 0))
        # j -> line 1 (column preserved, clamped to line length)
        process_key(state, "j")
        # w from column 16 -> end of line (19)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state)[1], 1)
        # Reset to column 0 for next test
        process_key(state, "0")
        # w -> 'j' of jumps (1)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (1, 1))
        # w -> 'o' of over (7)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (7, 1))
        # w -> 't' of the (12)
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (12, 1))
        # j -> line 2 (column preserved)
        process_key(state, "j")
        process_key(state, "0")
        # w -> 'd' of dog (1) - line starts with space
        process_key(state, "w")
        self.assertEqual(get_cursor_pos(state), (1, 2))

    def test_lesson_3_motion_line(self):
        """Lesson 3: Line motions 0/^/$."""
        grid = [
            "   indented line",
            "another line here",
            "  third line    ",
        ]
        state = init_from_grid(grid)
        # Line 0: "   indented line" (len 16, indices 0-15)
        process_key(state, "0")
        self.assertEqual(get_cursor_pos(state), (0, 0))
        process_key(state, "^")
        self.assertEqual(get_cursor_pos(state), (3, 0))
        process_key(state, "$")
        self.assertEqual(get_cursor_pos(state), (15, 0))
        # Line 1: "another line here" (len 17, indices 0-16)
        process_key(state, "j")
        process_key(state, "0")
        self.assertEqual(get_cursor_pos(state), (0, 1))
        process_key(state, "^")
        self.assertEqual(get_cursor_pos(state), (0, 1))
        process_key(state, "$")
        self.assertEqual(get_cursor_pos(state), (16, 1))
        # Line 2: "  third line    " (len 16, indices 0-15, last char is space)
        process_key(state, "j")
        process_key(state, "0")
        self.assertEqual(get_cursor_pos(state), (0, 2))
        process_key(state, "^")
        self.assertEqual(get_cursor_pos(state), (2, 2))
        process_key(state, "$")
        self.assertEqual(get_cursor_pos(state), (15, 2))

    def test_lesson_4_delete_char(self):
        """Lesson 4: Delete chars with x/X."""
        grid = [
            "delete_me",
            "xXxXxXxXx",
            "........",
        ]
        state = init_from_grid(grid)
        # "delete_me" is 9 chars, need 9 x presses
        for _ in range(9):
            process_key(state, "x")
        row0 = get_grid_text(state)[0]
        self.assertFalse(any(c.isalnum() for c in row0))

    def test_lesson_5_delete_word(self):
        """Lesson 5: Delete words with dw/db/de."""
        grid = [
            "remove these words please",
            "..........................",
            "..........................",
        ]
        state = init_from_grid(grid)
        # Delete all words with dw (4 words)
        for _ in range(4):
            process_key(state, "d")
            process_key(state, "w")
        row0 = get_grid_text(state)[0]
        self.assertFalse(any(c.isalnum() for c in row0))

    def test_lesson_6_delete_line(self):
        """Lesson 6: Delete lines with dd/D."""
        grid = [
            "line one",
            "line two",
            "line three",
            "line four",
        ]
        state = init_from_grid(grid)
        process_key(state, "j")  # line 1 (line two)
        process_key(state, "d")
        process_key(state, "d")
        # After dd, cursor on next line (was line three, now line 1)
        self.assertEqual(len(get_grid_text(state)), 3)
        self.assertEqual(get_grid_text(state)[1], "line three")
        process_key(state, "d")
        process_key(state, "d")
        # After second dd, cursor on next line (was line four, now line 1)
        self.assertEqual(len(get_grid_text(state)), 2)
        self.assertEqual(get_grid_text(state)[0], "line one")
        self.assertEqual(get_grid_text(state)[1], "line four")

    def test_lesson_7_insert_mode(self):
        """Lesson 7: Insert mode i/a/o/O."""
        grid = [
            "hello world",
            "...........",
            "...........",
        ]
        state = init_from_grid(grid)
        # i before space at pos 5
        for _ in range(5):
            process_key(state, "l")
        process_key(state, "i")
        for ch in " beautiful":
            process_insert_char(state, ch)
        process_special_key(state, "escape")
        # a after 'd' at end
        process_key(state, "$")
        process_key(state, "a")
        process_insert_char(state, "!")
        process_special_key(state, "escape")
        # o on line 1 (which is dots)
        process_key(state, "j")
        process_key(state, "o")
        for ch in "new line below":
            process_insert_char(state, ch)
        process_special_key(state, "escape")
        row0 = get_grid_text(state)[0]
        row1 = get_grid_text(state)[1]
        row2 = get_grid_text(state)[2]
        self.assertIn("beautiful", row0)
        self.assertIn("!", row0)
        self.assertIn("new line below", row2)  # o creates line below current

    def test_lesson_8_change_operator(self):
        """Lesson 8: Change operator cw/cc/C."""
        grid = [
            "replace this word",
            "change whole line",
            ".................",
        ]
        state = init_from_grid(grid)
        # cw on 'this' -> 'it'
        for _ in range(8):
            process_key(state, "l")
        process_key(state, "c")
        process_key(state, "w")
        process_insert_char(state, "i")
        process_insert_char(state, "t")
        process_special_key(state, "escape")
        # cc on line 1 -> 'new line'
        process_key(state, "j")
        process_key(state, "c")
        process_key(state, "c")
        for ch in "new line":
            process_insert_char(state, ch)
        process_special_key(state, "escape")
        row0 = get_grid_text(state)[0]
        row1 = get_grid_text(state)[1]
        self.assertIn("it", row0)
        self.assertIn("new line", row1)

    def test_lesson_9_visual_mode(self):
        """Lesson 9: Visual mode v/V."""
        grid = [
            "select this text",
            "and delete it",
            "..............",
        ]
        state = init_from_grid(grid)
        # v + select 'this text' + d
        process_key(state, "v")
        for _ in range(10):
            process_key(state, "l")
        process_key(state, "d")
        # V + delete line 1
        process_key(state, "j")
        process_key(state, "V")
        process_key(state, "j")
        process_key(state, "d")
        row0 = get_grid_text(state)[0]
        self.assertNotIn("select", row0)
        self.assertEqual(len(get_grid_text(state)), 1)

    def test_lesson_10_search_replace(self):
        """Lesson 10: Search / n N * # :s."""
        grid = [
            "find the word vim here",
            "vim is powerful vim",
            "......................",
        ]
        state = init_from_grid(grid)
        text = "\n".join(get_grid_text(state))
        self.assertEqual(text.count("vim"), 3)

    def test_lesson_11_undo_redo(self):
        """Lesson 11: Undo u and Redo Ctrl+r."""
        grid = [
            "make a mistake",
            "then fix it",
            "..............",
        ]
        state = init_from_grid(grid)
        process_key(state, "x")  # delete 'm'
        self.assertEqual(get_grid_text(state)[0], "ake a mistake")
        _undo(state)
        self.assertEqual(get_grid_text(state)[0], "make a mistake")
        _redo(state)
        self.assertEqual(get_grid_text(state)[0], "ake a mistake")

    def test_lesson_12_repeat_count(self):
        """Lesson 12: Count prefixes 5j 3dw 2dd 10x."""
        grid = [
            "........",
            "........",
            "........",
            "........",
            "........",
            "........",
            "@.......",
        ]
        state = init_from_grid(grid)
        # @ at (0, 6)
        process_key(state, "5")
        process_key(state, "k")
        self.assertEqual(get_cursor_pos(state)[1], 1)  # line 1
        process_key(state, "3")
        process_key(state, "l")
        self.assertEqual(get_cursor_pos(state)[0], 3)


class _Event:
    def __init__(self, keysym="", keycode=0, char="", state=0):
        self.keysym = keysym
        self.keycode = keycode
        self.char = char
        self.state = state


class VimTrainerNavigationTests(unittest.TestCase):
    """Ctrl+N/Ctrl+P lesson navigation and printable guard."""

    @classmethod
    def setUpClass(cls):
        tk = pytest.importorskip("tkinter")
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as e:
            pytest.skip(f"no Tk display: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _make_game(self):
        from stamina.lounge.vim_trainer import VimTrainerGame
        g = VimTrainerGame.__new__(VimTrainerGame)
        g.state = init_from_grid(["@hello"])
        g.lesson_idx = 0
        g.completed_lessons = set()
        g.pending_count = ""
        g._pending_count = ""
        g.message = ""
        g.message_color = "#fff"
        g.redraw = lambda *a, **k: None
        g.save_progress = lambda *a, **k: None
        g.add_score = lambda *a, **k: 0
        g._check_lesson_complete = lambda *a, **k: None
        g.handle_help_keys = lambda *a, **k: False
        g.reference_open = lambda *a, **k: False
        g._load_lesson = lambda idx: setattr(g, 'lesson_idx', idx)
        g._next_lesson = VimTrainerGame._next_lesson.__get__(g, VimTrainerGame)
        g._prev_lesson = VimTrainerGame._prev_lesson.__get__(g, VimTrainerGame)
        return g

    def test_ctrl_n_advances_lesson(self):
        g = self._make_game()
        VimTrainerGame.on_key(g, _Event("n", keycode=78, char="\x0e", state=0x4))
        self.assertEqual(g.lesson_idx, 1)

    def test_ctrl_n_russian_layout_advances_lesson(self):
        g = self._make_game()
        VimTrainerGame.on_key(g, _Event("Cyrillic_te", keycode=78, char="?", state=0x4))
        self.assertEqual(g.lesson_idx, 1)

    def test_ctrl_p_goes_previous(self):
        g = self._make_game()
        g.lesson_idx = 2
        VimTrainerGame.on_key(g, _Event("p", keycode=80, char="\x10", state=0x4))
        self.assertEqual(g.lesson_idx, 1)

    def test_ctrl_p_russian_layout_goes_previous(self):
        g = self._make_game()
        g.lesson_idx = 2
        VimTrainerGame.on_key(g, _Event("Cyrillic_ze", keycode=80, char="?", state=0x4))
        self.assertEqual(g.lesson_idx, 1)

    def test_ctrl_t_does_not_switch_lesson(self):
        g = self._make_game()
        g.lesson_idx = 1
        VimTrainerGame.on_key(g, _Event("t", keycode=84, char="\x14", state=0x4))
        self.assertEqual(g.lesson_idx, 1)

    def test_ctrl_n_not_sent_to_engine(self):
        g = self._make_game()
        g.state = init_from_grid(["@foo foo"])
        VimTrainerGame.on_key(g, _Event("n", keycode=78, char="\x0e", state=0x4))
        self.assertEqual(get_cursor_pos(g.state), (0, 0))
        self.assertEqual(g.lesson_idx, 1)


class VimTrainerIntegrationTests(unittest.TestCase):
    """Integration tests for the full trainer flow."""

    def test_all_lessons_load(self):
        """All 24 lessons should be loadable."""
        from stamina.lounge.vim_trainer import LESSONS
        self.assertEqual(len(LESSONS), 24)
        for i, lesson in enumerate(LESSONS):
            state = init_from_grid(lesson["grid"])
            self.assertIsNotNone(state)
            self.assertTrue(len(state.grid) > 0)
            if "cursor" in lesson:
                x, y = lesson["cursor"]
                self.assertLess(y, len(state.grid))
                self.assertLessEqual(x, len(state.grid[y]))

    def test_lesson_targets_defined(self):
        """Each lesson has a target or a generic expect check."""
        from stamina.lounge.vim_trainer import LESSONS
        for lesson in LESSONS:
            self.assertTrue("target" in lesson or "expect" in lesson, lesson["id"])
            self.assertIn("grid", lesson)
            self.assertIn("hint", lesson)

    def test_new_lessons_have_task_text_and_hints(self):
        """Generated-text lessons must be self-explanatory."""
        from stamina.lounge.vim_trainer import LESSONS
        for lesson in LESSONS[12:]:
            self.assertTrue(lesson.get("tasks"), lesson["id"])
            self.assertGreaterEqual(len(lesson.get("hints") or []), 2, lesson["id"])
            self.assertTrue(set(lesson.get("focus") or []), lesson["id"])

    def test_lesson_grid_has_at_marker(self):
        """First lesson should have @ marker for cursor."""
        from stamina.lounge.vim_trainer import LESSONS
        first = LESSONS[0]
        grid_text = "\n".join(first["grid"])
        self.assertIn("@", grid_text)


class VimTrainerControlTests(unittest.TestCase):
    """Keys that go through VimTrainerGame.on_key (not straight into the engine)."""

    def _make_game(self, grid=None):
        g = VimTrainerGame.__new__(VimTrainerGame)
        g.state = init_from_grid(grid or ["@hello world", "second line", "third line"])
        g.lesson_idx = 0
        g.practice = False
        g.completed_lessons = set()
        g.message = ""
        g.message_color = "#fff"
        g._pending_count = ""
        g._targets = {"word": set(), "line": set()}
        g._search_text = ""
        g._search_hits = set()
        g._command = ""
        g._command_prefix = ""
        g._vim_found_count = 0
        g._did_undo_redo = False
        g._used_count = False
        g.redraw = lambda *a, **k: None
        g.save_progress = lambda *a, **k: None
        g.add_score = lambda *a, **k: 0
        g._check_lesson_complete = lambda *a, **k: None
        g.handle_help_keys = lambda *a, **k: False
        g.reference_open = lambda *a, **k: False
        g._next_lesson = lambda *a, **k: None
        g._prev_lesson = lambda *a, **k: None
        g._restore_focus = lambda *a, **k: None
        return g

    def test_escape_leaves_insert_visual_and_visual_line(self):
        for mode in ("INSERT", "VISUAL", "VISUAL_LINE"):
            g = self._make_game()
            g.state.mode = mode
            g.state.visual_start = (0, 0) if mode.startswith("VISUAL") else None
            VimTrainerGame.on_key(g, _Event("escape"))
            self.assertEqual(get_mode(g.state), "NORMAL", mode)

    def test_escape_cancels_command_line(self):
        g = self._make_game()
        g.state.mode = "COMMAND"
        g._command = ":s/old/new/"
        VimTrainerGame.on_key(g, _Event("escape"))
        self.assertEqual(get_mode(g.state), "NORMAL")
        self.assertEqual(g._command, "")

    def test_arrows_move_in_normal_and_visual(self):
        g = self._make_game(["@hello", "second", "third"])
        VimTrainerGame.on_key(g, _Event("Right"))
        self.assertEqual(get_cursor_pos(g.state), (1, 0))
        g.state.mode = "VISUAL"
        g.state.visual_start = (0, 1)
        g.state.cursor_x, g.state.cursor_y = 1, 0
        VimTrainerGame.on_key(g, _Event("Down"))
        self.assertEqual(get_cursor_pos(g.state), (1, 1))

    def test_count_reaches_engine_and_marks_usage(self):
        g = self._make_game(["@one", "two", "three", "four", "five", "six"])
        VimTrainerGame.on_key(g, _Event("5"))
        VimTrainerGame.on_key(g, _Event("j"))
        self.assertEqual(get_cursor_pos(g.state)[1], 5)
        self.assertTrue(g._used_count)
        self.assertEqual(g._pending_count, "")

    def test_search_command_and_n_count_hits(self):
        g = self._make_game(["@find the word vim here", "vim is powerful vim"])
        VimTrainerGame.on_key(g, _Event("slash", char="/"))
        self.assertEqual(get_mode(g.state), "COMMAND")
        for ch in "vim":
            VimTrainerGame.on_key(g, _Event(ch))
        VimTrainerGame.on_key(g, _Event("Return"))
        self.assertEqual(get_mode(g.state), "NORMAL")
        self.assertGreaterEqual(g._vim_found_count, 1)
        VimTrainerGame.on_key(g, _Event("n"))
        self.assertGreaterEqual(g._vim_found_count, 2)


class VimTrainerEscPriorityTests(unittest.TestCase):
    """Esc belongs to the trainer in any VIM mode until F3 allows double-Esc exit."""

    def _owner(self, mode="NORMAL", *, current=None, command="", keysym="Escape"):
        from types import SimpleNamespace

        from stamina import lounge_hook
        from stamina.cockpit import Cockpit

        seen = []
        game = SimpleNamespace(
            game_id="vim_trainer",
            state=SimpleNamespace(mode=mode),
            _command=command,
            esc_isolated=True,
            on_key=lambda e: seen.append(e),
        )
        fake = SimpleNamespace(
            current=current or lounge_hook.KEY,
            screens={lounge_hook.KEY: SimpleNamespace(game=game)},
        )
        event = _Event(keysym)
        return Cockpit._vim_trainer_owner(fake, event), seen, event

    def test_non_normal_modes_own_escape(self):
        for mode in ("INSERT", "VISUAL", "VISUAL_LINE", "COMMAND"):
            owner, _, _ = self._owner(mode)
            self.assertIsNotNone(owner, mode)

    def test_escape_is_owned_in_any_vim_mode(self):
        # Из урока нельзя вылететь двойным Esc: клавиша всегда идёт в тренажёр.
        self.assertIsNotNone(self._owner("NORMAL")[0])
        self.assertIsNotNone(self._owner("INSERT")[0])

    def test_other_screens_and_other_keys_do_not_steal_escape(self):
        self.assertIsNone(self._owner("INSERT", current="bridge")[0])
        self.assertIsNone(self._owner("INSERT", keysym="Left")[0])

    def test_pending_command_still_owns_escape_in_normal_mode(self):
        self.assertIsNotNone(self._owner("NORMAL", command=":s/old/")[0])


class VimTrainerArenaTests(unittest.TestCase):
    def test_first_lesson_arena_is_large(self):
        from stamina.lounge.vim_trainer import LESSONS
        first = LESSONS[0]
        self.assertGreaterEqual(len(first["grid"]), 8)
        self.assertGreaterEqual(len(first["grid"][0]), 16)
        self.assertEqual(first["goal_pos"][0], len(first["grid"][0]) - 1)

    def test_practice_arena_is_large_and_uniform(self):
        from stamina.lounge.vim_trainer import PRACTICE_GRID
        self.assertGreaterEqual(len(PRACTICE_GRID), 8)
        widths = {len(row) for row in PRACTICE_GRID}
        self.assertEqual(len(widths), 1)
        self.assertGreaterEqual(widths.pop(), 16)


class VimTrainerIsolationTests(unittest.TestCase):
    """F3: изоляция Esc и возврат двойного Esc для выхода из тренажёра."""

    def _make_game(self, grid=None):
        g = VimTrainerGame.__new__(VimTrainerGame)
        g.state = init_from_grid(grid or ["@hello world", "second line", "third line"])
        g.lesson_idx = 0
        g.practice = False
        g.completed_lessons = set()
        g.message = ""
        g.message_color = "#fff"
        g._pending_count = ""
        g._targets = {"word": set(), "line": set()}
        g._search_text = ""
        g._search_hits = set()
        g._command = ""
        g._command_prefix = ""
        g._vim_found_count = 0
        g._did_undo_redo = False
        g._used_count = False
        g._used_keys = set()
        g._typed_commands = []
        g._macros = {}
        g._macro_keys = []
        g._macro_recording = False
        g._macro_replayed = False
        g._expect_targets = []
        g._hint_index = 0
        g._idle_keys = 0
        g._progress_sig = None
        g.esc_isolated = True
        g._esc_exit_at = 0.0
        g.btn_iso = None
        g.backs = []
        g._back = lambda: g.backs.append(True)
        g.redraw = lambda *a, **k: None
        g.save_progress = lambda *a, **k: None
        g.add_score = lambda *a, **k: 0
        g._check_lesson_complete = lambda *a, **k: None
        g.handle_help_keys = lambda *a, **k: False
        g.reference_open = lambda *a, **k: False
        g._next_lesson = lambda *a, **k: None
        g._prev_lesson = lambda *a, **k: None
        g._restore_focus = lambda *a, **k: None
        return g

    def test_f3_toggles_isolation(self):
        g = self._make_game()
        self.assertTrue(g.esc_isolated)
        VimTrainerGame.on_key(g, _Event("F3"))
        self.assertFalse(g.esc_isolated)
        self.assertIn("ВЫКЛ", g._iso_text())
        self.assertIn("выход", g.message)
        VimTrainerGame.on_key(g, _Event("F3"))
        self.assertTrue(g.esc_isolated)

    def test_double_esc_does_not_exit_while_isolated(self):
        g = self._make_game()
        VimTrainerGame.on_key(g, _Event("Escape"))
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(g.backs, [])

    def test_double_esc_exits_after_f3(self):
        g = self._make_game()
        VimTrainerGame.on_key(g, _Event("F3"))
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(g.backs, [])
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(g.backs, [True])

    def test_other_key_resets_double_esc_timer(self):
        g = self._make_game()
        VimTrainerGame.on_key(g, _Event("F3"))
        VimTrainerGame.on_key(g, _Event("Escape"))
        VimTrainerGame.on_key(g, _Event("x"))
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(g.backs, [])

    def test_escape_still_switches_mode_before_exit(self):
        g = self._make_game()
        g.state.mode = "INSERT"
        VimTrainerGame.on_key(g, _Event("F3"))
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(get_mode(g.state), "NORMAL")
        VimTrainerGame.on_key(g, _Event("Escape"))
        self.assertEqual(g.backs, [True])

    def test_question_key_shows_lesson_hint(self):
        g = self._make_game()
        g.lesson_idx = 12
        VimTrainerGame.on_key(g, _Event("question", char="?"))
        self.assertIn("Подсказка 1/", g.message)

    def test_macro_record_and_replay(self):
        g = self._make_game(["@xxxx first", "xxxx second", "third"])
        for key in ("q", "x", "x", "q", "j", "@", "a"):
            VimTrainerGame.on_key(g, _Event(key))
        self.assertEqual(get_grid_text(g.state)[1], "xx second")
        self.assertTrue(g._macro_replayed)

    def test_expect_visit_tracks_each_target(self):
        g = self._make_game()
        expect = {"kind": "visit", "targets": [(0, 0), (5, 0)]}
        self.assertFalse(g._check_expect(expect, [], (0, 0)))
        self.assertTrue(g._check_expect(expect, [], (5, 0)))

    def test_expect_text_checks_edited_rows(self):
        g = self._make_game()
        expect = {"kind": "text", "rows": ["CC Def", "second line"]}
        self.assertTrue(g._check_expect(expect, ["CC Def", "second line", "third line"], (0, 0)))
        self.assertFalse(g._check_expect(expect, ["xx Def", "second line"], (0, 0)))

    def test_expect_commands_need_typed_command(self):
        g = self._make_game()
        expect = {"kind": "commands", "any": [":sp", ":tabnew"]}
        self.assertFalse(g._check_expect(expect, [], (0, 0)))
        g._typed_commands.append(":sp")
        self.assertTrue(g._check_expect(expect, [], (0, 0)))


class VimTrainerAdvancedLessonTests(unittest.TestCase):
    """Уроки 13–24 проходятся теми клавишами, которые показаны игроку."""

    SEQUENCES = {
        12: ["g", "g", "G"],
        13: ["f", "(", "f", ")", "f", "x"],
        14: ["%", "%"],
        15: ["r", "C", "l", "~"],
        16: ["d", "i", "w", "w", "d", "a", "w"],
        17: [">", ">", "j", "<", "<"],
        18: ["m", "a", "j", "'", "a"],
        19: ["y", "y", "j", "p"],
        20: ["x", ".", ".", "."],
        21: ["/", "v", "i", "m", "Return", "n", "n", ":", "s", "/", "v", "i", "m",
             "/", "V", "I", "M", "/", "g", "Return", "k", ":", "s", "/", "v", "i",
             "m", "/", "V", "I", "M", "/", "g", "Return"],
        22: ["q", "x", "x", "x", "x", "q", "j", "@", "a"],
        23: [":", "s", "p", "Return", ":", "v", "s", "p", "Return",
             ":", "t", "a", "b", "n", "e", "w", "Return", ":", "q", "Return"],
    }

    def _make_game(self, idx):
        lesson = LESSONS[idx]
        g = VimTrainerGame.__new__(VimTrainerGame)
        g.state = init_from_grid(lesson["grid"])
        if "cursor" in lesson:
            g.state.cursor_x, g.state.cursor_y = lesson["cursor"]
        g.lesson_idx = idx
        g.practice = False
        g.completed_lessons = set()
        g.message = ""
        g.message_color = "#fff"
        g._pending_count = ""
        g._targets = {"word": set(), "line": set()}
        g._search_text = ""
        g._search_hits = set()
        g._command = ""
        g._command_prefix = ""
        g._vim_found_count = 0
        g._did_undo_redo = False
        g._used_count = False
        g._ensure_tracking()
        g._reset_progress_state()
        g.btn_iso = None
        g.backs = []
        g._back = lambda: g.backs.append(True)
        g.redraw = lambda *a, **k: None
        g.save_progress = lambda *a, **k: None
        g.add_score = lambda *a, **k: None
        g.handle_help_keys = lambda *a, **k: False
        g.reference_open = lambda *a, **k: False
        g._next_lesson = lambda *a, **k: None
        g._prev_lesson = lambda *a, **k: None
        g._restore_focus = lambda *a, **k: None
        return g

    def test_every_advanced_lesson_completes(self):
        for idx, sequence in self.SEQUENCES.items():
            with self.subTest(lesson=LESSONS[idx]["id"]):
                g = self._make_game(idx)
                for key in sequence:
                    event = _Event(key, char=key if len(key) == 1 else "")
                    VimTrainerGame.on_key(g, event)
                self.assertIn(idx, g.completed_lessons)
                self.assertIn("Урок пройден", g.message)

    def test_completion_banner_survives_further_commands(self):
        g = self._make_game(21)
        for key in self.SEQUENCES[21]:
            VimTrainerGame.on_key(g, _Event(key, char=key if len(key) == 1 else ""))
        self.assertIn("Урок пройден", g.message)
        for key in (":", "x", "Return"):
            VimTrainerGame.on_key(g, _Event(key, char=key if len(key) == 1 else ""))
        self.assertIn("Урок пройден", g.message)


if __name__ == "__main__":
    unittest.main()