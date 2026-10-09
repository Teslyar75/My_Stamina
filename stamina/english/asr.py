"""Распознавание речи без интернета: Vosk (малая английская модель в папке models/ проекта,
скачивается scripts/download_vosk_model.ps1)
+ sounddevice для микрофона. Если чего-то нет — available() == False и интерфейс
переходит на самооценку (SPEC §0). События отдаются через очередь: UI опрашивает poll()."""
from __future__ import annotations

import array
import json
import math
import queue
import threading
import time

from . import paths


class ASR:
    def __init__(self) -> None:
        self.model = None
        self.status = "не загружен"
        self.events: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self.listening = False
        self._loading = False

    # -- доступность ---------------------------------------------------------
    def libs_ok(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            import vosk  # noqa: F401
            return True
        except Exception:
            return False

    def available(self) -> bool:
        return self.libs_ok() and paths.vosk_model_dir() is not None

    def why_unavailable(self) -> str:
        if not self.libs_ok():
            return "нет библиотек vosk / sounddevice (pip install vosk sounddevice)"
        if paths.vosk_model_dir() is None:
            return f"нет модели Vosk в {paths.MODELS_DIR}"
        return self.status

    def load_async(self) -> None:
        if self.model is not None or self._loading or not self.available():
            return
        self._loading = True

        def work():
            try:
                import vosk
                vosk.SetLogLevel(-1)
                self.status = "загрузка модели…"
                self.model = vosk.Model(str(paths.vosk_model_dir()))
                self.status = "готов"
            except Exception as exc:  # noqa: BLE001
                self.status = f"ошибка: {exc}"
            finally:
                self._loading = False
        threading.Thread(target=work, daemon=True).start()

    # -- запись ----------------------------------------------------------------
    def listen(self, max_sec: float = 9.0) -> bool:
        """Начать запись. События: ('partial', text), ('final', [alternatives]), ('error', msg)."""
        if self.listening:
            return False
        if not self.available():
            self.events.put(("error", self.why_unavailable()))
            return False
        self._stop.clear()
        self.listening = True
        threading.Thread(target=self._run, args=(max_sec,), daemon=True).start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self, max_sec: float) -> None:
        try:
            import sounddevice as sd
            import vosk
            t0 = time.time()
            while self.model is None and time.time() - t0 < 20:
                if not self._loading:
                    self.load_async()
                time.sleep(0.1)
            if self.model is None:
                raise RuntimeError("модель не загрузилась")
            rec = vosk.KaldiRecognizer(self.model, 16000)
            rec.SetMaxAlternatives(5)
            q: queue.Queue = queue.Queue()

            peak = [0.0]
            last_lvl = [0.0]

            def cb(indata, frames, t, status):
                b = bytes(indata)
                q.put(b)
                try:  # уровень входа (RMS) для индикатора — без numpy/audioop
                    a = array.array("h")
                    a.frombytes(b[: len(b) - len(b) % 2])
                    n = len(a) or 1
                    rms = math.sqrt(sum(x * x for x in a[::4]) / max(1, n // 4)) / 32768.0
                    peak[0] = max(peak[0], rms)
                    now = time.time()
                    if now - last_lvl[0] > 0.06:
                        last_lvl[0] = now
                        self.events.put(("level", rms))
                except Exception:
                    pass
            alts: list[str] = []
            heard_any = False
            with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1, callback=cb):
                self.events.put(("started", ""))
                start = time.time()
                while not self._stop.is_set() and time.time() - start < max_sec:
                    try:
                        data = q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        alts = _alts(rec.Result())
                        if any(a.strip() for a in alts):
                            break  # конец фразы (пауза)
                    else:
                        p = json.loads(rec.PartialResult()).get("partial", "")
                        if p:
                            heard_any = True
                            self.events.put(("partial", p))
            self.events.put(("processing", ""))
            if not any(a.strip() for a in alts):
                alts = _alts(rec.FinalResult())
            if peak[0] < 0.004 and not any(a.strip() for a in alts):
                self.events.put(("silent", "Микрофон не слышит звук — проверьте устройство ввода в Windows "
                                           "(Параметры → Звук → Ввод) и доступ к микрофону"))
            self.events.put(("final", [a for a in alts if a.strip()] or ([] if not heard_any else [])))
        except Exception as exc:  # noqa: BLE001
            self.events.put(("error", str(exc)))
        finally:
            self.listening = False

    def poll(self) -> list[tuple]:
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out


def _alts(raw: str) -> list[str]:
    try:
        d = json.loads(raw)
    except ValueError:
        return []
    if "alternatives" in d:
        return [a.get("text", "") for a in d["alternatives"]]
    return [d.get("text", "")]
