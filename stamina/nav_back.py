"""Глобальная навигация «назад» по Backspace: стек экранов и подпанелей.

Backspace возвращает на предыдущий экран или закрывает подпанель.
Не срабатывает, пока клавиша стирает текст (Entry/Text, тренажёр набора,
поле сканера, чат). На корневом экране — ничего не делает.
"""
from __future__ import annotations

from dataclasses import dataclass

from stamina.hotkeys import typing_in

LIMIT = 32
# Ctrl; Alt на Windows — расширенный бит 0x20000.
_CTRL = 0x4
_ALT_WIN = 0x20000


@dataclass(frozen=True)
class Place:
    """Точка в навигации: отсек и, если нужно, вкладка/язык/подпанель."""

    screen: str
    sub: str = ""
    lang: str = ""
    extra: str = ""


class BackStack:
    """История мест. Первый arrive только запоминает «здесь», без выталкивания."""

    def __init__(self, limit: int = LIMIT) -> None:
        self.limit = limit
        self._stack: list[Place] = []
        self.here: Place | None = None

    def arrive(self, place: Place) -> None:
        if self.here is None:
            self.here = place
            return
        if place == self.here:
            return
        self._stack.append(self.here)
        if len(self._stack) > self.limit:
            self._stack = self._stack[-self.limit :]
        self.here = place

    def back(self) -> Place | None:
        if not self._stack:
            return None
        self.here = self._stack.pop()
        return self.here

    def empty(self) -> bool:
        return not self._stack


def is_back_key(event) -> bool:
    """Чистый Backspace, без Ctrl/Alt (те не должны уводить с экрана)."""
    ks = getattr(event, "keysym", "") or ""
    if ks not in ("BackSpace", "Backspace"):
        return False
    state = int(getattr(event, "state", 0) or 0)
    if state & _CTRL:
        return False
    if state & _ALT_WIN:
        return False
    return True


def screen_edits_text(app) -> bool:
    """Экран сам просит Backspace для правки текста.

    Нужно играм с вводом на холсте (Docker-тренажёр): там нет Entry, поэтому
    ``typing_in`` его не видит, а Backspace уводил бы из игры в лобби.
    Экран отвечает методом/флагом ``backspace_edits``; нет ответа — навигация
    работает как раньше, во всех прочих отсеках ничего не меняется.
    """
    screens = getattr(app, "screens", None)
    if not isinstance(screens, dict):
        return False
    scr = screens.get(getattr(app, "current", None))
    if scr is None:
        return False
    hook = getattr(scr, "backspace_edits", None)
    if hook is None:
        return False
    try:
        return bool(hook() if callable(hook) else hook)
    except Exception:  # noqa: BLE001
        return False


def backspace_edits_text(app, event) -> bool:
    """True, если Backspace должен править текст, а не менять экран."""
    widget = getattr(event, "widget", None)
    if typing_in(widget):
        return True
    if screen_edits_text(app):
        return True
    zen = getattr(app, "zen", None)
    if zen is not None and getattr(zen, "on", False):
        return True
    if getattr(app, "current", None) == "bridge":
        screens = getattr(app, "screens", None) or {}
        br = screens.get("bridge") if isinstance(screens, dict) else None
        if br is not None and getattr(br, "state", None) in ("run", "ready"):
            return True
    return False


def snapshot_screen(name: str, scr) -> Place:
    """Снимок текущего отсека: свой snapshot_place или screen + вкладка."""
    custom = getattr(scr, "snapshot_place", None)
    if callable(custom):
        place = custom()
        if place is not None:
            return place
    sub = ""
    if scr is not None:
        tab = getattr(scr, "current_tab", None)
        if isinstance(tab, str):
            sub = tab
        else:
            cur = getattr(scr, "current", None)
            if isinstance(cur, str):
                sub = cur
    return Place(screen=name, sub=sub)


def notify(app) -> None:
    """Сообщить пульту, что вкладка или подстраница сменилась (не из go_back)."""
    rec = getattr(app, "record_place", None)
    if callable(rec):
        rec()
