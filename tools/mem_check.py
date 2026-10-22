"""Кто сколько ест памяти: python/pythonw по PID, рабочий набор и приватные байты.

    python tools\\mem_check.py            # один снимок
    python tools\\mem_check.py --watch 30 --count 5

«Рабочий набор» (working set) — то, что реально лежит в физической памяти сейчас.
«Приватные» (private bytes) — сколько памяти процесс зарезервировал под себя;
большая разница означает «зарезервировано, но выгружено на диск».
"""
from __future__ import annotations

import subprocess
import sys
import time

PS = (
    "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
    "ForEach-Object { $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; "
    "'{0}|{1:HH:mm:ss}|{2}|{3}|{4}' -f $_.ProcessId, $_.CreationDate, "
    "[math]::Round($p.WorkingSet64/1MB), [math]::Round($p.PrivateMemorySize64/1MB), "
    "($_.CommandLine -replace '.*python(w)?\\.exe\"?\\s*','') }"
)


def snapshot() -> str:
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        return (done.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"(ошибка: {exc})"


def show() -> None:
    rows = [line.split("|") for line in snapshot().splitlines() if line.count("|") >= 4]
    work = priv = 0
    print(f"{'PID':>6}  {'старт':>8}  {'рабочий':>9}  {'приват':>8}  кто")
    for pid, started, w, p, cmd in (rows or []):
        work += int(w or 0)
        priv += int(p or 0)
        print(f"{pid:>6}  {started:>8}  {w + ' МБ':>9}  {p + ' МБ':>8}  {cmd.strip()[:70]}")
    print(f"{'':>6}  {'':>8}  {str(work) + ' МБ':>9}  {str(priv) + ' МБ':>8}  всего")


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    wait = 0.0
    count = 1
    if "--watch" in argv:
        wait = float(argv[argv.index("--watch") + 1])
    if "--count" in argv:
        count = max(1, int(argv[argv.index("--count") + 1]))
    for i in range(count):
        if i:
            time.sleep(wait)
        print(f"\n=== {time.strftime('%H:%M:%S')} ===")
        show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
