"""Сборка мусора только в главном потоке (Linux).

Фоновые потоки (разбор книг, озвучка) могут запустить сборщик мусора, и тот
удалит циклические объекты Tk (PhotoImage, переменные, окна) не в том потоке —
Tcl на Linux падает с «Illegal instruction». Поэтому автоматический сборщик
выключаем и собираем мусор сами по таймеру Tk: поколение 0 — раз в секунду,
1 — раз в 10 с, полный — раз в минуту.
"""
from __future__ import annotations

import gc
import sys

_installed = False


def install(root, *, force: bool = False) -> bool:
    global _installed
    if _installed or (sys.platform == "win32" and not force):
        return False
    _installed = True
    gc.disable()
    tick = [0]

    def step() -> None:
        tick[0] += 1
        gen = 2 if tick[0] % 60 == 0 else 1 if tick[0] % 10 == 0 else 0
        gc.collect(gen)
        try:
            root.after(1000, step)
        except Exception:  # noqa: BLE001 — окно закрыто: сборщик возвращаем
            uninstall()

    root.after(1000, step)
    return True


def uninstall() -> None:
    global _installed
    _installed = False
    gc.enable()
