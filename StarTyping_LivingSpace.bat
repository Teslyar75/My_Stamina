@echo off
rem Прототип «Живой космос» (ветка feature/living-space) — отдельно от основной установки.
rem Данные — в отдельной папке %APPDATA%\StaminaLivingSpace (основной прогресс не трогается).
set "APPDATA=%APPDATA%\StaminaLivingSpace"
if not exist "%APPDATA%" mkdir "%APPDATA%"
cd /d D:\My_New_Stamina_living_space
start "" pythonw main.py
