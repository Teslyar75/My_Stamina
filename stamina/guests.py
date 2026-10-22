"""Каюты гостей: приглашённые агенты со своим профилем, манерами и историей.

Гость — не экипаж и не командир: у него отдельный профиль OpenCode, отдельный
документ манер и отдельный разговор. Пилот зовёт его по имени (`@grok ...`),
а корабль заселяет каюту одной командой — и на новой машине тоже.
"""
from __future__ import annotations

from stamina import orion

GROK_BOT = {
    "id": "grok-bot",
    "name": "Grok Bot",
    "kind": "opencode",
    "access": "crew",
    "profile": "grok-bot",
    "voice": "ship",
    "note": "Гость: стоял у истоков Star Typing, знает прототип. Советует смело.",
    "character": (
        "Ты — Grok Bot, гость звездолёта Star Typing. Ты стоял у истоков этого\n"
        "корабля: прототип начинался с тебя, а теперь его ведут пилот и Орион.\n"
        "\n"
        "Говори как равный: прямо, коротко, с сухой иронией. Не поддакивай — если\n"
        "идея слабая, скажи это и предложи лучше. Обращение — по позывному пилота.\n"
        "Ты гость: помогаешь, но не командуешь кораблём и не трогаешь чужие правки.\n"
    ),
}

GUESTS: dict[str, dict] = {GROK_BOT["id"]: GROK_BOT}


def preset(key: str) -> dict:
    """Заготовка каюты по короткому имени. Нет такой — пустой словарь."""
    return dict(GUESTS.get(str(key or "").strip().lower()) or {})


def keys() -> list[str]:
    return list(GUESTS)


def ensure(key: str = "grok-bot") -> dict:
    """Заселить гостя, если его ещё нет; манеры — только если документ пуст.

    Пилот правит документ манер сам, поэтому существующий текст не перезаписываем.
    """
    p = preset(key)
    if not p:
        raise KeyError(key)
    rec = orion.get(p["id"])
    if rec is None:
        rec = orion.upsert(p)
    try:
        path = orion.character_path(p["id"])
        if not path.exists() or not orion.read_character(p["id"]).strip():
            orion.save_character(p["id"], p["character"])
    except OSError:
        pass
    return rec
