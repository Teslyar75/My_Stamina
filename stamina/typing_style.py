"""Оформление строки набора на мостике (порт «Мостик → Настройки» из веб-версии).

Чистые функции без Tk: какие размеры, цвета и шрифты брать из настроек.
Пустая строка в цвете или размере = «как в скине / как основной размер»,
поэтому скины продолжают задавать цвета, пока пилот не выбрал свои.
"""

from __future__ import annotations

FONT_KEYS = ("S", "M", "L", "XL", "XXL")
# размер букв в иллюминаторе (pt до масштабирования интерфейса)
FONT_SIZES = {"S": 20, "M": 26, "L": 32, "XL": 40, "XXL": 48}
# слово в окошке прицела (панель UPLINK)
BOX_SIZES = {"S": 16, "M": 19, "L": 22, "XL": 26, "XXL": 30}
FACES = ("mono", "sans", "serif", "system")
BLINKS = ("off", "on", "fast")

DEFAULTS = {
    "sight": True,            # рамка-прицел на текущей букве; выкл — только подчёркивание
    "cursor_font": "",        # размер буквы в прицеле ("" — как основной)
    "cursor_color": "",       # цвет буквы в прицеле ("" — белый)
    "typed_font": "",         # размер набранного ("" — как основной)
    "ahead_font": "",         # размер текста впереди ("" — как основной)
    "typing_face": "mono",    # шрифт строки набора
    "typed_color": "",        # цвет набранного ("" — из скина)
    "ahead_color": "",        # цвет текста впереди ("" — из скина)
    "sight_box_font": "L",    # размер слова в окошке прицела
    "sight_box_face": "mono",
    "sight_on_color": "",     # текущая буква в окошке прицела ("" — красная из скина)
}


def _font_key(value, fallback: str = "M") -> str:
    return value if value in FONT_KEYS else fallback


def size_for(st: dict, key: str) -> int:
    """Размер в pt для 'font' | 'typed_font' | 'ahead_font' | 'cursor_font'."""
    base = _font_key(st.get("font"), "M")
    if key == "font":
        return FONT_SIZES[base]
    return FONT_SIZES[_font_key(st.get(key) or base, base)]


def box_size(st: dict) -> int:
    return BOX_SIZES[_font_key(st.get("sight_box_font"), "L")]


def face(value) -> str:
    return value if value in FACES else "mono"


def color(st: dict, key: str, default: str) -> str:
    """Цвет из настроек (#RRGGBB) или default."""
    v = st.get(key) or ""
    if isinstance(v, str) and len(v) == 7 and v.startswith("#"):
        try:
            int(v[1:], 16)
            return v.upper()
        except ValueError:
            pass
    return default


def family_for(face_id: str, hud_family: str, mono_family: str) -> str:
    """Семейство шрифта Tk для выбранного начертания."""
    face_id = face(face_id)
    if face_id == "mono":
        return mono_family
    if face_id == "serif":
        return "Georgia"
    if face_id == "system":
        return "TkDefaultFont"
    return hud_family
