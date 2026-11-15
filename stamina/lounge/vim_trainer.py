"""VIM Trainer — interactive VIM editor tutorial game for the Lounge.

Teaches VIM motions, edits, and modes through progressive challenges.
Inspired by Vim Adventures, PacVim, and VIM Master.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, PANEL, PURPLE, RED, TEXT, blend, px

from .base import GameShell
from . import store


# ─── Lesson Data ──────────────────────────────────────────────────────────────

LESSONS = [
    {
        "id": "motion_basic",
        "title": _t("Урок 1: Базовые движения"),
        "keys": "h j k l",
        "desc": _t("В VIM курсор двигается клавишами h/j/k/l (не стрелками!). Это основа."),
        "target": "MOVE_CURSOR",
        "grid": [
            "........",
            ".@......",
            "........",
        ],
        "goal_pos": (7, 1),
        "hint": _t("Задание: дойди курсором (@) до правого края строки. Нажимай l."),
        "tasks": [
            _t("1. Нажми l 7 раз — курсор дойдёт до конца"),
            _t("2. Попробуй h — вернёшься назад"),
            _t("3. j/k — вверх/вниз (пока одна строка)"),
        ],
    },
    {
        "id": "motion_word",
        "title": _t("Урок 2: Словесные движения"),
        "keys": "w b e",
        "desc": _t("w — к началу следующего слова, b — к началу предыдущего, e — к концу слова."),
        "target": "WORD_MOTION",
        "grid": [
            "the quick brown fox",
            " jumps over the lazy",
            " dog...............",
        ],
        "word_targets": [(3, 0), (9, 0), (15, 0), (5, 1), (10, 1), (14, 1), (4, 2)],
        "hint": _t("Задание: посети все начала слов (w) и концы слов (e)."),
        "tasks": [
            _t("1. Нажми w — прыгни на 'quick' (позиция 4)"),
            _t("2. Ещё w — на 'brown' (10), ещё — на 'fox' (16)"),
            _t("3. Нажми b — вернёшься к началу слова"),
            _t("4. Нажми e — прыгни к концу текущего слова"),
            _t("5. Посети все 7 целей на трёх строках"),
        ],
    },
    {
        "id": "motion_line",
        "title": _t("Урок 3: Строчные движения"),
        "keys": "0 ^ $",
        "desc": _t("0 — абсолютное начало строки, ^ — первый не-пробел, $ — конец строки."),
        "target": "LINE_MOTION",
        "grid": [
            "   indented line",
            "another line here",
            "  third line    ",
        ],
        "line_targets": [(0, 0), (3, 0), (15, 0), (0, 1), (16, 1), (2, 2), (12, 2)],
        "hint": _t("Задание: попробуй 0, ^, $ на каждой из трёх строк."),
        "tasks": [
            _t("1. Строка 1: нажми 0 (позиция 0), потом ^ (позиция 3 — 'i'), потом $ (15)"),
            _t("2. Строка 2: 0 (0), ^ (0), $ (16)"),
            _t("3. Строка 3: 0 (0), ^ (2 — 't'), $ (12)"),
            _t("4. Посети все 7 целей"),
        ],
    },
    {
        "id": "delete_char",
        "title": _t("Урок 4: Удаление символов"),
        "keys": "x X",
        "desc": _t("x — удалить символ ПОД курсором, X — удалить символ ПЕРЕД курсором (Shift+x)."),
        "target": "DELETE_CHAR",
        "grid": [
            "delete_me",
            "xXxXxXxXx",
            "........",
        ],
        "delete_targets": [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0)],
        "hint": _t("Задание: удали все буквы в первой строке (x). Вторая строка — подсказка."),
        "tasks": [
            _t("1. Курсор на 'd' — нажми x, буква исчезнет"),
            _t("2. Ещё x — удалит 'e', и так далее до конца слова"),
            _t("3. X (Shift+x) удаляет ПЕРЕД курсором — полезно, если проехал"),
            _t("4. Очисти первую строку полностью"),
        ],
    },
    {
        "id": "delete_word",
        "title": _t("Урок 5: Удаление слов"),
        "keys": "dw db de",
        "desc": _t("dw — удалить слово (от курсора до следующего), db — назад, de — до конца слова."),
        "target": "DELETE_WORD",
        "grid": [
            "remove these words please",
            "..........................",
            "..........................",
        ],
        "hint": _t("Задание: удали все слова на первой строке командой dw."),
        "tasks": [
            _t("1. Курсор в начале строки — нажми dw, удалится 'remove '"),
            _t("2. Ещё dw — 'these ', ещё — 'words ', ещё — 'please'"),
            _t("3. db удаляет слово НАЗАД (курсор в середине слова)"),
            _t("4. de удаляет от курсора до КОНЦА слова"),
            _t("5. Очисти первую строку полностью"),
        ],
    },
    {
        "id": "delete_line",
        "title": _t("Урок 6: Удаление строк"),
        "keys": "dd D",
        "desc": _t("dd — удалить ЦЕЛУЮ строку, D — удалить от курсора до конца строки."),
        "target": "DELETE_LINE",
        "grid": [
            "line one",
            "line two",
            "line three",
            "line four",
        ],
        "hint": _t("Задание: удали вторую и третью строки (dd на каждой)."),
        "tasks": [
            _t("1. Спустись на вторую строку (j)"),
            _t("2. Нажми dd — строка 'line two' исчезнет"),
            _t("3. Снова j (теперь это бывшая строка 3) — нажми dd"),
            _t("4. D удаляет только ХВОСТ строки от курсора"),
            _t("5. Остаются только первая и последняя строки"),
        ],
    },
    {
        "id": "change_mode",
        "title": _t("Урок 7: Режим вставки"),
        "keys": "i a o O",
        "desc": _t("i — вставить ПЕРЕД курсором, a — ПОСЛЕ, o — новая строка НИЖЕ, O — ВЫШЕ."),
        "target": "INSERT_MODE",
        "grid": [
            "hello world",
            "...........",
            "...........",
        ],
        "insert_tasks": [
            {"pos": (5, 0), "mode": "i", "text": " beautiful", "desc": _t("i перед пробелом → 'hello beautiful world'")},
            {"pos": (11, 0), "mode": "a", "text": "!", "desc": _t("a после 'd' → 'world!'")},
            {"pos": (0, 1), "mode": "o", "text": "new line below", "desc": _t("o на пустой строке → новая строка ниже")},
        ],
        "hint": _t("Задание: выполни 3 вставки: i, a, o. Esc — выход в NORMAL."),
        "tasks": [
            _t("1. Курсор на пробел (позиция 5) — нажми i, введи ' beautiful', Esc"),
            _t("2. Курсор на 'd' (позиция 11) — нажми a, введи '!', Esc"),
            _t("3. На пустой строке 2 — нажми o, введи 'new line below', Esc"),
            _t("4. O создаёт строку ВЫШЕ текущей"),
        ],
    },
    {
        "id": "change_operator",
        "title": _t("Урок 8: Оператор изменения"),
        "keys": "cw cb ce cc C",
        "desc": _t("c = change (удалить + войти в INSERT). cw — слово, cc — строка, C — до конца строки."),
        "target": "CHANGE_OPERATOR",
        "grid": [
            "replace this word",
            "change whole line",
            ".................",
        ],
        "hint": _t("Задание: замени 'this word' на 'it' (cw), вторую строку целиком (cc)."),
        "tasks": [
            _t("1. Курсор на 't' слова 'this' — нажми cw, введи 'it', Esc"),
            _t("2. Спустись на строку 2 (j) — нажми cc, введи 'new line', Esc"),
            _t("3. C = c$ — изменить от курсора до конца строки"),
            _t("4. cb/ce — назад/до конца слова (редко нужны)"),
        ],
    },
    {
        "id": "visual_mode",
        "title": _t("Урок 9: Визуальный режим"),
        "keys": "v V",
        "desc": _t("v — посимвольное выделение, V — построчное. Выделил → d/y/c."),
        "target": "VISUAL_MODE",
        "grid": [
            "select this text",
            "and delete it",
            "..............",
        ],
        "hint": _t("Задание: выдели 'this text' (v + llll), удали (d). Потом строку 2 (V + d)."),
        "tasks": [
            _t("1. Курсор на 't' слова 'this' — нажми v (вход в VISUAL)"),
            _t("2. Нажимай l 8 раз — выделится 'this text'"),
            _t("3. Нажми d — выделенное удалится"),
            _t("4. Спустись на строку 2 — нажми V (VISUAL LINE)"),
            _t("5. Нажми d — вся строка удалится"),
            _t("6. y — копировать (yank), c — изменить"),
        ],
    },
    {
        "id": "search_replace",
        "title": _t("Урок 10: Поиск и замена"),
        "keys": "/ n N * # :s",
        "desc": _t("/pattern — поиск вперёд, ? — назад. n/N — следующее/предыдущее. * — слово под курсором. :s — замена."),
        "target": "SEARCH_REPLACE",
        "grid": [
            "find the word vim here",
            "vim is powerful vim",
            "......................",
        ],
        "hint": _t("Задание: найди все 3 вхождения 'vim' (/vim → n → n)."),
        "tasks": [
            _t("1. Нажми /, введи 'vim', Enter — курсор прыгнет на первое 'vim'"),
            _t("2. Нажми n — прыжок на второе 'vim' (строка 2)"),
            _t("3. Ещё n — на третье 'vim' (конец строки 2)"),
            _t("4. N — назад по совпадениям"),
            _t("5. * — мгновенный поиск слова ПОД курсором"),
            _t("6. :s/old/new/g — замена в строке (в тренажере упрощено)"),
        ],
    },
    {
        "id": "undo_redo",
        "title": _t("Урок 11: Отмена и возврат"),
        "keys": "u Ctrl+r",
        "desc": _t("u — отменить последнее ИЗМЕНЕНИЕ (не движение!). Ctrl+r — вернуть отменённое."),
        "target": "UNDO_REDO",
        "grid": [
            "make a mistake",
            "then fix it",
            "..............",
        ],
        "hint": _t("Задание: сделай изменение (x или dw), нажми u — вернётся. Ctrl+r — снова уйдёт."),
        "tasks": [
            _t("1. Нажми x — удалит 'm' в 'make'"),
            _t("2. Нажми u — 'm' вернётся (отмена)"),
            _t("3. Нажми Ctrl+r — 'm' снова исчезнет (возврат)"),
            _t("4. u работает с ЛЮБЫМ изменением: x, dw, dd, cw, p, ..."),
            _t("5. Дерево отмен в VIM — мощнейшая фишка"),
        ],
    },
    {
        "id": "repeat_count",
        "title": _t("Урок 12: Повторители (каунтеры)"),
        "keys": "5j 3dw 2dd 10x",
        "desc": _t("Число ПЕРЕД командой = повтор: 5j = jjjjj, 3dw = 3 раза dw, 2dd = 2 строки."),
        "target": "REPEAT_COUNT",
        "grid": [
            "........",
            "........",
            "........",
            "........",
            "........",
            "@.......",
        ],
        "hint": _t("Задание: с нижней строки — 5k (вверх 5), потом 3l (вправо 3)."),
        "tasks": [
            _t("1. Ты на строке 5 (индекс 5) — нажми 5k, окажешься на строке 0"),
            _t("2. Нажми 3l — курсор сдвинется на 3 вправо"),
            _t("3. 2dd — удалит 2 строки подряд"),
            _t("4. 10x — удалит 10 символов"),
            _t("5. Работает с ПОЧТИ ВСЕМИ командами движения и изменения"),
        ],
    },
]


def lesson_key() -> str:
    return _t("h/j/k/l движение · w/b/e слова · 0/^/$ строки · x/dw/dd удаление · i/a/o вставка · cw/cc замена · v/V выделение · / поиск · u/Ctrl+r отмена · 5j счетчики")


# ─── VIM Trainer Game ────────────────────────────────────────────────────────

class VimTrainerGame(GameShell):
    game_id = "vim_trainer"
    title = _t("VIM ТРЕНАЖЁР · УЧИ КОМАНДЫ")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.lesson_idx = 0
        self.cursor = [1, 1]  # x, y в сетке уроков
        self.grid_data: list[str] = []
        self.cell_w = 18
        self.cell_h = 22
        self.mode = "NORMAL"  # NORMAL, INSERT, VISUAL, COMMAND
        self.visual_start: tuple[int, int] | None = None
        self.command_buffer = ""
        self.message = ""
        self.message_color = AMBER
        self.completed_lessons: set[int] = set()
        # Tracking for special lessons
        self._vim_found_count = 0
        self._did_undo_redo = False
        self._used_count = False
        self.load_progress()
        self._load_lesson(0)
        self.set_hint(lesson_key())

    def load_progress(self) -> None:
        data = store.load()
        vim_data = data.get("vim_trainer", {})
        self.completed_lessons = set(vim_data.get("completed", []))

    def save_progress(self) -> None:
        data = store.load()
        data["vim_trainer"] = {"completed": list(self.completed_lessons)}
        store.save(data)

    def _load_lesson(self, idx: int) -> None:
        if idx < 0 or idx >= len(LESSONS):
            return
        self.lesson_idx = idx
        lesson = LESSONS[idx]
        self.grid_data = [list(row) for row in lesson["grid"]]
        self.cursor = [1, 1]
        self.mode = "NORMAL"
        self.visual_start = None
        self.command_buffer = ""
        self.message = lesson.get("hint", "")
        self.message_color = AMBER
        self.title = lesson["title"]
        self.lbl_title.configure(text=self.title)

    def tick_ms(self) -> int:
        return 100

    def tick(self) -> None:
        pass

    def reset(self) -> None:
        self.lesson_idx = 0
        self.completed_lessons.clear()
        self.save_progress()
        self._load_lesson(0)
        self.set_score(0)

    def on_key(self, e: tk.Event) -> None:
        k = e.keysym.lower()
        state = getattr(e, "state", 0) or 0
        ctrl = bool(state & 0x4)
        shift = bool(state & 0x1)

        if self.mode == "INSERT":
            self._handle_insert(k, e)
            return
        if self.mode == "VISUAL":
            self._handle_visual(k)
            return
        if self.mode == "COMMAND":
            self._handle_command(k, e)
            return

        # NORMAL mode
        self._handle_normal(k, ctrl, shift)

    def _handle_normal(self, k: str, ctrl: bool, shift: bool) -> None:
        lesson = LESSONS[self.lesson_idx]
        target = lesson["target"]
        moved = False

        # Movement
        if k in ("h", "left"):
            self.cursor[0] = max(0, self.cursor[0] - 1)
            moved = True
        elif k in ("j", "down"):
            self.cursor[1] = min(len(self.grid_data) - 1, self.cursor[1] + 1)
            moved = True
        elif k in ("k", "up"):
            self.cursor[1] = max(0, self.cursor[1] - 1)
            moved = True
        elif k in ("l", "right"):
            row_len = len(self.grid_data[self.cursor[1]])
            self.cursor[0] = min(row_len - 1, self.cursor[0] + 1)
            moved = True

        # Word motions
        elif k == "w":
            self._move_word_forward()
            moved = True
        elif k == "b":
            self._move_word_backward()
            moved = True
        elif k == "e":
            self._move_word_end()
            moved = True

        # Line motions
        elif k == "0":
            self.cursor[0] = 0
            moved = True
        elif k == "^":
            row = self.grid_data[self.cursor[1]]
            for i, ch in enumerate(row):
                if ch != " " and ch != ".":
                    self.cursor[0] = i
                    break
            moved = True
        elif k == "$":
            row = self.grid_data[self.cursor[1]]
            self.cursor[0] = len(row) - 1
            moved = True

        # Deletions
        elif k == "x":
            self._delete_char()
        elif k == "X" or (shift and k == "x"):
            if self.cursor[0] > 0:
                self.cursor[0] -= 1
                self._delete_char()

        # Operators (simplified - immediate action)
        elif k == "d":
            self._start_operator("d")
        elif k == "c":
            self._start_operator("c")
        elif k == "y":
            self._start_operator("y")

        # Insert mode entry
        elif k == "i":
            self.mode = "INSERT"
            self.message = _t("РЕЖИМ ВСТАВКИ — пиши текст, Esc для выхода")
            self.message_color = GREEN
        elif k == "a":
            self.cursor[0] = min(len(self.grid_data[self.cursor[1]]) - 1, self.cursor[0] + 1)
            self.mode = "INSERT"
            self.message = _t("РЕЖИМ ВСТАВКИ (после курсора) — Esc для выхода")
            self.message_color = GREEN
        elif k == "o":
            self._open_line_below()
        elif k == "O":
            self._open_line_above()

        # Visual mode
        elif k == "v":
            self.mode = "VISUAL"
            self.visual_start = tuple(self.cursor)
            self.message = _t("ВИЗУАЛЬНЫЙ РЕЖИМ — выдели, потом d/y/c")
            self.message_color = PURPLE
        elif k == "V":
            self.mode = "VISUAL_LINE"
            self.visual_start = tuple(self.cursor)
            self.message = _t("ВИЗУАЛЬНЫЙ РЕЖИМ (СТРОКИ) — выдели, потом d/y/c")
            self.message_color = PURPLE

        # Search
        elif k == "/":
            self.mode = "COMMAND"
            self.command_buffer = "/"
            self.message = _t("ПОИСК: введи паттерн, Enter")
            self.message_color = CYAN
        elif k == "?":
            self.mode = "COMMAND"
            self.command_buffer = "?"
            self.message = _t("ПОИСК НАЗАД: введи паттерн, Enter")
            self.message_color = CYAN
        elif k == "n":
            # Next search result
            if hasattr(self, "_last_search") and self._last_search:
                self._search(self._last_search)
        elif k == "N":
            # Previous search result - simplified
            if hasattr(self, "_last_search") and self._last_search:
                self.message = _t("N — поиск назад (упрощено)")
                self.message_color = MUTED

        # Undo/Redo
        elif k == "u":
            self._did_undo_redo = True
            self.message = _t("Отмена (u) — сделано! Попробуй Ctrl+r для возврата")
            self.message_color = GREEN
        elif ctrl and k == "r":
            self._did_undo_redo = True
            self.message = _t("Возврат (Ctrl+r) — сделано! u / Ctrl+r работают парой")
            self.message_color = GREEN

        # Repeat counts
        elif k.isdigit() and k != "0":
            self._used_count = True
            self.message = _t("Счетчик {0}... нажми команду (j/k/l/h/dw/dd)").format(k)
            self.message_color = AMBER

        # Next/prev lesson
        elif k == "n" and ctrl:
            self._next_lesson()
        elif k == "p" and ctrl:
            self._prev_lesson()

        # Check lesson completion
        if moved:
            self._check_lesson_complete()

        self.redraw()

    def _handle_insert(self, k: str, e: tk.Event) -> None:
        if k == "escape":
            self.mode = "NORMAL"
            self.message = _t("Выйшли в NORMAL режим")
            self.message_color = AMBER
        elif k == "backspace":
            if self.cursor[0] > 0:
                row = self.grid_data[self.cursor[1]]
                if self.cursor[0] <= len(row):
                    del row[self.cursor[0] - 1]
                    self.cursor[0] -= 1
        elif k == "return":
            self._open_line_below()
        elif k == "space":
            row = self.grid_data[self.cursor[1]]
            row.insert(self.cursor[0], " ")
            self.cursor[0] += 1
        elif len(k) == 1 and k.isprintable():
            row = self.grid_data[self.cursor[1]]
            row.insert(self.cursor[0], k)
            self.cursor[0] += 1
        self.redraw()

    def _handle_visual(self, k: str) -> None:
        if k == "escape":
            self.mode = "NORMAL"
            self.visual_start = None
            self.message = _t("Выйшли из визуального режима")
            self.message_color = AMBER
        elif k in ("h", "left"):
            self.cursor[0] = max(0, self.cursor[0] - 1)
        elif k in ("j", "down"):
            self.cursor[1] = min(len(self.grid_data) - 1, self.cursor[1] + 1)
        elif k in ("k", "up"):
            self.cursor[1] = max(0, self.cursor[1] - 1)
        elif k in ("l", "right"):
            row_len = len(self.grid_data[self.cursor[1]])
            self.cursor[0] = min(row_len - 1, self.cursor[0] + 1)
        elif k in ("d", "x"):
            self._delete_visual_selection()
        elif k == "y":
            self.message = _t("Скопировано (y) — в тренажере упрощено")
            self.mode = "NORMAL"
            self.visual_start = None
        elif k == "c":
            self._delete_visual_selection()
            self.mode = "INSERT"
            self.message = _t("РЕЖИМ ВСТАВКИ — пиши текст")
            self.message_color = GREEN
        self.redraw()

    def _handle_command(self, k: str, e: tk.Event) -> None:
        if k == "escape":
            self.mode = "NORMAL"
            self.command_buffer = ""
            self.message = _t("Отмена поиска")
            self.message_color = MUTED
        elif k == "return":
            if self.command_buffer.startswith("/"):
                pattern = self.command_buffer[1:]
                self._last_search = pattern
                self._search(pattern)
            elif self.command_buffer.startswith("?"):
                pattern = self.command_buffer[1:]
                self._last_search = pattern
                # Backward search - simplified
                self._search(pattern)
            self.mode = "NORMAL"
            self.command_buffer = ""
        elif k == "backspace":
            self.command_buffer = self.command_buffer[:-1]
        elif len(k) == 1 and k.isprintable():
            self.command_buffer += k
        self.message = f":{self.command_buffer}"
        self.message_color = CYAN
        self.redraw()

    # ─── Movement helpers ──────────────────────────────────────────────────

    def _move_word_forward(self) -> None:
        row = self.grid_data[self.cursor[1]]
        pos = self.cursor[0]
        # skip current word
        while pos < len(row) and row[pos].isalnum():
            pos += 1
        # skip spaces
        while pos < len(row) and not row[pos].isalnum():
            pos += 1
        # find next word start
        while pos < len(row) and not row[pos].isalnum():
            pos += 1
        self.cursor[0] = min(pos, len(row) - 1)

    def _move_word_backward(self) -> None:
        row = self.grid_data[self.cursor[1]]
        pos = self.cursor[0]
        # skip spaces
        while pos > 0 and not row[pos - 1].isalnum():
            pos -= 1
        # find word start
        while pos > 0 and row[pos - 1].isalnum():
            pos -= 1
        self.cursor[0] = pos

    def _move_word_end(self) -> None:
        row = self.grid_data[self.cursor[1]]
        pos = self.cursor[0]
        # if on word, go to end
        while pos < len(row) - 1 and row[pos + 1].isalnum():
            pos += 1
        self.cursor[0] = pos

    # ─── Edit operations ───────────────────────────────────────────────────

    def _delete_char(self) -> None:
        row = self.grid_data[self.cursor[1]]
        if self.cursor[0] < len(row):
            del row[self.cursor[0]]

    def _delete_word(self) -> None:
        row = self.grid_data[self.cursor[1]]
        start = self.cursor[0]
        end = start
        while end < len(row) and row[end].isalnum():
            end += 1
        while end < len(row) and not row[end].isalnum():
            end += 1
        del row[start:end]

    def _delete_line(self) -> None:
        if len(self.grid_data) > 1:
            del self.grid_data[self.cursor[1]]
            if self.cursor[1] >= len(self.grid_data):
                self.cursor[1] = len(self.grid_data) - 1
            self.cursor[0] = 0

    def _start_operator(self, op: str) -> None:
        self.message = _t("Оператор {0} — в тренажере сразу: dw/db/de/dd").format(op)
        self.message_color = AMBER

    def _open_line_below(self) -> None:
        self.grid_data.insert(self.cursor[1] + 1, [])
        self.cursor[1] += 1
        self.cursor[0] = 0

    def _open_line_above(self) -> None:
        self.grid_data.insert(self.cursor[1], [])
        self.cursor[0] = 0

    def _delete_visual_selection(self) -> None:
        if not self.visual_start:
            return
        y1, x1 = self.visual_start
        y2, x2 = self.cursor[1], self.cursor[0]
        if y1 > y2 or (y1 == y2 and x1 > x2):
            y1, y2 = y2, y1
            x1, x2 = x2, x1
        if y1 == y2:
            row = self.grid_data[y1]
            del row[x1:x2 + 1]
        else:
            # multi-line: simplify
            for y in range(y1, y2 + 1):
                if y < len(self.grid_data):
                    self.grid_data[y] = []
        self.mode = "NORMAL"
        self.visual_start = None

    def _search(self, pattern: str) -> None:
        if not pattern:
            return
        found = False
        count = 0
        for y in range(self.cursor[1], len(self.grid_data)):
            row = "".join(self.grid_data[y])
            start = self.cursor[0] if y == self.cursor[1] else 0
            idx = row.find(pattern, start)
            if idx >= 0:
                count += 1
                if not found:
                    self.cursor[1] = y
                    self.cursor[0] = idx
                    found = True
        if not found:
            for y in range(0, self.cursor[1]):
                row = "".join(self.grid_data[y])
                idx = row.find(pattern)
                if idx >= 0:
                    count += 1
                    if not found:
                        self.cursor[1] = y
                        self.cursor[0] = idx
                        found = True
        if found:
            self._vim_found_count += count
            self.message = _t("Найдено: {0} (всего найдено: {1})").format(pattern, self._vim_found_count)
            self.message_color = GREEN
        else:
            self.message = _t("Не найдено: {0}").format(pattern)
            self.message_color = RED

    def _check_lesson_complete(self) -> None:
        lesson = LESSONS[self.lesson_idx]
        target = lesson["target"]

        if target == "MOVE_CURSOR" and "goal_pos" in lesson:
            gx, gy = lesson["goal_pos"]
            if self.cursor[0] >= gx and self.cursor[1] == gy:
                self._complete_lesson()

        elif target == "WORD_MOTION" and "word_targets" in lesson:
            targets = set(lesson["word_targets"])
            if tuple(self.cursor) in targets:
                targets.discard(tuple(self.cursor))
                lesson["word_targets"] = list(targets)
                if not targets:
                    self._complete_lesson()

        elif target == "LINE_MOTION" and "line_targets" in lesson:
            targets = set(lesson["line_targets"])
            if tuple(self.cursor) in targets:
                targets.discard(tuple(self.cursor))
                lesson["line_targets"] = list(targets)
                if not targets:
                    self._complete_lesson()

        elif target == "DELETE_CHAR" and "delete_targets" in lesson:
            targets = set(lesson["delete_targets"])
            row = self.grid_data[0]
            # Check if all target positions are now empty (deleted)
            all_deleted = True
            for tx, ty in targets:
                if ty < len(self.grid_data) and tx < len(self.grid_data[ty]):
                    if self.grid_data[ty][tx] != " " and self.grid_data[ty][tx] != ".":
                        all_deleted = False
                        break
            if all_deleted:
                self._complete_lesson()

        elif target == "DELETE_WORD":
            # Check if first line is empty (only dots/spaces)
            row0 = "".join(self.grid_data[0]) if self.grid_data else ""
            if not any(c.isalnum() for c in row0):
                self._complete_lesson()

        elif target == "DELETE_LINE":
            # Check if lines 1 and 2 (original) are gone - now only 2 lines remain
            if len(self.grid_data) <= 2:
                self._complete_lesson()

        elif target == "INSERT_MODE" and "insert_tasks" in lesson:
            # Check if all insert tasks are done - simplified: check grid has expected content
            row0 = "".join(self.grid_data[0]) if len(self.grid_data) > 0 else ""
            row1 = "".join(self.grid_data[1]) if len(self.grid_data) > 1 else ""
            if "beautiful" in row0 and "!" in row0 and "new line below" in row1:
                self._complete_lesson()

        elif target == "CHANGE_OPERATOR":
            row0 = "".join(self.grid_data[0]) if len(self.grid_data) > 0 else ""
            row1 = "".join(self.grid_data[1]) if len(self.grid_data) > 1 else ""
            if "it" in row0 and "new line" in row1:
                self._complete_lesson()

        elif target == "VISUAL_MODE":
            # Check if first line has "select " removed and second line gone
            row0 = "".join(self.grid_data[0]) if len(self.grid_data) > 0 else ""
            if "select" not in row0 and len(self.grid_data) <= 2:
                self._complete_lesson()

        elif target == "SEARCH_REPLACE":
            # Check if all 3 'vim' occurrences were found (tracked via searches)
            # Simplified: if user searched for vim at least once
            if hasattr(self, "_vim_found_count") and self._vim_found_count >= 3:
                self._complete_lesson()

        elif target == "UNDO_REDO":
            # Check if user did undo/redo - track via attribute
            if hasattr(self, "_did_undo_redo") and self._did_undo_redo:
                self._complete_lesson()

        elif target == "REPEAT_COUNT":
            # Check if user used count (5k from bottom row or similar)
            if hasattr(self, "_used_count") and self._used_count:
                self._complete_lesson()

    def _complete_lesson(self) -> None:
        if self.lesson_idx not in self.completed_lessons:
            self.completed_lessons.add(self.lesson_idx)
            self.save_progress()
            self.add_score(100)
            self.message = _t("Урок пройден! Ctrl+n — следующий урок")
            self.message_color = GREEN

    def _next_lesson(self) -> None:
        if self.lesson_idx + 1 < len(LESSONS):
            self._load_lesson(self.lesson_idx + 1)
        else:
            self.message = _t("Все уроки пройдены! Отличная работа!")
            self.message_color = GREEN

    def _prev_lesson(self) -> None:
        if self.lesson_idx > 0:
            self._load_lesson(self.lesson_idx - 1)

    # ─── Rendering ──────────────────────────────────────────────────────────

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)
        c.create_rectangle(0, 0, w, h, fill=BG2, outline="")

        lesson = LESSONS[self.lesson_idx]

        # Left panel: grid
        grid_w = min(px(520), w - px(320))
        start_x = px(20)
        start_y = px(20)

        for y, row in enumerate(self.grid_data):
            for x, ch in enumerate(row):
                cx = start_x + x * self.cell_w
                cy = start_y + y * self.cell_h

                if cx + self.cell_w > start_x + grid_w:
                    continue

                # Cell background
                is_cursor = (x == self.cursor[0] and y == self.cursor[1])
                is_visual = False
                if self.visual_start:
                    vy, vx = self.visual_start
                    y1, x1 = min(vy, y), min(vx, x)
                    y2, x2 = max(vy, y), max(vx, x)
                    if y1 <= y <= y2:
                        if y1 == y2:
                            is_visual = x1 <= x <= x2
                        else:
                            if y == y1:
                                is_visual = x >= x1
                            elif y == y2:
                                is_visual = x <= x2
                            else:
                                is_visual = True

                if is_cursor:
                    fill = CYAN
                elif is_visual:
                    fill = blend(PURPLE, BG2, 0.5)
                elif ch == ".":
                    fill = blend(BG2, MUTED, 0.3)
                else:
                    fill = PANEL

                c.create_rectangle(cx, cy, cx + self.cell_w, cy + self.cell_h,
                                   fill=fill, outline=blend(fill, TEXT, 0.3))

                # Character
                if ch != "." and ch != " ":
                    color = TEXT if not is_cursor else BG
                    c.create_text(cx + self.cell_w // 2, cy + self.cell_h // 2,
                                  text=ch, fill=color, font=theme.font(11, True, mono=True))
                elif is_cursor:
                    c.create_text(cx + self.cell_w // 2, cy + self.cell_h // 2,
                                  text="@", fill=BG, font=theme.font(11, True, mono=True))

        # Right panel: hints & tasks
        panel_x = start_x + grid_w + px(16)
        panel_w = w - panel_x - px(20)
        if panel_w > px(180):
            # Lesson title & desc
            c.create_text(panel_x, start_y, text=lesson["title"], fill=AMBER,
                          anchor="nw", font=theme.font(13, True), width=panel_w)
            c.create_text(panel_x, start_y + px(30), text=lesson["desc"], fill=TEXT,
                          anchor="nw", font=theme.font(10), width=panel_w)

            # Keys
            c.create_text(panel_x, start_y + px(65), text=_t("Клавиши урока: {0}").format(lesson["keys"]), fill=CYAN,
                          anchor="nw", font=theme.font(10, True), width=panel_w)

            # Main hint
            c.create_text(panel_x, start_y + px(95), text=lesson["hint"], fill=GREEN,
                          anchor="nw", font=theme.font(10, True), width=panel_w)

            # Tasks
            tasks = lesson.get("tasks", [])
            if tasks:
                ty = start_y + px(135)
                c.create_text(panel_x, ty, text=_t("Задания:"), fill=AMBER,
                              anchor="nw", font=theme.font(10, True))
                for i, task in enumerate(tasks):
                    c.create_text(panel_x + px(10), ty + px(22) + i * px(20), text=task, fill=TEXT,
                                  anchor="nw", font=theme.font(9), width=panel_w - px(10))

            # Insert tasks (lesson 7)
            insert_tasks = lesson.get("insert_tasks", [])
            if insert_tasks:
                ty = start_y + px(135) + len(tasks) * px(22) + px(10)
                c.create_text(panel_x, ty, text=_t("Цели вставки:"), fill=AMBER,
                              anchor="nw", font=theme.font(10, True))
                for i, it in enumerate(insert_tasks):
                    c.create_text(panel_x + px(10), ty + px(22) + i * px(20),
                                  text=_t("  {0}: '{1}' ({2})").format(it["mode"], it["text"], it["desc"]),
                                  fill=TEXT, anchor="nw", font=theme.font(9), width=panel_w - px(10))

        # Status bar
        status_y = h - px(50)
        c.create_rectangle(0, status_y, w, h, fill=BG, outline=blend(BG, TEXT, 0.2))
        c.create_text(px(10), status_y + px(10), text=_t("Режим: {0}").format(self.mode),
                      fill=AMBER if self.mode == "NORMAL" else (GREEN if self.mode == "INSERT" else PURPLE),
                      anchor="w", font=theme.font(10, True))
        c.create_text(px(150), status_y + px(10), text=_t("Урок {0}/{1}").format(self.lesson_idx + 1, len(LESSONS)),
                      fill=CYAN, anchor="w", font=theme.font(10, True))
        c.create_text(px(300), status_y + px(10), text=_t("Клавиши: {0}").format(lesson["keys"]),
                      fill=TEXT, anchor="w", font=theme.font(10))

        # Progress dots
        dot_x = w - px(20) - len(LESSONS) * px(18)
        for i in range(len(LESSONS)):
            color = GREEN if i in self.completed_lessons else (AMBER if i == self.lesson_idx else MUTED)
            c.create_oval(dot_x + i * px(18), status_y + px(5),
                          dot_x + i * px(18) + px(10), status_y + px(15),
                          fill=color, outline="")

        # Message
        if self.message:
            c.create_text(w // 2, h - px(18), text=self.message, fill=self.message_color,
                          font=theme.font(11, True), anchor="center")

        # Help line
        c.create_text(w // 2, h - px(4), text=lesson_key(), fill=MUTED,
                      font=theme.font(8), anchor="center")

        # Next lesson hint
        if self.lesson_idx in self.completed_lessons and self.lesson_idx + 1 < len(LESSONS):
            c.create_text(w - px(10), status_y + px(10), text=_t("Ctrl+n → дальше"),
                          fill=GREEN, anchor="e", font=theme.font(9, True))