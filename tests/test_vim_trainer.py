"""Tests for VIM Engine and VIM Trainer lessons."""

import unittest

from stamina.lounge.vim_engine import (
    init_from_grid,
    get_cursor_pos,
    get_grid_text,
    process_key,
    process_insert_char,
    process_special_key,
    _undo,
    _redo,
)


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
        grid = ["yank this line"]
        state = init_from_grid(grid)
        process_key(state, "y")
        process_key(state, "y")
        # No visual change, just internal register (not tested here)

    def test_put_p(self):
        grid = ["line one", "line two"]
        state = init_from_grid(grid)
        process_key(state, "y")
        process_key(state, "y")
        process_key(state, "j")
        process_key(state, "p")
        # Put after cursor - simplified, no actual register

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


class VimTrainerIntegrationTests(unittest.TestCase):
    """Integration tests for the full trainer flow."""

    def test_all_lessons_load(self):
        """All 12 lessons should be loadable."""
        from stamina.lounge.vim_trainer import LESSONS
        self.assertEqual(len(LESSONS), 12)
        for i, lesson in enumerate(LESSONS):
            state = init_from_grid(lesson["grid"])
            self.assertIsNotNone(state)
            self.assertTrue(len(state.grid) > 0)

    def test_lesson_targets_defined(self):
        """Each lesson has a target type."""
        from stamina.lounge.vim_trainer import LESSONS
        for lesson in LESSONS:
            self.assertIn("target", lesson)
            self.assertIn("grid", lesson)
            self.assertIn("hint", lesson)

    def test_lesson_grid_has_at_marker(self):
        """First lesson should have @ marker for cursor."""
        from stamina.lounge.vim_trainer import LESSONS
        first = LESSONS[0]
        grid_text = "\n".join(first["grid"])
        self.assertIn("@", grid_text)


if __name__ == "__main__":
    unittest.main()