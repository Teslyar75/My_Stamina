#!/usr/bin/env python3
"""Запуск Star Typing (бывший Stamina). Точка входа для ярлыка — не переименовывать."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Сначала проверка среды, потом окно.

    Проверка нужна, чтобы «программа не запускается» не выглядело как молчание:
    без tkinter или без экрана человек получает объяснение и окно с причиной.
    ``--check`` печатает отчёт о среде и выходит (для поддержки: ``./run.sh --check``).
    """
    args = sys.argv[1:] if argv is None else list(argv)
    from stamina import launch_check

    if "--check" in args:
        lines = launch_check.report()
        launch_check.write_log("\n".join(lines))
        text = "\n".join(lines)
        try:
            print(text)
        except Exception:  # noqa: BLE001 — под pythonw печатать некуда
            pass
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
