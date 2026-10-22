"""Что запущено на борту до старта корабля: время, python-процессы, автозапуск.

Запускать после перезагрузки, ДО запуска Star Typing:

    python tools\\boot_check.py

Пишет отчёт в %TEMP%\\opencode\\boot_check_<дата-время>.txt и печатает его же.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

OUT_DIR = Path(os.environ.get("TEMP", ".")) / "opencode"


def ps(command: str) -> str:
    """Один запрос к PowerShell; ошибки не валят отчёт."""
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        return (done.stdout or "").strip() or "(пусто)"
    except Exception as exc:  # noqa: BLE001
        return f"(ошибка: {exc})"


def main() -> int:
    try:                                     # консоль Windows часто в cp1251
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    now = datetime.now()
    boot = ps("(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')")
    procs = ps(
        "Get-Process python,pythonw -ErrorAction SilentlyContinue | "
        "ForEach-Object { '{0} | {1} | {2} | {3}' -f $_.Id, $_.ProcessName, "
        "$_.StartTime.ToString('HH:mm:ss'), $_.Path }"
    )
    startup_user = ps(
        "$p=[Environment]::GetFolderPath('Startup'); "
        "Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }"
    )
    run_hkcu = ps("reg query 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' 2>$null")
    ship_log = Path(os.environ.get("APPDATA", "")) / "Stamina" / "startup_out.log"
    log_tail = "(нет файла)"
    if ship_log.is_file():
        try:
            lines = ship_log.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = "\n".join(lines[-15:]) or "(пусто)"
            log_tail = f"{ship_log} (изменён {datetime.fromtimestamp(ship_log.stat().st_mtime):%Y-%m-%d %H:%M:%S})\n{log_tail}"
        except OSError as exc:
            log_tail = f"(не прочитать: {exc})"

    report = "\n".join([
        "=== BOOT CHECK ===",
        f"сейчас:        {now:%Y-%m-%d %H:%M:%S}",
        f"загрузка ОС:   {boot}",
        "",
        "--- процессы python/pythonw ---",
        procs,
        "",
        "--- автозапуск пользователя (папка) ---",
        startup_user,
        "",
        "--- автозапуск пользователя (реестр) ---",
        run_hkcu,
        "",
        "--- журнал запуска корабля ---",
        log_tail,
        "",
        f"корабль запущен? {'ДА' if 'pythonw' in procs.lower() and 'main.py' in procs.lower() else 'НЕТ (pythonw с main.py не видно)'}",
    ])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"boot_check_{now:%Y%m%d-%H%M%S}.txt"
    out.write_text(report, encoding="utf-8-sig")
    print(report)
    print(f"\nсохранено: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
