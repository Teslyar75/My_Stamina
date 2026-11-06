"""Проверка перед стартом: почему окно может не открыться и что с этим делать.

Раньше при отсутствии tkinter или графического экрана программа молча выходила:
под ярлыком с ``Terminal=false`` это выглядело как «ничего не произошло» — человек
щёлкал и не понимал, что случилось. Теперь причина пишется в журнал и, если есть
чем показать, выводится окном.

Проверка нарочно не тянет ни Tk, ни остальное приложение: она должна работать
именно тогда, когда окно открыть нельзя.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LOG_NAME = "launch.log"


@dataclass(frozen=True)
class Problem:
    """Что мешает запуску: заголовок окна и объяснение с командами."""

    title: str
    detail: str


# --------------------------------------------------------------------------- пути
def log_path() -> Path:
    """Журнал запуска: рядом с данными программы (там же, где start.log)."""
    try:
        from stamina import pilots

        return Path(pilots.ROOT_DIR) / LOG_NAME
    except Exception:  # noqa: BLE001 — журнал не должен мешать запуску
        return Path.home() / "star-typing-launch.log"


def write_log(text: str) -> None:
    """Дописать строку в журнал запуска (молча, если писать некуда)."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except OSError:
        pass


# ------------------------------------------------------------------------ проверки
def has_tkinter() -> bool:
    """Есть ли в этом Python библиотека окон (только импорт)."""
    try:
        import tkinter  # noqa: F401
    except Exception:  # noqa: BLE001 — битый _tkinter тоже сюда
        return False
    return True


def has_tk_window() -> bool:
    """Создаётся ли настоящее окно — импорт ничего не доказывает.

    В Python 3.13.0 из ``.venv`` на Windows импорт проходит, а ``tkinter.Tk()``
    падает с «Can't find a usable init.tcl» (ошибка CPython gh-125235, исправлена
    в 3.13.1). Раньше проверка смотрела только на импорт, поэтому вместо окна с
    причиной пилот получал тишину.
    """
    try:
        import tkinter
    except Exception:  # noqa: BLE001
        return False
    root = None
    try:
        root = tkinter.Tk()
        root.withdraw()
        return True
    except Exception:  # noqa: BLE001 — TclError и всё, что он принесёт с собой
        return False
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass


def tcl_dir(base_prefix: str) -> Path | None:
    """Каталог Tcl в базовой установке Python (8.6, 9.0 — как в этой сборке)."""
    root = Path(base_prefix) / "tcl"
    if not root.is_dir():
        return None
    try:
        import tkinter

        want = f"tcl{float(tkinter.TkVersion):.1f}"     # _tkinter знает версию и без окна
    except Exception:  # noqa: BLE001
        want = ""
    for name in (want, "tcl8.6", "tcl9.0"):
        if name and (root / name / "init.tcl").is_file():
            return root / name
    for cand in sorted(root.iterdir()):                # на всякий случай: любой живой Tcl
        if (cand / "init.tcl").is_file():
            return cand
    return None


def repair_tcl_env() -> str | None:
    """Подставить TCL_LIBRARY из базовой установки: окно без ручных переменных.

    Пока пилот не обновил Python 3.13.0, ``_tkinter`` в venv ищет библиотеку Tcl
    внутри ``.venv`` и не находит, хотя рядом лежит исправная базовая установка
    (CPython gh-125235). Возвращает подставленный путь или ``None``, если не понадобилось.
    """
    if os.environ.get("TCL_LIBRARY") or not sys.platform.startswith("win"):
        return None
    if sys.prefix == sys.base_prefix:          # не venv — _tkinter ищет сам
        return None
    tcl = tcl_dir(sys.base_prefix)
    if tcl is None:
        return None
    os.environ["TCL_LIBRARY"] = str(tcl)
    return str(tcl)


