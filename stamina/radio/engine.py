"""Глобальный приёмник: играет в фоне между отсеками."""
from __future__ import annotations

import threading
from typing import Callable

from . import browser, store
from .player import StreamPlayer, backend_name, backend_ok

_engine: "RadioEngine | None" = None
_lock = threading.Lock()


def get_engine() -> "RadioEngine":
    global _engine
    with _lock:
        if _engine is None:
            _engine = RadioEngine()
        return _engine


class RadioEngine:
    def __init__(self) -> None:
        self.player = StreamPlayer()
        self.data = store.load()
        self.station: dict | None = self.data.get("last")
        self.history: list[str] = []  # треки сеанса
        self._listeners: list[Callable] = []
        self.player.set_volume(int(self.data.get("volume") or 70))
        self.player.set_meta_callback(self._on_meta)

    def reload_store(self) -> None:
        self.data = store.load()

    def subscribe(self, cb: Callable) -> None:
        if cb not in self._listeners:
            self._listeners.append(cb)

    def unsubscribe(self, cb: Callable) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass

    def _on_meta(self, title: str) -> None:
        if title and (not self.history or self.history[0] != title):
            self.history.insert(0, title)
            self.history = self.history[:40]
        self._notify()

    @property
    def playing(self) -> bool:
        return self.player.playing

    @property
    def track(self) -> str:
        return self.player.track

    @property
    def volume(self) -> int:
        return self.player.volume

    @property
    def backend(self) -> str | None:
        return backend_name()

    def ready(self) -> bool:
        return backend_ok()

    def play_station(self, station: dict) -> bool:
        if not station:
            return False
        url = station.get("url") or ""
        uuid = station.get("uuid") or ""
        if uuid:
            resolved = browser.register_click(uuid)
            if resolved:
                url = resolved
                station = dict(station)
                station["url"] = url
        if not url:
            return False
        ok = self.player.play(url, volume=int(self.data.get("volume") or 70))
        if ok:
            self.station = station
            self.data["last"] = station
            store.save(self.data)
            self._notify()
        return ok

    def stop(self) -> None:
        self.player.stop()
        self._notify()

    def toggle(self) -> None:
        if self.playing:
            self.stop()
        elif self.station:
            self.play_station(self.station)
        self._notify()

    def set_volume(self, vol: int) -> None:
        self.player.set_volume(vol)
        self.data["volume"] = int(vol)
        store.save(self.data)
        self._notify()

    def duck(self, level: int = 12) -> None:
        self.player.duck(level)
        self._notify()

    def unduck(self) -> None:
        self.player.unduck()
        self._notify()

    def next_favorite(self) -> None:
        favs = self.data.get("favorites") or []
        if not favs:
            return
        cur = (self.station or {}).get("uuid")
        idx = next((i for i, f in enumerate(favs) if f.get("uuid") == cur), -1)
        self.play_station(favs[(idx + 1) % len(favs)])

    def prev_favorite(self) -> None:
        favs = self.data.get("favorites") or []
        if not favs:
            return
        cur = (self.station or {}).get("uuid")
        idx = next((i for i, f in enumerate(favs) if f.get("uuid") == cur), 0)
        self.play_station(favs[(idx - 1) % len(favs)])

    def close(self) -> None:
        self.player.stop()
