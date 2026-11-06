#!/usr/bin/env python3
"""Запуск Star Typing (бывший Stamina). Точка входа для ярлыка — не переименовывать."""

from __future__ import annotations

import sys


def _print(text: str) -> None:
    """Напечатать отчёт, не падая на кодировке консоли.

    В cmd с cp1252/cp866 кириллица не влезает в поток и ``print`` бросает
    UnicodeEncodeError — раньше его глотал ``except``, и ``--check > файл``
    давал пустой файл. Теперь символы, которых нет в кодировке, заменяются.
    """
    try:
        if sys.stdout is None:      # под pythonw печатать некуда
            return
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001 — поток без reconfigure
            pass
        print(text)
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    """Сначала проверка среды, потом окно.

    Проверка нужна, чтобы «программа не запускается» не выглядело как молчание:
    без tkinter или без экрана человек получает объяснение и окно с причиной.
    ``--check`` печатает отчёт о среде и выходит (для поддержки: ``./run.sh --check``).
    """
    args = sys.argv[1:] if argv is None else list(argv)
    from stamina import launch_check

    # Python 3.13.0 + .venv на Windows не находит Tcl (CPython gh-125235):
    # подставляем каталог из базовой установки, пока пилот не обновил Python.
    launch_check.repair_tcl_env()

    if "--check" in args:
        lines = launch_check.report()
        launch_check.write_log("\n".join(lines))
        _print("\n".join(lines))
        # окно не показываем: проверку запускают из терминала, а модальное окно
        # ждало бы нажатия и выглядело бы как зависание
        return 0

    if not launch_check.preflight():
        return 2

    from stamina.app import run_app

    run_app(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
