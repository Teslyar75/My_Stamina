"""Речь пилота → текст внутри корабля: офлайн-распознавание на Vosk.

Работает без интернета: движок Vosk + библиотека sounddevice, русская модель в папке
`models/` корабля (скачать: `python tools/voice_input/get_model.py`). Аудио никуда
не отправляется.

Слой без tkinter: экран только забирает события через `Listener.poll()` — поэтому
логику конца фразы, чистку текста и поиск модели проверяют обычные тесты.

Пример:

    lst = Listener()
    if lst.start():
        while True:
            for kind, value in lst.poll():
                ...
"""

from __future__ import annotations

import array
import json
import math
import os
import queue
import re
import threading
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_RATE = 16000
BLOCK = 4000                      # 0.25 с при 16 кГц
LANG = "ru"

# Коды событий Listener (UI переводит их сам — в слое данных нет i18n):
#   ("status", "loading" | "listening")   состояние записи
#   ("level", 0…1)                        громкость для шкалы
#   ("partial", "текст")                  распознавание на лету
#   ("final", "текст")                    готовая фраза
#   ("error", "пояснение")                сбой (нет библиотеки, нет модели, тишина…)
#   ("done", None)                        запись закончена, поток закрыт


# -- модель --------------------------------------------------------------------
def models_dir() -> Path:
    """Папка моделей: `STAR_TYPING_MODELS` или `models/` корабля."""
    return Path(os.environ.get("STAR_TYPING_MODELS") or (PROJECT_DIR / "models"))


def find_model(root: Path | None = None, prefer: str = LANG) -> Path | None:
    """Папка модели Vosk: сначала с нужным языком (vosk-model-small-ru-…), иначе любая."""
    root = root or models_dir()
    if not root.is_dir():
        return None
    found = [p for p in sorted(root.iterdir())
             if p.is_dir() and p.name.startswith("vosk-model") and (p / "am").exists()]
    for p in found:
        if f"-{prefer}-" in p.name:
            return p
    return found[0] if found else None


def deps_ok() -> tuple[bool, str]:
    """Есть ли библиотеки распознавания. Возвращает (готово, пояснение)."""
    for name in ("vosk", "sounddevice"):
        try:
            __import__(name)
        except Exception as exc:  # noqa: BLE001
            return False, str(getattr(exc, "name", "") or name)
    return True, ""


def ready() -> tuple[bool, str]:
    """Готов ли голосовой ввод целиком: (готово, причина отказа)."""
    ok, missing = deps_ok()
    if not ok:
        return False, f"нет библиотеки {missing}"
    path = find_model()
    if path is None:
        return False, f"нет модели Vosk в {models_dir()}"
    return True, ""


_MODEL = None
_MODEL_PATH: Path | None = None


def load_model(path: Path | None = None):
    """Загрузить модель Vosk (с кэшем: вторая загрузка мгновенная)."""
    global _MODEL, _MODEL_PATH
    path = Path(path) if path else find_model()
    if path is None or not path.is_dir():
        return None
    if _MODEL is not None and _MODEL_PATH == path:
        return _MODEL
    import vosk
    vosk.SetLogLevel(-1)
    _MODEL = vosk.Model(str(path))
    _MODEL_PATH = path
    return _MODEL


# -- логика фразы (без микрофона — тестируется отдельно) ------------------------
class PhraseSplitter:
    """Решает, когда фраза закончилась: после тишины, по лимиту или «молчит».

    Чистая логика: feed() получает распознанный частичный текст, громкость и
    длительность блока. Возвращает True, когда запись пора заканчивать.
    """

    def __init__(self, silence_sec: float = 1.5, max_sec: float = 12.0,
                 idle_sec: float = 6.0, rms_gate: float = 0.003) -> None:
        self.silence_sec = silence_sec
        self.max_sec = max_sec
        self.idle_sec = idle_sec
        self.rms_gate = rms_gate
        self.elapsed = 0.0
        self.silence = 0.0
        self.heard = False

    def feed(self, partial: str, rms: float, dt: float) -> bool:
        self.elapsed += dt
        if partial.strip():
            self.heard = True
        if rms >= self.rms_gate:
            self.silence = 0.0
        else:
            self.silence += dt
        if self.elapsed >= self.max_sec:
            return True
        if self.heard and self.silence >= self.silence_sec:
            return True
        if not self.heard and self.elapsed >= self.idle_sec:
            return True
        return False


