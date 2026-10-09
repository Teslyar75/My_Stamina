"""Подключение вкладки «АНГЛИЙСКИЙ» (пакет stamina.english).

Если пакета нет или он упал при импорте — Star Typing работает без вкладки, а причина
пишется в %APPDATA%\\Stamina\\english_error.log.
"""
from __future__ import annotations

import time
import traceback

KEY, TITLE = "english", "АНГЛИЙСКИЙ"


def _log(text: str) -> None:
    try:
        from stamina.pilots import ROOT_DIR as DATA_DIR  # логи общие для экипажа
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "english_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:  # noqa: BLE001
        pass


def load_class():
    """Класс экрана EnglishScreen или None (без исключений)."""
    try:
        from stamina.english import EnglishScreen
        return EnglishScreen
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None


def create(cls, master, app):
    """Создать экран; при ошибке - None и запись в лог."""
    try:
        return cls(master, app)
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None