def tk_problem(platform: str) -> Problem:
    """Объяснение, что делать без tkinter — своё для каждой системы."""
    if platform.startswith("win"):
        detail = (
            "В этом Python нет библиотеки окон tkinter.\n\n"
            "Переустановите Python с сайта python.org и при установке включите\n"
            "пункт «tcl/tk and IDLE». Затем запустите install.bat."
        )
    elif platform == "darwin":
        detail = (
            "В этом Python нет библиотеки окон tkinter.\n\n"
            "Поставьте Python с python.org (в нём tkinter есть) или выполните:\n"
            "  brew install python-tk"
        )
    else:
        detail = (
            "В этом Python нет библиотеки окон tkinter.\n\n"
            "Ubuntu / Debian / Mint:   sudo apt install python3-tk\n"
            "Fedora:                   sudo dnf install python3-tkinter\n"
            "Arch / Manjaro:           sudo pacman -S tk\n"
            "openSUSE:                 sudo zypper install python3-tk\n\n"
            "После установки запустите снова:\n"
            "  bash install.sh        (или ./run.sh)"
        )
    return Problem("Star Typing: не открывается окно", detail)


def tcl_problem(platform: str) -> Problem:
    """Импорт tkinter есть, а окно не создаётся — обычно Tcl/Tk не нашёлся из venv."""
    if platform.startswith("win"):
        detail = (
            "Python нашёл tkinter, но библиотека окон Tcl/Tk не загружается:\n"
            "  Can't find a usable init.tcl\n\n"
            "Так ведёт себя Python 3.13.0, запущенный из папки .venv — ошибка\n"
            "CPython gh-125235, исправлена в 3.13.1.\n\n"
            "Что делать (любой из двух вариантов):\n"
            "  1. Обновить Python до 3.13.1 или новее и запустить install.bat заново.\n"
            "  2. Не трогая Python, задать папку Tcl перед запуском:\n"
            "       set TCL_LIBRARY=<папка Python>\\tcl\\tcl8.6\n"
            "     и запустить программу из этого же окна.\n\n"
            "Star Typing подставляет эту переменную сам. Это окно означает, что\n"
            "подстановка не помогла: скорее всего TCL_LIBRARY уже задан неверно."
        )
    elif platform == "darwin":
        detail = (
            "Python нашёл tkinter, но окно не создаётся: библиотека Tk не загружается.\n\n"
            "Поставьте Tk от python.org или выполните:\n"
            "  brew install python-tk"
        )
    else:
        detail = (
            "Python нашёл tkinter, но окно не создаётся: библиотека Tk не загружается.\n\n"
            "Ubuntu / Debian / Mint:   sudo apt install python3-tk\n"
            "Fedora:                   sudo dnf install python3-tkinter\n"
            "Arch / Manjaro:           sudo pacman -S tk\n"
            "openSUSE:                 sudo zypper install python3-tk"
        )
    return Problem("Star Typing: не открывается окно", detail)


def display_problem(platform: str, env) -> Problem | None:
    """Linux: Tk рисует через X11 — проверяем, есть ли к чему подключаться."""
    if not platform.startswith("linux"):
        return None
    if env.get("DISPLAY"):
        return None
    if env.get("WAYLAND_DISPLAY"):
        return Problem(
            "Star Typing: нет X11 (XWayland)",
            "Сессия работает на Wayland без XWayland, а окна Tk рисуются через X11.\n\n"
            "Поставьте пакет xwayland и войдите в систему заново —\n"
            "или запустите программу в сессии с X11.",
        )
    return Problem(
        "Star Typing: нет графического экрана",
        "Программа запущена без рабочего стола: так бывает по SSH, из службы\n"
        "или через sudo без доступа к экрану.\n\n"
        "Открывайте её из меню приложений или ярлыком на рабочем столе.",
    )


def check(*, tk_ok: bool | None = None, window_ok: bool | None = None,
          env=None, platform: str | None = None) -> Problem | None:
    """Вернуть помеху запуску или ``None``, если всё на месте.

    Параметры нужны тестам: на машине сборки нет ни Linux, ни реального экрана,
    а окно проверяется по-настоящему — без подстановок не обойтись.
    """
    plat = platform or sys.platform
    environment = os.environ if env is None else env
    # На Linux сначала проверяем DISPLAY: если его нет, проблема в отсутствии экрана,
    # а не в tkinter или Tcl
    if plat.startswith("linux"):
        disp_problem = display_problem(plat, environment)
        if disp_problem is not None:
            return disp_problem
    if not (has_tkinter() if tk_ok is None else tk_ok):
        return tk_problem(plat)
    if not (has_tk_window() if window_ok is None else window_ok):
        return tcl_problem(plat)
    return display_problem(plat, environment)


