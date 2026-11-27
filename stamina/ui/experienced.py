from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import nav, theme
from stamina.alt_ui import AltNavButton
from stamina.hud import HudButton as HB
from stamina.i18n import t as tr_
from stamina.theme import BG, MUTED, blend, px

from .timeline import Timeline
from .slideshow import Slideshow
from .earth_downloader import EarthDownloader


def _core_wallpapers() -> list:
    base = Path(__file__).resolve().parents[1] / "assets" / "alt_wallpapers" / "starship"
    names = ["bridge.jpg", "bridge_2.jpg", "bridge_3.jpg", "bridge_4.jpg", "lounge.jpg", "lounge_2.jpg"]
    out = []
    for n in names:
        p = base / n
        if p.is_file():
            out.append(p)
    return out


def build_chrome(app) -> tk.Frame:
    """Build experienced-pilot chrome. Returns content host frame for app.content."""
    prof = "starship"
    app._alt_profile = prof
    app._xp_profile = prof
    st = app.store.settings
    head_bg = blend(BG, theme.CYAN, 0.03)

    # top timeline ribbon (zones)
    app._xp_top = Timeline(app, orientation="horizontal", command=lambda iid, _it: app.show_zone(iid),
                           bg=blend(BG, theme.CYAN, 0.02), height=px(40))
    app._xp_top.pack(fill=tk.X, padx=px(8), pady=(px(4), 0))

    head = tk.Frame(app, bg=head_bg)
    head.pack(fill=tk.X)
    logo = tk.Canvas(head, bg=head_bg, highlightthickness=0, width=px(180), height=px(42))
    logo.pack(side=tk.LEFT, padx=(px(10), 0), pady=px(2))
    try:
        app._draw_logo(logo)
    except Exception:
        pass
    app._alt_logo = logo

    right = tk.Frame(head, bg=head_bg)
    right.pack(side=tk.RIGHT, padx=(0, px(10)))
    app.clock = tk.Label(right, text="", bg=head_bg, fg=theme.CYAN, font=theme.font(14, True, mono=True))
    app.clock.pack(side=tk.RIGHT, padx=(px(10), 0))
    app.rank_label = tk.Canvas(right, bg=head_bg, highlightthickness=0, height=px(42), width=px(170), cursor="hand2")
    app.rank_label.pack(side=tk.RIGHT, padx=px(6))
    app.rank_label.bind("<Button-1>", lambda _e: app.pilot_menu())
    app.btn_help = HB(right, "? F1", app.open_help, height=34, font_size=9, width=60, color=theme.AMBER)
    app.btn_help.pack(side=tk.RIGHT, padx=px(4))
    app.btn_slides = HB(right, tr_("СЛАЙДЫ"), lambda: app.idle.open(), height=34, font_size=9, width=90, color=theme.CYAN)
    app.btn_slides.pack(side=tk.RIGHT, padx=px(4))
    app.btn_orion = HB(right, tr_("ОРИОН"), app._call_orion, height=34, font_size=9, width=90, color=theme.GREEN)
    app.btn_orion._alt_nocompact = True
    app.btn_orion.pack(side=tk.RIGHT, padx=px(4))

    mid = tk.Frame(head, bg=head_bg)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(12))
    trow = tk.Frame(mid, bg=head_bg)
    trow.pack(side=tk.TOP, anchor="w", fill=tk.X)
    app._alt_crumbs = tk.Frame(trow, bg=head_bg)
    app._alt_crumbs.pack(side=tk.LEFT, anchor="w")
    app._alt_crumbs_key = None
    app._alt_title = tk.Label(trow, text="", bg=head_bg, fg=theme.TEXT, font=theme.font(15, True), anchor="w")
    app._alt_title.pack(side=tk.LEFT, anchor="w")
    app._alt_slot = tk.Frame(trow, bg=head_bg)
    app._alt_slot.pack(side=tk.LEFT, padx=(px(8), 0))
    app._alt_slot_owner = None
    app._alt_slot_btn = HB(app._alt_slot, tr_("ОБЗОР"), lambda: None, height=28, font_size=8, color=theme.AMBER)
    app._alt_slot_btn.pack_forget()
    srow = tk.Frame(mid, bg=head_bg)
    srow.pack(side=tk.TOP, anchor="w", fill=tk.X)
    sub = tk.Label(srow, text=tr_("ПУЛЬТ ПИЛОТА"), bg=head_bg, fg=theme.CYAN_DIM, font=theme.font(7, True), anchor="w")
    sub.pack(side=tk.LEFT, anchor="w")
    app._alt_subtitle = sub

    # drawer row (same attrs cockpit expects)
    app._mini_row = tk.Frame(app, bg=blend(BG, theme.CYAN, 0.05))
    app._alt_drawer_open = False
    drawer_bg = app._mini_row["bg"]
    tk.Label(app._mini_row, text=tr_("ПРИБОРЫ") + ":", bg=drawer_bg, fg=MUTED, font=theme.font(8, True)).pack(
        side=tk.LEFT, padx=(px(12), px(6)), pady=px(4))
    app.btn_sound = HB(app._mini_row, tr_("♪ ЗВУК ВЫКЛ"), app.toggle_sound, height=32, font_size=9, width=116)
    app.btn_sound.pack(side=tk.LEFT, padx=px(3), pady=px(4))
    app.btn_screen = HB(app._mini_row, tr_("⛶ ЭКРАН"), app.toggle_fullscreen, height=32, font_size=9, width=104, color=theme.CYAN)
    app.btn_screen.pack(side=tk.LEFT, padx=px(3))
    HB(app._mini_row, tr_("★ ПИЛОТ"), lambda: app.pilot_menu(), height=32, font_size=9, width=104, color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    app._radio_mini = None
    try:
        from stamina.radio.minibark import RadioMiniBar
        app._radio_mini = RadioMiniBar(app._mini_row, app, draggable=False)
    except Exception:
        pass

    body = tk.Frame(app, bg=BG)
    body.pack(fill=tk.BOTH, expand=True)
    app._alt_body = body

    # Боковая лента всегда справа (вертикальная).
    app._xp_side = Timeline(body, orientation="vertical", command=lambda iid, _it: _bottom_activate(app, iid),
                            bg=blend(BG, theme.AMBER, 0.03), width=px(28))
    app._xp_side.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, px(6)), pady=px(6))

    # wallpaper canvas behind content
    wall_host = tk.Frame(body, bg=BG)
    wall_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(8), px(4)), pady=px(6))
    wall_canvas = tk.Canvas(wall_host, bg=BG, highlightthickness=0, bd=0)
    wall_canvas.place(x=0, y=0, relwidth=1, relheight=1)
    app._xp_wall_canvas = wall_canvas
    app._xp_slideshow = Slideshow(wall_canvas, interval_ms=25000, fade_ms=900)
    core = _core_wallpapers()
    app._xp_slideshow.set_frames(core)
    app._xp_slideshow.start()

    # earth downloader -> add frames as they arrive
    manifest = Path(__file__).resolve().parents[1] / "assets" / "backgrounds" / "earth" / "manifest.json"
    def _on_earth(path):
        try:
            app.after_idle(lambda p=path: app._xp_slideshow.add_frame(p))
        except Exception:
            pass
    app._xp_earth = EarthDownloader(manifest, on_ready=_on_earth)
    try:
        cached = app._xp_earth.cached_files()
        if cached:
            app._xp_slideshow.set_frames(core + cached)
    except Exception:
        pass
    try:
        app._xp_earth.start()
    except Exception:
        pass

    # Рабочая область поверх фото, с полями, чтобы подложка была видна вокруг панелей.
    scrim = tk.Frame(wall_host, bg="#0B0E14")
    scrim.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(12))
    inner = tk.Frame(scrim, bg=BG)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    app._alt_frames = [scrim]

    # nav/subnav compatibility attrs
    class _NavStripShim:
        def __init__(self, parent):
            self.inner = tk.Frame(parent, bg=BG)
        def wire(self, *_a, **_k):
            pass
        def _sync(self):
            pass
    app.nav_strip = _NavStripShim(inner)
    app.nav_buttons = {}
    app.crumbs = tk.Frame(inner, bg=BG)
    app.crumbs.pack(fill=tk.X, padx=px(10), pady=(px(4), 0))
    app.crumb_path = tk.Frame(app.crumbs, bg=BG)
    app.crumb_path.pack(side=tk.LEFT)
    app.subnav = tk.Frame(app.crumbs, bg=BG)
    app.subnav.pack(side=tk.LEFT)
    app.subnav_buttons = {}

    _rebuild_top(app)
    _rebuild_side(app, "bridge")
    app.bind("<F8>", lambda _e: toggle_drawer(app) or "break", add="+")
    return inner


