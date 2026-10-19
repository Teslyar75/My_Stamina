"""Движки озвучки: текст → голос. Общий слой для Ориона и читалки.

Зачем отдельный слой: раньше озвучка жила в двух местах и по-разному —
`stamina/voice/tts.py` (короткие реплики Ориона: сказал и забыл, лимит знаков) и
`stamina/english/tts.py` (английский модуль: рабочий процесс с очередью событий).
Читалке нужен второй вариант, но без привязки к английскому языку.

Протокол (по строкам, UTF-8, конец строки только \\n):

    Python → PS:  SAY|<id>|<rate>|<lang>|<base64 text>      STOP
    PS → Python:  VOICE|<случайный голос>   START|<id>
                  DONE|<id>|<ms>   CANCEL|<id>   ERR|<id>|<текст>   FATAL|<текст>

Голос выбирается по языку текста: `ru-*` для кириллицы, `en-*` для латиницы, либо явное
имя голоса (`lang` = `Microsoft Irina` — берётся как есть).

Интерфейс движка намеренно узкий, чтобы позже подключить edge-tts или Piper без правок
читалки:

    engine = make_engine("sapi")
    sid = engine.speak("текст", rate=-2)      # → id фразы
    for kind, sid, extra in engine.poll():    # start / done / cancel / error / dead
        ...
    engine.stop()                             # оборвать текущую фразу
    engine.close()                            # закрыть процесс

Ограничения на длину текста у движков нет: режут на предложения не они, а очередь чтения
(`stamina/voice/reader_tts.py`) — ради подсветки и управляемой паузы.
"""

from __future__ import annotations

import base64
import itertools
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

try:                       # проигрывание WAV: только Windows
    import winsound
except ImportError:        # pragma: no cover
    winsound = None        # type: ignore[assignment]

from stamina.i18n import t as _t


CYR = re.compile(r"[\u0400-\u04FF]")
LAT = re.compile(r"[A-Za-z]")

#: Соответствие «язык текста → шаблон голоса Windows».
VOICE_PATTERNS = {
    "ru": "ru-*",
    "uk": "uk-*",
    "en": "en-*",
    "de": "de-*",
    "fr": "fr-*",
    "es": "es-*",
    "": "*",          # любой включённый голос — последняя надежда
}


def guess_lang(text: str) -> str:
    """Язык текста по алфавиту: `ru` для кириллицы, `en` для латиницы, иначе ''."""
    sample = (text or "")[:400]
    if CYR.search(sample):
        return "ru"
    if LAT.search(sample):
        return "en"
    return ""


def voice_pattern(lang: str) -> str:
    """Шаблон голоса для языка (пустая строка — «любой»)."""
    lang = (lang or "").strip()
    if not lang:
        return "*"
    if lang in VOICE_PATTERNS:
        return VOICE_PATTERNS[lang]
    return lang if "*" in lang or " " in lang else lang


# --- PowerShell: один процесс, фразы по строкам --------------------------------------------

