"""Подключение вкладки «ДОКУМЕНТЫ» — тексты и снимки пилота.

Если пакет упал при импорте — Star Typing работает без вкладки; причина
в %APPDATA%\\Stamina\\docs_error.log.
"""
from __future__ import annotations

from stamina.i18n import t

import time
import traceback

KEY, TITLE = "docs", t("ДОКУМЕНТЫ")


def _log(text: str) -> None:
    try:
        from stamina.pilots import ROOT_DIR as DATA_DIR  # журнал общий для экипажа
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "docs_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:  # noqa: BLE001
        pass


def load_class():
    """Класс экрана DocsScreen или None (без исключений)."""
    try:
        from stamina.docs_screen import DocsScreen
        return DocsScreen
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None


def create(cls, master, app):
    """Создать экран; при ошибке — None и запись в журнал."""
    try:
        return cls(master, app)
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None
