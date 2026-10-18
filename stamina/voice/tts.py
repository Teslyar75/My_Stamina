"""Текст → голос: Орион говорит голосами Windows (System.Speech), без интернета.

Озвучка идёт в отдельном процессе PowerShell (`say.ps1` рядом с этим файлом), поэтому
интерфейс не замирает на время речи. Если пилот задал новую фразу, пока звучит прежняя,
прежняя обрывается — Орион не говорит сам с собой.

Голос по умолчанию — русский из системы (Microsoft Pavel). Список: `voices()`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAY_PS1 = HERE / "say.ps1"

_proc: subprocess.Popen | None = None
_lock = threading.Lock()
SPEECH_LIMIT = 420          # символов на озвучку: длинный отчёт читать вслух утомительно


def say_script() -> Path:
    """Скрипт озвучки: свой или заданный в `STAR_TYPING_SAY_PS1`."""
    custom = os.environ.get("STAR_TYPING_SAY_PS1")
    return Path(custom) if custom else SAY_PS1


def powershell() -> str:
    """Где PowerShell (Windows PowerShell 5.1 или PowerShell 7)."""
    for exe in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        from shutil import which
        found = which(exe)
        if found:
            return found
    return ""


def available() -> bool:
    """Можно ли говорить: Windows + PowerShell + скрипт озвучки на месте."""
    return sys.platform == "win32" and bool(powershell()) and say_script().is_file()


def speech_text(text: str, limit: int = SPEECH_LIMIT) -> str:
    """Убрать разметку и обрезать по границе предложения — чтобы голос не тараторил отчёт."""
    t = text or ""
    t = re.sub(r"⟦[^⟧]*⟧[^\n]*", " ", t)          # служебные маркеры корабля не читаем
    t = re.sub(r"```.*?```", " ", t, flags=re.S)     # блоки кода
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)   # маркеры списка
    t = re.sub(r"[#>*`_]+", "", t)                   # разметка markdown
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)   # ссылки → текст
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    for stop in (". ", "! ", "? ", "… "):
        pos = cut.rfind(stop)
        if pos > limit * 0.5:
            return cut[: pos + 1].strip()
    return cut.rstrip() + "…"


def speak(text: str, *, voice: str = "", rate: int = 0, volume: int = 100) -> bool:
    """Произнести текст. Не блокирует: речь идёт в отдельном процессе."""
    global _proc
    phrase = speech_text(text)
    if not phrase or not available():
        return False
    stop()
    tmp = Path(tempfile.gettempdir()) / f"orion_say_{os.getpid()}_{abs(hash(phrase)) % 10 ** 8}.txt"
    try:
        tmp.write_text(phrase, encoding="utf-8")
    except OSError:
        return False
    cmd = [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(say_script()),
           "-Path", str(tmp), "-Rate", str(rate), "-Volume", str(volume)]
    if voice:
        cmd += ["-Voice", voice]
    flags = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
    try:
        with _lock:
            _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=flags)
    except OSError:
        return False
    return True


def stop() -> None:
    """Оборвать текущую речь (если говорит)."""
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            try:
                _proc.terminate()
            except OSError:
                pass
        _proc = None


def speaking() -> bool:
    with _lock:
        return _proc is not None and _proc.poll() is None


def voices() -> list[str]:
    """Установленные голоса Windows: «Имя|язык»."""
    if not available():
        return []
    try:
        out = subprocess.run([powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", str(say_script()), "-ListVoices"],
                             capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    text = out.stdout.decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines() if "|" in line]
