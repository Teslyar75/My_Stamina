"""Общий «компоновщик»: вставка текста и картинок из буфера, снимки окна, миниатюры.

Один код для чата Ориона и для отсека «Документация»: экраны не повторяют
работу с буфером обмена, Pillow и превью, а только решают, куда положить
результат (приложение к сообщению или картинка в документе).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import shots, theme
from stamina.i18n import t as _t
from stamina.theme import BG, MUTED, px

IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
NO_PILLOW = "Снимки недоступны: нет Pillow (pip install Pillow)"


def clipboard_image():
    """Картинка из буфера обмена (Win+Shift+S или файл из Проводника) или None."""
    if not shots.available():
        return None
    return shots.grab_clipboard()


def clipboard_text(widget) -> str:
    """Текст из буфера обмена ('' — пусто или там не текст)."""
    try:
        return widget.clipboard_get() or ""
    except tk.TclError:
        return ""


def window_image():
    """Снимок активного окна (или всего экрана) или None."""
    if not shots.available():
        return None
    return shots.grab_active_window() or shots.grab_screen()


def pick_image_files(parent, title: str | None = None) -> tuple:
    """Диалог «выбрать картинки»: кортеж путей (пустой — отмена)."""
    from tkinter import filedialog
    return filedialog.askopenfilenames(
        parent=parent, title=title or _t("Приложить картинки"),
        filetypes=[(_t("Картинки"), " ".join("*" + e for e in IMAGE_TYPES)),
                   (_t("Все файлы"), "*.*")]) or ()


def image_paths(names) -> list[Path]:
    """Только картинки из списка путей."""
    return [Path(n) for n in names or () if Path(n).suffix.lower() in IMAGE_TYPES]


def open_image(parent, path: str) -> bool:
    """Открыть картинку целиком: встроенный просмотрщик, иначе программа системы."""
    if not path or not Path(path).is_file():
        return True
    from stamina import image_viewer
    return image_viewer.show(parent, path) is not None or shots.open_file(Path(path))


class ShotTray:
    """Ряд миниатюр приложенных картинок: клик — открыть, ✕ — снять одну.

    Хранит Tk-ссылки на картинки (иначе их съест сборщик мусора).
    """

    def __init__(self, master, *, bg=None, size: int = 72, limit: int = 8,
                 on_open=None, on_drop=None) -> None:
        self.bg = BG if bg is None else bg
        self.size, self.limit = size, limit
        self.on_open, self.on_drop = on_open, on_drop
        self.frame = tk.Frame(master, bg=self.bg, bd=0)
        self.previews: list = []

    def draw(self, paths) -> None:
        for w in self.frame.winfo_children():
            w.destroy()
        self.previews = []
        try:
            from PIL import ImageTk
        except Exception:  # noqa: BLE001
            ImageTk = None
        for path in list(paths)[:self.limit]:
            cell = tk.Frame(self.frame, bg=self.bg)
            cell.pack(side=tk.LEFT, padx=(0, px(6)))
            pic = shots.thumbnail(Path(path), size=self.size)
            if pic is None or ImageTk is None:
                lab = tk.Label(cell, text="📷 " + Path(path).name[:18], bg=self.bg, fg=MUTED,
                               font=theme.font(8), cursor="hand2")
            else:
                photo = ImageTk.PhotoImage(pic, master=cell)
                self.previews.append(photo)
                lab = tk.Label(cell, image=photo, bg=self.bg, bd=1, relief=tk.SOLID, cursor="hand2")
            lab.pack()
            if self.on_open:
                lab.bind("<Button-1>", lambda _e, p=path: self.on_open(p))
            x = tk.Label(cell, text="✕", bg=self.bg, fg=MUTED, font=theme.font(8, True), cursor="hand2")
            x.place(relx=1.0, x=-1, y=1, anchor="ne")
            if self.on_drop:
                x.bind("<Button-1>", lambda _e, p=path: self.on_drop(p))
