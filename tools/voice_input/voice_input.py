"""Голосовой ввод: говорите в микрофон — распознанный текст попадает в буфер обмена.

Работает без интернета: vosk + sounddevice, русская модель в папке models/
(скачать: python tools/voice_input/get_model.py).

Запуск:
    python tools/voice_input/voice_input.py            # Enter -> фраза -> текст
    python tools/voice_input/voice_input.py --listen    # непрерывно, текст копится
    python tools/voice_input/voice_input.py --type      # набрать текст в активное окно

Это вспомогательная утилита для диалога с ассистентом, а не часть Star Typing.
Подробности — tools/voice_input/README.md

Заминка посреди речи фразу не закрывает: пауза от Vosk копится в общий текст, конец
фразы определяет PhraseSplitter — тишина 2,5 с (настраивается `--silence`), лимит
времени или клавиша. `--hold` вообще не рвёт фразу по тишине.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import os
import queue
import re
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "voice_log.txt"

SAMPLE_RATE = 16000
BLOCK = 4000                      # 0.25 с при 16 кГц
LANG = "ru"


# -- модель --------------------------------------------------------------------
def models_dir() -> Path:
    return Path(os.environ.get("STAR_TYPING_MODELS") or (PROJECT_DIR / "models"))


def find_model(root: Path | None = None, prefer: str = LANG) -> Path | None:
    """Папка модели Vosk: сначала с нужным языком (vosk-model-small-ru-...), иначе любая."""
    root = root or models_dir()
    if not root.is_dir():
        return None
    found = [p for p in sorted(root.iterdir())
             if p.is_dir() and p.name.startswith("vosk-model") and (p / "am").exists()]
    for p in found:
        if f"-{prefer}-" in p.name:
            return p
    return found[0] if found else None


def load_model(args):
    import vosk
    vosk.SetLogLevel(-1)
    path = Path(args.model) if args.model else find_model()
    if path is None or not path.is_dir():
        print(f"Нет модели Vosk в {models_dir()}")
        print("Скачайте её:  python tools/voice_input/get_model.py")
        return None
    print(f"Модель: {path.name} — загружаю…", flush=True)
    t0 = time.time()
    model = vosk.Model(str(path))
    print(f"Готово за {time.time() - t0:.1f} с.")
    return model


# -- логика фразы (без микрофона — тестируется отдельно) ------------------------
class PhraseSplitter:
    """Решает, когда фраза закончилась: после тишины, по лимиту или «молчит».

    Чистая логика: feed() получает распознанный частичный текст, громкость и
    длительность блока. Возвращает True, когда запись пора заканчивать.

    Заминка посреди речи — не конец фразы. После `soft_sec` тишины пилот получает
    предупреждение (`self.paused`), а запись закрывается только после `silence_sec`.
    `silence_sec = 0` — не рвать по тишине совсем (режим «говорите, пока не нажму СТОП»).
    `self.reason` объясняет, почему фраза закрыта: silence / max / idle / key.
    """

    def __init__(self, silence_sec: float = 2.5, max_sec: float = 120.0,
                 idle_sec: float = 12.0, rms_gate: float = 0.003,
                 soft_sec: float = 0.7) -> None:
        self.silence_sec = silence_sec
        self.max_sec = max_sec
        self.idle_sec = idle_sec
        self.rms_gate = rms_gate
        self.soft_sec = soft_sec
        self.elapsed = 0.0
        self.silence = 0.0
        self.heard = False
        self.paused = False          # тянется тишина: «…пауза 1,2 с»
        self.reason = ""             # почему закрыли фразу

    def feed(self, partial: str, rms: float, dt: float) -> bool:
        self.elapsed += dt
        if partial.strip():
            self.heard = True
        if rms >= self.rms_gate:
            self.silence = 0.0
        else:
            self.silence += dt
        self.paused = bool(self.heard and self.soft_sec > 0 and self.silence >= self.soft_sec)
        if self.elapsed >= self.max_sec:
            self.reason = "max"
            return True
        if self.heard and self.silence_sec > 0 and self.silence >= self.silence_sec:
            self.reason = "silence"
            return True
        if not self.heard and self.elapsed >= self.idle_sec:
            self.reason = "idle"
            return True
        return False

    def live_start(self) -> None:
        """Vosk услышал паузу и закрыл кусок сам: это ещё не конец фразы."""
        self.heard = True
        self.silence = 0.0
        self.paused = False


CAL_BLOCKS = 6        # блоков на замер фона перед первой фразой (~1,5 с)


def noise_gate(levels: list[float], base: float = 0.003, cap: float = 0.02) -> float:
    """Порог тишины по замерам фона: шумная комната — выше, тихая — как в настройках.

    Берём самый тихий блок (речь его не занижает) и поднимаем порог не более чем
    в 2,5 раза, но не выше `cap`: иначе своё же эхо начнёт рвать фразу.
    """
    if not levels:
        return base
    return max(base, min(cap, min(levels) * 2.5))


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


def append_log(text: str, path: Path = LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


# -- буфер обмена и ввод в окно -------------------------------------------------
def copy_to_clipboard(text: str) -> bool:
    if sys.platform == "win32":
        return _win_clipboard(text)
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b"]):
        try:
            if subprocess_run(cmd, text):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def subprocess_run(cmd: list[str], text: str) -> bool:
    import subprocess
    try:
        p = subprocess.run(cmd, input=text.encode("utf-8"), timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p.returncode == 0
    except FileNotFoundError:
        return False


def _win_clipboard(text: str) -> bool:
    """Кириллица в буфере обмена Windows — через ctypes (clip.exe портит кодировку)."""
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    # Без явных типов ctypes считает дескрипторы памяти 32-битными и падает на x64.
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    opened = False
    for _ in range(8):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.05)
    if not opened:
        return False
    try:
        if not user32.EmptyClipboard():
            return False
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(0x0002, len(data))       # GMEM_MOVEABLE
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):            # CF_UNICODETEXT
            kernel32.GlobalFree(handle)
            return False
        return True                                            # память теперь у буфера
    finally:
        user32.CloseClipboard()


_WIN_INPUT = None


def _win_input_types():
    """Структуры Windows для SendInput (собираются один раз, с проверкой размера)."""
    global _WIN_INPUT
    if _WIN_INPUT is None:
        import ctypes
        from ctypes import wintypes
        from types import SimpleNamespace

        class KeyBdInput(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", wintypes.WPARAM)]

        class MouseInput(ctypes.Structure):                  # нужен только для размера union
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", wintypes.WPARAM)]

        class HardwareInput(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class InputUnion(ctypes.Union):
            _fields_ = [("mi", MouseInput), ("ki", KeyBdInput), ("hi", HardwareInput)]

        class Input(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", InputUnion)]

        _WIN_INPUT = SimpleNamespace(Input=Input, KeyBdInput=KeyBdInput,
                                     InputUnion=InputUnion, size=ctypes.sizeof(Input))
    return _WIN_INPUT


def type_text(text: str) -> bool:
    """Набрать текст в активное окно (только Windows). Символы Unicode через SendInput."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    t = _win_input_types()
    send = ctypes.windll.user32.SendInput
    send.argtypes = [wintypes.UINT, ctypes.POINTER(t.Input), ctypes.c_int]
    send.restype = wintypes.UINT
    key_down, key_up = 0x0004, 0x0004 | 0x0002       # UNICODE, UNICODE|KEYUP

    inputs = []
    for ch in text.replace("\r", " ").replace("\n", " "):
        for flags in (key_down, key_up):
            inputs.append(t.Input(type=1, u=t.InputUnion(ki=t.KeyBdInput(0, ord(ch), flags, 0, 0))))

    sent = 0
    for i in range(0, len(inputs), 64):              # порциями, SendInput не любит огромные пачки
        chunk = inputs[i:i + 64]
        arr = (t.Input * len(chunk))(*chunk)
        sent += send(len(chunk), arr, t.size)
    return sent == len(inputs)


