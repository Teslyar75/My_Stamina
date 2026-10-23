"""Минималистичный режим «Слепой печати» (в духе Monkeytype).

Поверх всего окна кабины кладётся спокойная панель: только строки текста,
курсор, скорость (WPM/CPM), точность и таймер — в цветах текущего скина.
Корабль, обои, боковые панели и шапка скрыты под ней. Логика набора не
меняется: клавиши по-прежнему идут в Bridge.on_key, панель только рисует.

Вход/выход — мгновенная смена кадра, без шлюза и анимаций: кнопка «◯ ДЗЕН»
на мостике или Ctrl+M. Назад: Ctrl+M, двойной Esc (одиночный Esc — заново,
как в Monkeytype) или значок «⟵ на борт» в углу (виден при движении мыши).
Скин, вид, отсек и позиция в тексте не меняются — панель просто убирается.
Выбор запоминается в настройках (settings["zen_mode"]).
"""
from __future__ import annotations

import time
import tkinter as tk

from stamina import theme
from stamina.i18n import t

HOTKEY_LABEL = "Ctrl+M"
SHOW_BEFORE = 120     # символов набранного слева от курсора
SHOW_AFTER = 260      # символов впереди
ESC_DOUBLE_MS = 400   # Esc Esc быстрее этого — выход на борт


SERIKA_DARK = {   # палитра Monkeytype «serika dark»
    "bg": "#323437", "typed": "#d1d0c5", "ahead": "#646669", "caret": "#e2b714",
    "error": "#ca4754", "stat": "#e2b714", "muted": "#646669", "chip": "#2c2e31",
}
PALETTES = ("skin", "serika")


def _palette(name: str = "skin") -> dict[str, str]:
    """Цвета из themes/<skin>.json через движок скинов (theme.c) или «serika dark»."""
    if name == "serika":
        return dict(SERIKA_DARK)
    bg = theme.c("bg")
    return {
        "bg": bg,
        "typed": theme.c("text"),
        "ahead": theme.blend(theme.c("muted"), bg, 0.25),
        "caret": theme.c("accent"),
        "error": theme.c("error"),
        "stat": theme.c("accent"),
        "muted": theme.blend(theme.c("muted"), bg, 0.35),
        "chip": theme.blend(theme.c("panel"), bg, 0.5),
    }


def is_zen_hotkey(e) -> bool:
    """Ctrl+M в любой раскладке (код клавиши M = 77 на Windows; keysym m/M/ь)."""
    if not (getattr(e, "state", 0) & 0x4) or (getattr(e, "state", 0) & 0x8):
        return False
    return getattr(e, "keysym", "") in ("m", "M", "Cyrillic_softsign", "Cyrillic_SOFTSIGN") \
        or getattr(e, "keycode", 0) == 77


