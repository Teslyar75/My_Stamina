"""Вкладка «РАДИОРУБКА»: ЭФИР (поиск волн) и ПРИЁМНИК."""
from __future__ import annotations

from stamina.i18n import t as _t

import threading
import tkinter as tk
from tkinter import ttk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, RED, TEXT, blend, px

from . import browser, store
from .engine import get_engine
from .player import backend_ok, backend_name


class RadioScreen(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.eng = get_engine()
        self.eng.reload_store()
        self._stations: list[dict] = []
        self._pulse = 0
        self._eq_job = None

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X, padx=px(14), pady=(px(8), px(4)))
        tk.Label(bar, text=_t("РАДИОРУБКА"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(side=tk.LEFT)
        self.tab_btns = {}
        for key, title in (("air", _t("ЭФИР")), ("receiver", _t("ПРИЁМНИК"))):
            b = HudButton(bar, title, lambda k=key: self.show(k), height=30, font_size=9, width=110)
            b.pack(side=tk.LEFT, padx=px(4))
            self.tab_btns[key] = b
        self.lbl_backend = tk.Label(bar, text="", bg=BG, fg=MUTED, font=theme.font(8))
        self.lbl_backend.pack(side=tk.RIGHT)

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self.pages = {
            "air": self._build_air(self.body),
            "receiver": self._build_receiver(self.body),
        }
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")
        self.current = "air"
        self.show("air")
        self.eng.subscribe(self._on_engine)
        self.after(80, self._boot_catalog)
        self.after(200, self._tick_eq)

    # ------------------------------------------------------------------ lifecycle
    def on_leave(self) -> None:
        pass

    def close(self) -> None:
        self.eng.unsubscribe(self._on_engine)
        if self._eq_job:
            try:
                self.after_cancel(self._eq_job)
            except tk.TclError:
                pass

    def on_key(self, e) -> str | None:
        k = e.keysym
        if k == "space":
            self.eng.toggle()
            return "break"
        if k in ("plus", "equal", "KP_Add"):
            self.eng.set_volume(min(100, self.eng.volume + 5))
            self.vol.set(self.eng.volume)
            return "break"
        if k in ("minus", "KP_Subtract"):
            self.eng.set_volume(max(0, self.eng.volume - 5))
            self.vol.set(self.eng.volume)
            return "break"
        if k == "Right":
            self.eng.next_favorite()
            return "break"
        if k == "Left":
            self.eng.prev_favorite()
            return "break"
        return None

    def show(self, name: str) -> None:
        self.current = name
        self.pages[name].tkraise()
        for k, b in self.tab_btns.items():
            b.set_active(k == name)
        if name == "receiver":
            self._refresh_receiver()
        self._update_backend_label()

    def _on_engine(self) -> None:
        try:
            self.after(0, self._refresh_receiver)
            self.after(0, self._paint_list)
        except tk.TclError:
            pass

    def _update_backend_label(self) -> None:
        be = backend_name()
        if be:
            self.lbl_backend.configure(text=_t("приёмник: {0}").format(be.upper()), fg=MUTED)
        else:
            self.lbl_backend.configure(
                text=_t("нет mpv/ffplay — установите mpv для эфира"), fg=AMBER)

    # ------------------------------------------------------------------ air
    def _build_air(self, parent) -> tk.Frame:
        fr = tk.Frame(parent, bg=BG)
        left = HudPanel(fr, _t("ФИЛЬТРЫ ВОЛН"), accent=CYAN)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(px(10), px(6)), pady=px(6))
        left.configure(width=px(240))
        b = left.body

        tk.Label(b, text=_t("ПОИСК"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.ent_q = tk.Entry(b, bg=blend(PANEL, CYAN, 0.08), fg=TEXT, insertbackground=CYAN,
                              relief=tk.FLAT, font=theme.font(11))
        self.ent_q.pack(fill=tk.X, pady=(px(2), px(8)))
        self.ent_q.bind("<Return>", lambda _e: self._do_search())

        tk.Label(b, text=_t("СТРАНА"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.cmb_country = ttk.Combobox(b, state="readonly", width=28)
        self.cmb_country.pack(fill=tk.X, pady=(px(2), px(8)))

        tk.Label(b, text=_t("ЯЗЫК"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.cmb_lang = ttk.Combobox(b, state="readonly", width=28)
        self.cmb_lang.pack(fill=tk.X, pady=(px(2), px(8)))

        tk.Label(b, text=_t("ЖАНР"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.cmb_tag = ttk.Combobox(b, state="readonly", width=28)
        self.cmb_tag.pack(fill=tk.X, pady=(px(2), px(8)))

        HudButton(b, _t("🔍 ИСКАТЬ"), self._do_search, color=CYAN, height=34).pack(fill=tk.X, pady=px(4))
        HudButton(b, _t("★ МОИ ВОЛНЫ"), self._show_favorites, color=AMBER, height=32).pack(fill=tk.X, pady=px(2))
        HudButton(b, _t("ТОП ЭФИРА"), self._boot_catalog, color=GREEN, height=32).pack(fill=tk.X, pady=px(2))

        self.lbl_status = tk.Label(b, text="", bg=PANEL, fg=MUTED, wraplength=px(200),
                                   justify="left", font=theme.font(8))
        self.lbl_status.pack(anchor="w", pady=(px(10), 0))

        right = tk.Frame(fr, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, px(10)), pady=px(6))
        head = tk.Frame(right, bg=BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=_t("ЧАСТОТЫ"), bg=BG, fg=CYAN, font=theme.font(11, True)).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(head, text="", bg=BG, fg=MUTED, font=theme.font(9))
        self.lbl_count.pack(side=tk.LEFT, padx=px(10))

        wrap = tk.Frame(right, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True, pady=(px(4), 0))
        sb = tk.Scrollbar(wrap)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, yscrollcommand=sb.set)
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.configure(command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg=BG)
        self._list_win = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda _e: self.list_canvas.configure(
            scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", self._on_list_cfg)
        self.list_canvas.bind("<MouseWheel>", self._on_wheel)
        self.list_inner.bind("<MouseWheel>", self._on_wheel)
        return fr

    def _safe_after(self, fn) -> None:
        try:
            if self.winfo_exists():
                self.after(0, fn)
        except (tk.TclError, RuntimeError):
            pass

    def _on_list_cfg(self, e) -> None:
        self.list_canvas.itemconfigure(self._list_win, width=e.width)

    def _on_wheel(self, e) -> None:
        if self.current != "air":
            return
        self.list_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _boot_catalog(self) -> None:
        self.lbl_status.configure(text=_t("Загрузка частот…"), fg=AMBER)
        box: dict = {}

        def work():
            items, err = browser.top_stations(70)
            countries = browser.countries()
            langs = browser.languages()
            tags = browser.tags()
            box["items"] = items
            box["err"] = err
            box["countries"] = countries
            box["langs"] = langs
            box["tags"] = tags

        def done():
            if not self.winfo_exists():
                return
            self.cmb_country["values"] = [_t("(все страны)")] + [
                f"{n} ({c})" for n, c in box.get("countries") or []]
            self.cmb_country.current(0)
            self.cmb_lang["values"] = [_t("(все языки)")] + list(box.get("langs") or [])
            self.cmb_lang.current(0)
            self.cmb_tag["values"] = [_t("(все жанры)")] + list(box.get("tags") or [])
            self.cmb_tag.current(0)
            self._stations = box.get("items") or []
            err = box.get("err")
            if err == "cache":
                self.lbl_status.configure(text=_t("Нет сети — показан кэш частот"), fg=AMBER)
            elif err:
                self.lbl_status.configure(text=_t("Нет связи с эфиром: {0}").format(err), fg=RED)
            else:
                self.lbl_status.configure(text=_t("Топ по голосам radio-browser"), fg=MUTED)
            self._paint_list()

        threading.Thread(target=lambda: (work(), self._safe_after(done)), daemon=True).start()

    def _filters(self) -> dict:
        c = self.cmb_country.get() if self.cmb_country.get() and self.cmb_country.current() > 0 else ""
        code = ""
        if c and "(" in c and c.endswith(")"):
            code = c[c.rfind("(") + 1:-1]
        lang = self.cmb_lang.get() if self.cmb_lang.current() > 0 else ""
        tag = self.cmb_tag.get() if self.cmb_tag.current() > 0 else ""
        return {"name": self.ent_q.get().strip(), "country": code, "language": lang, "tag": tag}

    def _do_search(self) -> None:
        f = self._filters()
        self.lbl_status.configure(text=_t("Поиск…"), fg=AMBER)
        box: dict = {}

        def work():
            items, err = browser.search_stations(**f)
            box["items"], box["err"] = items, err

        def done():
            if not self.winfo_exists():
                return
            self._stations = box.get("items") or []
            err = box.get("err")
            if err:
                self.lbl_status.configure(text=_t("Нет связи с эфиром: {0}").format(err), fg=RED)
            else:
                self.lbl_status.configure(text=_t("Найдено: {0}").format(len(self._stations)), fg=MUTED)
            self._paint_list()

        threading.Thread(target=lambda: (work(), self._safe_after(done)), daemon=True).start()

    def _show_favorites(self) -> None:
        self.eng.reload_store()
        self._stations = list(self.eng.data.get("favorites") or [])
        self.lbl_status.configure(text=_t("Мои волны пилота"), fg=AMBER)
        self._paint_list()

    def _paint_list(self) -> None:
        for w in self.list_inner.winfo_children():
            w.destroy()
        self.lbl_count.configure(text=_t("{0} станций").format(len(self._stations)))
        if not self._stations:
            tk.Label(self.list_inner, text=_t("Станции не найдены"), bg=BG, fg=MUTED,
                     font=theme.font(11)).pack(pady=px(30))
            return
        fav_uuids = {f.get("uuid") for f in (self.eng.data.get("favorites") or [])}
        playing = (self.eng.station or {}).get("uuid")
        for st in self._stations[:120]:
            row = tk.Frame(self.list_inner, bg=blend(PANEL, CYAN, 0.06),
                           highlightbackground=CYAN if st.get("uuid") == playing else blend(PANEL, CYAN, 0.25),
                           highlightthickness=1)
            row.pack(fill=tk.X, pady=px(3), padx=px(2))
            logo = tk.Canvas(row, width=px(44), height=px(44), bg=blend(PANEL, CYAN, 0.12),
                             highlightthickness=0)
            logo.pack(side=tk.LEFT, padx=px(6), pady=px(6))
            self._draw_antenna(logo)
            info = tk.Frame(row, bg=row["bg"])
            info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=px(6))
            tk.Label(info, text=st.get("name", "—")[:48], bg=row["bg"], fg=TEXT,
                     font=theme.font(11, True), anchor="w").pack(fill=tk.X)
            sub = " · ".join(x for x in (
                st.get("country") or st.get("countrycode"),
                (st.get("tags") or "")[:40],
                f"{st['bitrate']} kbps" if st.get("bitrate") else "",
            ) if x)
            tk.Label(info, text=sub or "—", bg=row["bg"], fg=MUTED, font=theme.font(8),
                     anchor="w").pack(fill=tk.X)
            star = "★" if st.get("uuid") in fav_uuids else "☆"
            HudButton(row, star, lambda s=st: self._toggle_fav(s), height=30, font_size=12,
                      width=40, color=AMBER).pack(side=tk.RIGHT, padx=px(4))
            HudButton(row, _t("▶"), lambda s=st: self._play(s), height=30, font_size=11,
                      width=44, color=GREEN).pack(side=tk.RIGHT, padx=px(4))

    def _draw_antenna(self, c: tk.Canvas) -> None:
        w, h = px(44), px(44)
        c.create_oval(8, 8, w - 8, h - 8, outline=CYAN, width=2)
        c.create_line(w // 2, 12, w // 2, h - 10, fill=AMBER, width=2)
        c.create_line(w // 2, 14, w // 2 + 10, 22, fill=AMBER, width=2)
        c.create_line(w // 2, 14, w // 2 - 10, 22, fill=AMBER, width=2)

    def _toggle_fav(self, st: dict) -> None:
        store.toggle_favorite(self.eng.data, st)
        self._paint_list()
        self.app.set_status(_t("МОИ ВОЛНЫ обновлены"), CYAN)

    def _play(self, st: dict) -> None:
        if not backend_ok():
            self.app.set_status(_t("Установите mpv (или ffplay) для приёма эфира"), AMBER)
            self.lbl_status.configure(
                text=_t("Нужен mpv: winget install mpv / sudo apt install mpv"), fg=AMBER)
            return
        ok = self.eng.play_station(st)
        if ok:
            self.app.set_status(_t("В ЭФИРЕ · {0}").format(st.get("name", "")), GREEN)
            self.show("receiver")
        else:
            self.app.set_status(_t("Не удалось открыть поток"), RED)

    # ------------------------------------------------------------------ receiver
    def _build_receiver(self, parent) -> tk.Frame:
        fr = tk.Frame(parent, bg=BG)
        card = HudPanel(fr, _t("ПРИЁМНИК"), accent=GREEN)
        card.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(10))
        body = card.body

        top = tk.Frame(body, bg=PANEL)
        top.pack(fill=tk.X, pady=px(8))
        self.rx_logo = tk.Canvas(top, width=px(140), height=px(140),
                                 bg=blend(PANEL, CYAN, 0.1), highlightthickness=1,
                                 highlightbackground=CYAN)
        self.rx_logo.pack(side=tk.LEFT, padx=px(10))
        self._draw_antenna(self.rx_logo)

        meta = tk.Frame(top, bg=PANEL)
        meta.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(10))
        self.rx_name = tk.Label(meta, text=_t("Нет станции"), bg=PANEL, fg=TEXT,
                                font=theme.font(16, True), anchor="w")
        self.rx_name.pack(fill=tk.X)
        self.rx_track = tk.Label(meta, text="", bg=PANEL, fg=CYAN, font=theme.font(12),
                                 anchor="w", wraplength=px(520), justify="left")
        self.rx_track.pack(fill=tk.X, pady=(px(6), 0))
        live = tk.Frame(meta, bg=PANEL)
        live.pack(anchor="w", pady=px(10))
        self.rx_dot = tk.Label(live, text="●", bg=PANEL, fg=MUTED, font=theme.font(12))
        self.rx_dot.pack(side=tk.LEFT)
        self.rx_live = tk.Label(live, text=_t("ТИШИНА"), bg=PANEL, fg=MUTED,
                                font=theme.font(10, True))
        self.rx_live.pack(side=tk.LEFT, padx=px(6))
        self.eq = tk.Canvas(meta, height=px(36), bg=blend(PANEL, CYAN, 0.08),
                            highlightthickness=0)
        self.eq.pack(fill=tk.X, pady=px(8))

        controls = tk.Frame(body, bg=PANEL)
        controls.pack(fill=tk.X, pady=px(8))
        HudButton(controls, _t("⏮"), self.eng.prev_favorite, height=40, width=56,
                  color=CYAN).pack(side=tk.LEFT, padx=px(4))
        self.btn_play = HudButton(controls, _t("▶ ПУСК"), self._toggle_play, height=44,
                                  width=140, color=GREEN, font_size=12)
        self.btn_play.pack(side=tk.LEFT, padx=px(8))
        HudButton(controls, _t("⏹ СТОП"), self.eng.stop, height=40, width=100,
                  color=RED).pack(side=tk.LEFT, padx=px(4))
        HudButton(controls, _t("⏭"), self.eng.next_favorite, height=40, width=56,
                  color=CYAN).pack(side=tk.LEFT, padx=px(4))

        vol_fr = tk.Frame(body, bg=PANEL)
        vol_fr.pack(fill=tk.X, pady=px(6))
        tk.Label(vol_fr, text=_t("ГРОМКОСТЬ"), bg=PANEL, fg=MUTED,
                 font=theme.font(8, True)).pack(side=tk.LEFT)
        self.vol = tk.Scale(vol_fr, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=1,
                            bg=PANEL, fg=CYAN, troughcolor=blend(PANEL, "#000000", 0.35),
                            highlightthickness=0, command=self._on_vol)
        self.vol.set(self.eng.volume)
        self.vol.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(10))

        opts = tk.Frame(body, bg=PANEL)
        opts.pack(fill=tk.X, pady=px(4))
        self.var_duck = tk.BooleanVar(value=bool(self.eng.data.get("duck_typing")))
        tk.Checkbutton(opts, text=_t("приглушать радио во время набора"), variable=self.var_duck,
                       command=self._save_duck, bg=PANEL, fg=TEXT, selectcolor=BG,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=theme.font(9)).pack(anchor="w")

        tk.Label(body, text=_t("ИСТОРИЯ ТРЕКОВ (сеанс)"), bg=PANEL, fg=MUTED,
                 font=theme.font(9, True)).pack(anchor="w", pady=(px(10), px(4)))
        self.hist = tk.Listbox(body, bg=blend(PANEL, CYAN, 0.06), fg=TEXT,
                               selectbackground=CYAN, font=theme.font(10),
                               height=8, relief=tk.FLAT, highlightthickness=1,
                               highlightbackground=blend(PANEL, CYAN, 0.3))
        self.hist.pack(fill=tk.BOTH, expand=True)
        return fr

    def _save_duck(self) -> None:
        self.eng.data["duck_typing"] = bool(self.var_duck.get())
        store.save(self.eng.data)

    def _on_vol(self, v) -> None:
        self.eng.set_volume(int(float(v)))

    def _toggle_play(self) -> None:
        if self.eng.playing:
            self.eng.stop()
        elif self.eng.station:
            self._play(self.eng.station)

    def _refresh_receiver(self) -> None:
        st = self.eng.station
        if st:
            self.rx_name.configure(text=st.get("name", "—")[:60])
        else:
            self.rx_name.configure(text=_t("Нет станции"))
        track = self.eng.track or (st.get("tags", "") if st else "")
        self.rx_track.configure(text=track or _t("ожидание метаданных эфира…"))
        if self.eng.playing:
            self.rx_dot.configure(fg=RED)
            self.rx_live.configure(text=_t("В ЭФИРЕ"), fg=RED)
            self.btn_play.set_text(_t("▮▮ ПАУЗА"))
        else:
            self.rx_dot.configure(fg=MUTED)
            self.rx_live.configure(text=_t("ТИШИНА"), fg=MUTED)
            self.btn_play.set_text(_t("▶ ПУСК"))
        self.hist.delete(0, tk.END)
        for t in self.eng.history:
            self.hist.insert(tk.END, t)
        try:
            self.vol.set(self.eng.volume)
        except tk.TclError:
            pass

    def _tick_eq(self) -> None:
        if not self.winfo_exists():
            return
        self._pulse = (self._pulse + 1) % 20
        c = self.eq
        c.delete("all")
        w = max(c.winfo_width(), 100)
        h = px(36)
        n = 24
        playing = self.eng.playing
        for i in range(n):
            if playing:
                amp = 0.25 + 0.75 * abs(((i * 3 + self._pulse) % 10) / 10 - 0.3)
            else:
                amp = 0.08
            bh = max(2, int(h * amp))
            x0 = 4 + i * (w - 8) / n
            c.create_rectangle(x0, h - bh, x0 + (w - 8) / n - 2, h - 2,
                               fill=CYAN if playing else MUTED, outline="")
        if self.eng.playing and self._pulse % 2 == 0:
            self.rx_dot.configure(fg=RED if self._pulse % 4 < 2 else blend(RED, PANEL, 0.5))
        self._eq_job = self.after(120, self._tick_eq)
