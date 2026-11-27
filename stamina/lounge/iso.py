"""Isometric projection helpers for terraformer map rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math

from stamina.terraformer_trainer import Camera


ISO_RATIO = 0.62          # вертикальный угол камеры (h/w = 0.62 вместо 0.5)
TILE_W = 64               # ширина ромба (вертикальная диагональ)
TILE_H = int(TILE_W * ISO_RATIO)  # высота ромба = ширина * ISO_RATIO

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
    hh = (TILE_W * ISO_RATIO / 2) * zoom

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
    Uses ISO_RATIO for correct isometric projection.
    """
    old_cell = (TILE_W / 2) * zoom
    old_hh = (TILE_W * ISO_RATIO / 2) * zoom
    # Screen to world before zoom
    dx = sx - canvas_w / 2
    dy = sy - canvas_h / 2
    wx = cam.cx + (dx / old_cell - dy / old_hh) / 2
    wy = cam.cy + (dx / old_cell + dy / old_hh) / 2

    if direction < 0:
        zoom = min(ZOOM_MAX, zoom * ZOOM_STEP)
    elif direction > 0:
        zoom = max(ZOOM_MIN, zoom / ZOOM_STEP)

    new_cell = (TILE_W / 2) * zoom
    new_hh = (TILE_W * ISO_RATIO / 2) * zoom
    # Keep world point under cursor
    cam.cx = wx - (dx / new_cell - dy / new_hh) / 2
    cam.cy = wy - (dx / new_cell + dy / new_hh) / 2

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


def screen_to_world_at_gz(sx: float, sy: float, gz: float, m: TileMetrics) -> tuple[float, float]:
    """
    Inverse projection on a known gz plane.
    Returns (gx, gy) in grid coordinates at the specified gz.
    """
    dy_prime = (sy - m.oy) + gz * m.hh * 2
    dx = sx - m.ox
    gx = (dx / m.hw + dy_prime / m.hh) / 2
    gy = (dy_prime / m.hh - dx / m.hw) / 2
    return gx, gy


