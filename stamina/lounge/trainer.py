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
    PLATFORM_YIELD,
    PLATFORM_VARIANTS,
    VARIANT_DESC,
    VARIANT_YIELD_MULT,
    PROGRESSION_TIERS,
    get_language_level,
    get_unlocked_variants,
    get_next_tier_preview,
    platform_height,
)
from .. import terraformer_strategy as strategy
from . import iso

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
    "space": ("dig",), "e": ("place_block",), "q": ("finds",),
    "b": ("build_plan",), "tab": ("cycle_priority",), "g": ("gallery",),
    "t": ("missions",), "n": ("structures",), "x": ("select_all",),
    "m": ("mixed_mode",), "plus": ("zoom_in",), "equal": ("zoom_in",), "kp_add": ("zoom_in",),
    "minus": ("zoom_out",), "kp_subtract": ("zoom_out",),
    "0": ("home",), "kp_0": ("home",),
    "escape": ("esc",), "p": ("pause",), "f1": ("help",), "i": ("iso",),
}
KEYCODE_ACTIONS = {
    65: ("move", -1, 0), 87: ("move", 0, -1), 68: ("move", 1, 0), 83: ("move", 0, 1),
    32: ("dig",), 69: ("place_block",), 81: ("finds",), 66: ("build_plan",), 9: ("cycle_priority",), 71: ("gallery",),
    84: ("missions",), 78: ("structures",), 88: ("select_all",),
    80: ("pause",),
    187: ("zoom_in",), 107: ("zoom_in",), 189: ("zoom_out",), 109: ("zoom_out",),
    48: ("home",), 96: ("home",), 112: ("help",), 73: ("iso",),
}


def key_hint() -> str:
    """Постоянная подсказка внизу экрана (одна строка, влезает в 1280 на всех языках)."""
    return _t("F1 справка · WASD ход · Пробел копать · E блок · Q находки · B план · "
              "G галерея · T задания · N стройка · ЛКМ выбор · ПКМ ход · СКМ карта · I изо")


def resource_name(res: str) -> str:
    return {
        "water": _t("Источник воды"),
        "stone": _t("Камень"),
        "organic": _t("Органика"),
        "iron": _t("Железная руда"),
        "quartz": _t("Кварцевый песок"),
        "spice": _t("Специя"),
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
        "spice": (_t("Самый ценный ресурс пустыни — топливо для прыжков."), _t("дальние карты")),
    }.get(res, ("", ""))


def help_sections() -> list[tuple[str, str]]:
    """Разделы инструкции F1. Каждый факт сверен с кодом тренажёра.

    Текст намеренно по-русски без ``_t()``: это учебник смены, как help_texts,
    и он не должен растить долг переводов.
    """
    return [
        ("Что это",
         "Стратегическая смена на планете: восемь уровней — A1, A2, B1.1, B1.2, B2.1, "
         "B2.2, C1, C2 — как у английского. Следующий уровень открывается, когда предыдущий "
         "пройден больше чем на 80 %. Ошибки на тренажёре ничего не портят."),
        ("Управление",
         "Стрелки или WASD — ехать главным терраформером. Esc или P — пауза. "
         "Ctrl+колесо — масштаб вокруг курсора, СКМ — таскать карту, 0 — вернуться к отряду."),
("Отряд и приказы",
          "ЛКМ: рамка выделяет отряд, клик по юниту выделяет, клик по пустой земле снимает выделение. "
          "ПКМ — приказ идти выделенным терраформерам (как в Red Alert). "
          "X — выделить весь отряд. Отряд обходит здания и источники, а карта растёт, "
          "когда терраформер подходит к краю."),
        ("Копание и грунт",
         "Пробел — копать клетку под главным терраформером. Отсек грунта вмещает 5. "
         "Стройплощадку и источник воды копать нельзя. E — уложить блок из полного отсека."),
        ("Находки и платформы",
         "В клетках спрятаны находки: вода, камень, органика, железо, кварц. Q — отсек "
         "«Находки». Платформа — схема блоков вокруг ресурса; когда все клетки заполнены, "
         "она даёт ресурс каждый тик. Чем выше уровень терраформера, тем выше здание платформы."),
        ("Туман войны",
         "Карта большая, но видно только то, что попало в радиус обзора отряда. "
         "Разведанная часть остаётся на карте приглушённой. Радар и высокие здания "
         "расширяют обзор."),
        ("Задания и тревоги",
         "Задания приходят сообщениями-тревогами; выполненные отмечаются зелёной галочкой "
         "и открывают инфраструктуру. T — список заданий. Награда — кредиты."),
        ("Здания и доход",
         "N — стройка: ↑/↓ выбрать здание, Пробел — построить под выбранным терраформером. "
         "Высота здания ограничена уровнем терраформера: A1 — 1, C2 — 8. Завершённые и "
         "связанные здания приносят кредиты каждый тик; связь — до 6 клеток до другого "
         "здания или базы."),
        ("Песчаный червь",
         "Червь идёт под песком: след вспучивает песок, по нему видно, где он прошёл. "
         "На фундаменте и камне техника в безопасности; на открытом песке червь бьёт. "
         "Иногда он оставляет специю — самый ценный ресурс."),
        ("Сохранение и «ЗАНОВО»",
         "Площадка сохраняется сама в папке пилота (terraformer_trainer.json). «ЗАНОВО» "
         "кладёт текущую площадку в архив terraformer_trainer_archive/ и начинает новую."),
    ]


