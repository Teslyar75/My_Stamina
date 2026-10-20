"""Запуск кабины без окон входа и кода (для работы с агентом).

Запускать: pythonw.exe D:\\My_New_Stamina\\_bypass.py
Рабочая папка значения не имеет — путь к проекту берётся из расположения файла.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stamina import pilot_screens

pilot_screens.ask_pin = lambda *a, **k: True

from stamina import app

app.run_app(["--pilot", "p-20261009-4fa9"])
