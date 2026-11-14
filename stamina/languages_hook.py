"""Подключение отсека «ИНОСТРАННЫЕ ЯЗЫКИ»."""
from __future__ import annotations

from stamina.i18n import t

import time
import traceback
from pathlib import Path

KEY, TITLE = "languages", t("ИНОСТРАННЫЕ ЯЗЫКИ")

AVAILABLE = True
_SCREEN = Path(__file__).resolve().parent / "languages" / "screen.py"


def _log(text: str) -> None:
    try:
        from stamina.pilots import ROOT_DIR as DATA_DIR
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "languages_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:
        pass


def load_class():
    try:
        return AVAILABLE if _SCREEN.is_file() else None
    except Exception:
        _log(traceback.format_exc())
        return None


def create(cls, master, app):
    try:
        if cls is None or cls is AVAILABLE:
            from stamina.languages.screen import LanguagesScreen as cls
        return cls(master, app)
    except Exception:
        _log(traceback.format_exc())
        return None