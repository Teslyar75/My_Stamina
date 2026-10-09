"""Физическая клавиатура: английские и русские подписи, зоны пальцев.

Каждая клавиша: ``(id, en, ru, ширина_в_юнитах, палец)``. Ширина каждого
ряда — 15 юнитов, как у обычной клавиатуры ноутбука без цифрового блока.
"""

from __future__ import annotations

from stamina import theme
from stamina.i18n import t

# Пальцы
L_PINKY, L_RING, L_MIDDLE, L_INDEX, R_INDEX, R_MIDDLE, R_RING, R_PINKY, THUMB, MOD = range(10)

FINGER_NAMES = {
    L_PINKY: t("левый мизинец"),
    L_RING: t("левый безымянный"),
    L_MIDDLE: t("левый средний"),
    L_INDEX: t("левый указательный"),
    R_INDEX: t("правый указательный"),
    R_MIDDLE: t("правый средний"),
    R_RING: t("правый безымянный"),
    R_PINKY: t("правый мизинец"),
    THUMB: t("большой палец"),
    MOD: "",
}

FINGER_COLORS = {
    L_PINKY: theme.ZONE_PINKY,
    L_RING: theme.ZONE_RING,
    L_MIDDLE: theme.ZONE_MIDDLE,
    L_INDEX: theme.ZONE_L_INDEX,
    R_INDEX: theme.ZONE_R_INDEX,
    R_MIDDLE: theme.ZONE_MIDDLE,
    R_RING: theme.ZONE_RING,
    R_PINKY: theme.ZONE_PINKY,
    THUMB: theme.ZONE_THUMB,
    MOD: theme.ZONE_MOD,
}

Key = tuple[str, str, str, float, int]

ROWS: list[list[Key]] = [
    [
        ("`", "`", "ё", 1, L_PINKY), ("1", "1", "1", 1, L_PINKY),
        ("2", "2", "2", 1, L_RING), ("3", "3", "3", 1, L_MIDDLE),
        ("4", "4", "4", 1, L_INDEX), ("5", "5", "5", 1, L_INDEX),
        ("6", "6", "6", 1, R_INDEX), ("7", "7", "7", 1, R_INDEX),
        ("8", "8", "8", 1, R_MIDDLE), ("9", "9", "9", 1, R_RING),
        ("0", "0", "0", 1, R_PINKY), ("-", "-", "-", 1, R_PINKY),
        ("=", "=", "=", 1, R_PINKY), ("bksp", "⌫", "⌫", 2, MOD),
    ],
    [
        ("tab", "Tab", "Tab", 1.5, MOD), ("q", "Q", "Й", 1, L_PINKY),
        ("w", "W", "Ц", 1, L_RING), ("e", "E", "У", 1, L_MIDDLE),
        ("r", "R", "К", 1, L_INDEX), ("t", "T", "Е", 1, L_INDEX),
        ("y", "Y", "Н", 1, R_INDEX), ("u", "U", "Г", 1, R_INDEX),
        ("i", "I", "Ш", 1, R_MIDDLE), ("o", "O", "Щ", 1, R_RING),
        ("p", "P", "З", 1, R_PINKY), ("[", "[", "Х", 1, R_PINKY),
        ("]", "]", "Ъ", 1, R_PINKY), ("\\", "\\", "\\", 1.5, R_PINKY),
    ],
    [
        ("caps", "Caps", "Caps", 1.75, MOD), ("a", "A", "Ф", 1, L_PINKY),
        ("s", "S", "Ы", 1, L_RING), ("d", "D", "В", 1, L_MIDDLE),
        ("f", "F", "А", 1, L_INDEX), ("g", "G", "П", 1, L_INDEX),
        ("h", "H", "Р", 1, R_INDEX), ("j", "J", "О", 1, R_INDEX),
        ("k", "K", "Л", 1, R_MIDDLE), ("l", "L", "Д", 1, R_RING),
        (";", ";", "Ж", 1, R_PINKY), ("'", "'", "Э", 1, R_PINKY),
        ("enter", "Enter", "Enter", 2.25, MOD),
    ],
    [
        ("lshift", "Shift", "Shift", 2.25, MOD), ("z", "Z", "Я", 1, L_PINKY),
        ("x", "X", "Ч", 1, L_RING), ("c", "C", "С", 1, L_MIDDLE),
        ("v", "V", "М", 1, L_INDEX), ("b", "B", "И", 1, L_INDEX),
        ("n", "N", "Т", 1, R_INDEX), ("m", "M", "Ь", 1, R_INDEX),
        (",", ",", "Б", 1, R_MIDDLE), (".", ".", "Ю", 1, R_RING),
        ("/", "/", ".", 1, R_PINKY), ("rshift", "Shift", "Shift", 2.75, MOD),
    ],
    [
        ("lctrl", "Ctrl", "Ctrl", 1.5, MOD), ("lwin", "Win", "Win", 1.25, MOD),
        ("lalt", "Alt", "Alt", 1.25, MOD), ("space", "", "", 7, THUMB),
        ("ralt", "Alt", "Alt", 1.25, MOD), ("rwin", "Win", "Win", 1.25, MOD),
        ("rctrl", "Ctrl", "Ctrl", 1.5, MOD),
    ],
]

ROW_UNITS = 15.0

# Клавиши «домашнего ряда» — на F и J (А и О) есть насечки.
HOME_BUMPS = {"f", "j"}

