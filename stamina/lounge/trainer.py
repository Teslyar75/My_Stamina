"""Тренажёр терраформера A1 — учебная смена в комнате отдыха."""
from __future__ import annotations

from stamina.i18n import t as _t

import math
import tkinter as tk

from stamina import theme, wheel_router
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, TEXT, blend, px

from ..terraformer_trainer import (
    HOLD_CAP,
    Camera,
    TrainerModel,
    archive_blueprint,
    load_blueprint,
    save_blueprint,
)

from .base import GameShell

SOIL = "#7A4A2B"
CLAY = "#B8860B"
METAL = "#8FA6BF"
DUG_OUT = "#0A1420"


class TrainerGame(GameShell):
    game_id = "trainer"
    title = _t("ТРЕНАЖЁР ТЕРРАФОРМЕРА · УЧЕБНАЯ СМЕНА")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.model = load_blueprint() or TrainerModel()
        self.camera = Camera(self.model.w, self.model.h)
        self.camera.reset(*self.model.robot)
        self.msg = ""
        # в верхней строке — короткая подсказка (влезает на 1280), полная — внизу поля
        self.set_hint(_t("WASD · Пробел · E · Q · Ctrl+колесо · 0"))
        self.set_score(len(self.model.blocks))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(seq, self._wheel_event)

    def tick_ms(self) -> int:
        return 250

    def tick(self) -> None:
        pass

    def reset(self) -> None:
        # ЗАНОВО: прежняя площадка не теряется — сохраняем и кладём копию в архив
        model = getattr(self, "model", None)
        if model is not None:
            try:
                save_blueprint(model)
                archive_blueprint()
            except Exception:  # noqa: BLE001
                pass
        self.model = TrainerModel()
        self.camera = Camera(self.model.w, self.model.h)
        self.camera.reset(*self.model.robot)
        self.msg = ""
        self.set_score(0)
        self.redraw()

    def stop(self) -> None:
        super().stop()
        try:
            save_blueprint(self.model)
        except Exception:  # noqa: BLE001
            pass

    # -- клавиатура ----------------------------------------------------------
    def on_key(self, e: tk.Event) -> None:
        key = (getattr(e, "keysym", "") or "").lower()
        if key in ("escape", "p"):
            self.toggle_pause()
            return
        if self.paused:
            return

        moves = {
            "left": (-1, 0), "a": (-1, 0),
            "up": (0, -1), "w": (0, -1),
            "right": (1, 0), "d": (1, 0),
            "down": (0, 1), "s": (0, 1),
        }
        zoom_in = ("plus", "equal", "kp_add")
        zoom_out = ("minus", "kp_subtract")
        reset_keys = ("0", "kp_0")
        known = set(moves) | set(zoom_in) | set(zoom_out) | set(reset_keys) | {
            "space", "e", "q",
        }

        if key in moves:
            self.do_move(*moves[key])
            return
        if key == "space":
            self.do_dig()
            return
        if key == "e":
            self.do_unload()
            return
        if key == "q":
            self.do_switch()
            return
        if key in zoom_in:
            self.camera.zoom_in()
            self.redraw()
            return
        if key in zoom_out:
            self.camera.zoom_out()
            self.redraw()
            return
        if key in reset_keys:
            self.camera.reset(*self.model.robot)
            self.redraw()
            return
        if key in known:
            return

        # Русская раскладка: keysym — кириллица, дорогая клавиша узнаётся по keycode.
        code = getattr(e, "keycode", 0) or 0
        codes = {
            65: (-1, 0), 87: (0, -1), 68: (1, 0), 83: (0, 1),
        }
        if code in codes:
            self.do_move(*codes[code])
        elif code == 32:
            self.do_dig()
        elif code == 69:
            self.do_unload()
        elif code == 81:
            self.do_switch()
        elif code in (187, 107):
            self.camera.zoom_in()
            self.redraw()
        elif code in (189, 109):
            self.camera.zoom_out()
            self.redraw()
        elif code in (48, 96):
            self.camera.reset(*self.model.robot)
            self.redraw()

    # -- действия ------------------------------------------------------------
    def do_move(self, dx: int, dy: int) -> bool:
        moved = self.model.move(dx, dy)
        self.camera.track(*self.model.robot)
        self.msg = ""
        self.redraw()
        return moved

    def do_dig(self) -> str:
        result = self.model.dig()
        if result == "site":
            self.msg = _t("Здесь стройплощадка")
        elif result == "too_deep":
            self.msg = _t("Слой недоступен для A1")
        elif result == "hold_full":
            self.msg = _t("Отсек грунта полон — нажми E")
        else:
            self.msg = ""
        self.camera.track(*self.model.robot)
        self.redraw()
        return result

    def do_unload(self) -> str:
        result = self.model.unload()
        if result == "not_full":
            self.msg = _t("Отсек не полон: {0}/{1}").format(
                self.model.holds.get("soil", 0), HOLD_CAP)
        elif result in ("ok", "complete"):
            self.msg = (_t("Фундамент готов — стены открыты!") if result == "complete"
                        else _t("Блок уложен {0}/{1}").format(*self.model.progress()))
        else:  # done
            self.msg = _t("Фундамент готов — стены открыты!")
        self.camera.track(*self.model.robot)
        self.set_score(len(self.model.blocks))
        save_blueprint(self.model)
        self.redraw()
        return result

    def do_switch(self) -> str:
        name = self.model.switch_hold()
        self.msg = _t("Активный отсек: {0}").format(name)
        self.camera.track(*self.model.robot)
        self.redraw()
        return name

    # -- колесо --------------------------------------------------------------
    def on_wheel(self, direction: int, ctrl: bool, shift: bool) -> None:
        if ctrl:
            if direction < 0:
                self.camera.zoom_in()
            elif direction > 0:
                self.camera.zoom_out()
        elif shift:
            self.camera.pan(2 * direction, 0)
        else:
            self.camera.pan(0, 2 * direction)
        self.redraw()

    def _wheel_event(self, e: tk.Event) -> str:
        state = getattr(e, "state", 0) or 0
        self.on_wheel(wheel_router.direction(e), bool(state & 0x4), bool(state & 0x1))
        return "break"

    # -- отрисовка -----------------------------------------------------------
    def _layer_color(self, depth: int) -> str:
        if depth <= 0:
            return SOIL
        if depth == 1:
            return CLAY
        if depth == 2:
            return METAL
        return DUG_OUT

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)
        c.create_rectangle(0, 0, w, h, fill=BG2, outline="")

        model = self.model
        cam = self.camera
        cell = max(cam.cell_px(), 4.0)
        half_w = w / (2.0 * cell)
        half_h = h / (2.0 * cell)
        x0 = max(0, int(math.floor(cam.cx - half_w)) - 1)
        x1 = min(model.w - 1, int(math.ceil(cam.cx + half_w)) + 1)
        y0 = max(0, int(math.floor(cam.cy - half_h)) - 1)
        y1 = min(model.h - 1, int(math.ceil(cam.cy + half_h)) + 1)

        for y in range(y0, y1 + 1):
            row = model.dug[y]
            for x in range(x0, x1 + 1):
                sx, sy = cam.to_screen(x, y, w, h)
                color = self._layer_color(row[x])
                c.create_rectangle(sx, sy, sx + cell, sy + cell,
                                   fill=color, outline=blend(color, BG2, 0.45))

        # контур стройплощадки
        for x, y in model.site_cells():
            px_, py_ = cam.to_screen(x, y, w, h)
            c.create_rectangle(px_ + 2, py_ + 2, px_ + cell - 2, py_ + cell - 2,
                               outline=AMBER, dash=(3, 3), width=1)

        # уложенные блоки
        block_fill = blend(AMBER, TEXT, 0.25)
        for x, y in model.blocks:
            px_, py_ = cam.to_screen(x, y, w, h)
            c.create_rectangle(px_ + 2, py_ + 2, px_ + cell - 2, py_ + cell - 2,
                               fill=block_fill, outline=AMBER, width=2)

        # граница поля
        bx0, by0 = cam.to_screen(0, 0, w, h)
        bx1, by1 = cam.to_screen(model.w, model.h, w, h)
        c.create_rectangle(bx0, by0, bx1, by1, outline=LINE, width=2)

        self._draw_robot(w, h, cell)

        # верхняя панель — всегда в экранных координатах, на тёмной подложке
        hud_h = px(8) + px(16) * (5 if model.walls_open else 4) + px(4)
        c.create_rectangle(0, 0, px(230), hud_h, fill=BG, outline=LINE)
        ty = px(8)
        lines = (
            (_t("Учебная смена / тренажёр"), TEXT, True),
            (_t("Грунт {0}/{1}").format(model.holds.get("soil", 0), HOLD_CAP), MUTED, False),
            (_t("Фундамент {0}/{1}").format(*model.progress()), MUTED, False),
            (_t("Масштаб {0}%").format(int(round(cam.zoom * 100))), MUTED, False),
        )
        for text, color, bold in lines:
            c.create_text(px(10), ty, text=text, fill=color, anchor="nw",
                          font=theme.font(10, bold))
            ty += px(16)
        if model.walls_open:
            c.create_text(px(10), ty, text=_t("СТЕНЫ ОТКРЫТЫ"), fill=GREEN, anchor="nw",
                          font=theme.font(11, True))

        full = _t("Стрелки/WASD — ехать · Пробел — копать · E — блок · Q — отсек · "
                  "Ctrl+колесо, +/− — масштаб · 0 — к роботу")
        tid = c.create_text(w - px(10), h - px(10), text=full, fill=MUTED, anchor="se",
                            font=theme.font(9), width=max(px(200), w // 2 - px(20)), justify="right")
        bb = c.bbox(tid)
        if bb:
            back = c.create_rectangle(bb[0] - px(6), bb[1] - px(4), bb[2] + px(6), bb[3] + px(4),
                                      fill=BG, outline=LINE)
            c.tag_lower(back, tid)
        if self.msg:
            c.create_text(px(10), h - px(10), text=self.msg, fill=AMBER, anchor="sw",
                          font=theme.font(10, True))

        if self.paused:
            self.draw_overlay(_t("ПАУЗА"))

    def _draw_robot(self, w: int, h: int, cell: float) -> None:
        c = self.canvas
        rx, ry = self.model.robot
        sx, sy = self.camera.to_screen(rx, ry, w, h)
        cx = sx + cell / 2.0
        cy = sy + cell / 2.0
        body = cell * 0.52
        track_w = max(2.0, cell * 0.16)

        c.create_rectangle(sx + cell * 0.10, sy + cell * 0.20,
                           sx + cell * 0.10 + track_w, sy + cell * 0.80,
                           fill=MUTED, outline="")
        c.create_rectangle(sx + cell * 0.90 - track_w, sy + cell * 0.20,
                           sx + cell * 0.90, sy + cell * 0.80,
                           fill=MUTED, outline="")
        c.create_rectangle(cx - body / 2, cy - body / 2, cx + body / 2, cy + body / 2,
                           fill=CYAN, outline=blend(CYAN, TEXT, 0.35))

        fx, fy = self.model.facing
        c.create_line(cx, cy,
                      cx + fx * cell * 0.45, cy + fy * cell * 0.45,
                      fill=AMBER, width=max(2, int(cell * 0.12)), arrow="last")
        c.create_text(cx, cy, text="A1", fill=BG, font=theme.font(8, True, mono=True))
