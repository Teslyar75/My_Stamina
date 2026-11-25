"""Речь языкового отсека: de, es, fr, it.

Та же связка, что в английском отсеке: Vosk слушает, оценка слова и фразы
считается теми же функциями. Модели лежат в models/lang/, не в корне models/,
чтобы английский отсек по-прежнему брал свою модель.
"""
from __future__ import annotations

import threading
import urllib.request
import zipfile
from pathlib import Path

from stamina.english.asr import ASR
from stamina.english.paths import MODELS_DIR
from stamina.english.tts import TTS
from stamina.i18n import t as _t

# Малые модели alphacephei: десятки мегабайт, не полные словари на гигабайт.
MODELS = {
    "de": (
        "vosk-model-small-de-0.15",
        "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
    ),
    "es": (
        "vosk-model-small-es-0.42",
        "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
    ),
    "fr": (
        "vosk-model-small-fr-0.22",
        "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
    ),
    "it": (
        "vosk-model-small-it-0.22",
        "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip",
    ),
}
CULTURE = {"de": "de-*", "es": "es-*", "fr": "fr-*", "it": "it-*"}

_asr: dict[str, "LangASR"] = {}
_tts: TTS | None = None
_busy: set[str] = set()


def culture_for(lang: str) -> str:
    return CULTURE.get(lang, "")


def expected_dir(lang: str) -> Path | None:
    spec = MODELS.get(lang)
    if spec is None:
        return None
    return MODELS_DIR / "lang" / spec[0]


def model_ready(lang: str) -> bool:
    folder = expected_dir(lang)
    return bool(folder and folder.is_dir() and (folder / "am").is_dir())


class LangASR(ASR):
    """Распознавание одного языка. Пока архив качается, причина — в why_unavailable."""

    def __init__(self, lang: str, folder: Path | None) -> None:
        super().__init__(model_dir=folder)
        self.lang = lang

    def why_unavailable(self) -> str:
        if self._dir() is None and self.lang in _busy:
            return _t("модель речи для {0} ещё скачивается").format(self.lang.upper())
        return super().why_unavailable()


def asr_for(lang: str) -> LangASR:
    cur = _asr.get(lang)
    if cur is None:
        folder = expected_dir(lang) or (MODELS_DIR / "lang" / f"missing-{lang}")
        cur = LangASR(lang, folder)
        _asr[lang] = cur
    return cur


def tts() -> TTS:
    global _tts
    if _tts is None:
        _tts = TTS()
    return _tts


def ensure_model(lang: str, on_done=None) -> None:
    """Скачать малую модель, если её ещё нет. Повторный вызов ничего не качает."""
    if lang not in MODELS or model_ready(lang) or lang in _busy:
        return
    _busy.add(lang)

    def work() -> None:
        try:
            _download(lang)
        finally:
            _busy.discard(lang)
            if on_done is not None:
                on_done()

    threading.Thread(target=work, daemon=True, name=f"vosk-{lang}").start()


def _download(lang: str) -> None:
    name, url = MODELS[lang]
    dest = MODELS_DIR / "lang"
    dest.mkdir(parents=True, exist_ok=True)
    part = dest / f"{name}.zip.part"
    req = urllib.request.Request(url, headers={"User-Agent": "StarTyping-vocab/1.0"})
    with urllib.request.urlopen(req, timeout=180) as src, part.open("wb") as out:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    archive = dest / f"{name}.zip"
    part.replace(archive)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = [p for p in info.filename.replace("\\", "/").split("/") if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts):
                continue
            target = root.joinpath(*parts)
            try:
                target.relative_to(root)
            except ValueError:
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as src, target.open("wb") as out:
                out.write(src.read())
    archive.unlink(missing_ok=True)


import hashlib
import importlib.util
import subprocess
import tempfile
import time

_VOICES = {
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "it": "it-IT-ElsaNeural",
}
_player = None
_player_lock = threading.Lock()
_edge: bool | None = None       # есть ли пакет edge-tts (живые голоса Microsoft из сети)


def edge_ready() -> bool:
    """Есть ли пакет edge-tts: сетевой голос Microsoft на все четыре языка."""
    global _edge
    if _edge is None:
        _edge = importlib.util.find_spec("edge_tts") is not None
    return _edge


