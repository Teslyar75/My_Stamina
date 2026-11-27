from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import alt_ui, nav, theme
from stamina.hud import HudButton as HB
from stamina.i18n import t as tr_
from stamina.theme import BG, MUTED, blend, px

from .timeline import Timeline
from .slideshow import Slideshow
from .earth_downloader import EarthDownloader


TOP_H = 46
SIDE_W = 30
GAP = 4
HOME_ID = "xp_home"


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
    """Build experienced-pilot chrome. Returns the hidden work-area host.

    The home screen is only a full-window slideshow canvas. Ribbon dashes are
    drawn on that same canvas; the work window is a separate frame which stays
    hidden until the pilot chooses an item from a ribbon popup.
    """
    try:
        prof = alt_ui.profile_id(theme.theme_id())
    except Exception:  # noqa: BLE001
        prof = "starship"
    app._alt_profile = prof
    app._xp_profile = prof
    st = app.store.settings

    body = tk.Frame(app, bg=BG)
    body.pack(fill=tk.BOTH, expand=True)
    app._xp_body = body
    app._alt_body = body       # хост плавающей панели радио (как в alt_ui)

    canvas = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
    canvas.place(x=0, y=0, relwidth=1, relheight=1)
    app._xp_canvas = canvas

    def _raise_ribbons() -> None:
        if getattr(app, "_xp_work_open", False):
            surfaces = (getattr(app, "_xp_top_overlay", None),
                        getattr(app, "_xp_side_overlay", None))
        else:
            surfaces = (canvas,)
        for surface in surfaces:
            if surface is not None and surface.winfo_exists():
                surface.tag_raise("timeline")

    slides = Slideshow(canvas, interval_ms=25000, fade_ms=900, scrim_alpha=0.0,
                       on_frame=_raise_ribbons)
    app._xp_slideshow = slides
    slides.set_frames(_core_wallpapers())
    slides.start()

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
            slides.set_frames(_core_wallpapers() + cached)
    except Exception:
        pass
    try:
        app._xp_earth.start()
    except Exception:
        pass

    def _top_region():
        w = max(1, canvas.winfo_width())
        if getattr(app, "_xp_work_open", False):
            return (0, 0, w, px(TOP_H))
        return (0, 0, w, px(TOP_H))

    def _side_geometry():
        """Положение правой чёрточки в координатах основного холста."""
        # Компактная лента справа, под виджетом радио: центр ленты = центр окна.
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        sw = px(SIDE_W)
        side = getattr(app, "_xp_side", None)
        n = len(side.items()) if side is not None else 1
        gap = side._gap() if side is not None else px(34)
        rh = max(px(48), n * gap + px(28))
        top_h = px(TOP_H) + px(GAP)
        y = (h - rh) // 2
        if y < top_h:
            y = top_h
        if y + rh > h - px(GAP):
            rh = max(px(48), h - y - px(GAP))
        return (max(0, w - sw), y, sw, rh)

    def _side_region():
        x, y, sw, rh = _side_geometry()
        if getattr(app, "_xp_work_open", False):
            # Чёрточка живёт на своей накладке над рабочим окном: координаты
            # внутри накладки начинаются с нуля, а не с правого края окна.
            return (0, 0, sw, rh)
        return (x, y, sw, rh)

    # Чёрточки — item'ы на одном холсте со слайдшоу, без своих Canvas-подложек.
    app._xp_top = Timeline(app, orientation="horizontal", surface=canvas, region=_top_region,
                           tag="xp_top", height=px(TOP_H), command=_top_action_factory(app),
                           bg=blend(BG, theme.CYAN, 0.02))
    app._xp_side = Timeline(app, orientation="vertical", surface=canvas, region=_side_region,
                            tag="xp_side", dash_width=px(SIDE_W), width=px(SIDE_W),
                            command=_side_action_factory(app),
                            bg=blend(BG, theme.AMBER, 0.03))

    # Радио — тот же класс и то же место, что в альтернативном виде; сдвинуто
    # влево на ширину правой ленты, чтобы не закрывать штрихи.
    app._alt_radio = None
    try:
        from stamina.radio.altpanel import AltRadioPanel
        app._alt_radio = AltRadioPanel(app, body, prof, right_inset=px(SIDE_W) + px(4))
        body.bind("<Destroy>", lambda e, p=app._alt_radio: p.eng.unsubscribe(p._on_eng)
                  if e.widget is body else None, add="+")
    except Exception:  # noqa: BLE001
        app._alt_radio = None

    # Рабочее окно занимает весь холст (общий зенид), но не заходит под ленты:
    # чёрточки рисуются на двух узких накладках поверх окна.
    work = tk.Frame(body, bg=BG)
    app._xp_work = work
    app._xp_work_open = False
    app._xp_ribbon_surface = canvas
    work.place_forget()

    top_overlay = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
    side_overlay = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
    app._xp_top_overlay, app._xp_side_overlay = top_overlay, side_overlay
    top_overlay.place_forget()
    side_overlay.place_forget()

    def _place_work() -> None:
        work.place(x=0, y=0, relwidth=1, relheight=1)

    def _place_overlays() -> None:
        w = max(1, canvas.winfo_width())
        _tx, _ty, _tw, th = _top_region()
        sx, sy, sw, sh = _side_geometry()
        top_overlay.place(x=0, y=0, width=w, height=max(1, th))
        side_overlay.place(x=sx, y=sy, width=sw, height=sh)

    def _use_ribbon_surface(*surfaces) -> None:
        for ribbon, surface in zip((app._xp_top, app._xp_side), surfaces):
            if ribbon is not None:
                ribbon.set_surface(surface)
        app._xp_ribbon_surface = surfaces[0]

    def _on_zen(on: bool) -> None:
        """Единый хук зенида: рабочее окно и ленты меняют место одной парой."""
        if on:
            app._xp_work_open = True
            _place_work()
            _place_overlays()
            _use_ribbon_surface(top_overlay, side_overlay)
        else:
            app._xp_work_open = False
            _use_ribbon_surface(canvas, canvas)
            work.place_forget()
            top_overlay.place_forget()
            side_overlay.place_forget()
            # Возврат в предыдущее окно не должен оставлять чёрный полноэкранный вид.
            if getattr(app, "_fullscreen", False):
                app.toggle_fullscreen(False)
        _raise_ribbons()
        _lift_chrome(app)

    # zen_mode ищет хук на самом виджете: он сработает и для Ctrl+O, и для Esc Esc.
    work.after_zen_toggle = _on_zen

    inner = tk.Frame(work, bg=BG)
    # Верхняя и правая полосы заняты чёрточками — контент под них не заезжает.
    inner.pack(fill=tk.BOTH, expand=True,
               padx=(px(8), px(SIDE_W) + px(16)),
               pady=(px(TOP_H) + px(10), px(8)))
    app._alt_frames = []

    # Всё, что ждёт кабина от шапки, живёт внутри скрытого рабочего окна.
    tools = tk.Frame(work, bg=BG)

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
    app.crumb_path = tk.Frame(app.crumbs, bg=BG)
    app.crumb_path.pack(side=tk.LEFT)
    app.subnav = tk.Frame(app.crumbs, bg=BG)
    app.subnav.pack(side=tk.LEFT)
    app.subnav_buttons = {}

    app.clock = tk.Label(tools, text="", bg=BG, fg=theme.CYAN, font=theme.font(14, True, mono=True))
    app.rank_label = tk.Canvas(tools, bg=BG, highlightthickness=0, height=px(42), width=px(170),
                               cursor="hand2")
    app.rank_label.bind("<Button-1>", lambda _e: app.pilot_menu())
    app.btn_help = HB(tools, "? F1", app.open_help, height=34, font_size=9, width=60, color=theme.AMBER)
    app.btn_slides = HB(tools, tr_("СЛАЙДЫ"), lambda: app.idle.open(), height=34, font_size=9,
                        width=90, color=theme.CYAN)
    app.btn_orion = HB(tools, tr_("ОРИОН"), app._call_orion, height=34, font_size=9, width=90,
                       color=theme.GREEN)
    app.btn_orion._alt_nocompact = True

    app._mini_row = tk.Frame(work, bg=blend(BG, theme.CYAN, 0.05))
    app._alt_drawer_open = False
    tk.Label(app._mini_row, text=tr_("ПРИБОРЫ") + ":", bg=app._mini_row["bg"], fg=MUTED,
             font=theme.font(8, True)).pack(side=tk.LEFT, padx=(px(12), px(6)), pady=px(4))
    app.btn_sound = HB(app._mini_row, tr_("♪ ЗВУК ВЫКЛ"), app.toggle_sound, height=32, font_size=9, width=116)
    app.btn_sound.pack(side=tk.LEFT, padx=px(3), pady=px(4))
    app.btn_screen = HB(app._mini_row, tr_("⛶ ЭКРАН"), app.toggle_fullscreen, height=32,
                        font_size=9, width=104, color=theme.CYAN)
    app.btn_screen.pack(side=tk.LEFT, padx=px(3))
    HB(app._mini_row, tr_("★ ПИЛОТ"), lambda: app.pilot_menu(), height=32, font_size=9,
       width=104, color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    app._radio_mini = None  # в опытном виде — плавающая AltRadioPanel, не плашка F8

    # Видимая кнопка «на весь экран»: убирает полосу с названием программы.
    # Живёт на холсте, а не в скрытой полке F8, поэтому доступна и на старте.
    app._xp_screen_button = HB(body, tr_("⛶ ЭКРАН"), app.toggle_fullscreen,
                               height=32, font_size=9, width=104, color=theme.CYAN)
    app._xp_screen_button.place(x=px(12), rely=1, y=-px(12), anchor="sw")

    def _on_canvas_cfg(e=None):
        if e is not None and getattr(e, "widget", None) is not canvas:
            return
        try:
            if getattr(app, "_xp_work_open", False):
                _place_overlays()
            app._xp_top.redraw()
            app._xp_side.redraw()
            _raise_ribbons()
            _lift_chrome(app)
        except Exception:  # noqa: BLE001
            pass

    _rebuild_top(app)
    _rebuild_side(app, "bridge")
    canvas.bind("<Configure>", _on_canvas_cfg, add="+")
    app.bind("<F8>", lambda _e: toggle_drawer(app) or "break", add="+")
    return inner


def _top_action_factory(app):
    def action(iid, _item, from_popup=False):
        if iid == HOME_ID:
            close_work(app)
            return
        if not from_popup:
            return
        app.show_zone(iid)
        open_work(app)
    return action


def _side_action_factory(app):
    def action(iid, _item, from_popup=False):
        if not from_popup:
            return
        app.show(iid)
        open_work(app)
    return action


def _lift_chrome(app) -> None:
    """Порядок слоёв: фото → рабочее окно → чёрточки → радио."""
    work = getattr(app, "_xp_work", None)
    if work is not None and work.winfo_exists() and work.winfo_ismapped():
        work.lift()
    for attr in ("_xp_top_overlay", "_xp_side_overlay"):
        overlay = getattr(app, attr, None)
        if overlay is not None and overlay.winfo_exists() and overlay.winfo_ismapped():
            overlay.lift()
    screen_btn = getattr(app, "_xp_screen_button", None)
    if screen_btn is not None and screen_btn.winfo_exists() and screen_btn.winfo_ismapped():
        screen_btn.lift()
    radio = getattr(app, "_alt_radio", None)
    if radio is None:
        return
    shown = getattr(radio, "_shown", None)
    frame = getattr(radio, "frame", None)
    tab = getattr(radio, "tab", None)
    try:
        # zen_mode на входе прячет соседей окна через FocusMode — вернём радио.
        if shown and frame is not None and not frame.winfo_ismapped():
            radio._shown = None
            radio._place(shown)
        for widget in (frame, tab):
            if widget is not None and widget.winfo_exists() and widget.winfo_ismapped():
                widget.lift()
    except tk.TclError:
        pass


def open_work(app) -> None:
    """Открыть отсек в общем полноэкранном режиме (тот же, что Ctrl+O)."""
    from stamina import zen_mode

    work = getattr(app, "_xp_work", None)
    if work is None:
        return
    if not zen_mode.is_active(work):
        zen_mode.enter(work)         # хук work.after_zen_toggle раскладывает ленты
    else:
        _lift_chrome(app)
    try:
        app.focus_set()
    except tk.TclError:
        pass


def close_work(app) -> None:
    """Двойной Esc / «ДОМОЙ» — пустой вид: фото, чёрточки и радио."""
    from stamina import zen_mode

    work = getattr(app, "_xp_work", None)
    if work is None:
        return
    if zen_mode.is_active(work):
        zen_mode.exit_zen(work)      # хук сам убирает окно и возвращает ленты
    else:
        hook = getattr(work, "after_zen_toggle", None)
        if callable(hook):
            hook(False)
    try:
        app.focus_set()
    except tk.TclError:
        pass


def _bottom_activate(app, item_id: str) -> None:
    try:
        app.show(item_id)
    except Exception:
        try:
            app.show_zone(item_id)
        except Exception:
            return
    open_work(app)


def _rebuild_top(app) -> None:
    items = [{"id": HOME_ID, "label": "⌂ " + tr_("ДОМОЙ")}]
    for name, title in getattr(app, "SCREENS", []):
        children = []
        if name == "bridge":
            children = [{"id": k, "label": tr_(t)} for k, t in nav.BRIDGE_LEAVES]
        items.append({"id": name, "label": tr_(dict(getattr(app, "SCREENS", [])).get(name, name)),
                      "children": children})
    app._xp_top.set_items(items)
    for name, _ in getattr(app, "SCREENS", []):
        app.nav_buttons[name] = _NavProxy(app, name, role="nav")
    try:
        zone = nav.zone_of(getattr(app, "current", "bridge")) or "bridge"
        app._xp_top.set_active(zone)
    except Exception:
        pass


class _NavProxy:
    """Скрытая кнопка навигации с контрактом HudButton для старых вызовов."""

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
            button = alt_ui.AltNavButton(app, tr_(titles.get(name, name)), command,
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
            except Exception:  # noqa: BLE001
                pass


def _rebuild_side(app, zone: str, active: str | None = None) -> None:
    if zone == "bridge":
        children = [{"id": k, "label": tr_(t)} for k, t in nav.BRIDGE_LEAVES]
    else:
        children = [{"id": zone, "label": tr_(nav.ZONE_TITLES.get(zone, zone.upper()))}]
    app._xp_side.set_items(children)
    ids = {c["id"] for c in children}
    app._xp_side.set_active(active if active in ids else (children[0]["id"] if children else None))
    app.subnav_buttons = {c["id"]: _NavProxy(app, c["id"], role="subnav") for c in children}


def toggle_drawer(app, open_: bool | None = None) -> None:
    """F8 не должен открывать полку на пустом стартовом экране."""
    if not getattr(app, "_xp_work_open", False) and open_:
        return
    want = (not getattr(app, "_alt_drawer_open", False)) if open_ is None else open_
    row = getattr(app, "_mini_row", None)
    if row is None:
        return
    try:
        if want:
            row.pack(fill=tk.X)
        else:
            row.pack_forget()
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
    # Имя зоны и крошки в опытном виде не показываем никогда.
    try:
        app._alt_title.configure(text="")
    except Exception:
        pass


def status_hint(n: int) -> str:
    return tr_("F1 справка и все клавиши · F8 приборы · Home Орион · Ctrl+1…{0} отсеки").format(n)