def point_in_diamond(sx: float, sy: float, polygon: list[float]) -> bool:
    """
    Hit-test a screen point against an 8-coord top diamond.
    Polygon order: top, right, bottom, left (clockwise from north).
    """
    x0, y0, x1, y1, x2, y2, x3, y3 = polygon
    # Use winding number / point-in-polygon test for convex quadrilateral
    # Check if point is on the same side of all edges
    def cross(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    
    c1 = cross(x0, y0, x1, y1, sx, sy)
    c2 = cross(x1, y1, x2, y2, sx, sy)
    c2 = cross(x1, y1, x2, y2, sx, sy)
    c3 = cross(x2, y2, x3, y3, sx, sy)
    c4 = cross(x3, y3, x0, y0, sx, sy)
    
    # All same sign (or zero)
    return (c1 >= 0 and c2 >= 0 and c3 >= 0 and c4 >= 0) or \
           (c1 <= 0 and c2 <= 0 and c3 <= 0 and c4 <= 0)


def pick_surface(sx: float, sy: float, m: TileMetrics, dug_grid: list[list[int]],
                 map_w: int, map_h: int) -> Optional[tuple[int, int, int]]:
    """
    Find the top-most terrain surface under the cursor.
    
    Returns (gx, gy, surface_gz) of the front-most hit, or None if no hit.
    surface_gz is the gz of the drawn top face (terrain_gz(dug) + 1, matching tile_polygon).
    """
    # Start from gz=0 unprojection as seed
    gx_f, gy_f = screen_to_world(sx, sy, m)
    seed_gx = math.floor(gx_f)
    seed_gy = math.floor(gy_f)
    
    # Search in a neighborhood around the seed
    # Iterate front-to-back: higher gx+gy first (closer to camera in isometric)
    candidates = []
    radius = 3
    for gy in range(seed_gy - radius, seed_gy + radius + 1):
        for gx in range(seed_gx - radius, seed_gx + radius + 1):
            if 0 <= gx < map_w and 0 <= gy < map_h:
                candidates.append((gx, gy))
    
    # Sort front-to-back: higher gx+gy first (closer to camera)
    candidates.sort(key=lambda c: -(c[0] + c[1]))
    
    for gx, gy in candidates:
        dug = dug_grid[gy][gx]
        surface_gz = terrain_gz(dug)  # This is the ground level
        top_gz = surface_gz + 1       # tile_polygon draws top at gz+1
        
        # Build the SAME top diamond the renderer draws
        poly = tile_polygon(gx, gy, surface_gz, m)
        
        if point_in_diamond(sx, sy, poly):
            return gx, gy, top_gz
    
    return None


def apply_zoom(direction: int, sx: float, sy: float, canvas_w: int, canvas_h: int,
               cam: Camera, zoom: float, dug_grid: list[list[int]] | None = None,
               map_w: int = 0, map_h: int = 0) -> float:
    """
    Surface-aware zoom around a screen point for isometric view.
    
    If dug_grid is provided, anchors on the visible top surface under the cursor.
    Otherwise falls back to gz=0 behavior (compatible with old zoom_at).
    """
    # Get current metrics
    m = tile_metrics(zoom, canvas_w, canvas_h, cam)
    
    # Find surface point to anchor on
    if dug_grid is not None and map_w > 0 and map_h > 0:
        hit = pick_surface(sx, sy, m, dug_grid, map_w, map_h)
        if hit is not None:
            gx, gy, surface_gz = hit
            # Use exact world coordinates on the surface (not cell center)
            anchor_gx, anchor_gy = screen_to_world_at_gz(sx, sy, surface_gz, m)
            anchor_gz = surface_gz
        else:
            # Fallback to gz=0
            anchor_gx, anchor_gy = screen_to_world(sx, sy, m)
            anchor_gz = 0.0
    else:
        # Old behavior: gz=0
        anchor_gx, anchor_gy = screen_to_world(sx, sy, m)
        anchor_gz = 0.0
    
    # Compute the camera values that would keep this world point at the same screen position
    # after zoom change. We solve for new cam.cx, cam.cy directly.
    # 
    # Screen position formulas:
    # sx = (gx - gy) * hw + canvas_w/2 - (cx - cy) * hw
    # sy = (gx + gy) * hh - gz * hh * 2 + canvas_h/2 - (cx + cy) * hh
    #
    # Solving for cx, cy:
    # cx - cy = (gx - gy) + canvas_w/(2*hw) - sx/hw
    # cx + cy = (gx + gy) - 2*gz + canvas_h/(2*hh) - sy/hh
    
    # Before zoom (current camera already satisfies this, but we compute target screen pos)
    sx_target = sx
    sy_target = sy
    
    # Apply zoom
    if direction < 0:
        zoom = min(ZOOM_MAX, zoom * ZOOM_STEP)
    elif direction > 0:
        zoom = max(ZOOM_MIN, zoom / ZOOM_STEP)
    
    # New metrics after zoom
    hw_new = (TILE_W / 2) * zoom
    hh_new = (TILE_W * ISO_RATIO / 2) * zoom
    
    # Compute new camera position to keep anchor point at same screen position
    cx_minus_cy = (anchor_gx - anchor_gy) + canvas_w / (2 * hw_new) - sx_target / hw_new
    cx_plus_cy = (anchor_gx + anchor_gy) - 2 * anchor_gz + canvas_h / (2 * hh_new) - sy_target / hh_new
    
    cam.cx = (cx_minus_cy + cx_plus_cy) / 2
    cam.cy = (cx_plus_cy - cx_minus_cy) / 2
    cam._clamp()
    
    return zoom


def terrain_gz(dug: int) -> int:
    """
    Convert dug depth to isometric ground height (gz).

    Ground surface is TOP at gz=0. Dug cells go DOWN (negative gz).
    dug=0 (undug surface) -> gz=0
    dug=1 (one layer down) -> gz=-1
    dug=2 (two layers down) -> gz=-2
    etc.
    """
    return -dug


@dataclass(frozen=True)
class PrismFaces:
    """Polygons for an isometric prism (terrain column)."""
    top: list[float]              # 8 coords: top diamond
    sw: list[float]               # 8 coords: southwest side wall
    se: list[float]               # 8 coords: southeast side wall


def prism_faces(gx: int, gy: int, gz_top: int, gz_bottom: int, m: TileMetrics) -> PrismFaces:
    """
    Generate prism faces for a terrain column from gz_top down to gz_bottom.

    gz_top: height of the top face (e.g., terrain_gz(dug))
    gz_bottom: height of the bottom face (e.g., terrain_gz(dug) - 1 for a 1-layer-thick slab,
               or a fixed bedrock depth like -8 for fully dug cells)

    Returns top diamond + two visible side walls (SW and SE).
    """
    # Top face at gz_top
    top = tile_polygon(gx, gy, gz_top, m)

    # SW wall: connects left edge of top to left edge of bottom
    # Left edge of top: corners 3 (left) and 0 (top) -> indices 6,7 and 0,1
    # Left edge of bottom: corners at gz_bottom
    x0_t, y0_t = world_to_screen(gx, gy, gz_top + 1, m)
    x3_t, y3_t = world_to_screen(gx, gy + 1, gz_top + 1, m)
    x0_b, y0_b = world_to_screen(gx, gy, gz_bottom + 1, m)
    x3_b, y3_b = world_to_screen(gx, gy + 1, gz_bottom + 1, m)
    # SW wall goes: top-left -> top-top -> bottom-top -> bottom-left (clockwise)
    sw = [x3_t, y3_t, x0_t, y0_t, x0_b, y0_b, x3_b, y3_b]

    # SE wall: connects top edge of top to top edge of bottom
    # Top edge of top: corners 0 (top) and 1 (right) -> indices 0,1 and 2,3
    # Top edge of bottom: corners at gz_bottom
    x1_t, y1_t = world_to_screen(gx + 1, gy, gz_top + 1, m)
    x1_b, y1_b = world_to_screen(gx + 1, gy, gz_bottom + 1, m)
    # SE wall goes: top-top -> top-right -> bottom-right -> bottom-top (clockwise)
    se = [x0_t, y0_t, x1_t, y1_t, x1_b, y1_b, x0_b, y0_b]

    return PrismFaces(top=top, sw=sw, se=se)