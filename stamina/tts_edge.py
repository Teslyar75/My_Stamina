"""Сетевые голоса Microsoft (edge-tts): синтез в mp3 и проигрывание.

Один движок на всё приложение: английский отсек и языковые сканеры говорят
одними и теми же живыми голосами. Пакет edge-tts необязателен: `ready()`
проверяет его наличие, а вызывающий код при отказе говорит голосом Windows.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import tempfile
import threading
from pathlib import Path

# Голос каждого языка: нейросетевые голоса Microsoft, читают естественно.
VOICES = {
    "en": "en-US-AriaNeural",
    "en-GB": "en-GB-SoniaNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "it": "it-IT-ElsaNeural",
}

_PLAY = (
    "Add-Type -AssemblyName presentationCore; "
    "$m = New-Object System.Windows.Media.MediaPlayer; "
    "$m.Open([uri]$env:STAMINA_SAY); "
    "$m.Volume = 1; $m.Play(); "
    "$until = (Get-Date).AddSeconds(60); "
    "while (-not $m.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $until) { Start-Sleep -Milliseconds 40 }; "
    "if ($m.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds ([int]$m.NaturalDuration.TimeSpan.TotalMilliseconds + 200) }"
)

_ready: bool | None = None
_player: subprocess.Popen | None = None
_lock = threading.Lock()


def ready() -> bool:
    """Установлен ли пакет edge-tts (синтез идёт через сеть)."""
    global _ready
    if _ready is None:
        _ready = importlib.util.find_spec("edge_tts") is not None
    return _ready


def voice_for(lang: str, culture: str = "") -> str:
    """Голос по коду языка (de/es/fr/it/en); культура уточняет варианты английского."""
    culture = (culture or "").replace("*", "")
    if culture.lower().startswith("en-gb"):
        return VOICES["en-GB"]
    return VOICES.get(lang) or VOICES.get(culture[:2].lower()) or ""


def _percent(rate: int = 0, slow: bool = False) -> str:
    if slow:
        return "-25%"
    pct = max(-45, min(45, int(rate) * 5))
    return f"{pct:+d}%"


def synth(text: str, voice: str, *, rate: int = 0, slow: bool = False) -> Path:
    """Синтезировать фразу в mp3 (кэш в %TEMP%/stamina-say). Блокирует поток."""
    import asyncio
    import edge_tts
    folder = Path(tempfile.gettempdir()) / "stamina-say"
    folder.mkdir(exist_ok=True)
    pct = _percent(rate, slow)
    key = hashlib.sha1(f"{voice}|{pct}|{text}".encode("utf-8")).hexdigest()[:16]
    path = folder / f"{key}.mp3"
    if not path.is_file() or path.stat().st_size < 200:
        async def save() -> None:
            await edge_tts.Communicate(text, voice, rate=pct).save(str(path))
        asyncio.run(save())
    return path


def play(path: Path) -> subprocess.Popen:
    """Проиграть файл через MediaPlayer; процесс завершится, когда фраза отзвучит."""
    stop()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-STA", "-Command", _PLAY],
        env={**os.environ, "STAMINA_SAY": str(path)},
        creationflags=flags,
    )
    global _player
    with _lock:
        _player = proc
    return proc


def stop() -> None:
    """Остановить текущую сетевую фразу."""
    global _player
    with _lock:
        proc = _player
        _player = None
    if proc is not None and proc.poll() is None:
        proc.kill()
