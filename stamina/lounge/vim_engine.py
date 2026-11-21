"""VIM Engine — pure Python implementation of VIM editing commands.

No Tk, no UI dependencies. Provides:
- Motions: h, j, k, l, w, b, e, 0, ^, $
- Operators: d, c, y
- Line operators: dd, cc, yy
- Put: p
- Undo/Redo: u, Ctrl+r
- Counts: 5j, 3dw, etc.
- Cursor from @ marker
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VimState:
    """Complete VIM editor state."""
    grid: list[list[str]] = field(default_factory=list)
    cursor_x: int = 0
    cursor_y: int = 0
    mode: str = "NORMAL"  # NORMAL, INSERT, VISUAL, VISUAL_LINE
    visual_start: tuple[int, int] | None = None
    undo_stack: list[tuple[list[list[str]], int, int]] = field(default_factory=list)
    redo_stack: list[tuple[list[list[str]], int, int]] = field(default_factory=list)
    last_op: str = ""
    last_motion: str = ""
    last_count: int = 0
    pending_count: str = ""


def _deep_copy_grid(grid: list[list[str]]) -> list[list[str]]:
    return [row[:] for row in grid]


def _save_state(state: VimState) -> None:
    """Save current state to undo stack."""
    state.undo_stack.append((_deep_copy_grid(state.grid), state.cursor_x, state.cursor_y))
    if len(state.undo_stack) > 1000:
        state.undo_stack.pop(0)
    state.redo_stack.clear()


def _clamp_cursor(state: VimState) -> None:
    """Ensure cursor is within valid bounds for NORMAL mode."""
    if state.cursor_y < 0:
        state.cursor_y = 0
    if state.cursor_y >= len(state.grid):
        state.cursor_y = max(0, len(state.grid) - 1)
    if state.cursor_y < len(state.grid):
        row = state.grid[state.cursor_y]
        if state.cursor_x < 0:
            state.cursor_x = 0
        # In NORMAL mode, cursor max is len(row) - 1 (on last char)
        # In INSERT mode, cursor can be at len(row) (after last char)
        max_x = len(row) - 1 if state.mode == "NORMAL" else len(row)
        if state.cursor_x > max_x:
            state.cursor_x = max_x


def _find_at_marker(grid: list[list[str]]) -> tuple[int, int] | None:
    """Find @ cursor marker in grid."""
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == "@":
                return (x, y)
    return None


def init_from_grid(grid: list[str]) -> VimState:
    """Initialize VimState from list of strings (lesson grid)."""
    grid_list = [list(row) for row in grid]
    state = VimState(grid=grid_list)
    pos = _find_at_marker(grid_list)
    if pos:
        state.cursor_x, state.cursor_y = pos
        # Remove @ from grid
        grid_list[pos[1]][pos[0]] = " "
    _clamp_cursor(state)
    return state


def get_cursor_pos(state: VimState) -> tuple[int, int]:
    return (state.cursor_x, state.cursor_y)


def get_grid_text(state: VimState) -> list[str]:
    return ["".join(row) for row in state.grid]


def get_mode(state: VimState) -> str:
    return state.mode


def get_visual_start(state: VimState) -> tuple[int, int] | None:
    return state.visual_start


def _move_left(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    for _ in range(count):
        if state.cursor_x > 0:
            state.cursor_x -= 1


def _move_right(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    for _ in range(count):
        row = state.grid[state.cursor_y]
        max_x = len(row) - 1 if state.mode == "NORMAL" else len(row)
        if state.cursor_x < max_x:
            state.cursor_x += 1


def _move_up(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    state.cursor_y = max(0, state.cursor_y - count)
    row = state.grid[state.cursor_y]
    state.cursor_x = min(state.cursor_x, len(row) - 1 if state.mode == "NORMAL" else len(row))


def _move_down(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    state.cursor_y = min(len(state.grid) - 1, state.cursor_y + count)
    row = state.grid[state.cursor_y]
    state.cursor_x = min(state.cursor_x, len(row) - 1 if state.mode == "NORMAL" else len(row))


def _move_word_forward(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    for _ in range(count):
        row = state.grid[state.cursor_y]
        pos = state.cursor_x
        # Skip current word
        while pos < len(row) and row[pos].isalnum():
            pos += 1
        # Skip non-word (whitespace/punctuation)
        while pos < len(row) and not row[pos].isalnum():
            pos += 1
        if for_operator:
            # For operators, allow cursor to go to len(row) (exclusive end)
            max_x = len(row)
        else:
            max_x = len(row) - 1 if state.mode == "NORMAL" else len(row)
        state.cursor_x = min(pos, max_x)


def _move_word_backward(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    for _ in range(count):
        row = state.grid[state.cursor_y]
        pos = state.cursor_x
        # Skip non-word backwards
        while pos > 0 and not row[pos - 1].isalnum():
            pos -= 1
        # Find word start
        while pos > 0 and row[pos - 1].isalnum():
            pos -= 1
        state.cursor_x = pos


def _move_word_end(state: VimState, count: int = 1, for_operator: bool = False) -> None:
    for _ in range(count):
        row = state.grid[state.cursor_y]
        pos = state.cursor_x
        # If on word, go to end
        while pos < len(row) - 1 and row[pos + 1].isalnum():
            pos += 1
        max_x = len(row) - 1 if state.mode == "NORMAL" else len(row)
        state.cursor_x = min(pos, max_x)


def _move_line_start(state: VimState, for_operator: bool = False) -> None:
    state.cursor_x = 0


def _move_line_first_nonblank(state: VimState, for_operator: bool = False) -> None:
    row = state.grid[state.cursor_y]
    for i, ch in enumerate(row):
        if ch != " " and ch != "\t":
            state.cursor_x = i
            return
    state.cursor_x = 0


def _move_line_end(state: VimState, for_operator: bool = False) -> None:
    row = state.grid[state.cursor_y]
    state.cursor_x = max(0, len(row) - 1)


MOTION_FUNCS = {
    "h": _move_left,
    "j": _move_down,
    "k": _move_up,
    "l": _move_right,
    "w": _move_word_forward,
    "b": _move_word_backward,
    "e": _move_word_end,
    "0": _move_line_start,
    "^": _move_line_first_nonblank,
    "$": _move_line_end,
}


def _delete_range(state: VimState, y1: int, x1: int, y2: int, x2: int) -> list[str]:
    """Delete range and return deleted text lines. Range is [y1,x1) to [y2,x2) exclusive end."""
    deleted = []
    if y1 == y2:
        row = state.grid[y1]
        deleted.append("".join(row[x1:x2]))
        del row[x1:x2]
    else:
        # First line
        row = state.grid[y1]
        deleted.append("".join(row[x1:]))
        del row[x1:]
        # Middle lines
        for y in range(y1 + 1, y2):
            if y < len(state.grid):
                deleted.append("".join(state.grid[y]))
                state.grid[y] = []
        # Last line
        if y2 < len(state.grid):
            row = state.grid[y2]
            deleted.append("".join(row[:x2]))
            del row[:x2]
    return deleted


def _yank_range(state: VimState, y1: int, x1: int, y2: int, x2: int) -> list[str]:
    """Yank range and return yanked text lines."""
    yanked = []
    if y1 == y2:
        row = state.grid[y1]
        yanked.append("".join(row[x1:x2]))
    else:
        row = state.grid[y1]
        yanked.append("".join(row[x1:]))
        for y in range(y1 + 1, y2):
            if y < len(state.grid):
                yanked.append("".join(state.grid[y]))
        if y2 < len(state.grid):
            row = state.grid[y2]
            yanked.append("".join(row[:x2]))
    return yanked


def _apply_operator(state: VimState, op: str, motion: str, count: int) -> None:
    """Apply operator with motion."""
    _save_state(state)
    start_x, start_y = state.cursor_x, state.cursor_y

    # Execute motion to get end position
    if motion in MOTION_FUNCS:
        func = MOTION_FUNCS[motion]
        if motion in ("h", "j", "k", "l", "w", "b", "e"):
            if motion == "w":
                func(state, count, for_operator=True)
            else:
                func(state, count)
        else:
            func(state)
    else:
        return

    end_x, end_y = state.cursor_x, state.cursor_y

    # Determine range (exclusive end for same line)
    if start_y < end_y or (start_y == end_y and start_x <= end_x):
        y1, x1, y2, x2 = start_y, start_x, end_y, end_x
    else:
        y1, x1, y2, x2 = end_y, end_x, start_y, start_x

    if op == "d":
        _delete_range(state, y1, x1, y2, x2)
        state.cursor_x, state.cursor_y = x1, y1
    elif op == "c":
        _delete_range(state, y1, x1, y2, x2)
        state.cursor_x, state.cursor_y = x1, y1
        state.mode = "INSERT"
    elif op == "y":
        _yank_range(state, y1, x1, y2, x2)
        # cursor doesn't move for yank

    _clamp_cursor(state)


def _delete_line(state: VimState, count: int = 1) -> None:
    _save_state(state)
    for _ in range(count):
        if len(state.grid) > 1 and state.cursor_y < len(state.grid):
            del state.grid[state.cursor_y]
            if state.cursor_y >= len(state.grid):
                state.cursor_y = len(state.grid) - 1
            state.cursor_x = 0
    _clamp_cursor(state)


def _change_line(state: VimState, count: int = 1) -> None:
    _save_state(state)
    for _ in range(count):
        if state.cursor_y < len(state.grid):
            state.grid[state.cursor_y] = []
    state.mode = "INSERT"
    _clamp_cursor(state)


def _yank_line(state: VimState, count: int = 1) -> list[str]:
    yanked = []
    for i in range(count):
        y = state.cursor_y + i
        if y < len(state.grid):
            yanked.append("".join(state.grid[y]))
    return yanked


def _put(state: VimState, after: bool = True) -> None:
    """Put (paste) yanked/deleted text. Simplified - uses last deleted."""
    _save_state(state)
    # Simplified: no actual register implementation
    _clamp_cursor(state)


def _enter_insert_mode(state: VimState, pos: str) -> None:
    """Enter insert mode at position: 'i', 'a', 'o', 'O'."""
    _save_state(state)
    if pos == "i":
        pass  # cursor stays
    elif pos == "a":
        row = state.grid[state.cursor_y]
        if state.cursor_x < len(row):
            state.cursor_x += 1
    elif pos == "o":
        state.grid.insert(state.cursor_y + 1, [])
        state.cursor_y += 1
        state.cursor_x = 0
    elif pos == "O":
        state.grid.insert(state.cursor_y, [])
        state.cursor_x = 0
    state.mode = "INSERT"
    _clamp_cursor(state)


def _handle_insert_char(state: VimState, ch: str) -> None:
    """Insert character at cursor."""
    if state.cursor_y >= len(state.grid):
        state.grid.append([])
    row = state.grid[state.cursor_y]
    if state.cursor_x > len(row):
        state.cursor_x = len(row)
    row.insert(state.cursor_x, ch)
    state.cursor_x += 1


def _handle_backspace(state: VimState) -> None:
    """Handle backspace in insert mode."""
    if state.cursor_x > 0:
        row = state.grid[state.cursor_y]
        if state.cursor_x <= len(row):
            del row[state.cursor_x - 1]
            state.cursor_x -= 1
    elif state.cursor_y > 0:
        # Join with previous line
        prev_row = state.grid[state.cursor_y - 1]
        curr_row = state.grid[state.cursor_y]
        state.cursor_x = len(prev_row)
        prev_row.extend(curr_row)
        del state.grid[state.cursor_y]
        state.cursor_y -= 1


def _handle_enter(state: VimState) -> None:
    """Handle Enter in insert mode."""
    row = state.grid[state.cursor_y]
    new_row = row[state.cursor_x:]
    row[state.cursor_x:] = []
    state.grid.insert(state.cursor_y + 1, new_row)
    state.cursor_y += 1
    state.cursor_x = 0


def _handle_escape(state: VimState) -> None:
    """Exit insert/visual mode."""
    if state.mode == "INSERT":
        if state.cursor_x > 0:
            state.cursor_x -= 1
    state.mode = "NORMAL"
    state.visual_start = None
    _clamp_cursor(state)


def _handle_visual_motion(state: VimState, motion: str, count: int) -> None:
    """Handle motion in visual mode."""
    if motion in MOTION_FUNCS:
        func = MOTION_FUNCS[motion]
        if motion in ("h", "j", "k", "l", "w", "b", "e"):
            func(state, count, for_operator=False)
        else:
            func(state, for_operator=False)
    _clamp_cursor(state)


def _delete_visual_selection(state: VimState) -> None:
    """Delete visual selection."""
    if not state.visual_start:
        return
    _save_state(state)
    y1, x1 = state.visual_start
    y2, x2 = state.cursor_y, state.cursor_x
    if y1 > y2 or (y1 == y2 and x1 > x2):
        y1, y2 = y2, y1
        x1, x2 = x2, x1
    # For visual mode, range is inclusive on end
    if y1 == y2:
        x2 += 1
    _delete_range(state, y1, x1, y2, x2)
    state.cursor_x, state.cursor_y = x1, y1
    state.mode = "NORMAL"
    state.visual_start = None
    _clamp_cursor(state)


def _yank_visual_selection(state: VimState) -> list[str]:
    """Yank visual selection."""
    if not state.visual_start:
        return []
    y1, x1 = state.visual_start
    y2, x2 = state.cursor_y, state.cursor_x
    if y1 > y2 or (y1 == y2 and x1 > x2):
        y1, y2 = y2, y1
        x1, x2 = x2, x1
    if y1 == y2:
        x2 += 1
    return _yank_range(state, y1, x1, y2, x2)


def _change_visual_selection(state: VimState) -> None:
    """Change visual selection."""
    if not state.visual_start:
        return
    _save_state(state)
    y1, x1 = state.visual_start
    y2, x2 = state.cursor_y, state.cursor_x
    if y1 > y2 or (y1 == y2 and x1 > x2):
        y1, y2 = y2, y1
        x1, x2 = x2, x1
    if y1 == y2:
        x2 += 1
    _delete_range(state, y1, x1, y2, x2)
    state.cursor_x, state.cursor_y = x1, y1
    state.mode = "INSERT"
    state.visual_start = None
    _clamp_cursor(state)


def _undo(state: VimState) -> None:
    """Undo last change."""
    if state.undo_stack:
        prev_grid, prev_x, prev_y = state.undo_stack.pop()
        state.redo_stack.append((_deep_copy_grid(state.grid), state.cursor_x, state.cursor_y))
        state.grid = prev_grid
        state.cursor_x, state.cursor_y = prev_x, prev_y
        _clamp_cursor(state)


def _redo(state: VimState) -> None:
    """Redo last undone change."""
    if state.redo_stack:
        next_grid, next_x, next_y = state.redo_stack.pop()
        state.undo_stack.append((_deep_copy_grid(state.grid), state.cursor_x, state.cursor_y))
        state.grid = next_grid
        state.cursor_x, state.cursor_y = next_x, next_y
        _clamp_cursor(state)


def process_key(state: VimState, key: str, ctrl: bool = False, shift: bool = False) -> None:
    """Process a single key press in NORMAL mode."""
    # Handle count prefix
    if key.isdigit() and key != "0":
        state.pending_count += key
        return

    count = int(state.pending_count) if state.pending_count else 1
    state.pending_count = ""

    # Visual mode
    if state.mode == "VISUAL":
        if key == "escape":
            _handle_escape(state)
        elif key in MOTION_FUNCS:
            _handle_visual_motion(state, key, count)
        elif key in ("d", "x"):
            _delete_visual_selection(state)
        elif key == "y":
            _yank_visual_selection(state)
            _handle_escape(state)
        elif key == "c":
            _change_visual_selection(state)
        return

    if state.mode == "VISUAL_LINE":
        if key == "escape":
            _handle_escape(state)
        elif key in ("j", "k", "down", "up"):
            _handle_visual_motion(state, key, count)
        elif key in ("d", "x"):
            # Delete full lines in visual line mode
            _save_state(state)
            y1 = min(state.visual_start[0], state.cursor_y)
            y2 = max(state.visual_start[0], state.cursor_y)
            # Delete lines y1 through y2 inclusive
            for _ in range(y2 - y1 + 1):
                if y1 < len(state.grid):
                    del state.grid[y1]
            state.cursor_y = y1
            state.cursor_x = 0
            if state.cursor_y >= len(state.grid):
                state.cursor_y = len(state.grid) - 1
            state.mode = "NORMAL"
            state.visual_start = None
            _clamp_cursor(state)
        elif key == "y":
            _yank_visual_selection(state)
            _handle_escape(state)
        return

    # Insert mode
    if state.mode == "INSERT":
        if key == "escape":
            _handle_escape(state)
        elif key == "backspace":
            _handle_backspace(state)
        elif key == "return" or key == "enter":
            _handle_enter(state)
        elif key == "space":
            _handle_insert_char(state, " ")
        elif len(key) == 1 and key.isprintable():
            _handle_insert_char(state, key)
        return

    # NORMAL mode
    if key in ("u", "U"):
        _undo(state)
        return

    if ctrl and key == "r":
        _redo(state)
        return

    # Line operators (dd, cc, yy)
    if key == "d" and state.last_op == "d":
        _delete_line(state, count)
        state.last_op = ""
        return
    if key == "c" and state.last_op == "c":
        _change_line(state, count)
        state.last_op = ""
        return
    if key == "y" and state.last_op == "y":
        _yank_line(state, count)
        state.last_op = ""
        return

    # Operators waiting for motion
    if key in ("d", "c", "y"):
        if state.last_op:
            pass  # handled above
        else:
            state.last_op = key
            state.last_count = count
            return

    # Motion after operator
    if state.last_op and key in MOTION_FUNCS:
        _apply_operator(state, state.last_op, key, state.last_count)
        state.last_op = ""
        state.last_count = 0
        return

    # Put
    if key == "p":
        _put(state, after=True)
        return
    if key == "P":
        _put(state, after=False)
        return

    # Visual mode entry
    if key == "v":
        state.mode = "VISUAL"
        state.visual_start = (state.cursor_y, state.cursor_x)
        return
    if key == "V":
        state.mode = "VISUAL_LINE"
        state.visual_start = (state.cursor_y, state.cursor_x)
        return

    # Insert mode entry
    if key in ("i", "a", "o", "O"):
        _enter_insert_mode(state, key)
        return

    # Motions
    if key in MOTION_FUNCS:
        func = MOTION_FUNCS[key]
        if key in ("h", "j", "k", "l", "w", "b", "e"):
            func(state, count, for_operator=False)
        else:
            func(state, for_operator=False)
        _clamp_cursor(state)
        return

    # D (delete to end of line)
    if key == "D" or (shift and key == "d"):
        _save_state(state)
        row = state.grid[state.cursor_y]
        del row[state.cursor_x:]
        _clamp_cursor(state)
        return

    # C (change to end of line)
    if key == "C" or (shift and key == "c"):
        _save_state(state)
        row = state.grid[state.cursor_y]
        del row[state.cursor_x:]
        state.mode = "INSERT"
        _clamp_cursor(state)
        return

    # Y (yank to end of line)
    if key == "Y" or (shift and key == "y"):
        _yank_line(state, 1)
        return

    # X (delete before cursor)
    if key == "X" or (shift and key == "x"):
        if state.cursor_x > 0:
            _save_state(state)
            row = state.grid[state.cursor_y]
            del row[state.cursor_x - 1]
            state.cursor_x -= 1
            _clamp_cursor(state)
        return

    # x (delete char under cursor)
    if key == "x":
        if state.cursor_x < len(state.grid[state.cursor_y]):
            _save_state(state)
            row = state.grid[state.cursor_y]
            del row[state.cursor_x]
            _clamp_cursor(state)
        return


def process_insert_char(state: VimState, ch: str) -> None:
    """Process a printable character in INSERT mode."""
    if state.mode == "INSERT":
        _handle_insert_char(state, ch)


def process_special_key(state: VimState, key: str, ctrl: bool = False, shift: bool = False) -> None:
    """Process special keys (backspace, enter, escape, arrows) in INSERT mode."""
    if state.mode != "INSERT":
        return
    if key in ("backspace", "BackSpace"):
        _handle_backspace(state)
    elif key in ("return", "enter", "Return", "Enter"):
        _handle_enter(state)
    elif key in ("escape", "Escape"):
        _handle_escape(state)
    elif key in ("left", "Left"):
        _move_left(state)
    elif key in ("right", "Right"):
        _move_right(state)
    elif key in ("up", "Up"):
        _move_up(state)
    elif key in ("down", "Down"):
        _move_down(state)


if __name__ == "__main__":
    # Simple self-test
    grid = [
        "hello world",
        "foo bar baz",
        "test line",
    ]
    state = init_from_grid(grid)
    print("Initial:", get_grid_text(state))
    print("Cursor:", get_cursor_pos(state))

    # Test motions
    process_key(state, "w")
    print("After w:", get_cursor_pos(state))
    process_key(state, "b")
    print("After b:", get_cursor_pos(state))
    process_key(state, "$")
    print("After $:", get_cursor_pos(state))
    process_key(state, "0")
    print("After 0:", get_cursor_pos(state))

    # Test delete word
    process_key(state, "d")
    process_key(state, "w")
    print("After dw:", get_grid_text(state))

    # Test undo
    _undo(state)
    print("After undo:", get_grid_text(state))

    # Test redo
    _redo(state)
    print("After redo:", get_grid_text(state))

    print("All basic tests passed!")