_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
function Out([string]$m) { [Console]::Out.WriteLine($m); [Console]::Out.Flush() }
try {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SetOutputToDefaultAudioDevice()
  $first = $s.GetInstalledVoices() | Where-Object { $_.Enabled } | Select-Object -First 1
  if ($first) { $s.SelectVoice($first.VoiceInfo.Name); Out ('VOICE|' + $first.VoiceInfo.Name) } else { Out 'VOICE|' }
} catch { Out ('FATAL|' + $_.Exception.Message); exit 1 }
# [Console]::In читает синхронно и блокирует цикл — берём StreamReader с ReadLineAsync
$in = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding($false)))
$task = $in.ReadLineAsync()
$cur = $null; $curId = ''; $sw = $null
while ($true) {
  if ($cur -ne $null -and $cur.IsCompleted) {
    Out ('DONE|' + $curId + '|' + $sw.ElapsedMilliseconds); $cur = $null; $curId = ''
  }
  if ($task.IsCompleted) {
    $line = $task.Result
    if ($line -eq $null) { break }
    $task = $in.ReadLineAsync()
    $line = $line.Trim()
    if ($line -eq '') { continue }
    $p = $line.Split('|', 5)
    if ($p[0] -eq 'STOP') {
      if ($cur -ne $null) { $s.SpeakAsyncCancelAll(); Out ('CANCEL|' + $curId); $cur = $null; $curId = '' }
      continue
    }
    if ($p[0] -eq 'SAY' -and $p.Length -eq 5) {
      try {
        if ($cur -ne $null) { $s.SpeakAsyncCancelAll(); Out ('CANCEL|' + $curId); $cur = $null }
        if ($s.State -eq 'Ready') { try { $s.SetOutputToDefaultAudioDevice() } catch { } }
        $s.Rate = [Math]::Max(-10, [Math]::Min(10, [int]$p[2]))
        $want = $p[3]
        $v = $null
        if ($want -ne '') {
          $v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and ($_.VoiceInfo.Name -eq $want -or $_.VoiceInfo.Culture.Name -like $want) } | Select-Object -First 1
        }
        if ($v -eq $null) { $v = $s.GetInstalledVoices() | Where-Object { $_.Enabled } | Select-Object -First 1 }
        if ($v -eq $null) { Out ('ERR|' + $p[1] + '|в Windows нет голосов. Параметры → Время и язык → Речь'); continue }
        $s.SelectVoice($v.VoiceInfo.Name)
        $txt = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p[4]))
        if ($txt.Trim() -eq '') { Out ('DONE|' + $p[1] + '|0'); continue }
        $curId = $p[1]; $sw = [Diagnostics.Stopwatch]::StartNew()
        $cur = $s.SpeakAsync($txt)
        Out ('START|' + $curId)
      } catch { Out ('ERR|' + $p[1] + '|' + $_.Exception.Message); $cur = $null; $curId = '' }
    }
    continue
  }
  Start-Sleep -Milliseconds 25
}
"""

_PS_VOICES = (r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object {
  [Console]::Out.WriteLine($_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name + '|' + $_.VoiceInfo.Gender)
}
""")


def _powershell() -> str:
    """Где PowerShell: PowerShell 5.1 или PowerShell 7."""
    for exe in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(exe)
        if found:
            return found
    return ""


def _run_ps(script: str, timeout: float = 12.0) -> str:
    """Выполнить короткий скрипт и вернуть stdout (без окна консоли)."""
    exe = _powershell()
    if not exe:
        return ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode("ascii")]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=flags)
    except Exception:  # noqa: BLE001
        return ""
    return res.stdout.decode("utf-8", "replace")


def windows_voices() -> list[tuple[str, str, str]]:
    """Установленные голоса Windows: [(имя, культура, пол)]. Пусто — Windows не наша или нет голосов."""
    if sys.platform != "win32":
        return []
    out = []
    for line in _run_ps(_PS_VOICES).splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and parts[0]:
            out.append((parts[0], parts[1], parts[2]))
    return out


class Engine:
    """Базовый движок: очередь отправки, события, оборвать/закрыть.

    Наследник обязан реализовать `_start(sid, text, rate, lang)` — отправить фразу в работу,
    и `_cancel()`. События кладутся в `self.events` как `(kind, sid, extra)`.
    """

    name = "engine"

    def __init__(self) -> None:
        self.events: queue.Queue = queue.Queue()
        self.voice = ""
        self.last_error = ""
        self.available = False
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    # -- общее ------------------------------------------------------------------------
    def why_unavailable(self) -> str:
        return self.last_error or _t("озвучка не настроена")

    def warm_up(self) -> None:
        """Прогрев в фоне: первый запуск процесса не должен попадать в первую фразу."""

    def poll(self) -> list[tuple]:
        """События движка, накопленные с прошлого вызова: (kind, sid, extra)."""
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out

    def speak(self, text: str, rate: int = 0, lang: str = "", voice: str = "") -> int:
        """Поставить фразу в работу. → id фразы (0 — не пошло, причина в событии 'error').

        `voice` — конкретный голос (пусто — подобрать по языку текста).
        """
        if not (text or "").strip():
            return 0
        with self._lock:
            if not self.available:
                self.events.put(("error", 0, self.why_unavailable()))
                return 0
            sid = next(self._ids)
            try:
                self._start(sid, text, int(rate), lang or guess_lang(text), voice)
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                self.events.put(("error", sid, str(exc)))
            return sid

    def stop(self) -> None:
        with self._lock:
            self._cancel()

    def close(self) -> None:
        self.stop()

    # -- для наследников --------------------------------------------------------------
    def _start(self, sid: int, text: str, rate: int, lang: str, voice: str = "") -> None:
        raise NotImplementedError

    def _cancel(self) -> None:
        raise NotImplementedError


