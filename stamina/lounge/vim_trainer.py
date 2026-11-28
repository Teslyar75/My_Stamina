"""VIM Trainer — interactive VIM editor tutorial game for the Lounge.

Teaches VIM motions, edits, and modes through progressive challenges.
Inspired by Vim Adventures, PacVim, and VIM Master.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import time
import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, PANEL, PURPLE, TEXT, blend, px

from .base import GameShell
from . import store
from .vim_ref_panel import VimReferencePanel
from .vim_engine import (
    VimState,
    init_from_grid,
    process_key,
    process_special_key,
    get_cursor_pos,
    get_grid_text,
    get_mode,
    get_visual_start,
)

# F3 переключает «изоляцию Esc». Пока изоляция включена, Esc принадлежит VIM
# (переключает режимы) и не может вывести из урока. Когда выключена — два Esc
# подряд возвращают в лобби. Таймер свой, чтобы не зависеть от зенида.
ESC_EXIT_WINDOW = 0.6
ISO_ON = _t("ИЗОЛЯЦИЯ ESC: ВКЛ · F3 — разрешить выход")
ISO_OFF = _t("ИЗОЛЯЦИЯ ESC: ВЫКЛ · F3 — изолировать · Esc Esc — выход")


# ─── Lesson Data ──────────────────────────────────────────────────────────────

LESSONS = [
    {
        "id": "motion_basic",
        "title": _t("Урок 1: Базовые движения"),
        "keys": "h j k l",
        "desc": _t("В VIM курсор двигается клавишами h/j/k/l; в тренажёре их дублируют стрелки. Это основа."),
        "target": "MOVE_CURSOR",
        "grid": [
            "................",
            ".@..............",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
        ],
        "goal_pos": (15, 1),
        "hint": _t("Задание: дойди курсором (@) до цели справа. Нажимай l, стрелки тоже работают."),
        "tasks": [
            _t("1. Нажми l — курсор дойдёт до цели справа"),
            _t("2. Попробуй h — вернёшься назад"),
            _t("3. j/k — вверх/вниз по восьми строкам"),
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
    # ─── Второй круг: уверенное владение редактором ──────────────────────────
    {
        "id": "motion_file",
        "title": _t("Урок 13: Движение по файлу"),
        "keys": "gg G 5gg",
        "desc": _t("gg — первая строка, G — последняя, 5G — пятая. Не пролистывайте файл по строке."),
        "grid": [
            "................",
            "line two........",
            "line three......",
            "line four.......",
            "line five.......",
            "line six........",
            "line seven......",
            "................",
        ],
        "cursor": (0, 7),
        "hint": _t("Задание: побывай на первой и последней строках: gg, потом G."),
        "hints": [
            _t("Две клавиши подряд: g, затем g — это и есть команда gg."),
            _t("G (Shift+g) без числа — последняя строка файла."),
        ],
        "tasks": [
            _t("1. Нажми g, потом g — прыжок на строку 0"),
            _t("2. Нажми G — прыжок на последнюю строку"),
            _t("3. 5G — переход на пятую строку"),
        ],
        "focus": ["g", "G"],
        "expect": {"kind": "visit", "targets": [(0, 0), (0, 7)]},
    },
    {
        "id": "motion_char",
        "title": _t("Урок 14: Прыжок к символу"),
        "keys": "fx tx Fx Tx ; ,",
        "desc": _t("f — к символу вперёд, t — перед ним, F/T — назад. ; и , повторяют последний прыжок."),
        "grid": [
            "find (the) quick fox",
            "jump to x: xxxxxxxx",
            "....................",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: побывай на '(', ')' и на последней 'x' первой строки."),
        "hints": [
            _t("Нажми f, затем символ ( — курсор прыгнет прямо на скобку."),
            _t("Повтори поиск той же буквы клавишей ; —например, ; после fx."),
            _t("T и F ищут назад; запятая повторяет поиск в обратном направлении."),
        ],
        "tasks": [
            _t("1. f + ( — прыжок на позицию 5"),
            _t("2. f + ) — на позицию 9"),
            _t("3. f + x — на последнюю x строки"),
            _t("4. ; повторяет поиск, , — отменяет направление"),
        ],
        "focus": ["f", "t", ";"],
        "expect": {"kind": "visit", "targets": [(5, 0), (9, 0), (19, 0)]},
    },
    {
        "id": "motion_bracket",
        "title": _t("Урок 15: Парные скобки"),
        "keys": "%",
        "desc": _t("% прыгает от открывающей скобки к закрывающей и обратно — быстрее, чем искать глазом."),
        "grid": [
            " @(alpha) and (beta)",
            "....................",
        ],
        "hint": _t("Задание: нажми % на '(', окажешься на ')'; ещё раз — вернёшься."),
        "hints": [
            _t("Курсор уже стоит рядом со скобкой. Нажми только %."),
            _t("% работает и с {}, и с [] — это общее движение, а не команда для кода."),
        ],
        "tasks": [
            _t("1. % — прыжок к парной скобке"),
            _t("2. Ещё % — обратно"),
            _t("3. Попробуй поставить курсор на любую скобку в песочнице"),
        ],
        "focus": ["%"],
        "expect": {"kind": "visit", "targets": [(8, 0), (2, 0)]},
    },
    {
        "id": "replace_char",
        "title": _t("Урок 16: Замена символа и регистра"),
        "keys": "r<char> ~",
        "desc": _t("r меняет один символ под курсором, ~ переключает регистр — оба без входа в INSERT."),
        "grid": [
            "ac Def",
            ".......",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: исправь 'a' на 'C' командой rC, затем переключи регистр 'c' тильдой."),
        "hints": [
            _t("Нажми r, потом C — буква под курсором станет C, и вы останетесь в NORMAL."),
            _t("l — сдвинуться на один символ вправо, ~ — перевернуть его регистр."),
        ],
        "tasks": [
            _t("1. rC — заменить первую букву"),
            _t("2. l — перейти на следующую"),
            _t("3. ~ — переключить регистр"),
            _t("4. Должно получиться 'CC Def'"),
        ],
        "focus": ["r", "~", "l"],
        "expect": {"kind": "text", "rows": ["CC Def", "......."]},
    },
    {
        "id": "text_object",
        "title": _t("Урок 17: Текстовые объекты iw / aw"),
        "keys": "iw aw diw daw ciw",
        "desc": _t("iw — только слово под курсором, aw — слово вместе с пробелом. Не нужно попадать точно в начало."),
        "grid": [
            "one two three",
            ".............",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: diw удалит слово под курсором, daw — вместе с пробелом. Должно остаться ' three'."),
        "hints": [
            _t("Курсор стоит на первой букве. Нажми d, i, w — слово исчезнет."),
            _t("w — прыжок к началу следующего слова, потом d, a, w."),
            _t("ciw работает так же, но сразу открывает INSERT для нового слова."),
        ],
        "tasks": [
            _t("1. diw — удалить 'one'"),
            _t("2. w — перейти к 'two'"),
            _t("3. daw — удалить слово вместе с пробелом"),
            _t("4. Результат: ' three'"),
        ],
        "focus": ["i", "a", "w", "d"],
        "expect": {"kind": "text", "rows": [" three", "............."]},
    },
    {
        "id": "indent",
        "title": _t("Урок 18: Отступы"),
        "keys": ">> <<",
        "desc": _t(">> добавляет отступ строке, << убирает. Это управление кодом, а не набор пробелов вручную."),
        "grid": [
            "def f():",
            "print(1)",
            "  return 2",
            "..........",
        ],
        "cursor": (0, 1),
        "hint": _t("Задание: сделай отступ у print(1) командой >>, затем убери отступ у return командой <<."),
        "hints": [
            _t("Нажми > два раза — это команда >>, а не два отступа подряд."),
            _t("j — спуститься на строку return, затем < <."),
        ],
        "tasks": [
            _t("1. >> — отступ у строки 2"),
            _t("2. j — вниз"),
            _t("3. << — убрать отступ у строки 3"),
            _t("4. Визуальный режим + > меняет отступ сразу у блока"),
        ],
        "focus": [">", "<"],
        "expect": {"kind": "text", "rows": ["def f():", "  print(1)", "return 2", ".........."]},
    },
    {
        "id": "marks",
        "title": _t("Урок 19: Метки"),
        "keys": "ma 'a `a",
        "desc": _t("m + буква ставит метку, ' + буква возвращает на строку, ` + буква — точно на символ."),
        "grid": [
            "alpha beta",
            "gamma delta",
            "..........",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: поставь метку a в начале, спустись на вторую строку и вернись клавишей 'a."),
        "hints": [
            _t("m, потом a — метка поставлена; теперь можно уйти куда угодно."),
            _t("Одинарная кавычка + a возвращает на строку метки."),
        ],
        "tasks": [
            _t("1. ma — запомнить позицию"),
            _t("2. j — уйти вниз"),
            _t("3. 'a — вернуться"),
            _t("4. `` — позиция перед прошлым прыжком"),
        ],
        "focus": ["m", "'", "j"],
        "expect": {"kind": "visit", "targets": [(0, 1), (0, 0)]},
    },
    {
        "id": "registers",
        "title": _t("Урок 20: Регистры"),
        "keys": "yy p P \"ayy \"ap",
        "desc": _t("yy копирует строку в регистр, p вставляет после курсора, P — перед. \"a — именной регистр."),
        "grid": [
            "copy me",
            "",
            "........",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: скопируй строку в регистр (yy), спустись вниз и вставь её (p)."),
        "hints": [
            _t("yy — две клавиши y подряд: строка уходит в безымянный регистр."),
            _t("j — на пустую строку, потом p — вставка после курсора."),
            _t("\"ayy и \"ap — тот же приём с именным регистром a."),
        ],
        "tasks": [
            _t("1. yy — скопировать строку"),
            _t("2. j — вниз"),
            _t("3. p — вставить"),
            _t("4. Строки 1 и 2 станут одинаковыми"),
        ],
        "focus": ["y", "p", '"'],
        "expect": {"kind": "text", "rows": ["copy me", "copy me", "........"]},
    },
    {
        "id": "dot_repeat",
        "title": _t("Урок 21: Точка — повтор изменения"),
        "keys": ". u Ctrl+r",
        "desc": _t("Точка повторяет последнее изменение. Это клавиша, которая экономит больше всего времени."),
        "grid": [
            "@xxx delete me",
            "..............",
        ],
        "hint": _t("Задание: удали первый символ клавишей x, потом точкой повтори удаление ещё три раза."),
        "hints": [
            _t("x — удалить символ под курсором; точка повторит ровно это действие."),
            _t("u отменяет последнее изменение, Ctrl+r возвращает его."),
        ],
        "tasks": [
            _t("1. x — удалить первый символ"),
            _t("2. . — удалить следующую x"),
            _t("3. . — ещё одну x"),
            _t("4. . — последнюю x; должно получиться ' delete me'"),
        ],
        "focus": [".", "x"],
        "expect": {"kind": "text", "rows": [" delete me", ".............."]},
    },
    {
        "id": "substitute_command",
        "title": _t("Урок 22: Поиск и замена в тексте"),
        "keys": "/ vim n :s/old/new/g",
        "desc": _t("Поиск — это движение: /vim находит, n ведёт дальше. :s/old/new/g меняет все вхождения в строке."),
        "grid": [
            "vim vim vim",
            "vim is fun",
            "...........",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: найди все 'vim' (/vim, Enter, n, n), потом замени их в обеих строках командой :s/vim/VIM/g."),
        "hints": [
            _t("Нажми /, набери vim и Enter — курсор встанет на первое совпадение."),
            _t("n — следующее совпадение; N — предыдущее. Два n приведут на вторую строку."),
            _t("Команда :s/vim/VIM/g меняет все вхождения в текущей строке; k — на первую, и повтори."),
        ],
        "tasks": [
            _t("1. /vim + Enter — первое совпадение"),
            _t("2. n, n — остальные совпадения, курсор на второй строке"),
            _t("3. :s/vim/VIM/g — замена во второй строке"),
            _t("4. k и та же команда — замена в первой строке"),
        ],
        "focus": ["/", "n", ":"],
        "expect": {
            "kind": "text",
            "rows": ["VIM VIM VIM", "VIM is fun", "..........."],
            "require_commands": ["/vim", ":s/vim/VIM/g"],
        },
    },
    {
        "id": "macros",
        "title": _t("Урок 23: Макросы"),
        "keys": "q @",
        "desc": _t("q начинает и останавливает запись, @a проигрывает макрос. Один записанный приём — сто повторений."),
        "grid": [
            "xxxx first line",
            "xxxx second line",
            "................",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: запиши макрос q → xxxx → q, спустись на вторую строку и проиграй его (@, потом a)."),
        "hints": [
            _t("Первая q включает запись в регистр a, вторая — останавливает."),
            _t("Внутри записи нажми x четыре раза — макрос запомнит удаление четырёх символов."),
            _t("Проигрыш: @, затем a (в настоящем VIM это одна команда @a)."),
        ],
        "tasks": [
            _t("1. q — начать запись"),
            _t("2. xxxx — четыре удаления"),
            _t("3. q — остановить запись"),
            _t("4. j — вниз, @a — проиграть макрос"),
        ],
        "focus": ["q", "@", "x"],
        "expect": {"kind": "macro"},
    },
    {
        "id": "windows_tabs",
        "title": _t("Урок 24: Окна, вкладки, буферы"),
        "keys": ":sp :vsp :tabnew gt :bn :q",
        "desc": _t("Окна делят экран, вкладки хранят наборы окон, буферы — открытые файлы. Всё это — команды ':'."),
        "grid": [
            "split the window  ",
            "open another tab  ",
            "switch the buffer ",
            "..................",
        ],
        "cursor": (0, 0),
        "hint": _t("Задание: набери по очереди :sp, :vsp, :tabnew и :q — посмотри, как тренажёр отвечает на команды."),
        "hints": [
            _t("Нажми :, набери sp и Enter — командная строка приняла команду."),
            _t("Полный список окон и вкладок — в учебнике по F2, темы «Вкладки» и «Буферы и окна»."),
            _t("Здесь окна не создаются по-настоящему: тренажёр честно показывает, что команда распознана."),
        ],
        "tasks": [
            _t("1. :sp — горизонтальное разделение"),
            _t("2. :vsp — вертикальное"),
            _t("3. :tabnew — новая вкладка"),
            _t("4. :q — закрыть текущее окно"),
        ],
        "focus": [":"],
        "expect": {"kind": "commands", "any": [":sp", ":vsp", ":tabnew", ":q"]},
    },
]

# Как в Vim Adventures: у каждого уровня одна «клавиша-ключ», которую
# осваивает первым. Подсвечивается на клавиатуре и в мягкой подсказке.
NEXT_KEYS = [
    "l", "w", "0", "x", "d", "d", "i", "c", "v", "/", "x", "5",
    "g", "f", "%", "r", "w", ">", "m", "\"", ".", "/", "q", ":",
]

# Свободная песочница: большая арена без цели и оценки. Открывается кнопкой
# «ПЕСОЧНИЦА», чтобы закрепить движения после первого урока, не проходя 12 уроков подряд.
PRACTICE_GRID = [
    "the quick brown ",
    "fox (jumps) over",
    "  the lazy dog  ",
    "find f/t, % here",
    "one two three   ",
    "  indented line ",
    "@ move: hjkl w b",
    "try q-record @a ",
]
PRACTICE_LESSON = {
    "id": "practice",
    "title": _t("ПЕСОЧНИЦА · СВОБОДНАЯ ТРЕНИРОВКА"),
    "keys": "h j k l · w b e · gg/G · f/t/% · x/r/~ · i Esc · v Esc · yy/p · . · q/@ · / :",
    "desc": _t("В VIM курсор двигается клавишами h/j/k/l; в тренажёре их дублируют стрелки. Это основа."),
    "hint": _t("Попробуй любые команды: h/j/k/l, w/b/e, gg/G, f/t, %, r, x, >>/<<, yy/p, q/@, / и :s. "
               "Цели и оценки нет; ? — подсказка, F3 — изоляция Esc."),
    "tasks": [],
}


def lesson_key() -> str:
    return _t("h/j/k/l движение · w/b/e слова · 0/^/$ строки · gg/G/ge файл · f/t/F/T символы · % скобки · x/r/~ правка · dw/dd/diw удаление · i/a/o вставка · cw/cc замена · v/V выделение · >/< отступы · m/' метки · yy/p (регистры) · . повтор · q/@ макросы · / поиск · :s замена · :help тема · ? подсказка · F3 изоляция Esc · u/Ctrl+r отмена · 5j счетчики")


# ─── VIM Trainer Game ────────────────────────────────────────────────────────

class VimTrainerGame(GameShell):
    game_id = "vim_trainer"
    title = _t("VIM ТРЕНАЖЁР · УЧИ КОМАНДЫ")
    tools_row = True            # вторая строка: кнопка «УЧЕБНИК  F2»
    ref_panel = None            # панель-учебник создаётся по F2

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.lesson_idx = 0
        self.cell_w = 18
        self.cell_h = 22
        self.state: VimState | None = None
        self.completed_lessons: set[int] = set()
        # Tracking for special lessons
        self._vim_found_count = 0
        self._did_undo_redo = False
        self._used_count = False
        self._pending_count = ""
        self._targets: dict[str, set[tuple[int, int]]] = {"word": set(), "line": set()}
        self._search_text = ""
        self._search_hits: set[tuple[int, int]] = set()
        self._command = ""
        self._command_prefix = ""
        self._mistakes = 0
        self.practice = False
        # Изоляция Esc включена по умолчанию: двойной Esc не выносит из урока.
        # F3 переключает её; в выключенном состоянии два Esc — выход в лобби.
        self.esc_isolated = True
        self._esc_exit_at = 0.0
        # Учебные счётчики: visited-цели, нажатые клавиши, введённые ':'-команды,
        # запись макросов и мягкие подсказки после заминки.
        self._expect_targets: list[tuple[int, int]] = []
        self._used_keys: set[str] = set()
        self._typed_commands: list[str] = []
        self._macros: dict[str, list[str]] = {}
        self._macro_keys: list[str] = []
        self._macro_recording = False
        self._macro_replayed = False
        self._hint_index = 0
        self._idle_keys = 0
        self._progress_sig: tuple | None = None
        self.load_progress()
        self._load_lesson(0)
        self.set_hint(lesson_key())
        self._bind_hud_focus()

    def build_tools(self) -> None:
        """Вторая строка панели: учебник, навигация и песочница."""
        HudButton(self.tools, _t("УЧЕБНИК  F2"), self.toggle_reference, height=30,
                  font_size=9, width=140, color=AMBER).pack(side=tk.LEFT, padx=(0, px(8)))
        HudButton(self.tools, _t("СЛЕДУЮЩИЙ УРОК ▶"), self._next_lesson, height=30,
                  font_size=9, width=160, color=CYAN).pack(side=tk.LEFT, padx=(0, px(8)))
        HudButton(self.tools, _t("ПЕСОЧНИЦА"), self.toggle_practice, height=30,
                  font_size=9, width=110, color=GREEN).pack(side=tk.LEFT, padx=(0, px(8)))
        self.btn_iso = HudButton(self.tools, ISO_ON, self.toggle_esc_isolation, height=30,
                                 font_size=9, width=250, color=AMBER)
        self.btn_iso.pack(side=tk.LEFT, padx=(0, px(8)))
        tk.Label(self.tools, text=_t("клавиши, примеры и теория по темам · F2 в игре"),
                 bg=BG, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT)

    # -- фокус: клавиши VIM не должны уходить в навигацию по HudButton --------
    def _restore_focus(self) -> None:
        """После клика по кнопке вернуть фокус игре — иначе keynav съедает Esc/стрелки."""
        try:
            self.after_idle(self.focus_set)
        except Exception:  # noqa: BLE001 — во время закрытия виджета фокус не нужен
            pass

    def _bind_hud_focus(self) -> None:
        def walk(widget) -> None:
            for child in widget.winfo_children():
                if isinstance(child, HudButton) and not getattr(child, "_vim_focus_bound", False):
                    child._vim_focus_bound = True
                    child.bind("<ButtonRelease-1>", lambda _e: self._restore_focus(), add="+")
                walk(child)
        walk(self)

    def start(self) -> None:
        super().start()
        self._restore_focus()

    def _current_lesson(self) -> dict:
        return PRACTICE_LESSON if self.practice else LESSONS[self.lesson_idx]

    # -- учебник клавиш ------------------------------------------------------
    def reference_open(self) -> bool:
        return self.ref_panel is not None and self.ref_panel.winfo_ismapped()

    def toggle_reference(self) -> None:
        if self.reference_open():
            self.close_reference()
            return
        if self.ref_panel is None:
            self.ref_panel = VimReferencePanel(
                self.canvas.master, on_lesson=self.open_lesson,
                on_close=self.close_reference,
            )
        self.ref_panel.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.ref_panel.lift()
        self.set_hint(_t("Учебник открыт: тема → клавиши → «К УРОКУ» · F2 — закрыть"))

    def close_reference(self) -> None:
        if self.ref_panel is not None:
            self.ref_panel.place_forget()
        self.set_hint(lesson_key())
        self.focus_set()
        self.redraw()

    def toggle_practice(self) -> None:
        """Большая арена без задания: закреплять команды свободно, без оценки."""
        self.practice = not self.practice
        if self.practice:
            self.state = init_from_grid([list(row) for row in PRACTICE_GRID])
            self.state.mode = "NORMAL"
            self._command = ""
            self._command_prefix = ""
            self._pending_count = ""
            self._search_text = ""
            self._search_hits.clear()
            self._esc_exit_at = 0.0
            self._reset_progress_state()
            self.message = PRACTICE_LESSON["hint"]
            self.message_color = GREEN
            self.title = PRACTICE_LESSON["title"]
        else:
            self._load_lesson(self.lesson_idx)
        self.lbl_title.configure(text=self.title)
        self._restore_focus()
        self.redraw()

    # -- изоляция Esc (F3) -----------------------------------------------------
    def _iso_text(self) -> str:
        return ISO_ON if self.esc_isolated else ISO_OFF

    def _update_iso_button(self) -> None:
        btn = getattr(self, "btn_iso", None)
        if btn is not None:
            btn.set_text(self._iso_text())

    def toggle_esc_isolation(self) -> None:
        """F3: изолировать Esc или вернуть двойному Esc выход из тренажёра."""
        self.esc_isolated = not self.esc_isolated
        self._esc_exit_at = 0.0
        from stamina import zen_mode
        zen_mode.reset_escape()      # чтобы первый Esc не «дозрел» до двойного
        if self.esc_isolated:
            self.message = _t("Esc изолирован: он только переключает режим VIM. F3 — разрешить выход")
            self.message_color = AMBER
        else:
            self.message = _t("Два Esc подряд — выход из тренажёра. F3 — снова изолировать")
            self.message_color = GREEN
        self._update_iso_button()
        self._restore_focus()
        self.redraw()

    def _esc_exit_tap(self) -> bool:
        """Считать двойной Esc, только когда изоляция снята F3."""
        now = time.monotonic()
        if self._esc_exit_at and now - self._esc_exit_at <= ESC_EXIT_WINDOW:
            self._esc_exit_at = 0.0
            self._back()              # тот же путь, что кнопка «← В ЛОББИ»
            return True
        self._esc_exit_at = now
        return False

    # -- мягкие подсказки -----------------------------------------------------
    def _hint_list(self) -> list[str]:
        if self.practice or self.state is None:
            return []
        return list(self._current_lesson().get("hints") or [])

    def _progress_signature(self):
        if getattr(self, "state", None) is None:
            return None
        return (get_cursor_pos(self.state), tuple(get_grid_text(self.state)), get_mode(self.state))

    def _show_next_hint(self) -> None:
        """'?' или три клавиши без сдвига — показать следующую подсказку урока."""
        hints = self._hint_list()
        if not hints:
            self.message = _t("Подсказок у этого урока нет — открой F2 или песочницу")
            self.message_color = MUTED
            self.redraw()
            return
        idx = self._hint_index % len(hints)
        self._hint_index += 1
        self.message = _t("Подсказка {0}/{1}: {2}").format(idx + 1, len(hints), hints[idx])
        self.message_color = AMBER
        self.redraw()

    def _after_key(self, before) -> None:
        if before is None or not self._hint_list():
            return
        if not self.practice and self.lesson_idx in self.completed_lessons:
            return                      # пройденный урок больше не дёргает подсказками
        now = self._progress_signature()
        if now != before:
            self._idle_keys = 0
            self._progress_sig = now
            return
        self._idle_keys += 1
        if self._idle_keys >= 3:
            self._idle_keys = 0
            self._show_next_hint()

    def open_lesson(self, lesson_id: str) -> None:
        """Кнопка «К УРОКУ»: открыть урок, где эта клавиша отрабатывается."""
        for idx, lesson in enumerate(LESSONS):
            if lesson["id"] == lesson_id:
                self.close_reference()
                self._load_lesson(idx)
                self.message = _t("Из учебника: урок {0} — пройдите его руками").format(idx + 1)
                self.message_color = CYAN
                self.redraw()
                return
        self.close_reference()

    def load_progress(self) -> None:
        data = store.load()
        vim_data = data.get("vim_trainer", {})
        self.completed_lessons = set(vim_data.get("completed", []))

    def save_progress(self) -> None:
        data = store.load()
        data["vim_trainer"] = {"completed": list(self.completed_lessons)}
        store.save(data)

    def _ensure_tracking(self) -> None:
        """Тесты и старые вызовы создают игру через __new__ — поля могут отсутствовать."""
        defaults = {
            "_used_keys": set, "_typed_commands": list, "_macros": dict,
            "_macro_keys": list, "_expect_targets": list,
            "_macro_recording": lambda: False, "_macro_replayed": lambda: False,
            "_hint_index": lambda: 0, "_idle_keys": lambda: 0,
            "_esc_exit_at": lambda: 0.0, "esc_isolated": lambda: True,
            "practice": lambda: False,
        }
        for name, factory in defaults.items():
            if not hasattr(self, name):
                setattr(self, name, factory())

    def _reset_progress_state(self) -> None:
        """Сбросить всё, что копится между уроками и песочницей."""
        self._expect_targets = [tuple(p) for p in
                                (self._current_lesson().get("expect", {}).get("targets") or [])]
        self._used_keys.clear()
        self._typed_commands.clear()
        self._macros.clear()
        self._macro_keys.clear()
        self._macro_recording = False
        self._macro_replayed = False
        self._hint_index = 0
        self._idle_keys = 0
        self._progress_sig = self._progress_signature()

    def _load_lesson(self, idx: int) -> None:
        if idx < 0 or idx >= len(LESSONS):
            return
        self.lesson_idx = idx
        lesson = LESSONS[idx]
        grid = [list(row) for row in lesson["grid"]]
        self.state = init_from_grid(grid)
        # Find @ position and set cursor there
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == "@":
                    self.state.cursor_x = x
                    self.state.cursor_y = y
                    break
        self.state.mode = "NORMAL"
        self.practice = False
        self._command = ""
        self._command_prefix = ""
        self._pending_count = ""
        self._search_text = ""
        self._search_hits.clear()
        self._vim_found_count = 0
        self._did_undo_redo = False
        self._used_count = False
        self._esc_exit_at = 0.0
        self._reset_progress_state()
        # Явная стартовая позиция у уроков на сгенерированных текстах.
        if "cursor" in lesson:
            self.state.cursor_x, self.state.cursor_y = lesson["cursor"]
        # Цели копируются: раньше уроки 2/3 навсегда теряли пройденные цели
        # при повторном открытии, потому что правился сам LESSONS.
        self._targets = {
            "word": set(lesson.get("word_targets", [])),
            "line": set(lesson.get("line_targets", [])),
        }
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

    def help_level_id(self) -> str | None:
        if self.practice:
            return "motion_basic"
        try:
            return LESSONS[self.lesson_idx]["id"]
        except (IndexError, KeyError, TypeError):
            return "motion_basic"

    def on_key(self, e: tk.Event) -> None:
        """Обёртка: замечает заминку и показывает подсказку, если нет progress."""
        self._ensure_tracking()
        before = self._progress_signature()
        self._on_key_impl(e)
        self._after_key(before)

    def _on_key_impl(self, e: tk.Event) -> None:
        if self.handle_help_keys(e):
            return
        raw_key = (getattr(e, "keysym", "") or "")
        k = raw_key.lower()
        # F3 — isolation-переключатель; работает и при открытом учебнике.
        if k == "f3":
            self.toggle_esc_isolation()
            return
        # Учебник перекрывает поле: пока он открыт, клавиши ему не мешают.
        if e.keysym == "F2":
            self.toggle_reference()
            return
        if self.reference_open():
            if e.keysym == "Escape":
                self.close_reference()
            return
        if self.state is None:
            return
        self._ensure_tracking()
        # Любая другая клавиша сбрасывает «первый Esc» двойного нажатия.
        if k != "escape":
            self._esc_exit_at = 0.0
        modifier_state = getattr(e, "state", 0) or 0
        ctrl = bool(modifier_state & 0x4)
        shift = bool(modifier_state & 0x1)
        # С письменной оговоркой F3: двойной Esc работает, только когда изоляция снята.
        if k == "escape" and not self.esc_isolated and self._esc_exit_tap():
            return

        # Навигация урока и Ctrl+R — до движка, иначе 'n' станет поиском, а 'r' — вводом.
        keycode = int(getattr(e, "keycode", 0) or 0)
        if ctrl and k == "r":
            process_key(self.state, "r", ctrl=True)
            self._did_undo_redo = True
            self.message = _t("Возврат (Ctrl+r) — сделано! u / Ctrl+r работают парой")
            self.message_color = GREEN
            self._check_lesson_complete()
            self.redraw()
            return
        if ctrl:
            if k in ("n", "cyrillic_te", "т") or keycode == 78:
                self._next_lesson()
                return
            if k in ("p", "cyrillic_ze", "з") or keycode == 80:
                self._prev_lesson()
                return
            if (len(k) == 1 and k.isprintable()) or k.startswith("cyrillic_"):
                return

        # Строка команд ':' / '/': Esc отменяет ввод, Enter исполняет.
        if self.state.mode == "COMMAND":
            if k == "escape":
                self._cancel_command()
                return
            if k == "backspace":
                self._command = self._command[:-1]
                self.redraw()
                return
            if k in ("return", "enter"):
                self._run_command()
                return
            if k == "space":
                self._command += " "
                self.redraw()
                return
            ch = self._typed_char(e, raw_key)
            if ch:
                self._command += ch
                self.redraw()
            return

        if k == "escape":
            self._clear_count()
            if self.esc_isolated:
                self._esc_exit_at = 0.0
            process_key(self.state, "escape")
            self.message = _t("Режим: {0}").format(get_mode(self.state))
            self.message_color = AMBER
            self.redraw()
            return
        if k == "return":
            process_special_key(self.state, "enter")
            self.redraw()
            return
        if k == "backspace":
            process_special_key(self.state, "backspace")
            self.redraw()
            return
        if k == "space":
            process_special_key(self.state, "space")
            self._check_lesson_complete()
            self.redraw()
            return
        if k == "tab":
            process_special_key(self.state, "tab")
            self.redraw()
            return
        if k in ("left", "right", "up", "down"):
            count = self._count_value()
            if count > 1:
                self._used_count = True
            self.state.pending_count = self._pending_count
            process_special_key(self.state, k)
            self._clear_count()
            self._check_lesson_complete()
            self.redraw()
            return

        ch = self._typed_char(e, raw_key)
        if not ch:
            self.redraw()
            return
        self._used_keys.add(ch)
        if ch == "?":
            self._show_next_hint()
            return
        if ch.isdigit():
            self._pending_count += ch
            self.message = _t("Счетчик {0}... нажми команду (j/k/l/h/dw/dd)").format(self._pending_count)
            self.message_color = AMBER
            self.redraw()
            return

        if get_mode(self.state) == "NORMAL" and ch in ("/", ":"):
            self._start_command(ch)
            return
        if ch == "*":
            self._search_word()
            self._check_lesson_complete()
            self.redraw()
            return
        if ch in ("n", "N") and self._search_text:
            self._search(ch == "n")
            self._check_lesson_complete()
            self.redraw()
            return

        if get_mode(self.state) == "NORMAL" and ch == "q" and not self._macro_recording:
            self._macro_recording = True
            self._macro_keys.clear()
            self.message = _t("Запись макроса в регистр a: нажимай клавиши, q — остановить")
            self.message_color = AMBER
            self.redraw()
            return
        if self._macro_recording:
            if ch == "q":
                self._macros["a"] = self._macro_keys[:]
                self._macro_recording = False
                self.message = _t("Макрос записан ({0} клавиш). Проиграй: @, потом a").format(
                    len(self._macro_keys))
                self.message_color = GREEN
                self.redraw()
                return
            self._macro_keys.append(ch)
        elif get_mode(self.state) == "NORMAL" and ch == "@":
            replay = self._macros.get("a") or []
            if replay:
                self._macro_replayed = True
                for token in replay:
                    self._apply_char(token)
            self._check_lesson_complete()
            if self.lesson_idx not in self.completed_lessons:
                self.message = _t("Макрос проигран ({0} клавиш)").format(len(replay))
                self.message_color = GREEN if replay else AMBER
            self.redraw()
            return

        self._apply_char(ch, shift=shift)

    def _apply_char(self, ch: str, shift: bool = False) -> None:
        """Одна клавиша в движок; сюда же приходят клавиши записанного макроса."""
        count = self._count_value()
        if count > 1:
            self._used_count = True
        self.state.pending_count = self._pending_count
        # Раньше count уходил третьим аргументом в ctrl и ломал 'r'.
        process_key(self.state, ch, shift=shift)
        self._clear_count()
        self._check_lesson_complete()
        self.redraw()

    @staticmethod
    def _typed_char(e: tk.Event, k: str) -> str:
        """Printable character from the ORIGINAL keysym (uppercase VIM commands!)."""
        if len(k) == 1 and k.isprintable():
            return k
        names = {"colon": ":", "slash": "/", "question": "?", "period": ".", "comma": ","}
        low = k.lower()
        if low in names:
            return names[low]
        ch = getattr(e, "char", "") or ""
        return ch if len(ch) == 1 and ch.isprintable() else ""

    def _count_value(self) -> int:
        return int(self._pending_count) if self._pending_count else 1

    def _clear_count(self) -> None:
        self._pending_count = ""
        if self.state is not None:
            self.state.pending_count = ""

    def _start_command(self, prefix: str) -> None:
        self._clear_count()
        self._command_prefix = prefix
        self._command = ""
        self.state.mode = "COMMAND"
        if self.practice or self.lesson_idx not in self.completed_lessons:
            self.message = prefix + self._command + "  (Esc — отмена)"
            self.message_color = AMBER

    def _cancel_command(self) -> None:
        self._clear_count()
        self._command = ""
        self._command_prefix = ""
        self.state.mode = "NORMAL"
        self.message = _t("Режим: {0}").format("NORMAL")
        self.message_color = AMBER
        self.redraw()

    def _run_command(self) -> None:
        text = self._command.strip()
        prefix = self._command_prefix
        typed = prefix + text
        if text:
            self._ensure_tracking()
            self._typed_commands.append(typed)
        if prefix == "/" and text:
            self._search_text = text
            self._search(True)
        elif prefix == ":" and text.startswith("s/"):
            self._substitute(text)
        elif prefix == ":" and text == "keyboard":
            self._show_keyboard_help()
        elif prefix == ":" and text.startswith("help"):
            self._open_help_topic(text[4:].strip())
        elif text and (self.practice or self.lesson_idx not in self.completed_lessons):
            # После прохождения урока баннер «Урок пройден» должен оставаться
            # на экране, даже если игрок продолжает пробовать команды.
            self.message = _t("Клавиши: {0}").format(typed)
            self.message_color = AMBER
        self._clear_count()
        self._command = ""
        self._command_prefix = ""
        self.state.mode = "NORMAL"
        self._check_lesson_complete()
        self.redraw()

    def _show_keyboard_help(self) -> None:
        self.message = _t(":keyboard — полоса клавиш внизу поля; ? — подсказка; F3 — изоляция Esc")
        self.message_color = CYAN

    def _open_help_topic(self, query: str) -> None:
        """Vim Adventures: ':help topic' открывает учебник на нужной теме."""
        from . import vim_reference
        topics = vim_reference.topics()
        chosen = next((t for t in topics if t["id"] == query), None)
        if chosen is None and query:
            chosen = next((t for t in topics if query.lower() in t["title"].lower()), None)
        if chosen is None and query:
            chosen = next((t for t in topics
                           if any(c["cmd"] == query for c in t["commands"])), None)
        if chosen is None:
            chosen = topics[0] if topics else None
        if chosen is None:
            return
        if self.ref_panel is None:
            self.toggle_reference()
        if self.ref_panel is not None:
            self.ref_panel.select_topic(chosen["id"])
        self.message = _t(":help {0} — тема «{1}» в учебнике (F2 — закрыть)").format(
            query or chosen["id"], chosen["title"])
        self.message_color = CYAN

    def _find_starts(self, needle: str) -> list[tuple[int, int]]:
        return [
            (x, y)
            for y, row in enumerate(get_grid_text(self.state))
            for x in range(len(row))
            if row.startswith(needle, x)
        ]

    def _mark_search_hit(self, pos: tuple[int, int]) -> None:
        self.state.cursor_x, self.state.cursor_y = pos
        if pos not in self._search_hits:
            self._search_hits.add(pos)
            self._vim_found_count += 1
        self.message = _t("Клавиши: {0}").format("/" + self._search_text)
        self.message_color = GREEN

    def _search(self, forward: bool = True) -> None:
        starts = self._find_starts(self._search_text)
        if not starts:
            self.message = _t("Клавиши: {0}").format("/" + self._search_text) + "  ?"
            self.message_color = AMBER
            return
        x, y = get_cursor_pos(self.state)
        current = (y, x)
        if forward:
            later = [p for p in starts if (p[1], p[0]) > current]
            self._mark_search_hit(later[0] if later else starts[0])
        else:
            earlier = [p for p in reversed(starts) if (p[1], p[0]) < current]
            self._mark_search_hit(earlier[0] if earlier else starts[-1])

    def _search_word(self) -> None:
        x, y = get_cursor_pos(self.state)
        row = get_grid_text(self.state)[y] if y < len(get_grid_text(self.state)) else ""
        left = x
        while left > 0 and row[left - 1].isalnum():
            left -= 1
        right = x
        while right < len(row) and row[right].isalnum():
            right += 1
        if right <= left:
            return
        self._search_text = row[left:right]
        self._search(True)

    def _substitute(self, text: str) -> None:
        parts = text.split("/")
        if len(parts) < 3:
            return
        old, new = parts[1], parts[2]
        y = self.state.cursor_y
        if y < len(self.state.grid):
            row = "".join(self.state.grid[y])
            self.state.grid[y] = list(row.replace(old, new))
            self.state.cursor_x = min(self.state.cursor_x, max(0, len(row.replace(old, new)) - 1))
        if self.practice or self.lesson_idx not in self.completed_lessons:
            self.message = _t("Клавиши: {0}").format(":" + text)
            self.message_color = GREEN

    def _check_expect(self, expect: dict, grid_text: list[str], pos: tuple[int, int]) -> bool:
        """Универсальная проверка уроков 13–24."""
        self._ensure_tracking()
        required = expect.get("require_commands") or []
        if required:
            def seen(cmd: str) -> bool:
                return any(cmd == typed or cmd in typed for typed in self._typed_commands)
            if not all(seen(cmd) for cmd in required):
                return False
        kind = expect.get("kind")
        if kind == "visit":
            targets = [tuple(p) for p in expect.get("targets") or []]
            if not targets:
                return False
            if not self._expect_targets and self.lesson_idx not in self.completed_lessons:
                self._expect_targets = targets[:]
            if pos in self._expect_targets:
                self._expect_targets.remove(pos)
            return not self._expect_targets
        if kind == "text":
            rows = expect.get("rows")
            return bool(rows) and grid_text[:len(rows)] == list(rows)
        if kind == "commands":
            any_cmds = expect.get("any") or []
            return bool(any_cmds) and any(any(cmd == typed or cmd in typed
                                              for typed in self._typed_commands)
                                          for cmd in any_cmds)
        if kind == "macro":
            return bool(self._macros.get("a")) and bool(self._macro_replayed)
        return False

    def _check_lesson_complete(self) -> None:
        if self.state is None or self.practice:
            return
        lesson = self._current_lesson()
        target = lesson.get("target")
        cursor_x, cursor_y = get_cursor_pos(self.state)
        grid_text = get_grid_text(self.state)
        mode = get_mode(self.state)

        # Новые уроки проверяются через общий expect: посещённые позиции,
        # результат редактирования, введённые команды и записанный макрос.
        expect = lesson.get("expect")
        if expect:
            if self._check_expect(expect, grid_text, (cursor_x, cursor_y)):
                self._complete_lesson()
            return

        if target == "MOVE_CURSOR" and "goal_pos" in lesson:
            gx, gy = lesson["goal_pos"]
            if cursor_x >= gx and cursor_y == gy:
                self._complete_lesson()

        elif target == "WORD_MOTION":
            pos = (cursor_x, cursor_y)
            if pos in self._targets["word"]:
                self._targets["word"].discard(pos)
                if not self._targets["word"]:
                    self._complete_lesson()

        elif target == "LINE_MOTION":
            pos = (cursor_x, cursor_y)
            if pos in self._targets["line"]:
                self._targets["line"].discard(pos)
                if not self._targets["line"]:
                    self._complete_lesson()

        elif target == "DELETE_CHAR" and "delete_targets" in lesson:
            targets = set(lesson["delete_targets"])
            all_deleted = True
            for tx, ty in targets:
                if ty < len(grid_text) and tx < len(grid_text[ty]):
                    if grid_text[ty][tx] != " " and grid_text[ty][tx] != ".":
                        all_deleted = False
                        break
            if all_deleted:
                self._complete_lesson()

        elif target == "DELETE_WORD":
            row0 = grid_text[0] if grid_text else ""
            if not any(c.isalnum() for c in row0):
                self._complete_lesson()

        elif target == "DELETE_LINE":
            if len(grid_text) <= 2:
                self._complete_lesson()

        elif target == "INSERT_MODE" and "insert_tasks" in lesson:
            row0 = grid_text[0] if len(grid_text) > 0 else ""
            row1 = grid_text[1] if len(grid_text) > 1 else ""
            if "beautiful" in row0 and "!" in row0 and "new line below" in row1:
                self._complete_lesson()

        elif target == "CHANGE_OPERATOR":
            row0 = grid_text[0] if len(grid_text) > 0 else ""
            row1 = grid_text[1] if len(grid_text) > 1 else ""
            if "it" in row0 and "new line" in row1:
                self._complete_lesson()

        elif target == "VISUAL_MODE":
            row0 = grid_text[0] if len(grid_text) > 0 else ""
            if "select" not in row0 and len(grid_text) <= 2:
                self._complete_lesson()

        elif target == "SEARCH_REPLACE":
            if self._vim_found_count >= 3:
                self._complete_lesson()

        elif target == "UNDO_REDO":
            if self._did_undo_redo:
                self._complete_lesson()

        elif target == "REPEAT_COUNT":
            if self._used_count:
                self._complete_lesson()

    def _complete_lesson(self) -> None:
        if self.lesson_idx not in self.completed_lessons:
            self.completed_lessons.add(self.lesson_idx)
            self.save_progress()
            self.add_score(100)
            self.message = _t("Урок пройден! Кнопка «Следующий урок ▶» или Ctrl+N / Ctrl+Т")
            self.message_color = GREEN

    def _next_lesson(self) -> None:
        if self.lesson_idx + 1 < len(LESSONS):
            self._load_lesson(self.lesson_idx + 1)
            self._restore_focus()
        else:
            self.message = _t("Все уроки пройдены! Отличная работа!")
            self.message_color = GREEN

    def _prev_lesson(self) -> None:
        if self.lesson_idx > 0:
            self._load_lesson(self.lesson_idx - 1)
            self._restore_focus()

    # ─── Rendering ──────────────────────────────────────────────────────────

    def redraw(self) -> None:
        if self.state is None:
            return
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)
        c.create_rectangle(0, 0, w, h, fill=BG2, outline="")

        lesson = self._current_lesson()
        grid_text = get_grid_text(self.state)
        cursor_x, cursor_y = get_cursor_pos(self.state)
        mode = get_mode(self.state)
        visual_start = get_visual_start(self.state)

        # Левая панель: ячейки подстраиваются под арену, вместо фиксированных 18×22.
        # Большое поле первого урока и песочница остаются читаемыми на узком окне.
        rows = max(1, len(grid_text))
        cols = max(1, max((len(row) for row in grid_text), default=1))
        grid_w = max(px(220), min(w - px(300), max(px(420), cols * px(18))))
        self.cell_w = max(px(10), min(px(26), (grid_w - px(12)) // cols))
        self.cell_h = max(px(12), min(px(28), (h - px(130)) // rows))
        start_x = px(20)
        start_y = px(20)

        for y, row in enumerate(grid_text):
            for x, ch in enumerate(row):
                cx = start_x + x * self.cell_w
                cy = start_y + y * self.cell_h

                if cx + self.cell_w > start_x + grid_w:
                    continue

                # Cell background
                is_cursor = (x == cursor_x and y == cursor_y)
                is_visual = False
                if visual_start:
                    vy, vx = visual_start
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

        # Полоса клавиш: как в Vim Adventures — видно, какие клавиши урока осваиваются.
        kb = ["Esc", "h", "j", "k", "l", "w", "b", "e", "gg", "f", "t", "%",
              "x", "r", "~", "d", "y", "p", "i", "v", "/", ":", "u", ".", "q", "@", "?"]
        focus = set(lesson.get("focus") or [])
        if not focus and not self.practice and self.lesson_idx < len(NEXT_KEYS):
            focus.add(NEXT_KEYS[self.lesson_idx])
        kb_y = h - px(78)
        kb_w = px(26)
        for i, key in enumerate(kb):
            bx = px(12) + i * (kb_w + px(3))
            if bx + kb_w > w - px(12):
                break
            hot = key in focus or (key == "F3" and not self.esc_isolated)
            c.create_rectangle(bx, kb_y, bx + kb_w, kb_y + px(20),
                               fill=blend(PURPLE, BG2, 0.4) if hot else PANEL,
                               outline=blend(PURPLE if hot else MUTED, BG2, 0.5))
            c.create_text(bx + kb_w // 2, kb_y + px(10), text=key,
                          fill=TEXT if hot else MUTED, font=theme.font(8, hot, mono=True))

        # Status bar
        status_y = h - px(50)
        c.create_rectangle(0, status_y, w, h, fill=BG, outline=blend(BG, TEXT, 0.2))
        c.create_text(px(10), status_y + px(10), text=_t("Режим: {0}").format(mode),
                      fill=AMBER if mode == "NORMAL" else (GREEN if mode == "INSERT" else PURPLE),
                      anchor="w", font=theme.font(10, True))
        lesson_label = (_t("ПЕСОЧНИЦА") if self.practice else
                        _t("Урок {0}/{1}").format(self.lesson_idx + 1, len(LESSONS)))
        c.create_text(px(150), status_y + px(10), text=lesson_label,
                      fill=CYAN, anchor="w", font=theme.font(10, True))
        c.create_text(px(150), status_y + px(24), text=self._iso_text(),
                      fill=GREEN if self.esc_isolated else AMBER,
                      anchor="w", font=theme.font(9, True))
        c.create_text(px(300), status_y + px(10),
                      text="@ {0},{1} · ".format(cursor_x, cursor_y) + _t("Клавиши: {0}").format(lesson["keys"]),
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
        if not self.practice and self.lesson_idx in self.completed_lessons and self.lesson_idx + 1 < len(LESSONS):
            c.create_text(w - px(10), status_y + px(10), text=_t("Ctrl+n / Ctrl+Т → дальше"),
                          fill=GREEN, anchor="e", font=theme.font(9, True))