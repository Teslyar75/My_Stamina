@echo off
REM Демо-режим Лаборатории: созвездия из искусственных данных, плашка «ДЕМО-ДАННЫЕ».
REM Файлы пилота не читаются и не пишутся. Для скриншотов и замеров FPS.
cd /d "%~dp0"
set STAMINA_LAB_DEMO=1
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" main.py
) else (
  py -3 main.py 2>nul || python main.py
)
