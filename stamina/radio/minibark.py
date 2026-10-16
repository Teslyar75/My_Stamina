"""Компактная полоса приёмника в шапке (фон между отсеками)."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, RED, blend, px

from .engine import get_engine


MAX_LABEL_PX = 260  # подпись мини-приёмника не шире этого (в px при масштабе 1)


class RadioMiniBar(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=blend(BG, CYAN, 0.08),
                         highlightthickness=1, highlightbackground=blend(BG, CYAN, 0.35))
        self.app = app
        self.eng = get_engine()
        self.eng.bind_ui(app)
        self._packed = False
        self._full_text = ""
        self._fit_job = None
        app.bind("<Configure>", self._on_resize, add="+")

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
        self.eng.subscribe(self._on_eng)
        self._refresh()

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
        self._full_text = text
        self.lbl.configure(text=text, fg=GREEN if self.eng.playing else MUTED)
        self._show()
        self._fit()

    def _fit(self) -> None:
        """Подпись станции ужимается с «…» под свободное место шапки — окно не растёт, «ЭКРАН» не уезжает."""
        import tkinter.font as tkfont
        text = getattr(self, "_full_text", "")
        if not text or not self._packed:
            return
        try:
            top = self.master.master            # строка шапки: логотип · зоны · правый блок
            win = self.winfo_toplevel().winfo_width()
            if win < 50:
                return
            self.lbl.configure(text="")
            self.update_idletasks()
            avail = win - top.winfo_reqwidth() - px(24)
            f = tkfont.Font(font=self.lbl.cget("font"))
            cap = min(avail, px(MAX_LABEL_PX))
            if cap < px(40):
                # места нет даже под название — прячем мини-приёмник целиком, «ЭКРАН» важнее
                self.lbl.configure(text="📻")
                self.update_idletasks()
                if top.winfo_reqwidth() > win:
                    self.pack_forget()
                    self._packed = False
                return
            if f.measure(text) > cap:
                while text and f.measure(text + "…") > cap:
                    text = text[:-1]
                text = text.rstrip() + "…"
            self.lbl.configure(text=text)
        except tk.TclError:
            pass

    def _show(self) -> None:
        if not self._packed:
            self.pack(side=tk.RIGHT, padx=px(6))
            self._packed = True

    def _on_resize(self, e) -> None:
        try:
            if not self.winfo_exists() or e.widget is not self.winfo_toplevel() or not self._packed:
                return
        except tk.TclError:
            return
        if self._fit_job:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(120, self._fit)

    def _hide(self) -> None:
        if self._packed:
            self.pack_forget()
            self._packed = False

    def destroy(self) -> None:
        self.eng.unsubscribe(self._on_eng)
        super().destroy()
