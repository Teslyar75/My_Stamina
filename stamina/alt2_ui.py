"""Альтернативный вид №2 — «Штурманский планшет» (ALT UI 2).

Отличие от «Пульт-кабины» (stamina/alt_ui.py) — не косметика, а раскладка:

* отсеки живут одной строкой сверху, а не доком слева;
* нет панорамы отсека и крупного дока: экран получает всё место;
* слева от листа — узкая штурманская линейка с точками отсеков (клик — переход);
* лист один, обои скина видны по полям вокруг него;
* «ПРИБОРЫ» (F8), шапка, путь и горячие клавиши — те же, что в кабине.

Цвета — только токены скина; строки — через tr_(); размеры — px(). Модуль
собирает раму и не трогает экраны: их создаёт кабина, как и для других видов.
"""

from __future__ import annotations

import tkinter as tk

from stamina import alt_ui, nav, theme
from stamina.hud import HScrollStrip, HudButton, px

BG = theme.BG


class ZoneDots(tk.Canvas):
    """Штурманская линейка: восемь точек-отсеков, текущий подсвечен.

    Рисуется только при смене размера или отсека. Клик по точке — переход.
    """

    WIDTH = 54

    def __init__(self, master, app, profile: str, bg: str) -> None:
        super().__init__(master, bg=bg, highlightthickness=0, width=px(self.WIDTH))
        self.living_skip = True
        self.app = app
        self.profile = profile
        self.zone = None
        self._size = None
        self.bind("<Configure>", self._on_size)
        self.bind("<Button-1>", self._click)

    def _on_size(self, e) -> None:
        size = (int(e.width), int(e.height))
        if size != self._size:
            self._size = size
            self._paint()

    def set_zone(self, zone: str | None) -> None:
        if zone != self.zone:
            self.zone = zone
            self._paint()

    def _paint(self) -> None:
        self.delete("all")
        if not self._size:
            return
        w, h = self._size
        zones = [z for z, _t in self.app.SCREENS]
        if not zones:
            return
        step = h / len(zones)
        x = w / 2
        self.create_line(x, step / 2, x, h - step / 2, fill=theme.LINE)
        for i, z in enumerate(zones):
            cy = step * (i + 0.5)
            active = z == self.zone
            r = px(9 if active else 6)
            col = theme.GREEN if active else theme.CYAN_DIM
            self.create_oval(x - r, cy - r, x + r, cy + r,
                             fill=blend_fill(active), outline=col, width=2 if active else 1)
            self.create_text(x, cy, text=alt_ui.glyph(self.profile, z), fill=theme.TEXT if active else theme.MUTED,
                             font=theme.font(7, True))
        self.create_text(x, h - px(7), text="⌖", fill=theme.FAINT, font=theme.font(7))

    def _click(self, e) -> None:
        zones = [z for z, _t in self.app.SCREENS]
        if not zones or not self._size:
            return
        i = int(e.y / (self._size[1] / len(zones)))
        if 0 <= i < len(zones):
            self.app.show_zone(zones[i])


def blend_fill(active: bool) -> str:
    return theme.blend(theme.BG, theme.GREEN if active else theme.CYAN, 0.22 if active else 0.06)


def _fit(app, e) -> None:
    """Узкое окно: короткая подпись «☰», без звания и часов — как в кабине."""
    w = int(e.width) / max(0.01, px(100) / 100)
    level = sum(1 for t in alt_ui.HEAD_LEVELS if w < t)
    if level == getattr(app, "_alt_head_level", 0):
        return
    app._alt_head_level = level
    try:
        app.btn_tools.set_text("☰ F8" if level >= 1 else "☰ ПРИБОРЫ · F8")
        if level >= 2:
            app.rank_label.pack_forget()
        elif not app.rank_label.winfo_manager():
            app.rank_label.pack(side=tk.RIGHT, padx=px(6), before=app.btn_tools)
        if level >= 3:
            app.clock.pack_forget()
            app.btn_help.pack_forget()
            app._alt_logo.configure(width=px(52))
            alt_ui._logo_text(app._alt_logo, False)
            alt_ui._title_font(app, 11)
        else:
            if not app.btn_help.winfo_manager():
                app.btn_help.pack(side=tk.RIGHT, padx=px(4), before=app.btn_orion)
            alt_ui._title_font(app, 16)
            if not app.clock.winfo_manager():
                app.clock.pack(side=tk.RIGHT, padx=(px(10), 0),
                               before=app.rank_label if app.rank_label.winfo_manager() else app.btn_tools)
            app._alt_logo.configure(width=px(200))
            alt_ui._logo_text(app._alt_logo, True)
        hint = getattr(app, "_status_hint", None)
        if hint is not None:
            if level >= 2:
                hint.pack_forget()
            elif not hint.winfo_manager():
                hint.pack(side=tk.RIGHT, padx=px(10))
    except tk.TclError:
        pass


