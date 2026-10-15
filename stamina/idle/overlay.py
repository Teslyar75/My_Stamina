"""Контроллер простоя и полноэкранное слайдшоу поверх главного окна (Tk)."""

from __future__ import annotations

import threading
import time
import tkinter as tk

from stamina import theme
from stamina.i18n import t as _t
from stamina.idle import FADE_MS, RADIO_TARGET, SLIDE_MS, fade_volume, is_idle, pick_station, settings_of

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = ImageTk = None


def skin_slideshow() -> dict | None:
    return theme.current().get("slideshow") or None


class IdleController:
    """Следит за клавиатурой; по таймауту открывает слайдшоу (только у скинов со slideshow)."""

    def __init__(self, app) -> None:
        self.app = app
        self.last = time.time()
        self.show: Slideshow | None = None
        app.bind_all("<KeyPress>", self.touch, add="+")
        app.bind_all("<ButtonPress>", self.touch, add="+")
        app.after(5000, self._tick)

    def touch(self, _e=None) -> None:
        self.last = time.time()

    def _tick(self) -> None:
        try:
            s = settings_of(self.app.store.settings)
            if (self.show is None and skin_slideshow() and self.app.focus_displayof() is not None
                    and is_idle(self.last, time.time(), s["idle_minutes"])):
                self.open()
            self.app.after(5000, self._tick)
        except tk.TclError:
            pass

    def open(self) -> None:
        if self.show is not None or not skin_slideshow():
            return
        self.show = Slideshow(self.app, on_close=self._closed)

    def _closed(self) -> None:
        self.show = None
        self.last = time.time()


class Slideshow(tk.Frame):
    def __init__(self, app, on_close) -> None:
        super().__init__(app, bg="#000000", highlightthickness=0)
        self.app = app
        self.on_close = on_close
        self.cfg = settings_of(app.store.settings)
        self.items: list[dict] = []
        self.idx = 0
        self._photo = None
        self._job = None
        self._fade_job = None
        self._radio_started = False
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.cv = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._paint())
        for seq in ("<KeyPress>", "<KeyRelease>"):
            self.bind(seq, self._key)
            self.cv.bind(seq, self._key)
        self.cv.bind("<ButtonPress>", self._key)
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.cv.create_text(20, 20, anchor="nw", text=_t("Загрузка…"), fill=theme.MUTED, font=theme.font(12))
        skin = theme.theme_id()
        ss = theme.current().get("slideshow") or {}
        threading.Thread(target=self._load, args=(skin, ss), daemon=True).start()
        if self.cfg["idle_radio"]:
            self._start_radio()

    # -- картинки
    def _load(self, skin: str, ss: dict) -> None:
        from stamina.idle.images import load_images
        items = load_images(skin, ss)
        try:
            self.after(0, lambda: self._got(items))
        except (tk.TclError, RuntimeError):
            pass

    def _got(self, items: list[dict]) -> None:
        if not self.winfo_exists():
            return
        self.items = items
        self.idx = 0
        self._paint()
        self._job = self.after(SLIDE_MS, self._next)

    def _next(self) -> None:
        if self.items:
            self.idx = (self.idx + 1) % len(self.items)
            self._paint()
        self._job = self.after(SLIDE_MS, self._next)

    def _paint(self) -> None:
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 50 or h < 50 or not self.items or Image is None:
            return
        it = self.items[self.idx]
        self.cv.delete("all")
        try:
            src = Image.open(it["path"]).convert("RGB")
            sw, sh = src.size
            sc = max(w / sw, h / sh)
            src = src.resize((max(1, int(sw * sc)), max(1, int(sh * sc))), Image.LANCZOS)
            l, tp = (src.width - w) // 2, (src.height - h) // 2
            self._photo = ImageTk.PhotoImage(src.crop((l, tp, l + w, tp + h)))
            self.cv.create_image(0, 0, anchor="nw", image=self._photo)
        except OSError:
            pass
        cap = " · ".join(x for x in (it.get("title", "")[:60], it.get("author", ""), it.get("license", ""),
                                     it.get("source", "")) if x and x != "skin")
        f = theme.font(9)
        if cap:
            self.cv.create_rectangle(0, h - 30, w, h, fill="#000000", outline="", stipple="gray50")
            self.cv.create_text(12, h - 15, anchor="w", text=_t("Фото") + ": " + cap, fill="#e8e2d0", font=f)
        self.cv.create_text(w - 12, h - 15, anchor="e", text=_t("Любая клавиша — вернуться"),
                            fill="#e8c766", font=f)

    # -- радио скина
    def _start_radio(self) -> None:
        conf = theme.current().get("radio") or {}
        if not conf.get("tags"):
            return
        try:
            from stamina.radio import get_engine
            eng = get_engine()
        except Exception:  # noqa: BLE001
            return
        if eng.playing or not eng.ready():
            return

        def work():
            from stamina.radio import browser
            items, _err = browser.skin_stations(conf)
            st = pick_station(items, conf.get("pinned"))
            if st:
                try:
                    self.after(0, lambda: self._play(eng, st))
                except (tk.TclError, RuntimeError):
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _play(self, eng, st: dict) -> None:
        if not self.winfo_exists():
            return
        full = int(eng.volume)
        target = min(full, int(RADIO_TARGET * 100))  # плавный вход до ~30 %
        if not eng.play_station(st):
            return
        self._radio_started = True
        self._radio_full = full
        t0 = time.time()

        def step():
            el = (time.time() - t0) * 1000
            try:
                eng.player.set_volume(int(fade_volume(el, FADE_MS, target)))
            except Exception:  # noqa: BLE001
                return
            if el < FADE_MS and self.winfo_exists():
                self._fade_job = self.after(150, step)

        step()

    def _stop_radio(self) -> None:
        if not self._radio_started:
            return
        try:
            from stamina.radio import get_engine
            eng = get_engine()
            if self.cfg["idle_after"] == "stop":
                eng.stop()
            eng.player.set_volume(getattr(self, "_radio_full", eng.volume))
        except Exception:  # noqa: BLE001
            pass

    # -- закрытие: первое нажатие глотаем
    def _key(self, e) -> str:
        if getattr(e, "type", "") in ("3", tk.EventType.KeyRelease):
            return "break"
        self.close()
        return "break"

    def close(self) -> None:
        for j in (self._job, self._fade_job):
            if j:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
        self._stop_radio()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        cb = self.on_close
        self.destroy()
        cb()
