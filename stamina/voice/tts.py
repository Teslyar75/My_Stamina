"""Текст → голос: Орион и гид говорят голосами Windows, без интернета.

Озвучка идёт в отдельном процессе PowerShell (`say.ps1` рядом с этим файлом), поэтому
интерфейс не замирает на время речи. Если пилот задал новую фразу, пока звучит прежняя,
прежняя обрывается — Орион не говорит сам с собой.

Голос берётся из хранилища OneCore (`Windows.Media.SpeechSynthesis`): там лежат современные
голоса, и для русского там есть мужской — Microsoft Pavel. Старое System.Speech таких голосов
не видит вообще (только Irina и Zira, обе женские) — потому корабль раньше и говорил женским
машинным голосом. Если OneCore недоступен, `say.ps1` сам уходит на System.Speech.
Список голосов обоих хранилищ: `voices()`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from stamina.voice.engine import guess_lang

HERE = Path(__file__).resolve().parent
SAY_PS1 = HERE / "say.ps1"

_proc: subprocess.Popen | None = None
_lock = threading.Lock()
#: Символов на озвучку. Лимита у движка нет — это забота о пилоте: длинный отчёт
#: вслух утомляет, поэтому длинный текст режется по границе предложения.
SPEECH_LIMIT = 1200


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


def linux_tool() -> str:
    """Linux/macOS: чем говорить — espeak-ng, espeak или spd-say (speech-dispatcher). "" — нечем."""
    if sys.platform == "win32" or os.environ.get("STAR_TYPING_NO_LINUX_TTS"):
        return ""
    from shutil import which
    for exe in ("espeak-ng", "espeak", "spd-say"):
        found = which(exe)
        if found:
            return found
    return ""


def _player() -> str:
    """Проигрыватель WAV на Linux: pw-play / paplay / aplay."""
    from shutil import which
    for exe in ("pw-play", "paplay", "aplay"):
        found = which(exe)
        if found:
            return found
    return ""


def _linux_cmd(tool: str, phrase: str, *, lang: str, rate: int, volume: int, out: str = "") -> list[str]:
    code = (lang or "ru").split("-")[0].lower()
    if Path(tool).name == "spd-say":
        return [tool, "-w", "-l", code, "-r", str(max(-100, min(100, rate * 10))),
                "-i", str(max(-100, min(100, volume * 2 - 100))), phrase]
    cmd = [tool, "-v", code, "-s", str(max(80, 170 + rate * 15)), "-a", str(max(0, min(200, volume * 2)))]
    if out:
        cmd += ["-w", out]
    return cmd + [phrase]


def available() -> bool:
    """Можно ли говорить: Windows + PowerShell + say.ps1, либо espeak-ng / spd-say на Linux."""
    if sys.platform == "win32":
        return bool(powershell()) and say_script().is_file()
    return bool(linux_tool())


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


ROLES = {
    # Голос разработчика/ИИ-агента: Павел, чуть ниже и с паузами на знаках препинания.
    "dev": {"pitch": "-4%", "pauses": True},
    "guide": {},
}


def speak(text: str, *, voice: str = "", rate: int = 0, volume: int = 100,
          lang: str = "", role: str = "") -> bool:
    """Произнести текст. Не блокирует: речь идёт в отдельном процессе.

    `lang` — язык текста (`ru`, `en`): по нему выбирается голос, иначе определяется сам.
    """
    global _proc
    phrase = speech_text(text)
    if not phrase or not available():
        return False
    if not lang:
        lang = guess_lang(phrase)
    stop()
    tool = linux_tool()
    if tool:
        try:
            with _lock:
                _proc = subprocess.Popen(_linux_cmd(tool, phrase, lang=lang, rate=rate, volume=volume),
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        return True
    tmp = Path(tempfile.gettempdir()) / f"orion_say_{os.getpid()}_{abs(hash(phrase)) % 10 ** 8}.txt"
    try:
        tmp.write_text(phrase, encoding="utf-8")
    except OSError:
        return False
    cmd = [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(say_script()),
           "-Path", str(tmp), "-Rate", str(rate), "-Volume", str(volume), "-Lang", lang]
    if voice:
        cmd += ["-Voice", voice]
    prof = ROLES.get(role, {})
    if prof.get("pitch"):
        cmd += ["-Pitch", prof["pitch"]]
    if prof.get("pauses"):
        cmd.append("-Pauses")
    flags = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
    try:
        with _lock:
            _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=flags)
    except OSError:
        return False
    return True


def _say_cmd(phrase_path: Path, *, voice: str, rate: int, volume: int, lang: str, role: str) -> list[str]:
    cmd = [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(say_script()),
           "-Path", str(phrase_path), "-Rate", str(rate), "-Volume", str(volume), "-Lang", lang]
    if voice:
        cmd += ["-Voice", voice]
    prof = ROLES.get(role, {})
    if prof.get("pitch"):
        cmd += ["-Pitch", prof["pitch"]]
    if prof.get("pauses"):
        cmd.append("-Pauses")
    return cmd


def cache_dir() -> Path:
    """Готовые WAV коротких фраз (временная папка системы: не жалко потерять)."""
    d = Path(tempfile.gettempdir()) / "star_typing_tts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(text: str, *, voice: str = "", lang: str = "", role: str = "") -> Path:
    import hashlib
    key = "|".join((speech_text(text), voice, lang, role)).encode("utf-8")
    return cache_dir() / (hashlib.sha1(key).hexdigest()[:20] + ".wav")


def render(text: str, *, voice: str = "", lang: str = "", role: str = "", timeout: float = 30.0) -> Path | None:
    """Синтезировать фразу в WAV заранее (блокирует — вызывать из потока). None — не вышло."""
    phrase = speech_text(text)
    if not phrase or not available():
        return None
    out = cache_path(phrase, voice=voice, lang=lang, role=role)
    if out.is_file() and out.stat().st_size > 1000:
        return out
    lang = lang or guess_lang(phrase)
    tool = linux_tool()
    if tool:
        if Path(tool).name == "spd-say":
            return None                          # spd-say в файл не пишет — фраза пойдёт живой речью
        try:
            subprocess.run(_linux_cmd(tool, phrase, lang=lang, rate=0, volume=100, out=str(out)),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            return None
        return out if out.is_file() and out.stat().st_size > 1000 else None
    tmp = Path(tempfile.gettempdir()) / f"orion_render_{os.getpid()}_{out.stem}.txt"
    try:
        tmp.write_text(phrase, encoding="utf-8")
        cmd = _say_cmd(tmp, voice=voice, rate=0, volume=100, lang=lang, role=role) + ["-Out", str(out)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    except (OSError, subprocess.SubprocessError):
        return None
    return out if out.is_file() and out.stat().st_size > 1000 else None


def play_cached(text: str, *, voice: str = "", lang: str = "", role: str = "") -> bool:
    """Мгновенно проиграть готовый WAV (если он уже в кэше). False — кэша нет."""
    global _proc
    out = cache_path(text, voice=voice, lang=lang, role=role)
    if not out.is_file():
        return False
    if sys.platform != "win32":
        player = _player()
        if not player:
            return False
        stop()
        try:
            with _lock:
                _proc = subprocess.Popen([player, str(out)], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        except OSError:
            return False
        return True
    stop()
    try:
        import winsound
        winsound.PlaySound(str(out), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:  # noqa: BLE001
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
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:  # noqa: BLE001
            pass


def speaking() -> bool:
    with _lock:
        return _proc is not None and _proc.poll() is None


def voices() -> list[str]:
    """Голоса системы: «хранилище|имя|язык|пол» — OneCore первым, затем System.Speech."""
    if sys.platform != "win32" or not available():
        return []
    try:
        out = subprocess.run([powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", str(say_script()), "-ListVoices"],
                             capture_output=True, timeout=30,
                             creationflags=0x08000000 if sys.platform == "win32" else 0)
    except (OSError, subprocess.SubprocessError):
        return []
    text = out.stdout.decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines() if "|" in line]


def voice_rows() -> list[tuple[str, str, str, str]]:
    """Голоса обоих хранилищ: [(хранилище, имя, язык, пол)] — OneCore первым."""
    rows = []
    for line in voices():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


def preferred_voice(lang: str = "ru") -> str:
    """Голос под язык текста: мужской из OneCore, иначе первый подходящий по языку.

    Для английского мужского в OneCore может не быть (пока не поставили английский
    голос в системе) — тогда берём любой английский, а не русский: английскую книгу
    Павел читать не должен.
    """
    code = (lang or "").split("-")[0].lower()
    rows = voice_rows()
    core = [r for r in rows if r[0].lower() == "onecore"]
    pool = [r for r in (core or rows) if r[2].lower().startswith(code)] if code else list(rows)
    if not pool:
        pool = [r for r in rows if r[2].lower().startswith(code)] if code else list(rows)
    if not pool:
        return ""
    for row in pool:
        if row[3].lower() == "male":
            return row[1]
    return pool[0][1]


def male_voice() -> str:
    """Мужской русский голос для речи Ориона (Павел, иначе русский из System.Speech)."""
    for row in voice_rows():
        if row[0].lower() == "onecore" and row[3].lower() == "male" and row[2].lower().startswith("ru"):
            return row[1]
    return preferred_voice("ru")
