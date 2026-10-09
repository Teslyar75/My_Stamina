"""Язык интерфейса: t("русская фраза") → перевод на выбранный язык (или сама фраза).

Переводы — JSON рядом с модулем: ru.json (все ключи), uk.json, en.json, de.json.
Ключ — исходная русская фраза (как в gettext), поэтому без перевода показывается русский текст.
Выбор хранится вне папок пилотов: <корень данных>/ui.json → {"ui_lang": "uk"}; общий для всех пилотов
и для экрана приветствия. Язык читается при запуске (до импорта экранов), смена — после перезапуска
(кнопка «ПЕРЕЗАПУСТИТЬ» делает это сразу). Переменная окружения STAMINA_LANG важнее файла.
Тексты для печати, словари и книги не переводятся — это содержимое, а не интерфейс.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
LANGS = {"ru": "Русский", "uk": "Українська", "en": "English", "de": "Deutsch"}
DEFAULT = "ru"

_lang = DEFAULT
_table: dict = {}


def _config_path() -> Path:
    from stamina import pilots
    return pilots.default_root() / "ui.json"


def saved_language() -> str:
    try:
        lang = json.loads(_config_path().read_text(encoding="utf-8")).get("ui_lang", "")
    except (OSError, ValueError, AttributeError):
        lang = ""
    return lang if lang in LANGS else ""


def save_language(lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(lang)
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["ui_lang"] = lang
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_table(lang: str) -> dict:
    if lang == DEFAULT:
        return {}
    try:
        data = json.loads((DIR / f"{lang}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v}


def set_language(lang: str) -> None:
    global _lang, _table
    _lang = lang if lang in LANGS else DEFAULT
    _table = load_table(_lang)


def language() -> str:
    return _lang


def t(key: str) -> str:
    """Перевод фразы интерфейса; нет перевода → исходная (русская) фраза."""
    return _table.get(key, key)


def _initial() -> str:
    env = os.environ.get("STAMINA_LANG", "")
    if env in LANGS:
        return env
    if "unittest" in sys.modules or "pytest" in sys.modules:      # тесты — всегда по-русски
        return DEFAULT
    return saved_language() or DEFAULT


set_language(_initial())
