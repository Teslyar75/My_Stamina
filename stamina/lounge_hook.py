"""Подключение вкладки «ОТДЫХ» — комната отдыха экипажа (простые игры).

Если пакет упал при импорте — Star Typing работает без вкладки; причина
в %APPDATA%\\Stamina\\lounge_error.log.
"""
from __future__ import annotations

from stamina.i18n import t

import time
import traceback

KEY, TITLE = "lounge", t("ОТДЫХ")


def _log(text: str) -> None:
    try:
        from stamina.pilots import ROOT_DIR as DATA_DIR
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "lounge_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:  # noqa: BLE001
        pass


def load_class():
    try:
        from stamina.lounge import LoungeScreen
        return LoungeScreen
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None


def create(cls, master, app):
    try:
        return cls(master, app)
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None
