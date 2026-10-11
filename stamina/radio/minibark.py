"""Компактная полоса приёмника в шапке (фон между отсеками)."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, RED, blend, px

from .engine import get_engine


class RadioMiniBar(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=blend(BG, CYAN, 0.08),
                         highlightthickness=1, highlightbackground=blend(BG, CYAN, 0.35))
        self.app = app
        self.eng = get_engine()
        self._packed = False

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
        try:
            self.after(0, self._refresh)
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
        self.lbl.configure(text=text, fg=GREEN if self.eng.playing else MUTED)
        self._show()

    def _show(self) -> None:
        if not self._packed:
            self.pack(side=tk.RIGHT, padx=px(6))
            self._packed = True

    def _hide(self) -> None:
        if self._packed:
            self.pack_forget()
            self._packed = False

    def destroy(self) -> None:
        self.eng.unsubscribe(self._on_eng)
        super().destroy()
