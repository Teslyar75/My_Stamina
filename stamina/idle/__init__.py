"""Простой: слайдшоу в стиле скина + радио скина (порт веб-модуля S8 E2).

Через N минут без клавиатуры (настройки → ЕЩЁ) — полноэкранное слайдшоу поверх окна и
станция по жанрам скина с плавным входом до ~30 %. Первое нажатие закрывает и НЕ уходит в набор.
Работает только в скинах, у которых в JSON есть блок ``slideshow`` («Звездолёт» не затронут).
Картинки: Wikimedia Commons (без ключа), кэш на диске; без сети — фото скина.
"""

from __future__ import annotations

IDLE_MINUTES = (0, 1, 3, 5, 10, 15)
IDLE_DEFAULTS = {"idle_minutes": 3, "idle_radio": True, "idle_after": "stop", "idle_provider": "auto"}
SLIDE_MS = 12_000
FADE_MS = 6_000
XFADE_MS = 1_200      # плавная смена слайдов
XFADE_STEPS = 18     # ~15 кадров/с, кадры смешиваются в потоке
GIF_MAX_FRAMES = 60  # анимированный GIF — не больше 60 кадров
RADIO_TARGET = 0.3


def is_idle(last: float, now: float, minutes: int) -> bool:
    return minutes > 0 and now - last >= minutes * 60


def fade_volume(elapsed_ms: float, dur_ms: float, target: float) -> float:
    if dur_ms <= 0:
        return target
    return max(0.0, min(target, elapsed_ms / dur_ms * target))


def pick_station(stations: list[dict], pinned: list[str] | None = None) -> dict | None:
    for p in pinned or []:
        for s in stations:
            if p.lower() in str(s.get("name", "")).lower():
                return s
    return stations[0] if stations else None


def settings_of(st: dict) -> dict:
    out = {k: st.get(k, v) for k, v in IDLE_DEFAULTS.items()}
    if out["idle_minutes"] not in IDLE_MINUTES:
        out["idle_minutes"] = IDLE_DEFAULTS["idle_minutes"]
    return out
