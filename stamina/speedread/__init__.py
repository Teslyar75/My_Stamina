"""Отсек «СКОРОЧТЕНИЕ» Star Typing: гипердрайв (RSVP), тренажёры обзора, библиотека.

SpeedReadScreen — ленивый экспорт (import только при открытии отсека).
"""
from __future__ import annotations

__all__ = ["SpeedReadScreen"]


def __getattr__(name: str):
    if name == "SpeedReadScreen":
        from .screen import SpeedReadScreen
        return SpeedReadScreen
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