KEY_FINGER: dict[str, int] = {k[0]: k[4] for row in ROWS for k in row}
KEY_LABELS: dict[str, tuple[str, str]] = {k[0]: (k[1], k[2]) for row in ROWS for k in row}

# Символ → id клавиши (в обеих раскладках, в нижнем регистре).
CHAR_TO_KEY: dict[str, str] = {" ": "space"}
for _row in ROWS:
    for _kid, _en, _ru, _w, _f in _row:
        if _f == MOD or _kid == "space":
            continue
        CHAR_TO_KEY.setdefault(_en.lower(), _kid)
        if _ru != _en:
            CHAR_TO_KEY.setdefault(_ru.lower(), _kid)
# В русской раскладке «,» — это Shift + «.»/«/» — для подсказки укажем «/».
CHAR_TO_KEY.setdefault("ъ", "]")


# Символы, набираемые с Shift: символ → клавиша (английская раскладка).
SHIFTED_EN = {"~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
              "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
              ":": ";", '"': "'", "<": ",", ">": ".", "?": "/"}
# Знаки в русской раскладке (ЙЦУКЕН): символ → (клавиша, нужен ли Shift).
PUNCT_RU = {".": ("/", False), ",": ("/", True), "!": ("1", True), '"': ("2", True),
            "№": ("3", True), ";": ("4", True), "%": ("5", True), ":": ("6", True),
            "?": ("7", True), "*": ("8", True), "(": ("9", True), ")": ("0", True),
            "-": ("-", False), "_": ("-", True), "=": ("=", False), "+": ("=", True),
            "\\": ("\\", False), "/": ("\\", True)}


# Немецкая раскладка QWERTZ на той же физической клавиатуре: подписи и символы.
DE_LABELS = {"y": "Z", "z": "Y", ";": "Ö", "'": "Ä", "[": "Ü", "]": "+", "-": "ß", "=": "´",
             "/": "-", "`": "^", "\\": "#"}
DE_CHAR_TO_KEY = {"z": "y", "y": "z", "ö": ";", "ä": "'", "ü": "[", "ß": "-", "ẞ": "-", "+": "]",
                  "#": "\\", "-": "/", ",": ",", ".": "."}
SHIFTED_DE = {"!": "1", '"': "2", "§": "3", "$": "4", "%": "5", "&": "6", "/": "7", "(": "8", ")": "9",
              "=": "0", "?": "-", "*": "]", "'": "\\", ";": ",", ":": ".", "_": "/", "°": "`"}
LATIN_LAYOUTS = {"en": "QWERTY", "de": "QWERTZ"}
# Украинская раскладка ЙЦУКЕН (Windows «Українська (розширена)»): отличия от русской.
UK_LABELS = {"s": "І", "'": "Є", "]": "Ї", "`": "'", "\\": "Ґ"}
UK_CHAR_TO_KEY = {"і": "s", "є": "'", "ї": "]", "ґ": "\\", "'": "`", "’": "`", "ʼ": "`"}
for _c, _k in UK_CHAR_TO_KEY.items():
    if _c.isalpha():
        CHAR_TO_KEY.setdefault(_c, _k)


def keyboard_for(text_lang: str) -> str:
    """Раскладка для подсказки по языку текста: ru/uk/be → ЙЦУКЕН, de → QWERTZ, остальное → QWERTY."""
    if text_lang in ("ru", "uk", "be"):
        return "ru"
    return "de" if text_lang == "de" else "en"


def label(kid: str, lang: str) -> tuple[str, str]:
    """(главная подпись, вторая подпись) клавиши для раскладки lang."""
    en, ru = KEY_LABELS[kid]
    if lang == "ru":
        return ru, en
    if lang == "de":
        return DE_LABELS.get(kid, en), ru
    if lang == "uk":
        return UK_LABELS.get(kid, ru), en
    return en, ru


def key_for_char(char: str | None, lang: str = "en") -> str | None:
    if not char:
        return None
    if lang == "de":
        if char in SHIFTED_DE:
            return SHIFTED_DE[char]
        low = char.lower() if char != "ẞ" else "ß"
        if low in DE_CHAR_TO_KEY:
            return DE_CHAR_TO_KEY[low]
        return CHAR_TO_KEY.get(low)
    if lang == "uk":
        low = char.lower()
        if low in UK_CHAR_TO_KEY:
            return UK_CHAR_TO_KEY[low]
        if char in PUNCT_RU:
            return PUNCT_RU[char][0]
        return CHAR_TO_KEY.get(low)
    if lang == "ru" and char in PUNCT_RU:
        return PUNCT_RU[char][0]
    if char in SHIFTED_EN:
        return SHIFTED_EN[char]
    return CHAR_TO_KEY.get(char.lower())


def needs_shift(char: str | None, lang: str = "en") -> bool:
    if not char:
        return False
    if char.isalpha():
        return char != char.lower()
    if lang == "de":
        return char in SHIFTED_DE
    if lang in ("ru", "uk") and char in PUNCT_RU:
        return PUNCT_RU[char][1]
    return char in SHIFTED_EN


def finger_for_char(char: str | None, lang: str = "en") -> int | None:
    kid = key_for_char(char, lang)
    return KEY_FINGER.get(kid) if kid else None


def is_cyrillic(char: str) -> bool:
    """Русские и украинские буквы (і ї є ґ тоже), апостроф — нет."""
    c = char.lower()
    return "а" <= c <= "я" or c in "ёіїєґўъ"
