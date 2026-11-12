"""Отсек «РАДИОРУБКА»: онлайн-радио через radio-browser.info.

Экспорт RadioScreen/get_engine — ленивый: мини-бар на мостике не должен
тянуть весь экран радиостанций при старте.
"""
from __future__ import annotations

__all__ = ["RadioScreen", "get_engine"]


def __getattr__(name: str):
    if name == "RadioScreen":
        from .screen import RadioScreen
        return RadioScreen
    if name == "get_engine":
        from .engine import get_engine
        return get_engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
