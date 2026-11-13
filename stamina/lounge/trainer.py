"""Тренажёр терраформера A1 — учебная смена в комнате отдыха.

F1 — инструкция (модальный оверлей поверх поля), Q — отсек «Находки».
Пока открыт оверлей, остальные клавиши и колесо не действуют.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import math
import tkinter as tk

from stamina import theme, wheel_router
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, TEXT, blend, px

from ..terraformer_trainer import (
    HOLD_CAP,
    RESOURCES,
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
SPRING = "#2E9BFF"
TOAST_MS = 2600

# keysym → действие; keycode (Windows) — запасной путь для русской раскладки
KEYSYM_ACTIONS = {
    "left": ("move", -1, 0), "a": ("move", -1, 0),
    "up": ("move", 0, -1), "w": ("move", 0, -1),
    "right": ("move", 1, 0), "d": ("move", 1, 0),
    "down": ("move", 0, 1), "s": ("move", 0, 1),
    "space": ("dig",), "e": ("unload",), "q": ("finds",),
    "plus": ("zoom_in",), "equal": ("zoom_in",), "kp_add": ("zoom_in",),
    "minus": ("zoom_out",), "kp_subtract": ("zoom_out",),
    "0": ("home",), "kp_0": ("home",),
    "escape": ("esc",), "p": ("pause",), "f1": ("help",),
}
KEYCODE_ACTIONS = {
    65: ("move", -1, 0), 87: ("move", 0, -1), 68: ("move", 1, 0), 83: ("move", 0, 1),
    32: ("dig",), 69: ("unload",), 81: ("finds",), 80: ("pause",),
    187: ("zoom_in",), 107: ("zoom_in",), 189: ("zoom_out",), 109: ("zoom_out",),
    48: ("home",), 96: ("home",), 112: ("help",),
}


def key_hint() -> str:
    """Постоянная подсказка внизу экрана (одна строка, влезает в 1280 на всех языках)."""
    return _t("F1 инструкция · WASD/стрелки · Пробел копать · E блок · Q находки · "
              "Ctrl+колесо масштаб · 0 к роботу")


def resource_name(res: str) -> str:
    return {
        "water": _t("Источник воды"),
        "stone": _t("Камень"),
        "organic": _t("Органика"),
        "iron": _t("Железная руда"),
        "quartz": _t("Кварцевый песок"),
    }.get(res, res)


def resource_use(res: str) -> tuple[str, str]:
    """(зачем нужен, на каком этапе пригодится)."""
    return {
        "water": (_t("Для будущих поселенцев и раствора для стен."),
                  _t("стены и инфраструктура")),
        "stone": (_t("Укрепление фундамента и стен."), _t("стены")),
        "organic": (_t("Почва для будущих теплиц."), _t("инфраструктура")),
        "iron": (_t("Каркас и инструменты; переплавим позже."), _t("укрытие")),
        "quartz": (_t("Стекло и солнечные панели."), _t("укрытие и инфраструктура")),
    }.get(res, ("", ""))


def help_sections() -> list[tuple[str, str]]:
    """Разделы инструкции F1. Каждый факт сверен с кодом тренажёра."""
    return [
        (_t("Что это"),
         _t("Учебная смена перед настоящим терраформированием. Поле 40×24 клетки, в каждой "
            "три слоя: грунт, глина, металл. Робот A1 снимает только верхний слой — грунт. "
            "Ошибки на тренажёре ничего не портят.")),
        (_t("Управление роботом"),
         _t("Стрелки или WASD — ехать (работает и в русской раскладке). "
            "Esc или P — пауза. Камера едет за роботом.")),
        (_t("Копание и урожай"),
         _t("Пробел — копать клетку под роботом. Отсек грунта вмещает 10. Когда он полон, "
            "грунт больше не берётся, но робот ездит дальше. Стройплощадку копать нельзя. "
            "Отсеки для глины и металла появятся на следующих этапах вместе с роботами A2+.")),
        (_t("Ресурсы и находки"),
         _t("В части клеток спрятаны находки: источник воды, камень, органика, железная руда, "
            "кварцевый песок. Находка открывается, когда снимаешь её слой, и идёт в отсек "
            "«Находки» — даже если отсек грунта полон. Источник воды отмечается на поле, "
            "эту клетку дальше не копают. Находки глубже грунта A1 не видит — их откроют "
            "роботы A2+. Q — открыть отсек «Находки».")),
        (_t("Фундамент из блоков"),
         _t("E — превратить полный отсек грунта (10) в блок. Блоки ложатся на стройплощадку "
            "4×3, всего 12. Когда уложены все 12 — «СТЕНЫ ОТКРЫТЫ».")),
        (_t("Сохранение и «ЗАНОВО»"),
         _t("Площадка сохраняется сама в папке пилота (terraformer_trainer.json): после "
            "каждого блока, находки и при выходе в лобби. «ЗАНОВО» сначала кладёт текущую площадку "
            "в архив terraformer_trainer_archive/ (хранятся 20 последних) и начинает новую.")),
        (_t("Масштаб и камера"),
         _t("Ctrl+колесо или +/− — масштаб, 0 — камера обратно к роботу. Колесо — "
            "вверх-вниз, Shift+колесо — вбок. После прокрутки камера стоит, пока не нажмёшь 0.")),
    ]


class TrainerGame(GameShell):
    game_id = "trainer"
    title = _t("ТРЕНАЖЁР ТЕРРАФОРМЕРА · УЧЕБНАЯ СМЕНА")

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.model = load_blueprint() or TrainerModel()
        self.camera = Camera(self.model.w, self.model.h)
        self.camera.reset(*self.model.robot)
        self.msg = ""
        self.overlay: str | None = None      # None | "help" | "finds"
        self.toast: tuple[str, bool] | None = None
        self._toast_job = None
        self.help_fits = True
        self.hint_font_size = 10
        self.set_hint("")                     # подсказка — одной строкой внизу поля
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
        self.overlay = None
        self._clear_toast()
        self.set_score(0)
        self.redraw()

    def stop(self) -> None:
        super().stop()
        self._clear_toast()
        try:
            save_blueprint(self.model)
        except Exception:  # noqa: BLE001
            pass

    # -- оверлеи ---------------------------------------------------------------
    def on_help(self) -> bool:
        """F1: открыть/закрыть инструкцию. True — F1 обработан тренажёром."""
        self.overlay = None if self.overlay == "help" else "help"
        self.redraw()
        return True

    def toggle_finds(self) -> str | None:
        self.overlay = None if self.overlay == "finds" else "finds"
        self.redraw()
        return self.overlay

    def close_overlay(self) -> None:
        self.overlay = None
        self.redraw()

    # -- клавиатура ----------------------------------------------------------
    @staticmethod
    def _action(e) -> tuple | None:
        key = (getattr(e, "keysym", "") or "").lower()
        act = KEYSYM_ACTIONS.get(key)
        if act is None:
            act = KEYCODE_ACTIONS.get(getattr(e, "keycode", 0) or 0)
        return act

    def on_key(self, e: tk.Event) -> None:
        act = self._action(e)
        name = act[0] if act else None
        # открыт оверлей — работают только его клавиши закрытия
        if self.overlay == "help":
            if name in ("esc", "help"):
                self.close_overlay()
            return
        if self.overlay == "finds":
            if name in ("esc", "finds"):
                self.close_overlay()
            return
        if name == "help":
            self.on_help()
            return
        if name in ("esc", "pause"):
            self.toggle_pause()
            return
        if self.paused or act is None:
            return
        if name == "move":
            self.do_move(act[1], act[2])
        elif name == "dig":
            self.do_dig()
        elif name == "unload":
            self.do_unload()
        elif name == "finds":
            self.toggle_finds()
        elif name == "zoom_in":
            self.camera.zoom_in()
            self.redraw()
        elif name == "zoom_out":
            self.camera.zoom_out()
            self.redraw()
        elif name == "home":
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
        elif result == "spring":
            self.msg = _t("Здесь источник воды — копать нельзя")
        else:
            self.msg = ""
        found = self.model.last_find
        if found:
            self.show_toast(self.find_text(found["res"]), bool(found["first"]))
            try:
                save_blueprint(self.model)
            except Exception:  # noqa: BLE001
                pass
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

    # -- уведомления -----------------------------------------------------------
    @staticmethod
    def find_text(res: str) -> str:
        if res == "water":
            return _t("Отлично, нашёл источник воды!")
        return _t("Нашёл ресурс: {0}").format(resource_name(res))

    def show_toast(self, text: str, bright: bool = False) -> None:
        self._clear_toast()
        self.toast = (text, bright)
        try:
            self._toast_job = self.after(TOAST_MS, self._toast_done)
        except tk.TclError:
            self._toast_job = None

    def _toast_done(self) -> None:
        self._toast_job = None
        self.toast = None
        try:
            self.redraw()
        except tk.TclError:
            pass

    def _clear_toast(self) -> None:
        if self._toast_job is not None:
            try:
                self.after_cancel(self._toast_job)
            except tk.TclError:
                pass
            self._toast_job = None
        self.toast = None

    # -- колесо --------------------------------------------------------------
    def on_wheel(self, direction: int, ctrl: bool, shift: bool) -> None:
        if self.overlay is not None:
            return                       # инструкция/находки не прокручиваются
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

        # открытые находки: источник воды — синий круг, прочее — маленький ромб
        for (x, y) in model.revealed:
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            res = model.finds[(x, y)][0]
            sx, sy = cam.to_screen(x, y, w, h)
            if res == "water":
                c.create_oval(sx + cell * 0.18, sy + cell * 0.18, sx + cell * 0.82, sy + cell * 0.82,
                              fill=SPRING, outline=TEXT, width=1)
            else:
                mx, my, r = sx + cell / 2, sy + cell / 2, cell * 0.16
                c.create_polygon(mx, my - r, mx + r, my, mx, my + r, mx - r, my,
                                 fill=GREEN, outline="")

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
        found = sum(model.finds_count.values())
        rows = 5 + (1 if model.walls_open else 0)
        hud_h = px(8) + px(16) * rows + px(4)
        c.create_rectangle(0, 0, px(230), hud_h, fill=BG, outline=LINE)
        ty = px(8)
        lines = (
            (_t("Учебная смена / тренажёр"), TEXT, True),
            (_t("Грунт {0}/{1}").format(model.holds.get("soil", 0), HOLD_CAP), MUTED, False),
            (_t("Фундамент {0}/{1}").format(*model.progress()), MUTED, False),
            (_t("Находки {0}").format(found), MUTED, False),
            (_t("Масштаб {0}%").format(int(round(cam.zoom * 100))), MUTED, False),
        )
        for text, color, bold in lines:
            c.create_text(px(10), ty, text=text, fill=color, anchor="nw",
                          font=theme.font(10, bold))
            ty += px(16)
        if model.walls_open:
            c.create_text(px(10), ty, text=_t("СТЕНЫ ОТКРЫТЫ"), fill=GREEN, anchor="nw",
                          font=theme.font(11, True))

        bar_top = self._draw_key_hint(w, h)
        if self.msg:
            c.create_text(px(10), bar_top - px(6), text=self.msg, fill=AMBER, anchor="sw",
                          font=theme.font(10, True))
        if self.toast:
            self._draw_toast(w)

        if self.overlay == "help":
            self._draw_help(w, h)
        elif self.overlay == "finds":
            self._draw_finds(w, h)
        elif self.paused:
            self.draw_overlay(_t("ПАУЗА"))

    def _draw_key_hint(self, w: int, h: int) -> int:
        """Одна строка подсказки внизу; шрифт уменьшается, если окно узкое. Возвращает верх полосы."""
        c = self.canvas
        text = key_hint()
        for size in (10, 9, 8):
            tid = c.create_text(px(10), h - px(6), text=text, fill=TEXT, anchor="sw",
                                font=theme.font(size), tags="keyhint")
            bb = c.bbox(tid)
            if not bb or bb[2] <= w - px(10) or size == 8:
                break
            c.delete(tid)
        self.hint_font_size = size
        bb = c.bbox(tid) or (0, h - px(24), w, h)
        top = bb[1] - px(4)
        back = c.create_rectangle(0, top, w, h, fill=BG, outline=LINE, tags="keyhint")
        c.tag_lower(back, tid)
        return top

    def _draw_toast(self, w: int) -> None:
        c = self.canvas
        text, bright = self.toast
        color = GREEN if bright else AMBER
        tid = c.create_text(w // 2, px(14), text=text, fill=color, anchor="n",
                            font=theme.font(14 if bright else 12, True), tags="toast")
        bb = c.bbox(tid)
        if bb:
            back = c.create_rectangle(bb[0] - px(14), bb[1] - px(6), bb[2] + px(14), bb[3] + px(6),
                                      fill=BG, outline=color, width=2 if bright else 1, tags="toast")
            c.tag_lower(back, tid)

    def _draw_help(self, w: int, h: int) -> None:
        """Инструкция поверх поля: две колонки; шрифт уменьшается, пока всё не влезет."""
        c = self.canvas
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")
        pad = px(18)
        secs = help_sections()
        half = (len(secs) + 1) // 2
        colw = max(px(160), (w - pad * 3) // 2)
        for size in (11, 10, 9, 8):
            title = c.create_text(w // 2, pad, text=_t("ИНСТРУКЦИЯ · ТРЕНАЖЁР ТЕРРАФОРМЕРА"),
                                  fill=AMBER, anchor="n", font=theme.font(size + 3, True), tags="help")
            top = (c.bbox(title) or (0, 0, 0, pad))[3] + px(10)
            ys = [top, top]
            for i, (head, body) in enumerate(secs):
                col = 0 if i < half else 1
                x = pad + col * (colw + pad)
                hid = c.create_text(x, ys[col], text=head, fill=CYAN, anchor="nw", width=colw,
                                    font=theme.font(size + 1, True), tags="help")
                ys[col] = c.bbox(hid)[3] + px(3)
                bid = c.create_text(x, ys[col], text=body, fill=TEXT, anchor="nw", width=colw,
                                    font=theme.font(size), tags="help")
                ys[col] = c.bbox(bid)[3] + px(10)
            foot = c.create_text(w // 2, h - px(8), text=_t("F1 или Esc — закрыть"), fill=MUTED,
                                 anchor="s", font=theme.font(size, True), tags="help")
            fits = max(ys) <= c.bbox(foot)[1] - px(2)
            if fits or size == 8:
                self.help_fits = fits
                break
            c.delete("help")

    def _draw_finds(self, w: int, h: int) -> None:
        """Отсек «Находки»: найденные типы, количество, зачем нужны; ненайденные — «???»."""
        c = self.canvas
        pw = min(w - px(40), px(760))
        x0 = (w - pw) // 2
        model = self.model
        for size in (11, 10, 9, 8):
            items = []
            y = px(18)
            items.append(c.create_text(w // 2, y, text=_t("ОТСЕК «НАХОДКИ»"), fill=AMBER, anchor="n",
                                       font=theme.font(size + 3, True), tags="finds"))
            y = c.bbox(items[-1])[3] + px(10)
            for res in RESOURCES:
                n = model.finds_count.get(res, 0)
                if n > 0:
                    use, stage = resource_use(res)
                    head = f"{resource_name(res)} × {n}"
                    body = use + "\n" + _t("Пригодится на этапе: {0}").format(stage)
                    hc, bc = GREEN, TEXT
                else:
                    head, body, hc, bc = "???", _t("Ещё не найдено"), MUTED, MUTED
                items.append(c.create_text(x0 + px(16), y, text=head, fill=hc, anchor="nw",
                                           font=theme.font(size + 1, True), tags="finds"))
                y = c.bbox(items[-1])[3] + px(2)
                items.append(c.create_text(x0 + px(16), y, text=body, fill=bc, anchor="nw",
                                           width=pw - px(32), font=theme.font(size), tags="finds"))
                y = c.bbox(items[-1])[3] + px(8)
            items.append(c.create_text(w // 2, y + px(4), text=_t("Q или Esc — закрыть"), fill=MUTED,
                                       anchor="n", font=theme.font(size, True), tags="finds"))
            bottom = c.bbox(items[-1])[3] + px(12)
            if bottom <= h - px(6) or size == 8:
                back = c.create_rectangle(x0, px(6), x0 + pw, min(h - px(2), bottom),
                                          fill=BG, outline=AMBER, width=2, tags="finds")
                c.tag_lower(back, items[0])
                break
            c.delete("finds")

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