class ZenOverlay(tk.Frame):
    def __init__(self, app, palette: str = "skin") -> None:
        self.pal_name = palette
        self.pal = _palette(palette)
        super().__init__(app, bg=self.pal["bg"], highlightthickness=0, bd=0)
        self.app = app
        self._errors_seen = 0
        self._err_until = 0.0
        self._job = None
        p = self.pal
        size = max(18, int(theme.px(22)))
        face = theme.MONO_FAMILY
        small = (face, max(9, int(theme.px(10))))
        # верхняя тонкая полоса: режим текста и выбор палитры (как чипы Monkeytype)
        self.bar = tk.Frame(self, bg=p["chip"])
        self.mode_lbl = tk.Label(self.bar, text="", bg=p["chip"], fg=p["muted"], font=small, padx=10, pady=4)
        self.mode_lbl.pack(side=tk.LEFT)
        tk.Label(self.bar, text=t("палитра:"), bg=p["chip"], fg=p["muted"], font=small).pack(side=tk.LEFT, padx=(14, 4))
        self.chips = {}
        for key, title in (("skin", t("скин")), ("serika", "serika dark")):
            lb = tk.Label(self.bar, text=title, bg=p["chip"], font=small, padx=6, pady=4, cursor="hand2",
                          fg=p["stat"] if key == palette else p["muted"])
            lb.pack(side=tk.LEFT)
            lb.bind("<Button-1>", lambda _e, k=key: (self.app.zen.set_palette(k), "break")[1])
            self.chips[key] = lb
        self.stats = tk.Label(self, text="", bg=p["bg"], fg=p["stat"], anchor="w", font=(face, max(11, int(theme.px(12)))))
        self.text = tk.Text(self, bg=p["bg"], fg=p["ahead"], bd=0, highlightthickness=0,
                            wrap="word", height=3, font=(face, size), cursor="arrow",
                            padx=0, pady=0, spacing3=int(size * 0.5), takefocus=0)
        self.text.tag_configure("typed", foreground=p["typed"])
        self.text.tag_configure("ahead", foreground=p["ahead"])
        self.text.tag_configure("cur", foreground=p["caret"], underline=True)
        self.text.tag_configure("err", foreground=p["bg"], background=p["error"])
        self.hint = tk.Label(self, text=t("Esc — заново · Esc Esc или {0} — на борт · Del — пауза").format(HOTKEY_LABEL),
                             bg=p["bg"], fg=p["muted"], font=small)
        self.bar.place(relx=0.5, rely=0.06, anchor="n")
        self.stats.place(relx=0.12, rely=0.38, anchor="sw")
        self.text.place(relx=0.5, rely=0.40, anchor="n", relwidth=0.76)
        self.hint.place(relx=0.5, rely=0.94, anchor="s")
        for w in (self, self.text, self.stats, self.hint):
            w.bind("<Button-1>", lambda _e: (self.app.focus_set(), "break")[1])
        # «⟵ на борт» — едва заметный значок в углу: появляется от мыши, гаснет через 2 с
        self.back = tk.Label(self, text=t("⟵ на борт"), bg=p["bg"], fg=p["muted"], cursor="hand2",
                             font=small, padx=6, pady=4)
        self.back.bind("<Button-1>", lambda _e: (self.app.zen.toggle(False), "break")[1])
        self._back_job = None
        for w in (self, self.text, self.stats, self.hint, self.bar):
            w.bind("<Motion>", self._motion, add="+")

    def _motion(self, _e=None) -> None:
        if not self.back.winfo_ismapped():
            self.back.place(x=12, y=10)
        if self._back_job:
            self.after_cancel(self._back_job)
        self._back_job = self.after(2000, self._hide_back)

    def _hide_back(self) -> None:
        self._back_job = None
        self.back.place_forget()

    # ------------------------------------------------------------------
    def show(self) -> None:
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.app.focus_set()
        self.refresh()
        self._loop()

    def hide(self) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        self.place_forget()

    def _loop(self) -> None:
        self.refresh()
        self._job = self.after(250, self._loop)

    def refresh(self) -> None:
        br = self.app.screens.get("bridge")
        # отчёт после полёта показываем как обычно — дзен на это время в сторону
        if getattr(br, "debrief", None) is not None:
            if self.winfo_ismapped():
                self.place_forget()
            return
        if not self.winfo_ismapped():
            self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()                      # «живой космос» и оверлеи не должны всплыть поверх
        eng = getattr(br, "engine", None)
        if eng is None:
            self._set_text(t("Выберите миссию или свой текст — Ctrl+2 / Ctrl+3"), 0, plain=True)
            self.stats.configure(text="")
            return
        now = time.perf_counter()
        if eng.errors > self._errors_seen:
            self._err_until = time.monotonic() + 0.35
        self._errors_seen = eng.errors
        i = eng.index
        start = max(0, i - SHOW_BEFORE)
        # начинаем с границы слова — строка не режется посреди слова
        if start:
            sp = eng.text.find(" ", start)
            start = sp + 1 if 0 <= sp < i else start
        chunk = eng.text[start:i + SHOW_AFTER]
        self._set_text(chunk, i - start, err=time.monotonic() < self._err_until)
        cpm = eng.cpm(now)
        acc = eng.accuracy
        el = int(eng.elapsed(now))
        state = getattr(br, "state", "")
        pause = "   ❚❚" if state == "pause" else ""
        meta = getattr(br, "meta", {}) or {}
        self.mode_lbl.configure(text=str(meta.get("title") or "")[:48])
        lang = {"en": "english", "ru": "русский", "uk": "українська", "de": "deutsch"}.get(
            meta.get("text_lang") or meta.get("lang"), meta.get("lang") or "")
        self.stats.configure(text=f"◍ {lang}    {cpm / 5:.0f} wpm   {cpm:.0f} cpm   "
                                  f"{'—' if acc is None else f'{acc:.0f}%'}   "
                                  f"{el // 60:02d}:{el % 60:02d}{pause}")

    def _set_text(self, chunk: str, cur: int, *, err: bool = False, plain: bool = False) -> None:
        tx = self.text
        tx.configure(state="normal")
        tx.delete("1.0", "end")
        if plain:
            tx.insert("end", chunk, "ahead")
        else:
            tx.insert("end", chunk[:cur], "typed")
            if cur < len(chunk):
                tx.insert("end", chunk[cur], "err" if err else "cur")
                tx.insert("end", chunk[cur + 1:], "ahead")
        tx.configure(state="disabled")
        # курсор держим во второй видимой строке: набранное уезжает вверх
        try:
            tx.yview_moveto(0)
            n = tx.count("1.0", f"1.0+{cur}c", "displaylines")
            n = (n[0] if isinstance(n, tuple) else n) or 0
            if n > 1:
                tx.yview_scroll(n - 1, "units")
        except tk.TclError:
            pass


