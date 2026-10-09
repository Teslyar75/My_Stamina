@echo off
rem Star Typing - установка в один клик для Windows.
rem Делает всё сам: Python (через winget, если его нет) -> папка .venv -> пакеты -> ярлык -> запуск.
rem Для проверок: STAMINA_PYTHON=путь\python.exe, STAMINA_NO_SHORTCUT=1, STAMINA_NO_LAUNCH=1.
chcp 65001 >nul
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo.
echo  ===================  STAR TYPING - УСТАНОВКА  ===================
echo.

call :find_python
if defined PYEXE goto :have_python
echo  [1/5] Python 3.10+ не найден - ставлю Python 3.12 через winget...
where winget >nul 2>&1
if errorlevel 1 goto :no_winget
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :find_python
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    set "PYARGS="
)
if defined PYEXE goto :have_python
:no_winget
echo.
echo  [!] Не получилось поставить Python автоматически.
echo      Скачайте Python 3.10+ с https://www.python.org/downloads/
echo      и в установщике поставьте галочку "Add python.exe to PATH".
echo      Потом снова дважды щёлкните install.bat.
start "" https://www.python.org/downloads/
pause
exit /b 1

:have_python
echo  [1/5] Python:
"%PYEXE%" %PYARGS% --version

echo  [2/5] Папка программы .venv ...
if not exist "%ROOT%.venv\Scripts\python.exe" "%PYEXE%" %PYARGS% -m venv "%ROOT%.venv"
set "VPY=%ROOT%.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo  [!] Не удалось создать .venv - ставлю пакеты в общий Python.
    set "VPY=%PYEXE%"
)

echo  [3/5] Пакеты: Pillow, pypdf ...
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt"
if errorlevel 1 echo  [!] pip не смог поставить пакеты - проверьте интернет. Программа запустится и без них.

echo.
echo  Проверка произношения в АНГЛИЙСКОМ: микрофон, vosk, модель ~40 МБ.
choice /C YN /T 20 /D N /M " Установить её тоже (через 20 с - нет)"
if errorlevel 2 goto :shortcut
echo  [4/5] vosk + sounddevice + модель речи ...
"%VPY%" -m pip install --disable-pip-version-check -q vosk sounddevice
"%VPY%" "%ROOT%scripts\download_vosk_model.py"

:shortcut
echo  [5/5] Ярлык "Star Typing" на рабочем столе ...
if defined STAMINA_NO_SHORTCUT goto :done_shortcut
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%create_shortcut.ps1"
:done_shortcut
echo done> "%ROOT%.first_run_done"
echo.
echo  Готово! Запускаю Star Typing. Дальше - ярлык на рабочем столе.
if not defined STAMINA_NO_LAUNCH call "%ROOT%Stamina.bat"
timeout /t 3 >nul
endlocal
exit /b 0

:find_python
set "PYEXE="
set "PYARGS="
if defined STAMINA_PYTHON (
    set "PYEXE=%STAMINA_PYTHON%"
    exit /b 0
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=py"
    set "PYARGS=-3"
    exit /b 0
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PYEXE=python"
exit /b 0
