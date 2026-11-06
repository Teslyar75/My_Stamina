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

rem Python 3.13.0 + .venv на Windows не находит библиотеку Tcl - ошибка CPython gh-125235.
rem Проверяем не импорт, а настоящее окно: импорт проходит и там, где окна не будет.
"%VPY%" -c "import tkinter; r=tkinter.Tk(); r.withdraw(); r.destroy()" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] В .venv не создаётся окно Tk - известная ошибка Python 3.13.0.
    echo      Star Typing запустится: он сам подставит папку Tcl из базового Python.
    echo      Правильнее обновить Python до 3.13.1 или новее и запустить install.bat заново:
    echo      https://www.python.org/downloads/
    echo.
)

echo  [3/5] Пакеты: Pillow, pypdf, fpdf2 ...
rem pip читает requirements.txt в кодировке локали; PYTHONUTF8=1 держит кириллицу в комментариях.
set "PYTHONUTF8=1"
set "PIPLOG=%TEMP%\star-typing-pip.log"
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt" >"%PIPLOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [!] pip не смог поставить пакеты. Вот что он сказал:
    type "%PIPLOG%"
    echo.
    echo      Программа запустится и без них, но без Pillow нет фона и аватаров,
    echo      без pypdf не импортируется PDF, без fpdf2 нет кнопки PDF.
    echo      Обычно помогает повторить установку при рабочем интернете.
    echo.
    timeout /t 8 >nul
)

echo.
echo  Проверка произношения в АНГЛИЙСКОМ: микрофон, vosk, модель ~40 МБ.
choice /C YN /T 20 /D N /M " Установить её тоже (через 20 с - нет)"
if errorlevel 2 goto :shortcut
echo  [4/5] vosk + sounddevice + модель речи ...
"%VPY%" -m pip install --disable-pip-version-check -q vosk sounddevice
"%VPY%" "%ROOT%scripts\download_vosk_model.py"

echo.
echo  Радиорубка (онлайн-радио): нужен mpv. Если его нет — поставьте: winget install shinchiro.mpv
where mpv >nul 2>&1
if errorlevel 1 (
    choice /C YN /T 15 /D N /M " Установить mpv через winget (через 15 с - нет)"
    if not errorlevel 2 winget install -e --id shinchiro.mpv --accept-package-agreements --accept-source-agreements
)

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
