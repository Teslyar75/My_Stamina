"""Фоновые движки скинов: единый интерфейс start / stop / resize / set_speed.

`living_space` остаётся основной реализацией для скина «Звездолёт».
Остальные скины рисуют затемнённый bg-кадр + лёгкую анимацию поверх.
"""

from __future__ import annotations

from typing import Any, Protocol


class BackgroundEngine(Protocol):
    def start(self, canvas: Any) -> None: ...
    def stop(self) -> None: ...
    def resize(self, w: int, h: int) -> None: ...
    def set_speed(self, cpm: float) -> None: ...


def get_engine_name(theme_data: dict | None = None) -> str:
    from stamina import theme as th
    data = theme_data or th.current()
    bg = data.get("background") or {}
    return str(bg.get("engine") or "living_space")


def create_image_backdrop(theme_id: str):
    """Простой фон по картинке скина (sonar/gears/candles/city_rain/zen)."""
    from stamina.backgrounds.image_backdrop import ImageBackdrop
    return ImageBackdrop(theme_id)