class TrainerGame(GameShell):
    game_id = "trainer"
    title = _t("ТЕРРАФОРМЕР · СТРАТЕГИЯ ПЛАНЕТЫ")

    @staticmethod
    def _draw_text_stacked(c: tk.Canvas, x: int, ty: int, text: str, fill: str, anchor: str, font, width: int | None = None, pad: int = 4) -> int:
        """Рисует текст с anchor='nw' в (x, ty), возвращает новый ty после текста + pad.
        Если bbox недоступен — падает назад на фиксированный шаг.
        """
        kw = {"anchor": "nw", "fill": fill, "font": font}
        if width is not None:
            kw["width"] = width
        tid = c.create_text(x, ty, text=text, **kw)
        bb = c.bbox(tid)
        if bb is not None:
            return bb[3] + pad
        # фолбэк: приблизительная высота строки
        return ty + px(14) + pad

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.model = load_blueprint() or TrainerModel()
        self.camera = Camera(self.model.w, self.model.h)
        self.camera.reset(*self.model.robot)
        self.msg = ""
        self.overlay: str | None = None      # help | finds | build_plan | gallery | missions | structures
        self.toast: tuple[str, bool] | None = None
        self._toast_job = None
        self.help_fits = True
        self.hint_font_size = 10
        # состояние галереи
        self._gallery_resource: str = "water"
        self._gallery_variant: int = 0
        self._gallery_view_3d: bool = False
        # состояние стратегии: рамка выделения и перетаскивание карты
        self._lmb_start: tuple[float, float] | None = None
        self._lmb_box: int | None = None
        self._rmb_start: tuple[float, float] | None = None
        self._rmb_cell: tuple[int, int] | None = None
        self._rmb_box: int | None = None
        self._mmb_last: tuple[float, float] | None = None
        self._struct_index = 0
        self._last_mouse: tuple[int, int] = (0, 0)
        self._iso_view = False                # I: переключение плоский/изометрический вид
        self._iso_zoom = 1.0                  # отдельный зум для изометрии
        self.set_hint("")                     # подсказка — одной строкой внизу поля
        self.set_score(len(self.model.blocks))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(seq, self._wheel_event)
        # стратегическое управление: ЛПМ — рамка/выделение, ПКМ — приказ идти, СКМ — таскать карту
        self.canvas.bind("<Button-1>", self._on_lmb_down)
        self.canvas.bind("<B1-Motion>", self._on_lmb_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_lmb_up)
        # стратегическое управление: ПКМ — приказ идти, СКМ — таскать карту
        self.canvas.bind("<Button-3>", self._on_rmb_down)
        self.canvas.bind("<B3-Motion>", self._on_rmb_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_rmb_up)
        self.canvas.bind("<Button-2>", self._on_mmb_down)
        self.canvas.bind("<B2-Motion>", self._on_mmb_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_mmb_up)
        self.canvas.bind("<Motion>", self._on_motion)

    def tick_ms(self) -> int:
        return 250

    def tick(self) -> None:
        # отряд, экономика, червь, задания
        if self.model.tick_units():
            self.camera.resize(self.model.w, self.model.h)
            self.camera.track(*self.model.robot)
        if self.model.tick_income():
            pass
        event = self.model.tick_worm()
        if event and event.get("spice"):
            self.show_toast(_t("Специя! Червь оставил ценный ресурс"), True)
        if event and event.get("attacked"):
            self.show_toast(_t("Червь атакует технику на песке!"))
        fresh = self.model.evaluate_missions()
        if fresh:
            m = fresh[-1]
            self.show_toast(_t("Задание выполнено: {0}").format(m.title), True)
            self.set_score(self.model.credits + len(self.model.buildings) * 10)
        added = self.model.refresh_standing()
        if added:
            u = added[-1]
            self.show_toast(_t("Новый терраформер: {0}").format(u.name), True)
        # автодобыча с платформ
        gained = self.model.tick_extraction()
        if gained:
            # показываем тост только за первый ресурс, чтобы не спамить
            first_res, amount = next(iter(gained.items()))
            self.show_toast(_t("Добыто: {0} ×{1}").format(resource_name(first_res), amount))
        self.redraw()

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
        self._lmb_start = None
        self._lmb_box = None
        self._rmb_start = None
        self._rmb_cell = None
        self._rmb_box = None
        self._mmb_last = None
        self._struct_index = 0
        self._gallery_resource = "water"
        self._gallery_variant = 0
        self._gallery_view_3d = False
        self._last_mouse = (0, 0)
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
    def help_game_id(self) -> str:
        return "terraformer"

    def help_level_id(self) -> str | None:
        try:
            from stamina.terraformer_trainer import get_language_level
            lvl = int(get_language_level())
        except Exception:
            lvl = 0
        return f"stage_{max(0, min(len(strategy.LEVELS) - 1, lvl))}"

    def on_help(self) -> bool:
        """F1 / «?»: общий оверлей справки текущего этапа языка."""
        if self.overlay == "help":
            self.overlay = None
        return super().on_help()


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
        if self.handle_help_keys(e):
            return
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
        if self.overlay == "build_plan":
            if name in ("esc", "build_plan"):
                self.close_overlay()
            elif name == "cycle_priority":
                self.cycle_priority()
            return
        if self.overlay == "gallery":
            if name in ("esc", "gallery"):
                self.close_overlay()
            elif name == "move":
                # влево/вправо — смена ресурса, вверх/вниз — смена варианта
                if act[1] != 0:  # left/right
                    self._gallery_change_resource(act[1])
                elif act[2] != 0:  # up/down
                    self._gallery_change_variant(act[2])
            elif name in ("space", "return"):  # переключение 2D/3D
                self._gallery_toggle_3d()
            return
        if self.overlay == "missions":
            if name in ("esc", "missions"):
                self.model.mission_book.mark_read()
                self.close_overlay()
            elif name in ("space", "return"):
                self.model.mission_book.mark_read()
                self.redraw()
            return
        if self.overlay == "structures":
            if name in ("esc", "structures"):
                self.close_overlay()
            elif name == "move":
                if act[2] != 0:
                    self._struct_change(act[2])
            elif name in ("space", "return"):
                self._struct_build()
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
        elif name == "place_block":
            self.do_place_block()
        elif name == "finds":
            self.toggle_finds()
        elif name == "build_plan":
            self.toggle_build_plan()
        elif name == "cycle_priority":
            self.cycle_priority()
        elif name == "gallery":
            self.toggle_gallery()
        elif name == "missions":
            self.toggle_missions()
        elif name == "structures":
            self.toggle_structures()
        elif name == "select_all":
            self.model.select_all()
            self.show_toast(_t("Выделен весь отряд: {0}").format(len(self.model.units)))
            self.redraw()
        elif name == "zoom_in":
            if self._iso_view:
                self._iso_zoom = min(iso.ZOOM_MAX, self._iso_zoom * iso.ZOOM_STEP)
            else:
                self.camera.zoom_in()
            self.redraw()
        elif name == "zoom_out":
            if self._iso_view:
                self._iso_zoom = max(iso.ZOOM_MIN, self._iso_zoom / iso.ZOOM_STEP)
            else:
                self.camera.zoom_out()
            self.redraw()
        elif name == "home":
            self.camera.reset(*self.model.robot)
            self.redraw()
        elif name == "mixed_mode":
            self._toggle_mixed_mode()
            self.redraw()
        elif name == "iso":
            self._toggle_iso_view()
            self.redraw()

    def _toggle_iso_view(self) -> None:
        """Переключает между плоским (топ-даун) и изометрическим видом."""
        self._iso_view = not self._iso_view
        mode = _t("ИЗОМЕТРИЯ") if self._iso_view else _t("ПЛОСКИЙ ВИД")
        self.show_toast(_t("Вид: {0}").format(mode))

    @property
    def iso_view(self) -> bool:
        """Включён ли изометрический вид."""
        return self._iso_view

    def _toggle_mixed_mode(self) -> None:
        """Переключает смешанный режим: Orion-foreman копает и достраивает приоритетную платформу/базу."""
        self.model._mixed_mode = not getattr(self.model, "_mixed_mode", False)
        status = _t("ВКЛ") if self.model._mixed_mode else _t("ВЫКЛ")
        self.show_toast(_t("Смешанный режим {0}").format(status))

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

    def do_place_block(self) -> tuple[bool, str]:
        """Укладка блока в текущей клетке робота (E)."""
        x, y = self.model.robot
        success, msg = self.model.try_place_block(x, y)
        if success:
            self.msg = msg
            self.show_toast(msg)
            self.set_score(len(self.model.blocks) + len(self.model.platform_blocks))
        else:
            # более полезная подсказка
            if self.model.holds.get("soil", 0) < HOLD_CAP:
                self.msg = _t("Соберите {0} грунта (Пробел)").format(HOLD_CAP - self.model.holds.get("soil", 0))
            else:
                # подсказываем, где ближайшая платформа
                prio = self.model.get_priority_platform()
                if prio and not prio.complete:
                    rx, ry = self.model.robot
                    # направление к платформе
                    cx, cy = prio.center
                    dx = "→" if cx > rx else "←" if cx < rx else ""
                    dy = "↓" if cy > ry else "↑" if cy < ry else ""
                    self.msg = _t("Платформа {0} {1}{2} (B — план, Tab — приоритет)").format(
                        resource_name(prio.resource), dx, dy)
                else:
                    self.msg = _t("Нельзя уложить: {0}").format(msg)
        self.camera.track(*self.model.robot)
        save_blueprint(self.model)
        self.redraw()
        return success, msg

    def do_unload(self) -> str:
        """Выгрузка грунта на стройплощадку (E при полном отсеке)."""
        result = self.model.unload()
        if result == "not_full":
            self.msg = _t("Отсек не полон — набери {0} грунта").format(HOLD_CAP - self.model.holds.get("soil", 0))
        elif result == "ok":
            self.msg = _t("Блок уложен")
        elif result == "complete":
            self.msg = _t("Платформа завершена — стены открыты!")
        elif result == "done":
            self.msg = _t("Все блоки уже уложены")
        self.set_score(len(self.model.blocks) + len(self.model.platform_blocks))
        self.camera.track(*self.model.robot)
        save_blueprint(self.model)
        self.redraw()
        return result

    def toggle_build_plan(self) -> str | None:
        self.overlay = None if self.overlay == "build_plan" else "build_plan"
        self.redraw()
        return self.overlay

    def cycle_priority(self) -> None:
        """Переключает приоритет на следующую незавершённую платформу."""
        platforms = [p for p in self.model.platforms if not p.complete]
        if not platforms:
            return
        # находим текущую приоритетную
        current = None
        for i, p in enumerate(platforms):
            if p.priority > 0:
                current = i
                break
        # снимаем приоритет у текущей
        if current is not None:
            self.model.set_platform_priority(platforms[current].resource, platforms[current].center, 0)
        # ставим приоритет на следующую
        next_idx = (current + 1) % len(platforms) if current is not None else 0
        next_p = platforms[next_idx]
        self.model.set_platform_priority(next_p.resource, next_p.center, 1)
        self.show_toast(_t("Приоритет: {0} ({1},{2})").format(
            resource_name(next_p.resource), next_p.center[0], next_p.center[1]))
        self.redraw()

    # -- галерея платформ ------------------------------------------------------
    def toggle_gallery(self) -> str | None:
        self.overlay = None if self.overlay == "gallery" else "gallery"
        if self.overlay == "gallery":
            # инициализируем на первом найденном ресурсе или воде
            found = self.model.found_types()
            self._gallery_resource = found[0] if found else "water"
            self._gallery_variant = 0
            self._gallery_view_3d = False
        self.redraw()
        return self.overlay

    def _gallery_change_resource(self, direction: int) -> None:
        resources = RESOURCES
        idx = resources.index(self._gallery_resource) if self._gallery_resource in resources else 0
        idx = (idx + direction) % len(resources)
        self._gallery_resource = resources[idx]
        self._gallery_variant = 0
        self.redraw()

    def _gallery_change_variant(self, direction: int) -> None:
        variants = PLATFORM_VARIANTS.get(self._gallery_resource, ())
        if not variants:
            return
        unlocked = get_unlocked_variants(self._gallery_resource)
        if not unlocked:
            return
        # циклим только по разблокированным
        try:
            idx = unlocked.index(self._gallery_variant)
        except ValueError:
            idx = 0
        idx = (idx + direction) % len(unlocked)
        self._gallery_variant = unlocked[idx]
        self.redraw()

    def _gallery_toggle_3d(self) -> None:
        self._gallery_view_3d = not self._gallery_view_3d
        self.redraw()

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

    def _on_canvas_click(self, e: tk.Event) -> None:
        """Обработка кликов по холсту: кнопка 'Language boost' в галерее."""
        if self.overlay != "gallery":
            return
        # проверяем, попал ли клик в кнопку "Учить английский"
        # кнопка находится в левой части, под описанием тиров
        # примерные координаты: x=pad..pad+180, y=после описаний
        # проще: ищем тег
        item = self.canvas.find_closest(e.x, e.y)
        if item:
            tags = self.canvas.gettags(item[0])
            if "lang_boost_btn" in tags:
                self.close_overlay()
                # переключаемся на английский
                if hasattr(self.app, "open_english"):
                    self.app.open_english()
                return

    # -- колесо --------------------------------------------------------------
    def on_wheel(self, direction: int, ctrl: bool, shift: bool,
                 x: int | None = None, y: int | None = None) -> None:
        ov = getattr(self, "help_overlay", None)
        if ov is not None and ov.is_visible():
            return
        if self.overlay is not None:
            return                       # инструкция/находки не прокручиваются
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 10)
        if ctrl:
            # масштаб вокруг указателя мыши
            if self._iso_view:
                self._iso_zoom = iso.zoom_at(direction,
                    self._last_mouse[0] if x is None else x,
                    self._last_mouse[1] if y is None else y, w, h,
                    self.camera, self._iso_zoom)
            else:
                self.camera.zoom_at(direction, self._last_mouse[0] if x is None else x,
                                    self._last_mouse[1] if y is None else y, w, h)
        elif shift:
            self.camera.pan(2 * direction, 0)
        else:
            self.camera.pan(0, 2 * direction)
        self.redraw()

    def _wheel_event(self, e: tk.Event) -> str:
        state = getattr(e, "state", 0) or 0
        self._last_mouse = (int(getattr(e, "x", 0)), int(getattr(e, "y", 0)))
        self.on_wheel(wheel_router.direction(e), bool(state & 0x4), bool(state & 0x1),
                      self._last_mouse[0], self._last_mouse[1])
        return "break"

    def _on_motion(self, e: tk.Event) -> None:
        self._last_mouse = (int(e.x), int(e.y))

    # -- мышь: выделение рамкой и приказ --------------------------------
    def _on_rmb_down(self, e: tk.Event) -> str:
        if self.overlay is not None or self.paused:
            return ""
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 10)
        self._rmb_start = (float(e.x), float(e.y))
        self._rmb_cell = self.camera.to_cell(e.x, e.y, w, h)
        return "break"

    def _on_rmb_drag(self, e: tk.Event) -> str:
        # RMB drag does nothing (no selection rectangle)
        if self._rmb_start is not None:
            return "break"
        return ""

    def _on_rmb_up(self, e: tk.Event) -> str:
        start = self._rmb_start
        self._rmb_start = None
        if start is None or self.overlay is not None or self.paused:
            return ""
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 10)
        tx, ty = self.camera.to_cell(e.x, e.y, w, h)
        if 0 <= tx < self.model.w and 0 <= ty < self.model.h:
            # RMB click: order selected units to move (не выделяет, не box-select)
            result = self.model.command_move(tx, ty)
            n = sum(1 for v in result.values() if v)
            self.show_toast(_t("Приказ: идти в {0},{1} ({2})").format(tx, ty, n))
        self.redraw()
        return "break"

    def _on_lmb_down(self, e: tk.Event) -> str:
        if self.paused:
            return ""
        if self.overlay == "gallery":
            # gallery button handling from _on_canvas_click
            item = self.canvas.find_closest(e.x, e.y)
            if item:
                tags = self.canvas.gettags(item[0])
                if "lang_boost_btn" in tags:
                    self.close_overlay()
                    if hasattr(self.app, "open_english"):
                        self.app.open_english()
                    return ""
        if self.overlay is not None:
            return ""
        self._lmb_start = (float(e.x), float(e.y))
        self._lmb_cell = self.camera.to_cell(e.x, e.y, max(self.canvas.winfo_width(), 10), max(self.canvas.winfo_height(), 10))
        self._lmb_box = None
        return "break"

    def _on_lmb_drag(self, e: tk.Event) -> str:
        if self._lmb_start is None:
            return ""
        x0, y0 = self._lmb_start
        if abs(e.x - x0) + abs(e.y - y0) < 6 and self._lmb_box is None:
            return "break"
        if self._lmb_box is not None:
            self.canvas.delete(self._lmb_box)
        self._lmb_box = self.canvas.create_rectangle(
            x0, y0, e.x, e.y, outline=GREEN, width=2, dash=(4, 2), tags="selbox")
        return "break"

    def _on_lmb_up(self, e: tk.Event) -> str:
        start = self._lmb_start
        self._lmb_start = None
        if self._lmb_box is not None:
            self.canvas.delete(self._lmb_box)
            self._lmb_box = None
        if start is None or self.overlay is not None or self.paused:
            return ""
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 10)
        x0, y0 = start
        if abs(e.x - x0) + abs(e.y - y0) >= 6:
            # box select
            ax, ay = self.camera.to_cell(x0, y0, w, h)
            bx, by = self.camera.to_cell(e.x, e.y, w, h)
            picked = self.model.select_rect(ax, ay, bx, by)
            self.show_toast(_t("Выделено терраформеров: {0}").format(len(picked)))
        else:
            # LMB click - select unit or clear selection
            tx, ty = self.camera.to_cell(e.x, e.y, w, h)
            if 0 <= tx < self.model.w and 0 <= ty < self.model.h:
                unit = self.model.unit_at(tx, ty)
                if unit is not None:
                    self.model.selected = {unit.uid}
                    self.show_toast(_t("Выделено терраформеров: {0}").format(1))
                else:
                    self.model.clear_selection()
        self.redraw()
        return "break"

    def _on_mmb_down(self, e: tk.Event) -> str:
        self._mmb_last = (float(e.x), float(e.y))
        return "break"

    def _on_mmb_drag(self, e: tk.Event) -> str:
        if self._mmb_last is None:
            return ""
        lx, ly = self._mmb_last
        cell = max(self.camera.cell_px(), 1.0)
        self.camera.pan(-(e.x - lx) / cell, -(e.y - ly) / cell)
        self._mmb_last = (float(e.x), float(e.y))
        self.redraw()
        return "break"

    def _on_mmb_up(self, e: tk.Event) -> str:
        self._mmb_last = None
        return "break"

    # -- оверлеи заданий и стройки --------------------------------------
    def toggle_missions(self) -> str | None:
        self.overlay = None if self.overlay == "missions" else "missions"
        if self.overlay == "missions":
            self.model.mission_book.mark_read()
        self.redraw()
        return self.overlay

    def toggle_structures(self) -> str | None:
        self.overlay = None if self.overlay == "structures" else "structures"
        self.redraw()
        return self.overlay

    def _structure_rows(self) -> list[strategy.Structure]:
        return list(strategy.STRUCTURES.values())

    def _available_structures(self) -> list[strategy.Structure]:
        unit = (self.model.selected_units() or [self.model.main_unit])[0]
        return [s for s in strategy.STRUCTURES.values()
                if strategy.structure_available(s.key, unit.level, self.model.developer)]

    def _struct_change(self, direction: int) -> None:
        items = self._structure_rows()
        if not items:
            return
        self._struct_index = (self._struct_index + direction) % len(items)
        self.redraw()

    def _struct_build(self) -> None:
        items = self._structure_rows()
        if not items:
            return
        spec = items[self._struct_index % len(items)]
        ok, msg = self.model.build_structure(spec.key)
        self.msg = msg
        self.show_toast(msg, ok)
        save_blueprint(self.model)
        self.redraw()

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

        if self._iso_view:
            self._draw_iso(w, h)
            # HUD и оверлеи рисуются в _draw_iso через _draw_hud
            self._draw_overlays(w, h)
            return

        model = self.model
        cam = self.camera
        cell = max(cam.cell_px(), 4.0)
        half_w = w / (2.0 * cell)
        half_h = h / (2.0 * cell)
        x0 = max(0, int(math.floor(cam.cx - half_w)) - 1)
        x1 = min(model.w - 1, int(math.ceil(cam.cx + half_w)) + 1)
        y0 = max(0, int(math.floor(cam.cy - half_h)) - 1)
        y1 = min(model.h - 1, int(math.ceil(cam.cy + half_h)) + 1)

        visible = model.visible_cells()
        explored = model.explored

        for y in range(y0, y1 + 1):
            row = model.dug[y]
            for x in range(x0, x1 + 1):
                sx, sy = cam.to_screen(x, y, w, h)
                if (x, y) not in explored:
                    # туман: карта большая, видна только разведанная часть
                    c.create_rectangle(sx, sy, sx + cell, sy + cell, fill=BG, outline="")
                    continue
                color = self._layer_color(row[x])
                if (x, y) not in visible:
                    color = blend(color, BG, 0.62)      # разведано, но сейчас не видно
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

        # уложенные блоки (фундамент + платформы)
        block_fill = blend(AMBER, TEXT, 0.25)
        for x, y in model.blocks:
            px_, py_ = cam.to_screen(x, y, w, h)
            c.create_rectangle(px_ + 2, py_ + 2, px_ + cell - 2, py_ + cell - 2,
                               fill=block_fill, outline=AMBER, width=2)
        # блоки платформ добычи — тот же стиль
        for x, y in model.platform_blocks:
            px_, py_ = cam.to_screen(x, y, w, h)
            c.create_rectangle(px_ + 2, py_ + 2, px_ + cell - 2, py_ + cell - 2,
                               fill=block_fill, outline=AMBER, width=2)

        # граница поля
        bx0, by0 = cam.to_screen(0, 0, w, h)
        bx1, by1 = cam.to_screen(model.w, model.h, w, h)
        c.create_rectangle(bx0, by0, bx1, by1, outline=LINE, width=2)

        # призрачный паттерн приоритетной платформы на карте
        self._draw_priority_ghost(w, h, cell, cam, x0, x1, y0, y1)

        self._draw_buildings(w, h, cell)
        self._draw_worm(w, h, cell)
        self._draw_units(w, h, cell)

        # подсказка платформы, если робот стоит на открытой находке
        self._draw_platform_hint(w, h, cell)

        # верхняя панель — всегда в экранных координатах, на тёмной подложке
        # Рисуем фон ПЕРВЫМ, сохраняем id, и перерисуем coords в конце по реальному ty
        found = sum(model.finds_count.values())
        bg_id = c.create_rectangle(0, 0, px(230), px(8), fill=BG, outline=LINE)
        ty = px(8)
        level_name = model.standing.current_level
        lines = (
            (_t("Учебная смена / тренажёр"), TEXT, True),
            (f"Уровень {level_name} · высота до {model.max_build_height}", AMBER, True),
            (_t("Грунт {0}/{1}").format(model.holds.get("soil", 0), HOLD_CAP), MUTED, False),
            (_t("Фундамент {0}/{1}").format(*model.progress()), MUTED, False),
            (_t("Находки {0}").format(found), MUTED, False),
            (f"Кредиты {model.credits}", GREEN, False),
            (f"Отряд {len(model.units)}", MUTED, False),
            (_t("Масштаб {0}%").format(int(round(cam.zoom * 100))), MUTED, False),
        )
        for text, color, bold in lines:
            c.create_text(px(10), ty, text=text, fill=color, anchor="nw",
                          font=theme.font(10, bold))
            ty += px(16)

        # задания: сколько выполнено и сколько непрочитанных тревог
        book = model.mission_book
        done = book.done_count()
        total = len(book.missions)
        mark = " ●" if book.unread else ""
        c.create_text(px(10), ty, text=f"ЗАДАНИЯ {done}/{total}{mark}",
                      fill=GREEN if done else MUTED, anchor="nw", font=theme.font(9, True))
        ty += px(15)
        if model.holds.get(strategy.SPICE, 0):
            c.create_text(px(10), ty, text=f"Специя {model.holds.get(strategy.SPICE, 0)}",
                          fill=AMBER, anchor="nw", font=theme.font(9, True))
            ty += px(14)

        # прогресс платформ в HUD
        active_platforms = [p for p in model.platforms if not p.complete]
        if active_platforms:
            ty += px(4)
            c.create_text(px(10), ty, text=_t("ПЛАТФОРМЫ:"), fill=CYAN, anchor="nw",
                          font=theme.font(9, True))
            ty += px(14)
            for p in active_platforms[:3]:  # показываем до 3
                prio_mark = " ★" if p.priority > 0 else ""
                pct = p.progress_pct()
                fill = GREEN if pct == 100 else AMBER if pct > 0 else MUTED
                c.create_text(px(10), ty,
                              text=f"{resource_name(p.resource)[:10]} {pct}% · h{p.height}{prio_mark}",
                              fill=fill, anchor="nw", font=theme.font(8))
                ty += px(13)

        if model.walls_open:
            c.create_text(px(10), ty, text=_t("СТЕНЫ ОТКРЫТЫ"), fill=GREEN, anchor="nw",
                          font=theme.font(11, True))
            ty += px(16)

        # визуальная шкала прогресса языка — возвращает нижнюю Y
        ty = self._draw_language_progress_bar(w, h, ty + px(10))

        # расширяем фон панели под реальный контент
        c.coords(bg_id, 0, 0, px(230), ty)

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
        elif self.overlay == "gallery":
            self._draw_gallery(w, h)
        elif self.overlay == "missions":
            self._draw_missions(w, h)
        elif self.overlay == "structures":
            self._draw_structures(w, h)
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

    @staticmethod
    def _upgrade_display_names() -> dict[str, str]:
        """Возвращает локализованные имена апгрейдов по их id."""
        return {
            "soil_compactor": _t("Пресс для грунта"),
            "auto_unloader": _t("Автовыгрузка"),
            "water_purifier": _t("Очистка воды"),
            "yield_booster": _t("Усилитель добычи"),
            "remote_control": _t("Дистанционное управление"),
            "logistics_network": _t("Логистическая сеть"),
            "auto_builder": _t("Автостроитель"),
            "terraform_core": _t("Ядро терраформирования"),
        }

    def _draw_language_progress_bar(self, w: int, h: int, y: int) -> int:
        """Шкала из восьми уровней A1…C2: текущий, проценты и что откроется дальше.

        Возвращает нижнюю Y после всего содержимого.
        """
        c = self.canvas
        standing = self.model.standing
        levels = strategy.LEVELS
        current = standing.current
        tier = PROGRESSION_TIERS.get(current.index, PROGRESSION_TIERS[0])
        next_tier = get_next_tier_preview(current.index)

        bar_x = px(10)
        bar_w = px(210)
        bar_h = px(16)
        seg_w = max(1, bar_w // len(levels))

        ty = self._draw_text_stacked(c, bar_x, y, _t("ПРОГРЕСС ЯЗЫКА →"), CYAN, "nw",
                                     theme.font(9, True))
        c.create_rectangle(bar_x, ty, bar_x + bar_w, ty + bar_h, fill=BG2,
                           outline=LINE, tags="langbar")
        bar_y = ty
        ty += bar_h + px(4)

        for i, name in enumerate(levels):
            state = standing.levels[i]
            seg_x = bar_x + i * seg_w
            is_current = name == current.level
            fill = AMBER if is_current else (CYAN if state.unlocked else BG2)
            c.create_rectangle(seg_x + 1, bar_y + 1, seg_x + seg_w - 1, bar_y + bar_h - 1,
                               fill=fill, outline="", tags="langbar")
            # процент внутри сегмента — зелёная полоса снизу
            if state.pct > 0:
                pct_w = int((seg_w - 2) * min(100, state.pct) / 100)
                if pct_w > 0:
                    c.create_rectangle(seg_x + 1, bar_y + bar_h - px(5),
                                       seg_x + 1 + pct_w, bar_y + bar_h - 1,
                                       fill=GREEN, outline="", tags="langbar")
            c.create_text(seg_x + seg_w / 2, bar_y + bar_h / 2 - px(1), text=name,
                          fill=BG if is_current else TEXT, anchor="center",
                          font=theme.font(7, True, mono=True), tags="langbar")

        ty = self._draw_text_stacked(
            c, bar_x, ty,
            f"Сейчас: {current.title} · {current.pct}%",
            TEXT, "nw", theme.font(8, True), width=bar_w)

        unlocked_variants: list[int] = []
        for res in RESOURCES:
            unlocked_variants.extend(tier["platform_variants"].get(res, []))
        max_var = max(unlocked_variants) if unlocked_variants else 0
        robots = ", ".join(tier["robots"])
        upgrade_names = self._upgrade_display_names()
        upgrades_localized = (", ".join(upgrade_names.get(u, u) for u in tier["upgrades"])
                              if tier["upgrades"] else _t("—"))
        ty = self._draw_text_stacked(
            c, bar_x, ty,
            _t("Открыто: варианты до {0} · Роботы: {1} · Апгрейды: {2}").format(
                max_var, robots, upgrades_localized),
            TEXT, "nw", theme.font(8), width=bar_w)

        if next_tier and current.index < len(levels) - 1:
            next_unlocked: list[int] = []
            for res in RESOURCES:
                next_unlocked.extend(next_tier["platform_variants"].get(res, []))
            next_max_var = max(next_unlocked) if next_unlocked else max_var
            next_robots = ", ".join(next_tier["robots"])
            next_upgrades = (", ".join(upgrade_names.get(u, u) for u in next_tier["upgrades"])
                             if next_tier["upgrades"] else _t("—"))
            ty = self._draw_text_stacked(
                c, bar_x, ty,
                _t("След. уровень: варианты до {0} · {1} · {2}").format(
                    next_max_var, next_robots, next_upgrades),
                AMBER, "nw", theme.font(8, True), width=bar_w)
            ty = self._draw_text_stacked(
                c, bar_x, ty,
                f"До уровня {standing.next_level}: {100 - current.pct}%",
                MUTED, "nw", theme.font(7), width=bar_w)

        return ty

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

    def _draw_platform_hint(self, w: int, h: int, cell: float) -> None:
        """Рисует мини-схему платформы вокруг ресурса, если робот стоит на этой находке."""
        c = self.canvas
        model = self.model
        rx, ry = model.robot

        # проверяем, стоит ли робот на открытой находке
        if (rx, ry) not in model.revealed:
            return

        res = model.finds.get((rx, ry))
        if not res:
            return
        res = res[0]

        # находим платформу для этого ресурса и центра
        platform = None
        for p in model.platforms:
            if p.resource == res and p.center == (rx, ry):
                platform = p
                break
        if not platform:
            return

        # рисуем мини-схему справа от робота
        sx, sy = self.camera.to_screen(rx, ry, w, h)
        # схема появляется справа от робота
        hint_x = sx + cell + px(8)
        hint_y = sy - px(4)
        max_h = h - hint_y - px(40)  # место под подсказку
        if max_h < px(80):
            hint_y = sy - max_h - px(8)
            if hint_y < px(40):
                hint_y = px(40)

        # границы паттерна
        min_dx = min(dx for dx, _ in platform.pattern) if platform.pattern else -1
        max_dx = max(dx for dx, _ in platform.pattern) if platform.pattern else 1
        min_dy = min(dy for _, dy in platform.pattern) if platform.pattern else -1
        max_dy = max(dy for _, dy in platform.pattern) if platform.pattern else 1
        grid_w = max_dx - min_dx + 1
        grid_h = max_dy - min_dy + 1
        cell_size = min(px(18), max(px(8), min(max_h // max(1, grid_h), px(80) // max(1, grid_w))))

        # заголовок
        unlocked = get_unlocked_variants(res)
        is_unlocked = platform.variant_index in unlocked
        variant_num = unlocked.index(platform.variant_index) + 1 if is_unlocked else platform.variant_index + 1
        total_unlocked = len(unlocked)

        title = _t("Платформа {0}: {1}/{2}").format(
            resource_name(res), variant_num, total_unlocked)
        if not is_unlocked:
            title += " 🔒"
        c.create_text(hint_x, hint_y, text=title, fill=AMBER if is_unlocked else MUTED, anchor="nw",
                      font=theme.font(9, True), tags="hint")
        hint_y += px(18)

        # сетка
        origin_x = hint_x
        origin_y = hint_y

        for dy in range(min_dy, max_dy + 1):
            for dx in range(min_dx, max_dx + 1):
                cx = origin_x + (dx - min_dx) * cell_size
                cy = origin_y + (dy - min_dy) * cell_size
                is_center = (dx == 0 and dy == 0)
                is_block = (dx, dy) in platform.pattern
                is_built = (dx, dy) in platform.built

                if is_center:
                    # центр — находка
                    fill = SPRING if res == "water" else GREEN
                    c.create_rectangle(cx, cy, cx + cell_size, cy + cell_size,
                                       fill=fill, outline=TEXT, width=2, tags="hint")
                    c.create_text(cx + cell_size // 2, cy + cell_size // 2, text="●",
                                  fill=BG, anchor="center", font=theme.font(max(8, cell_size // 2)), tags="hint")
                elif is_block:
                    # клетка платформы
                    if is_built:
                        fill = AMBER
                        outline = TEXT
                    else:
                        fill = blend(AMBER, BG, 0.4) if is_unlocked else MUTED
                        outline = LINE
                    c.create_rectangle(cx + 1, cy + 1, cx + cell_size - 1, cy + cell_size - 1,
                                       fill=fill, outline=outline, width=1, tags="hint")
                    if is_built:
                        c.create_text(cx + cell_size // 2, cy + cell_size // 2, text="█",
                                      fill=BG, anchor="center", font=theme.font(max(8, cell_size // 2)), tags="hint")
                else:
                    # пусто
                    c.create_rectangle(cx, cy, cx + cell_size, cy + cell_size,
                                       fill=BG2, outline=LINE, tags="hint")

        # легенда
        legend_y = origin_y + grid_h * cell_size + px(4)
        c.create_text(hint_x, legend_y, text=_t("● — ресурс   █ — блок   □ — нужно поставить"),
                      fill=MUTED, anchor="nw", font=theme.font(7), tags="hint")
        if not is_unlocked:
            needed_level = next(i for i, t in PROGRESSION_TIERS.items()
                                if platform.variant_index in t["platform_variants"].get(res, ()))
            c.create_text(hint_x, legend_y + px(12),
                          text=_t("🔒 Нужен уровень языка {0}").format(needed_level),
                          fill=AMBER, anchor="nw", font=theme.font(8, True), tags="hint")

    def _draw_priority_ghost(self, w: int, h: int, cell: float, cam, x0: int, x1: int, y0: int, y1: int) -> None:
        """Рисует полупрозрачный призрачный паттерн приоритетной платформы на карте."""
        c = self.canvas
        model = self.model
        prio = model.get_priority_platform()
        if not prio or prio.complete:
            return

        # рисуем только если платформа на экране
        cx, cy = prio.center
        # проверяем, виден ли центр
        min_dx = min(dx for dx, _ in prio.pattern) if prio.pattern else -1
        max_dx = max(dx for dx, _ in prio.pattern) if prio.pattern else 1
        min_dy = min(dy for _, dy in prio.pattern) if prio.pattern else -1
        max_dy = max(dy for _, dy in prio.pattern) if prio.pattern else 1

        for dy in range(min_dy, max_dy + 1):
            for dx in range(min_dx, max_dx + 1):
                x = cx + dx
                y = cy + dy
                if (dx == 0 and dy == 0) or (x, y) not in prio.all_cells_abs():
                    continue
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    continue
                sx, sy = cam.to_screen(x, y, w, h)
                is_built = (x, y) in prio.built
                if is_built:
                    continue  # уже уложенные блоки рисуются отдельно
                # полупрозрачный призрак
                fill = blend(AMBER, BG2, 0.6)
                c.create_rectangle(sx + 2, sy + 2, sx + cell - 2, sy + cell - 2,
                                   fill=fill, outline=AMBER, width=1, dash=(4, 4), tags="ghost")
                # маленькая стрелка-указатель
                if cell > 16:
                    mx = sx + cell / 2
                    my = sy + cell / 2
                    c.create_text(mx, my, text="▢", fill=AMBER, anchor="center",
                                  font=theme.font(max(8, int(cell * 0.3))), tags="ghost")

        # метка ресурса у центра
        sx, sy = cam.to_screen(cx, cy, w, h)
        c.create_text(sx + cell / 2, sy - cell * 0.3,
                      text=_t("🎯 {0}").format(resource_name(prio.resource)),
                      fill=AMBER, anchor="s", font=theme.font(8, True), tags="ghost")

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

    def _draw_missions(self, w: int, h: int) -> None:
        """Оверлей заданий: уровни слева, задания текущего уровня и тревоги справа."""
        c = self.canvas
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")
        pad = px(16)
        book = self.model.mission_book
        standing = self.model.standing
        c.create_text(w // 2, pad, text="ЗАДАНИЯ · ТРЕВОГИ", fill=AMBER, anchor="n",
                      font=theme.font(14, True), tags="missions")
        top = pad + px(28)

        left_w = min(px(300), w // 3)
        y = top
        c.create_text(pad, y, text="УРОВНИ", fill=CYAN, anchor="nw",
                      font=theme.font(10, True), tags="missions")
        y += px(20)
        for i, name in enumerate(strategy.LEVELS):
            items = book.by_level(name)
            done = sum(1 for m in items if m.done)
            total = len(items)
            state = standing.levels[i]
            is_cur = name == standing.current_level
            complete = bool(total) and done == total
            mark = "✓" if complete else "○"
            color = GREEN if complete else (AMBER if is_cur else (TEXT if state.unlocked else MUTED))
            prefix = "▶ " if is_cur else "  "
            c.create_text(pad, y, text=f"{prefix}{mark} {name} · {done}/{total} · {state.pct}%",
                          fill=color, anchor="nw",
                          font=theme.font(9, is_cur), tags="missions")
            y += px(18)

        c.create_line(pad + left_w, top, pad + left_w, h - px(38), fill=LINE, tags="missions")
        x = pad + left_w + px(16)
        right_w = max(px(120), w - x - pad)
        y = top
        cur = standing.current_level
        y = self._draw_text_stacked(c, x, y, f"ЗАДАНИЯ УРОВНЯ {cur}", CYAN, "nw",
                                    theme.font(10, True), width=right_w)
        stats = self.model.stats()
        for m in book.by_level(cur):
            prog = m.progress(stats)
            head = ("✓ " if m.done else "○ ") + m.title
            y = self._draw_text_stacked(c, x, y, head, GREEN if m.done else TEXT, "nw",
                                        theme.font(9, True), width=right_w)
            body = f"{m.hint}  [{prog}/{m.target}]  +{m.reward_credits} кр."
            y = self._draw_text_stacked(c, x + px(12), y, body, MUTED, "nw",
                                        theme.font(8), width=right_w - px(12))
            y += px(4)

        y += px(4)
        y = self._draw_text_stacked(c, x, y, "ТРЕВОГИ", AMBER, "nw",
                                    theme.font(10, True), width=right_w)
        alerts = book.alerts[-5:]
        if not alerts:
            y = self._draw_text_stacked(c, x, y, "Пока тихо. Копайте и стройте.", MUTED, "nw",
                                        theme.font(8), width=right_w)
        for a in alerts:
            color = {"mission": GREEN, "reward": GREEN, "warn": AMBER}.get(a.kind, MUTED)
            line = a.title + (f" — {a.body}" if a.body else "")
            y = self._draw_text_stacked(c, x, y, line, color, "nw",
                                        theme.font(8), width=right_w)

        c.create_text(w // 2, h - px(8), text="T или Esc — закрыть", fill=MUTED,
                      anchor="s", font=theme.font(9, True), tags="missions")

    def _draw_structures(self, w: int, h: int) -> None:
        """Оверлей стройки: высота, цена, доход и требуемый уровень каждого здания."""
        c = self.canvas
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")
        pad = px(16)
        rows = list(strategy.STRUCTURES.values())
        if not rows:
            return
        self._struct_index %= len(rows)
        unit = (self.model.selected_units() or [self.model.main_unit])[0]
        c.create_text(w // 2, pad, text="СТРОЙКА · ЗДАНИЯ", fill=AMBER, anchor="n",
                      font=theme.font(14, True), tags="structs")
        top = pad + px(28)
        c.create_text(pad, top, text=f"Кредиты: {self.model.credits}", fill=GREEN,
                      anchor="nw", font=theme.font(10, True), tags="structs")
        c.create_text(pad, top + px(16),
                      text=f"Строитель: {unit.name} · высота до {unit.max_height}",
                      fill=TEXT, anchor="nw", font=theme.font(9), tags="structs")

        y = top + px(40)
        row_h = px(22)
        for i, spec in enumerate(rows):
            avail = strategy.structure_available(spec.key, unit.level, self.model.developer)
            afford = self.model.credits >= spec.cost
            selected = i == self._struct_index
            color = GREEN if (avail and afford) else (AMBER if avail else MUTED)
            mark = "✓" if avail else "🔒"
            prefix = "▶ " if selected else "  "
            if selected:
                c.create_rectangle(pad - px(4), y - px(2), w - pad, y + row_h - px(4),
                                   fill=BG2, outline=AMBER, tags="structs")
            c.create_text(pad, y, anchor="nw", fill=color, font=theme.font(9, selected), tags="structs",
                          text=f"{prefix}{mark} {spec.title}  h{spec.height}  "
                               f"{spec.cost} кр · +{spec.income}/тик · {spec.level}+")
            y += row_h

        spec = rows[self._struct_index]
        y += px(6)
        y = self._draw_text_stacked(c, pad, y, spec.hint, TEXT, "nw",
                                    theme.font(9), width=w - pad * 2)
        if not strategy.structure_available(spec.key, unit.level, self.model.developer):
            y = self._draw_text_stacked(
                c, pad, y,
                f"Нужен терраформер {spec.level} (высота {spec.height}).",
                AMBER, "nw", theme.font(9, True), width=w - pad * 2)
        elif self.model.credits < spec.cost:
            y = self._draw_text_stacked(
                c, pad, y,
                f"Не хватает {spec.cost - self.model.credits} кредитов.",
                AMBER, "nw", theme.font(9, True), width=w - pad * 2)

        c.create_text(w // 2, h - px(8),
                      text="↑/↓ выбор · Пробел построить · N или Esc — закрыть",
                      fill=MUTED, anchor="s", font=theme.font(9, True), tags="structs")

    def _unit_color(self, level: str) -> str:
        palette = (CYAN, GREEN, AMBER, "#FF7AD9", "#9B8CFF", "#FFB454", "#7FE0C3", TEXT)
        return palette[strategy.level_index(level) % len(palette)]

    def _draw_units(self, w: int, h: int, cell: float) -> None:
        """Все терраформеры отряда: цвет по уровню, кольцо выделения, HP."""
        c = self.canvas
        for u in self.model.units:
            sx, sy = self.camera.to_screen(u.x, u.y, w, h)
            cx = sx + cell / 2.0
            cy = sy + cell / 2.0
            body = cell * 0.52
            color = self._unit_color(u.level)
            if u.uid in self.model.selected:
                c.create_oval(sx + 1, sy + 1, sx + cell - 1, sy + cell - 1,
                              outline=GREEN, width=max(2, int(cell * 0.08)), tags="unit")
            track_w = max(2.0, cell * 0.16)
            c.create_rectangle(sx + cell * 0.10, sy + cell * 0.20,
                               sx + cell * 0.10 + track_w, sy + cell * 0.80,
                               fill=MUTED, outline="", tags="unit")
            c.create_rectangle(sx + cell * 0.90 - track_w, sy + cell * 0.20,
                               sx + cell * 0.90, sy + cell * 0.80,
                               fill=MUTED, outline="", tags="unit")
            c.create_rectangle(cx - body / 2, cy - body / 2, cx + body / 2, cy + body / 2,
                               fill=color, outline=blend(color, TEXT, 0.35), tags="unit")
            label = u.level if len(u.level) <= 4 else u.level[:4]
            c.create_text(cx, cy, text=label, fill=BG, tags="unit",
                          font=theme.font(max(6, int(cell * 0.24)), True, mono=True))
            if u.hp < 100:
                bar_w = cell * 0.7
                x0 = sx + cell * 0.15
                y0 = sy + cell * 0.92
                c.create_rectangle(x0, y0, x0 + bar_w, y0 + max(2, cell * 0.08),
                                   fill=BG, outline="", tags="unit")
                c.create_rectangle(x0, y0, x0 + bar_w * max(0, u.hp) / 100.0,
                                   y0 + max(2, cell * 0.08), fill=GREEN if u.hp > 40 else AMBER,
                                   outline="", tags="unit")
            if u.uid == self.model.main_unit.uid:
                fx, fy = self.model.facing
                c.create_line(cx, cy, cx + fx * cell * 0.45, cy + fy * cell * 0.45,
                              fill=AMBER, width=max(2, int(cell * 0.12)), arrow="last",
                              tags="unit")
            if u.path:
                # пунктир маршрута
                points = [cx, cy]
                for px_, py_ in u.path[::max(1, len(u.path) // 8)]:
                    ax, ay = self.camera.to_screen(px_, py_, w, h)
                    points += [ax + cell / 2, ay + cell / 2]
                if u.target:
                    ax, ay = self.camera.to_screen(u.target[0], u.target[1], w, h)
                    points += [ax + cell / 2, ay + cell / 2]
                if len(points) >= 4:
                    c.create_line(*points, fill=color, width=1, dash=(2, 4), tags="unit")

    def _draw_robot(self, w: int, h: int, cell: float) -> None:
        """Совместимость: главный терраформер рисуется вместе с отрядом."""
        self._draw_units(w, h, cell)

    def _draw_buildings(self, w: int, h: int, cell: float) -> None:
        """Здания: высота видна как вертикальный объём, связь — зелёная нить."""
        c = self.canvas
        model = self.model
        for b in model.buildings:
            sx, sy = self.camera.to_screen(b.center[0], b.center[1], w, h)
            if sx < -cell * 4 or sy < -cell * 8 or sx > w + cell or sy > h + cell:
                continue
            spec = strategy.STRUCTURES.get(b.type)
            color = GREEN if b.built else MUTED
            rise = cell * 0.16 * max(1, b.height)
            # тень/основание
            c.create_rectangle(sx + 2, sy + 2, sx + cell - 2, sy + cell - 2,
                               fill=blend(color, BG, 0.55), outline=color, width=1, tags="building")
            # объём вверх
            c.create_rectangle(sx + cell * 0.28, sy - rise, sx + cell * 0.72, sy + cell * 0.55,
                               fill=color, outline=blend(color, TEXT, 0.4), tags="building")
            c.create_text(sx + cell / 2, sy + cell * 0.30,
                          text=f"h{b.height}", fill=BG, tags="building",
                          font=theme.font(max(6, int(cell * 0.2)), True))
            if b.connected:
                # коммуникация к ближайшему зданию/базе
                best = None
                for other in model.buildings + [None]:
                    ox, oy = (other.center if other is not None else model.site[:2])
                    if (ox, oy) == tuple(b.center):
                        continue
                    d = abs(ox - b.center[0]) + abs(oy - b.center[1])
                    if best is None or d < best[0]:
                        best = (d, ox, oy)
                if best:
                    ox, oy = self.camera.to_screen(best[1], best[2], w, h)
                    c.create_line(sx + cell / 2, sy + cell / 2, ox + cell / 2, oy + cell / 2,
                                  fill=blend(GREEN, BG, 0.35), width=1, dash=(1, 3), tags="building")

    def _draw_worm(self, w: int, h: int, cell: float) -> None:
        """След червя (песок вспучился) и сам червь под верхним слоем."""
        c = self.canvas
        worm = self.model.worm
        if not worm.alive:
            return
        for (x, y), ttl in worm.trail.items():
            if not self.model.is_explored(x, y):
                continue
            sx, sy = self.camera.to_screen(x, y, w, h)
            fade = max(0.15, min(1.0, ttl / max(1, strategy.WORM_TRAIL_TTL)))
            c.create_rectangle(sx + cell * 0.18, sy + cell * 0.18,
                               sx + cell * 0.82, sy + cell * 0.82,
                               fill=blend("#C79A4A", BG, 1.0 - fade), outline="", tags="worm")
        sx, sy = self.camera.to_screen(worm.x, worm.y, w, h)
        cx, cy = sx + cell / 2, sy + cell / 2
        r = cell * 0.34
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=blend("#C79A4A", BG, 0.25), outline=AMBER, width=2, tags="worm")
        c.create_text(cx, cy, text="≈", fill=BG, tags="worm",
                      font=theme.font(max(8, int(cell * 0.35)), True))

    # -- галерея платформ: отрисовка -------------------------------------------
    def _draw_gallery(self, w: int, h: int) -> None:
        """Галерея платформ: 2D схема + 3D превью (псевдо-изометрия), прогрессия языка."""
        c = self.canvas
        c.create_rectangle(0, 0, w, h, fill=BG, outline="")
        pad = px(20)

        # заголовок
        lang_level = get_language_level()
        tier = PROGRESSION_TIERS.get(lang_level, PROGRESSION_TIERS[0])
        next_tier = get_next_tier_preview(lang_level)

        title_text = _t("ГАЛЕРЕЯ ПЛАТФОРМ · Уровень языка: {0}").format(lang_level)
        c.create_text(w // 2, pad, text=title_text, fill=AMBER, anchor="n",
                      font=theme.font(14, True), tags="gallery")

        # текущий тир
        y = pad + px(30)
        c.create_text(pad, y, text=_t("Текущий уровень:"), fill=CYAN, anchor="nw",
                      font=theme.font(10, True), tags="gallery")
        y += px(18)
        for line in tier["description"].split(". "):
            c.create_text(pad + px(10), y, text="• " + line, fill=TEXT, anchor="nw",
                          font=theme.font(9), width=w - pad * 2 - px(20), tags="gallery")
            y += px(16)

        # следующий тир — мотивация
        if next_tier:
            y += px(10)
            c.create_text(pad, y, text=_t("Следующий уровень (мотивация учить):"), fill=GREEN, anchor="nw",
                          font=theme.font(10, True), tags="gallery")
            y += px(18)
            for line in next_tier["description"].split(". "):
                c.create_text(pad + px(10), y, text="→ " + line, fill=MUTED, anchor="nw",
                              font=theme.font(9), width=w - pad * 2 - px(20), tags="gallery")
                y += px(16)
            c.create_text(pad, y + px(4), text=_t("Изучайте язык, чтобы разблокировать!"), fill=AMBER, anchor="nw",
                          font=theme.font(9, True), tags="gallery")

        # кнопка-скороход к обучению языку
        if lang_level < 5:
            btn_y = y + px(28)
            btn_w = px(180)
            btn_h = px(28)
            btn_x = pad
            # проверяем наведение мыши (простая реализация — просто рисуем кнопку)
            c.create_rectangle(btn_x, btn_y, btn_x + btn_w, btn_y + btn_h,
                               fill=GREEN, outline=CYAN, width=2, tags=("gallery", "lang_boost_btn"))
            c.create_text(btn_x + btn_w // 2, btn_y + btn_h // 2,
                          text=_t("📚 Учить английский →"), fill=BG, anchor="center",
                          font=theme.font(10, True), tags=("gallery", "lang_boost_btn"))

        # область превью справа
        preview_x = w // 2 + pad
        preview_w = w // 2 - pad * 2
        preview_y = pad + px(30)

        # выбор ресурса (вкладки сверху)
        res_y = preview_y
        res_names = RESOURCES
        btn_w = preview_w // len(res_names)
        for i, res in enumerate(res_names):
            bx = preview_x + i * btn_w
            unlocked = get_unlocked_variants(res)
            is_sel = res == self._gallery_resource
            is_unlocked = bool(unlocked)
            fill = AMBER if is_sel else (CYAN if is_unlocked else MUTED)
            outline = TEXT if is_sel else LINE
            c.create_rectangle(bx + 2, res_y, bx + btn_w - 2, res_y + px(28),
                               fill=fill, outline=outline, width=2 if is_sel else 1, tags="gallery")
            c.create_text(bx + btn_w // 2, res_y + px(14), text=resource_name(res)[:12],
                          fill=BG if is_sel else TEXT, anchor="center",
                          font=theme.font(8, True), tags="gallery")
            if not is_unlocked:
                c.create_text(bx + btn_w // 2, res_y + px(14), text="🔒",
                              fill=MUTED, anchor="center", font=theme.font(10), tags="gallery")

        # область схемы
        schema_y = res_y + px(36)
        schema_h = h - schema_y - pad - px(40)
        schema_w = preview_w

        # рисуем 2D схему или 3D превью
        if self._gallery_view_3d:
            self._draw_gallery_3d_preview(c, preview_x, schema_y, schema_w, schema_h)
        else:
            self._draw_gallery_2d_schema(c, preview_x, schema_y, schema_w, schema_h)

        # переключатель 2D/3D
        toggle_y = h - pad - px(24)
        c.create_rectangle(preview_x, toggle_y, preview_x + schema_w, toggle_y + px(28),
                           fill=BG2, outline=LINE, tags="gallery")
        view_text = _t("3D превью") if self._gallery_view_3d else _t("2D схема")
        c.create_text(preview_x + schema_w // 2, toggle_y + px(14),
                      text=_t("Пробел/Enter: {0}").format(view_text), fill=TEXT, anchor="center",
                      font=theme.font(9), tags="gallery")

        # подсказки управления
        hint_y = h - pad - px(8)
        c.create_text(w // 2, hint_y, text=_t("←/→ ресурс · ↑/↓ вариант · Пробел 2D/3D · G/Esc закрыть"),
                      fill=MUTED, anchor="s", font=theme.font(8), tags="gallery")

    def _draw_gallery_2d_schema(self, c: tk.Canvas, x: int, y: int, w: int, h: int) -> None:
        """Рисует 2D схему платформы: сетка с центром, блоками, легендой."""
        res = self._gallery_resource
        variant_idx = self._gallery_variant
        variants = PLATFORM_VARIANTS.get(res, ())
        if variant_idx >= len(variants):
            variant_idx = 0
        pattern = variants[variant_idx]
        desc = VARIANT_DESC.get(res, ("",))[variant_idx] if variant_idx < len(VARIANT_DESC.get(res, ("",))) else ""
        mult = VARIANT_YIELD_MULT.get(res, (1.0,))[variant_idx] if variant_idx < len(VARIANT_YIELD_MULT.get(res, (1.0,))) else 1.0
        base_res, base_amount = PLATFORM_YIELD.get(res, (res, 0))
        yield_amount = int(base_amount * mult)
        unlocked = get_unlocked_variants(res)
        is_unlocked = variant_idx in unlocked

        # заголовок варианта
        c.create_text(x, y, text=_t("Вариант {0} из {1}").format(
            unlocked.index(variant_idx) + 1 if is_unlocked else "🔒",
            len(unlocked)
        ), fill=AMBER if is_unlocked else MUTED, anchor="nw", font=theme.font(11, True), tags="gallery")
        y += px(22)

        # описание
        c.create_text(x, y, text=desc, fill=TEXT, anchor="nw", width=w,
                      font=theme.font(9), tags="gallery")
        y += px(40)

        # сетка: вычисляем границы паттерна
        min_dx = min(dx for dx, _ in pattern) if pattern else -1
        max_dx = max(dx for dx, _ in pattern) if pattern else 1
        min_dy = min(dy for _, dy in pattern) if pattern else -1
        max_dy = max(dy for _, dy in pattern) if pattern else 1
        grid_w = max_dx - min_dx + 1
        grid_h = max_dy - min_dy + 1
        cell_size = min(w // max(1, grid_w + 2), h // max(1, grid_h + 2), 32)
        origin_x = x + (w - grid_w * cell_size) // 2
        origin_y = y + (h - grid_h * cell_size) // 2

        # рисуем клетки
        for dy in range(min_dy, max_dy + 1):
            for dx in range(min_dx, max_dx + 1):
                cx = origin_x + (dx - min_dx) * cell_size
                cy = origin_y + (dy - min_dy) * cell_size
                is_center = (dx == 0 and dy == 0)
                is_block = (dx, dy) in pattern

                if is_center:
                    # центр находки
                    c.create_rectangle(cx, cy, cx + cell_size, cy + cell_size,
                                       fill=SPRING if res == "water" else GREEN, outline=TEXT, width=2, tags="gallery")
                    c.create_text(cx + cell_size // 2, cy + cell_size // 2, text="●",
                                  fill=BG, anchor="center", font=theme.font(max(8, cell_size // 2)), tags="gallery")
                elif is_block:
                    # блок платформы
                    fill = AMBER if is_unlocked else MUTED
                    c.create_rectangle(cx + 1, cy + 1, cx + cell_size - 1, cy + cell_size - 1,
                                       fill=fill, outline=TEXT, width=1, tags="gallery")
                    c.create_text(cx + cell_size // 2, cy + cell_size // 2, text="█",
                                  fill=BG, anchor="center", font=theme.font(max(8, cell_size // 2)), tags="gallery")
                else:
                    # пусто
                    c.create_rectangle(cx, cy, cx + cell_size, cy + cell_size,
                                       fill=BG2, outline=LINE, tags="gallery")

        # легенда и статы под сеткой
        legend_y = origin_y + grid_h * cell_size + px(10)
        platform_h = platform_height(res, variant_idx)
        need_level = strategy.level_for_height(platform_h)
        height_ok = (self.model.developer
                     or get_language_level() >= strategy.level_index(need_level))
        stats = [
            (_t("Блоков: {0}").format(len(pattern)), CYAN),
            (f"Высота здания: h{platform_h} · нужен {need_level}", GREEN if height_ok else AMBER),
            (_t("Добыча/тик: {0} ×{1}").format(resource_name(base_res), yield_amount), GREEN),
            (_t("Множитель: {0:.0%}").format(mult), AMBER),
        ]
        if not height_ok:
            stats.insert(0, (f"🔒 Высокое здание: нужен терраформер {need_level}", MUTED))
        if not is_unlocked:
            needed_level = next(i for i, t in PROGRESSION_TIERS.items() if variant_idx in t["platform_variants"].get(res, ()))
            stats.insert(0, (_t("🔒 ЗАБЛОКИРОВАНО — нужен уровень языка {0}").format(needed_level), MUTED))
            # визуальная шкала прогресса к нужному уровню
            current_level = get_language_level()
            prog = None
            try:
                from stamina.english.progress import Progress
                from stamina import pilots
                prog = Progress(pilots.active_dir() / "english.json")
            except Exception:
                pass
            if prog:
                xp_total = prog.xp_total
                lvl, start_xp, next_xp = prog.level()
                # прогресс к нужному уровню
                target_start_xp = 50 * (needed_level - 1) ** 2 if needed_level > 0 else 0
                target_next_xp = 50 * needed_level ** 2
                if xp_total < target_next_xp:
                    pct = (xp_total - target_start_xp) / (target_next_xp - target_start_xp)
                    pct = max(0, min(1, pct))
                    bar_w = px(180)
                    bar_h = px(8)
                    bar_x = x
                    bar_y = legend_y + px(20)
                    c.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, fill=BG2, outline=LINE, tags="gallery")
                    c.create_rectangle(bar_x, bar_y, bar_x + int(bar_w * pct), bar_y + bar_h, fill=GREEN, outline="", tags="gallery")
                    c.create_text(bar_x + bar_w + px(8), bar_y + bar_h // 2,
                                  text=_t("{0}% к уровню {1}").format(int(pct * 100), needed_level),
                                  fill=AMBER, anchor="w", font=theme.font(8, True), tags="gallery")
                    legend_y += px(28)

        for text, color in stats:
            c.create_text(x, legend_y, text=text, fill=color, anchor="nw", font=theme.font(10, color != MUTED), tags="gallery")
            legend_y += px(18)

    def _draw_gallery_3d_preview(self, c: tk.Canvas, x: int, y: int, w: int, h: int) -> None:
        """Псевдо-3D изометрический превью платформы (простая проекция)."""
        res = self._gallery_resource
        variant_idx = self._gallery_variant
        variants = PLATFORM_VARIANTS.get(res, ())
        if variant_idx >= len(variants):
            variant_idx = 0
        pattern = variants[variant_idx]
        unlocked = get_unlocked_variants(res)
        is_unlocked = variant_idx in unlocked

        # заголовок
        c.create_text(x, y, text=_t("3D превью (изометрия)"), fill=AMBER, anchor="nw", font=theme.font(11, True), tags="gallery")
        y += px(20)
        platform_h = platform_height(res, variant_idx)
        need_level = strategy.level_for_height(platform_h)
        height_ok = (self.model.developer
                     or get_language_level() >= strategy.level_index(need_level))
        c.create_text(x, y, text=f"Высота здания: h{platform_h} · нужен {need_level}",
                      fill=GREEN if height_ok else AMBER, anchor="nw",
                      font=theme.font(9, True), tags="gallery")
        y += px(22)

        # изометрическая проекция: x->right-down, y->left-down, z->up
        iso_w = w * 0.9
        iso_h = h - px(50)
        cx = x + iso_w // 2
        cy = y + iso_h // 3

        # цвета по ресурсу
        res_colors = {
            "water": ("#2E9BFF", "#1A5FB4"),
            "stone": ("#888888", "#555555"),
            "organic": ("#4A7C2E", "#2E4D1A"),
            "iron": ("#A0522D", "#6B341A"),
            "quartz": ("#E8E8F0", "#B0B0C0"),
        }
        top_color, side_color = res_colors.get(res, ("#888888", "#555555"))
        if not is_unlocked:
            top_color = "#555555"
            side_color = "#333333"

        # границы паттерна
        min_dx = min(dx for dx, _ in pattern) if pattern else -1
        max_dx = max(dx for dx, _ in pattern) if pattern else 1
        min_dy = min(dy for _, dy in pattern) if pattern else -1
        max_dy = max(dy for _, dy in pattern) if pattern else 1

        cell_w = 24
        cell_h = 12
        height = 16

        # рисуем блоки в изометрии (сначала дальние, потом ближние)
        # сортируем по dy+dx для правильного порядка
        blocks = [(dx, dy) for dx, dy in pattern]
        blocks.sort(key=lambda p: p[0] + p[1])

        for dx, dy in blocks:
            # изометрические координаты
            ix = cx + (dx - dy) * cell_w // 2
            iy = cy + (dx + dy) * cell_h // 2

            # верхняя грань
            top = [
                (ix, iy - height),
                (ix + cell_w // 2, iy - height + cell_h // 2),
                (ix, iy - height + cell_h),
                (ix - cell_w // 2, iy - height + cell_h // 2),
            ]
            c.create_polygon([c for p in top for c in p], fill=top_color, outline=TEXT, width=1, tags="gallery")

            # правая грань
            right = [
                (ix + cell_w // 2, iy - height + cell_h // 2),
                (ix + cell_w // 2, iy + cell_h // 2),
                (ix, iy + cell_h),
                (ix, iy - height + cell_h),
            ]
            c.create_polygon([c for p in right for c in p], fill=side_color, outline="", tags="gallery")

            # левая грань
            left = [
                (ix - cell_w // 2, iy - height + cell_h // 2),
                (ix - cell_w // 2, iy + cell_h // 2),
                (ix, iy + cell_h),
                (ix, iy - height + cell_h),
            ]
            darker = "#" + "".join(f"{max(0, int(c, 16) - 30):02x}" for c in (side_color[1:3], side_color[3:5], side_color[5:7]))
            c.create_polygon([c for p in left for c in p], fill=darker, outline="", tags="gallery")

        # центр находки
        ix = cx
        iy = cy
        center_top = [
            (ix, iy - height),
            (ix + cell_w // 2, iy - height + cell_h // 2),
            (ix, iy - height + cell_h),
            (ix - cell_w // 2, iy - height + cell_h // 2),
        ]
        center_color = SPRING if res == "water" else GREEN
        c.create_polygon([c for p in center_top for c in p], fill=center_color, outline=TEXT, width=2, tags="gallery")

        # легенда
        legend_y = y + iso_h - px(60)
        if not is_unlocked:
            c.create_text(x, legend_y, text=_t("🔒 Разблокируется на уровне языка..."), fill=MUTED, anchor="nw", font=theme.font(10, True), tags="gallery")
        elif not height_ok:
            c.create_text(x, legend_y, text=f"🔒 Нужен терраформер {need_level}", fill=MUTED, anchor="nw", font=theme.font(10, True), tags="gallery")
        else:
            c.create_text(x, legend_y, text=_t("Доступно для строительства"), fill=GREEN, anchor="nw", font=theme.font(10, True), tags="gallery")

    # -- изометрическая отрисовка -------------------------------------------------
    def _draw_iso(self, w: int, h: int) -> None:
        """Отрисовка карты в изометрической проекции."""
        c = self.canvas
        model = self.model
        cam = self.camera

        # вычисляем метрики тайла для текущего зума
        m = iso.tile_metrics(self._iso_zoom, w, h, cam)

        # видимые клетки с запасом
        min_gx, min_gy, max_gx, max_gy = iso.visible_cell_bounds(m, model.w, model.h, w, h)

        explored = model.explored
        visible = model.visible_cells()

        # цвета слоев (как в плоском виде)
        layer_colors = [SOIL, CLAY, METAL, DUG_OUT]

        # рисуем тайлы: сначала дальние (y + x), потом ближние
        # порядок: по диагоналям от левого-верхнего к правому-нижнему
        for depth_sum in range(min_gx + min_gy, max_gx + max_gy + 1):
            for gy in range(min_gy, max_gy + 1):
                gx = depth_sum - gy
                if not (min_gx <= gx <= max_gx):
                    continue
                if (gx, gy) not in explored:
                    continue

                gz = model.dug[gy][gx]
                poly = iso.tile_polygon(gx, gy, gz, m)

                # цвет по глубине
                color = layer_colors[min(gz, len(layer_colors) - 1)]
                if (gx, gy) not in visible:
                    color = blend(color, BG, 0.62)

                c.create_polygon(*poly, fill=color, outline=blend(color, BG2, 0.45), tags="map")

        # открытые находки
        for (x, y) in model.revealed:
            if not (min_gx <= x <= max_gx and min_gy <= y <= max_gy):
                continue
            res = model.finds[(x, y)][0]
            # центр верхней грани тайла
            cx, cy = iso.world_to_screen(x + 0.5, y + 0.5, model.dug[y][x] + 1, m)
            if res == "water":
                r = m.hw * 0.35
                c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SPRING, outline=TEXT, width=1, tags="map")
            else:
                r = m.hw * 0.2
                c.create_polygon(cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy,
                                 fill=GREEN, outline="", tags="map")

        # стройплощадка
        for x, y in model.site_cells():
            if not (min_gx <= x <= max_gx and min_gy <= y <= max_gy):
                continue
            poly = iso.tile_polygon(x, y, model.dug[y][x], m)
            c.create_polygon(*poly, outline=AMBER, dash=(3, 3), width=1, fill="", tags="map")

        # блоки (фундамент + платформы)
        block_fill = blend(AMBER, TEXT, 0.25)
        for x, y in model.blocks:
            if not (min_gx <= x <= max_gx and min_gy <= y <= max_gy):
                continue
            poly = iso.tile_polygon(x, y, model.dug[y][x] + 1, m)
            c.create_polygon(*poly, fill=block_fill, outline=AMBER, width=2, tags="map")
        for x, y in model.platform_blocks:
            if not (min_gx <= x <= max_gx and min_gy <= y <= max_gy):
                continue
            poly = iso.tile_polygon(x, y, model.dug[y][x] + 1, m)
            c.create_polygon(*poly, fill=block_fill, outline=AMBER, width=2, tags="map")

        # граница поля (рамка из 4-х углов карты)
        corners = [
            iso.world_to_screen(0, 0, 0, m),
            iso.world_to_screen(model.w, 0, 0, m),
            iso.world_to_screen(model.w, model.h, 0, m),
            iso.world_to_screen(0, model.h, 0, m),
        ]
        flat = [c for p in corners for c in p]
        c.create_polygon(*flat, outline=LINE, width=2, fill="", tags="map")

        # здания, червь, отряд
        self._draw_buildings_iso(w, h, m)
        self._draw_worm_iso(w, h, m)
        self._draw_units_iso(w, h, m)

        # HUD (переиспользуем существующий код панели)
        self._draw_hud(w, h, m)

    def _draw_buildings_iso(self, w: int, h: int, m: iso.TileMetrics) -> None:
        """Здания в изометрии: объём вверх."""
        c = self.canvas
        model = self.model
        for b in model.buildings:
            cx, cy = iso.world_to_screen(b.center[0] + 0.5, b.center[1] + 0.5, model.dug[b.center[1]][b.center[0]] + 1, m)
            # проверка видимости
            if cx < -m.hw * 4 or cy < -m.hh * 8 or cx > w + m.hw or cy > h + m.hh:
                continue
            spec = strategy.STRUCTURES.get(b.type)
            color = GREEN if b.built else MUTED
            rise = m.hh * 0.8 * max(1, b.height)
            # основание
            base_poly = iso.tile_polygon(b.center[0], b.center[1], model.dug[b.center[1]][b.center[0]] + 1, m)
            c.create_polygon(*base_poly, fill=blend(color, BG, 0.55), outline=color, width=1, tags="building")
            # объём вверх (прямоугольник от центра базы)
            top_y = cy - rise
            c.create_rectangle(cx - m.hw * 0.3, top_y, cx + m.hw * 0.3, cy - m.hh * 0.2,
                               fill=color, outline=blend(color, TEXT, 0.4), tags="building")
            c.create_text(cx, cy - m.hh * 0.35, text=f"h{b.height}", fill=BG, tags="building",
                          font=theme.font(max(6, int(m.hw * 0.15)), True))
            if b.connected:
                best = None
                for other in model.buildings + [None]:
                    ox, oy = (other.center if other is not None else model.site[:2])
                    if (ox, oy) == tuple(b.center):
                        continue
                    d = abs(ox - b.center[0]) + abs(oy - b.center[1])
                    if best is None or d < best[0]:
                        best = (d, ox, oy)
                if best:
                    ox, oy = iso.world_to_screen(best[1] + 0.5, best[2] + 0.5,
                                                  model.dug[best[2]][best[1]] + 1, m)
                    c.create_line(cx, cy - m.hh * 0.3, ox, oy - m.hh * 0.3,
                                  fill=blend(GREEN, BG, 0.35), width=1, dash=(1, 3), tags="building")

    def _draw_worm_iso(self, w: int, h: int, m: iso.TileMetrics) -> None:
        """След червя и червь в изометрии."""
        c = self.canvas
        worm = self.model.worm
        if not worm.alive:
            return
        for (x, y), ttl in worm.trail.items():
            if not self.model.is_explored(x, y):
                continue
            cx, cy = iso.world_to_screen(x + 0.5, y + 0.5, self.model.dug[y][x] + 1, m)
            fade = max(0.15, min(1.0, ttl / max(1, strategy.WORM_TRAIL_TTL)))
            r = m.hw * 0.35
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill=blend("#C79A4A", BG, 1.0 - fade), outline="", tags="worm")
        cx, cy = iso.world_to_screen(worm.x + 0.5, worm.y + 0.5, self.model.dug[worm.y][worm.x] + 1, m)
        r = m.hw * 0.4
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=blend("#C79A4A", BG, 0.25), outline=AMBER, width=2, tags="worm")
        c.create_text(cx, cy, text="≈", fill=BG, tags="worm",
                      font=theme.font(max(8, int(m.hw * 0.3)), True))

    def _draw_units_iso(self, w: int, h: int, m: iso.TileMetrics) -> None:
        """Отряд в изометрии."""
        c = self.canvas
        for u in self.model.units:
            cx, cy = iso.world_to_screen(u.x + 0.5, u.y + 0.5, self.model.dug[u.y][u.x] + 1, m)
            body = m.hw * 0.55
            color = self._unit_color(u.level)
            if u.uid in self.model.selected:
                r = m.hw * 0.6
                c.create_oval(cx - r, cy - r, cx + r, cy + r,
                              outline=GREEN, width=max(2, int(m.hw * 0.1)), tags="unit")
            track_w = max(2.0, m.hw * 0.18)
            c.create_rectangle(cx - m.hw * 0.15, cy - m.hh * 0.3,
                               cx - m.hw * 0.15 + track_w, cy + m.hh * 0.3,
                               fill=MUTED, outline="", tags="unit")
            c.create_rectangle(cx + m.hw * 0.15 - track_w, cy - m.hh * 0.3,
                               cx + m.hw * 0.15, cy + m.hh * 0.3,
                               fill=MUTED, outline="", tags="unit")
            c.create_rectangle(cx - body / 2, cy - body / 2, cx + body / 2, cy + body / 2,
                               fill=color, outline=blend(color, TEXT, 0.35), tags="unit")
            label = u.level if len(u.level) <= 4 else u.level[:4]
            c.create_text(cx, cy, text=label, fill=BG, tags="unit",
                          font=theme.font(max(6, int(m.hw * 0.2)), True, mono=True))
            if u.hp < 100:
                bar_w = m.hw * 0.7
                x0 = cx - bar_w / 2
                y0 = cy + m.hh * 0.4
                c.create_rectangle(x0, y0, x0 + bar_w, y0 + max(2, m.hh * 0.1),
                                   fill=BG, outline="", tags="unit")
                c.create_rectangle(x0, y0, x0 + bar_w * max(0, u.hp) / 100.0,
                                   y0 + max(2, m.hh * 0.1), fill=GREEN if u.hp > 40 else AMBER,
                                   outline="", tags="unit")
            if u.uid == self.model.main_unit.uid:
                fx, fy = self.model.facing
                c.create_line(cx, cy, cx + fx * m.hw * 0.5, cy + fy * m.hh * 0.5,
                              fill=AMBER, width=max(2, int(m.hw * 0.15)), arrow="last",
                              tags="unit")
            if u.path:
                points = [cx, cy]
                for px_, py_ in u.path[::max(1, len(u.path) // 8)]:
                    ax, ay = iso.world_to_screen(px_ + 0.5, py_ + 0.5,
                                                  self.model.dug[py_][px_] + 1, m)
                    points += [ax, ay]
                if u.target:
                    ax, ay = iso.world_to_screen(u.target[0] + 0.5, u.target[1] + 0.5,
                                                  self.model.dug[u.target[1]][u.target[0]] + 1, m)
                    points += [ax, ay]
                if len(points) >= 4:
                    c.create_line(*points, fill=color, width=1, dash=(2, 4), tags="unit")

    def _draw_hud(self, w: int, h: int, m: iso.TileMetrics) -> None:
        """HUD панель (верхняя левая) — как в плоском виде."""
        c = self.canvas
        model = self.model
        found = sum(model.finds_count.values())
        bg_id = c.create_rectangle(0, 0, px(230), px(8), fill=BG, outline=LINE)
        ty = px(8)
        level_name = model.standing.current_level
        lines = (
            (_t("Учебная смена / тренажёр"), TEXT, True),
            (f"Уровень {level_name} · высота до {model.max_build_height}", AMBER, True),
            (_t("Грунт {0}/{1}").format(model.holds.get("soil", 0), HOLD_CAP), MUTED, False),
            (_t("Фундамент {0}/{1}").format(*model.progress()), MUTED, False),
            (_t("Находки {0}").format(found), MUTED, False),
            (f"Кредиты {model.credits}", GREEN, False),
            (f"Отряд {len(model.units)}", MUTED, False),
            (_t("Масштаб {0}%").format(int(round(self._iso_zoom * 100))), MUTED, False),
        )
        for text, color, bold in lines:
            c.create_text(px(10), ty, text=text, fill=color, anchor="nw",
                          font=theme.font(10, bold))
            ty += px(16)

        book = model.mission_book
        done = book.done_count()
        total = len(book.missions)
        mark = " ●" if book.unread else ""
        c.create_text(px(10), ty, text=f"ЗАДАНИЯ {done}/{total}{mark}",
                      fill=GREEN if done else MUTED, anchor="nw", font=theme.font(9, True))
        ty += px(15)
        if model.holds.get(strategy.SPICE, 0):
            c.create_text(px(10), ty, text=f"Специя {model.holds.get(strategy.SPICE, 0)}",
                          fill=AMBER, anchor="nw", font=theme.font(9, True))
            ty += px(14)

        active_platforms = [p for p in model.platforms if not p.complete]
        if active_platforms:
            ty += px(4)
            c.create_text(px(10), ty, text=_t("ПЛАТФОРМЫ:"), fill=CYAN, anchor="nw",
                          font=theme.font(9, True))
            ty += px(14)
            for p in active_platforms[:3]:
                prio_mark = " ★" if p.priority > 0 else ""
                pct = p.progress_pct()
                fill = GREEN if pct == 100 else AMBER if pct > 0 else MUTED
                c.create_text(px(10), ty,
                              text=f"{resource_name(p.resource)[:10]} {pct}% · h{p.height}{prio_mark}",
                              fill=fill, anchor="nw", font=theme.font(8))
                ty += px(13)

        if model.walls_open:
            c.create_text(px(10), ty, text=_t("СТЕНЫ ОТКРЫТЫ"), fill=GREEN, anchor="nw",
                          font=theme.font(11, True))
            ty += px(16)

        ty = self._draw_language_progress_bar(w, h, ty + px(10))
        c.coords(bg_id, 0, 0, px(230), ty)

    def _draw_overlays(self, w: int, h: int) -> None:
        """Оверлеи (подсказка, тост, модальные окна) — общие для обоих видов."""
        c = self.canvas
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
        elif self.overlay == "gallery":
            self._draw_gallery(w, h)
        elif self.overlay == "missions":
            self._draw_missions(w, h)
        elif self.overlay == "structures":
            self._draw_structures(w, h)
        elif self.paused:
            self.draw_overlay(_t("ПАУЗА"))