class SapiEngine(Engine):
    """Голоса Windows (System.Speech) через один фоновый PowerShell — офлайн, без лимита.

    Голос подбирается по языку текста (`ru-*`, `en-*`, `de-*`) либо берётся по имени.
    """

    name = "sapi"

    def __init__(self) -> None:
        super().__init__()
        self.proc: subprocess.Popen | None = None
        self.available = sys.platform == "win32" and bool(_powershell())

    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", "replace").strip()
                kind, _, rest = line.partition("|")
                if kind == "VOICE":
                    self.voice = rest
                    if not rest:
                        self.last_error = _t("в Windows нет голосов. Параметры → Время и язык → Речь")
                elif kind == "FATAL":
                    self.last_error = rest
                    self.events.put(("error", 0, rest))
                elif kind in ("START", "DONE", "CANCEL"):
                    sid = rest.split("|")[0]
                    ms = rest.split("|")[1] if "|" in rest else ""
                    self.events.put((kind.lower(), int(sid) if sid.isdigit() else 0, ms))
                elif kind == "ERR":
                    sid, _, msg = rest.partition("|")
                    self.last_error = msg
                    self.events.put(("error", int(sid) if sid.isdigit() else 0, msg))
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.proc is proc:
                self.events.put(("dead", 0, self.last_error or _t("процесс озвучки завершился")))

    def _ensure(self) -> bool:
        if not self.available:
            return False
        if self.proc and self.proc.poll() is None:
            return True
        exe = _powershell()
        if not exe:
            self.available = False
            self.last_error = _t("нет PowerShell")
            return False
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.proc = subprocess.Popen(
                [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", base64.b64encode(_PS.encode("utf-16-le")).decode("ascii")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=flags)          # двоичный режим: никаких «\r\r\n»
            threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = _t("не удалось запустить PowerShell: {0}").format(exc)
            self.available = False
            return False

    def warm_up(self) -> None:
        threading.Thread(target=self._ensure, daemon=True).start()

    def _send(self, line: str) -> bool:
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = _t("канал озвучки оборвался: {0}").format(exc)
            self.proc = None
            return False

    def _start(self, sid: int, text: str, rate: int, lang: str, voice: str = "") -> None:
        if not self._ensure():
            self.events.put(("error", sid, self.why_unavailable()))
            return
        data = base64.b64encode(text.encode("utf-8")).decode("ascii")
        want = voice or ("" if lang in VOICE_PATTERNS[""] else voice_pattern(lang))
        line = f"SAY|{sid}|{max(-10, min(10, rate))}|{want}|{data}"
        if not self._send(line):                      # один перезапуск процесса
            if not (self._ensure() and self._send(line)):
                self.events.put(("error", sid, self.why_unavailable()))

    def _cancel(self) -> None:
        if self.proc and self.proc.poll() is None:
            self._send("STOP")

    def voices(self) -> list[tuple[str, str, str]]:
        """Голоса системы: [(имя, культура, пол)]."""
        return windows_voices()


class EspeakEngine(Engine):
    """Linux: espeak-ng / espeak / spd-say — офлайн, без лимита, по процессу на фразу."""

    name = "espeak"

    def __init__(self) -> None:
        super().__init__()
        self.cmd: list[str] | None = None
        if sys.platform != "win32":
            for exe, args in (("espeak-ng", ["-v", "ru"]), ("espeak", ["-v", "ru"]),
                              ("spd-say", ["-w", "-l", "ru"])):
                path = shutil.which(exe)
                if path:
                    self.cmd = [path, *args]
                    break
        self.available = self.cmd is not None
        self._proc: subprocess.Popen | None = None

    def why_unavailable(self) -> str:
        return self.last_error or (_t("нет программы озвучки. Установите: ") + LINUX_HINT)

    def _voice_arg(self, lang: str) -> list[str]:
        code = {"ru": "ru", "en": "en-us", "de": "de", "uk": "uk"}.get(lang or "ru", lang or "ru")
        return [code]

    def _start(self, sid: int, text: str, rate: int, lang: str, voice: str = "") -> None:
        base = list(self.cmd or [])
        if not base:
            self.events.put(("error", sid, self.why_unavailable()))
            return
        if "spd-say" in base[0]:
            cmd = base + ["-r", str(max(-100, min(100, rate * 10))), text]
        else:
            speed = max(-100, min(100, (rate - 5) * 8))
            cmd = [base[0], *self._voice_arg(lang), "-s", str(max(80, min(450, 175 + speed))), text]
        old = self._proc
        if old and old.poll() is None:
            old.terminate()
        t0 = time.monotonic()
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.events.put(("start", sid, ""))

        def wait(proc: subprocess.Popen) -> None:
            code = proc.wait()
            if code == 0:
                self.events.put(("done", sid, str(int((time.monotonic() - t0) * 1000))))
            else:
                self.events.put(("cancel", sid, ""))

        threading.Thread(target=wait, args=(self._proc,), daemon=True).start()

    def _cancel(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def voices(self) -> list[tuple[str, str, str]]:
        return []


LINUX_HINT = "sudo apt install espeak-ng   (Fedora: sudo dnf install espeak-ng · Arch: sudo pacman -S espeak-ng)"
# --- OneCore: современные голоса Windows (там есть и мужской русский) ----------------------

_PS_ONECORE = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
function Out([string]$m) { [Console]::Out.WriteLine($m); [Console]::Out.Flush() }
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime]
  $streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media, ContentType=WindowsRuntime]
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
      $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($task, $type) {
    $m = $asTask.MakeGenericMethod($type)
    $t = $m.Invoke($null, @($task))
    $t.Wait(-1) | Out-Null
    $t.Result
  }
  $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
} catch { Out ('FATAL|' + $_.Exception.Message); exit 1 }
foreach ($v in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
  Out ('VS|' + $v.DisplayName + '|' + $v.Language + '|' + $v.Gender)
}
Out 'VSEND'
$in = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding($false)))
$task = $in.ReadLineAsync()
while ($true) {
  if ($task.IsCompleted) {
    $line = $task.Result
    if ($line -eq $null) { break }
    $task = $in.ReadLineAsync()
    $line = $line.Trim()
    if ($line -eq '') { continue }
    $p = $line.Split('|', 5)
    if ($p[0] -eq 'SYN' -and $p.Length -eq 5) {
      try {
        $want = $p[2]
        $pick = $null
        if ($want -ne '') {
          $pick = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
            Where-Object { $_.DisplayName -eq $want -or $_.Language -like $want } | Select-Object -First 1
        }
        if ($pick -ne $null) { $synth.Voice = $pick }
        $speed = [double]1 + ([double]$p[3] * 0.12)
        if ($speed -lt 0.5) { $speed = 0.5 }
        if ($speed -gt 2.5) { $speed = 2.5 }
        $txt = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p[4]))
        $ssml = "<speak version='1.0' xml:lang='" + $synth.Voice.Language + "'><prosody rate='" +
                $speed.ToString([Globalization.CultureInfo]::InvariantCulture) + "'>" +
                [System.Security.SecurityElement]::Escape($txt) + '</prosody></speak>'
        $stream = Await ($synth.SynthesizeSsmlToStreamAsync($ssml)) $streamType
        $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
        $ms = New-Object System.IO.MemoryStream
        $net.CopyTo($ms)
        Out ('WAV|' + $p[1] + '|' + [Convert]::ToBase64String($ms.ToArray()))
      } catch { Out ('ERR|' + $p[1] + '|' + $_.Exception.Message) }
    }
    continue
  }
  Start-Sleep -Milliseconds 20
}
"""

# Голоса новых партий Windows — раньше старых: Mark и David свежее Zira, Aria/Guy свежее обоих.
_FRESHNESS = ("Aria", "Guy", "Jenny", "Mark", "Davis", "Steffan", "Christopher",
              "Eric", "Roger", "David", "Zira", "Hazel", "George", "Susan")


def pick_voice(voices: list[tuple[str, str, str]], lang: str = "", want: str = "",
               *, prefer_male: bool = True) -> str:
    """Голос из списка [(имя, язык, пол)]: по имени, по языку, с предпочтением мужского.

    Язык текста решает всё: английскую книгу не должен читать русский голос.
    """
    if not voices:
        return ""
    want = (want or "").strip()
    if want:
        for name, _lang, _gender in voices:
            if name == want:
                return name
        low = want.lower()
        for name, vlang, _gender in voices:
            if vlang.lower().startswith(low):
                return name
        for name, _lang, _gender in voices:
            if low in name.lower():
                return name
        return ""
    code = (lang or "").split("-")[0].lower()
    pool = [v for v in voices if v[1].split("-")[0].lower() == code] if code else list(voices)
    if not pool:
        return ""
    # Свежесть: голоса новых партий Windows читают живее древних ровесников Zira.
    def rank(item):
        name, _vlang, gender = item
        short = name.split()[-1]
        return (_FRESHNESS.index(short) if short in _FRESHNESS else len(_FRESHNESS),
                0 if (prefer_male and gender.lower() == "male") else 1)
    return sorted(pool, key=rank)[0][0]


class OneCoreEngine(Engine):
    """Голоса OneCore через один живой PowerShell: синтез там, проигрывание — в Python.

    Зачем так: System.Speech (SapiEngine) видит только старые голоса — русских женских
    Ирину и английскую Zira. Современные голоса, включая мужской русский Павел и
    английские Aria/Guy, лежат в OneCore, и дотянуться до них можно только через
    Windows.Media.SpeechSynthesis. Синтез — в постоянном процессе (быстро, без задержек
    на каждую фразу), а звук отдаём в winsound: его можно оборвать мгновенно.
    """

    name = "onecore"

    def __init__(self, fallback: Engine | None = None) -> None:
        super().__init__()
        self.proc: subprocess.Popen | None = None
        self.voices: list[tuple[str, str, str]] = []
        self.fallback = fallback if fallback is not None else SapiEngine()
        self.available = sys.platform == "win32" and winsound is not None and bool(_powershell())
        self._header = threading.Event()
        self._cur = 0                     # id фразы, которая сейчас звучит
        self._mix = threading.Lock()      # отдельный замок: _start зовут под self._lock
        self._spawn = threading.Lock()    # прогрев и первый запрос не запускают два процесса
        self._active = "onecore"

    # -- запуск процесса ----------------------------------------------------------------
    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", "replace").strip()
                kind, _, rest = line.partition("|")
                if kind == "VS":
                    name, _, tail = rest.partition("|")
                    vlang, _, gender = tail.partition("|")
                    if name:
                        self.voices.append((name, vlang, gender))
                elif kind == "VSEND":
                    self._header.set()
                elif kind == "WAV":
                    sid, _, data = rest.partition("|")
                    try:
                        wav = base64.b64decode(data)
                    except Exception:  # noqa: BLE001
                        continue
                    threading.Thread(target=self._play, args=(int(sid or 0), wav),
                                     daemon=True).start()
                elif kind == "ERR":
                    sid, _, msg = rest.partition("|")
                    self.last_error = msg
                    self.events.put(("error", int(sid) if sid.isdigit() else 0, msg))
                elif kind == "FATAL":
                    self.last_error = rest
                    self.events.put(("error", 0, rest))
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._header.set()
            if self.proc is proc:
                self.events.put(("dead", 0, self.last_error or _t("процесс озвучки завершился")))

    def _ensure(self) -> bool:
        with self._spawn:              # прогрев и первый запрос не запускают два процесса
            return self._spawn_process()

    def _spawn_process(self) -> bool:
        if not self.available:
            return False
        if self.proc and self.proc.poll() is None:
            return True
        exe = _powershell()
        if not exe:
            self.available = False
            self.last_error = _t("нет PowerShell")
            return False
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.proc = subprocess.Popen(
                [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", base64.b64encode(_PS_ONECORE.encode("utf-16-le")).decode("ascii")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=flags)
        except Exception as exc:  # noqa: BLE001
            self.last_error = _t("не удалось запустить PowerShell: {0}").format(exc)
            self.available = False
            return False
        self._header.clear()
        self.voices.clear()
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
        if not self._header.wait(8.0) and not self.last_error:
            self.last_error = _t("голоса OneCore не ответили")
        return True

    def warm_up(self) -> None:
        threading.Thread(target=self._ensure, daemon=True).start()

    def _send(self, line: str) -> bool:
        try:
            self.proc.stdin.write((line + "\n").encode("utf-8"))  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = _t("канал озвучки оборвался: {0}").format(exc)
            self.proc = None
            return False

    def _play(self, sid: int, wav: bytes) -> None:
        """Звук идёт из Python: winsound умеет и играть, и мгновенно замолкать."""
        if not sid:
            return
        with self._mix:
            self._cur = sid
        t0 = time.monotonic()
        self.events.put(("start", sid, ""))
        try:
            winsound.PlaySound(wav, winsound.SND_MEMORY)
        except Exception as exc:  # noqa: BLE001
            self.events.put(("error", sid, str(exc)))
            return
        with self._mix:
            replaced = self._cur != sid      # фразу заменили, пока звучала
        if replaced:
            self.events.put(("cancel", sid, ""))
        else:
            self.events.put(("done", sid, str(int((time.monotonic() - t0) * 1000))))

    # -- речь ---------------------------------------------------------------------------
    def _start(self, sid: int, text: str, rate: int, lang: str, voice: str = "") -> None:
        if not self._ensure():
            self._to_fallback(sid, text, rate, lang, voice)
            return
        pick = voice or pick_voice(self.voices, lang)
        if not pick:
            # В OneCore нет голоса этого языка: пусть читает тот движок, где он есть
            # (например английскую книгу — Zira из System.Speech).
            self._to_fallback(sid, text, rate, lang, voice)
            return
        self._active = "onecore"
        data = base64.b64encode(text.encode("utf-8")).decode("ascii")
        line = f"SYN|{sid}|{pick}|{max(-10, min(10, rate))}|{data}"
        if not self._send(line) and not (self._ensure() and self._send(line)):
            self.events.put(("error", sid, self.why_unavailable()))

    def _to_fallback(self, sid: int, text: str, rate: int, lang: str, voice: str) -> None:
        """Читать чужим движком, но события отдавать со своим id — очередь их поймёт."""
        self._active = "sapi"
        self.fallback._start(sid, text, rate, lang, voice)

    def _cancel(self) -> None:
        if self._active == "sapi":
            self.fallback._cancel()
            return
        with self._mix:
            self._cur = 0
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:  # noqa: BLE001
            pass

    def poll(self) -> list[tuple]:
        out = super().poll()
        if self.fallback is not None:
            out += self.fallback.poll()
        return out

    def close(self) -> None:
        self.stop()
        if self.fallback is not None:
            self.fallback.close()
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def voices_list(self) -> list[tuple[str, str, str]]:
        """Голоса OneCore: [(имя, язык, пол)] — пусто, пока процесс не ответил."""
        if not self.voices:
            self._ensure()
        return list(self.voices)


ENGINES = {"sapi": SapiEngine, "espeak": EspeakEngine, "onecore": OneCoreEngine, "auto": None}

_cache: dict[str, Engine] = {}


def make_engine(name: str = "auto", *, fresh: bool = False) -> Engine | None:
    """Движок по имени: `onecore`, `sapi`, `espeak`, `auto` (что доступно). Движки переиспользуются.

    `auto` на Windows — OneCore: там современные голоса (мужской русский Павел, английские
    Aria/Guy), а SapiEngine остаётся и запасным движком, и хозяином старого хранилища.
    `fresh=True` — всегда новый экземпляр (для тестов и смены настроек на ходу).
    """
    name = (name or "auto").strip().lower()
    if name == "auto":
        cls = OneCoreEngine if sys.platform == "win32" else EspeakEngine
    else:
        cls = ENGINES.get(name)
        if cls is None:
            cls = OneCoreEngine if sys.platform == "win32" else EspeakEngine
    if fresh or name not in _cache or not isinstance(_cache.get(name), cls):
        _cache[name] = cls()
    return _cache[name]


def voice_options() -> list[tuple[str, str]]:
    """Голоса для выбора пилотом: [(подпись, выбор)] — «по языку текста», затем OneCore, затем SAPI.

    Выбор хранится строкой `хранилище:имя` — по ней `make_engine_for` вернёт и движок, и голос.
    """
    rows: list[tuple[str, str, str, str]] = []
    if sys.platform == "win32":
        core = OneCoreEngine()
        try:
            for item in core.voices_list():
                rows.append(("onecore", *item))
        except Exception:  # noqa: BLE001
            pass
        try:
            for item in windows_voices():
                rows.append(("sapi", *item))
        except Exception:  # noqa: BLE001
            pass
    out = [(_t("по языку текста"), "")]
    for store, name, vlang, gender in rows:
        who = gender.lower()
        if who == "male":
            who = _t("мужской")
        elif who == "female":
            who = _t("женский")
        out.append((f"{name} · {vlang} · {who}", f"{store}:{name}"))
    return out


def make_engine_for(spec: str = "") -> tuple[Engine, str]:
    """Движок и голос по выбору пилота. Пусто — движок по системе, голос по языку текста."""
    spec = (spec or "").strip()
    if ":" in spec:
        store, name = spec.split(":", 1)
        store, name = store.strip().lower(), name.strip()
        if store == "sapi":
            return make_engine("sapi"), name
        if store == "onecore":
            return make_engine("onecore"), name
    return make_engine("auto"), ""


def available_engines() -> list[tuple[str, str]]:
    """[(имя, человеческое название)] из доступных на этой машине — для настроек читалки."""
    out = []
    if sys.platform == "win32" and _powershell():
        out.append(("sapi", _t("Голоса Windows (SAPI)")))
    elif sys.platform != "win32" and EspeakEngine().available:
        out.append(("espeak", _t("espeak-ng (Linux)")))
    return out
