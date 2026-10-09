"""Озвучка без интернета: голос Windows (System.Speech, например Microsoft Zira) через один
фоновый процесс PowerShell. Без дополнительных библиотек. На других ОС — недоступна.

Протокол (по строкам, UTF-8, конец строки только \\n):
  Python → PS:  SAY|<id>|<rate>|<base64 text>      STOP
  PS → Python:  VOICE|<name>   START|<id>   DONE|<id>|<ms>   CANCEL|<id>   ERR|<id>|<текст>
События для интерфейса кладутся в очередь self.events и забираются из главного потока (poll()).

ВАЖНО (причина «немого» голоса в прошлой версии): stdin открывался в текстовом режиме, и Windows
превращала «\\r\\n» в «\\r\\r\\n». PowerShell читал лишнюю пустую строку, а на каждую строку
скрипт делал SpeakAsyncCancelAll() — то есть фраза отменялась через миллисекунды после старта.
Теперь канал двоичный, пустые строки игнорируются, а конец фразы подтверждается событием DONE.
"""
from __future__ import annotations

import base64
import itertools
import queue
import subprocess
import sys
import threading

_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
function Out([string]$m) { [Console]::Out.WriteLine($m); [Console]::Out.Flush() }
try {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
  if ($v) { $s.SelectVoice($v.VoiceInfo.Name); Out ('VOICE|' + $v.VoiceInfo.Name) } else { Out 'VOICE|' }
  $s.SetOutputToDefaultAudioDevice()
} catch { Out ('FATAL|' + $_.Exception.Message); exit 1 }
# Не [Console]::In: его ReadLineAsync на деле синхронный и блокирует цикл (не было бы DONE)
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
    $p = $line.Split('|', 4)
    if ($p[0] -eq 'STOP') {
      if ($cur -ne $null) { $s.SpeakAsyncCancelAll(); Out ('CANCEL|' + $curId); $cur = $null; $curId = '' }
      continue
    }
    if ($p[0] -eq 'SAY' -and $p.Length -eq 4) {
      try {
        if ($cur -ne $null) { $s.SpeakAsyncCancelAll(); Out ('CANCEL|' + $curId); $cur = $null }
        if ($s.State -eq 'Ready') { try { $s.SetOutputToDefaultAudioDevice() } catch { } }  # если сменили устройство вывода
        $s.Rate = [Math]::Max(-10, [Math]::Min(10, [int]$p[2]))
        $t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p[3]))
        $curId = $p[1]; $sw = [Diagnostics.Stopwatch]::StartNew()
        $cur = $s.SpeakAsync($t)
        Out ('START|' + $curId)
      } catch { Out ('ERR|' + $p[1] + '|' + $_.Exception.Message); $cur = $null; $curId = '' }
    }
    continue
  }
  Start-Sleep -Milliseconds 30
}
"""


class TTS:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.voice = ""
        self.last_error = ""
        self.available = sys.platform == "win32"
        self.events: queue.Queue = queue.Queue()   # (kind, id, extra)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def why_unavailable(self) -> str:
        if sys.platform != "win32":
            return "озвучка работает только в Windows"
        return self.last_error or "голос Windows не запустился"

    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", "replace").strip()
                kind, _, rest = line.partition("|")
                if kind == "VOICE":
                    self.voice = rest
                    if not rest:
                        self.last_error = "в Windows нет английского голоса (нужен Microsoft Zira / David)"
                elif kind == "FATAL":
                    self.last_error = rest
                    self.events.put(("error", 0, rest))
                elif kind in ("START", "DONE", "CANCEL"):
                    sid = rest.split("|")[0]
                    self.events.put((kind.lower(), int(sid) if sid.isdigit() else 0, ""))
                elif kind == "ERR":
                    sid, _, msg = rest.partition("|")
                    self.last_error = msg
                    self.events.put(("error", int(sid) if sid.isdigit() else 0, msg))
        except Exception:
            pass
        finally:
            if self.proc is proc:
                self.events.put(("dead", 0, self.last_error or "процесс озвучки завершился"))

    def _ensure(self) -> bool:
        if not self.available:
            return False
        if self.proc and self.proc.poll() is None:
            return True
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", base64.b64encode(_PS.encode("utf-16-le")).decode("ascii")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=flags)  # двоичный режим: никаких «\r\r\n»
            threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"не удалось запустить PowerShell: {exc}"
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
            self.last_error = f"канал озвучки оборвался: {exc}"
            self.proc = None
            return False

    def speak(self, text: str, rate: int = 0) -> int:
        """rate: −10…10 (0 — обычная, −4 — медленно). Возвращает id фразы (0 — не отправлено,
        причина в событии ('error', 0, текст))."""
        if not text:
            return 0
        with self._lock:
            if not self._ensure():
                self.events.put(("error", 0, self.why_unavailable()))
                return 0
            sid = next(self._ids)
            data = base64.b64encode(text.encode("utf-8")).decode("ascii")
            if not self._send(f"SAY|{sid}|{int(rate)}|{data}"):
                # одна попытка перезапуска процесса
                if not (self._ensure() and self._send(f"SAY|{sid}|{int(rate)}|{data}")):
                    self.events.put(("error", sid, self.why_unavailable()))
            return sid

    def poll(self) -> list[tuple]:
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def stop(self) -> None:
        with self._lock:
            if self.proc and self.proc.poll() is None:
                self._send("STOP")

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()  # type: ignore[union-attr]
                self.proc.terminate()
            except Exception:
                pass