class ZenController:
    """Состояние режима и связь с кабиной."""

    def __init__(self, app) -> None:
        self.app = app
        self.overlay: ZenOverlay | None = None
        self.on = False
        self._esc_job = None

    def _wanted(self) -> bool:
        return bool(self.app.store.settings.get("zen_mode"))

    def toggle(self, on: bool | None = None) -> None:
        on = (not self.on) if on is None else on
        self.app.store.settings["zen_mode"] = on
        try:
            self.app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass
        self.apply()

    def set_palette(self, name: str) -> None:
        if name in PALETTES:
            self.app.store.settings["zen_palette"] = name
            try:
                self.app.store.save_settings()
            except Exception:  # noqa: BLE001
                pass
            self.apply()

    def apply(self) -> None:
        """Показать/скрыть панель: дзен виден только на «Полёте» мостика."""
        show = self._wanted() and getattr(self.app, "current", None) == "bridge"
        if show:
            pal = self.app.store.settings.get("zen_palette", "skin")
            if self.overlay is None or self.overlay.pal_name != pal or self.overlay.pal != _palette(pal):
                if self.overlay is not None:
                    self.overlay.destroy()
                self.overlay = ZenOverlay(self.app, pal)
            self.overlay.show()
        elif self.overlay is not None:
            self.overlay.hide()
            try:
                self.app.focus_set()     # клавиатура — снова пульту, текст и позиция не тронуты
            except tk.TclError:
                pass
        self.on = show
        br = getattr(self.app, "screens", {}).get("bridge")
        btn = getattr(br, "btn_zen", None)
        if btn is not None:
            try:
                btn.set_active(self._wanted())
            except Exception:  # noqa: BLE001
                pass

    def handle_key(self, e) -> str | None:
        """Вызывается первым в Cockpit._on_key. "break" — клавиша съедена."""
        if is_zen_hotkey(e):
            if getattr(self.app, "current", None) == "bridge" or self.on:
                self.toggle()
                return "break"
            return None
        if self.on and getattr(e, "keysym", "") == "Escape":
            br = self.app.screens.get("bridge")
            if br is not None and getattr(br, "debrief", None) is not None:
                return None          # отчёт после полёта закрывается как обычно
            # как в Monkeytype: Esc — заново; Esc Esc (≤400 мс) — назад на борт.
            # Перезапуск ждёт 400 мс, чтобы двойной Esc вернул текст на прежнем месте.
            if self._esc_job is not None:
                self.app.after_cancel(self._esc_job)
                self._esc_job = None
                self.toggle(False)
            else:
                self._esc_job = self.app.after(ESC_DOUBLE_MS, self._esc_restart)
            return "break"
        return None

    def _esc_restart(self) -> None:
        self._esc_job = None
        if self.on:
            try:
                self.app.restart_current()
            except Exception:  # noqa: BLE001
                pass
            self.after_key()

    def after_key(self) -> None:
        if self.on and self.overlay is not None:
            self.overlay.refresh()