def clean(text: str) -> str:
    """Лишние пробелы убрать, первую букву сделать заглавной (Vosk отдаёт строчными)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def rms_of(block: bytes) -> float:
    """Громкость блока int16 (0…1) — без numpy, каждый 4-й сэмпл."""
    a = array.array("h")
    a.frombytes(block[: len(block) - len(block) % 2])
    vals = a[::4]
    if not vals:
        return 0.0
    return math.sqrt(sum(x * x for x in vals) / len(vals)) / 32768.0


def append_log(text: str, path: Path | None = None) -> None:
    """Журнал распознанного: по умолчанию в папку данных корабля."""
    if path is None:
        try:
            from stamina.pilots import ROOT_DIR as DATA_DIR
            path = DATA_DIR / "voice_log.txt"
        except Exception:  # noqa: BLE001
            path = PROJECT_DIR / "voice_log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


# -- запись фразы в отдельном потоке --------------------------------------------
class Listener:
    """Запись одной фразы: микрофон и Vosk работают в фоне, экран читает события.

    Экран вызывает `start()` (по кнопке), затем периодически `poll()` и раскладывает
    события по интерфейсу. Запись заканчивается сама: тишина, лимит времени или `stop()`.
    """

    def __init__(self, *, model_path: Path | None = None, device: int | None = None,
                 silence_sec: float = 1.3, max_sec: float = 30.0, idle_sec: float = 8.0,
                 rms_gate: float = 0.003) -> None:
        self.model_path = model_path
        self.device = device
        self.silence_sec = silence_sec
        self.max_sec = max_sec
        self.idle_sec = idle_sec
        self.rms_gate = rms_gate
        self.events: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error = ""

    # -- управление
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Начать запись. False — не получилось (причина уже в очереди событий)."""
        if self.running:
            return True
        ok, why = ready()
        if not ok:
            self._push(("error", why))
            self._push(("done", None))
            return False
        self._stop.clear()
        self.error = ""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Прервать запись: то, что успело распознаться, ещё придёт событием `final`."""
        self._stop.set()

    def poll(self) -> list[tuple[str, object]]:
        """Забрать накопившиеся события (не блокирует)."""
        out: list[tuple[str, object]] = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def _push(self, event: tuple[str, object]) -> None:
        self.events.put(event)

    # -- поток
    def _run(self) -> None:
        try:
            self._push(("status", "loading"))
            model = load_model(self.model_path)
            if model is None:
                raise RuntimeError(f"нет модели Vosk в {models_dir()}")
            import sounddevice as sd
            import vosk

            rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
            splitter = PhraseSplitter(silence_sec=self.silence_sec, max_sec=self.max_sec,
                                      idle_sec=self.idle_sec, rms_gate=self.rms_gate)
            audio: queue.Queue = queue.Queue()
            step = BLOCK / SAMPLE_RATE

            def callback(indata, frames, _t, _status) -> None:
                audio.put(bytes(indata))

            parts: list[str] = []
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, dtype="int16",
                                   channels=1, device=self.device, callback=callback):
                self._push(("status", "listening"))
                while not self._stop.is_set():
                    try:
                        data = audio.get(timeout=0.25)
                    except queue.Empty:
                        if splitter.feed("", 0.0, step):
                            break
                        continue
                    if rec.AcceptWaveform(data):          # Vosk сам заметил паузу
                        text = clean(json.loads(rec.Result()).get("text", ""))
                        if text:
                            parts.append(text)
                        break
                    partial = json.loads(rec.PartialResult()).get("partial", "")
                    level = rms_of(data)
                    self._push(("level", level))
                    if partial.strip():
                        self._push(("partial", clean(partial)))
                    if splitter.feed(partial, level, step):
                        break
                tail = clean(json.loads(rec.FinalResult()).get("text", ""))
            if tail:
                parts.append(tail)
            self._push(("final", clean(" ".join(parts))))
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            self._push(("error", str(exc)))
        finally:
            self._push(("done", None))
