"""Контроллер простоя и полноэкранное слайдшоу поверх главного окна (Tk)."""

from __future__ import annotations

import queue
import random
import threading
import time
import tkinter as tk

from stamina import theme
from stamina import safe_mode
from stamina.i18n import t as _t
from stamina.idle import DRIFT, FADE_MS, GIF_MAX_FRAMES, order_stations, station_genre, XFADE_MS, XFADE_STEPS, RADIO_TARGET, SLIDE_MS, fade_volume, is_idle, pick_station, settings_of

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = ImageTk = None

ELLIPSIS = "…"


def skin_slideshow() -> dict | None:
    return theme.current().get("slideshow") or None


def fit_text(text: str, measure, max_px: int) -> str:
    """Обрезать строку по ширине в пикселях, добавив «…».

    ``measure`` — функция «строка → ширина в px» (в кадре это холст, в тестах —
    простая оценка). Нужна, чтобы длинное имя волны не вылезало за рамку плашки
    в слайдшоу: имя режем по пикселям, а не по числу букв.
    """
    text = " ".join(str(text or "").split())
    if not text or max_px <= 0:
        return ""
    if measure(text) <= max_px:
        return text
    if measure(ELLIPSIS) > max_px:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(text[:mid].rstrip() + ELLIPSIS) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ELLIPSIS if lo else ELLIPSIS


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
        # Слайдшоу закрывает само себя (Esc, правая кнопка мыши). Раньше здесь
        # стояло «любая клавиша закрывает» — из-за этого стрелка «волна вправо»
        # выбрасывала из кадра, а через раз не срабатывала вовсе.

    def _tick(self) -> None:
        try:
            s = settings_of(self.app.store.settings)
            # виджеты с "break" (списки, крошки, кнопки) не доходят до bind_all -
            # добираем активность по системному простою ввода (tk inactive)
            try:
                ms = int(self.app.tk.call("tk", "inactive"))
                if ms >= 0:
                    self.last = max(self.last, time.time() - ms / 1000)
            except (tk.TclError, ValueError):
                pass
            if (self.show is None and skin_slideshow() and self.app.focus_displayof() is not None
                    and is_idle(self.last, time.time(), s["idle_minutes"])):
                self.open()
            self.app.after(5000, self._tick)
        except tk.TclError:
            pass

    def open(self) -> None:
        if safe_mode.enabled() or self.show is not None or not skin_slideshow():
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
        self._drift_job = None
        self._pos = (0.0, 0.0)
        self._radio_started = False
        self.stations: list[dict] = []
        self.st_i = 0
        self._muted = False
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.cv = tk.Canvas(self, bg="#000000", highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._on_resize())
        for seq in ("<KeyPress>", "<KeyRelease>"):
            self.bind(seq, self._key)
            self.cv.bind(seq, self._key)
        self.cv.bind("<ButtonPress>", self._click)
        self.cv.bind("<Button-3>", lambda _e: (self.close(), "break")[1])
        self._app_bind = self.app.bind("<KeyPress>", self._key, add="+")
        # Клавиатура — на холст слайдшоу: иначе буквы уходят в поле набора,
        # а стрелки срабатывают через раз (было: любая клавиша закрывала кадр).
        self.after(60, self._grab_focus)
        # Захват клавиатуры и focus_force НЕ ставим: глобальный grab отбирает
        # клавиши у всей системы (перестаёт переключаться раскладка), а окно
        # выглядит зависшим. Слайдшоу закрывается по любой клавише/клику через
        # IdleController.touch (bind_all на главном окне).
        self.cv.create_text(20, 20, anchor="nw", text=_t("Загрузка…"), fill=theme.MUTED, font=theme.font(12),
                            tags="loading")
        skin = theme.theme_id()
        ss = theme.current().get("slideshow") or {}
        threading.Thread(target=self._load, args=(skin, ss), daemon=True).start()
        if self.cfg["idle_radio"]:
            self._start_radio()

    def _grab_focus(self) -> None:
        try:
            self.cv.focus_set()
        except tk.TclError:
            pass

    def _click(self, e) -> str:
        """Щелчок по кадру: левая — следующая волна, если радио есть, иначе тишина."""
        if self.stations:
            self.switch_station(1)
        return "break"

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

    def _measure_text(self, text: str, font_spec) -> int:
        """Ширина строки на холсте; без Tk-шрифта — грубая оценка для тестов."""
        try:
            return int(self.cv.tk.call("font", "measure", font_spec, text))
        except (tk.TclError, ValueError):
            return len(text) * 7

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
        w, h = int(w * DRIFT), int(h * DRIFT)  # чуть больше экрана — для медленного «проплыва»
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
        q: queue.Queue = queue.Queue(maxsize=3)  # кадры наложения по одному — память не растёт

        def work():
            try:
                frames, durs = self._frames(nxt, w, h)
            except Exception:  # noqa: BLE001 — битый файл: просто пропускаем
                frames, durs = [], []
            fade = bool(frames) and prev is not None and prev.size == frames[0].size
            try:
                self.after(0, lambda: self._crossfade(nxt, q if fade else None, frames, durs))
            except (tk.TclError, RuntimeError):
                return
            if fade:
                for k in range(XFADE_STEPS):
                    q.put(Image.blend(prev, frames[0], (k + 1) / (XFADE_STEPS + 1)))
                q.put(None)

        threading.Thread(target=work, daemon=True).start()

    def _crossfade(self, it: dict, q, frames: list, durs: list[int]) -> None:
        if not self.winfo_exists():
            return
        if not frames:
            self._busy = False
            self._job = self.after(1000, self._next)
            return
        self._stop_anim()
        dt = XFADE_MS // max(1, XFADE_STEPS)

        def done() -> None:
            self._fade_img_job = None
            self.cur = it
            self._busy = False
            self._show(it, frames, durs)
            total = sum(durs) if len(frames) > 1 else 0
            dur = max(SLIDE_MS, total * 2)
            self._start_drift(dur + XFADE_MS)
            self._job = self.after(dur, self._next)

        def step() -> None:
            if not self.winfo_exists():
                return
            try:
                img = q.get_nowait() if q is not None else None
            except queue.Empty:
                self._fade_img_job = self.after(15, step)
                return
            if img is None:
                done()
                return
            self._set_image(img)
            self._fade_img_job = self.after(dt, step)

        step()

    # -- медленный проплыв кадра (Ken Burns без пересчёта картинки: двигаем её по холсту)
    def _start_drift(self, dur_ms: int) -> None:
        self._stop_drift()
        w, h = self._size()
        mx, my = -(int(w * DRIFT) - w), -(int(h * DRIFT) - h)
        x0, y0 = self._pos
        x1, y1 = random.choice(((0, 0), (mx, 0), (0, my), (mx, my)))
        if (x1, y1) == (round(x0), round(y0)):
            x1, y1 = mx - x1, my - y1
        t0 = time.time()

        def step() -> None:
            if not self.winfo_exists() or self._img_id is None:
                return
            k = min(1.0, (time.time() - t0) * 1000 / max(1, dur_ms))
            e = k * k * (3 - 2 * k)  # плавный старт и финиш
            self._pos = (x0 + (x1 - x0) * e, y0 + (y1 - y0) * e)
            self.cv.coords(self._img_id, int(self._pos[0]), int(self._pos[1]))
            if k < 1.0:
                self._drift_job = self.after(50, step)

        step()

    def _stop_drift(self) -> None:
        if self._drift_job:
            try:
                self.after_cancel(self._drift_job)
            except tk.TclError:
                pass
            self._drift_job = None

    def _set_image(self, img) -> None:
        self._photo = ImageTk.PhotoImage(img)
        if self._img_id is None:
            self._img_id = self.cv.create_image(int(self._pos[0]), int(self._pos[1]), anchor="nw",
                                                image=self._photo)
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
        lim = max(24, w // 8 - 34)  # не наезжать на «Любая клавиша — вернуться»
        if len(cap) > lim:
            cap = cap[:lim - 1].rstrip() + "…"
        f = theme.font(9)
        if cap:
            self.cv.create_rectangle(0, h - 30, w, h, fill="#000000", outline="", stipple="gray50", tags="cap")
            self.cv.create_text(12, h - 15, anchor="w", text=_t("Фото") + ": " + cap, fill="#e8e2d0", font=f,
                                tags="cap")
        self.cv.create_text(w - 12, h - 15, anchor="e", text=_t("Любая клавиша — вернуться"),
                            fill="#e8c766", font=f, tags="cap")
        self._plate()

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
        self._start_drift(SLIDE_MS + XFADE_MS)

    # -- радио скина: переключатель волн на плашке (← → волна, ↑ ↓ громкость, M — тише/громче)
    def _engine(self):
        try:
            from stamina.radio import get_engine
            eng = get_engine()
        except Exception:  # noqa: BLE001
            return None
        return eng if eng.ready() else None

    def _start_radio(self) -> None:
        conf = theme.current().get("radio") or {}
        if not conf.get("tags"):
            return
        eng = self._engine()
        if eng is None:
            return
        autoplay = not eng.playing
        saved = (self.app.store.settings.get("idle_station") or {}).get(theme.theme_id())

        def work():
            from stamina.radio import browser
            items, _err = browser.skin_stations(conf)
            items = order_stations(items, saved, conf.get("pinned"))
            try:
                self.after(0, lambda: self._got_stations(eng, items, autoplay))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _got_stations(self, eng, items: list[dict], autoplay: bool) -> None:
        if not self.winfo_exists() or not items:
            return
        self.stations = items
        self.st_i = 0
        if autoplay:
            self._play(eng, items[0])
        self._plate()

    def _play(self, eng, st: dict) -> None:
        if not self.winfo_exists():
            return
        if not self._radio_started:
            self._radio_full = int(eng.volume)
        full = self._radio_full
        target = min(full, int(RADIO_TARGET * 100))
        self._stop_fade()
        try:
            eng.player.set_volume(0)
        except Exception:  # noqa: BLE001
            pass
        if not eng.play_station(st):
            self._plate(_t("нет связи с волной"))
            return
        self._radio_started = True
        self._muted = False
        self._target = target
        t0 = time.time()

        def step():
            el = (time.time() - t0) * 1000
            try:
                eng.player.set_volume(int(fade_volume(el, FADE_MS, self._target)))
            except Exception:  # noqa: BLE001
                return
            if el < FADE_MS and self.winfo_exists():
                self._fade_job = self.after(60, step)
            else:
                self._fade_job = None

        step()

    def _stop_fade(self) -> None:
        if self._fade_job:
            try:
                self.after_cancel(self._fade_job)
            except tk.TclError:
                pass
            self._fade_job = None

    def switch_station(self, delta: int) -> None:
        eng = self._engine()
        if eng is None or not self.stations:
            return
        self.st_i = (self.st_i + delta) % len(self.stations)
        st = self.stations[self.st_i]
        self._remember(st)
        self._play(eng, st)
        self._plate()

    def _remember(self, st: dict) -> None:
        store = self.app.store
        saved = dict(store.settings.get("idle_station") or {})
        saved[theme.theme_id()] = str(st.get("name", ""))
        store.settings["idle_station"] = saved
        try:
            store.save_settings()
        except Exception:  # noqa: BLE001
            pass

    def change_volume(self, delta: int) -> None:
        eng = self._engine()
        if eng is None or not self._radio_started:
            return
        self._stop_fade()
        self._target = max(0, min(100, getattr(self, "_target", 40) + delta))
        self._muted = False
        try:
            eng.player.set_volume(self._target)
        except Exception:  # noqa: BLE001
            pass
        self._plate()

    def toggle_mute(self) -> None:
        eng = self._engine()
        if eng is None or not self._radio_started:
            return
        self._stop_fade()
        self._muted = not self._muted
        try:
            eng.player.set_volume(0 if self._muted else getattr(self, "_target", 40))
        except Exception:  # noqa: BLE001
            pass
        self._plate()

    def _plate(self, note: str | None = None) -> None:
        """Плашка волны в стиле скина: имя станции, жанр, громкость и подсказка."""
        self.cv.delete("plate")
        if not self.stations:
            return
        w, h = self._size()
        st = self.stations[self.st_i]
        c = theme.current().get("colors") or {}
        paper = c.get("panel") or "#1b1712"
        gold = c.get("accent") or "#e8c766"
        ink = c.get("text") or "#e8e2d0"
        name = str(st.get("name", "")).strip() or "—"
        genre = station_genre(st)
        vol = _t("без звука") if self._muted else f"{getattr(self, '_target', 40)}%"
        line1 = f"♪ {name}" + (f"  ·  {genre}" if genre else "")
        line2 = note or (_t("← → — волна · ↑ ↓ — громкость · M — звук · Esc — выйти") + f"   [{self.st_i + 1}/{len(self.stations)} · {vol}]")
        pw = min(w - 40, max(420, int(w * 0.46)))
        # Имя волны режем по пикселям: длинные названия иначе вылезают за рамку
        # плашки, особенно в узком окне и на крупном системном шрифте.
        f1 = theme.font(11, True)
        line1 = fit_text(line1, lambda s: self._measure_text(s, f1), max(80, pw - 24))
        x0, y1 = (w - pw) // 2, h - 40
        y0 = y1 - 54
        self.cv.create_rectangle(x0, y0, x0 + pw, y1, fill=paper, outline=gold, width=2, tags="plate")
        self.cv.create_rectangle(x0 + 4, y0 + 4, x0 + pw - 4, y1 - 4, outline=gold, width=1, tags="plate")
        self.cv.create_text(w // 2, y0 + 18, text=line1, fill=gold, font=f1, tags="plate")
        self.cv.create_text(w // 2, y0 + 38, text=line2, fill=ink, font=theme.font(9), tags="plate")

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
    RADIO_KEYS = {"Left": ("switch", -1), "Right": ("switch", 1), "Up": ("vol", 10), "Down": ("vol", -10),
                  "m": ("mute", 0), "M": ("mute", 0), "Cyrillic_softsign": ("mute", 0),
                  "Cyrillic_SOFTSIGN": ("mute", 0)}

    def _key(self, e) -> str:
        if getattr(e, "type", "") in ("3", tk.EventType.KeyRelease):
            return "break"
        key = getattr(e, "keysym", "")
        if key in ("Escape", "q", "Q", "Cyrillic_shorti", "Cyrillic_SHORTI"):
            self.close()
            return "break"
        act = self.RADIO_KEYS.get(key) if self.stations else None
        if act:
            kind, n = act
            if kind == "switch":
                self.switch_station(n)
            elif kind == "vol":
                self.change_volume(n)
            else:
                self.toggle_mute()
        # Остальные клавиши глотаем, но кадр не закрываем: выход — Esc или правая кнопка мыши.
        return "break"

    def close(self) -> None:
        for j in (self._job, self._fade_job, self._fade_img_job, self._anim_job, self._resize_job, self._drift_job):
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
        try:
            if getattr(self, "_app_bind", None):
                self.app.unbind("<KeyPress>", self._app_bind)
        except tk.TclError:
            pass
        cb = self.on_close
        self.destroy()
        cb()
