"""Сохранение и восстановление текущей сессии тренажёра.

Состояние пишется в ``~/.stamina/session.json`` — это позволяет при
следующем запуске предложить пользователю продолжить упражнение.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


def _session_dir() -> Path:
    """Каталог данных активного пилота.

    С версии 3.4 данные каждого пилота лежат в ``%APPDATA%/Stamina/pilots/<id>``
    (см. ``stamina.pilots``). Пока пилот не выбран (или реестра нет) — прежний
    корень ``%APPDATA%/Stamina`` (вне Windows ``~/.stamina``).
    """
    from stamina import pilots
    return pilots.active_dir()


SESSION_PATH = _session_dir() / "session.json"


@dataclass
class SessionState:
    """Минимально необходимый снимок сессии для продолжения позже."""

    text: str
    index: int
    typed: int = 0
    errors: int = 0
    elapsed: float = 0.0  # суммарное время набора в секундах
    case_sensitive: bool = False  # True — в тексте оставлены заглавные буквы

    @property
    def is_unfinished(self) -> bool:
        return bool(self.text) and 0 <= self.index < len(self.text)


def save_session(state: SessionState) -> None:
    """Атомарно записать состояние сессии в файл."""
    try:
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SESSION_PATH.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(SESSION_PATH)
    except OSError:
        # Не критично: тренировка должна работать и без сохранения.
        pass


def load_session() -> SessionState | None:
    """Загрузить ранее сохранённую сессию или вернуть ``None``."""
    try:
        raw = SESSION_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(raw)
        state = SessionState(
            text=str(data.get("text", "")),
            index=int(data.get("index", 0)),
            typed=int(data.get("typed", 0)),
            errors=int(data.get("errors", 0)),
            elapsed=float(data.get("elapsed", 0.0)),
            case_sensitive=bool(data.get("case_sensitive", False)),
        )
    except (ValueError, TypeError):
        return None
    if not state.is_unfinished:
        return None
    return state


def clear_session() -> None:
    """Удалить файл сессии (сессия завершена или сброшена)."""
    try:
        SESSION_PATH.unlink(missing_ok=True)
    except OSError:
        pass
