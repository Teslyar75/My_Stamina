"""Тренажёр терраформера A1 — чистая логика без Tk.

Модель поля, камера и сохранение чертежа. Отрисовка живёт в lounge/trainer.py.
"""
from __future__ import annotations

import json
from pathlib import Path

GRID_W = 40
GRID_H = 24
LAYERS = ("soil", "clay", "metal")
HOLD_CAP = 10
SITE = (2, 2, 4, 3)          # x, y, width, height — 12 блоков фундамента
BLUEPRINT_NAME = "terraformer_trainer.json"
ZOOM_MIN = 0.5
ZOOM_MAX = 3.0
ZOOM_STEP = 1.25
BASE_CELL = 28


class TrainerModel:
    """Поле, робот, отсеки и фундамент учебной смены."""

    def __init__(self, w: int = GRID_W, h: int = GRID_H, depth: int = 1) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.depth = max(1, min(int(depth), len(LAYERS)))
        self.dug = [[0] * self.w for _ in range(self.h)]
        self.robot = [self.w // 2, self.h // 2]
        self.facing = (1, 0)
        self.holds = {name: 0 for name in LAYERS}
        self.active_hold = "soil"
        self.blocks: list[tuple[int, int]] = []
        self.walls_open = False

    # -- стройплощадка -------------------------------------------------------
    def site_cells(self) -> list[tuple[int, int]]:
        x, y, w, h = SITE
        return [(cx, cy) for cy in range(y, y + h) for cx in range(x, x + w)]

    def on_site(self, x: int, y: int) -> bool:
        sx, sy, sw, sh = SITE
        return sx <= x < sx + sw and sy <= y < sy + sh

    # -- действия робота -----------------------------------------------------
    def move(self, dx: int, dy: int) -> bool:
        self.facing = (dx, dy)
        x = max(0, min(self.w - 1, self.robot[0] + dx))
        y = max(0, min(self.h - 1, self.robot[1] + dy))
        moved = (x, y) != (self.robot[0], self.robot[1])
        self.robot = [x, y]
        return moved

    def dig(self) -> str:
        x, y = self.robot
        if self.on_site(x, y):
            return "site"
        layers = self.dug[y][x]
        if layers >= self.depth or layers >= len(LAYERS):
            return "too_deep"
        hold = LAYERS[layers]
        if self.holds[hold] >= HOLD_CAP:
            return "hold_full"
        self.dug[y][x] = layers + 1
        self.holds[hold] += 1
        return "ok"

    def hold_full(self, name: str = "soil") -> bool:
        return self.holds.get(name, 0) >= HOLD_CAP

    def switch_hold(self) -> str:
        try:
            idx = LAYERS.index(self.active_hold)
        except ValueError:
            idx = 0
        self.active_hold = LAYERS[(idx + 1) % len(LAYERS)]
        return self.active_hold

    def unload(self) -> str:
        if self.holds.get("soil", 0) < HOLD_CAP:
            return "not_full"
        site = self.site_cells()
        if len(self.blocks) >= len(site):
            return "done"
        free = next((cell for cell in site if cell not in self.blocks), None)
        if free is None:
            return "done"
        self.blocks.append(free)
        self.holds["soil"] = 0
        if len(self.blocks) >= len(site):
            self.walls_open = True
            return "complete"
        return "ok"

    def progress(self) -> tuple[int, int]:
        return len(self.blocks), len(self.site_cells())

    def layer_left(self, x: int, y: int) -> int:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return 0
        total = min(self.depth, len(LAYERS))
        return max(0, total - self.dug[y][x])

    # -- чертёж --------------------------------------------------------------
    def to_blueprint(self) -> dict:
        return {
            "kind": "terraformer_trainer",
            "version": 1,
            "w": self.w,
            "h": self.h,
            "depth": self.depth,
            "dug": [row[:] for row in self.dug],
            "robot": list(self.robot),
            "holds": dict(self.holds),
            "blocks": [[x, y] for x, y in self.blocks],
            "walls_open": bool(self.walls_open),
        }

    @classmethod
    def from_blueprint(cls, d: dict) -> "TrainerModel":
        if not isinstance(d, dict) or d.get("kind") != "terraformer_trainer":
            return cls()
        try:
            w = int(d.get("w", GRID_W))
            h = int(d.get("h", GRID_H))
        except (TypeError, ValueError):
            return cls()
        if not (1 <= w <= 1000 and 1 <= h <= 1000):
            return cls()
        try:
            depth = int(d.get("depth", 1))
        except (TypeError, ValueError):
            depth = 1
        model = cls(w, h, depth)

        dug = d.get("dug")
        if not isinstance(dug, list) or len(dug) != h:
            return cls()
        cap = min(model.depth, len(LAYERS))
        for y, row in enumerate(dug):
            if not isinstance(row, list) or len(row) != w:
                return cls()
            for x, value in enumerate(row):
                try:
                    v = int(value)
                except (TypeError, ValueError):
                    v = 0
                model.dug[y][x] = max(0, min(cap, v))

        robot = d.get("robot")
        if isinstance(robot, (list, tuple)) and len(robot) >= 2:
            try:
                rx, ry = int(robot[0]), int(robot[1])
            except (TypeError, ValueError):
                rx, ry = model.w // 2, model.h // 2
            model.robot = [max(0, min(model.w - 1, rx)), max(0, min(model.h - 1, ry))]

        holds = d.get("holds")
        if isinstance(holds, dict):
            for name in LAYERS:
                try:
                    value = int(holds.get(name, 0))
                except (TypeError, ValueError):
                    value = 0
                model.holds[name] = max(0, min(HOLD_CAP, value))

        blocks = d.get("blocks")
        if isinstance(blocks, list):
            seen: set[tuple[int, int]] = set()
            for item in blocks:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                try:
                    bx, by = int(item[0]), int(item[1])
                except (TypeError, ValueError):
                    continue
                cell = (bx, by)
                if model.on_site(bx, by) and cell not in seen:
                    seen.add(cell)
                    model.blocks.append(cell)

        model.walls_open = bool(d.get("walls_open")) or len(model.blocks) >= len(model.site_cells())
        return model


class Camera:
    """Простая камера: центр в координатах клеток, масштаб в пикселях."""

    def __init__(self, w: int, h: int) -> None:
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.zoom = 1.0
        self.cx = self.w / 2.0
        self.cy = self.h / 2.0
        self.follow = True
        self._clamp()

    def _clamp(self) -> None:
        self.cx = max(0.0, min(float(self.w), self.cx))
        self.cy = max(0.0, min(float(self.h), self.cy))

    def cell_px(self) -> float:
        return BASE_CELL * self.zoom

    def zoom_in(self) -> float:
        self.zoom = min(ZOOM_MAX, self.zoom * ZOOM_STEP)
        return self.zoom

    def zoom_out(self) -> float:
        self.zoom = max(ZOOM_MIN, self.zoom / ZOOM_STEP)
        return self.zoom

    def pan(self, dx_cells: float, dy_cells: float) -> None:
        self.follow = False
        self.cx += dx_cells
        self.cy += dy_cells
        self._clamp()

    def reset(self, x: float, y: float) -> None:
        self.zoom = 1.0
        self.cx = x + 0.5
        self.cy = y + 0.5
        self.follow = True
        self._clamp()

    def track(self, x: float, y: float) -> None:
        if not self.follow:
            return
        self.cx = x + 0.5
        self.cy = y + 0.5
        self._clamp()

    def to_screen(self, x: float, y: float, width: int, height: int) -> tuple[float, float]:
        cell = self.cell_px()
        return (
            width / 2.0 + (x - self.cx) * cell,
            height / 2.0 + (y - self.cy) * cell,
        )


def blueprint_path() -> Path:
    from stamina import pilots

    return Path(pilots.active_dir()) / BLUEPRINT_NAME


def save_blueprint(model: TrainerModel, path: Path | None = None) -> bool:
    target = Path(path) if path is not None else blueprint_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(model.to_blueprint(), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(target)
        return True
    except OSError:
        return False


def load_blueprint(path: Path | None = None) -> TrainerModel | None:
    target = Path(path) if path is not None else blueprint_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "terraformer_trainer":
        return None
    return TrainerModel.from_blueprint(data)