def preflight() -> bool:
    """Проверить условия запуска. ``False`` — окно открыть нельзя, причина уже показана."""
    try:
        repair_tcl_env()          # Python 3.13.0 + venv: иначе окна не будет вовсе
        problem = check()
    except Exception:  # noqa: BLE001 — проверка не имеет права мешать полётам
        return True
    if problem is None:
        return True
    text = f"{problem.title}\n\n{problem.detail}\n\nЖурнал: {log_path()}"
    write_log(text)
    _print(text)
    show_dialog(problem.title, text)
    return False


def _print(text: str) -> None:
    """Напечатать в консоль, если она есть (под pythonw потоков нет).

    Кодировка консоли бывает cp1252/cp866 — кириллица в неё не влезает. Ради
    отчёта не стоит падать: печатаем с заменами, главное — причина видна.
    """
    try:
        if sys.stderr is None:
            return
        try:
            sys.stderr.reconfigure(errors="replace")   # 3.7+: кириллица → «?», но текст виден
        except Exception:  # noqa: BLE001 — поток без reconfigure (перенаправлен в чужой объект)
            pass
        print(text, file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


def show_dialog(title: str, text: str) -> bool:
    """Показать окно с объяснением. ``True`` — показали.

    Tk здесь не годится: его как раз может не быть. Поэтому системные средства:
    на Windows — MessageBox, на Linux — zenity / kdialog / xmessage.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)  # MB_ICONERROR
            return True
        except Exception:  # noqa: BLE001
            return False
    if sys.platform == "darwin":
        try:
            script = f'display dialog {_applescript(text)} with title {_applescript(title)} buttons {{"OK"}}'
            subprocess.run(["osascript", "-e", script], timeout=180, check=False)
            return True
        except Exception:  # noqa: BLE001
            return False
    variants = (
        ("zenity", ["--error", "--no-wrap", "--title", title, "--text", text]),
        ("kdialog", ["--error", text, "--title", title]),
        ("xmessage", ["-center", "-title", title, text]),
    )
    for name, args in variants:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            subprocess.run([exe, *args], timeout=300, check=False)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _applescript(text: str) -> str:
    """Строка для AppleScript: кавычки и переводы строк не должны его ломать."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ------------------------------------------------------------------------ --check
def report() -> list[str]:
    """Короткий отчёт о среде запуска — для ``run.sh --check`` и писем в поддержку."""
    import platform as _platform

    lines = [
        f"Star Typing: проверка среды",
        f"Python: {sys.version.split()[0]} ({sys.executable})",
        f"Система: {_platform.platform()}",
    ]
    tk_import = has_tkinter()
    window = has_tk_window() if tk_import else False
    if tk_import:
        import tkinter

        lines.append(f"tkinter: есть, Tk {tkinter.TkVersion}")
        lines.append("окно: создаётся" if window else "окно: НЕ создаётся — см. подсказку ниже")
    else:
        lines.append("tkinter: НЕТ — окно не откроется, см. подсказку ниже")
    if sys.platform.startswith("linux"):
        lines.append(f"DISPLAY: {os.environ.get('DISPLAY') or 'нет'}")
        lines.append(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY') or 'нет'}")
        for name in ("zenity", "kdialog", "xmessage"):
            if shutil.which(name):
                lines.append(f"окно сообщений: {name}")
                break
        else:
            lines.append("окно сообщений: нет (zenity/kdialog/xmessage)")
    for module, label in (("PIL", "Pillow"), ("pypdf", "pypdf")):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            lines.append(f"{label}: нет (необязательно)")
        else:
            lines.append(f"{label}: есть")
    lines.append(f"данные: {log_path().parent}")
    problem = check(tk_ok=tk_import, window_ok=window)
    if problem is not None:
        lines.append("")
        lines.append(problem.title)
        lines.append(problem.detail)
    return lines
