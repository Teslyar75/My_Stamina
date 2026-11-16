"""Предварительная редакция снимка перед отправкой Ориону.

Открывается двойным кликом по миниатюре над полем ввода: рамка обрезки мышью,
поворот, «Применить». Работаем с копией — исходный файл остаётся, пока пилот
не нажмёт «Применить»; после применения старый снимок уходит с борта.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import shots, theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, RED, px


class ShotEditor(tk.Toplevel):
    """Рамка обрезки, поворот на 90° и запись снимка обратно на борт."""

    MAX_W = 1100
    MAX_H = 680

    def __init__(self, master, path: str, on_done=None) -> None:
        super().__init__(master, bg=BG)
        self.title(_t("Правка снимка"))
        self.transient(master.winfo_toplevel())
        self.path = Path(path)
        self.on_done = on_done

        from PIL import Image

        try:
            img = Image.open(self.path)
            img.load()
        except Exception as exc:  # noqa: BLE001
            self.destroy()
            raise RuntimeError(_t("Не удалось открыть снимок: {0}").format(exc)) from exc
        self.src = img.convert("RGBA")
        self.image = self.src.copy()
        self.scale = 1.0
        self._photo = None
        self._coords: tuple | None = None          # активная рамка в координатах картинки
        self._drag: tuple | None = None

        hud = tk.Frame(self, bg=BG)
        hud.pack(fill=tk.X, padx=px(10), pady=(px(8), px(4)))
        tk.Label(hud, text=_t("ПРЕДВАРИТЕЛЬНАЯ РЕДАКЦИЯ"), bg=BG, fg=AMBER,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        self.info = tk.Label(hud, text="", bg=BG, fg=MUTED, font=theme.font(9))
        self.info.pack(side=tk.LEFT, padx=px(12))
        self.hint = tk.Label(hud, text="", bg=BG, fg=CYAN, font=theme.font(9))
        self.hint.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self, bg=PANEL, highlightthickness=1, highlightbackground=MUTED, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._release)

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X, padx=px(10), pady=(px(4), px(10)))
        HudButton(bar, _t("⟲ ПОВЕРНУТЬ"), self.rotate, height=32, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=px(2))
        HudButton(bar, _t("▣ ОБРЕЗАТЬ"), self.crop, height=32, font_size=9,
                  color=GREEN).pack(side=tk.LEFT, padx=px(2))
        HudButton(bar, _t("⟲ СБРОС"), self.reset, height=32, font_size=9,
                  color=MUTED).pack(side=tk.LEFT, padx=px(2))
        HudButton(bar, _t("ПРИМЕНИТЬ"), self.apply, height=32, font_size=10,
                  color=AMBER).pack(side=tk.RIGHT, padx=px(2))
        HudButton(bar, _t("ОТМЕНА"), self.cancel, height=32, font_size=9,
                  color=MUTED).pack(side=tk.RIGHT, padx=px(2))
        HudButton(bar, _t("🗑 УБРАТЬ СНИМОК"), self.drop, height=32, font_size=9,
                  color=RED).pack(side=tk.RIGHT, padx=px(2))

        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Escape>", lambda _e: self.cancel())
        self.bind("<Return>", lambda _e: self.apply())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.update_idletasks()
        self._center()
        self.redraw()

    # -- геометрия ---------------------------------------------------------
    def _center(self) -> None:
        root = self.master.winfo_toplevel()
        w = min(self.MAX_W, max(px(560), root.winfo_width() - px(120)))
        h = min(self.MAX_H, max(px(420), root.winfo_height() - px(160)))
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + (root.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _fit(self) -> None:
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        iw, ih = self.image.size
        self.scale = min(cw / iw, ch / ih, 1.0)
        self.info.configure(text=_t("{0}×{1} · {2}%").format(iw, ih, round(self.scale * 100)))

    # -- рисование ---------------------------------------------------------
    def redraw(self) -> None:
        from PIL import ImageTk

        self.canvas.delete("all")
        if self.canvas.winfo_width() < 20 or self.canvas.winfo_height() < 20:
            return                            # окно ещё не разложено: придёт <Configure>
        self._fit()
        iw, ih = self.image.size
        w, h = max(1, int(iw * self.scale)), max(1, int(ih * self.scale))
        shown = self.image if self.scale >= 1 else self.image.resize((w, h))
        self._photo = ImageTk.PhotoImage(shown, master=self)
        ox = (self.canvas.winfo_width() - w) // 2
        oy = (self.canvas.winfo_height() - h) // 2
        self._orig = (ox, oy)
        self.canvas.create_image(ox, oy, image=self._photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, w, h))
        if self._coords:
            x1, y1, x2, y2 = self._screen_box()
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=AMBER, width=2, dash=(6, 3))

    def _screen_box(self) -> tuple:
        ox, oy = getattr(self, "_orig", (0, 0))
        x1, y1, x2, y2 = self._coords or (0, 0, 0, 0)
        return (ox + x1 * self.scale, oy + y1 * self.scale,
                ox + x2 * self.scale, oy + y2 * self.scale)

    def _to_image(self, sx: float, sy: float) -> tuple:
        ox, oy = getattr(self, "_orig", (0, 0))
        iw, ih = self.image.size
        x = int(round((sx - ox) / self.scale)) if self.scale else 0
        y = int(round((sy - oy) / self.scale)) if self.scale else 0
        return max(0, min(iw, x)), max(0, min(ih, y))

    # -- рамка -------------------------------------------------------------
    def _press(self, e) -> None:
        self._drag = self._to_image(e.x, e.y)
        self._coords = (*self._drag, *self._drag)
        self.redraw()

    def _drag_move(self, e) -> None:
        if not self._drag:
            return
        x, y = self._to_image(e.x, e.y)
        self._coords = (min(self._drag[0], x), min(self._drag[1], y),
                        max(self._drag[0], x), max(self._drag[1], y))
        self.redraw()

    def _release(self, _e=None) -> None:
        self._drag = None
        if self._coords:
            x1, y1, x2, y2 = self._coords
            if x2 - x1 < 8 or y2 - y1 < 8:
                self._coords = None
                self.redraw()
                self.hint.configure(text=_t("Рамка слишком мала — обведёте область заново"), fg=RED)
            else:
                self.hint.configure(text=_t("Обведено — нажмите «Обрезать»"), fg=CYAN)

    # -- действия ----------------------------------------------------------
    def rotate(self) -> None:
        self.image = self.image.transpose(_rot90())
        self._coords = None
        self.redraw()
        self.hint.configure(text=_t("Повёрнуто"), fg=CYAN)

    def crop(self) -> None:
        if not self._coords:
            self.hint.configure(text=_t("Сначала обведите область мышью"), fg=AMBER)
            return
        self.image = self.image.crop(self._coords)
        self._coords = None
        self.redraw()
        self.hint.configure(text=_t("Обрезано"), fg=GREEN)

    def reset(self) -> None:
        self.image = self.src.copy()
        self._coords = None
        self.redraw()
        self.hint.configure(text=_t("Исходный вид"), fg=MUTED)

    def apply(self) -> None:
        try:
            new_path = shots.save_image(self.image)
        except Exception as exc:  # noqa: BLE001
            self.hint.configure(text=_t("Не сохранилось: {0}").format(exc), fg=RED)
            return
        try:
            if self.path.exists() and self.path != new_path:
                self.path.unlink()
        except OSError:
            pass
        self._finish(str(new_path))

    def drop(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass
        self._finish("")

    def cancel(self) -> None:
        self._finish(None)

    def _finish(self, result) -> None:
        callback, self.on_done = self.on_done, None
        self.destroy()
        if callback is not None:
            callback(result)


def _rot90():
    from PIL import Image
    return getattr(Image, "Transpose", Image).ROTATE_270
