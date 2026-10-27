"""Вкладка «РАДИОРУБКА»: ЭФИР (поиск волн) и ПРИЁМНИК."""
from __future__ import annotations

from stamina.i18n import t as _t

import queue
import threading
import tkinter as tk
from tkinter import ttk

from stamina import theme
from stamina.adapt import ensure_hud_combo_style, make_vscroll
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, RED, TEXT, blend, px

from . import browser, store
from .engine import get_engine
from .player import backend_ok, backend_name


class RadioScreen(tk.Frame):
    def page_help_key(self) -> str:
        return f"radio.{self.current or 'air'}"

    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.eng = get_engine()
        self.eng.bind_ui(self.winfo_toplevel())
        self.eng.reload_store()
        self._stations: list[dict] = []
        self._cards: dict[str, dict] = {}
        self._list_cols = 0
        self._reflow_job = None
        self._pulse = 0
        self._eq_job = None
        self._ui_q: queue.SimpleQueue = queue.SimpleQueue()
        self._catalog_booted = False
        self.after(50, self._drain_ui)

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X, padx=px(14), pady=(px(8), px(4)))
        tk.Label(bar, text=_t("РАДИОРУБКА"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(side=tk.LEFT)
        self.tab_btns = {}
        for key, title in (("air", _t("ЭФИР")), ("receiver", _t("ПРИЁМНИК"))):
            b = HudButton(bar, title, lambda k=key: self.show(k), height=30, font_size=9, width=110)
            b.pack(side=tk.LEFT, padx=px(4))
            self.tab_btns[key] = b
        # справка в своей рамке: иначе alt-шапка считает её вкладкой («?» в списке ОБЗОР)
        hbox = tk.Frame(bar, bg=BG)
        hbox.pack(side=tk.RIGHT, padx=(px(8), 0))
        HudButton(hbox, "?", lambda: self.app.open_help(), height=28, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
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
        self.after(200, self._tick_eq)

    # ------------------------------------------------------------------ lifecycle
    def on_leave(self) -> None:
        pass

    def close(self) -> None:
        self.eng.unsubscribe(self._on_engine)
        for job in (self._eq_job, self._reflow_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._reflow_job = None

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
        if k == "F7":
            self.show("air")
            self._show_skin_waves()
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
        elif self._cards:
            self._sync_cards()          # вернулись с приёмника — подсветка эфира свежая
        self._update_backend_label()
        hook = getattr(self.app, "_alt_page_hook", None)   # только в alt-оболочке
        if hook is not None:
            hook()

    def refresh(self) -> None:
        """Вызывается пультом при открытии вкладки «РАДИОРУБКА»."""
        self._update_backend_label()
        if not self._catalog_booted:
            self._catalog_booted = True
            self.after(40, self._boot_catalog)
        if self.current == "receiver":
            self._refresh_receiver()

    def _on_engine(self) -> None:
        # вызывается уже из главного потока (RadioEngine._drain_ui)
        try:
            if self.winfo_exists():
                self._refresh_receiver()
                if self.current == "air":
                    self._sync_cards()
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
        self.cmb_country = ttk.Combobox(b, state="readonly", width=28, style=ensure_hud_combo_style(b))
        self.cmb_country.pack(fill=tk.X, pady=(px(2), px(8)))

        tk.Label(b, text=_t("ЯЗЫК"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.cmb_lang = ttk.Combobox(b, state="readonly", width=28, style=ensure_hud_combo_style(b))
        self.cmb_lang.pack(fill=tk.X, pady=(px(2), px(8)))

        tk.Label(b, text=_t("ЖАНР"), bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(anchor="w")
        self.cmb_tag = ttk.Combobox(b, state="readonly", width=28, style=ensure_hud_combo_style(b))
        self.cmb_tag.pack(fill=tk.X, pady=(px(2), px(8)))

        HudButton(b, _t("🔍 ИСКАТЬ"), self._do_search, color=CYAN, height=34).pack(fill=tk.X, pady=px(4))
        HudButton(b, _t("★ МОИ ВОЛНЫ"), self._show_favorites, color=AMBER, height=32).pack(fill=tk.X, pady=px(2))
        HudButton(b, _t("ТОП ЭФИРА"), self._boot_catalog, color=GREEN, height=32).pack(fill=tk.X, pady=px(2))
        if (theme.current().get("radio") or {}).get("tags"):   # волны скина (у «Звездолёта» нет)
            HudButton(b, _t("♫ ВОЛНЫ СКИНА  F7"), self._show_skin_waves, color=AMBER,
                      height=32).pack(fill=tk.X, pady=px(2))

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
        sb = make_vscroll(wrap)
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
        """Поставить UI-колбэк в очередь. Нельзя звать Tk из фонового потока — зависает Windows."""
        try:
            self._ui_q.put(fn)
        except Exception:  # noqa: BLE001
            pass

    def _drain_ui(self) -> None:
        try:
            while True:
                fn = self._ui_q.get_nowait()
                try:
                    if self.winfo_exists():
                        fn()
                except tk.TclError:
                    pass
                except Exception:  # noqa: BLE001
                    pass
        except queue.Empty:
            pass
        try:
            self.after(50, self._drain_ui)
        except tk.TclError:
            pass

    def _on_list_cfg(self, e) -> None:
        self.list_canvas.itemconfigure(self._list_win, width=e.width)
        # ширина перешла порог двух колонок — переложить плашки (по успокоению окна)
        if self._stations and self._columns_for(e.width) != self._list_cols \
                and self._reflow_job is None:
            try:
                self._reflow_job = self.after(150, self._reflow)
            except tk.TclError:
                self._reflow_job = None

    def _reflow(self) -> None:
        self._reflow_job = None
        try:
            if self.winfo_exists() and self._stations:
                self._paint_list()
        except tk.TclError:
            pass

    def _on_wheel(self, e) -> None:
        if self.current != "air":
            return
        self.list_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _boot_catalog(self) -> None:
        self._skin_mode = False
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
            if getattr(self, "_skin_mode", False):   # пока грузился топ, пилот уже открыл волны скина
                return
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

    def _show_skin_waves(self) -> None:
        conf = theme.current().get("radio") or {}
        if not conf.get("tags"):
            return
        self._skin_mode = True
        self.lbl_status.configure(text=_t("Поиск…"), fg=AMBER)
        box: dict = {}

        def work():
            box["items"], box["err"] = browser.skin_stations(conf)

        def done():
            if not self.winfo_exists():
                return
            self._stations = box.get("items") or []
            err = box.get("err")
            if err:
                self.lbl_status.configure(text=_t("Нет связи с эфиром: {0}").format(err), fg=RED)
            else:
                self.lbl_status.configure(text=_t("Волны скина: {0}").format(len(self._stations)), fg=AMBER)
            self._paint_list()

        threading.Thread(target=lambda: (work(), self._safe_after(done)), daemon=True).start()

    def _show_favorites(self) -> None:
        self.eng.reload_store()
        self._stations = list(self.eng.data.get("favorites") or [])
        self.lbl_status.configure(text=_t("Мои волны пилота"), fg=AMBER)
        self._paint_list()

    # эфирные плашки: две колонки, пока каждая не уже ~430 px; иначе одна
    COL_MIN = 860

    def _list_width(self) -> int:
        """Ширина, под которую раскладываются плашки волн."""
        try:
            w = self.list_canvas.winfo_width()
            if w <= 1:                                   # ещё не разложено
                w = self.winfo_width()
                if w > 1:
                    w -= px(280)                         # слева панель фильтров
        except tk.TclError:
            return px(1200)
        return w if w > 1 else px(1200)

    @staticmethod
    def _columns_for(width: int) -> int:
        return 2 if width >= px(RadioScreen.COL_MIN) else 1

    def _paint_list(self) -> None:
        for w in self.list_inner.winfo_children():
            w.destroy()
        self._cards = {}
        self.lbl_count.configure(text=_t("{0} станций").format(len(self._stations)))
        try:
            if self._reflow_job is not None:
                self.after_cancel(self._reflow_job)
        except tk.TclError:
            pass
        self._reflow_job = None
        width = self._list_width()
        cols = self._columns_for(width)
        self._list_cols = cols
        try:
            self.list_canvas.itemconfigure(self._list_win, width=width)
        except tk.TclError:
            pass
        for c in range(2):
            self.list_inner.grid_columnconfigure(
                c, weight=1 if c < cols else 0, uniform="waves" if c < cols else "")
        if not self._stations:
            tk.Label(self.list_inner, text=_t("Станции не найдены"), bg=BG, fg=MUTED,
                     font=theme.font(11)).grid(row=0, column=0, columnspan=cols, pady=px(30))
            return
        fav_uuids = {f.get("uuid") for f in (self.eng.data.get("favorites") or [])}
        playing = (self.eng.station or {}).get("uuid")
        for i, st in enumerate(self._stations[:120]):
            card = self._make_card(st, fav_uuids, playing)
            card.grid(row=i // cols, column=i % cols, sticky="ew", padx=px(3), pady=px(3))

    def _make_card(self, st: dict, fav_uuids: set, playing_uuid: str | None) -> tk.Frame:
        """Плашка волны: антенна, имя целиком, композиция (или жанр/страна), ▶ и ☆."""
        uuid = st.get("uuid")
        live = bool(uuid and uuid == playing_uuid)
        bg = blend(PANEL, CYAN, 0.10 if live else 0.06)
        card = tk.Frame(self.list_inner, bg=bg, highlightthickness=1,
                        highlightbackground=CYAN if live else blend(PANEL, CYAN, 0.25))
        logo = tk.Canvas(card, width=px(44), height=px(44), bg=blend(PANEL, CYAN, 0.12),
                         highlightthickness=0)
        logo.pack(side=tk.LEFT, padx=px(8), pady=px(6))
        self._draw_antenna(logo)
        # сначала кнопки справа, потом текст: имя забирает всю оставшуюся ширину
        HudButton(card, "★" if uuid in fav_uuids else "☆", lambda s=st: self._toggle_fav(s),
                  height=30, font_size=12, width=40, color=AMBER).pack(
                      side=tk.RIGHT, padx=(px(2), px(8)))
        HudButton(card, _t("▶"), lambda s=st: self._play(s), height=30, font_size=11,
                  width=44, color=GREEN).pack(side=tk.RIGHT, padx=px(2))
        info = tk.Frame(card, bg=bg)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(4), pady=px(6))
        name_font = theme.font(11, True)
        sub_font = theme.font(9)
        # width=1: длинное имя не раздвигает плашку; хвост режем «…» по факту ширины
        name = tk.Label(info, text="", bg=bg, fg=TEXT, width=1, font=name_font, anchor="w")
        name.pack(fill=tk.X)
        sub = tk.Label(info, text="", bg=bg, fg=CYAN if live else MUTED, width=1,
                       font=sub_font, anchor="w")
        sub.pack(fill=tk.X)
        self._set_label(name, str(st.get("name") or "—"), name_font)
        self._set_label(sub, self._sub_text(st), sub_font)
        self._cards[uuid or f"#{id(st)}"] = {
            "st": st, "card": card, "sub": sub, "sub_font": sub_font}
        return card

    def _sub_text(self, st: dict) -> str:
        """Вторая строка плашки: у играющей волны — композиция, у прочих — страна/жанр."""
        uuid = st.get("uuid")
        track = (self.eng.track or "").strip()
        if uuid and uuid == (self.eng.station or {}).get("uuid") and track:
            return f"♪ {track}"
        meta = " · ".join(x for x in (
            st.get("country") or st.get("countrycode"),
            st.get("tags") or "",
            f"{st['bitrate']} kbps" if st.get("bitrate") else "",
        ) if x)
        return meta or "—"

    def _sync_cards(self) -> None:
        """Обновление без пересборки: подсветка эфира и название композиции."""
        if not self._cards:
            return
        playing = (self.eng.station or {}).get("uuid")
        for uuid, c in list(self._cards.items()):
            try:
                if not c["card"].winfo_exists():
                    continue
                live = bool(uuid and uuid == playing)
                border = CYAN if live else blend(PANEL, CYAN, 0.25)
                if c["card"].cget("highlightbackground") != border:
                    c["card"].configure(highlightbackground=border)
                c["sub"].configure(fg=CYAN if live else MUTED)
                want = self._sub_text(c["st"])
                if getattr(c["sub"], "_full_text", "") != want:
                    self._set_label(c["sub"], want, c["sub_font"])
            except tk.TclError:
                continue

    def _set_label(self, lbl: tk.Label, text: str, font_spec=None) -> None:
        """Подпись с «…» по своей ширине: Tk режет текст без многоточия."""
        lbl._full_text = text
        lbl._fit_font = font_spec or lbl.cget("font")
        if not getattr(lbl, "_fit_bound", False):
            lbl._fit_bound = True
            lbl.bind("<Configure>", self._fit_label)
        self._fit_label(lbl)

    def _fit_label(self, e) -> None:
        lbl = getattr(e, "widget", e)          # зовём и напрямую, и из <Configure>
        full = getattr(lbl, "_full_text", "")
        w = lbl.winfo_width()
        txt = full
        if w > px(24):
            from stamina.hud import fit_text
            txt = fit_text(getattr(lbl, "_fit_font", lbl.cget("font")), full, w - px(4))
        if lbl.cget("text") != txt:
            lbl.configure(text=txt)

    def _set_rx_name(self, text: str) -> None:
        self._rx_full = text
        self._fit_rx_name()

    def _fit_rx_name(self) -> None:
        """Имя станции в приёмнике - одна строка 16pt: длинное режем «…» по ширине."""
        from stamina.hud import fit_text
        full = getattr(self, "_rx_full", "")
        w = self.rx_name.master.winfo_width()
        txt = fit_text(theme.font(16, True), full, w - px(4)) if w > 20 else full
        if self.rx_name.cget("text") != txt:
            self.rx_name.configure(text=txt)

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
                text=_t("Нужен mpv: winget install shinchiro.mpv / sudo apt install mpv"), fg=AMBER)
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
        self.rx_name = tk.Label(meta, text=_t("Нет станции"), bg=PANEL, fg=TEXT, width=1,
                                font=theme.font(16, True), anchor="w")
        self.rx_name.pack(fill=tk.X)
        self._rx_full = self.rx_name.cget("text")
        meta.bind("<Configure>", lambda _e: self._fit_rx_name(), add="+")
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
            self._set_rx_name(st.get("name", "—")[:60])
        else:
            self._set_rx_name(_t("Нет станции"))
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