def _bottom_activate(app, item_id: str) -> None:
    # item_id can be screen key
    try:
        app.show(item_id)
    except Exception:
        try:
            app.show_zone(item_id)
        except Exception:
            pass


def _rebuild_top(app) -> None:
    items = []
    for name, _title in getattr(app, "SCREENS", []):
        children = []
        if name == "bridge":
            children = [{"id": k, "label": tr_(t)} for k, t in nav.BRIDGE_LEAVES]
        items.append({"id": name, "label": tr_(dict(getattr(app, "SCREENS", [])).get(name, name)), "children": children})
    app._xp_top.set_items(items)
    # nav_buttons compatibility: реальная (скрытая) кнопка за прокси, как в ALT UI
    for name, _ in getattr(app, "SCREENS", []):
        app.nav_buttons[name] = _NavProxy(app, name, role="nav")
    try:
        zone = nav.zone_of(getattr(app, "current", "bridge")) or "bridge"
        app._xp_top.set_active(zone)
    except Exception:
        pass


class _NavProxy:
    """Настоящая скрытая кнопка навигации с проксированием всего контракта HudButton.

    Пульт (update_comm_badge, bridge_menu, keynav и т.д.) работает с nav_buttons как
    с HudButton/tk.Canvas: set_color, set_narrow, configure, bind, winfo_*. Прокси
    держит такую кнопку в тех же руках, но не пакет в видимую шапку: видна только
    чёрточка на ленте, которую отмечает set_active.
    """

    _OWN = frozenset(("_app", "_name", "_role", "_button"))

    def __init__(self, app, name: str, *, role: str = "nav"):
        object.__setattr__(self, "_app", app)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_role", role)
        cache = getattr(app, "_xp_proxy_buttons", None)
        if cache is None:
            cache = {}
            app._xp_proxy_buttons = cache
        key = (role, name)
        button = cache.get(key)
        if button is None:
            titles = dict(getattr(app, "SCREENS", [])) if role == "nav" else dict(nav.BRIDGE_LEAVES)
            command = (lambda: app.show_zone(name)) if role == "nav" else (lambda: app.show(name))
            button = AltNavButton(app, tr_(titles.get(name, name)), command,
                                  profile=getattr(app, "_xp_profile", "starship"),
                                  height=34 if role == "nav" else 26, font_size=9)
            try:
                button.place_forget()
            except tk.TclError:
                pass
            cache[key] = button
        object.__setattr__(self, "_button", button)

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_button"), item)

    def __setattr__(self, key, value):
        if key in _NavProxy._OWN:
            object.__setattr__(self, key, value)
        else:
            setattr(self._button, key, value)

    def set_active(self, on: bool) -> None:
        button = object.__getattribute__(self, "_button")
        button.set_active(bool(on))
        if not on:
            return
        app = object.__getattribute__(self, "_app")
        ribbon = app._xp_top if object.__getattribute__(self, "_role") == "nav" else getattr(app, "_xp_side", None)
        if ribbon is not None:
            try:
                ribbon.set_active(object.__getattribute__(self, "_name"))
            except Exception:  # noqa: BLE001 — лента не должна ронять смену отсека
                pass


