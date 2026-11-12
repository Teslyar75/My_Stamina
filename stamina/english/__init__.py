"""Вкладка «АНГЛИЙСКИЙ» для Star Typing. Подключается через stamina/english_hook.py.

EnglishScreen импортируется лениво — только при открытии отсека.
"""
from __future__ import annotations

__all__ = ["EnglishScreen", "TITLE"]


def __getattr__(name: str):
    if name == "EnglishScreen":
        from .screen import EnglishScreen
        return EnglishScreen
    if name == "TITLE":
        from .screen import EnglishScreen
        return EnglishScreen.TITLE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
