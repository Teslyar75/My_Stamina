"""Подключение вкладки «СКОРОЧТЕНИЕ» (пакет stamina.speedread).

Если пакета нет или он упал при импорте — Star Typing работает без вкладки, а причина
пишется в %APPDATA%\\Stamina\\speedread_error.log.

load_class() только проверяет наличие файлов (без import тяжёлого модуля).
Реальный import — в create(), когда пилот впервые открывает отсек.
"""
from __future__ import annotations

from stamina.i18n import t

import time
import traceback
from pathlib import Path

KEY, TITLE = "speedread", t("СКОРОЧТЕНИЕ")

AVAILABLE = True
_SCREEN = Path(__file__).resolve().parent / "speedread" / "screen.py"


def _log(text: str) -> None:
    try:
        from stamina.pilots import ROOT_DIR as DATA_DIR  # логи общие для экипажа
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "speedread_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:  # noqa: BLE001
        pass


def load_class():
    """AVAILABLE, если пакет на месте; иначе None. Без import модуля экрана."""
    try:
        return AVAILABLE if _SCREEN.is_file() else None
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None


def create(cls, master, app):
    """Создать экран; при ошибке - None и запись в лог. Import — здесь."""
    try:
        if cls is None or cls is AVAILABLE:
            from stamina.speedread import SpeedReadScreen as cls
        return cls(master, app)
    except Exception:  # noqa: BLE001
        _log(traceback.format_exc())
        return None
