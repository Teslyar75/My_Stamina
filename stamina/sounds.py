"""Звуки пульта: щелчок печатной машинки, сигнал ошибки, колокольчик.

Все звуки синтезируются этим модулем (никаких чужих файлов и лицензий) и
лежат маленькими WAV-файлами в ``stamina/sounds``. Проигрываются через
стандартный ``winsound`` в асинхронном режиме — программа не тормозит.
На других ОС звук просто отключается.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

try:  # только Windows
    import winsound
except ImportError:  # pragma: no cover - Linux/macOS
    winsound = None  # type: ignore[assignment]

RATE = 22050
VOLUMES = {1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}
SOUND_DIR = Path(__file__).resolve().parent / "sounds"
CLICK_VARIANTS = 3


# --- Синтез ----------------------------------------------------------------

def _click(seed: int) -> list[float]:
    """Щелчок клавиши печатной машинки: удар + металлический «тик»."""
    rng = random.Random(seed)
    n = int(RATE * 0.045)
    out = []
    prev = 0.0
    tick_f = 2600 + seed * 230
    for i in range(n):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        hp = noise - prev          # простейший ВЧ-фильтр — «сухой» щелчок
        prev = noise
        strike = hp * math.exp(-t / 0.0035) * 0.9
        tick = math.sin(2 * math.pi * tick_f * t) * math.exp(-t / 0.006) * 0.35
        thump = math.sin(2 * math.pi * 170 * t) * math.exp(-t / 0.012) * 0.55
        # второй, тихий удар — возврат рычага
        t2 = t - 0.018
        back = 0.0
        if t2 > 0:
            back = rng.uniform(-1, 1) * math.exp(-t2 / 0.003) * 0.25
        out.append(strike + tick + thump + back)
    return out


def _error() -> list[float]:
    """Глухой «бззт» — сразу понятно, что ошибка."""
    n = int(RATE * 0.16)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / 0.004) * math.exp(-t / 0.07)
        sq = 1.0 if math.sin(2 * math.pi * 115 * t) >= 0 else -1.0
        sq2 = 1.0 if math.sin(2 * math.pi * 173 * t) >= 0 else -1.0
        thunk = math.sin(2 * math.pi * 80 * t) * math.exp(-t / 0.02)
        out.append((sq * 0.35 + sq2 * 0.25) * env + thunk * 0.6)
    return out


def _bell() -> list[float]:
    """Колокольчик каретки — миссия выполнена."""
    n = int(RATE * 0.9)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / 0.002) * math.exp(-t / 0.28)
        v = (math.sin(2 * math.pi * 2093 * t) * 0.55
             + math.sin(2 * math.pi * 2637 * t) * 0.25
             + math.sin(2 * math.pi * 4186 * t) * 0.12 * math.exp(-t / 0.08))
        out.append(v * env)
    return out


def _start() -> list[float]:
    """Короткий восходящий сигнал «к запуску готов»."""
    n = int(RATE * 0.18)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = 600 + 900 * (t / 0.18)
        phase += 2 * math.pi * f / RATE
        env = min(1.0, t / 0.01) * (1 - t / 0.18)
        out.append(math.sin(phase) * env * 0.5)
    return out


def _write(path: Path, samples: list[float], volume: float) -> None:
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = 0.85 / peak * volume * 32767
    frames = b"".join(struct.pack("<h", int(max(-32767, min(32767, s * scale))))
                      for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)


def _all_sounds() -> dict[str, list[float]]:
    sounds = {f"click{i + 1}": _click(i) for i in range(CLICK_VARIANTS)}
    sounds.update(error=_error(), bell=_bell(), start=_start())
    return sounds


def generate_all(folder: Path = SOUND_DIR) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, samples in _all_sounds().items():
        for level, vol in VOLUMES.items():
            _write(folder / f"{name}_v{level}.wav", samples, vol)


# --- Проигрывание ------------------------------------------------------------

class SoundBoard:
    def __init__(self, enabled: bool = True, volume: int = 3) -> None:
        self.enabled = enabled
        self.volume = volume if volume in VOLUMES else 3
        self._click_i = 0
        self.available = winsound is not None
        if self.available:
            try:
                if not (SOUND_DIR / "click1_v1.wav").exists():
                    generate_all()
            except OSError:
                self.available = False

    def _play(self, name: str) -> None:
        if not (self.enabled and self.available):
            return
        path = SOUND_DIR / f"{name}_v{self.volume}.wav"
        try:
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except (RuntimeError, OSError):
            pass

    def click(self) -> None:
        self._click_i = (self._click_i + 1) % CLICK_VARIANTS
        self._play(f"click{self._click_i + 1}")

    def error(self) -> None:
        self._play("error")

    def bell(self) -> None:
        self._play("bell")

    def start(self) -> None:
        self._play("start")


if __name__ == "__main__":
    generate_all()
    print("Звуки сгенерированы в", SOUND_DIR)
