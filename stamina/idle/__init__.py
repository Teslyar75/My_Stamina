"""Простой: слайдшоу в стиле скина + радио скина (порт веб-модуля S8 E2).

Через N минут без клавиатуры (настройки → ЕЩЁ) — полноэкранное слайдшоу поверх окна и
станция по жанрам скина с плавным входом до ~30 %. Первое нажатие закрывает и НЕ уходит в набор.
Работает только в скинах, у которых в JSON есть блок ``slideshow`` («Звездолёт» не затронут).
Картинки: Wikimedia Commons (без ключа), кэш на диске; без сети — фото скина.
"""

from __future__ import annotations

IDLE_MINUTES = (0, 1, 3, 5)
IDLE_DEFAULTS = {"idle_minutes": 1, "idle_radio": True, "idle_after": "stop", "idle_provider": "auto"}
SLIDE_MS = 12_000
FADE_MS = 1_500
XFADE_MS = 1_200      # плавная смена слайдов
XFADE_STEPS = 18     # ~15 кадров/с, кадры смешиваются в потоке
GIF_MAX_FRAMES = 60
DRIFT = 1.08         # кадр на 8 % больше экрана и медленно проплывает (Ken Burns)  # анимированный GIF — не больше 60 кадров
RADIO_TARGET = 0.4


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
    try:
        m = int(out["idle_minutes"])
    except (TypeError, ValueError):
        m = IDLE_DEFAULTS["idle_minutes"]
    out["idle_minutes"] = 5 if m > 5 else m  # старые 10/15 мин → 5
    if out["idle_minutes"] not in IDLE_MINUTES:
        out["idle_minutes"] = IDLE_DEFAULTS["idle_minutes"]
    return out


def order_stations(stations: list[dict], saved: str | None = None, pinned: list[str] | None = None) -> list[dict]:
    """Порядок волн для переключателя: выбранная в прошлый раз — первой, затем закреплённые скином."""
    prefs = ([saved] if saved else []) + list(pinned or [])
    prefs = [p.lower() for p in prefs if p]

    def rank(s: dict) -> int:
        n = str(s.get("name", "")).lower()
        if saved and n == saved.lower():
            return -1
        return next((i for i, p in enumerate(prefs) if p in n), len(prefs))

    return sorted(stations, key=rank)


def station_genre(st: dict) -> str:
    tags = [t.strip() for t in str(st.get("tags") or "").split(",") if t.strip()]
    return ", ".join(tags[:2])
