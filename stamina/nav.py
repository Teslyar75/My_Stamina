"""Навигация по зонам (порт web shell/zones.ts + routes.ts).

Восемь зон в шапке: МОСТИК, АНГЛИЙСКИЙ, СКОРОЧТЕНИЕ, ОТДЫХ, РАДИОРУБКА, ЭФИР, ОРИОН, НАСТРОЙКИ.
Миссии, Свой текст, Бортжурнал и Настройки мостика — подменю Мостика.
Под шапкой — строка пути «МОСТИК › БОРТЖУРНАЛ» с кликабельными частями.
Модуль без Tk — его проверяют тесты.
"""

from __future__ import annotations

from stamina.i18n import t

ZONE_ORDER = ("bridge", "english", "speedread", "lounge", "radio", "comm", "orion", "settings")

# подменю Мостика: (экран, подпись)
BRIDGE_LEAVES = (
    ("bridge", "ПОЛЁТ"),
    ("missions", "МИССИИ"),
    ("cargo", "СВОЙ ТЕКСТ"),
    ("log", "БОРТЖУРНАЛ"),
    ("bridge_settings", "НАСТРОЙКИ МОСТИКА"),
)

ZONE_TITLES = {
    "bridge": "МОСТИК",
    "english": "АНГЛИЙСКИЙ",
    "speedread": "СКОРОЧТЕНИЕ",
    "lounge": "ОТДЫХ",
    "radio": "РАДИОРУБКА",
    "comm": "ЭФИР",
    "orion": "ОРИОН",
    "settings": "НАСТРОЙКИ",
}

# экраны вне зон: показываем отдельной строкой пути
EXTRA_TITLES = {"help": "СПРАВКА", "honor": "ДОСКА ПОЧЁТА"}

_BRIDGE_SCREENS = {k for k, _ in BRIDGE_LEAVES}


def zone_of(screen: str | None) -> str | None:
    """Зона, которой принадлежит экран (None — экран вне зон: справка, доска почёта)."""
    if screen in _BRIDGE_SCREENS:
        return "bridge"
    if screen in ZONE_TITLES:
        return screen
    return None


def zones(available: set[str] | None = None) -> list[str]:
    """Зоны по порядку; available — какие разделы реально загрузились."""
    return [z for z in ZONE_ORDER if available is None or z in available or z in ("bridge", "settings")]


def path(screen: str | None) -> list[tuple[str, str]]:
    """Путь для строки под шапкой: [(подпись, экран-цель), …]."""
    if screen is None:
        return []
    zone = zone_of(screen)
    if zone is None:
        return [(t(EXTRA_TITLES.get(screen, screen.upper())), screen)]
    segs = [(t(ZONE_TITLES[zone]), zone)]
    if zone == "bridge" and screen != "bridge":
        title = dict(BRIDGE_LEAVES)[screen]
        segs.append((t(title), screen))
    return segs
