"""Контроллер простоя и полноэкранное слайдшоу поверх главного окна (Tk)."""

from __future__ import annotations

import threading
import time
import tkinter as tk

from stamina import theme
from stamina.i18n import t as _t
from stamina.idle import FADE_MS, GIF_MAX_FRAMES, XFADE_MS, XFADE_STEPS, RADIO_TARGET, SLIDE_MS, fade_volume, is_idle, pick_station, settings_of

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
        self.bag = None
        self.cur: dict | None = None
        self._busy = False
        self._photo = None
        self._img_id = None
        self._last_img = None
        self._job = None
        self._fade_job = None
        self._fade_img_job = None
        self._anim_job = None
        self._resize_job = None
        self._radio_started = False
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.cv = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._on_resize())
        for seq in ("<KeyPress>", "<KeyRelease>"):
            self.bind(seq, self._key)
            self.cv.bind(seq, self._key)
        self.cv.bind("<ButtonPress>", self._key)
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.cv.create_text(20, 20, anchor="nw", text=_t("Загрузка…"), fill=theme.MUTED, font=theme.font(12),
                            tags="loading")
        skin = theme.theme_id()
        ss = theme.current().get("slideshow") or {}
        threading.Thread(target=self._load, args=(skin, ss), daemon=True).start()
        if self.cfg["idle_radio"]:
            self._start_radio()

    def _on_resize(self) -> None:
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(150, self._paint)

    # -- картинки
    def _load(self, skin: str, ss: dict) -> None:
        from stamina.idle.images import load_images

        def add(batch: list[dict]) -> None:
            try:
                self.after(0, lambda: self._got(batch))
            except (tk.TclError, RuntimeError):
                pass

        load_images(skin, ss, on_add=add)

    def _got(self, batch: list[dict]) -> None:
        if not self.winfo_exists():
            return
        from stamina.idle.images import ShuffleBag
        if self.bag is None:
            self.bag = ShuffleBag(batch)
            self.items = self.bag.items
            self.cur = self.bag.next()
            self._paint()
            self._job = self.after(SLIDE_MS, self._next)
        else:
            self.bag.add(batch)

    def _size(self) -> tuple[int, int]:
        return self.cv.winfo_width(), self.cv.winfo_height()

    @staticmethod
    def _fit(img, w: int, h: int):
        """Заполнить экран с обрезкой по центру (cover)."""
        img = img.convert("RGB")
        sw, sh = img.size
        sc = max(w / sw, h / sh)
        img = img.resize((max(1, int(sw * sc)), max(1, int(sh * sc))), Image.BILINEAR)
        l, tp = (img.width - w) // 2, (img.height - h) // 2
        return img.crop((l, tp, l + w, tp + h))

    def _frames(self, it: dict, w: int, h: int) -> tuple[list, list[int]]:
        """Кадры слайда: один для фото, несколько для анимированного GIF (с ограничением)."""
        src = Image.open(it["path"])
        n = getattr(src, "n_frames", 1)
        if n <= 1:
            return [self._fit(src, w, h)], [0]
        frames, durs = [], []
        for i in range(min(n, GIF_MAX_FRAMES)):
            src.seek(i)
            frames.append(self._fit(src, w, h))
            durs.append(max(40, int(src.info.get("duration", 80))))
        return frames, durs

    def _next(self) -> None:
        """Подготовить следующий слайд в потоке, затем плавно перейти."""
        self._job = None
        if self.bag is None or self._busy:
            self._job = self.after(SLIDE_MS, self._next)
            return
        nxt = self.bag.next()
        w, h = self._size()
        if nxt is None or nxt is self.cur or w < 50 or Image is None:
            self._job = self.after(SLIDE_MS, self._next)
            return
        self._busy = True
        prev = self._last_img

        def work():
            try:
                frames, durs = self._frames(nxt, w, h)
                steps = []
                if prev is not None and prev.size == frames[0].size:
                    steps = [Image.blend(prev, frames[0], (k + 1) / (XFADE_STEPS + 1)) for k in range(XFADE_STEPS)]
            except Exception:  # noqa: BLE001 — битый файл: просто пропускаем
                frames, durs, steps = [], [], []
            try:
                self.after(0, lambda: self._crossfade(nxt, steps, frames, durs))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _crossfade(self, it: dict, steps: list, frames: list, durs: list[int]) -> None:
        if not self.winfo_exists():
            return
        if not frames:
            self._busy = False
            self._job = self.after(1000, self._next)
            return
        self._stop_anim()

        def step(k: int) -> None:
            if not self.winfo_exists():
                return
            if k < len(steps):
                self._set_image(steps[k])
                self._fade_img_job = self.after(XFADE_MS // max(1, len(steps)), lambda: step(k + 1))
                return
            self._fade_img_job = None
            self.cur = it
            self._busy = False
            self._show(it, frames, durs)
            total = sum(durs) if len(frames) > 1 else 0
            self._job = self.after(max(SLIDE_MS, total * 2), self._next)

        step(0)

    def _set_image(self, img) -> None:
        self._photo = ImageTk.PhotoImage(img)
        if self._img_id is None:
            self._img_id = self.cv.create_image(0, 0, anchor="nw", image=self._photo)
            self.cv.tag_lower(self._img_id)
        else:
            self.cv.itemconfigure(self._img_id, image=self._photo)
        self._last_img = img

    def _stop_anim(self) -> None:
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None

    def _show(self, it: dict, frames: list, durs: list[int]) -> None:
        self._set_image(frames[0])
        self._caption(it)
        if len(frames) > 1:
            photos = [ImageTk.PhotoImage(f) for f in frames]

            def play(i: int) -> None:
                if not self.winfo_exists() or self._img_id is None:
                    return
                self._photo = photos[i]
                self._last_img = frames[i]
                self.cv.itemconfigure(self._img_id, image=self._photo)
                self._anim_job = self.after(durs[i], lambda: play((i + 1) % len(photos)))

            play(0)

    def _caption(self, it: dict) -> None:
        w, h = self._size()
        self.cv.delete("cap")
        cap = " · ".join(x for x in (it.get("title", "")[:60], it.get("author", ""), it.get("license", ""),
                                     it.get("source", "")) if x and x != "skin")
        f = theme.font(9)
        if cap:
            self.cv.create_rectangle(0, h - 30, w, h, fill="#000000", outline="", stipple="gray50", tags="cap")
            self.cv.create_text(12, h - 15, anchor="w", text=_t("Фото") + ": " + cap, fill="#e8e2d0", font=f,
                                tags="cap")
        self.cv.create_text(w - 12, h - 15, anchor="e", text=_t("Любая клавиша — вернуться"),
                            fill="#e8c766", font=f, tags="cap")

    def _paint(self) -> None:
        """Перерисовать текущий слайд без перехода (старт, смена размера окна)."""
        w, h = self._size()
        if w < 50 or h < 50 or self.cur is None or Image is None or self._busy:
            return
        try:
            frames, durs = self._frames(self.cur, w, h)
        except Exception:  # noqa: BLE001
            return
        self.cv.delete("loading")
        self._stop_anim()
        self._show(self.cur, frames, durs)

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
        for j in (self._job, self._fade_job, self._fade_img_job, self._anim_job, self._resize_job):
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
