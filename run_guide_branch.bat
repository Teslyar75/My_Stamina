@echo off
rem Star Typing - guide branch, local run (offline)
cd /d %~dp0
if exist .venv\Scripts\pythonw.exe (start "" .venv\Scripts\pythonw.exe main.py) else (start "" pythonw main.py)
rem Edit stamina\guide_content\ru.json, then rebuild voice: python tools\guide_voice\build.py
