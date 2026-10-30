"""Главное окно — «пульт космического корабля»: верхняя панель, разделы, статус."""

from __future__ import annotations

from stamina.i18n import t as tr_

import time
import os
import tkinter as tk
from tkinter import messagebox

from pathlib import Path

from stamina import (APP_NAME, __version__, avatars, comm, comm_hook, english_hook, lounge_hook,
                     missions, nav, docs_hook, orion_hook, pilots, radio_hook, speedread_hook, theme)
from stamina.bridge import Bridge
from stamina import safe_mode
from stamina import ontop
from stamina.bridge_settings import BridgeSettingsScreen
from stamina.hud import HScrollStrip, HudButton
from stamina.screens import CargoScreen, HelpScreen, LogScreen, MissionsScreen, SettingsScreen
from stamina.session_storage import clear_session, load_session
from stamina.sounds import SoundBoard
from stamina.storage import Store
from stamina.text_processing import process_text
from stamina.theme import AMBER, BG, CYAN, CYAN_DIM, GREEN, LINE, MUTED, PANEL, TEXT, blend, px


class Cockpit(tk.Tk):
    SCREENS = [("bridge", tr_("МОСТИК")), ("missions", tr_("МИССИИ")), ("cargo", tr_("СВОЙ ТЕКСТ")),
               ("log", tr_("БОРТЖУРНАЛ")), ("settings", tr_("НАСТРОЙКИ"))]

    def __init__(self) -> None:
        super().__init__()
        theme.init(self)
        self.store = Store()
        st = self.store.settings
        theme.set_ui_scale(st.get("ui_scale", "M"))
        theme.load_theme(st.get("skin", "spaceship"), apply_ui=False, root=self)
        self.sound = SoundBoard(False if safe_mode.enabled() else bool(st["sound"]), int(st.get("volume", 3)))
        self.translator = None
        self.current: str | None = None
        self._prev_screen: str | None = None
        self._last_action = None      # для F5: функция перезапуска
        self.pilot = pilots.active()  # None — режим без экипажа (миграция не удалась)
        self._update_title()
        self._set_icon()
        self.configure(bg=BG)
        self._apply_geometry()
        from stamina import monitors as _mon
        _mon.follow_toplevels(self)   # диалоги едут за окном на другой монитор
        ontop.apply(self, bool(st.get(ontop.KEY, True)))   # «Поверх всех окон»
        self._english_cls = english_hook.load_class()  # вкладка «АНГЛИЙСКИЙ» (stamina/english)
        if self._english_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(english_hook.KEY, english_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._speed_cls = speedread_hook.load_class()  # вкладка «СКОРОЧТЕНИЕ» (stamina/speedread)
        if self._speed_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(speedread_hook.KEY, speedread_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._lounge_cls = lounge_hook.load_class()  # вкладка «ОТДЫХ» (комната отдыха)
        if self._lounge_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(lounge_hook.KEY, lounge_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._radio_cls = radio_hook.load_class()  # вкладка «РАДИОРУБКА»
        if self._radio_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(radio_hook.KEY, radio_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._comm_cls = comm_hook.load_class()  # вкладка «ЭФИР» — лента сообщений экипажа
        if self._comm_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(comm_hook.KEY, comm_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._docs_cls = docs_hook.load_class()  # вкладка «ДОКУМЕНТЫ» — тексты и снимки
        if self._docs_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(docs_hook.KEY, docs_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        self._orion_cls = orion_hook.load_class()  # вкладка «ОРИОН» — бортовой разум
        if self._orion_cls is not None:
            self.SCREENS = [s for s in self.SCREENS if s[0] != "settings"] + \
                [(orion_hook.KEY, orion_hook.TITLE), ("settings", tr_("НАСТРОЙКИ"))]
        # восемь зон в шапке (как в веб-версии); Миссии/Свой текст/Бортжурнал — подменю Мостика
        loaded = {s[0] for s in self.SCREENS}
        self.SCREENS = [(z, tr_(nav.ZONE_TITLES[z])) for z in nav.zones(loaded)]
        self._last_bridge = "bridge"
        self._fullscreen = False
        from stamina import alt_ui
        self._layout = alt_ui.layout_of(st)  # вид интерфейса: classic | alt (docs/ALT_UI.md)
        self._build()
        self._start_stall_watch()
        # Окно не должно быть уже содержимого: иначе шапка, вкладки и клавиатура обрезаны
        self.after(800, self._fit_to_content)
        self.bind("<Key>", self._on_key)
        self.bind("<KeyRelease>", self._on_key_up, add="+")   # только для удержания T в АНГЛИЙСКОМ
        for i, (name, _t) in enumerate(self.SCREENS, 1):
            self.bind(f"<Control-Key-{i}>", lambda _e, n=name: self.show_zone(n))
        # Home — Орион, Prior (PgUp) — слайды, Next (PgDn) — экран (как на вебе)
        def _all_chrome(e, want: tuple[str, ...]):
            if e.keysym not in want:
                return None
            try:
                if e.widget.winfo_toplevel() is not self:
                    return None
            except tk.TclError:
                return None
            return "break" if self._chrome_hotkey(e) else None
        self.bind_all("<KeyPress-Home>", lambda e: _all_chrome(e, ("Home",)))
        self.bind_all("<KeyPress-Prior>", lambda e: _all_chrome(e, ("Prior",)))
        self.bind_all("<KeyPress-Next>", lambda e: _all_chrome(e, ("Next",)))
        # подвкладки с клавиатуры: Ctrl+Tab / Ctrl+Shift+Tab и Alt+1…9
        self.bind("<Control-Tab>", lambda _e: self.cycle_subtab(1) or "break")
        for seq in ("<Control-Shift-Tab>", "<Control-ISO_Left_Tab>"):
            try:
                self.bind(seq, lambda _e: self.cycle_subtab(-1) or "break")
            except tk.TclError:
                pass
        # подменю Мостика одним нажатием из любой зоны: Ctrl+F1…F5
        for i, (leaf, _tt) in enumerate(nav.BRIDGE_LEAVES, 1):
            self.bind(f"<Control-F{i}>", lambda _e, k=leaf: self.show(k) or "break")
        for i in range(1, 10):
            self.bind(f"<Alt-Key-{i}>", lambda _e, n=i: self.goto_subtab(n - 1) or "break")
        self.bind("<Control-Shift-P>", lambda _e: self.switch_pilot())
        for seq in ontop.HOTKEYS:   # «Поверх всех окон» вкл/выкл
            self.bind(seq, lambda _e: self.toggle_topmost() or "break")
        self.bind("<F5>", lambda _e: self.restart_current())
        self.bind("<F9>", self._on_f9)
        self.bind("<F1>", lambda _e: self.open_help())
        self.bind("<Shift-F1>", lambda _e: self._guide_help())  # гид читает справку окна вслух
        self.bind("<Button-3>", self._mark_point, add="+")
        self.bind("<FocusOut>", self._on_focus_out)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._clock_tick()
        from stamina import keynav
        keynav.install(self, current_menu=lambda: self.nav_buttons.get(nav.zone_of(self.current) or ""), before_tab=self._tab_typing)
        from stamina.living_space import LivingSpace, DEFAULT_MODE
        self.living = LivingSpace(self, self.content, "off" if safe_mode.enabled() else self.store.settings.get("living_space", DEFAULT_MODE))
        from stamina.idle.overlay import IdleController
        self.idle = IdleController(self)  # слайдшоу простоя — только у скинов со slideshow
        from stamina.guide_idle import GuideController
        self.guide = GuideController(self)
        from stamina.zen import ZenController
        self.zen = ZenController(self)   # минималистичный набор: Ctrl+M / Esc
        self.after(200, self.zen.apply)  # бортовой гид: шутки/факты и голосовая справка (офлайн)
        self.after(60, self._bootstrap)
        self.after(100, self._tick)
        # Кабина создаётся уже после окна входа: Windows не отдаёт ей клавиатуру
        # сама, и «клавиши не работают». Забираем фокус дважды — сразу и чуть позже.
        self.after(120, self._take_focus)
        self.after(900, self._take_focus)

    def _take_focus(self) -> None:
        """Сделать окно кабины активным и вернуть клавиатуру пульту."""
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _start_stall_watch(self) -> None:
        """Сторож главного потока: замерло дольше 1.5 с — пишем стек в журнал.

        Замирания зависят от пути входа: через экран логина событий раскладки
        в разы больше. Без журнала причину приходится угадывать, поэтому сторож
        всегда на борту и стоит копейки — один пульс раз в 100 мс.
        """
        import sys
        import threading
        import traceback

        pulse = [time.time()]
        stop = threading.Event()
        self._stall_stop = stop
        main_id = threading.main_thread().ident
        folder = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                              "Stamina")
        path = os.path.join(folder, "stall.log")

        def beat() -> None:
            if stop.is_set():
                return
            pulse[0] = time.time()
            try:
                self.after(100, beat)
            except tk.TclError:
                pass

        def watch() -> None:
            while not stop.is_set():
                time.sleep(0.1)
                gap = time.time() - pulse[0]
                if gap < 1.5:
                    continue
                frame = sys._current_frames().get(main_id)
                lines = ["--- %.2f c  %s" % (gap, time.strftime("%H:%M:%S"))]
                try:
                    for fs in traceback.extract_stack(frame)[-12:]:
                        lines.append("%s:%s %s" % (os.path.basename(fs.filename),
                                                   fs.lineno, (fs.line or "")[:100]))
                except Exception:  # noqa: BLE001
                    lines.append("стек не снялся")
                try:
                    os.makedirs(folder, exist_ok=True)
                    with open(path, "a", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                except OSError:
                    pass
                pulse[0] = time.time()

        self.after(200, beat)
        threading.Thread(target=watch, daemon=True, name="stall-watch").start()

    def _fit_to_content(self) -> None:
        """Расширить окно до ширины содержимого (в пределах экрана).

        В alt («Пульт-кабина») не нужно: экран прокручивается, ряды кнопок свёрнуты.

        Иначе при крупном интерфейсе шапка и клавиатура не влезают и выглядят
        «сломанными»: текст обрезан, кнопки наезжают.
        """
        if getattr(self, "_layout", "classic") == "alt":
            return
        try:
            if self.state() == "zoomed":
                return                      # развёрнутое окно уже во весь экран
            req_w = self.winfo_reqwidth()
            cur_w, cur_h = self.winfo_width(), self.winfo_height()
        except tk.TclError:
            return
        from stamina import monitors
        l, t, r, b = monitors.work_area(self)     # монитор, где окно стоит СЕЙЧАС
        sw, sh = r - l, b - t
        # окно шире экрана = обрезанные шапка и клавиатура, поэтому жёсткий предел по экрану
        need = min(req_w + px(8), sw - px(20))
        if need <= cur_w:
            return
        try:
            self.geometry(f"{need}x{min(cur_h, sh - px(60))}"
                          f"+{l + max(0, (sw - need) // 2)}+{max(t, self.winfo_y())}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def _apply_geometry(self) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        from stamina import alt_ui
        if alt_ui.layout_of(self.store.settings) == "alt":
            # «Пульт-кабина» прокручивается: окно можно сузить до 1024×768 и 1280×720 при любом DPI
            self.minsize(min(1000, sw - 40), min(600, sh - 80))
        else:
            self.minsize(min(px(1000), sw - 40), min(px(660), sh - 80))
        geo = self.store.settings.get("geometry") or ""
        if self.pilot is not None:
            geo = pilots.load_app().get("geometry") or geo  # окно — общее для экипажа
        if geo == "zoomed":
            self.after(10, lambda: self.state("zoomed"))
            geo = ""
        if geo:
            try:
                size, x, y = geo.replace("+", " +").split(" ")[0], *geo.split("+")[1:3]
                w, h = (int(v) for v in size.split("x"))
                # сохранённая раскладка годится, только если окно целиком влезает в экран
                from stamina import monitors
                on = monitors.on_some_monitor(int(x) + 100, int(y) + 50)   # второй монитор, x<0
                inside = on if on is not None else (0 <= int(x) < sw - 100 and 0 <= int(y) < sh - 100)
                if inside and px(600) <= w <= sw * 3 and px(400) <= h <= sh * 3:
                    self.geometry(geo)
                    return
            except (ValueError, TypeError):
                pass
        w = min(px(1500), sw - px(20))
        h = min(px(860), sh - px(60))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - px(20))}")

    def _build(self) -> None:
        # Рама: классическая шапка или «Пульт-кабина» (stamina/alt_ui.py). Экраны,
        # статус-строка и горячие клавиши — общие для обоих видов.
        from stamina import alt_ui
        if getattr(self, "_layout", "classic") == "alt":
            host = alt_ui.build_chrome(self)
            self._content_host = getattr(self, "_alt_body", None)
        else:
            self._build_classic_chrome()
            host = self
            self._content_host = None
        self._build_body(host)

    def _build_classic_chrome(self) -> None:
        """Классическая шапка — как до ALT UI, поведение не менять."""
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(10), pady=(px(8), 0))
        self._compact = len(self.SCREENS) >= 6  # много разделов — шапка поуже
        logo = tk.Canvas(top, bg=BG, highlightthickness=0, width=px(160 if self._compact else 220),
                         height=px(44))
        logo.pack(side=tk.LEFT)
        self._draw_logo(logo)
        # справа сначала — чтобы середина (навигация) могла сжиматься и скроллиться
        right = tk.Frame(top, bg=BG)
        right.pack(side=tk.RIGHT)
        self.clock = tk.Label(right, text="", bg=BG, fg=CYAN, font=theme.font(14, True, mono=True))
        self.clock.pack(side=tk.RIGHT, padx=(px(10), 0))
        self.btn_sound = HudButton(right, tr_("♪ ЗВУК ВЫКЛ"), self.toggle_sound, height=36, font_size=9,
                                   width=116 if len(self.SCREENS) < 6 else 38)
        self.btn_sound.pack(side=tk.RIGHT, padx=px(4))
        self.btn_screen = HudButton(right, tr_("⛶ ЭКРАН"), self.toggle_fullscreen, height=36, font_size=9,
                                    width=104, color=CYAN)
        self.btn_screen.pack(side=tk.RIGHT, padx=px(4))
        self.btn_slides = HudButton(right, tr_("СЛАЙДЫ"), lambda: self.idle.open(), height=36, font_size=9,
                                    width=90, color=CYAN)
        self.btn_slides.pack(side=tk.RIGHT, padx=px(4))
        # Орион на десктопе: кнопка открывает зону «ОРИОН» и включает микрофон, хоткей Home
        self.btn_orion = HudButton(right, tr_("ОРИОН"), self._call_orion, height=36, font_size=9,
                                   width=90, color=GREEN)
        self.btn_orion.pack(side=tk.RIGHT, padx=px(4))
        self.btn_help = HudButton(right, "?" if self._compact else "? F1", self.open_help, height=36,
                                  font_size=9, width=36 if self._compact else 60, color=AMBER)
        self.btn_help.pack(side=tk.RIGHT, padx=px(4))
        self.rank_label = tk.Canvas(right, bg=BG, highlightthickness=0, height=px(44),
                                    width=px(180 if self._compact else 220), cursor="hand2")
        self.rank_label.pack(side=tk.RIGHT, padx=px(6))
        self.rank_label.bind("<Button-1>", lambda _e: self.pilot_menu())
        # мини-приёмник — отдельной строкой под шапкой: в самой шапке ему не хватало места
        self._radio_mini = None
        self._mini_row = tk.Frame(self, bg=BG)
        self._mini_row.pack(fill=tk.X, padx=px(10))
        # подменю Мостика живёт в этой же строке: кнопки слева, приёмник справа
        self.subnav = tk.Frame(self._mini_row, bg=BG)
        self.subnav.pack(side=tk.LEFT)
        self.subnav_buttons: dict[str, HudButton] = {}
        for i, (key, title) in enumerate(nav.BRIDGE_LEAVES, 1):
            b = HudButton(self.subnav, f"{tr_(title)} · Ctrl+F{i}", lambda k=key: self.show(k), height=26, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            b.nav_menu = True
            self.subnav_buttons[key] = b
        try:
            from stamina.radio.minibark import RadioMiniBar
            self._radio_mini = RadioMiniBar(self._mini_row, self)
        except Exception:  # noqa: BLE001
            self._radio_mini = None
        # навигация зон — горизонтальный скролл колёсиком (кнопки не «пропадают» при крупном UI)
        self.nav_strip = HScrollStrip(top, height=44, bg=BG)
        self.nav_strip.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(4 if self._compact else 10))
        navf = self.nav_strip.inner
        self.nav_buttons: dict[str, HudButton] = {}
        for i, (name, title) in enumerate(self.SCREENS, 1):
            fs = 10 if len(self.SCREENS) <= 5 else 9 if len(self.SCREENS) <= 6 else 8
            # ширина по тексту (без ручного /S — иначе при крупном UI кнопки раздуваются и вылезают)
            b = HudButton(navf, f"{title}", lambda n=name: self.show_zone(n), height=36, font_size=fs)
            if name == "bridge":
                b.bind("<Button-3>", lambda _e: self.bridge_menu())
            b.pack(side=tk.LEFT, padx=px(2))
            b.nav_menu = True
            self.nav_buttons[name] = b
            self.nav_strip.wire(b)
        self.after_idle(self.nav_strip._sync)
        line = tk.Canvas(self, bg=BG, highlightthickness=0, height=px(6))
        line.pack(fill=tk.X, padx=px(10), pady=(px(4), 0))
        line.bind("<Configure>", lambda e: self._draw_line(line))

        # строка пути «МОСТИК › БОРТЖУРНАЛ» + подменю Мостика
        self.crumbs = tk.Frame(self, bg=BG)
        self.crumbs.pack(fill=tk.X, padx=px(14), pady=(px(2), 0))
        self.crumb_path = tk.Frame(self.crumbs, bg=BG)
        self.crumb_path.pack(side=tk.LEFT)

    def _build_body(self, host) -> None:
        """Область экранов и статус-строка (общая часть обоих видов)."""
        from stamina import alt_ui
        if self._layout == "alt":
            # alt: экраны лежат в окне с прокруткой — ничего не обрезается на 1024×768
            self.content = alt_ui.make_content(self, host)
        else:
            self.content = tk.Frame(host, bg=BG)
            self.content.pack(fill=tk.BOTH, expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        # Экран не должен «растягивать» окно под себя: все экраны лежат в одной ячейке,
        # и самый широкий из них (например, «Скорочтение», 2601 px) задавал ширину
        # всему окну. Из-за этого шапка и клавиатура уезжали за край, а Tk бесконечно
        # пересчитывал раскладку — окно уходило в 100 % CPU и не отвечало.
        self.content.grid_propagate(False)

        status = tk.Frame(self, bg=blend(BG, CYAN, 0.04))
        status.pack(fill=tk.X, side=tk.BOTTOM, before=self._content_host or self.content)  # статус-строка не выдавливается контентом
        self.status_dot = tk.Label(status, text="●", bg=status["bg"], fg=GREEN, font=theme.font(9))
        self.status_dot.pack(side=tk.LEFT, padx=(px(10), px(4)))
        self.status = tk.Label(status, text=tr_("ВСЕ СИСТЕМЫ В НОРМЕ"), bg=status["bg"], fg=MUTED,
                               font=theme.font(8, True))
        self.status.pack(side=tk.LEFT)
        self._status_hint = tk.Label(status, text=alt_ui.status_hint(len(self.SCREENS)) if self._layout == "alt" else tr_("F1 справка · F5 заново · Esc/Del пауза · Home Орион · PgUp слайды · PgDn экран · Ctrl+1…{0}").format(len(self.SCREENS)),
                 bg=status["bg"], fg=MUTED, font=theme.font(8))
        self._status_hint.pack(side=tk.RIGHT, padx=px(10))

        self.screens = {
            "bridge": Bridge(self.content, self),
            "missions": MissionsScreen(self.content, self),
            "cargo": CargoScreen(self.content, self),
            "log": LogScreen(self.content, self),
            "settings": SettingsScreen(self.content, self),
            "bridge_settings": BridgeSettingsScreen(self.content, self),
            "help": HelpScreen(self.content, self),
            "honor": self._make_honor(),
        }
        # Тяжёлые отсеки (книги, переписка, тексты «Английского») собираем после
        # первого кадра: их построение — это сотни миллисекунд процессорного времени,
        # и держать перед ними мёртвое окно нельзя. Отсек собирается по требованию
        # (show) или в фоне по одному между кадрами.
        self._factories: dict[str, object] = {}
        self._lazy(english_hook, self._english_cls)
        self._lazy(speedread_hook, self._speed_cls)
        self._lazy(lounge_hook, self._lounge_cls)
        self._lazy(radio_hook, self._radio_cls)
        self._lazy(comm_hook, self._comm_cls)
        self._lazy(docs_hook, self._docs_cls)
        self._lazy(orion_hook, self._orion_cls)
        for scr in self.screens.values():
            scr.grid(row=0, column=0, sticky="nsew")
        # Сразу оставляем в раскладке один экран: невидимые Tk всё равно перерисовывает,
        # а внутри них большие тексты — окно уходило в 100 % CPU (см. _only_screen).
        self._only_screen(self.current or "bridge")
        self.after(120, self._build_pending)
        self.update_rank()
        self._update_sound_button()
        self.update_comm_badge()

    def _set_icon(self) -> None:
        """Иконка окна и панели задач: звезда в шестиграннике (stamina/assets)."""
        assets = Path(__file__).resolve().parent / "assets"
        try:
            self._icon_img = tk.PhotoImage(file=str(assets / "star_typing_64.png"))
            self.iconphoto(True, self._icon_img)
        except tk.TclError:
            pass
        ico = assets / "star_typing.ico"
        if ico.exists() and self.tk.call("tk", "windowingsystem") == "win32":
            try:
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass

    def _draw_logo(self, c: tk.Canvas) -> None:
        cx, cy, r = px(22), px(22), px(17)
        import math
        pts = []
        for i in range(6):
            a = math.radians(60 * i + 30)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        c.create_polygon(pts, fill=blend(BG, CYAN, 0.15), outline=CYAN, width=2)
        star = []
        for i in range(10):
            a = math.radians(-90 + 36 * i)
            rr = r * (0.62 if i % 2 == 0 else 0.26)
            star += [cx + rr * math.cos(a), cy + px(1) + rr * math.sin(a)]
        c.create_polygon(star, fill=AMBER, outline="")
        compact = getattr(self, "_compact", False)
        c.create_text(px(48), px(15), text="STAR TYPING", anchor="w", fill=TEXT,
                      font=theme.font(14 if compact else 17, True))
        c.create_text(px(49), px(35), text=tr_("ПУЛЬТ ПИЛОТА") if compact else tr_("ПУЛЬТ ПИЛОТА · ТРЕНАЖЁР ПЕЧАТИ"),
                      anchor="w", fill=CYAN_DIM, font=theme.font(7, True))

    def _draw_line(self, c: tk.Canvas) -> None:
        c.delete("all")
        w = c.winfo_width()
        c.create_line(0, px(3), w, px(3), fill=LINE)
        c.create_line(0, px(3), px(260), px(3), fill=CYAN, width=2)
        c.create_line(w - px(160), px(3), w, px(3), fill=AMBER, width=2)
        for i in range(12):
            x = px(280) + i * px(10)
            c.create_line(x, px(1), x + px(5), px(1), fill=CYAN_DIM, width=2)

    # ------------------------------------------------------------------
    def _guide_help(self):
        guide = getattr(self, "guide", None)
        if guide is not None:
            guide.speak_help()
        return "break"

    def open_help(self) -> None:
        """F1 / «?»: модалка «как работает эта страница»; полная инструкция — из модалки."""
        from stamina.page_help import open_page_help
        open_page_help(self)

    # ------------------------------------------------------------------
    def _lazy(self, hook, cls) -> None:
        """Запомнить, как собрать отсек, вместо немедленной сборки."""
        if cls is None:
            return

        def build(hook=hook, cls=cls):
            return hook.create(cls, self.content, self)

        self._factories[hook.KEY] = build

    def _ensure_screen(self, name: str):
        """Вернуть экран, собрав его по требованию (отложенная сборка)."""
        scr = self.screens.get(name)
        if scr is not None:
            return scr
        build = self._factories.pop(name, None)
        if build is None:
            return None
        scr = build()
        if scr is None:
            self._drop_zone(name)
            return None
        self.screens[name] = scr
        scr.grid(row=0, column=0, sticky="nsew")
        if name != self.current:
            scr.grid_remove()
        return scr

    def _drop_zone(self, name: str) -> None:
        """Отсек не собрался (не установлен модуль) — убрать его из навигации."""
        self.SCREENS = [s for s in self.SCREENS if s[0] != name]
        btn = self.nav_buttons.pop(name, None)
        if btn is not None:
            try:
                btn.destroy()
            except tk.TclError:
                pass

    def _build_pending(self) -> None:
        """Собирать отложенные отсеки по одному между кадрами: окно остаётся живым."""
        if safe_mode.enabled():
            return  # безопасный режим: отсек собирается только когда в него зашли
        while self._factories:
            name = next(iter(self._factories))
            try:
                if self._ensure_screen(name) is not None:
                    break
            except Exception:  # noqa: BLE001
                self._drop_zone(name)
        if self._factories:
            self.after(80, self._build_pending)

    def _only_screen(self, name: str) -> None:
        """Оставить в раскладке только текущий экран.

        Все экраны лежали друг на друге в одной ячейке, и Tk перерисовывал их все —
        включая невидимые, а внутри них большие тексты (книга в «Скорочтении», лента
        Ориона). Из-за этого главный поток уходил в 100 % CPU, окно вставало и кнопки
        не нажимались. Замер: с убранными невидимыми экранами 1.25 с CPU за 5 с вместо 5.
        """
        for key, scr in (getattr(self, "screens", None) or {}).items():
            try:
                # Признак именно «лежит в раскладке» (grid), а не «виден на экране»:
                # на старте окно ещё не отрисовано, winfo_ismapped() = 0 у всех,
                # и лишние экраны оставались в раскладке — окно уходило в 100 % CPU.
                if key == name:
                    if scr.winfo_manager() != "grid":
                        scr.grid(row=0, column=0, sticky="nsew")
                elif scr.winfo_manager() == "grid":
                    scr.grid_remove()
            except tk.TclError:
                pass

    def show(self, name: str) -> None:
        if name == self.current:
            self._only_screen(name)      # экран уже открыт — просто убираем чужие
            return
        bridge: Bridge = self.screens["bridge"]
        if self.current == "bridge" and bridge.state in ("run", "ready") and name != "bridge":
            bridge.pause(tr_("Пауза — вы перешли в другой раздел"))
        if self.current == speedread_hook.KEY and name != self.current:
            try:
                self.screens[speedread_hook.KEY].on_leave()
            except Exception:  # noqa: BLE001
                pass
        if self.current == lounge_hook.KEY and name != self.current:
            try:
                self.screens[lounge_hook.KEY].on_leave()
            except Exception:  # noqa: BLE001
                pass
        if self.current == radio_hook.KEY and name != self.current:
            try:
                self.screens[radio_hook.KEY].on_leave()
            except Exception:  # noqa: BLE001
                pass
        if name == "honor" and self.current != "honor":
            try:
                from stamina.pilot_stats import summary
                self.store.save_stats()
                if self.pilot is not None:
                    pilots.update_pilot(self.pilot["id"], summary=summary(self.pilot["id"]))
            except Exception:  # noqa: BLE001
                pass
        # куда вернуться (Бортжурнал) и откуда пилот позвал Ориона — прежний раздел
        self._prev_screen = self.current
        self.current = name
        scr = self._ensure_screen(name)
        if scr is None:
            self.current = self._prev_screen
            return
        self._only_screen(name)          # невидимые экраны не рисуем (см. _only_screen)
        scr.tkraise()
        if hasattr(scr, "refresh"):
            scr.refresh()
        if hasattr(self, "living"):
            self.after(30, lambda s_=scr: self.current_screen_is(s_) and self.living.attach(s_))
        zone = nav.zone_of(name)
        if zone == "bridge":
            self._last_bridge = name
        for n, b in self.nav_buttons.items():
            b.set_active(n == zone)
        self._update_crumbs()
        self.update_comm_badge()
        self.btn_help.set_active(False)
        if getattr(self, "zen", None) is not None:
            self.zen.apply()             # дзен-режим виден только на «Полёте»
        if name == "cargo":
            scr.text.focus_set()
        elif name == comm_hook.KEY and hasattr(scr, "focus_input"):
            scr.focus_input()
        elif name == docs_hook.KEY and hasattr(scr, "focus_input"):
            scr.focus_input()
        elif name == orion_hook.KEY and hasattr(scr, "focus_input"):
            scr.focus_input()
            if hasattr(scr, "on_show"):
                scr.on_show()
        else:
            # Орион — гид: при входе в любой отсек рассказывает что происходит
            orion_scr = self.screens.get(orion_hook.KEY)
            if orion_scr is not None and hasattr(orion_scr, "on_zone_enter"):
                zone = nav.zone_of(name)
                sub = ""
                scr_obj = self.screens.get(name)
                if scr_obj is not None and hasattr(scr_obj, "current_tab"):
                    titles = dict(getattr(scr_obj, "TABS", ()))
                    sub = titles.get(scr_obj.current_tab, "")
                orion_scr.on_zone_enter(zone or name, sub)
            self.focus_set()

    def update_comm_badge(self) -> None:
        """Эфир: если есть непрочитанные сообщения, кнопка раздела подсвечена янтарным."""
        b = self.nav_buttons.get(comm_hook.KEY)
        if b is None:
            return
        try:
            n = 0 if self.current == comm_hook.KEY else comm.unread((self.pilot or {}).get("id", ""))
        except Exception:  # noqa: BLE001
            n = 0
        b.set_color(AMBER if n else CYAN)

    def show_zone(self, zone: str) -> None:
        """Кнопка зоны в шапке / Ctrl+1…9. Мостик из другой зоны — туда, где были в нём последний раз."""
        if zone == "bridge":
            in_bridge = nav.zone_of(self.current) == "bridge"
            self.show("bridge" if in_bridge else (self._last_bridge or "bridge"))
        else:
            self.show(zone)

    def subtabs(self):
        """Подвкладки текущего экрана: (ключи, текущий, показать) — для Ctrl+Tab и Alt+1…9.

        Экран со своими вкладками (НАСТРОЙКИ, НАСТРОЙКИ МОСТИКА) — его вкладки,
        иначе в зоне Мостика — подменю Мостика."""
        scr = self.screens.get(self.current)
        if scr is not None and hasattr(scr, "tab_keys") and hasattr(scr, "show_tab"):
            return scr.tab_keys(), scr.current_tab, scr.show_tab
        if nav.zone_of(self.current) == "bridge":
            return [k for k, _ in nav.BRIDGE_LEAVES], self.current, self.show
        return None

    def cycle_subtab(self, step: int) -> None:
        st = self.subtabs()
        if not st:
            return
        keys, cur, show = st
        i = keys.index(cur) if cur in keys else -step
        show(keys[(i + step) % len(keys)])

    def goto_subtab(self, idx: int) -> None:
        st = self.subtabs()
        if st and 0 <= idx < len(st[0]):
            st[2](st[0][idx])

    def bridge_menu(self) -> None:
        """Правый клик по «МОСТИК» — выпадающее подменю."""
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=blend(PANEL, AMBER, 0.2),
                    activeforeground=TEXT, font=theme.font(10, True))
        for key, title in nav.BRIDGE_LEAVES:
            m.add_command(label=tr_(title), command=lambda k=key: self.show(k))
        b = self.nav_buttons["bridge"]
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _update_crumbs(self) -> None:
        for w in self.crumb_path.winfo_children():
            w.destroy()
        segs = nav.path(self.current)
        for i, (label, target) in enumerate(segs):
            last = i == len(segs) - 1
            if i:
                tk.Label(self.crumb_path, text="›", bg=BG, fg=MUTED,
                         font=theme.font(10, True)).pack(side=tk.LEFT, padx=px(4))
            lb = tk.Label(self.crumb_path, text=label, bg=BG, fg=AMBER if last else CYAN,
                          font=theme.font(9, True, mono=False), cursor="arrow" if last else "hand2")
            lb.pack(side=tk.LEFT)
            if not last:
                lb.bind("<Button-1>", lambda _e, tg=target: self.show(tg))
                lb.bind("<Enter>", lambda _e, w=lb: w.configure(fg=TEXT))
                lb.bind("<Leave>", lambda _e, w=lb: w.configure(fg=CYAN))
        in_bridge = nav.zone_of(self.current) == "bridge"
        if in_bridge:
            if not self.subnav.winfo_ismapped():
                # кнопки — слева; приёмник, если уже показан, остаётся справа
                self.subnav.pack(side=tk.LEFT)
            for k, b in self.subnav_buttons.items():
                b.set_active(k == self.current)
        else:
            self.subnav.pack_forget()
        if getattr(self, "_layout", "classic") == "alt":
            from stamina import alt_ui
            alt_ui.on_screen(self)

    def toggle_fullscreen(self, on: bool | None = None) -> None:
        """ЭКРАН: полный экран для любого раздела (PgDn; выход — Esc/Del или «✕ ЭКРАН»)."""
        on = (not self._fullscreen) if on is None else on
        try:
            self.attributes("-fullscreen", on)
        except tk.TclError:
            return
        self._fullscreen = on
        self.btn_screen.set_text(tr_("✕ ЭКРАН") if on else tr_("⛶ ЭКРАН"))
        self.btn_screen.set_active(on)
        self.btn_screen.set_color(AMBER if on else CYAN)

    def _esc_fullscreen(self, _e=None) -> None:
        if self._fullscreen:
            self.toggle_fullscreen(False)

    def _make_honor(self):
        from stamina.pilot_screens import HonorBoard
        return HonorBoard(self.content, on_back=lambda: self.show(self._prev_screen or "bridge"),
                          active=self.pilot["id"] if self.pilot else None)

    def _zone_title(self, name: str | None) -> str:
        """Русское имя отсека по ключу — для пометок и подсказок."""
        for key, title in getattr(self, "SCREENS", []):
            if key == name:
                return title
        return name or ""

    @staticmethod
    def _widget_label(w) -> str:
        """Подпись виджета под курсором: «HudButton «ПЕЧАТЬ»», «Text», «Label «Ранг»»."""
        if w is None:
            return ""
        try:
            kind = w.winfo_class()
        except tk.TclError:
            return ""
        label = getattr(w, "text", "")
        if not isinstance(label, str) or not label:
            try:
                got = w.cget("text")
                label = got if isinstance(got, str) else ""
            except Exception:  # noqa: BLE001
                label = ""
        label = label.strip()
        if label:
            return f"{kind} «{label}»"
        return kind

    def _mark_point(self, e) -> None:
        """Правая кнопка мыши: запомнить место, о котором говорит пилот.

        Пометка уходит в «Орион» вместе с пожеланием — подчинённый агент получает
        не «где-то в интерфейсе», а отсек, подвкладку и точку в координатах окна.
        """
        try:
            from stamina import marks

            zone = self._zone_title(self.current)
            scr = self.screens.get(self.current or "")
            subtab = getattr(scr, "current_tab", "") if scr is not None else ""
            under = self.winfo_containing(e.x_root, e.y_root)
            mark = marks.add(
                e.x_root - self.winfo_rootx(),
                e.y_root - self.winfo_rooty(),
                zone,
                str(subtab or ""),
                self._widget_label(under),
                root=(self.winfo_width(), self.winfo_height()),
            )
            text = marks.describe(mark)
            copied = self._copy_mark(text, e.widget)
            self.set_status("⊕ " + text + (
                "  ·  скопировано" if copied else ""), GREEN)
            try:
                self.sound.click()
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass

    def _copy_mark(self, text: str, widget=None) -> bool:
        """Put the location string on the system clipboard.

        Text fields keep their own clipboard/context menu: a right click there must
        not overwrite what the pilot is about to paste.
        """
        if isinstance(widget, (tk.Entry, tk.Text)):
            return False
        from stamina import clipboard

        return clipboard.set_text(text, self)

    def set_status(self, text: str, color: str | None = None) -> None:
        self.status.configure(text=text, fg=color or theme.MUTED)

    def update_rank(self) -> None:
        xp = self.store.stats["xp"]
        rank, lo, hi = missions.rank_for(xp)
        from stamina import theme as _th
        rank = _th.skin_rank(rank)
        tail = f"{xp} / {hi} XP" if hi else f"{xp} XP"
        c = self.rank_label
        c.delete("all")
        w = int(c.cget("width"))
        x = w - px(2)
        from stamina.hud import fit_text
        if self.pilot is not None:
            avatars.draw(c, w - px(18), px(22), px(34), self.pilot, bg=BG)
            x = w - px(42)
            name = self.pilot["callsign"]
            if len(name) > 13:
                name = name[:12] + "…"
            room = max(px(20), x - px(2))
            f_name = theme.font(8, True)
            f_rank = theme.font(7, True)
            f_tail = theme.font(7, True)
            c.create_text(x, px(9), text=fit_text(f_name, f"{name.upper()} ▾", room), anchor="e",
                          fill=TEXT, font=f_name)
            c.create_text(x, px(24), text=fit_text(f_rank, f"★ {rank.upper()}", room), anchor="e",
                          fill=AMBER, font=f_rank)
            c.create_text(x, px(37), text=fit_text(f_tail, tail, room), anchor="e",
                          fill=MUTED, font=f_tail)
        else:
            room = max(px(20), x - px(2))
            c.create_text(x, px(13), text=fit_text(theme.font(10, True), f"★ {rank.upper()}", room),
                          anchor="e", fill=AMBER, font=theme.font(10, True))
            c.create_text(x, px(32), text=fit_text(theme.font(9, True), tail, room), anchor="e",
                          fill=AMBER, font=theme.font(9, True))

    # ------------------------------------------------------------------
    # Экипаж
    # ------------------------------------------------------------------
    def _update_title(self) -> None:
        who = tr_("пилот {0}").format(self.pilot['callsign']) if self.pilot else tr_("пульт пилота")
        self.title(f"{APP_NAME} — {who}  v{__version__}")

    def pilot_menu(self) -> None:
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=blend(PANEL, AMBER, 0.2),
                    activeforeground=TEXT, font=theme.font(10, True))
        if self.pilot is not None:
            m.add_command(label=tr_("⇄  СМЕНИТЬ ПИЛОТА   Ctrl+Shift+P"), command=self.switch_pilot)
            m.add_command(label=tr_("✎  ЛИЧНОЕ ДЕЛО"), command=self.edit_pilot)
            m.add_command(label=tr_("⇪  ЭКСПОРТ ПИЛОТА"), command=self.export_pilot)
            m.add_separator()
        m.add_command(label=tr_("★  ДОСКА ПОЧЁТА"), command=lambda: self.show("honor"))
        c = self.rank_label
        m.tk_popup(c.winfo_rootx(), c.winfo_rooty() + c.winfo_height())

    def edit_pilot(self) -> None:
        from stamina.pilot_screens import ProfileDialog
        if self.pilot is None:
            return
        ProfileDialog(self, self.pilot["id"]).run()
        self.pilot = pilots.get(self.pilot["id"]) or self.pilot
        self._update_title()
        self.update_rank()

    def export_pilot(self) -> None:
        from stamina.pilot_screens import export_pilot
        if self.pilot is not None:
            export_pilot(self, pilots.get(self.pilot["id"]) or self.pilot, __version__)

    def switch_pilot(self) -> None:
        """Сохранить всё и перезапустить программу с экраном «ВХОД В КАБИНУ» (SPEC §6.3)."""
        if self.pilot is None:
            return
        import subprocess
        import sys
        self._save_all()
        main = Path(__file__).resolve().parent.parent / "main.py"
        try:
            subprocess.Popen([sys.executable, str(main), "--select"], cwd=str(main.parent))
        except OSError as exc:
            messagebox.showerror(tr_("Смена пилота"), tr_("Не удалось перезапустить программу:\n{0}").format(exc), parent=self)
            return
        self.destroy()

    # ------------------------------------------------------------------
    # Запуск упражнений
    # ------------------------------------------------------------------
    def start_mission(self, m: dict) -> None:
        if not self.store.is_unlocked(m):
            self.set_status(tr_("МИССИЯ ЗАКРЫТА — сначала пройдите предыдущую"), AMBER)
            return
        text = missions.generate_mission_text(m)
        keys = " ".join(m["new"].upper()) if m["new"] and not m["new"].isdigit() else (
            tr_("цифры 0–9") if m["new"] else tr_("все буквы"))
        self.screens["bridge"].start(
            text, mode="mission", mission=m,
            title=tr_("МИССИЯ {0}-{1:02d} · {2}").format(m['lang'].upper(), m['num'], m['title'].upper()),
            subtitle=tr_("Сектор: {0} · новые клавиши: {1} · цель: {2} зн/мин при точности ≥ {3:.0f}%").format(m['sector'].lower(), keys, m['goal'], missions.PASS_ACCURACY))
        self._last_action = lambda: self.start_mission(m)
        self.show("bridge")

    def start_repair(self, lang: str | None = None) -> None:
        lang = lang or self.store.settings.get("lang", "en")
        if lang not in ("ru", "en"):      # украинский → кириллица, немецкий и др. → латиница
            lang = "ru" if lang == "uk" else "en"
        weak = self.store.weakest_keys(lang)
        if not weak:
            other = "ru" if lang == "en" else "en"
            if self.store.weakest_keys(other):
                lang, weak = other, self.store.weakest_keys(other)
        if not weak:
            messagebox.showinfo(tr_("Ремонт систем"), tr_("Пока недостаточно данных об ошибках.\nПройдите пару миссий — и бортовой компьютер найдёт слабые клавиши."),
                                parent=self)
            return
        chars = [ch for ch, _r in weak]
        text = missions.generate_repair_text(chars, lang)
        self.screens["bridge"].start(
            text, mode="repair", title=tr_("РЕМОНТ СИСТЕМ · СЛАБЫЕ КЛАВИШИ"),
            subtitle=tr_("Тренируем: ") + "  ".join(f"«{c}»" for c in chars) +
                     tr_(" — упражнение собрано из слов с этими буквами"))
        self._last_action = lambda: self.start_repair(lang)
        self.show("bridge")

    def cargo_process(self):
        """Функция подготовки своего текста по текущим опциям."""
        opts = dict(self.store.settings.get("cargo_opts") or {})
        lower, punct, spaces = (bool(opts.get(k, True)) for k in ("lower", "punct", "spaces"))
        translit, yo = bool(opts.get("translit", False)), bool(opts.get("yo", False))
        glue = bool(opts.get("glue", True))
        return lambda t: process_text(t, lower=lower, punct=punct, spaces=spaces, translit=translit,
                                      yo=yo, glue=glue)

    def start_cargo(self, adapted: str, original: str, switch: bool = True) -> None:
        self.store.save_cargo(adapted, original)
        spd = self.screens.get(speedread_hook.KEY)
        if spd is not None:  # общая библиотека: текст сразу доступен и для чтения
            try:
                spd.lib.upsert_from_cargo(adapted, original, self.store.settings.get("cargo_opts"))
            except Exception:  # noqa: BLE001
                speedread_hook._log(__import__("traceback").format_exc())
        clear_session()
        self._start_cargo_engine(adapted, original, None, switch=switch)

    def resume_cargo(self) -> None:
        saved = load_session()
        if saved is None:
            self.show("cargo")
            return
        adapted, original = self.store.load_cargo()
        if not original or self.cargo_process()(original) != saved.text:
            original = ""
        self._start_cargo_engine(saved.text, original, saved)

    def _start_cargo_engine(self, text: str, original: str, resume, switch: bool = True) -> None:
        preview = text[:40] + ("…" if len(text) > 40 else "")
        lower = bool((self.store.settings.get("cargo_opts") or {}).get("lower", True))
        case_sensitive = resume.case_sensitive if resume is not None else not lower
        self.screens["bridge"].start(
            text, mode="cargo", resume=resume, original=original,
            case_sensitive=case_sensitive, process=self.cargo_process(),
            title=tr_("СВОЙ ТЕКСТ · ДОСТАВКА ГРУЗА"),
            subtitle=tr_("«{0}» · прогресс сохраняется автоматически, можно закрыть программу").format(preview)
                     + (tr_(" · с заглавными буквами") if case_sensitive else ""))

        def again():
            if messagebox.askyesno(tr_("Заново"), tr_("Начать этот текст с самого начала?"), parent=self):
                clear_session()
                self._start_cargo_engine(text, original, None)
        self._last_action = again
        if switch:
            self.show("bridge")

    def restart_current(self) -> None:
        if self._last_action:
            self._last_action()
        else:
            self.show("missions")

    # ------------------------------------------------------------------
    def get_translator(self):
        if self.translator is None:
            from stamina.translator import Translator
            self.translator = Translator()
        return self.translator

    def toggle_topmost(self) -> None:
        st = self.store.settings
        st[ontop.KEY] = not st.get(ontop.KEY, True)
        self.apply_settings()
        try:
            self.screens["settings"].refresh()
        except (KeyError, tk.TclError):
            pass

    def _on_f9(self, _e=None):
        """F9: в ДОКУМЕНТАХ — диктовка, в остальных отсеках — звук."""
        scr = self.screens.get(docs_hook.KEY) if self.current == docs_hook.KEY else None
        if scr is not None and hasattr(scr, "dictate"):
            scr.dictate()
        else:
            self.toggle_sound()
        return "break"

    def toggle_sound(self) -> None:
        st = self.store.settings
        st["sound"] = not st["sound"]
        self.apply_settings()
        self.screens["settings"].refresh()

    def _update_sound_button(self) -> None:
        on = self.store.settings["sound"]
        if len(self.SCREENS) >= 6:  # шесть зон + ЭКРАН — компактная кнопка
            self.btn_sound.set_text("♪" if on else "♪̸")
        else:
            self.btn_sound.set_text(tr_("♪ ЗВУК ВКЛ") if on else tr_("♪ ЗВУК ВЫКЛ"))
        self.btn_sound.set_active(on)
        self.btn_sound.set_color(CYAN if on else MUTED)

    def _tab_typing(self, e) -> bool:
        """Tab во время полёта на мостике — клавиша печати, как раньше (выйти: Esc, потом Tab)."""
        if self.current == "bridge" and self.screens["bridge"].state == "run":
            self.screens["bridge"].on_key(e)
            return True
        return False

    def current_screen_is(self, scr) -> bool:
        return self.screens.get(self.current) is scr

    def apply_settings(self) -> None:
        st = self.store.settings
        theme.set_ui_scale(st.get("ui_scale", "M"))
        skin = st.get("skin", "spaceship")
        if theme.theme_id() != skin:
            theme.load_theme(skin, apply_ui=True, root=self)
            try:
                self.configure(bg=theme.BG)
            except tk.TclError:
                pass
        ontop.apply(self, bool(st.get(ontop.KEY, True)))
        self.sound.enabled = bool(st["sound"])
        self.sound.volume = int(st.get("volume", 3))
        self._update_sound_button()
        self.screens["bridge"].apply_settings()
        mode = st.get("living_space", "light")
        if hasattr(self, "living"):
            self.living.set_mode(mode)
        try:   # окно входа не знает настроек пилота — режим фона дублируется в app.json
            app = pilots.load_app()
            if app.get("living_space") != mode:
                app["living_space"] = mode
                pilots.save_app(app)
            if app.get("skin") != skin:
                app["skin"] = skin
                pilots.save_app(app)
        except Exception:  # noqa: BLE001
            pass
        self.store.save_settings()

    # ------------------------------------------------------------------
    def _bootstrap(self) -> None:
        self._bootstrap_main()
        start = os.environ.pop("STAMINA_START", "")
        if start == "settings:skins":  # после смены скина — обратно в Настройки → Скины
            self.show("settings")
            self.after(200, lambda: self.goto_subtab(2))
        elif start == "settings:more":
            self.show("settings")
            self.after(200, lambda: self.goto_subtab(1))  # ЕЩЁ
        if not safe_mode.enabled():
            self.after(2500, self._check_updates_bg)
        else:
            self.set_status(tr_("Безопасный режим: без звука, сети и живого космоса"), AMBER)

    def _check_updates_bg(self) -> None:
        """Фоновая проверка GitHub Releases — ненавязчивый диалог при новой версии."""
        import threading
        from stamina import __version__
        from stamina.i18n import t as _t
        from stamina.updater import check_error_message, fetch_latest

        def work() -> None:
            try:
                info = fetch_latest()
            except Exception as exc:  # noqa: BLE001
                check_error_message(exc)
                return
            if not info.is_newer:
                return

            def ask() -> None:
                from tkinter import messagebox
                if messagebox.askyesno(
                    _t("Обновления"),
                    _t("Доступна версия {0} (сейчас {1}).\nОткрыть НАСТРОЙКИ → ЕЩЁ?").format(
                        info.version, __version__
                    ),
                    parent=self,
                ):
                    self.show("settings")
                    self.after(150, lambda: self.goto_subtab(1))
                    scr = self.screens.get("settings")
                    if scr is not None and hasattr(scr, "_apply_upd_info"):
                        scr._apply_upd_info(info)

            self.after(0, ask)

        threading.Thread(target=work, daemon=True).start()

    def _original_for(self, text: str, cargo_original: str) -> str:
        """Оригинал для продолженного текста: из груза или из библиотеки (по совпадению)."""
        try:
            if cargo_original and self.cargo_process()(cargo_original) == text:
                return cargo_original
        except Exception:  # noqa: BLE001
            pass
        try:
            from stamina.library import Library
            from stamina.library import sha as _sha
            lib = Library()
            key = _sha(text)
            for tid in lib.ids():
                m = lib.meta(tid)
                if m and m.get("prepared", {}).get("sha256") == key:
                    return lib.original(tid)
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _bootstrap_main(self) -> None:
        saved = load_session()
        adapted, original = self.store.load_cargo()
        if not adapted and saved:
            adapted = saved.text
        self.screens["cargo"].load_initial(adapted, original)
        if saved is not None and saved.is_unfinished:
            # Продолжаем ровно там, где пилот остановился: набранный фрагмент книги
            # остаётся в работе на мостике. Позиция хранится в session.json и пишется
            # во время набора, поэтому прогресс не теряется ни при переходе в другой
            # раздел, ни при закрытии программы.
            self._start_cargo_engine(saved.text, self._original_for(saved.text, original), saved)
            done = len(saved.text[:saved.index].split())
            total = len(saved.text.split())
            self.set_status(tr_("ПРОДОЛЖАЕМ С МЕСТА ОСТАНОВКИ — слово {0:,} из {1:,}").format(done, total), CYAN)
        elif saved is not None:
            self.show("bridge")
            self.set_status(tr_("Сохранённый груз ждёт в разделе «СВОЙ ТЕКСТ»"), MUTED)
        elif not self.store.stats.get("runs"):
            # новичок: сразу на мостик с первой миссией (домашний ряд) — нажмите любую клавишу и летите
            self.start_mission(missions.missions_for("en")[0])
            self.set_status(tr_("ДОБРО ПОЖАЛОВАТЬ НА БОРТ — первая миссия готова: печатайте F и J. F1 — инструкция"), AMBER)
        else:
            self.show("missions")

    def _call_orion(self) -> None:
        """Кнопка Ориона: на мостике - голосовой вызов агента; иначе как раньше."""
        vc = getattr(self, "voice_call", None)
        if self.current == "bridge" or (vc is not None and vc.active()):
            self._voice_call_toggle()
            return
        from stamina.voice import tts
        if tts.speaking():
            tts.stop()
            self.btn_orion.set_text(tr_("ОРИОН"))
            self.btn_orion.set_color(GREEN)
            return
        self.show(orion_hook.KEY)
        scr = self.screens.get(orion_hook.KEY)
        if scr is not None and hasattr(scr, "listen"):
            scr.listen()

    def _voice_call_toggle(self) -> None:
        """Голосовой вызов с мостика (stamina/voice_call.py): старт или отмена."""
        from stamina.voice_call import VoiceCall
        if getattr(self, "voice_call", None) is None:
            self.voice_call = VoiceCall(self, self._voice_call_state)
        if not self.voice_call.active():
            br = self.screens.get("bridge")
            if br is not None and getattr(br, "state", "") == "run":
                br.toggle_pause()          # говорим - печать на паузе
        self.voice_call.toggle()

    def _voice_call_state(self, state: str, text: str = "") -> None:
        """Статус вызова на самой кнопке ОРИОН: места на 1024x600 не занимает."""
        labels = {"listening": ("● " + tr_("СЛУШАЮ"), AMBER), "thinking": ("… " + tr_("ДУМАЮ"), CYAN),
                  "speaking": ("♪ " + tr_("ОТВЕТ"), CYAN), "error": ("! " + tr_("ОРИОН"), AMBER)}
        label, color = labels.get(state, (tr_("ОРИОН"), GREEN))
        try:
            self.btn_orion.set_text(label)
            self.btn_orion.set_color(color)
            if state == "listening":
                self.set_status(tr_("Орион слушает: спросите голосом. Тишина - отправить, Esc или Home - отмена"), AMBER)
            elif state == "thinking":
                self.set_status(tr_("Вопрос Ориону: {0}").format(text[:80]), CYAN)
            elif state == "error":
                self.set_status(text[:120], AMBER)
        except tk.TclError:
            pass

    def show_orion_agents(self) -> None:
        """Открыть зону Ориона с вкладкой «АГЕНТЫ» (для заселения с экрана входа)."""
        self.show(orion_hook.KEY)
        scr = self.screens.get(orion_hook.KEY)
        if scr is not None and hasattr(scr, "show_tab"):
            scr.show_tab("agents")

    def _greet_orion(self) -> None:
        """Орион приветствует пилота при входе в зону."""
        scr = self.screens.get(orion_hook.KEY)
        if scr is not None and hasattr(scr, "on_show"):
            scr.on_show()

    def _chrome_hotkey(self, e: tk.Event) -> bool:
        """Home → Орион, Prior(PgUp) → слайды, Next(PgDn) → экран."""
        if e.state & 0x4 or e.state & 0x8 or e.state & 0x1:  # Ctrl / Alt / Shift
            return False
        from stamina.hotkeys import typing_in
        if typing_in(getattr(e, "widget", None)):
            return False                  # в поле ввода Home/PgUp/PgDn принадлежат тексту
        ks = e.keysym
        # Не перебиваем локальную навигацию по карточкам в английской зоне:
        # там PgUp/PgDn листают страницы, как и раньше.
        if self.current == "english" and ks in ("Prior", "Next"):
            return False
        if ks == "Home":
            self._call_orion()
            return True
        if ks == "Prior":
            try:
                self.idle.open()
            except Exception:  # noqa: BLE001
                pass
            return True
        if ks == "Next":
            self.toggle_fullscreen()
            return True
        return False

    def _on_key(self, e: tk.Event) -> str | None:
        zen = getattr(self, "zen", None)
        if zen is not None and zen.handle_key(e):
            return "break"               # Ctrl+M / Esc — дзен-режим (stamina/zen.py)
        vc = getattr(self, "voice_call", None)
        if e.keysym == "Escape" and vc is not None and vc.active():
            vc.cancel()                  # Esc - отмена голосового вызова, а не пауза
            return "break"
        if e.keysym == "Escape" and self.current == english_hook.KEY:
            scr = self.screens.get(english_hook.KEY)
            if scr is not None and getattr(scr, "focus_active", lambda: False)():
                scr.pages[scr.current].toggle_focus(False)   # Esc в фокус-режиме — только выход из него
                return "break"
        if e.keysym == "Escape" and self.current == docs_hook.KEY:
            scr = self.screens.get(docs_hook.KEY)
            if scr is not None and getattr(scr, "in_focus", lambda: False)():
                scr.toggle_focus(False)      # Документы: Esc — выход из фокус-режима
                return "break"
        if e.keysym in ("Escape", "Delete") and self._fullscreen:
            self.toggle_fullscreen(False)     # Esc/Del выходит из ЭКРАНА
            # На мостике в паузе — сразу продолжить полёт тем же Esc/Del
            if self.current == "bridge" and self.screens["bridge"].state == "pause":
                self.screens["bridge"].resume()
            return
        if e.keysym == "Escape" and self.current == "bridge_settings":
            from stamina.hud import HudButton
            if not isinstance(self.focus_get(), HudButton):
                self.show("bridge")               # Esc — назад на мостик
                return
        # Ctrl+Shift+P в любой раскладке (Windows: код клавиши P = 80)
        if (e.state & 0x4) and (e.state & 0x1) and (e.keycode == 80 or e.keysym in ("P", "p")):
            self.switch_pilot()
            return
        if self._chrome_hotkey(e):
            return "break"      # не даём тому же хоткею сработать ещё раз через bind_all
        if self.current == "bridge":
            from stamina.hud import HudButton
            if isinstance(self.focus_get(), HudButton):
                self.focus_set()         # начали печатать с кнопки в фокусе — фокус обратно мостику
            self.screens["bridge"].on_key(e)
            if zen is not None:
                zen.after_key()
        elif self.current == english_hook.KEY:
            self.screens[english_hook.KEY].on_key(e)
        elif self.current == speedread_hook.KEY:
            self.screens[speedread_hook.KEY].on_key(e)
        elif self.current == lounge_hook.KEY:
            self.screens[lounge_hook.KEY].on_key(e)
        elif self.current == radio_hook.KEY:
            self.screens[radio_hook.KEY].on_key(e)
        elif self.current == comm_hook.KEY:
            self.screens[comm_hook.KEY].on_key(e)
        elif self.current == docs_hook.KEY:
            self.screens[docs_hook.KEY].on_key(e)
        elif self.current == orion_hook.KEY:
            self.screens[orion_hook.KEY].on_key(e)
        elif self.current == "honor":
            self.screens["honor"].on_key(e)

    def _on_key_up(self, e: tk.Event) -> None:
        """Отпускание клавиши — только английской зоне (подсказка T держится, пока клавиша нажата)."""
        if self.current == english_hook.KEY:
            scr = self.screens.get(english_hook.KEY)
            if scr is not None and hasattr(scr, "on_key_up"):
                scr.on_key_up(e)

    def _on_focus_out(self, _e) -> None:
        def check():
            try:
                if self.focus_displayof() is None and self.current == "bridge":
                    self.screens["bridge"].pause(tr_("Окно потеряло фокус — полёт на паузе"))
            except (tk.TclError, KeyError):
                pass
        self.after(150, check)

    def _clock_tick(self) -> None:
        self.clock.configure(text=time.strftime("%H:%M"))
        self.status_dot.configure(fg=GREEN if int(time.time()) % 2 else blend(GREEN, BG, 0.6))
        self.after(1000, self._clock_tick)

    def _tick(self) -> None:
        smooth = False
        try:
            visible = self.current == "bridge" and self.state() != "iconic"
            smooth = self.screens["bridge"].tick(visible)
        except tk.TclError:
            return
        self.after(33 if smooth else 200, self._tick)

    def _on_close(self) -> None:
        self._stop_agents()
        self._save_all()
        self.destroy()

    def _stop_agents(self) -> None:
        """Закрыли корабль — гасим живых агентов: сирота доделает работу в пустоту."""
        try:
            from stamina import orion
            orion.stop_all()
        except Exception:
            pass

    def _save_all(self) -> None:
        try:
            self.screens["bridge"].leave_current()
        except Exception:
            pass
        for key in (english_hook.KEY, speedread_hook.KEY, lounge_hook.KEY, radio_hook.KEY):
            if key in self.screens:
                try:
                    self.screens[key].close()
                except Exception:
                    pass
        try:
            from stamina.radio.engine import get_engine
            get_engine().close()
        except Exception:
            pass
        st = self.store.settings
        st["geometry"] = "zoomed" if self.state() == "zoomed" else self.geometry()
        self.store.save_settings()
        self.store.save_stats()
        if self.translator is not None:
            self.translator.save()
        if self.pilot is not None:
            try:
                app = pilots.load_app()
                app["geometry"] = st["geometry"]
                pilots.save_app(app)
                from stamina.pilot_stats import summary
                pilots.update_pilot(self.pilot["id"], last_seen=pilots.now_iso(), summary=summary(self.pilot["id"]))
            except Exception:  # noqa: BLE001
                pass
