"""TTS/ASR abstraction layer for multiple providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TTSProvider:
    name: str
    voices: dict[str, list[str]]
    requires_api_key: bool = False
    local: bool = False


@dataclass
class ASRProvider:
    name: str
    models: dict[str, str]
    requires_api_key: bool = False
    local: bool = False


class TTSEngine(ABC):
    @abstractmethod
    def speak(self, text: str, lang: str, voice: str, **kwargs) -> bytes:
        pass

    @abstractmethod
    def save(self, text: str, lang: str, voice: str, path: Path, **kwargs) -> None:
        pass


class ASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, lang: str) -> str:
        pass

    @abstractmethod
    def stream_transcribe(self, audio_chunk: bytes, lang: str) -> str:
        pass


class VoiceManager:
    def __init__(self, voices_config: dict):
        self.config = voices_config
        self._tts_engines: dict[str, TTSEngine] = {}
        self._asr_engines: dict[str, ASREngine] = {}

    def get_tts_voices(self, lang: str) -> dict[str, list[str]]:
        return self.config.get("tts", {}).get(lang, {})

    def get_asr_models(self, lang: str) -> dict[str, str]:
        return self.config.get("asr", {}).get(lang, {})

    def register_tts(self, provider: str, engine: TTSEngine) -> None:
        self._tts_engines[provider] = engine

    def register_asr(self, provider: str, engine: ASREngine) -> None:
        self._asr_engines[provider] = engine

    def tts(self, text: str, lang: str, voice: str, provider: str = "auto", **kwargs) -> bytes:
        if provider == "auto":
            provider = "piper" if "piper" in self._tts_engines else next(iter(self._tts_engines), None)
        if provider not in self._tts_engines:
            raise ValueError(f"TTS provider not available: {provider}")
        return self._tts_engines[provider].speak(text, lang, voice, **kwargs)

    def asr(self, audio_path: Path, lang: str, provider: str = "auto") -> str:
        if provider == "auto":
            provider = "vosk" if "vosk" in self._asr_engines else next(iter(self._asr_engines), None)
        if provider not in self._asr_engines:
            raise ValueError(f"ASR provider not available: {provider}")
        return self._asr_engines[provider].transcribe(audio_path, lang)