def _rebuild_side(app, zone: str, active: str | None = None) -> None:
    children = []
    if zone == "bridge":
        children = [{"id": k, "label": tr_(t)} for k, t in nav.BRIDGE_LEAVES]
    else:
        # existing submenu buttons if any in subnav_buttons will be represented by screen itself
        children = [{"id": zone, "label": tr_(nav.ZONE_TITLES.get(zone, zone.upper()))}]
    app._xp_side.set_items(children)
    ids = {c["id"] for c in children}
    app._xp_side.set_active(active if active in ids else (children[0]["id"] if children else None))
    app.subnav_buttons = {c["id"]: _NavProxy(app, c["id"], role="subnav") for c in children}


def toggle_drawer(app, open_: bool | None = None) -> None:
    want = (not getattr(app, "_alt_drawer_open", False)) if open_ is None else open_
    try:
        if want:
            before = getattr(app, "_alt_body", None)
            if before is not None:
                app._mini_row.pack(fill=tk.X, before=before)
            else:
                app._mini_row.pack(fill=tk.X)
        else:
            app._mini_row.pack_forget()
        app._alt_drawer_open = want
    except Exception:
        pass


def on_screen(app) -> None:
    zone = nav.zone_of(getattr(app, "current", None)) or "bridge"
    try:
        app._xp_top.set_active(zone)
    except Exception:
        pass
    _rebuild_side(app, zone, getattr(app, "current", None))
    # sync title/crumbs
    try:
        segs = nav.path(app.current)
        title = segs[-1][0] if segs else ""
        app._alt_title.configure(text=title)
    except Exception:
        pass
    try:
        for w in app._alt_crumbs.winfo_children():
            w.destroy()
        segs = nav.path(app.current)
        for i, (label, target) in enumerate(segs[:-1]):
            b = tk.Label(app._alt_crumbs, text=label, bg=app._alt_crumbs.cget("bg"), fg=theme.AMBER,
                         font=theme.font(9, True), cursor="hand2")
            b.pack(side=tk.LEFT)
            b.bind("<Button-1>", lambda _e, t=target: app.show(t))
            tk.Label(app._alt_crumbs, text=" › ", bg=app._alt_crumbs.cget("bg"), fg=MUTED,
                     font=theme.font(9, True)).pack(side=tk.LEFT)
    except Exception:
        pass


def status_hint(n: int) -> str:
    return tr_("F1 справка и все клавиши · F8 приборы · Home Орион · Ctrl+1…{0} отсеки").format(n)
