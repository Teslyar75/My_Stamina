"""Isometric projection helpers for terraformer map rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math

from stamina.terraformer_trainer import Camera


TILE_W = 64

# ─── zoom constants (match Camera) ──────────────────────────────────────────
ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.25


@dataclass(frozen=True)
class TileMetrics:
    """Precomputed metrics for a given zoom level."""
    hw: float
    hh: float
    ox: float
    oy: float


def tile_metrics(zoom: float, canvas_w: int, canvas_h: int, cam: Camera) -> TileMetrics:
    """
    Compute half-width, half-height and screen origin for isometric projection.

    The origin (ox, oy) is chosen so that the camera's world center (cam.cx, cam.cy)
    maps to the canvas center.
    """
    hw = (TILE_W / 2) * zoom
    hh = (TILE_W / 4) * zoom

    ox = canvas_w / 2 - (cam.cx - cam.cy) * hw
    oy = canvas_h / 2 - (cam.cx + cam.cy) * hh

    return TileMetrics(hw=hw, hh=hh, ox=ox, oy=oy)


def world_to_screen(gx: float, gy: float, gz: float, m: TileMetrics) -> tuple[float, float]:
    """Convert grid (cell) coordinates to screen coordinates."""
    sx = (gx - gy) * m.hw + m.ox
    sy = (gx + gy) * m.hh - gz * m.hh * 2 + m.oy
    return sx, sy


def screen_to_world(sx: float, sy: float, m: TileMetrics) -> tuple[float, float]:
    """
    Inverse projection for ground level (gz=0).
    Returns (gx, gy) in grid coordinates.
    """
    dx = sx - m.ox
    dy = sy - m.oy
    gx = (dx / m.hw + dy / m.hh) / 2
    gy = (dy / m.hh - dx / m.hw) / 2
    return gx, gy


def tile_polygon(gx: int, gy: int, gz: int, m: TileMetrics) -> list[float]:
    """
    Return the 8 screen coordinates (x0,y0,x1,y1,x2,y2,x3,y3) of the diamond
    for cell (gx, gy) at height gz.
    Order: top, right, bottom, left (clockwise from north).
    """
    # Top corner
    x0, y0 = world_to_screen(gx, gy, gz + 1, m)
    # Right corner
    x1, y1 = world_to_screen(gx + 1, gy, gz + 1, m)
    # Bottom corner
    x2, y2 = world_to_screen(gx + 1, gy + 1, gz + 1, m)
    # Left corner
    x3, y3 = world_to_screen(gx, gy + 1, gz + 1, m)

    return [x0, y0, x1, y1, x2, y2, x3, y3]


def pick_tile(sx: float, sy: float, m: TileMetrics, w: int, h: int) -> Optional[tuple[int, int]]:
    """
    Convert screen coordinates to grid cell (gx, gy).
    Returns None if outside map bounds.
    Uses math.floor for correct handling of negative coordinates.
    """
    gx_f, gy_f = screen_to_world(sx, sy, m)
    gx = math.floor(gx_f)
    gy = math.floor(gy_f)

    if 0 <= gx < w and 0 <= gy < h:
        return gx, gy
    return None


def zoom_at(direction: int, sx: float, sy: float, canvas_w: int, canvas_h: int,
            cam: Camera, zoom: float) -> float:
    """
    Zoom around a screen point (like Camera.zoom_at for flat view).
    Returns the new zoom value.
    """
    old_cell = (TILE_W / 2) * zoom
    # Screen to world before zoom
    dx = sx - canvas_w / 2
    dy = sy - canvas_h / 2
    wx = cam.cx + (dx / old_cell - dy / (old_cell / 2)) / 2
    wy = cam.cy + (dx / old_cell + dy / (old_cell / 2)) / 2

    if direction < 0:
        zoom = min(ZOOM_MAX, zoom * ZOOM_STEP)
    elif direction > 0:
        zoom = max(ZOOM_MIN, zoom / ZOOM_STEP)

    new_cell = (TILE_W / 2) * zoom
    # Keep world point under cursor
    cam.cx = wx - (dx / new_cell - dy / (new_cell / 2)) / 2
    cam.cy = wy - (dx / new_cell + dy / (new_cell / 2)) / 2

    return zoom


def visible_cell_bounds(m: TileMetrics, w: int, h: int, canvas_w: int, canvas_h: int,
                        margin: int = 1) -> tuple[int, int, int, int]:
    """
    Return (min_gx, min_gy, max_gx, max_gy) of cells that intersect the viewport.
    Includes a 1-cell margin by default for edge tiles.
    """
    # Four corners of the screen in world coords
    corners = [
        screen_to_world(0, 0, m),
        screen_to_world(canvas_w, 0, m),
        screen_to_world(0, canvas_h, m),
        screen_to_world(canvas_w, canvas_h, m),
    ]
    gxs = [c[0] for c in corners]
    gys = [c[1] for c in corners]

    min_gx = max(0, math.floor(min(gxs)) - margin)
    max_gx = min(w - 1, math.ceil(max(gxs)) + margin)
    min_gy = max(0, math.floor(min(gys)) - margin)
    max_gy = min(h - 1, math.ceil(max(gys)) + margin)

    return min_gx, min_gy, max_gx, max_gy