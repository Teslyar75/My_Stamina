"""Просмотр снимка целиком — внутри корабля, на том же мониторе, что и окно.

Открывается кликом по миниатюре (лента Ориона, архив, строка приложенного).
Esc или ✕ — закрыть; колесо — масштаб вокруг курсора; перетаскивание — сдвиг;
двойной клик — «вписать в окно». Картинка ресэмплится через Pillow один раз на
каждый шаг масштаба (с короткой задержкой, чтобы колесо не тормозило).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import monitors, shots, theme
from stamina.i18n import t as _t
from stamina.theme import BG, CYAN, MUTED, PANEL, TEXT, px

_open: "ImageViewer | None" = None


def show(master, path) -> "ImageViewer | None":
    """Открыть (или переоткрыть) просмотрщик для файла path. None — не открылся."""
    global _open
    path = Path(path)
    if not path.is_file():
        return None
    try:
        from PIL import Image
        img = Image.open(path)
        img.load()
    except Exception:  # noqa: BLE001
        return None
    if _open is not None:
        _open.close()
    _open = ImageViewer(master, path, img)
    return _open


class ImageViewer(tk.Toplevel):
    MIN, MAX = 0.05, 8.0

    def __init__(self, master, path: Path, img) -> None:
        super().__init__(master, bg=BG)
        self.path, self.img = path, img.convert("RGBA") if img.mode not in ("RGB", "RGBA") else img
        self.withdraw()
        self.title(path.name)
        try:
            self.transient(master.winfo_toplevel())
        except tk.TclError:
            pass
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(side=tk.TOP, fill=tk.X)
        self.caption = tk.Label(bar, text="", bg=PANEL, fg=TEXT, font=theme.font(10, True),
                                anchor="w", padx=px(10), pady=px(4))
        self.caption.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for label, cmd in ((_t("Вписать"), self.fit), ("1:1", lambda: self.zoom_to(1.0)),
                           (_t("Открыть в системе"), self._external), ("✕", self.close)):
            b = tk.Label(bar, text=label, bg=PANEL, fg=CYAN, font=theme.font(10, True),
                         padx=px(8), cursor="hand2")
            b.pack(side=tk.LEFT)
            b.bind("<Button-1>", lambda _e, c=cmd: c())
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, cursor="fleur")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        tk.Label(self, text=_t("Колесо — масштаб · перетаскивание — сдвиг · двойной клик — вписать · Esc — закрыть"),
                 bg=BG, fg=MUTED, font=theme.font(8)).pack(side=tk.BOTTOM, fill=tk.X)
        self.scale = 1.0
        self.ox = self.oy = 0.0           # левый верхний угол картинки на холсте
        self._photo = None
        self._job = None
        self._drag = None
        self._place(master)
        for seq, fn in (("<Escape>", lambda _e: self.close()),
                        ("<MouseWheel>", self._wheel),
                        ("<Button-4>", lambda e: self._zoom_at(1.25, e.x, e.y)),
                        ("<Button-5>", lambda e: self._zoom_at(0.8, e.x, e.y))):
            self.bind(seq, fn)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.fit())
        self.canvas.bind("<ButtonRelease-1>", lambda _e: self._render())
        self._need_fit = True
        self.canvas.bind("<Configure>", lambda _e: self.fit() if self._need_fit else self._render(fast=True))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.deiconify()
        self.lift()
        self.focus_force()
        self.fit()

    # -- геометрия -------------------------------------------------------------
    def _place(self, master) -> None:
        l, t, r, b = monitors.work_area(master)
        mw, mh = r - l, b - t
        iw, ih = self.img.size
        chrome = px(60)
        fit = min(1.0, (mw * 0.9) / iw, (mh * 0.9 - chrome) / ih)
        w = max(px(360), int(iw * fit))
        h = max(px(240), int(ih * fit) + chrome)
        w, h = min(w, mw), min(h, mh)
        self.geometry(f"{w}x{h}+{l + (mw - w) // 2}+{t + (mh - h) // 2}")
        self._area = (l, t, r, b)

    def fit(self) -> None:
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10:            # ещё не выложен — впишем по первому <Configure>
            self._need_fit = True
            return
        self._need_fit = False
        iw, ih = self.img.size
        self.scale = max(self.MIN, min(1.0, cw / iw, ch / ih))
        self.ox, self.oy = (cw - iw * self.scale) / 2, (ch - ih * self.scale) / 2
        self._render()

    def zoom_to(self, s: float) -> None:
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        self._zoom_at(s / self.scale, cw / 2, ch / 2)

    def _zoom_at(self, k: float, x: float, y: float) -> str:
        s = max(self.MIN, min(self.MAX, self.scale * k))
        k = s / self.scale
        self.ox, self.oy = x - (x - self.ox) * k, y - (y - self.oy) * k
        self.scale = s
        self._render(fast=True)
        return "break"

    def _wheel(self, e) -> str:
        x = e.x_root - self.canvas.winfo_rootx()
        y = e.y_root - self.canvas.winfo_rooty()
        return self._zoom_at(1.25 if e.delta > 0 else 0.8, x, y)

    def _press(self, e) -> None:
        self._drag = (e.x, e.y, self.ox, self.oy)

    def _move(self, e) -> None:
        if self._drag:
            x0, y0, ox, oy = self._drag
            self.ox, self.oy = ox + e.x - x0, oy + e.y - y0
            self.canvas.coords("img", int(self.ox), int(self.oy))

    # -- отрисовка -------------------------------------------------------------
    def _render(self, fast: bool = False) -> None:
        """Отрисовать видимую часть. fast — сперва грубо (быстро), чётко — через 60 мс."""
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._draw(fast)
        if fast:
            self._job = self.after(60, lambda: self._draw(False))
        self.caption.configure(text=f"{self.path.name}   {self.img.size[0]}×{self.img.size[1]}   "
                                    f"{round(self.scale * 100)}%")

    def _draw(self, fast: bool) -> None:
        from PIL import Image, ImageTk
        self._job = None
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        iw, ih = self.img.size
        s = self.scale
        # обрезаем до видимого окна — огромные снимки при 800% не раздуваем целиком
        x0, y0 = max(0.0, -self.ox / s), max(0.0, -self.oy / s)
        x1, y1 = min(iw, (cw - self.ox) / s), min(ih, (ch - self.oy) / s)
        self.canvas.delete("img")
        if x1 <= x0 or y1 <= y0:
            return
        box = (int(x0), int(y0), max(int(x0) + 1, int(x1 + 1)), max(int(y0) + 1, int(y1 + 1)))
        box = (box[0], box[1], min(iw, box[2]), min(ih, box[3]))
        w = max(1, round((box[2] - box[0]) * s))
        h = max(1, round((box[3] - box[1]) * s))
        res = Image.Resampling.NEAREST if fast or s >= 2 else Image.Resampling.LANCZOS
        part = self.img.crop(box).resize((w, h), res)
        self._photo = ImageTk.PhotoImage(part, master=self)
        self.canvas.create_image(int(self.ox + box[0] * s), int(self.oy + box[1] * s),
                                 image=self._photo, anchor="nw", tags="img")

    def _external(self) -> None:
        shots.open_file(self.path)

    def close(self) -> None:
        global _open
        if _open is self:
            _open = None
        try:
            self.destroy()
        except tk.TclError:
            pass