def stop_speak() -> None:
    """Остановить текущую озвучку карточки."""
    global _player
    with _player_lock:
        proc = _player
        _player = None
    if proc is not None and proc.poll() is None:
        proc.kill()
    if _tts is not None:
        _tts.stop()          # голос Windows, если звучал он


def _no_voice_message(lang: str, why: str = "") -> str:
    """Понятная причина: чего не хватает для голоса этого языка.

    Это пояснение, а не подпись интерфейса, поэтому по-русски и без _t().
    """
    why = (why or "").strip()
    edge_hint = "Без голоса Windows можно включить edge-tts: pip install edge-tts."
    if why:
        return f"{why}. {edge_hint}"
    return (f"нет голоса для языка {lang.upper()}. "
            "Поставьте голос Windows этого языка (Параметры → Время и язык → Речь). "
            + edge_hint)


def speak(text: str, lang: str, slow: bool = False, on_error=None, on_done=None) -> None:
    """Озвучить слово или фразу голосом языка карточки.

    Сначала сетевой голос Microsoft (edge-tts), если пакет есть и сеть отвечает.
    Иначе — голос Windows нужной культуры. Если нет ни того, ни другого,
    on_error получает понятную причину, что поставить.
    """
    text = (text or "").strip()
    voice = _VOICES.get(lang)
    if not text or not voice:
        if on_done is not None:
            on_done()
        return

    def fail(message: str) -> None:
        if on_error is not None:
            on_error(message)

    def finish() -> None:
        if on_done is not None:
            on_done()

    def work() -> None:
        if edge_ready():
            try:
                _speak_edge(text, voice, slow)
                finish()
                return
            except Exception:  # noqa: BLE001
                pass                     # нет сети или пакет сломался — идём к голосу Windows
        _speak_sapi(text, lang, slow, fail, finish)

    threading.Thread(target=work, daemon=True, name=f"say-{lang}").start()


def _speak_edge(text: str, voice: str, slow: bool) -> None:
    """Нейросетевой образец Microsoft: mp3 кэшируется, играет MediaPlayer."""
    global _player
    import asyncio
    import edge_tts
    folder = Path(tempfile.gettempdir()) / "stamina-say"
    folder.mkdir(exist_ok=True)
    rate = "-25%" if slow else "+0%"
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:16]
    path = folder / f"{key}.mp3"
    if not path.is_file() or path.stat().st_size < 200:
        async def save() -> None:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
        asyncio.run(save())
    stop_speak()
    command = (
        "Add-Type -AssemblyName presentationCore; "
        "$m = New-Object System.Windows.Media.MediaPlayer; "
        "$m.Open([uri]$env:STAMINA_SAY); "
        "$m.Volume = 1; $m.Play(); "
        "$until = (Get-Date).AddSeconds(30); "
        "while (-not $m.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $until) { Start-Sleep -Milliseconds 40 }; "
        "if ($m.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds ([int]$m.NaturalDuration.TimeSpan.TotalMilliseconds + 200) }"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-STA", "-Command", command],
        env={**__import__("os").environ, "STAMINA_SAY": str(path)},
        creationflags=flags,
    )
    with _player_lock:
        _player = proc


def _speak_sapi(text: str, lang: str, slow: bool, fail, finish) -> None:
    """Запасной путь: голос Windows нужной культуры через общий движок TTS."""
    engine = tts()
    engine.last_error = ""            # причина прошлой фразы не должна всплыть сейчас
    sid = engine.speak(text, -4 if slow else 0, culture=culture_for(lang))
    if not sid:
        fail(_no_voice_message(lang, engine.last_error))
        finish()
        return
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for kind, ev_sid, message in engine.poll():
            if kind in ("error", "dead"):
                fail(_no_voice_message(lang, message))
                finish()
                return
            if kind in ("done", "cancel") and ev_sid == sid:
                finish()
                return
        if engine.last_error:         # голос не выбран — ждать дальше нечего
            fail(_no_voice_message(lang, engine.last_error))
            finish()
            return
        time.sleep(0.15)
    fail(_no_voice_message(lang, engine.last_error))
    finish()
