"""Комната отдыха экипажа: простые игры в стиле HUD.

LoungeScreen — ленивый экспорт (import только при открытии отсека).
"""
from __future__ import annotations

__all__ = ["LoungeScreen"]


def __getattr__(name: str):
    if name == "LoungeScreen":
        from .screen import LoungeScreen
        return LoungeScreen
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
