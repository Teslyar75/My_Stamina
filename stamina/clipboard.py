"""System clipboard helpers.

On Windows the text goes straight through the Win32 API: it stays on the
clipboard after the app loses focus or exits, and a busy/unavailable clipboard
returns False instead of crashing Tk (Tk's clipboard_clear can access-violate
when the clipboard is unavailable in the session).
"""
from __future__ import annotations

import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes as W
    
    def set_clipboard_text(text: str) -> bool:
        u = ctypes.WinDLL("user32", use_last_error=True); k = ctypes.WinDLL("kernel32", use_last_error=True)
        u.OpenClipboard.argtypes=[W.HWND]; u.SetClipboardData.argtypes=[W.UINT, W.HANDLE]; u.SetClipboardData.restype=W.HANDLE
        k.GlobalAlloc.argtypes=[W.UINT, ctypes.c_size_t]; k.GlobalAlloc.restype=W.HGLOBAL
        k.GlobalLock.argtypes=[W.HGLOBAL]; k.GlobalLock.restype=ctypes.c_void_p; k.GlobalUnlock.argtypes=[W.HGLOBAL]; k.GlobalFree.argtypes=[W.HGLOBAL]
        data = (text + "\0").encode("utf-16-le")
        if not u.OpenClipboard(None): return False
        try:
            u.EmptyClipboard()
            h = k.GlobalAlloc(0x0002, len(data))
            if not h: return False
            p = k.GlobalLock(h); ctypes.memmove(p, data, len(data)); k.GlobalUnlock(h)
            if not u.SetClipboardData(13, h): k.GlobalFree(h); return False
            return True
        finally:
            u.CloseClipboard()

    def get_clipboard_text():
        u = ctypes.WinDLL("user32"); k = ctypes.WinDLL("kernel32")
        u.GetClipboardData.restype=W.HANDLE; k.GlobalLock.argtypes=[W.HGLOBAL]; k.GlobalLock.restype=ctypes.c_void_p; k.GlobalUnlock.argtypes=[W.HGLOBAL]
        if not u.OpenClipboard(None): return None
        try:
            h=u.GetClipboardData(13)
            if not h: return None
            p=k.GlobalLock(h); s=ctypes.wstring_at(p); k.GlobalUnlock(h); return s
        finally: u.CloseClipboard()


def set_text(text: str, widget=None) -> bool:
    """Copy text; widget is the Tk fallback on non-Windows systems."""
    try:
        if sys.platform == "win32":
            return bool(set_clipboard_text(text))
        if widget is None:
            return False
        widget.clipboard_clear()
        widget.clipboard_append(text)
        widget.update_idletasks()
        return True
    except Exception:  # noqa: BLE001
        return False


def get_text(widget=None):
    try:
        if sys.platform == "win32":
            return get_clipboard_text()
        return widget.clipboard_get() if widget is not None else None
    except Exception:  # noqa: BLE001
        return None
