from __future__ import annotations

import random
import time
from pathlib import Path

import tkinter as tk

from stamina import theme

try:
    from PIL import Image, ImageEnhance, ImageTk
except Exception:  # noqa: BLE001
    Image = None
    ImageEnhance = None
    ImageTk = None


class Slideshow:
    """Background slideshow with lazy decode, preloading, and crossfade.

    Never blocks UI. Frames are file paths; missing/bad files are skipped.
    """

    def __init__(self, canvas: tk.Canvas, *, interval_ms: int = 25000, fade_ms: int = 900,
                 scrim_alpha: float = 0.42):
        self.canvas = canvas
        self.interval_ms = max(3000, int(interval_ms))
        self.fade_ms = max(120, int(fade_ms))
        self.scrim_alpha = float(scrim_alpha)
        self._frames: list[Path] = []
        self._deck: list[Path] = []
        self._current: Path | None = None
        self._next: Path | None = None
        self._photo = None
        self._photo_next = None
        self._photo_overlay = None
        self._job = None
        self._fade_job = None
        self._running = False
        self._size = (1, 1)
        self._last_switch = 0.0
        self._scrim_color = "#0B0E14"
        self._preload_cache: dict[tuple[str, int, int], object] = {}
        self.canvas.bind("<Configure>", self._on_configure, add="+")
        self.canvas.bind("<Destroy>", lambda _e: self.stop(), add="+")

    def set_frames(self, frames: list[Path | str]) -> None:
        paths = []
        seen = set()
        for f in frames:
            p = Path(f)
            k = str(p).lower()
            if k in seen:
                continue
            seen.add(k)
            if p.is_file():
                paths.append(p)
        cur = self._current
        self._frames = paths
        # keep deck stable but ensure it contains only known frames
        self._deck = [p for p in self._deck if p in self._frames]
        if cur not in self._frames:
            self._current = None
        if not self._running:
            return
        if self._current is None and self._frames:
            self._show_next(initial=True)
        else:
            self._preload_next()

    def add_frame(self, frame: Path | str) -> None:
        p = Path(frame)
        if not p.is_file():
            return
        if any(str(p).lower() == str(x).lower() for x in self._frames):
            return
        self._frames.append(p)
        if self._running and self._current is None:
            self._show_next(initial=True)
        elif self._running and self._next is None:
            self._preload_next()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._frames:
            self._show_next(initial=True)
        self._schedule()

    def stop(self) -> None:
        self._running = False
        if self._job is not None:
            try:
                self.canvas.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._fade_job is not None:
            try:
                self.canvas.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None

    def _schedule(self) -> None:
        if self._job is not None:
            try:
                self.canvas.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if not self._running:
            return
        self._job = self.canvas.after(self.interval_ms, self._tick)

    def _tick(self) -> None:
        self._job = None
        if not self._running:
            return
        self._show_next(initial=False)
        self._schedule()

    def _on_configure(self, e) -> None:
        w, h = max(1, int(e.width)), max(1, int(e.height))
        if (w, h) == self._size:
            return
        self._size = (w, h)
        if self._current is not None:
            self._render_current()

    def _reshuffle(self) -> None:
        prev_last = self._deck[-1] if self._deck else self._current
        deck = list(self._frames)
        random.shuffle(deck)
        if prev_last is not None and len(deck) > 1 and deck and deck[0] == prev_last:
            deck.append(deck.pop(0))
        self._deck = deck

    def _pick_next(self) -> Path | None:
        if not self._frames:
            return None
        if not self._deck:
            self._reshuffle()
        while self._deck and self._deck[0] not in self._frames:
            self._deck.pop(0)
        if not self._deck:
            self._reshuffle()
        return self._deck.pop(0) if self._deck else None

    def _preload_next(self) -> None:
        if self._next is not None and self._next in self._frames:
            return
        nxt = self._pick_next()
        if nxt is None:
            return
        self._next = nxt
        self._decode_async(nxt)

    def _show_next(self, *, initial: bool) -> None:
        if self._next is None:
            self._preload_next()
        nxt = self._next
        self._next = None
        if nxt is None or nxt not in self._frames:
            return
        prev = self._current
        self._current = nxt
        self._last_switch = time.monotonic()
        self._render_current(prev=prev if not initial else None)
        self._preload_next()

    def _decode(self, path: Path):
        if Image is None or ImageTk is None:
            return None
        w, h = self._size
        key = (str(path).lower(), w, h)
        if key in self._preload_cache:
            return self._preload_cache[key]
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                iw, ih = im.size
                if iw <= 0 or ih <= 0:
                    return None
                scale = max(w / iw, h / ih)
                nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
                im = im.resize((nw, nh), Image.LANCZOS)
                left = max(0, (nw - w) // 2)
                top = max(0, (nh - h) // 2)
                im = im.crop((left, top, left + w, top + h))
                if ImageEnhance is not None:
                    im = ImageEnhance.Brightness(im).enhance(0.72)
                photo = ImageTk.PhotoImage(im)
        except Exception:
            return None
        self._preload_cache[key] = photo
        # keep cache small
        if len(self._preload_cache) > 8:
            for k in list(self._preload_cache.keys())[:-6]:
                self._preload_cache.pop(k, None)
        return photo

    def _decode_async(self, path: Path) -> None:
        # Decode in UI thread lazily but quickly; files are local/cache and resized.
        # This avoids Tk threading issues; call is cheap once cached.
        self.canvas.after_idle(lambda p=path: self._decode(p))

    def _render_current(self, prev: Path | None = None) -> None:
        if self._current is None:
            return
        photo = self._decode(self._current)
        if photo is None:
            # bad frame - drop it
            self._frames = [p for p in self._frames if p != self._current]
            self._current = None
            self._show_next(initial=True)
            return
        if prev is not None and self.fade_ms > 0 and Image is not None and ImageTk is not None:
            prev_photo = self._decode(prev)
            if prev_photo is not None:
                self._fade(prev_photo, photo)
                return
        self._draw_photo(photo)

    def _draw_photo(self, photo) -> None:
        self._photo = photo
        self.canvas.delete("slide")
        w, h = self._size
        self.canvas.create_image(0, 0, anchor="nw", image=photo, tags=("slide",))
        self._draw_scrim(w, h)
        self.canvas.tag_lower("slide")

    def _draw_scrim(self, w: int, h: int) -> None:
        self.canvas.delete("scrim")
        # Tk has no true alpha fill; approximate with stipple if available.
        # Use a dark rectangle; visual scrim is complemented by UI panel backgrounds.
        color = self._scrim_color
        try:
            self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="", stipple="gray50", tags=("scrim",))
        except tk.TclError:
            self.canvas.create_rectangle(0, 0, w, h, fill=color, outline="", tags=("scrim",))
        self.canvas.tag_raise("scrim")

    def _fade(self, prev_photo, next_photo) -> None:
        if self._fade_job is not None:
            try:
                self.canvas.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None
        steps = 8
        delay = max(20, self.fade_ms // steps)

        def step(i=0):
            if not self._running:
                return
            if i >= steps:
                self._photo_overlay = None
                self._draw_photo(next_photo)
                return
            # Crossfade approximation: draw next, then overlay previous with increasing stipple sparsity.
            self.canvas.delete("slide")
            self.canvas.delete("scrim")
            self._photo = next_photo
            self._photo_next = prev_photo
            self.canvas.create_image(0, 0, anchor="nw", image=next_photo, tags=("slide",))
            stipples = ["gray75", "gray50", "gray25", "gray12"]
            st = stipples[min(len(stipples) - 1, i * len(stipples) // steps)]
            try:
                self.canvas.create_image(0, 0, anchor="nw", image=prev_photo, tags=("slide", "fade"), stipple=st)
            except tk.TclError:
                pass
            self._draw_scrim(*self._size)
            self.canvas.tag_lower("slide")
            self._fade_job = self.canvas.after(delay, lambda: step(i + 1))

        step(0)
