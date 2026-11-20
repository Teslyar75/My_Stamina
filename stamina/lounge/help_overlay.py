"""Общий оверлей справки Lounge: три раздела, кнопка «?», F1, пауза пока открыт."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import TYPE_CHECKING

from stamina import theme
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, TEXT, px

from stamina.lounge.help_texts import load_help, load_overview

if TYPE_CHECKING:
    from stamina.lounge.base import GameShell

TAG = "help_overlay"
TAG_SWITCH = "help_overlay_switch"


def format_help_body(data: dict | None) -> str:
    """Собрать текст трёх разделов: цель+шаги, зачем, интерфейс."""
    data = data or {}
    goal = str(data.get("goal") or "").strip()
    steps = data.get("steps") or []
    if isinstance(steps, str):
        steps = [steps]
    step_lines = []
    for i, item in enumerate(steps, 1):
        s = str(item).strip()
        if s:
            step_lines.append(f"{i}. {s}")
    first = "\n".join(x for x in (goal, "\n".join(step_lines)) if x)
    purpose = str(data.get("purpose") or data.get("why") or "").strip()
    interface = str(data.get("interface") or data.get("ui") or "").strip()
    blocks = [
        (_t("Что нужно сделать"), first),
        (_t("Зачем эта игра"), purpose),
        (_t("Интерфейс"), interface),
    ]
    out: list[str] = []
    for head, body in blocks:
        if not body:
            continue
        out.append(f"{head}\n{body}")
    return "\n\n".join(out)


def format_help_block(data: dict | None, heading: str | None = None) -> str:
    """Блок справки с заголовком (для Orion / page_help)."""
    data = data or {}
    title = str(data.get("title") or "").strip()
    cap = heading or ""
    if cap and title:
        cap = f"{cap} · {title}"
    elif title:
        cap = title
    body = format_help_body(data)
    if cap and body:
        return f"{cap}\n\n{body}"
    return cap or body


class HelpOverlay:
    """Модальная справка поверх canvas GameShell.

    Тексты берутся из help_texts/<game>.json (поля goal / purpose / interface / steps).
    Escape не вешается через bind_all — закрытие идёт через handle_help_keys оболочки.
    """

    def __init__(self, shell: "GameShell") -> None:
        self.shell = shell
        self._visible = False
        self._overview = False
        self._paused_by_us = False
        self._bound = False

    def is_visible(self) -> bool:
        return self._visible

    def showing_overview(self) -> bool:
        return self._overview

    def toggle(self, overview: bool = False) -> bool:
        if self._visible:
            if overview and not self._overview:
                self._overview = True
                self.shell.redraw()
                return True
            self.hide()
        else:
            self.show(overview=overview)
        return True

    def show(self, overview: bool = False) -> None:
        self._overview = overview
        if self._visible:
            self.shell.redraw()
            return
        self._visible = True
        self._paused_by_us = False
        if not self.shell.paused and not self.shell.over:
            self._paused_by_us = True
            self.shell.toggle_pause()
        else:
            self.shell.redraw()

    def hide(self) -> None:
        if not self._visible:
            return
        self._visible = False
        self._overview = False
        unpause = self._paused_by_us and self.shell.paused and not self.shell.over
        self._paused_by_us = False
        if unpause:
            self.shell.toggle_pause()
        else:
            self.shell.redraw()

    def current_data(self) -> dict:
        game = self.shell.help_game_id()
        if self._overview:
            data = load_overview(game) or {}
        else:
            data = load_help(game, self.shell.help_level_id()) or {}
        return data

    def draw(self) -> None:
        if not self._visible:
            return
        c = self.shell.canvas
        try:
            c.delete(TAG)
        except tk.TclError:
            return
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 10)

        c.create_rectangle(0, 0, w, h, fill=BG, stipple="gray50", outline="", tags=TAG)

        panel_w = min(w - px(40), px(760))
        panel_h = min(h - px(40), px(560))
        x0 = (w - panel_w) // 2
        y0 = (h - panel_h) // 2

        c.create_rectangle(x0, y0, x0 + panel_w, y0 + panel_h, fill=PANEL, outline=AMBER, width=2, tags=TAG)
        c.create_rectangle(x0, y0, x0 + panel_w, y0 + px(36), fill=AMBER, outline="", tags=TAG)

        data = self.current_data()
        title = str((data or {}).get("title") or self.shell.title or _t("ПОМОЩЬ"))
        c.create_text(
            w // 2, y0 + px(18), text=title, fill=BG, anchor="center",
            font=theme.font(14, True), tags=TAG,
        )

        body = format_help_body(data) or _t("Справка для этого уровня пока не заполнена.")
        content_w = panel_w - px(32)
        c.create_text(
            x0 + px(16), y0 + px(48), text=body, fill=TEXT, anchor="nw",
            font=theme.font(10), width=content_w, tags=TAG,
        )

        foot_y = y0 + panel_h - px(14)
        c.create_text(
            x0 + px(16), foot_y, text=_t("F1 или Esc — закрыть"),
            fill=MUTED, anchor="sw", font=theme.font(10, True), tags=TAG,
        )
        switch = _t("К уровню") if self._overview else _t("Обзор")
        c.create_text(
            x0 + panel_w - px(16), foot_y, text=switch,
            fill=CYAN, anchor="se", font=theme.font(10, True), tags=(TAG, TAG_SWITCH),
        )
        self._ensure_binds()

    def _ensure_binds(self) -> None:
        if self._bound:
            return
        c = self.shell.canvas
        c.tag_bind(TAG_SWITCH, "<Button-1>", self._on_switch)
        self._bound = True

    def _on_switch(self, _e: tk.Event | None = None) -> str:
        if not self._visible:
            return "break"
        # «К уровню» имеет смысл только если есть текущий уровень
        if self._overview and not self.shell.help_level_id():
            return "break"
        self._overview = not self._overview
        self.shell.redraw()
        return "break"
