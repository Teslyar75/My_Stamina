"""Фоновые движки скинов.

- `living_space` — штатная космическая сцена (stamina.living_space.Scene)
- sonar / gears / candles / city_rain / zen — SkinScene из backgrounds.scenes
"""

from __future__ import annotations

from typing import Any


def engine_for_theme(theme_data: dict | None = None) -> str:
    from stamina import theme as th
    data = theme_data or th.current()
    bg = data.get("background") or {}
    return str(bg.get("engine") or "living_space")


def make_scene(w: int, h: int, mode: str, theme_data: dict | None = None):
    """Фабрика сцены для LivingSpace (тот же контракт, что Scene)."""
    from stamina import theme as th
    data = theme_data or th.current()
    engine = engine_for_theme(data)
    tid = str(data.get("id") or th.theme_id())
    if engine == "living_space" or engine not in (
        "sonar", "gears", "candles", "city_rain", "zen", "generic",
    ):
        if engine == "living_space":
            from stamina.living_space import Scene
            return Scene(w, h, mode)
        # неизвестный → skin generic с картинкой
        from stamina.backgrounds.scenes import SkinScene
        return SkinScene(w, h, mode=mode, theme_id=tid)
    from stamina.backgrounds.scenes import make_skin_scene
    return make_skin_scene(w, h, mode, tid, engine)


def create_image_backdrop(theme_id: str) -> Any:
    from stamina.backgrounds.image_backdrop import ImageBackdrop
    return ImageBackdrop(theme_id)
