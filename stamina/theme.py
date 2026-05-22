"""Цвета, шрифты и размеры — как в Stamina2_XAML (WPF MainWindow.xaml)."""

# --- Цвета клавиш (1:1 из MainWindow.xaml) ---
PINK = "#EA6E91"      # #FFEA6E91 — мизинец
YELLOW = "#F0E110"    # #FFF0E110 — безымянный
GREEN = "#10F013"     # #FF10F013 — средний
CYAN = "#19C0E0"      # #FF19C0E0 — указательный
PURPLE = "#D710F0"    # #FFD710F0 — указательный (внешний)
GRAY = "#83837B"      # #FF83837B — служебные клавиши
HIGHLIGHT = "#FF0000" # текущая клавиша подсвечивается красным (как в C#)

# --- Цвета окна ---
# В WPF Window по умолчанию белый — повторяем точно.
WINDOW_BG = "#FFFFFF"
PANEL_BG = "#FFFFFF"

# Цветовая полоса набора: уже набранная часть и оставшаяся.
SEQUENCE_DONE_BG = "#19C0E0"      # бирюзовый — как клавиши указательного пальца
SEQUENCE_REMAINING_BG = "#9A9A9A" # средне-серый, чтобы тёмный текст был читаем
SEQUENCE_BORDER = "#5A5A5A"

TEXT_FG = "#1A1A1A"
MUTED_FG = "#666666"

# --- Шрифты ---
FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
# Моноширинный — чтобы подчёркивание точно «садилось» под букву.
FONT_SEQUENCE = ("Consolas", 22)
FONT_KEY = ("Segoe UI", 14)
FONT_KEY_WIDE = ("Segoe UI", 11)

# --- Геометрия клавиш ---
KEY_RADIUS = 10        # CornerRadius="10" в XAML
KEY_PADX = 2
KEY_PADY = 2

# --- Размеры окна (Width=1050 Height=450 из MainWindow.xaml) ---
WINDOW_SIZE = "1050x460"
WINDOW_MIN = (940, 420)
KEYBOARD_MAX_WIDTH = 1050
KEYBOARD_ROW_HEIGHT = 52
KEYBOARD_HEIGHT = KEYBOARD_ROW_HEIGHT * 5 + KEY_PADY * 2 * 5
