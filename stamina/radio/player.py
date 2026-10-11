"""Потоковый приёмник: mpv (предпочтительно) или ffplay через subprocess.

Без pip-зависимостей — только внешняя программа в PATH (как espeak-ng).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable


def backend_name() -> str | None:
    if shutil.which("mpv"):
        return "mpv"
    if shutil.which("ffplay"):
        return "ffplay"
    return None


def backend_ok() -> bool:
    return backend_name() is not None


class StreamPlayer:
    """Фоновый проигрыватель HTTP-потока (MP3/AAC/HLS через mpv/ffplay)."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._ipc: Path | None = None
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._playing = False
        self._volume = 70
        self._ducked = False
        self._vol_before_duck = 70
        self._url = ""
        self._title = ""
        self._meta = ""
        self._on_meta: Callable[[str], None] | None = None
        self._backend = backend_name()

    @property
    def playing(self) -> bool:
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                self._playing = False
            return self._playing

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def track(self) -> str:
        return self._meta

    @property
    def url(self) -> str:
        return self._url

    def set_meta_callback(self, cb: Callable[[str], None] | None) -> None:
        self._on_meta = cb

    def play(self, url: str, *, volume: int | None = None) -> bool:
        url = (url or "").strip()
        if not url:
            return False
        if volume is not None:
            self._volume = max(0, min(100, int(volume)))
        self.stop()
        self._url = url
        self._meta = ""
        self._backend = backend_name()
        if self._backend == "mpv":
            return self._play_mpv(url)
        if self._backend == "ffplay":
            return self._play_ffplay(url)
        return False

    def stop(self) -> None:
        with self._lock:
            proc, ipc = self._proc, self._ipc
            self._proc = None
            self._ipc = None
            self._playing = False
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        if ipc is not None:
            try:
                ipc.unlink(missing_ok=True)  # type: ignore[call-arg]
            except TypeError:
                try:
                    if ipc.exists():
                        ipc.unlink()
                except OSError:
                    pass
            except OSError:
                pass

    def set_volume(self, vol: int) -> None:
        self._volume = max(0, min(100, int(vol)))
        if self._ducked:
            return
        self._send_mpv(["set_property", "volume", self._volume])

    def duck(self, level: int = 15) -> None:
        if self._ducked or not self.playing:
            return
        self._ducked = True
        self._vol_before_duck = self._volume
        self._send_mpv(["set_property", "volume", max(0, min(100, level))])
        # ffplay: перезапуск с тише — слишком грубо; просто пауза через stop+flag
        if self._backend == "ffplay" and self._proc:
            # ffplay не умеет volume на лету — приглушаем стопом (unduck перезапустит)
            self._ffplay_paused = True
            self.stop()
            self._playing = False

    def unduck(self) -> None:
        if not self._ducked:
            return
        self._ducked = False
        vol = self._vol_before_duck
        self._volume = vol
        if getattr(self, "_ffplay_paused", False) and self._url:
            self._ffplay_paused = False
            self.play(self._url, volume=vol)
            return
        self._send_mpv(["set_property", "volume", vol])

    def toggle(self) -> bool:
        if self.playing:
            self.stop()
            return False
        if self._url:
            return self.play(self._url, volume=self._volume)
        return False

    # ------------------------------------------------------------------ mpv
    def _play_mpv(self, url: str) -> bool:
        sock = Path(tempfile.gettempdir()) / f"stamina-radio-{os.getpid()}.sock"
        try:
            sock.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if sock.exists():
                try:
                    sock.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        ipc = str(sock) if sys.platform != "win32" else r"\\.\pipe\stamina-radio-" + str(os.getpid())
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        cmd = [
            "mpv", "--no-video", "--quiet", "--no-terminal",
            f"--volume={self._volume}",
            f"--input-ipc-server={ipc}",
            "--idle=yes",
            url,
        ]
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, creationflags=flags,
            )
        except OSError:
            return False
        self._proc = proc
        self._ipc = sock if sys.platform != "win32" else None
        self._ipc_name = ipc
        self._playing = True
        # дать сокету подняться
        threading.Thread(target=self._mpv_boot, args=(url,), daemon=True).start()
        return True

    def _mpv_boot(self, url: str) -> None:
        time.sleep(0.35)
        self._send_mpv(["observe_property", 1, "metadata"])
        # url уже в cmdline; на всякий случай
        deadline = time.time() + 8
        while time.time() < deadline and self.playing:
            meta = self._ask_mpv(["get_property", "metadata"])
            if isinstance(meta, dict):
                title = meta.get("icy-title") or meta.get("title") or ""
                if title and title != self._meta:
                    self._meta = str(title)
                    cb = self._on_meta
                    if cb:
                        try:
                            cb(self._meta)
                        except Exception:  # noqa: BLE001
                            pass
            time.sleep(1.2)
            if self._proc is not None and self._proc.poll() is not None:
                self._playing = False
                break

    def _send_mpv(self, command: list) -> None:
        self._ask_mpv(command)

    def _ask_mpv(self, command: list):
        ipc = getattr(self, "_ipc_name", None)
        if not ipc or not self._playing:
            return None
        payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
        try:
            if sys.platform == "win32":
                # Named pipe: открыть на запись/чтение
                with open(ipc, "r+b", buffering=0) as f:
                    f.write(payload)
                    try:
                        line = f.readline()
                        if line:
                            return json.loads(line.decode("utf-8", errors="replace")).get("data")
                    except Exception:  # noqa: BLE001
                        return None
            else:
                import socket
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.4)
                s.connect(ipc)
                s.sendall(payload)
                try:
                    data = s.recv(8192)
                    s.close()
                    if data:
                        return json.loads(data.decode("utf-8", errors="replace").split("\n")[0]).get("data")
                except Exception:  # noqa: BLE001
                    try:
                        s.close()
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            return None
        return None

    # ------------------------------------------------------------------ ffplay
    def _play_ffplay(self, url: str) -> bool:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        # volume у ffplay: -volume 0..100
        cmd = [
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-volume", str(self._volume), url,
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, creationflags=flags,
            )
        except OSError:
            return False
        self._playing = True
        return True
