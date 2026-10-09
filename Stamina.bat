@echo off
rem Star Typing - запуск двойным щелчком (без чёрного окна).
rem Есть .venv (после install.bat) - запускаем из неё; иначе - системный Python.
rem Python нет совсем или первый запуск без пакетов - предлагаем install.bat.
chcp 65001 >nul
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%.venv\Scripts\pythonw.exe" (
    start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%main.py" %*
    exit /b 0
)

set "PYEXE="
set "PYARGS="
if defined STAMINA_PYTHON set "PYEXE=%STAMINA_PYTHON%"
if not defined PYEXE py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=py" && set "PYARGS=-3"
if not defined PYEXE python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE goto :need_install

if exist "%ROOT%.first_run_done" goto :run
"%PYEXE%" %PYARGS% -c "import PIL" >nul 2>&1
if not errorlevel 1 goto :run
:need_install
echo.
echo  Star Typing: похоже, это первый запуск - не хватает Python или пакетов.
echo  install.bat поставит всё сам: Python, пакеты, ярлык. Один щелчок.
echo.
choice /C YN /T 20 /D Y /M " Запустить установку сейчас (через 20 с - да)"
if errorlevel 2 (
    echo done> "%ROOT%.first_run_done"
    if defined PYEXE goto :run
    exit /b 1
)
call "%ROOT%install.bat"
exit /b 0

:run
set "PYW=%PYEXE%"
if "%PYEXE%"=="py" (where pyw.exe >nul 2>&1 && set "PYW=pyw")
if "%PYEXE%"=="python" (where pythonw.exe >nul 2>&1 && set "PYW=pythonw")
if defined STAMINA_PYTHON set "PYW=%STAMINA_PYTHON:python.exe=pythonw.exe%"
start "" "%PYW%" %PYARGS% "%ROOT%main.py" %*
endlocal