def build_chrome(app) -> tk.Frame:
    """Собрать «Штурманский планшет» на ``app``; вернуть рамку для экранов."""
    prof = alt_ui.profile_id()
    pdata = alt_ui.PROFILES[prof]
    app._alt_profile = prof
    app._compact = True
    st = app.store.settings
    bg = theme.BG

    alt_ui.OrnamentBand(app, prof, "top", height=8).pack(fill=tk.X)
    head = tk.Frame(app, bg=bg)
    head.pack(fill=tk.X)
    logo = tk.Canvas(head, bg=bg, highlightthickness=0, width=px(200), height=px(44))
    logo.pack(side=tk.LEFT, padx=(px(10), 0), pady=px(4))
    app._draw_logo(logo)
    app._alt_logo = logo

    right = tk.Frame(head, bg=bg)
    right.pack(side=tk.RIGHT, padx=(0, px(10)))
    app.clock = tk.Label(right, text="", bg=bg, fg=theme.CYAN, font=theme.font(14, True, mono=True))
    app.clock.pack(side=tk.RIGHT, padx=(px(10), 0))
    app.rank_label = tk.Canvas(right, bg=bg, highlightthickness=0, height=px(44), width=px(190), cursor="hand2")
    app.rank_label.pack(side=tk.RIGHT, padx=px(6))
    app.rank_label.bind("<Button-1>", lambda _e: app.pilot_menu())
    app.btn_tools = HudButton(right, f"☰ {alt_ui.tr_(pdata['drawer'])} · F8", lambda: alt_ui.toggle_drawer(app),
                              height=36, font_size=9, color=theme.CYAN)
    app.btn_tools.pack(side=tk.RIGHT, padx=px(4))
    app.btn_slides = HudButton(right, alt_ui.tr_("СЛАЙДЫ"), lambda: app.idle.open(), height=36, font_size=9,
                               width=90, color=theme.CYAN)
    app.btn_slides.pack(side=tk.RIGHT, padx=px(4))
    app.btn_help = HudButton(right, "? F1", app.open_help, height=36, font_size=9, width=60, color=theme.AMBER)
    app.btn_help.pack(side=tk.RIGHT, padx=px(4))
    app.btn_orion = HudButton(right, alt_ui.tr_("ОРИОН"), app._call_orion, height=36, font_size=9, width=90,
                              color=theme.GREEN)
    app.btn_orion.pack(side=tk.RIGHT, padx=px(4))

    mid = tk.Frame(head, bg=bg)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(14))
    trow = tk.Frame(mid, bg=bg)
    trow.pack(side=tk.TOP, anchor="w", fill=tk.X)
    app._alt_crumbs = tk.Frame(trow, bg=bg)
    app._alt_crumbs.pack(side=tk.LEFT, anchor="w")
    app._alt_crumbs_key = None
    app._alt_title = tk.Label(trow, text="", bg=bg, fg=theme.TEXT, font=theme.font(16, True), anchor="w")
    app._alt_title.pack(side=tk.LEFT, anchor="w")
    app._alt_slot = tk.Frame(trow, bg=bg)
    app._alt_slot.pack(side=tk.LEFT, padx=(px(alt_ui.SLOT_GAP), 0))
    app._alt_slot_owner = None
    app._alt_slot_btn = alt_ui.OverviewButton(app._alt_slot, alt_ui.overview_label(), lambda: alt_ui._slot_popup(app),
                                             height=30, font_size=9, color=theme.AMBER)
    app._alt_slot_btn._alt_more = True
    app._alt_slot_btn._alt_kind = "section"
    app._alt_slot_btn.pack(side=tk.LEFT)
    srow = tk.Frame(mid, bg=bg)
    srow.pack(side=tk.TOP, anchor="w", fill=tk.X)
    sub = tk.Label(srow, text=alt_ui.tr_(pdata["subtitle"]), bg=bg, fg=theme.CYAN_DIM, font=theme.font(7, True),
                   anchor="w", justify="left", wraplength=px(300))
    sub.pack(side=tk.LEFT, anchor="w", fill=tk.X, expand=True, padx=(px(8), 0))
    app._alt_subtitle = sub
    srow.bind("<Configure>", lambda e: sub.configure(wraplength=max(px(80), int(e.width) - px(12))))
    app._alt_head_level = 0
    app.bind("<Configure>", lambda e: _fit(app, e) if e.widget is app else None, add="+")

    strip_bg = theme.blend(bg, theme.CYAN, 0.05)
    strip = HScrollStrip(app, height=38, bg=strip_bg)
    strip.pack(fill=tk.X, padx=px(6), pady=(0, px(3)))
    app.nav_strip = strip
    app.nav_buttons = {}
    for name, title in app.SCREENS:
        b = alt_ui.AltNavButton(strip.inner, title, lambda n=name: app.show_zone(n), profile=prof,
                                glyph_char=alt_ui.glyph(prof, name), height=32, font_size=9)
        if name == "bridge":
            b.bind("<Button-3>", lambda _e: app.bridge_menu())
        b.pack(side=tk.LEFT, padx=px(2), pady=px(3))
        b.nav_menu = True
        app.nav_buttons[name] = b
        strip.wire(b)
    app.after_idle(strip._sync)

    # Полка «ПРИБОРЫ»: та же, что в кабине, но кнопки ниже и тише.
    app._mini_row = tk.Frame(app, bg=theme.blend(bg, theme.CYAN, 0.05))
    app._alt_drawer_open = False
    drawer_bg = app._mini_row["bg"]
    tk.Label(app._mini_row, text=alt_ui.tr_(pdata["drawer"]) + ":", bg=drawer_bg, fg=theme.MUTED,
             font=theme.font(8, True)).pack(side=tk.LEFT, padx=(px(12), px(6)), pady=px(4))
    app.btn_sound = HudButton(app._mini_row, alt_ui.tr_("♪ ЗВУК ВЫКЛ"), app.toggle_sound, height=32, font_size=9,
                              width=116)
    app.btn_sound.pack(side=tk.LEFT, padx=px(3), pady=px(4))
    app.btn_screen = HudButton(app._mini_row, alt_ui.tr_("⛶ ЭКРАН"), app.toggle_fullscreen, height=32, font_size=9,
                               width=104, color=theme.CYAN)
    app.btn_screen.pack(side=tk.LEFT, padx=px(3))
    HudButton(app._mini_row, alt_ui.tr_("? СПРАВКА"), app.open_help, height=32, font_size=9, width=104,
              color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    HudButton(app._mini_row, alt_ui.tr_("★ ПИЛОТ"), lambda: app.pilot_menu(), height=32, font_size=9, width=104,
              color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    tk.Label(app._mini_row, text=alt_ui.tr_("F9 звук · PgDn экран"), bg=drawer_bg, fg=theme.MUTED,
             font=theme.font(8)).pack(side=tk.LEFT, padx=px(8))
    app._radio_mini = None
    try:
        from stamina.radio.minibark import RadioMiniBar
        app._radio_mini = RadioMiniBar(app._mini_row, app)
    except Exception:  # noqa: BLE001
        app._radio_mini = None
    app._alt_band = alt_ui.OrnamentBand(app, prof, "bottom", height=8)
    app._alt_band.pack(fill=tk.X)

    body = tk.Frame(app, bg=bg)
    body.pack(fill=tk.BOTH, expand=True)
    app._alt_body = body
    app._alt_wall = alt_ui.Wallpaper(body, prof, float(st.get("alt_wallpaper_dim", alt_ui.WALL_DIM)),
                                     alt_ui.wall_interval(st))
    _mw, _mh = alt_ui.monitors.area_size(app)
    small = _mw <= 1366 or _mh <= 800
    gap = px(8 if small else 18)
    rail_bg = theme.blend(bg, theme.PANEL, 0.35)

    dots = ZoneDots(body, app, prof, rail_bg)
    dots.pack(side=tk.LEFT, fill=tk.Y, padx=(gap, px(4)), pady=gap)
    app._alt2_dots = dots

    win = alt_ui.wrap(body, prof, bg=bg, edge=12)
    win.pack(fill=tk.BOTH, expand=True, padx=(0, gap), pady=gap)
    app._alt_frames = [win]
    col = win.inner

    app.crumbs = tk.Frame(col, bg=bg)
    app.crumbs.pack(fill=tk.X, padx=px(14), pady=(px(4), 0))
    app.crumb_path = tk.Frame(app.crumbs, bg=bg)
    app.crumb_path.pack(side=tk.LEFT)
    tk.Frame(app.crumbs, bg=bg, width=px(16)).pack(side=tk.LEFT)
    app.subnav = tk.Frame(app.crumbs, bg=bg)
    app.subnav.pack(side=tk.LEFT)
    app.subnav_buttons = {}
    for i, (key, title) in enumerate(nav.BRIDGE_LEAVES, 1):
        b = HudButton(app.subnav, alt_ui.tr_(title), lambda k=key: app.show(k), height=26, font_size=8)
        b.pack(side=tk.LEFT, padx=px(2))
        b.nav_menu = True
        app.subnav_buttons[key] = b

    app._alt_banner = None
    app._alt_rail = None
    app._alt_gauge = None
    app._alt_rail_label = app._alt_rail_toggle = app._alt_rail_hint = None
    app.bind("<F8>", lambda _e: alt_ui.toggle_drawer(app) or "break")
    return col


def on_screen(app) -> None:
    """После смены экрана: линейка отсеков и общая шапка кабины."""
    dots = getattr(app, "_alt2_dots", None)
    if dots is not None:
        dots.set_zone(nav.zone_of(app.current))
    alt_ui.on_screen(app)
