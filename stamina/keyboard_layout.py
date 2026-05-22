"""Раскладка виртуальной клавиатуры — 30 колонок × 5 рядов.

Точно повторяет грид из ``Stamina2_XAML/MainWindow.xaml``: те же позиции
(``Grid.Column``/``Grid.ColumnSpan``) и те же фоновые цвета.
"""

from stamina.theme import CYAN, GRAY, GREEN, PINK, PURPLE, YELLOW

# (надпись, col, colspan, цвет фона)
ROW_NUMBER: list[tuple[str, int, int, str]] = [
    ("~", 0, 2, PINK),
    ("1", 2, 2, PINK),
    ("2", 4, 2, YELLOW),
    ("3", 6, 2, GREEN),
    ("4", 8, 2, CYAN),
    ("5", 10, 2, CYAN),
    ("6", 12, 2, CYAN),
    ("7", 14, 2, PURPLE),
    ("8", 16, 2, PURPLE),
    ("9", 18, 2, PINK),
    ("0", 20, 2, YELLOW),
    ("-", 22, 2, GREEN),
    ("=", 24, 2, GREEN),
    ("Backspace", 26, 4, GRAY),
]

ROW_Q: list[tuple[str, int, int, str]] = [
    ("Tab", 0, 3, GRAY),
    ("Q", 3, 2, YELLOW),
    ("W", 5, 2, YELLOW),
    ("E", 7, 2, GREEN),
    ("R", 9, 2, CYAN),
    ("T", 11, 2, CYAN),
    ("Y", 13, 2, PURPLE),
    ("U", 15, 2, PURPLE),
    ("I", 17, 2, PINK),
    ("O", 19, 2, YELLOW),
    ("P", 21, 2, GREEN),
    ("[", 23, 2, GREEN),
    ("]", 25, 2, GREEN),
    ("\\", 27, 3, GREEN),
]

ROW_A: list[tuple[str, int, int, str]] = [
    ("Caps lock", 0, 4, GRAY),
    ("A", 4, 2, YELLOW),
    ("S", 6, 2, YELLOW),
    ("D", 8, 2, GREEN),
    ("F", 10, 2, CYAN),
    ("G", 12, 2, CYAN),
    ("H", 14, 2, PURPLE),
    ("J", 16, 2, PURPLE),
    ("K", 18, 2, PINK),
    ("L", 20, 2, YELLOW),
    (";", 22, 2, GREEN),
    ("'", 24, 2, GREEN),
    ("Enter", 26, 4, GRAY),
]

ROW_Z: list[tuple[str, int, int, str]] = [
    ("Shift", 0, 5, GRAY),
    ("Z", 5, 2, YELLOW),
    ("X", 7, 2, YELLOW),
    ("C", 9, 2, GREEN),
    ("V", 11, 2, CYAN),
    ("B", 13, 2, CYAN),
    ("N", 15, 2, PURPLE),
    ("M", 17, 2, PURPLE),
    (",", 19, 2, PINK),
    (".", 21, 2, YELLOW),
    ("/", 23, 2, GREEN),
    ("Shift", 25, 5, GRAY),
]

ROW_SPACE: list[tuple[str, int, int, str]] = [
    ("Ctrl", 0, 3, GRAY),
    ("Win", 3, 3, GRAY),
    ("Alt", 6, 3, GRAY),
    ("Space", 9, 12, GRAY),
    ("Alt", 21, 3, GRAY),
    ("Win", 24, 3, GRAY),
    ("Ctrl", 27, 3, GRAY),
]

KEYBOARD_ROWS = [ROW_NUMBER, ROW_Q, ROW_A, ROW_Z, ROW_SPACE]
GRID_COLUMNS = 30
