"""Компактная полоса приёмника в шапке (фон между отсеками)."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, RED, blend, px

from . import drag
from .engine import get_engine


MAX_LABEL_PX = 260  # подпись мини-приёмника не шире этого (в px при масштабе 1)
POS_KEY = "radio_mini_pos"  # [доля x, доля y] в окне программы; None — в строке под шапкой


class RadioMiniBar(tk.Frame):
    def __init__(self, master, app, draggable: bool = True) -> None:
        # родитель — окно программы, в строку кладём pack(in_=row): так плашку можно
        # вынуть из строки и положить в любое место окна (place), и она едет вместе с окном
        self.row = master
        super().__init__(master.winfo_toplevel(), bg=blend(BG, CYAN, 0.08),
                         highlightthickness=1, highlightbackground=blend(BG, CYAN, 0.35))
        self.app = app
        self.eng = get_engine()
        self.eng.bind_ui(app)
        self._packed = False
        self._full_text = ""
        self._fit_job = None
        self._last_row_w = None      # последняя ширина строки: без изменений не перерисовываем
        self._last_view = None       # последний текст: одинаковый не перерисовываем
        # слушаем ТОЛЬКО свою строку, а не всё окно: иначе каждое изменение размера
        # любой кнопки вызывало пересчёт приёмника (тысячи событий в секунду)
        self.row.bind("<Configure>", self._on_resize, add="+")
        self.top = self.row.winfo_toplevel()
        self._floating = False

        self.grip = None
        if draggable:
            self.grip = tk.Label(self, text="⠿", bg=self["bg"], fg=MUTED, font=theme.font(9, True))
            self.grip.pack(side=tk.LEFT, padx=(px(4), 0))
        self.lbl = tk.Label(self, text="", bg=self["bg"], fg=CYAN,
                            font=theme.font(9, True), cursor="hand2")
        self.lbl.pack(side=tk.LEFT, padx=px(8), pady=px(3))
        self.lbl.bind("<Button-1>", lambda _e: self._open())
        HudButton(self, "▮▮", self.eng.toggle, height=26, width=36, font_size=8,
                  color=AMBER).pack(side=tk.LEFT, padx=px(2))
        HudButton(self, "−", lambda: self._vol(-8), height=26, width=28, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=px(1))
        HudButton(self, "+", lambda: self._vol(+8), height=26, width=28, font_size=9,
                  color=CYAN).pack(side=tk.LEFT, padx=px(1))
        HudButton(self, "✕", self._stop, height=26, width=28, font_size=8,
                  color=RED).pack(side=tk.LEFT, padx=(px(2), px(6)))
        self.drag = None
        if self.grip is not None:
            st = getattr(getattr(app, "store", None), "settings", {}) or {}
            self.drag = drag.Dragger(self, self.top, [self.grip], drag.load(st, POS_KEY), self._pos_changed)
            self.top.bind("<Configure>", self._on_top_resize, add="+")
        self.eng.subscribe(self._on_eng)
        self._refresh()

    def _pos_changed(self, pos) -> None:
        try:
            self.app.store.settings[POS_KEY] = list(pos) if pos else None
            self.app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass
        if self._packed:
            self._hide()
            self._show()

    def _on_top_resize(self, e) -> None:
        # окно сдвинули/изменили размер: плавающая плашка остаётся в его видимой части
        if e.widget is self.top and self._packed and self._floating:
            xy = self.drag.xy()
            if xy:
                self.place_configure(x=xy[0], y=xy[1])
                self.lift()

    def _vol(self, d: int) -> None:
        self.eng.set_volume(max(0, min(100, self.eng.volume + d)))

    def _stop(self) -> None:
        self.eng.stop()

    def _open(self) -> None:
        from stamina import radio_hook
        if radio_hook.KEY in self.app.screens:
            self.app.show(radio_hook.KEY)
            scr = self.app.screens[radio_hook.KEY]
            if hasattr(scr, "show"):
                scr.show("receiver")

    def _on_eng(self) -> None:
        # главный поток (RadioEngine); after из фона плеера на Windows зависает
        try:
            if self.winfo_exists():
                self._refresh()
        except tk.TclError:
            pass

    def _refresh(self) -> None:
        if not self.winfo_exists():
            return
        st = self.eng.station
        if not self.eng.playing and not st:
            self._hide()
            return
        name = (st or {}).get("name", _t("РАДИО"))[:28]
        track = (self.eng.track or "")[:36]
        mark = "▮▮" if self.eng.playing else "▶"
        text = f"📻 {name}"
        if track:
            text += f" — {track}"
        text += f"  {mark}  🔊{self.eng.volume}"
        view = (text, self.eng.playing)
        if view == self._last_view and self._packed:
            return                      # ничего не изменилось — не трогаем экран
        self._last_view = view
        self._full_text = text
        self.lbl.configure(text=text, fg=GREEN if self.eng.playing else MUTED)
        self._show()
        self._fit()

    def _fit(self) -> None:
        """Подпись станции ужимается с «…» под ширину строки — без update_idletasks и лишних перерисовок."""
        import tkinter.font as tkfont
        text = getattr(self, "_full_text", "")
        if not text or not self._packed:
            return
        try:
            if self._floating:
                cap = px(MAX_LABEL_PX)
                f = tkfont.Font(font=self.lbl.cget("font"))
                if f.measure(text) > cap:
                    while text and f.measure(text + "…") > cap:
                        text = text[:-1]
                    text = text.rstrip() + "…"
                self.lbl.configure(text=text)
                return
            row_w = self.row.winfo_width()
            if row_w < px(120):
                return
            # место, занятое соседями строки (кнопки Мостика слева)
            used = 0
            for ch in self.row.winfo_children():
                if ch is self or not ch.winfo_ismapped():
                    continue
                used += ch.winfo_width() + px(8)
            # кнопки «▮▮ − + ✕» занимают фиксированное место справа — подпись не должна на них наезжать
            avail = row_w - used - px(16) - px(150)
            f = tkfont.Font(font=self.lbl.cget("font"))
            cap = max(px(30), min(avail, px(MAX_LABEL_PX)))
            if f.measure(text) > cap:
                trimmed = text
                while trimmed and f.measure(trimmed + "…") > cap:
                    trimmed = trimmed[:-1]
                text = trimmed.rstrip() + "…"
            self.lbl.configure(text=text)
        except tk.TclError:
            pass

    def _show(self) -> None:
        if not self._packed:
            # справа от кнопок Мостика: кнопки слева, приёмник справа
            xy = self.drag.xy() if self.drag else None
            self._floating = xy is not None
            if self._floating:
                self.place(in_=self.top, x=xy[0], y=xy[1], anchor="nw")
                self.lift()
                self.after(50, lambda: self._on_top_resize(type("E", (), {"widget": self.top})()))
            else:
                self.pack(in_=self.row, side=tk.RIGHT, padx=px(6), pady=(px(2), px(2)))
            self._packed = True
            self._last_row_w = None
            # один повторный пересчёт, когда строка уже разложилась с кнопками-соседями
            if self._fit_job:
                self.after_cancel(self._fit_job)
            self._fit_job = self.after(300, self._fit)

    def _on_resize(self, e) -> None:
        # Реагируем только на реальное изменение ширины строки: иначе каждое событие
        # раскладки снова запускало пересчёт и перерисовку подписи.
        try:
            if not self.winfo_exists() or not self._packed:
                return
            w = int(getattr(e, "width", 0) or 0)
        except tk.TclError:
            return
        if w and w == self._last_row_w:
            return
        self._last_row_w = w
        if self._fit_job:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(120, self._fit)

    def _hide(self) -> None:
        if self._packed:
            self.pack_forget()
            self.place_forget()
            self._packed = False

    def destroy(self) -> None:
        self.eng.unsubscribe(self._on_eng)
        super().destroy()
