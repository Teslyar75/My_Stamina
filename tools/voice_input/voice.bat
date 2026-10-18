@echo off
rem Голосовой ввод (Vosk): речь -> текст в буфер обмена. См. README.md
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
set "PY=%HERE%..\..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%HERE%voice_input.py" %*
if errorlevel 1 pause
endlocal
