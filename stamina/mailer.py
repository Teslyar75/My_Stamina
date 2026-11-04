"""«ОТПРАВИТЬ»: письмо с вложением через почтовую программу пилота.

Windows: Simple MAPI (MAPISendMailW) с флагом MAPI_DIALOG — открывается окно
нового письма в Outlook/Thunderbird с уже приложенным файлом, отправляет сам
пилот. Linux/BSD: xdg-email --attach (Thunderbird, Evolution, KMail
прикладывают файл сами). Нет ни того ни другого — mailto: (тема и текст)
и папка с файлом, чтобы перетащить его в письмо. Ключей, паролей и серверов здесь нет.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

MAPI_DIALOG = 0x8
MAPI_LOGON_UI = 0x1
SUCCESS_SUCCESS = 0
MAPI_USER_ABORT = 1


def _mapi_send(path: Path, subject: str, body: str) -> int:
    import ctypes
    from ctypes import wintypes

    class MapiFileDescW(ctypes.Structure):
        _fields_ = [("ulReserved", wintypes.ULONG), ("flFlags", wintypes.ULONG),
                    ("nPosition", wintypes.ULONG), ("lpszPathName", wintypes.LPWSTR),
                    ("lpszFileName", wintypes.LPWSTR), ("lpFileType", ctypes.c_void_p)]

    class MapiMessageW(ctypes.Structure):
        _fields_ = [("ulReserved", wintypes.ULONG), ("lpszSubject", wintypes.LPWSTR),
                    ("lpszNoteText", wintypes.LPWSTR), ("lpszMessageType", wintypes.LPWSTR),
                    ("lpszDateReceived", wintypes.LPWSTR), ("lpszConversationID", wintypes.LPWSTR),
                    ("flFlags", wintypes.ULONG), ("lpOriginator", ctypes.c_void_p),
                    ("nRecipCount", wintypes.ULONG), ("lpRecips", ctypes.c_void_p),
                    ("nFileCount", wintypes.ULONG), ("lpFiles", ctypes.POINTER(MapiFileDescW))]

    lib = ctypes.WinDLL("mapi32.dll")
    send = lib.MAPISendMailW
    send.restype = wintypes.ULONG
    f = MapiFileDescW(0, 0, 0xFFFFFFFF, str(path), path.name, None)
    msg = MapiMessageW(0, subject, body, None, None, None, 0, None, 0, None, 1, ctypes.pointer(f))
    return int(send(None, 0, ctypes.byref(msg), MAPI_DIALOG | MAPI_LOGON_UI, 0))


def mailto_url(subject: str, body: str) -> str:
    q = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return "mailto:?" + q


def reveal(path: Path) -> None:
    """Показать файл в папке (Проводник выделит его)."""
    path = Path(path)
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


def xdg_email_send(path: Path, subject: str, body: str) -> bool:
    """Linux: новое письмо с вложением через xdg-email (xdg-utils). False — нет утилиты
    или она не смогла открыть почтовую программу."""
    exe = shutil.which("xdg-email")
    if not exe:
        return False
    try:
        rc = subprocess.run([exe, "--utf8", "--subject", subject, "--body", body, "--attach", str(path)],
                            timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    except (OSError, subprocess.SubprocessError):
        return False
    return rc == 0


def send_file(path: Path, subject: str, body: str = "") -> str:
    """Открыть письмо с вложением. Возвращает "mapi", "xdg", "cancel" или "mailto"
    ("mailto" — письмо без вложения, файл показан в папке)."""
    path = Path(path).resolve()
    if sys.platform.startswith("win") and not os.environ.get("STAR_TYPING_NO_MAPI"):
        try:
            rc = _mapi_send(path, subject, body)
            if rc == SUCCESS_SUCCESS:
                return "mapi"
            if rc == MAPI_USER_ABORT:
                return "cancel"
        except Exception:  # noqa: BLE001 — нет mapi32 или клиента
            pass
    elif not sys.platform.startswith(("win", "darwin")) and xdg_email_send(path, subject, body):
        return "xdg"
    webbrowser.open(mailto_url(subject, body))
    reveal(path)
    return "mailto"
