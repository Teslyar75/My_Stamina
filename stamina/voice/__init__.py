"""Голос корабля: распознавание речи (Vosk) и озвучка ответов (Windows).

Два подмодуля:

- `stt` — «речь пилота → текст» офлайн (Vosk + sounddevice), без tkinter;
- `tts` — «текст → голос» голосами Windows (System.Speech), без интернета.

Оба модуля чистые: их проверяют тесты без микрофона и без динамиков.
"""

from __future__ import annotations

from stamina.voice import stt, tts  # noqa: F401

__all__ = ["stt", "tts"]
