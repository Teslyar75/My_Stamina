@echo off
rem ──────────────────────────────────────────────────────────────
rem  Stamina — тренажёр печати. Двойной клик запускает программу
rem  без чёрного окна консоли (используется pythonw.exe).
rem ──────────────────────────────────────────────────────────────
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

where pythonw.exe >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw.exe "%ROOT%main.py"
) else (
    rem fallback на python.exe, если pythonw не найден
    start "" python.exe "%ROOT%main.py"
)
endlocal
