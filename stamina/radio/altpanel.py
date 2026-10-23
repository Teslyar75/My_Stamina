"""Плавающая панель радио в «Пульт-кабине» (alt_ui): справа поверх окна отсека.

Логика — та же, что у плашки классического вида (RadioMiniBar): движок ``get_engine()``,
пауза/пуск, громкость ±/ползунок, стоп, станции из избранного ◂◂ ▸▸, клик по названию —
в РАДИОРУБКУ. Вид — по скину: рамка ``alt_ui.wrap`` (hud, латунь, иллюминатор, неон,
гравюра, буквица, кисть), подпись, значок и акцент профиля, шрифты темы.
Видна, пока играет станция; «›» сворачивает в ярлычок, наведение — раскрывает.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.theme import blend, px

from .engine import get_engine

#: Профиль alt-скина → (заголовок, значок, акцентный токен, фон-смесь)
STYLE: dict[str, tuple[str, str, str, float]] = {
    "starship": ("АНТЕННЫЙ ОТСЕК", "≋", "CYAN", 0.10),
    "steampunk": ("ГРАММОФОН", "☊", "AMBER", 0.14),
    "bathyscaphe": ("ГИДРОФОН", "◉", "CYAN", 0.10),
    "neon_city": ("RADIO · FM", "≋", "PURPLE", 0.16),
    "old_england": ("WIRELESS", "☎", "AMBER", 0.10),
    "scriptorium": ("ПЕСНОПЕНИЯ", "♪", "AMBER", 0.08),
    "zen_garden": ("ЗВУКИ САДА", "≋", "GREEN", 0.06),
    "generic": ("РАДИО", "≋", "CYAN", 0.08),
}
STATE_KEY = "alt_radio_collapsed"


def style_of(prof: str) -> tuple[str, str, str, float]:
    return STYLE.get(prof, STYLE["generic"])


class AltRadioPanel:
    """Создаётся в ``alt_ui.build_chrome``: ``AltRadioPanel(app, app._alt_body, prof)``."""

    def __init__(self, app, host, prof: str) -> None:
        from stamina import alt_ui
        self.app, self.host, self.prof = app, host, prof
        self.eng = get_engine()
        self.eng.bind_ui(app)
        title, self.glyph, acc_name, mix = style_of(prof)
        self.acc = getattr(theme, acc_name, theme.CYAN)
        self.bg = blend(theme.BG, self.acc, mix)
        st = getattr(getattr(app, "store", None), "settings", {}) or {}
        self.collapsed = bool(st.get(STATE_KEY, False))
        self._hover = False
        self._leave_job = None
        self._shown = None          # None — скрыта, "full" / "tab"
        self._last = None

        # полная панель
        self.frame = alt_ui.wrap(host, prof, bg=self.bg, title=_t(title), edge=8)
        self.frame.living_skip = True
        inner = self.frame.inner
        head = tk.Frame(inner, bg=self.bg)
        head.pack(fill=tk.X, padx=px(6), pady=(px(4), 0))
        tk.Label(head, text=f"{self.glyph} {_t(title)}", bg=self.bg, fg=blend(self.acc, theme.TEXT, 0.25),
                 font=theme.font(7, True)).pack(side=tk.LEFT)
        self.btn_fold = HudButton(head, "›", self.fold, height=20, width=24, font_size=8, color=theme.MUTED)
        self.btn_fold.pack(side=tk.RIGHT)
        self.lbl = tk.Label(inner, text="", bg=self.bg, fg=theme.GREEN, font=theme.font(9, True),
                            cursor="hand2", anchor="w", justify="left", wraplength=px(190))
        self.lbl.pack(fill=tk.X, padx=px(8), pady=(px(4), 0))
        self.lbl.bind("<Button-1>", lambda _e: self.open_radio())
        self.track = tk.Label(inner, text="", bg=self.bg, fg=theme.MUTED, font=theme.font(8),
                              anchor="w", justify="left", wraplength=px(190))
        self.track.pack(fill=tk.X, padx=px(8))
        row = tk.Frame(inner, bg=self.bg)
        row.pack(padx=px(6), pady=px(4))
        self.btn_prev = HudButton(row, "◂◂", self.eng.prev_favorite, height=26, width=34, font_size=8, color=self.acc)
        self.btn_play = HudButton(row, "▮▮", self.eng.toggle, height=26, width=40, font_size=8, color=theme.AMBER)
        self.btn_next = HudButton(row, "▸▸", self.eng.next_favorite, height=26, width=34, font_size=8, color=self.acc)
        self.btn_stop = HudButton(row, "✕", self.eng.stop, height=26, width=28, font_size=8, color=theme.RED)
        for b in (self.btn_prev, self.btn_play, self.btn_next, self.btn_stop):
            b.pack(side=tk.LEFT, padx=px(1))
        vrow = tk.Frame(inner, bg=self.bg)
        vrow.pack(fill=tk.X, padx=px(6), pady=(0, px(6)))
        self.btn_down = HudButton(vrow, "−", lambda: self.step(-8), height=24, width=26, font_size=9, color=self.acc)
        self.btn_down.pack(side=tk.LEFT)
        self.vol = tk.IntVar(value=self.eng.volume)
        self.scale = tk.Scale(vrow, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.vol, showvalue=False,
                              length=px(96), sliderlength=px(14), width=px(8), bd=0, highlightthickness=0,
                              bg=self.bg, troughcolor=blend(self.bg, self.acc, 0.35),
                              activebackground=self.acc, command=self._on_scale)
        self.scale.pack(side=tk.LEFT, padx=px(3))
        self.btn_up = HudButton(vrow, "+", lambda: self.step(+8), height=24, width=26, font_size=9, color=self.acc)
        self.btn_up.pack(side=tk.LEFT)
        self.vlbl = tk.Label(vrow, text="", bg=self.bg, fg=theme.MUTED, font=theme.font(8, mono=True), width=3)
        self.vlbl.pack(side=tk.LEFT, padx=(px(3), 0))
        self._scale_job = None
        self._syncing = False

        # свёрнутый ярлычок
        self.tab = alt_ui.wrap(host, prof, bg=self.bg, edge=6)
        self.tab.living_skip = True
        self.tab_lbl = tk.Label(self.tab.inner, text=f"{self.glyph}\n‹", bg=self.bg, fg=self.acc,
                                font=theme.font(11, True), cursor="hand2", padx=px(4), pady=px(6))
        self.tab_lbl.pack()
        self.tab_lbl.bind("<Button-1>", lambda _e: self.unfold())
        for w in (self.tab, self.tab_lbl):
            w.bind("<Enter>", self._enter, add="+")
        self.frame.bind("<Enter>", self._enter, add="+")
        self.frame.bind("<Leave>", self._leave, add="+")

        self.eng.subscribe(self._on_eng)
        self.refresh()

    # --- действия: те же, что у плашки классики ---
    def step(self, d: int) -> None:
        self.eng.set_volume(max(0, min(100, self.eng.volume + d)))

    def _on_scale(self, _v=None) -> None:
        if self._syncing:
            return
        if self._scale_job:
            self.frame.after_cancel(self._scale_job)
        self._scale_job = self.frame.after(150, lambda: self.eng.set_volume(int(self.vol.get())))

    def open_radio(self) -> None:
        from stamina import radio_hook
        if radio_hook.KEY in getattr(self.app, "screens", {}):
            self.app.show(radio_hook.KEY)
            scr = self.app.screens[radio_hook.KEY]
            if hasattr(scr, "show"):
                scr.show("receiver")

    def fold(self) -> None:
        self.collapsed, self._hover = True, False
        self._save()
        self.refresh(force=True)

    def unfold(self) -> None:
        self.collapsed, self._hover = False, False
        self._save()
        self.refresh(force=True)

    def _save(self) -> None:
        try:
            self.app.store.settings[STATE_KEY] = self.collapsed
            self.app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass

    def _enter(self, _e=None) -> None:
        if self._leave_job:
            self.frame.after_cancel(self._leave_job)
            self._leave_job = None
        if self.collapsed and not self._hover:
            self._hover = True
            self.refresh(force=True)

    def _leave(self, e=None) -> None:
        if not (self.collapsed and self._hover):
            return
        # уход с панели (не на дочерний виджет): сворачиваем с небольшой задержкой
        try:
            x, y = self.frame.winfo_pointerxy()
            w = self.frame.winfo_containing(x, y)
            if w is not None and str(w).startswith(str(self.frame)):
                return
        except tk.TclError:
            pass
        self._leave_job = self.frame.after(700, self._hover_off)

    def _hover_off(self) -> None:
        self._leave_job = None
        self._hover = False
        self.refresh(force=True)

    # --- вид ---
    def _on_eng(self) -> None:
        try:
            if self.frame.winfo_exists():
                self.refresh()
        except tk.TclError:
            pass

    def mode(self) -> str | None:
        if not self.eng.playing and not self.eng.station:
            return None
        return "tab" if self.collapsed and not self._hover else "full"

    def refresh(self, force: bool = False) -> None:
        st = self.eng.station or {}
        playing = self.eng.playing
        view = (self.mode(), st.get("name"), self.eng.track, playing, self.eng.volume)
        if view == self._last and not force:
            return
        self._last = view
        self.lbl.configure(text=f"📻 {(st.get('name') or _t('РАДИО'))[:40]}",
                           fg=theme.GREEN if playing else theme.MUTED)
        self.track.configure(text=(self.eng.track or "")[:60])
        self.btn_play.set_text("▮▮" if playing else "▶") if hasattr(self.btn_play, "set_text") else None
        self._syncing = True
        self.vol.set(self.eng.volume)
        self._syncing = False
        self.vlbl.configure(text=str(self.eng.volume))
        favs = bool((getattr(self.eng, "data", {}) or {}).get("favorites"))
        for b in (self.btn_prev, self.btn_next):
            try:
                b.set_enabled(favs) if hasattr(b, "set_enabled") else None
            except Exception:  # noqa: BLE001
                pass
        self._place(self.mode())

    def _place(self, mode: str | None) -> None:
        if mode == self._shown:
            if mode:
                (self.frame if mode == "full" else self.tab).lift()
            return
        self._shown = mode
        self.frame.place_forget()
        self.tab.place_forget()
        if mode == "full":
            self.frame.place(relx=1.0, rely=0.5, anchor="e", x=-px(4))
            self.frame.lift()
        elif mode == "tab":
            self.tab.place(relx=1.0, rely=0.5, anchor="e", x=-px(2))
            self.tab.lift()

    def destroy(self) -> None:
        self.eng.unsubscribe(self._on_eng)
        for w in (self.frame, self.tab):
            try:
                w.destroy()
            except tk.TclError:
                pass
