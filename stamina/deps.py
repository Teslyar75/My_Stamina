"""Компоненты Star Typing: определение системы, проверка и установка недостающего в один клик.

Windows и Linux. pip-пакеты ставятся текущим интерпретатором (`sys.executable -m pip`), модель речи —
scripts/download_vosk_model.py, системные пакеты Linux — через pkexec + apt/dnf/pacman/zypper
(если pkexec нет — показываем готовую команду для терминала).
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SYSTEMS = ("windows", "linux")
SYSTEM_TITLES = {"windows": "Windows", "linux": "Linux"}

# системные пакеты Linux по менеджерам: компонент → имена пакетов
LINUX_PKGS = {
    "apt": {"tk": ["python3-tk"], "venv": ["python3-venv", "python3-pip"], "portaudio": ["libportaudio2"],
            "tts": ["espeak-ng"]},
    "dnf": {"tk": ["python3-tkinter"], "venv": ["python3-pip"], "portaudio": ["portaudio"], "tts": ["espeak-ng"]},
    "pacman": {"tk": ["tk"], "venv": ["python-pip"], "portaudio": ["portaudio"], "tts": ["espeak-ng"]},
    "zypper": {"tk": ["python3-tk"], "venv": ["python3-pip"], "portaudio": ["portaudio"], "tts": ["espeak-ng"]},
}
INSTALL_CMD = {"apt": "sudo apt install -y", "dnf": "sudo dnf install -y", "pacman": "sudo pacman -S --needed --noconfirm",
               "zypper": "sudo zypper install -y"}


PM_ARGS = {"apt": ["apt-get", "install", "-y"], "dnf": ["dnf", "install", "-y"],
           "pacman": ["pacman", "-S", "--needed", "--noconfirm"], "zypper": ["zypper", "--non-interactive", "install"]}


def detect_system() -> str:
    return "windows" if sys.platform == "win32" else "linux"


def system_details() -> str:
    if sys.platform == "win32":
        return f"Windows {platform.release()}"
    name = ""
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                name = line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return name or f"Linux {platform.release()}"


def package_manager() -> str | None:
    for pm in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(pm if pm != "apt" else "apt-get"):
            return pm
    return None


def has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def python_ok() -> bool:
    return sys.version_info >= (3, 10)


def _portaudio_ok() -> bool:
    if sys.platform == "win32":
        return True                   # sounddevice везёт PortAudio с собой
    import ctypes.util
    return ctypes.util.find_library("portaudio") is not None


def _tts_ok(system: str) -> bool:
    if system == "windows":
        return sys.platform == "win32"        # SAPI (System.Speech) встроен в Windows
    from stamina.english.tts import linux_engine
    return linux_engine() is not None


def check(system: str | None = None) -> list[dict]:
    """Пункты: key, name, ok, need, what, pip (пакеты pip), sys (компоненты системных пакетов), how."""
    system = system or detect_system()
    from stamina.english import paths
    pm = package_manager() if system == "linux" else None
    items = [
        {"key": "python", "name": f"Python {sys.version_info.major}.{sys.version_info.minor}", "ok": python_ok(),
         "need": "нужно", "what": "сама программа", "pip": [], "sys": [],
         "how": "python.org → Python 3.10+" if system == "windows" else "install.sh"},
        {"key": "pillow", "name": "Pillow", "ok": has("PIL"), "need": "рекомендуется",
         "what": "фон «Живой космос», аватары JPG", "pip": ["Pillow"], "sys": []},
        {"key": "tts", "name": "Озвучка: SAPI" if system == "windows" else "Озвучка: espeak-ng",
         "ok": _tts_ok(system), "need": "рекомендуется", "what": "произнести слово в АНГЛИЙСКОМ",
         "pip": [], "sys": [] if system == "windows" else ["tts"]},
        {"key": "vosk", "name": "vosk + sounddevice", "ok": has("vosk") and has("sounddevice") and _portaudio_ok(),
         "need": "необязательно", "what": "проверка произношения (микрофон)",
         "pip": [p for p, m in (("vosk", "vosk"), ("sounddevice", "sounddevice")) if not has(m)],
         "sys": [] if system == "windows" or _portaudio_ok() else ["portaudio"]},
        {"key": "model", "name": "Модель речи vosk", "ok": paths.vosk_model_dir() is not None, "need": "необязательно",
         "what": "проверка произношения, ≈ 40 МБ", "pip": [], "sys": []},
    ]
    for it in items:
        if "how" not in it:
            it["how"] = how(it, system, pm)
    return items


def how(it: dict, system: str, pm: str | None) -> str:
    parts = []
    if it["pip"]:
        parts.append("pip install " + " ".join(it["pip"]))
    if it["sys"]:
        parts.append(system_command(it["sys"], pm) or "пакеты: " + ", ".join(it["sys"]))
    if it["key"] == "model":
        parts.append("scripts/download_vosk_model.py")
    if it["key"] == "tts" and system == "windows":
        parts.append("Параметры → Время и язык → Речь → добавить английский голос")
    if not parts and (it["key"] == "pillow" or it["key"] == "vosk"):
        parts.append("pip install " + ("Pillow" if it["key"] == "pillow" else "vosk sounddevice"))
    return " · ".join(parts) or "—"


def system_packages(comps: list[str], pm: str | None) -> list[str]:
    if pm is None:
        return []
    out: list[str] = []
    for c in comps:
        out += LINUX_PKGS[pm].get(c, [])
    return out


def system_command(comps: list[str], pm: str | None) -> str:
    pk = system_packages(comps, pm)
    return f"{INSTALL_CMD[pm]} {' '.join(pk)}" if pk and pm else ""


def missing(items: list[dict]) -> list[dict]:
    return [it for it in items if not it["ok"] and it["key"] != "python"]


def install_all(items: list[dict], log=print, system: str | None = None) -> bool:
    """Поставить всё недостающее. log(str) — строки прогресса. → True, если всё получилось."""
    system = system or detect_system()
    ok = True
    pm = package_manager() if system == "linux" else None
    comps = sorted({c for it in missing(items) for c in it["sys"]})
    if comps:
        pk = system_packages(comps, pm)
        root = hasattr(os, "geteuid") and os.geteuid() == 0
        gui_sudo = shutil.which("pkexec") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if pk and (root or gui_sudo):
            cmd = ([] if root else ["pkexec"]) + PM_ARGS[pm] + pk
            log("Системные пакеты: " + " ".join(pk) + ("" if root else " (система спросит пароль)") + "…")
            ok &= _run(cmd, log)
        else:
            log("Системные пакеты поставьте в терминале:  " + (system_command(comps, pm) or ", ".join(comps)))
            ok = False
    pips = [p for it in missing(items) for p in it["pip"]]
    if pips:
        log("pip install " + " ".join(pips) + " …")
        res = _run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *pips], log)
        if not res:
            log("pip не смог установить пакеты. Запустите установщик: "
                + ("install.bat" if system == "windows" else "bash install.sh"))
        ok &= res
        importlib.invalidate_caches()
    if any(it["key"] == "model" for it in missing(items)):
        log("Скачиваю модель речи (≈ 40 МБ)…")
        ok &= _run([sys.executable, str(PROJECT / "scripts" / "download_vosk_model.py")], log)
    log("Готово." if ok else "Готово не всё — см. строки выше.")
    return ok


def _run(cmd: list[str], log) -> bool:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
        for raw in p.stdout:  # type: ignore[union-attr]
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                log("  " + line[-160:])
        return p.wait() == 0
    except OSError as exc:
        log(f"  ошибка запуска: {exc}")
        return False


def pillow_hint() -> str:
    tool = "install.bat" if sys.platform == "win32" else "bash install.sh"
    return f"Не установлен Pillow — фон «Живой космос» выключен. Установка: {tool} или кнопка «УСТАНОВИТЬ ВСЁ» в приветствии (pip install Pillow)."