# -- кнопка «прервать» в консоли ------------------------------------------------
def key_pressed() -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt
            return bool(msvcrt.kbhit())
        import select
        return bool(select.select([sys.stdin], [], [], 0)[0])
    except Exception:  # noqa: BLE001
        return False


# -- микрофон -------------------------------------------------------------------
class Mic:
    def __init__(self, device=None) -> None:
        import sounddevice as sd
        self.q: queue.Queue = queue.Queue()
        self.stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK,
                                        dtype="int16", channels=1, device=device,
                                        callback=self._callback)

    def _callback(self, indata, frames, t, status) -> None:
        self.q.put(bytes(indata))

    def start(self) -> None:
        self.stream.start()

    def close(self) -> None:
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:  # noqa: BLE001
            pass

    def flush(self) -> None:
        """Выбросить накопленное: пока мы ждали Enter, микрофон уже что-то записал."""
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return

    def read(self, timeout: float = 0.5) -> bytes | None:
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


def list_devices() -> int:
    import sounddevice as sd
    print(sd.query_devices())
    print("\nУстройство ввода по умолчанию:", sd.query_devices(kind="input")["name"])
    return 0


def test_mic(device=None, seconds: float = 6.0) -> int:
    """Живая шкала громкости: сразу видно, слышит ли микрофон."""
    mic = Mic(device)
    mic.start()
    print(f"Говорите обычным голосом {seconds:.0f} с… (Ctrl+C — выход)")
    peak = 0.0
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            data = mic.read(0.2)
            if data is None:
                continue
            level = rms_of(data)
            peak = max(peak, level)
            print("\r" + ("#" * min(40, int(level * 150))).ljust(40) + f" {level:.4f}",
                  end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        mic.close()
    print()
    if peak < 0.002:
        print("Тишина. Проверьте устройство ввода (--devices), разрешение микрофона в Windows\n"
              "(Параметры → Конфиденциальность → Микрофон) и что он не выключен кнопкой.")
        return 1
    print(f"Микрофон слышит: пик {peak:.4f}. Запускайте утилиту без --test-mic.")
    return 0


def self_test() -> int:
    """Проверка «бортовых систем» голосового ввода — без микрофона."""
    import ctypes
    problems = 0

    print("1. Библиотеки")
    for name in ("vosk", "sounddevice"):
        try:
            __import__(name)
            print(f"   {name}: есть")
        except Exception as exc:  # noqa: BLE001
            print(f"   {name}: нет ({exc})")
            problems += 1

    print("2. Модель Vosk")
    path = find_model()
    if path is None:
        print(f"   нет в {models_dir()} — запустите: python tools/voice_input/get_model.py")
        problems += 1
    else:
        print(f"   {path.name}")

    print("3. Буфер обмена (кириллица)")
    if sys.platform == "win32":
        sample = "Проверка буфера: кириллица, тире — и «ёлка»."
        if copy_to_clipboard(sample):
            print("   записано — вставьте в блокнот, чтобы убедиться (Ctrl+V)")
        else:
            print("   не удалось записать")
            problems += 1
        print("4. Набор текста в окно (SendInput)")
        size = _win_input_types().size
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        if size == expected:
            print(f"   структура INPUT: {size} байт (как ожидается)")
        else:
            print(f"   структура INPUT: {size} байт, ожидалось {expected} — набор текста не сработает")
            problems += 1
    else:
        print("   (Windows-only)")

    print("\nИтог: " + ("всё в порядке, запускайте без --self-test" if not problems
                        else f"проблем: {problems}"))
    return 0 if not problems else 1


def capture_phrase(mic: Mic, rec, splitter: PhraseSplitter, *, abort_key: bool = False,
                   on_partial=None, on_pause=None) -> str:
    """Записать одну фразу до тишины, лимита времени или нажатой клавиши.

    Пауза от Vosk (`AcceptWaveform`) фразу **не** закрывает: распознанный кусок
    добавляется к общей фразе, а решение о конце принимает `splitter`.
    """
    parts: list[str] = []
    step = BLOCK / SAMPLE_RATE
    cal: list[float] = []
    while True:
        data = mic.read()
        if abort_key and key_pressed():
            print()
            splitter.reason = splitter.reason or "key"
            break
        if data is None:
            if splitter.feed("", 0.0, step):
                break
            continue
        level = rms_of(data)
        if len(cal) < CAL_BLOCKS:                    # замер фона: тихий голос не должен выпадать
            cal.append(level)
            if len(cal) == CAL_BLOCKS:
                splitter.rms_gate = noise_gate(cal, splitter.rms_gate)
        if rec.AcceptWaveform(data):                 # Vosk заметил паузу — но фразу продолжаем
            text = clean(json.loads(rec.Result()).get("text", ""))
            if text:
                parts.append(text)
                splitter.live_start()
            if splitter.feed("", level, step):
                break
            continue
        partial = json.loads(rec.PartialResult()).get("partial", "")
        if partial and on_partial:
            on_partial(partial)
        if splitter.feed(partial, level, step):
            break
        if splitter.paused and on_pause:
            on_pause(splitter.silence)
    tail = clean(json.loads(rec.FinalResult()).get("text", ""))
    if tail:
        parts.append(tail)
    return clean(" ".join(parts))


STOP_WORDS = {"silence": "тишина", "max": "лимит времени",
              "idle": "речи не было", "key": "клавиша"}


def stop_reason(splitter: PhraseSplitter) -> str:
    """Человеческая причина: почему фраза закрылась (видно в консоли)."""
    word = STOP_WORDS.get(splitter.reason)
    if not word:
        return ""
    if splitter.reason == "silence":
        return f"{word} {splitter.silence_sec:g} с"
    return word


# -- вывод ----------------------------------------------------------------------
def type_with_delay(text: str, delay: float) -> None:
    """Набрать текст в активное окно, дав время переключиться из консоли в чат."""
    if delay > 0:
        print(f"Наберу текст через {delay:.0f} с — переключитесь в окно чата…")
        for i in range(int(delay), 0, -1):
            print(f"  {i}…", flush=True)
            time.sleep(1)
    print("Набираю: " + ("ок" if type_text(text) else "не получилось (только Windows)"))


def handle(text: str, args, accumulated: list[str]) -> None:
    """Одна готовая фраза: показать, записать в журнал, отдать в буфер обмена."""
    if not text:
        print("(ничего не разобрал)")
        return
    append_log(text)
    print("Распознано: " + text)

    if args.listen:
        accumulated.append(text)                 # в непрерывном режиме копим весь текст,
        full = " ".join(accumulated)             # чтобы в буфере всегда лежала вся диктовка
        if args.copy:
            ok = copy_to_clipboard(full)
            print(f"В буфере ({len(full)} симв.): " + ("да" if ok else "не получилось"))
        if args.type:
            type_text(text + " ")
        print("В чат: Ctrl+V")
    else:
        if args.copy:
            print("В буфере: " + ("да" if copy_to_clipboard(text) else "не получилось"))
        if args.type:
            type_with_delay(text, args.delay)
        print("В чат: Ctrl+V")


def run(args) -> int:
    if args.devices:
        return list_devices()
    if args.test_mic:
        return test_mic(args.device)
    if args.self_test:
        return self_test()

    model = load_model(args)
    if model is None:
        return 2

    import vosk
    vosk.SetLogLevel(-1)

    mic = Mic(args.device)
    mic.start()
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    dev = "микрофон по умолчанию" if args.device is None else f"устройство {args.device}"
    print(f"\nСлушаю: {dev}. Выход — Ctrl+C.\n")

    accumulated: list[str] = []
    if args.once:                                  # одна фраза: удобно для ярлыка и проверок
        sp = new_splitter(args)
        try:
            text = capture_phrase(mic, rec, sp, on_pause=None if args.quiet else show_pause)
        finally:
            mic.close()
        if not args.quiet and stop_reason(sp):
            print(f"  (фраза закрыта: {stop_reason(sp)})")
        handle(text, args, accumulated)
        return 0
    try:
        if args.listen:
            print("Непрерывный режим: говорите, фразы сами попадают в буфер обмена.")
            print("Enter — начать новую порцию текста (буфер очистится).\n")
            while True:
                sp = new_splitter(args)
                text = capture_phrase(mic, rec, sp, on_pause=None if args.quiet else show_pause)
                if not args.quiet and stop_reason(sp):
                    print(f"  (фраза закрыта: {stop_reason(sp)})")
                handle(text, args, accumulated)
                if key_pressed():
                    sys.stdin.read(1)
                    accumulated.clear()
                    print("--- новая порция ---")
                rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        else:
            print("Enter — начать фразу (говорите; Enter ещё раз — прервать).\n")
            while True:
                try:
                    input("> ")
                except EOFError:
                    break
                mic.flush()
                sp = new_splitter(args)
                text = capture_phrase(mic, rec, sp, abort_key=True,
                                      on_partial=None if args.quiet else show_partial,
                                      on_pause=None if args.quiet else show_pause)
                if not args.quiet and stop_reason(sp):
                    print(f"  (фраза закрыта: {stop_reason(sp)})")
                handle(text, args, accumulated)
                rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    except KeyboardInterrupt:
        print("\nВыход.")
    finally:
        mic.close()
    return 0


def new_splitter(args) -> PhraseSplitter:
    """Разделитель фраз по аргументам. `--hold`: по тишине не рвём вовсе."""
    silence = 0.0 if getattr(args, "hold", False) else args.silence
    return PhraseSplitter(silence_sec=silence, max_sec=args.max_sec,
                          idle_sec=args.idle, rms_gate=args.gate,
                          soft_sec=getattr(args, "soft", 0.7))


def show_partial(text: str) -> None:
    print("\r… " + text[:100] + " " * 10, end="", flush=True)


def show_pause(silence: float) -> None:
    """Тишина тянется: сказать пилоту, что фраза ещё пишется и не закроется сразу."""
    print(f"\r… пауза {silence:.1f} с — говорите, не закрываю " + " " * 6, end="", flush=True)


# -- аргументы -------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voice_input.py",
        description="Голосовой ввод офлайн (Vosk): речь -> текст в буфер обмена.",
        formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--listen", action="store_true",
                   help="непрерывно: фразы распознаются сами, текст копится в буфере")
    p.add_argument("--once", action="store_true",
                   help="записать одну фразу без ожидания Enter и выйти")
    p.add_argument("--type", action="store_true",
                   help="набрать текст в активное окно (только Windows)")
    p.add_argument("--delay", type=float, default=3.0,
                   help="пауза перед набором, чтобы успеть переключить окно (по умолчанию 3)")
    p.add_argument("--device", type=int, default=None, help="номер устройства ввода")
    p.add_argument("--devices", action="store_true", help="показать список устройств и выйти")
    p.add_argument("--test-mic", action="store_true",
                   help="живая шкала громкости: слышит ли микрофон (6 с)")
    p.add_argument("--self-test", action="store_true",
                   help="проверить библиотеки, модель, буфер обмена и набор текста (без микрофона)")
    p.add_argument("--model", default=None, help="путь к папке модели Vosk")
    p.add_argument("--silence", type=float, default=2.5,
                   help="тишина в конце фразы, с (заминка короче — фраза продолжается)")
    p.add_argument("--soft", type=float, default=0.7,
                   help="после какой тишины подсказывать «…пауза», с")
    p.add_argument("--hold", action="store_true",
                   help="не рвать фразу по тишине: только клавиша или лимит времени")
    p.add_argument("--max-sec", type=float, default=120.0, help="самая длинная фраза, с")
    p.add_argument("--idle", type=float, default=12.0, help="ждать речи не дольше, с")
    p.add_argument("--gate", type=float, default=0.003, help="порог тишины (0…1): ниже него — пауза")
    p.add_argument("--no-copy", dest="copy", action="store_false", help="не трогать буфер обмена")
    p.add_argument("--quiet", action="store_true", help="не показывать распознавание на лету")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")       # кириллица в консоли Windows
        except Exception:  # noqa: BLE001
            pass
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ModuleNotFoundError as exc:
        print(f"Не хватает библиотеки: {exc.name}")
        print("Установите:  pip install vosk sounddevice")
        return 3


if __name__ == "__main__":
    sys.exit(main())
