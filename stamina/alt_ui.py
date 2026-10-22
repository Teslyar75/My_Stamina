"""Альтернативный вид интерфейса — «Пульт-кабина» (ALT UI).

Классический вид (шапка со всеми зонами и кнопками) не меняется и остаётся
по умолчанию. Альтернативный вид включается в «НАСТРОЙКИ → СКИНЫ → Вид
интерфейса» (ключ ``ui_layout`` = ``"alt"`` в settings.json пилота) и
перестраивает только РАМУ корабля:

* шапка — логотип, крупное имя текущего отсека, ОРИОН, «?», ПРИБОРЫ, звание, часы;
* слева — док отсеков (вертикальная панель зон, сворачивается до значков);
* «ПРИБОРЫ» (F8) — выдвижная полка: звук, экран, слайды, мини-приёмник;
* подменю Мостика — в строке пути, только когда пилот в Мостике;
* антураж — орнаментальные полосы и приборы, нарисованные кодом по профилю скина.

Раскладка отделена от темы: профиль (``starship`` / ``steampunk`` / ``generic``)
даёт значки, подписи и рисунок орнамента, а цвета берутся только токенами
текущего скина (``theme.*`` + ``blend``). Новый скин получает свой профиль
полем ``"alt_ui": {"profile": "..."}`` в ``stamina/themes/<id>.json``;
без него — ``generic``. Все атрибуты, которые кабина ждёт от шапки
(``btn_sound``, ``btn_screen``, ``btn_slides``, ``btn_orion``, ``btn_help``,
``rank_label``, ``clock``, ``nav_buttons``, ``nav_strip``, ``subnav``,
``subnav_buttons``, ``_mini_row``, ``crumbs``, ``crumb_path``), создаются и здесь —
поэтому ни одна функция и горячая клавиша не теряется.

Правила из docs/HANG_100_CPU_2026-10-20.md соблюдены: рисунки перерисовываются
только при реальной смене размера, без ``update_idletasks()`` и без анимаций.
"""

from __future__ import annotations

import math
import random
import tkinter as tk

from stamina import monitors
from pathlib import Path

from stamina import nav, theme
from stamina.hud import HudButton, fit_text
from stamina.i18n import t as tr_
from stamina.theme import blend, chamfer, px

LAYOUTS = ("classic", "alt")
DEFAULT_LAYOUT = "classic"

# Профили антуража. Подписи — ключи i18n (переводятся при сборке).
PROFILES: dict[str, dict] = {
    "starship": {
        "glyphs": {"bridge": "◈", "english": "Ⓐ", "speedread": "»", "lounge": "◐",
                   "radio": "≋", "comm": "✉", "orion": "✦", "settings": "⚙"},
        "subtitle": "БОРТОВОЙ КОМПЬЮТЕР · ОТСЕКИ КОРАБЛЯ",
        "rail": "ОТСЕКИ",
        "drawer": "ПРИБОРЫ",
        "gauge": "РАДАР",
    },
    "steampunk": {
        "glyphs": {"bridge": "⚙", "english": "Æ", "speedread": "§", "lounge": "☕",
                   "radio": "☊", "comm": "✉", "orion": "☉", "settings": "⚒"},
        "subtitle": "МАСТЕРСКАЯ ИЗОБРЕТАТЕЛЯ · СМОТРОВЫЕ СТЁКЛА",
        "rail": "РЫЧАГИ",
        "drawer": "МАНОМЕТРЫ",
        "gauge": "ДАВЛЕНИЕ",
    },
    "generic": {
        "glyphs": {"bridge": "▣", "english": "A", "speedread": "»", "lounge": "◐",
                   "radio": "≋", "comm": "✉", "orion": "✦", "settings": "⚙"},
        "subtitle": "ПУЛЬТ ПИЛОТА",
        "rail": "ОТСЕКИ",
        "drawer": "ПРИБОРЫ",
        "gauge": "",
    },
}

SKIN_PROFILE = {"spaceship": "starship", "steampunk": "steampunk"}

RAIL_WIDE, RAIL_NARROW = 178, 50


def layout_of(settings: dict | None) -> str:
    """Вид интерфейса из настроек; всё незнакомое — классический."""
    v = (settings or {}).get("ui_layout", DEFAULT_LAYOUT)
    return v if v in LAYOUTS else DEFAULT_LAYOUT


def profile_id(skin_id: str | None = None, data: dict | None = None) -> str:
    """Профиль антуража скина: поле alt_ui.profile в JSON скина, иначе по id, иначе generic."""
    if data is None and skin_id is None:
        try:
            data = theme.current()
        except Exception:  # noqa: BLE001
            data = {}
    p = ((data or {}).get("alt_ui") or {}).get("profile")
    if p in PROFILES:
        return p
    sid = skin_id or (data or {}).get("id") or theme.theme_id()
    return SKIN_PROFILE.get(sid, "generic")


def glyph(profile: str, zone: str) -> str:
    return PROFILES.get(profile, PROFILES["generic"])["glyphs"].get(zone, "•")


# ---------------------------------------------------------------------------
# Кнопка дока отсеков
# ---------------------------------------------------------------------------

class AltNavButton(HudButton):
    """Кнопка зоны в доке. Тот же контракт, что у HudButton; другой рисунок.

    starship — приборный отсек: тёмная плита со срезом, индикатор-светодиод слева;
    steampunk — латунная табличка с заклёпками и бумажным ярлыком;
    generic — обычная кнопка скина.
    """

    def __init__(self, master, text: str, command=None, *, profile: str = "generic",
                 glyph_char: str = "•", **kw) -> None:
        self.profile = profile
        self.glyph = glyph_char
        self.title = text
        self.narrow = False
        super().__init__(master, f"{glyph_char}  {text}", command, **kw)

    def set_narrow(self, narrow: bool) -> None:
        self.narrow = narrow
        self.set_text(self.glyph if narrow else f"{self.glyph}  {self.title}")

    def _draw(self) -> None:  # noqa: C901 — три рисунка в одном месте нагляднее
        if self.profile == "generic":
            return super()._draw()
        w, h = self.winfo_width(), self.winfo_height()
        state = (w, h, self._text, self._enabled, self._pressed, self._active,
                 self._hover, self._focus, self.color, self.profile)
        if state == getattr(self, "_last_draw", None) and self.find_all():
            return
        self.delete("all")
        if w < 4 or h < 4:
            self._last_draw = None
            return
        col = self.color
        lit = self._active or self._hover or self._pressed
        if self.profile == "starship":
            c = min(px(10), h // 3)
            fill = blend(theme.PANEL, col, 0.22 if self._active else 0.10 if self._hover else 0.0)
            self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill=fill,
                                outline=col if lit else theme.LINE, width=2 if self._active else 1)
            # светодиод отсека: зелёный — вы здесь, циан — в ожидании, тусклый — спит
            r = px(4)
            cx, cy = px(12), h / 2
            led = theme.GREEN if self._active else col if self._hover else blend(col, theme.BG, 0.6)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=led, outline="")
            if self._active:
                self.create_oval(cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2, outline=blend(led, theme.BG, 0.5))
                self.create_line(w - px(6), px(6), w - px(6), h - px(6), fill=col, width=3)
            fg = theme.TEXT if lit else blend(col, theme.TEXT, 0.45)
            x0 = px(24)
        else:  # steampunk
            brass = blend(theme.PANEL, theme.AMBER, 0.42 if self._active else 0.26 if self._hover else 0.16)
            self.create_rectangle(1, 1, w - 2, h - 2, fill=brass, outline=theme.LINE_HI if lit else theme.LINE,
                                  width=2)
            rr = max(2, px(2))
            for (x, y) in ((px(5), px(5)), (w - px(6), px(5)), (px(5), h - px(6)), (w - px(6), h - px(6))):
                self.create_oval(x - rr, y - rr, x + rr, y + rr, fill=theme.LINE_HI, outline=theme.BG)
            if not self.narrow and w > px(80):   # бумажный ярлык под надпись
                self.create_rectangle(px(28), px(6), w - px(12), h - px(6),
                                      fill=blend(brass, theme.TEXT, 0.10), outline=blend(brass, theme.BG, 0.4))
            # «рычаг»: вверх — отсек открыт
            lx = px(16)
            self.create_line(lx, h - px(8), lx + (0 if self._active else px(5)), px(8),
                             fill=theme.TEXT if self._active else theme.MUTED, width=3)
            self.create_oval(lx - px(3), h - px(11), lx + px(3), h - px(5), fill=theme.LINE_HI, outline="")
            fg = theme.TEXT
            x0 = px(30)
        if self.narrow:
            self.create_text(w / 2 + (px(4) if self.profile == "starship" else px(6)), h / 2,
                             text=self.glyph, fill=fg, font=self._font)
        else:
            self.create_text(x0 + px(4), h / 2, anchor="w",
                             text=fit_text(self._font, self._text, w - x0 - px(14)), fill=fg, font=self._font)
        if self._focus:
            k = min(px(8), h // 2)
            for (x, y, dx, dy) in ((2, 2, 1, 1), (w - 3, 2, -1, 1), (2, h - 3, 1, -1), (w - 3, h - 3, -1, -1)):
                self.create_line(x, y + dy * k, x, y, x + dx * k, y, fill=theme.AMBER, width=2)
        self._last_draw = state


# ---------------------------------------------------------------------------
# Орнамент и приборы (рисуются кодом — без чужих картинок)
# ---------------------------------------------------------------------------

class OrnamentBand(tk.Canvas):
    """Полоса антуража. Перерисовка — только при смене размера (без шторма событий)."""

    def __init__(self, master, profile: str, kind: str = "top", height: int = 12) -> None:
        super().__init__(master, bg=theme.BG, highlightthickness=0, height=px(height))
        self.living_skip = True
        self.profile = profile
        self.kind = kind
        self._size = None
        self.bind("<Configure>", self._on_size)

    def _on_size(self, e) -> None:
        size = (int(e.width), int(e.height))
        if size == self._size:
            return
        self._size = size
        self.redraw(*size)

    def redraw(self, w: int, h: int) -> None:
        self.delete("all")
        getattr(self, f"_draw_{self.profile}", self._draw_generic)(w, h)

    def _draw_generic(self, w: int, h: int) -> None:
        y = h // 2
        self.create_line(0, y, w, y, fill=theme.LINE)
        self.create_line(0, y, px(220), y, fill=theme.CYAN, width=2)
        self.create_line(w - px(140), y, w, y, fill=theme.AMBER, width=2)

    def _draw_starship(self, w: int, h: int) -> None:
        rnd = random.Random(7 if self.kind == "top" else 11)   # звёзды стоят на месте
        for _ in range(max(10, w // 14)):
            x, y = rnd.randrange(0, max(1, w)), rnd.randrange(0, max(1, h))
            b = rnd.random()
            col = theme.TEXT if b > 0.93 else theme.CYAN_DIM if b > 0.6 else theme.FAINT
            self.create_rectangle(x, y, x + 1, y + 1, fill=col, outline="")
        if self.kind == "top":
            # обшивка: сегменты корпуса со срезанными углами и бортовые огни
            seg = px(120)
            y0, y1 = h - px(5), h - 1
            for i, x in enumerate(range(px(6), w - px(6), seg)):
                self.create_polygon(chamfer(x, y0, min(x + seg - px(8), w - px(6)), y1, px(3)),
                                    fill=theme.PANEL, outline=theme.LINE)
                if i % 3 == 1:
                    self.create_rectangle(x + seg // 2, y0 + 1, x + seg // 2 + px(6), y1 - 1,
                                          fill=theme.AMBER if i % 2 else theme.GREEN, outline="")
        else:
            y = px(3)
            self.create_line(0, y, w, y, fill=theme.LINE)
            self.create_line(0, y, px(300), y, fill=theme.CYAN, width=2)
            for i in range(0, w, px(24)):   # шкала прицела
                self.create_line(i, y, i, y + (px(5) if (i // px(24)) % 5 == 0 else px(2)), fill=theme.CYAN_DIM)
            self.create_line(w - px(180), y, w, y, fill=theme.AMBER, width=2)

    def _draw_steampunk(self, w: int, h: int) -> None:
        brass = blend(theme.PANEL, theme.AMBER, 0.30)
        if self.kind == "top":
            self.create_rectangle(0, 0, w, h, fill=brass, outline="")
            self.create_line(0, 1, w, 1, fill=theme.LINE_HI)
            self.create_line(0, h - 1, w, h - 1, fill=theme.BG)
            r = max(2, px(2))
            for x in range(px(10), w, px(26)):   # ряд заклёпок
                self.create_oval(x - r, h / 2 - r, x + r, h / 2 + r, fill=theme.LINE_HI, outline=theme.BG)
        else:
            # паропровод с вентилями
            y = h / 2
            self.create_line(0, y, w, y, fill=theme.CYAN_DIM, width=max(3, px(5)))
            self.create_line(0, y - px(2), w, y - px(2), fill=theme.LINE_HI)
            for x in range(px(140), w, px(260)):
                rr = px(5)
                self.create_rectangle(x - px(3), y - rr - px(1), x + px(3), y + rr + px(1), fill=brass, outline=theme.BG)
                self.create_oval(x - rr, y - rr, x + rr, y + rr, outline=theme.RED, width=2)


def draw_gear(c: tk.Canvas, cx: float, cy: float, r: float, teeth: int, fill: str, outline: str,
              angle: float = 0.0) -> None:
    pts = []
    for i in range(teeth * 2):
        a = angle + math.pi * i / teeth
        rr = r if i % 2 == 0 else r * 0.78
        pts += [cx + rr * math.cos(a), cy + rr * math.sin(a)]
    c.create_polygon(pts, fill=fill, outline=outline)
    c.create_oval(cx - r * 0.28, cy - r * 0.28, cx + r * 0.28, cy + r * 0.28, fill=theme.BG, outline=outline)


class GaugeCanvas(tk.Canvas):
    """Прибор внизу дока: радар (Звездолёт) или манометр с шестернями (Стимпанк).

    Статичный рисунок — он про атмосферу, а не про данные; на CPU не влияет.
    """

    def __init__(self, master, profile: str, size: int = 150) -> None:
        super().__init__(master, bg=master["bg"], highlightthickness=0, width=px(size), height=px(size))
        self.living_skip = True
        self.profile = profile
        self._size = None
        self.bind("<Configure>", self._on_size)

    def _on_size(self, e) -> None:
        size = (int(e.width), int(e.height))
        if size != self._size:
            self._size = size
            self.delete("all")
            (self._radar if self.profile == "starship" else self._manometer)(*size)

    def _radar(self, w: int, h: int) -> None:
        s = min(w, h)
        cx, cy, r = w / 2, h / 2, s / 2 - px(6)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=blend(theme.BG, theme.CYAN, 0.05), outline=theme.CYAN_DIM)
        for k in (0.66, 0.33):
            self.create_oval(cx - r * k, cy - r * k, cx + r * k, cy + r * k, outline=theme.LINE)
        self.create_line(cx - r, cy, cx + r, cy, fill=theme.LINE)
        self.create_line(cx, cy - r, cx, cy + r, fill=theme.LINE)
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=20, extent=40, fill=blend(theme.BG, theme.CYAN, 0.25),
                        outline="")
        self.create_line(cx, cy, cx + r * math.cos(math.radians(-60)), cy + r * math.sin(math.radians(-60)),
                         fill=theme.CYAN, width=2)
        for (dx, dy, col) in ((0.4, -0.3, theme.AMBER), (-0.5, 0.2, theme.GREEN), (0.15, 0.55, theme.CYAN)):
            x, y = cx + r * dx, cy + r * dy
            self.create_oval(x - px(2), y - px(2), x + px(2), y + px(2), fill=col, outline="")

    def _manometer(self, w: int, h: int) -> None:
        s = min(w, h)
        brass = blend(theme.PANEL, theme.AMBER, 0.35)
        draw_gear(self, w * 0.78, h * 0.80, s * 0.20, 10, blend(theme.PANEL, theme.AMBER, 0.2), theme.LINE)
        draw_gear(self, w * 0.20, h * 0.84, s * 0.13, 8, blend(theme.PANEL, theme.AMBER, 0.15), theme.LINE, 0.3)
        cx, cy, r = w / 2, h * 0.42, s * 0.34
        self.create_oval(cx - r - px(4), cy - r - px(4), cx + r + px(4), cy + r + px(4), fill=brass, outline=theme.LINE_HI,
                         width=2)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=blend(theme.TEXT, theme.PANEL, 0.12), outline=theme.BG)
        for i in range(11):   # шкала 0…10 по дуге 240°
            a = math.radians(210 - 24 * i)
            r1 = r * (0.78 if i % 5 else 0.70)
            self.create_line(cx + r1 * math.cos(a), cy - r1 * math.sin(a), cx + r * 0.92 * math.cos(a),
                             cy - r * 0.92 * math.sin(a), fill=theme.BG, width=2 if i % 5 == 0 else 1)
        self.create_arc(cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9, start=-30, extent=50,
                        style="arc", outline=theme.RED, width=3)
        a = math.radians(70)
        self.create_line(cx, cy, cx + r * 0.75 * math.cos(a), cy - r * 0.75 * math.sin(a), fill=theme.RED, width=2)
        self.create_oval(cx - px(4), cy - px(4), cx + px(4), cy + px(4), fill=theme.LINE_HI, outline=theme.BG)


# ---------------------------------------------------------------------------
# Рамки окон: каждый профиль задаёт свой стиль, механизм один
# ---------------------------------------------------------------------------

# Стиль рамки профиля; JSON скина может переопределить: "alt_ui": {"frame": "hud"}.
FRAME_OF_PROFILE = {"starship": "hud", "steampunk": "brass", "generic": "plain"}
FRAME_STYLES = ("hud", "brass", "plain")


def frame_style(profile: str, data: dict | None = None) -> str:
    if data is None:
        try:
            data = theme.current()
        except Exception:  # noqa: BLE001
            data = {}
    f = ((data or {}).get("alt_ui") or {}).get("frame")
    return f if f in FRAME_STYLES else FRAME_OF_PROFILE.get(profile, "plain")


class SkinFrame(tk.Frame):
    """Рамка вокруг окна/панели: четыре кромки-холста, внутри ``inner``.

    hud   — Звездолёт: иллюминатор/голо-панель — светящаяся кромка в 3 слоя,
            срезанные углы, болты переборки, метки шкалы.
    brass — Стимпанк: латунный брус с заклёпками, деревянная вставка,
            шестерни в углах, маленький манометр справа сверху.
    plain — тонкая линия токена LINE (для скинов без своего стиля).
    Перерисовка кромок — только при смене их размера.
    """

    def __init__(self, master, style: str, *, bg: str | None = None, edge: int = 10, title: str = "") -> None:
        bg = bg or theme.BG
        super().__init__(master, bg=bg)
        self.style = style
        self.title = title
        e = px(edge if style != "plain" else 2)
        self.edge = e
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._edges = {}
        for side, (r, c, cs, kw) in {"top": (0, 0, 3, {"height": e, "width": 1}), "bottom": (2, 0, 3, {"height": e, "width": 1}),
                                     "left": (1, 0, 1, {"width": e, "height": 1}), "right": (1, 2, 1, {"width": e, "height": 1})}.items():
            cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, **kw)
            cv.living_skip = True
            cv.grid(row=r, column=c, columnspan=cs, sticky="nsew")
            cv._size = None
            cv.bind("<Configure>", lambda ev, s=side: self._on_edge(s, ev))
            self._edges[side] = cv
        self.inner = tk.Frame(self, bg=bg)
        self.inner.grid(row=1, column=1, sticky="nsew")

    def _on_edge(self, side: str, ev) -> None:
        cv = self._edges[side]
        size = (int(ev.width), int(ev.height))
        if size == cv._size:
            return
        cv._size = size
        cv.delete("all")
        getattr(self, f"_edge_{self.style}", self._edge_plain)(cv, side, *size)

    def _edge_plain(self, cv, side, w, h) -> None:
        cv.create_rectangle(0, 0, w, h, fill=theme.LINE, outline="")

    def _edge_hud(self, cv, side, w, h) -> None:
        e = self.edge
        glow = [blend(theme.BG, theme.CYAN, k) for k in (0.18, 0.45, 1.0)]
        horiz = side in ("top", "bottom")
        # переборка: тёмная обшивка
        cv.create_rectangle(0, 0, w, h, fill=blend(theme.BG, theme.PANEL, 0.7), outline="")
        for i, col in enumerate(glow):   # светящаяся кромка стекла — к внутренней стороне
            off = e - 1 - (2 - i) * max(1, e // 5)
            if horiz:
                y = off if side == "top" else (h - 1 - off)
                cv.create_line(e, y, w - e, y, fill=col, width=1 if i < 2 else 2)
            else:
                x = off if side == "left" else (w - 1 - off)
                cv.create_line(x, 0, x, h, fill=col, width=1 if i < 2 else 2)
        if horiz:
            for x in range(e * 4, w - e * 4, px(16)):   # метки шкалы
                y0 = 1 if side == "top" else h - 3
                cv.create_line(x, y0, x, y0 + 2, fill=theme.CYAN_DIM)
            for x in (e // 2, w - e // 2):   # болты переборки в углах
                cy = h / 2
                cv.create_oval(x - 3, cy - 3, x + 3, cy + 3, fill=theme.LINE_HI, outline=theme.BG)
            # срез угла голо-панели
            cv.create_line(0, h if side == "top" else 0, e * 2, (h - e) if side == "top" else e, fill=theme.CYAN, width=2)
            cv.create_line(w, h if side == "top" else 0, w - e * 2, (h - e) if side == "top" else e, fill=theme.CYAN, width=2)
            if side == "top" and self.title:
                cv.create_text(e * 4, h / 2, anchor="w", text=self.title, fill=theme.CYAN, font=theme.font(7, True))
        else:
            cv.create_rectangle(1, h * 0.4, w - 1, h * 0.4 + px(30), fill=theme.AMBER_DIM, outline="")

    def _edge_brass(self, cv, side, w, h) -> None:
        e = self.edge
        brass = blend(theme.PANEL, theme.AMBER, 0.38)
        copper = blend(theme.PANEL, theme.RED, 0.35)
        wood = blend(theme.BG, theme.PANEL, 0.5)
        horiz = side in ("top", "bottom")
        cv.create_rectangle(0, 0, w, h, fill=brass, outline="")
        # внутренняя деревянная вставка и медная окантовка
        if horiz:
            yi = h - 3 if side == "top" else 0
            cv.create_rectangle(0, yi, w, yi + 3, fill=wood, outline="")
            cv.create_line(0, 0 if side == "top" else h - 1, w, 0 if side == "top" else h - 1, fill=theme.LINE_HI)
            cv.create_line(0, h / 2 + (2 if side == "top" else -2), w, h / 2 + (2 if side == "top" else -2), fill=copper)
            r = max(2, e // 5)
            for x in range(e * 3, w - e * 3, px(26)):   # заклёпки
                cv.create_oval(x - r, h / 2 - r - 1, x + r, h / 2 + r - 1, fill=theme.LINE_HI, outline=theme.BG)
            for x in (e, w - e):   # шестерни в углах
                draw_gear(cv, x, h / 2, e * 0.95, 8, copper, theme.BG)
            if side == "top":
                if self.title:
                    tw = len(self.title) * px(6) + px(16)
                    cv.create_rectangle(e * 3, 1, e * 3 + tw, h - 1, fill=blend(brass, theme.TEXT, 0.15), outline=theme.BG)
                    cv.create_text(e * 3 + px(8), h / 2, anchor="w", text=self.title, fill=theme.BG,
                                   font=theme.font(7, True))
                gx = w - e * 4   # маленький манометр на кромке
                cv.create_oval(gx - e, 0, gx + e, h, fill=blend(theme.TEXT, theme.PANEL, 0.15), outline=theme.LINE_HI)
                cv.create_line(gx, h / 2, gx + e * 0.6, h * 0.2, fill=theme.RED, width=2)
        else:
            xi = w - 3 if side == "left" else 0
            cv.create_rectangle(xi, 0, xi + 3, h, fill=wood, outline="")
            cv.create_line(w / 2, 0, w / 2, h, fill=copper)
            r = max(2, e // 5)
            for y in range(e * 2, h - e, px(26)):
                cv.create_oval(w / 2 - r, y - r, w / 2 + r, y + r, fill=theme.LINE_HI, outline=theme.BG)


def wrap(master, profile: str, *, bg: str | None = None, title: str = "", edge: int = 10) -> SkinFrame:
    """Обернуть панель рамкой стиля скина: ``wrap(parent, prof).inner`` — сюда класть содержимое."""
    return SkinFrame(master, frame_style(profile), bg=bg, title=title, edge=edge)


# ---------------------------------------------------------------------------
# Отсеки: у каждого свой фон-панорама и переход «шлюзом»
# ---------------------------------------------------------------------------

# Концепции отсеков: (заголовок-подпись сцены, акцентный токен). Рисунок — в _scene_*.
COMPARTMENTS: dict[str, dict[str, tuple[str, str]]] = {
    "starship": {
        "bridge": ("ХОДОВАЯ РУБКА · ОБЗОРНЫЙ ИЛЛЮМИНАТОР", "CYAN"),
        "english": ("ОТСЕК СВЯЗИ С ЗЕМЛЁЙ · ЛИНГВОМОДУЛЬ", "GREEN"),
        "speedread": ("ГИПЕРДВИГАТЕЛЬНЫЙ ОТСЕК", "PURPLE"),
        "lounge": ("ОРАНЖЕРЕЯ · КАЮТ-КОМПАНИЯ", "GREEN"),
        "radio": ("АНТЕННЫЙ ОТСЕК · ДАЛЬНЯЯ СВЯЗЬ", "AMBER"),
        "comm": ("ПОСТ СВЯЗИ ЭКИПАЖА", "CYAN"),
        "orion": ("ЯДРО БОРТОВОГО РАЗУМА", "PURPLE"),
        "settings": ("ИНЖЕНЕРНЫЙ ОТСЕК", "AMBER"),
    },
    "steampunk": {
        "bridge": ("КОТЕЛЬНАЯ · ГЛАВНЫЙ ПАРОВОЙ ПУЛЬТ", "AMBER"),
        "english": ("БИБЛИОТЕКА ПУТЕШЕСТВЕННИКА", "TEXT"),
        "speedread": ("ЧАСОВАЯ МАСТЕРСКАЯ", "AMBER"),
        "lounge": ("ЧАЙНЫЙ САЛОН", "GREEN"),
        "radio": ("ГРАММОФОННАЯ", "AMBER"),
        "comm": ("ТЕЛЕГРАФНАЯ · ПНЕВМОПОЧТА", "CYAN"),
        "orion": ("КАБИНЕТ АВТОМАТОНА · ПЛАНЕТАРИЙ", "PURPLE"),
        "settings": ("ВЕРСТАК МЕХАНИКА", "AMBER"),
    },
}


def compartment(profile: str, zone: str | None) -> tuple[str, str] | None:
    return COMPARTMENTS.get(profile, {}).get(zone or "")


# ---------------------------------------------------------------------------
# Обои отсеков: у каждого отсека своя картинка на весь фон (Звездолёт — вид
# из окон корпуса, Стимпанк — комнаты мастерской изобретателя). Файлы:
# stamina/assets/alt_wallpapers/<profile>/<zone>.jpg (генератор —
# tools/gen_alt_wallpapers.py). Нет файла или Pillow — фон цветом скина.
# Затемнение (alt_wallpaper_dim, 0…0.9) держит текст читаемым.
# ---------------------------------------------------------------------------
WALL_DIR = Path(__file__).resolve().parent / "assets" / "alt_wallpapers"
WALL_DIM = 0.35


def wallpaper_paths(profile: str, zone: str | None) -> list[Path]:
    """Набор обоев отсека для слайдшоу: ``<zone>.jpg``, ``<zone>_2.jpg``, ``<zone>_3.jpg``…"""
    if not zone:
        return []
    d = WALL_DIR / profile
    out: list[Path] = []
    for ext in ("jpg", "png"):
        p = d / f"{zone}.{ext}"
        if p.is_file():
            out.append(p)
    try:
        extra = sorted(q for q in d.glob(f"{zone}_*.*") if q.suffix.lower() in (".jpg", ".png"))
    except OSError:
        extra = []
    return out + extra


def wallpaper_path(profile: str, zone: str | None) -> Path | None:
    ps = wallpaper_paths(profile, zone)
    return ps[0] if ps else None


WALL_INTERVALS = (0, 15, 30, 60)   # секунды смены обоев; 0 — слайдшоу выключено
WALL_INTERVAL = 30


def wall_interval(settings: dict | None) -> int:
    try:
        v = int((settings or {}).get("alt_wall_interval", WALL_INTERVAL))
    except (TypeError, ValueError):
        v = WALL_INTERVAL
    return v if v in WALL_INTERVALS else WALL_INTERVAL


def _wall_image(profile, zone, w, h, dim, path: Path | None = None):
    """PIL-картинка cover под размер (w, h) с затемнением токеном BG; None — нет."""
    p = path or wallpaper_path(profile, zone)
    if p is None or w < 8 or h < 8:
        return None
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
    except Exception:  # noqa: BLE001 — нет Pillow или битый файл: фолбэк
        return None
    sc = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * sc) + 1), max(h, int(im.height * sc) + 1)))
    l, t = (im.width - w) // 2, (im.height - h) // 2
    im = im.crop((l, t, l + w, t + h))
    if dim > 0:
        bg = theme.BG.lstrip("#")
        im = Image.blend(im, Image.new("RGB", im.size, tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4))), dim)
    return im


class Wallpaper:
    """Обои за доком и окном: Label во всю площадь body, опущен под панели.

    Слайдшоу: у отсека 3–5 картинок, раз в ``alt_wall_interval`` секунд они
    сменяются плавным наплывом (константы наплыва — те же, что у слайдшоу простоя,
    ``stamina/idle``). Перерисовка — только при смене отсека, размера или кадра
    (без update_idletasks — см. docs/HANG_100_CPU_2026-10-20.md)."""

    def __init__(self, body: tk.Frame, profile: str, dim: float = WALL_DIM, interval: int = WALL_INTERVAL) -> None:
        self.body, self.profile, self.dim = body, profile, max(0.0, min(0.9, dim))
        self.interval = interval
        self.zone: str | None = None
        self.index = 0
        self.size = (0, 0)
        self.photo = None
        self.current = None      # PIL-кадр на экране (для наплыва)
        self.label = tk.Label(body, bg=body.cget("bg"), bd=0, highlightthickness=0)
        self.label.living_skip = True
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.label.lower()
        self._job = None
        self._timer = None
        self._fade = None
        body.bind("<Configure>", self._on_size, add="+")

    @property
    def available(self) -> bool:
        return wallpaper_path(self.profile, self.zone) is not None

    @property
    def paths(self) -> list[Path]:
        return wallpaper_paths(self.profile, self.zone)

    def _on_size(self, e) -> None:
        if e.widget is not self.body:
            return
        size = (int(e.width), int(e.height))
        if size != self.size:
            self.size = size
            self._schedule()

    def set_zone(self, zone: str | None) -> None:
        if zone != self.zone:
            self.zone = zone
            self.index = 0
            self._schedule(0)

    def set_interval(self, sec: int) -> None:
        self.interval = sec
        self._arm()

    def _cancel(self, attr: str) -> None:
        job = getattr(self, attr)
        if job is not None:
            try:
                self.body.after_cancel(job)
            except tk.TclError:
                pass
        setattr(self, attr, None)

    def _schedule(self, delay: int = 150) -> None:
        self._cancel("_job")
        try:
            self._job = self.body.after(delay, self._paint)
        except tk.TclError:
            self._job = None

    def _arm(self) -> None:
        """Взвести таймер следующей картинки (если слайдшоу включено и картинок > 1)."""
        self._cancel("_timer")
        if self.interval > 0 and len(self.paths) > 1:
            try:
                self._timer = self.body.after(self.interval * 1000, self.next)
            except tk.TclError:
                self._timer = None

    def _frame(self):
        ps = self.paths
        if not ps:
            return None
        return _wall_image(self.profile, self.zone, *self.size, self.dim, ps[self.index % len(ps)])

    def _set(self, im) -> None:
        from PIL import ImageTk
        self.photo = ImageTk.PhotoImage(im, master=self.body)
        self.label.configure(image=self.photo)
        self.label.lower()

    def _paint(self) -> None:
        self._job = None
        self._cancel("_fade")
        im = self._frame()
        try:
            if im is None:
                self.photo = self.current = None
                self.label.configure(image="")
                return
            self.current = im
            self._set(im)
        except Exception:  # noqa: BLE001
            self.photo = self.current = None
        self._arm()

    def next(self) -> None:
        """Следующая картинка отсека с наплывом."""
        self._timer = None
        ps = self.paths
        if len(ps) < 2:
            return
        self.index = (self.index + 1) % len(ps)
        new = self._frame()
        old = self.current
        if new is None:
            return
        if old is None or old.size != new.size:
            self.current = new
            self._schedule(0)
            return
        try:
            from stamina.idle import XFADE_MS
        except Exception:  # noqa: BLE001
            XFADE_MS = 1200
        steps = 8      # меньше кадров, чем у простоя: обои под рабочим экраном
        self._step_fade(old, new, 1, steps, max(30, XFADE_MS // steps))

    def _step_fade(self, old, new, k, steps, dt) -> None:
        self._fade = None
        try:
            from PIL import Image
            self._set(Image.blend(old, new, k / steps) if k < steps else new)
        except Exception:  # noqa: BLE001
            return
        if k < steps:
            self._fade = self.body.after(dt, lambda: self._step_fade(old, new, k + 1, steps, dt))
        else:
            self.current = new
            self._arm()


class CompartmentBanner(tk.Canvas):
    """Панорама отсека над экраном. Перерисовка — только при смене отсека или размера.

    Переход между отсеками — «шлюз»: две створки сходятся и расходятся
    (8 кадров ≈ 0.25 с, затем таймеры гаснут). При «уменьшении движения»
    или transition=False — мгновенная смена.
    """

    FRAMES = 8
    STEP_MS = 30

    def __init__(self, master, profile: str, height: int = 64, transition: bool = True) -> None:
        super().__init__(master, bg=theme.BG, highlightthickness=0, height=px(height))
        self.living_skip = True
        self.profile = profile
        self.zone: str | None = None
        self.transition = transition
        self._size = None
        self._job = None
        self.bind("<Configure>", self._on_size)

    def _on_size(self, e) -> None:
        size = (int(e.width), int(e.height))
        if size != self._size:
            self._size = size
            self._paint()

    def set_zone(self, zone: str | None, animate: bool = True) -> None:
        if zone == self.zone:
            return
        first = self.zone is None
        self.zone = zone
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if first or not (animate and self.transition) or self._size is None:
            self._paint()
            return
        self._airlock(0)

    def _airlock(self, k: int) -> None:
        """Створки шлюза: 0…F/2 — сходятся, затем смена сцены и расхождение."""
        w, h = self._size or (0, 0)
        half = self.FRAMES // 2
        if k == half:
            self._paint()
        closed = 1 - abs(k - half) / half          # 0 → 1 → 0
        self.delete("door")
        if closed > 0:
            dw = w / 2 * closed
            col = blend(theme.PANEL, theme.AMBER, 0.25) if self.profile == "steampunk" else theme.PANEL
            edge = theme.LINE_HI
            self.create_rectangle(0, 0, dw, h, fill=col, outline=edge, tags="door")
            self.create_rectangle(w - dw, 0, w, h, fill=col, outline=edge, tags="door")
            for y in range(px(8), h, px(12)):
                self.create_line(dw - px(10), y, dw - px(2), y, fill=edge, tags="door")
        if k >= self.FRAMES:
            self.delete("door")
            self._job = None
            return
        try:
            self._job = self.after(self.STEP_MS, lambda: self._airlock(k + 1))
        except tk.TclError:
            self._job = None

    def _paint(self) -> None:
        self.delete("all")
        if not self._size:
            return
        w, h = self._size
        info = compartment(self.profile, self.zone)
        if info is None:
            OrnamentBand._draw_generic(self, w, h)   # type: ignore[arg-type]
            return
        title, tok = info
        acc = getattr(theme, tok, theme.CYAN)
        base = blend(theme.BG, acc, 0.06)
        self.create_rectangle(0, 0, w, h, fill=base, outline="")
        self._photo = None
        im = _wall_image(self.profile, self.zone, w, h, 0.15)
        if im is not None:
            try:
                from PIL import ImageTk
                self._photo = ImageTk.PhotoImage(im, master=self)
                self.create_image(0, 0, image=self._photo, anchor="nw")
            except Exception:  # noqa: BLE001
                self._photo = None
        fn = getattr(self, f"_{self.profile}_{self.zone}", None)
        rnd = random.Random(sum(map(ord, f"{self.profile}{self.zone}")))
        if fn and self._photo is None:   # фолбэк: процедурная сцена
            fn(w, h, acc, rnd)
        # табличка отсека
        f = theme.font(9, True)
        txt = self.create_text(px(22), h - px(16), anchor="w", text=tr_(title), fill=theme.TEXT, font=f)
        bb = self.bbox(txt)
        tw = (bb[2] - px(10) + px(12)) if bb else len(tr_(title)) * px(8) + px(24)
        if self.profile == "steampunk":
            plate = blend(theme.PANEL, theme.AMBER, 0.35)
            pid = self.create_rectangle(px(10), h - px(26), px(10) + tw, h - px(6), fill=plate, outline=theme.LINE_HI, width=2)
            rv = [self.create_oval(x - 2, h - px(18), x + 2, h - px(14), fill=theme.LINE_HI, outline="")
                  for x in (px(15), px(5) + tw)]
        else:
            pid = self.create_polygon(chamfer(px(10), h - px(26), px(10) + tw, h - px(6), px(6)),
                                      fill=blend(theme.BG, acc, 0.15), outline=acc)
            rv = []
        self.tag_raise(pid)
        for r in rv:
            self.tag_raise(r)
        self.tag_raise(txt)
        self.create_line(0, h - 1, w, h - 1, fill=blend(acc, theme.BG, 0.5))

    # --- Звездолёт -------------------------------------------------------
    def _stars(self, w, h, rnd, n=None):
        for _ in range(n or max(20, w // 10)):
            x, y = rnd.randrange(0, max(1, w)), rnd.randrange(0, max(1, h))
            self.create_rectangle(x, y, x + 1, y + 1, fill=theme.TEXT if rnd.random() > 0.85 else theme.MUTED, outline="")

    def _starship_bridge(self, w, h, acc, rnd):
        self._stars(w, h, rnd)
        r = h * 1.4   # планета в иллюминаторе
        self.create_oval(w * 0.72, h * 0.35, w * 0.72 + r, h * 0.35 + r, fill=blend(theme.BG, acc, 0.25), outline=acc)
        for x in range(0, w, px(160)):   # рёбра иллюминатора
            self.create_line(x, 0, x + px(20), h, fill=theme.LINE, width=3)

    def _starship_english(self, w, h, acc, rnd):
        self._stars(w, h, rnd, w // 25)
        cx, cy = w * 0.8, h * 0.6
        for i in range(1, 6):   # волны передачи к Земле
            self.create_arc(cx - i * px(18), cy - i * px(18), cx + i * px(18), cy + i * px(18), start=120, extent=60,
                            style="arc", outline=blend(acc, theme.BG, i / 7), width=2)
        self.create_oval(w * 0.93, h * 0.2, w * 0.93 + px(30), h * 0.2 + px(30), fill=blend(theme.BG, theme.CYAN, 0.4),
                         outline=theme.GREEN)

    def _starship_speedread(self, w, h, acc, rnd):
        cx, cy = w * 0.7, h * 0.45
        for _ in range(60):   # гиперпространственные штрихи
            a = rnd.uniform(0, 2 * math.pi)
            r1, r2 = rnd.uniform(px(10), w * 0.2), rnd.uniform(w * 0.22, w * 0.5)
            self.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a) * 0.3, cx + r2 * math.cos(a),
                             cy + r2 * math.sin(a) * 0.3, fill=blend(acc, theme.BG, rnd.uniform(0.2, 0.7)))

    def _starship_lounge(self, w, h, acc, rnd):
        self._stars(w, h, rnd, w // 30)
        for x in range(px(260), w, px(70)):   # листья оранжереи
            hh = rnd.uniform(h * 0.3, h * 0.8)
            self.create_arc(x, h - hh, x + px(40), h + hh * 0.2, start=60, extent=80, style="arc", outline=acc, width=2)
            self.create_line(x + px(20), h, x + px(20), h - hh * 0.8, fill=theme.GREEN_DIM)

    def _starship_radio(self, w, h, acc, rnd):
        self._stars(w, h, rnd, w // 25)
        bx = w * 0.82
        self.create_line(bx, h, bx, h * 0.25, fill=theme.LINE_HI, width=3)
        self.create_arc(bx - px(30), h * 0.05, bx + px(30), h * 0.55, start=200, extent=140, style="arc", outline=acc, width=3)
        for i in range(1, 5):
            self.create_arc(bx - i * px(26), h * 0.25 - i * px(16), bx + i * px(26), h * 0.25 + i * px(16), start=30,
                            extent=120, style="arc", outline=blend(acc, theme.BG, i / 6))

    def _starship_comm(self, w, h, acc, rnd):
        pts = [(rnd.uniform(w * 0.3, w), rnd.uniform(0, h)) for _ in range(14)]
        for i, (x, y) in enumerate(pts):   # сеть связи экипажа
            x2, y2 = pts[(i * 5 + 3) % len(pts)]
            self.create_line(x, y, x2, y2, fill=blend(acc, theme.BG, 0.65))
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=acc, outline="")

    def _starship_orion(self, w, h, acc, rnd):
        cx, cy = w * 0.78, h * 0.5
        for i in range(1, 6):   # кольца ядра
            r = i * px(14)
            self.create_oval(cx - r * 1.8, cy - r * 0.5, cx + r * 1.8, cy + r * 0.5, outline=blend(acc, theme.BG, i / 7))
        self.create_oval(cx - px(9), cy - px(9), cx + px(9), cy + px(9), fill=acc, outline=theme.TEXT)

    def _starship_settings(self, w, h, acc, rnd):
        for x in range(0, w, px(24)):   # инженерная сетка и трубопроводы
            self.create_line(x, 0, x, h, fill=theme.LINE)
        for y in range(0, h, px(16)):
            self.create_line(0, y, w, y, fill=theme.LINE)
        self.create_line(w * 0.35, h * 0.3, w, h * 0.3, fill=acc, width=3)
        self.create_line(w * 0.5, h * 0.3, w * 0.5, h, fill=acc, width=3)

    # --- Стимпанк --------------------------------------------------------
    def _pipes(self, w, h, y, col):
        self.create_line(0, y, w, y, fill=col, width=max(4, px(7)))
        self.create_line(0, y - px(3), w, y - px(3), fill=theme.LINE_HI)
        for x in range(px(80), w, px(180)):
            self.create_rectangle(x - px(4), y - px(7), x + px(4), y + px(7), fill=theme.LINE_HI, outline=theme.BG)

    def _steampunk_bridge(self, w, h, acc, rnd):
        self._pipes(w, h, h * 0.3, theme.CYAN_DIM)
        bx = w * 0.82   # котёл с топкой
        self.create_rectangle(bx, h * 0.1, bx + px(90), h, fill=blend(theme.PANEL, acc, 0.3), outline=theme.LINE_HI, width=2)
        self.create_oval(bx + px(25), h * 0.45, bx + px(65), h * 0.45 + px(30), fill=theme.RED, outline=theme.LINE_HI)
        draw_gear(self, w * 0.68, h * 0.7, h * 0.45, 12, blend(theme.PANEL, acc, 0.2), theme.LINE)

    def _steampunk_english(self, w, h, acc, rnd):
        for x in range(int(w * 0.3), w, px(14)):   # корешки книг на полке
            bh = rnd.uniform(h * 0.4, h * 0.85)
            self.create_rectangle(x, h - bh, x + px(11), h - px(2),
                                  fill=blend(theme.PANEL, rnd.choice([theme.AMBER, theme.RED, theme.GREEN]), 0.35),
                                  outline=theme.BG)
        self.create_line(w * 0.3, h - px(2), w, h - px(2), fill=theme.LINE_HI, width=3)

    def _steampunk_speedread(self, w, h, acc, rnd):
        for i, (fx, r, t) in enumerate(((0.55, 0.5, 14), (0.68, 0.32, 10), (0.8, 0.6, 16), (0.93, 0.28, 8))):
            draw_gear(self, w * fx, h * (0.4 + 0.25 * (i % 2)), h * r, t, blend(theme.PANEL, acc, 0.15 + 0.07 * i),
                      theme.LINE, i * 0.2)

    def _steampunk_lounge(self, w, h, acc, rnd):
        cx = w * 0.8   # чайник и пар
        self.create_oval(cx - px(30), h * 0.4, cx + px(30), h, fill=blend(theme.PANEL, theme.AMBER, 0.35), outline=theme.LINE_HI)
        self.create_line(cx + px(28), h * 0.65, cx + px(52), h * 0.45, fill=theme.LINE_HI, width=4)
        for i in range(3):
            x = cx - px(10) + i * px(10)
            self.create_line(x, h * 0.38, x - px(6), h * 0.2, x + px(4), h * 0.05, smooth=True, fill=theme.MUTED)

    def _steampunk_radio(self, w, h, acc, rnd):
        cx, cy = w * 0.85, h * 0.4   # раструб граммофона
        self.create_polygon(cx, cy, cx - px(70), cy - h * 0.35, cx - px(70), cy + h * 0.45, fill=blend(theme.PANEL, acc, 0.45),
                            outline=theme.LINE_HI)
        self.create_rectangle(cx - px(5), cy, cx + px(40), h, fill=blend(theme.PANEL, theme.RED, 0.3), outline=theme.LINE_HI)
        for i in range(1, 4):
            self.create_arc(cx - px(70) - i * px(14), cy - i * px(14), cx - px(70) + i * px(14), cy + i * px(14), start=150,
                            extent=60, style="arc", outline=blend(acc, theme.BG, i / 5))

    def _steampunk_comm(self, w, h, acc, rnd):
        for k in range(3):   # трубы пневмопочты
            y = h * (0.2 + 0.25 * k)
            self._pipes(w, h, y, theme.CYAN_DIM)
        self.create_oval(w * 0.75, h * 0.1, w * 0.75 + px(40), h * 0.1 + px(18), fill=acc, outline=theme.BG)

    def _steampunk_orion(self, w, h, acc, rnd):
        cx, cy = w * 0.8, h * 0.5   # латунный планетарий
        for i, r in enumerate((px(14), px(28), px(42))):
            self.create_oval(cx - r * 1.6, cy - r * 0.6, cx + r * 1.6, cy + r * 0.6, outline=theme.LINE_HI)
            a = 0.8 + i
            x, y = cx + r * 1.6 * math.cos(a), cy + r * 0.6 * math.sin(a)
            self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=acc, outline="")
        self.create_oval(cx - px(8), cy - px(8), cx + px(8), cy + px(8), fill=theme.AMBER, outline=theme.LINE_HI)

    def _steampunk_settings(self, w, h, acc, rnd):
        self.create_rectangle(w * 0.3, h * 0.75, w, h, fill=blend(theme.PANEL, theme.AMBER, 0.2), outline=theme.LINE)
        for i, x in enumerate(range(int(w * 0.4), w, px(60))):   # инструменты на верстаке
            if i % 2:
                self.create_line(x, h * 0.2, x, h * 0.72, fill=theme.LINE_HI, width=4)
                self.create_oval(x - px(8), h * 0.1, x + px(8), h * 0.28, outline=theme.LINE_HI, width=3)
            else:
                draw_gear(self, x, h * 0.45, h * 0.22, 8, blend(theme.PANEL, acc, 0.25), theme.LINE)


# ---------------------------------------------------------------------------
# Док отсеков (замена горизонтальной ленты зон)
# ---------------------------------------------------------------------------

class AltRail(tk.Frame):
    """Вертикальный док зон. Повторяет контракт HScrollStrip, который ждёт кабина:
    ``inner``, ``wire(widget)``, ``_sync()``."""

    def __init__(self, master, profile: str, bg: str) -> None:
        super().__init__(master, bg=bg)
        self.profile = profile
        self.inner = tk.Frame(self, bg=bg)
        self.inner.pack(side=tk.TOP, fill=tk.X)

    def wire(self, _w) -> None:   # прокрутка колёсиком доку не нужна: зоны всегда влезают
        return None

    def _sync(self, _e=None) -> None:
        return None


# ---------------------------------------------------------------------------
# Окно с прокруткой: экран никогда не обрезается — если он выше окна,
# появляется тонкая полоса прокрутки в стиле скина (колесо, перетаскивание,
# фокус с клавиатуры прокручивает к кнопке).
# ---------------------------------------------------------------------------

class SlimBar(tk.Canvas):
    """Тонкая полоса прокрутки, нарисованная токенами скина."""

    def __init__(self, master, view: "ScrollViewport", bg: str) -> None:
        super().__init__(master, bg=bg, highlightthickness=0, width=px(10), cursor="hand2")
        self.view = view
        self.first, self.last = 0.0, 1.0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self._grab = None

    def set(self, first, last) -> None:
        self.first, self.last = float(first), float(last)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        h, w = self.winfo_height(), self.winfo_width()
        if self.last - self.first >= 0.999 or h < 4:
            return
        y0, y1 = self.first * h, max(self.first * h + px(18), self.last * h)
        self.create_rectangle(w // 2 - 1, 0, w // 2 + 1, h, fill=blend(theme.BG, theme.CYAN, 0.15), outline="")
        self.create_rectangle(1, y0, w - 1, y1, fill=blend(theme.BG, theme.AMBER if self.view.profile == "steampunk"
                                                           else theme.CYAN, 0.6), outline="")

    def _press(self, e) -> None:
        h = max(1, self.winfo_height())
        f = e.y / h
        if self.first <= f <= self.last:
            self._grab = f - self.first
        else:
            self._grab = (self.last - self.first) / 2
            self.view.canvas.yview_moveto(f - self._grab)

    def _drag(self, e) -> None:
        if self._grab is not None:
            self.view.canvas.yview_moveto(e.y / max(1, self.winfo_height()) - self._grab)


class ScrollViewport(tk.Frame):
    """Рамка, в которой лежат экраны кабины (``app.content`` = ``inner``)."""

    def __init__(self, master, app, bg: str, profile: str = "generic") -> None:
        super().__init__(master, bg=bg)
        self.app, self.profile = app, profile
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=px(24))
        self.bar = SlimBar(self, self, bg)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.bind("<Configure>", lambda _e: self.relayout())
        self.need = 0
        self._bar_on = False
        app.bind_all("<MouseWheel>", self._wheel, add="+")
        app.bind_all("<Button-4>", self._wheel, add="+")
        app.bind_all("<Button-5>", self._wheel, add="+")
        app.bind_all("<FocusIn>", self._focus, add="+")
        self.after(1000, self._watch)

    def _current(self):
        return (getattr(self.app, "screens", None) or {}).get(getattr(self.app, "current", None))

    def required(self) -> int:
        scr = self._current()
        wp = working_page(scr) if scr is not None else None
        if wp:
            # рабочая страница: высота — её собственная (а не самой высокой страницы
            # в общей ячейке grid), прокрутка — только если карточка правда не влезает
            try:
                page = wp[0]
                return int(scr.winfo_reqheight() - page.master.winfo_reqheight() + page.winfo_reqheight())
            except tk.TclError:
                return 0
        try:
            return int(scr.winfo_reqheight()) if scr is not None else 0
        except tk.TclError:
            return 0

    def relayout(self) -> None:
        try:
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        except tk.TclError:
            return
        if w < 4 or h < 4:
            return
        need = self.required()
        self.need = need
        full = max(h, need)
        self.canvas.itemconfigure(self.win, width=w, height=full)
        self.canvas.configure(scrollregion=(0, 0, w, full))
        over = need > h + 1
        if over != self._bar_on:
            self._bar_on = over
            if over:
                self.bar.pack(side=tk.RIGHT, fill=tk.Y, before=self.canvas)
            else:
                self.bar.pack_forget()
        if not over:
            self.canvas.yview_moveto(0)
            self._work_seen = None
            return
        # вошли в рабочую страницу, а она не влезает — прокрутить к ней (карточка сразу
        # на виду, навигация отсека выше — колесом/полосой)
        scr = self._current()
        wp = working_page(scr) if scr is not None else None
        key = (id(scr), id(wp[0])) if wp else None
        if key is not None and key != getattr(self, "_work_seen", None):
            self._work_seen = key
            try:
                focus = getattr(wp[0], "panel", None) or wp[0]   # сама карточка, если есть
                top = focus.winfo_rooty() - self.inner.winfo_rooty()
                self.canvas.yview_moveto(max(0, top - px(6)) / max(1, full))
            except tk.TclError:
                pass
        elif key is None:
            self._work_seen = None

    @property
    def overflow(self) -> bool:
        try:
            return self.need > self.canvas.winfo_height() + 1
        except tk.TclError:
            return False

    def _watch(self) -> None:
        """Раз в секунду: не вырос ли экран (вкладка, раскрытый список). Дёшево:
        одно winfo_reqheight, перестройка только при изменении."""
        try:
            scr = self._current()
            if getattr(self.app, "_alt_pressing", False):
                pass           # между нажатием и отпусканием экран не трогаем (иначе кнопка уезжает)
            elif scr is not None and bool(working_page(scr)) != bool(getattr(self.app, "_alt_working", False)):
                refresh_screen(self.app)   # страницу сменили без щелчка (клавиша, программно)
            elif self.required() != self.need:
                self.relayout()
            self.after(1000, self._watch)
        except tk.TclError:
            pass

    def _inside(self, w) -> bool:
        try:
            return str(w).startswith(str(self.inner))
        except Exception:  # noqa: BLE001
            return False

    def _wheel(self, e):
        w = e.widget
        if not self.overflow or not self._inside(w):
            return None
        # у списков и текстов — своя прокрутка
        x = w
        while x is not None and x is not self.inner:
            try:
                if x.winfo_class() in ("Text", "Listbox") or (
                        x.winfo_class() == "Canvas" and x is not self.canvas and str(x.cget("yscrollcommand"))):
                    return None
            except tk.TclError:
                return None
            x = getattr(x, "master", None)
        step = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step * 2, "units")
        return None

    def _focus(self, e) -> None:
        w = e.widget
        if not isinstance(w, tk.Misc) or not self.overflow or not self._inside(w):
            return
        if getattr(self.app, "_alt_pressing", False):
            return     # фокус от щелчка мышью: кнопка уже видна, прокрутка увела бы её из-под курсора
        self.see(w)

    def see(self, w) -> None:
        try:
            y = w.winfo_rooty() - self.inner.winfo_rooty()
            hh = w.winfo_height()
            top = self.canvas.canvasy(0)
            vh = self.canvas.winfo_height()
            full = max(1, self.need)
            if y < top:
                self.canvas.yview_moveto(max(0, y - px(10)) / full)
            elif y + hh > top + vh:
                self.canvas.yview_moveto(max(0, y + hh + px(10) - vh) / full)
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Окно входа, вариант «Пульт-кабина»: сцена над карточками пилотов.
# Звездолёт — шлюз / терминал посадки (створки, табло, слайдшоу обоев космоса),
# Стимпанк — вход в мастерскую / реестр изобретателя в рамке ар-нуво.
# Живой предпросмотр: сцена перестраивается при каждом выборе скина или варианта.
# ---------------------------------------------------------------------------
LOGIN_STAGE = {
    "starship": ("ШЛЮЗ · ТЕРМИНАЛ ПОСАДКИ", "Выберите пилота — створки шлюза откроются", "CYAN"),
    "steampunk": ("МАСТЕРСКАЯ · РЕЕСТР ИЗОБРЕТАТЕЛЯ", "Распишитесь в реестре — мастерская ждёт", "AMBER"),
}
LOGIN_SLIDE_MS = 7000


def login_wallpapers(profile: str) -> list[Path]:
    d = WALL_DIR / profile
    try:
        return sorted(q for q in d.glob("*.*") if q.suffix.lower() in (".jpg", ".png"))
    except OSError:
        return []


class LoginStage(tk.Frame):
    """Сцена окна входа. ``set(profile, variant, pair)`` — показать/спрятать и перерисовать."""

    def __init__(self, master, height: int = 130) -> None:
        super().__init__(master, bg=theme.BG)
        self.h = height
        self.profile = None
        self.shown = False
        self.pair = ""
        self.paths: list[Path] = []
        self.i = 0
        self.photo = None
        self.cv = None
        self._job = None
        self._paint_job = None

    def set(self, profile: str, variant: str, pair: str = "") -> bool:
        show = variant == "alt" and profile in LOGIN_STAGE
        self.pair = pair
        self._cancel()
        for w in self.winfo_children():
            w.destroy()
        self.cv = None
        self.configure(bg=theme.BG)
        self.shown = show
        if not show:
            return False
        self.profile = profile
        self.paths = login_wallpapers(profile)
        random.Random(len(self.paths)).shuffle(self.paths)
        frame = wrap(self, profile, edge=10)
        frame.pack(fill=tk.BOTH, expand=True)
        self.cv = tk.Canvas(frame.inner, height=px(self.h), bg=theme.BG2, highlightthickness=0, bd=0)
        self.cv.living_skip = True
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<Configure>", lambda _e: self._schedule())
        self._job = self.after(LOGIN_SLIDE_MS, self._next)
        return True

    def dispose(self) -> None:
        """Снять таймеры слайдшоу и отпустить картинку — сцена больше не нужна."""
        self._cancel()
        self.photo = None
        self.paths = []

    def destroy(self) -> None:
        self.dispose()
        super().destroy()

    def _cancel(self) -> None:
        for a in ("_job", "_paint_job"):
            j = getattr(self, a)
            if j is not None:
                try:
                    self.after_cancel(j)
                except tk.TclError:
                    pass
                setattr(self, a, None)

    def _schedule(self) -> None:
        if self._paint_job is not None:
            try:
                self.after_cancel(self._paint_job)
            except tk.TclError:
                pass
        self._paint_job = self.after(60, self._paint)

    def _next(self) -> None:
        self._job = None
        if not self.shown or not self.winfo_exists():
            return
        if self.paths:
            self.i = (self.i + 1) % len(self.paths)
            self._paint()
        self._job = self.after(LOGIN_SLIDE_MS, self._next)

    def _paint(self) -> None:
        self._paint_job = None
        cv = self.cv
        if cv is None or not cv.winfo_exists():
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or h < 20:
            return
        cv.delete("all")
        prof = self.profile
        title, sub, tok = LOGIN_STAGE[prof]
        acc = getattr(theme, tok, theme.CYAN)
        if self.paths:
            im = _wall_image(prof, None, w, h, 0.45, self.paths[self.i % len(self.paths)])
            if im is not None:
                from PIL import ImageTk
                self.photo = ImageTk.PhotoImage(im, master=cv)
                cv.create_image(0, 0, image=self.photo, anchor="nw")
        if prof == "starship":
            self._airlock(cv, w, h, acc)
        else:
            self._nouveau(cv, w, h, acc)
        cx = w // 2
        cv.create_text(cx, h // 2 - px(16), text=tr_(title), fill=acc, font=theme.font(15, True))
        cv.create_text(cx, h // 2 + px(10), text=tr_(sub), fill=theme.TEXT, font=theme.font(9))
        if self.pair:
            cv.create_text(cx, h - px(14), text=self.pair, fill=theme.MUTED, font=theme.font(8, True))
        if len(self.paths) > 1:
            cv.create_text(w - px(84), px(14), anchor="e", fill=acc, font=theme.font(8, True),
                           text=f"◆ {self.i % len(self.paths) + 1} / {len(self.paths)}")

    def _airlock(self, cv, w, h, acc) -> None:
        """Створки шлюза: скошенные панели по краям, жёлто-чёрная разметка, табло."""
        d = min(w // 5, px(170))
        for side in (0, 1):
            x0 = 0 if side == 0 else w
            sgn = 1 if side == 0 else -1
            pts = [x0, 0, x0 + sgn * d, 0, x0 + sgn * (d - px(26)), h // 2, x0 + sgn * d, h, x0, h]
            cv.create_polygon(*pts, fill=theme.BG2, outline=acc, width=2, stipple="gray50")
            for k in range(6):
                y = px(8) + k * (h - px(16)) // 6
                cv.create_line(x0 + sgn * px(6), y, x0 + sgn * px(22), y + px(10), fill=theme.AMBER, width=px(3))
        cv.create_rectangle(w // 2 - px(110), px(6), w // 2 + px(110), px(24), outline=acc)
        cv.create_text(w // 2, px(15), text=tr_("ДОК 7 · ДАВЛЕНИЕ НОРМА"), fill=theme.GREEN, font=theme.font(7, True))

    def _nouveau(self, cv, w, h, acc) -> None:
        """Ар-нуво: изогнутые латунные стебли и завитки по углам, шестерня-печать реестра."""
        col = theme.AMBER
        r = min(h // 2, px(60))
        for (x, y, a0) in ((0, 0, 270), (w, 0, 180), (0, h, 0), (w, h, 90)):
            for k in (1.0, 0.72, 0.46):
                rr = int(r * k)
                cv.create_arc(x - rr, y - rr, x + rr, y + rr, start=a0, extent=90, style="arc", outline=col, width=2)
        cv.create_line(px(70), h - px(26), w // 2 - px(130), h - px(26), fill=col, width=2, smooth=True)
        cv.create_line(w // 2 + px(130), h - px(26), w - px(70), h - px(26), fill=col, width=2)
        draw_gear(cv, w - px(70), h // 2, px(22), 10, theme.BG2, col)
        cv.create_text(w - px(70), h // 2, text="№", fill=acc, font=theme.font(10, True))


# ---------------------------------------------------------------------------
# Настройки в «Пульт-кабине»: вместо вкладок — все группы одна под другой в
# прокрутке, каждая сворачивается заголовком «▾ / ▸». Свёрнутые запоминаются
# у пилота (alt_settings_closed). Кнопки вкладок остаются: раскрывают группу и
# прокручивают к ней — горячие клавиши Alt+1…4 / Ctrl+Tab работают как раньше.
# ---------------------------------------------------------------------------
SECTION_KEY = "alt_settings_closed"


def settings_sections(scr) -> None:
    pnl0 = scr.tabs[next(iter(scr.tabs))][0]
    host = pnl0.master
    host.grid_rowconfigure(0, weight=0)
    st = scr.app.store.settings
    closed = set(st.get(SECTION_KEY) or [])
    scr._alt_sections = {}

    def title(key):
        return scr.tab_btns[key]._text.split(" · ")[0]

    def set_open(key, open_, save=True):
        pnl, head = scr._alt_sections[key]
        head.set_text(("▾ " if open_ else "▸ ") + title(key))
        head.set_active(open_)
        if open_:
            pnl.grid()
            closed.discard(key)
        else:
            pnl.grid_remove()
            closed.add(key)
        if save:
            st[SECTION_KEY] = sorted(closed)
            try:
                scr.app.store.save_settings()
            except Exception:  # noqa: BLE001 — сохранение свёрток не критично
                pass
        _later(scr.app, 60)

    for i, (key, (pnl, _inner)) in enumerate(scr.tabs.items()):
        head = HudButton(host, "▾ " + title(key), lambda k=key: set_open(k, k in closed),
                         height=28, font_size=10, color=theme.AMBER)
        head.grid(row=2 * i, column=0, sticky="w", pady=(px(8) if i else 0, px(2)))
        pnl.grid(row=2 * i + 1, column=0, sticky="nsew")
        scr._alt_sections[key] = (pnl, head)
        if key in closed:
            set_open(key, False, save=False)

    def show_tab(key):
        scr.current_tab = key
        for k, b in scr.tab_btns.items():
            b.set_active(k == key)
        if key in closed:
            set_open(key, True)
        vp = getattr(scr.app, "_alt_view", None)
        if vp is not None:
            scr.after(80, lambda: vp.see(scr._alt_sections[key][1]))

    scr.show_tab = show_tab
    scr._alt_set_open = set_open


# ---------------------------------------------------------------------------
# «Меньше кнопок на каждом уровне»: в строке кнопок экрана остаются видимыми не
# больше ROW_MAX (активные — всегда), остальные убираются в кнопку «⋯ ЕЩЁ» —
# список команд в стиле скина. Сами кнопки не пересоздаются: список вызывает
# их invoke(), поэтому функции и состояния те же, что в классическом виде.
# ---------------------------------------------------------------------------
ROW_MAX = 4
MORE_LABEL = {"starship": "⋯ КОНСОЛЬ", "steampunk": "⚙ ЯЩИК", "generic": "⋯ ЕЩЁ"}


def _is_cmd(w) -> bool:
    return isinstance(w, HudButton) and not isinstance(w, AltNavButton) and not getattr(w, "_alt_more", False)


class RowCompactor:
    """Состояние одной свёрнутой строки кнопок."""

    def __init__(self, row: tk.Misc, buttons: list, profile: str) -> None:
        self.row, self.buttons, self.profile = row, buttons, profile
        self.info = {}
        for b in buttons:
            i = dict(b.pack_info())
            i.pop("in", None)
            self.info[b] = i
        side = self.info[buttons[-1]].get("side", "left")
        self.more = HudButton(row, f"{tr_(MORE_LABEL.get(profile, MORE_LABEL['generic']))} · {0}", self.popup,
                              height=30, font_size=8, color=theme.AMBER)
        self.more._alt_more = True
        self.more.pack(side=side, padx=px(3), after=buttons[-1])
        row._alt_row = self
        self.hidden: list = []
        self.apply()

    def alive(self) -> list:
        out = []
        for b in self.buttons:
            try:
                if b.winfo_exists():
                    out.append(b)
            except tk.TclError:
                pass
        self.buttons = out
        return out

    def apply(self) -> None:
        bs = self.alive()
        if not bs:
            return
        actives = [b for b in bs if getattr(b, "_active", False)]
        # ряд-выбор (одна активная из ≥3) → выпадающий список «текущее ▾»: место под обои
        choice = len(bs) >= 3 and len(actives) == 1
        if choice:
            keep = set()
        elif len(bs) <= ROW_MAX:
            keep = set(bs)
        else:
            keep = [b for b in bs if getattr(b, "_active", False)]
            for b in bs:
                if len(keep) >= ROW_MAX - 1:
                    break
                if b not in keep:
                    keep.append(b)
            keep = set(keep)
        keep = self._fit_width(bs, keep)
        for b in bs:
            b.pack_forget()
        # «ещё» должна быть упакована, иначе pack(before=…) падает и кнопки теряются
        if self.more.winfo_manager() != "pack":
            self.more.pack(side=self.info[bs[-1]].get("side", "left"), padx=px(3))
        for b in bs:
            if b in keep:
                b.pack(**self.info[b], before=self.more)
        self.hidden = [b for b in bs if b not in keep]
        try:
            if choice:
                self.more.set_text(f"{actives[0]._text}  ▾")
                if self.more.winfo_manager() != "pack":
                    self.more.pack(side=self.info[bs[-1]].get("side", "left"), padx=px(3))
            elif self.hidden:
                self.more.set_text(f"{tr_(MORE_LABEL.get(self.profile, MORE_LABEL['generic']))} · {len(self.hidden)}")
                if self.more.winfo_manager() != "pack":
                    self.more.pack(side=self.info[bs[-1]].get("side", "left"), padx=px(3))
            else:
                self.more.pack_forget()
        except tk.TclError:
            pass

    def _fit_width(self, bs: list, keep: set) -> set:
        """Сколько кнопок реально влезает в ширину ряда (без update_idletasks:
        берём уже посчитанную ширину; 1 px — ряд ещё не разложен)."""
        avail = _avail(self.row)
        if avail <= 1:
            return keep
        pad = px(8)
        others = 0
        for k in self.row.winfo_children():
            try:
                if k not in bs and k is not self.more and k.winfo_manager() == "pack" \
                        and _pack_side(k) in ("left", "right"):
                    others += k.winfo_reqwidth() + pad
            except tk.TclError:
                pass

        def need(ks):
            n = others + sum(b.winfo_reqwidth() + pad for b in bs if b in ks)
            return n + (self.more.winfo_reqwidth() + pad if len(ks) < len(bs) else 0)
        order = [b for b in reversed(bs) if not getattr(b, "_active", False)]
        keep = set(keep)
        while keep and need(keep) > avail and order:
            b = order.pop(0)
            keep.discard(b)
        return keep

    def entries(self) -> list[tuple[str, object, bool, bool]]:
        """(подпись, кнопка, активна, доступна) — для меню и для теста паритета."""
        return [(b._text, b, bool(getattr(b, "_active", False)), bool(getattr(b, "_enabled", True)))
                for b in self.hidden]

    def popup(self) -> None:
        DropList(self.more, self.entries(), self._run, self.profile)

    def _run(self, b) -> None:
        b.invoke()
        try:
            self.row.after(50, self.apply)
        except tk.TclError:
            pass


POLL_MS = 300


class DropList(tk.Toplevel):
    """Выпадающий список в стиле скина (вместо системного меню): рамка акцентного
    цвета, ✓ у активного пункта. Мышь, ↑ ↓ Enter, Esc и щелчок мимо — закрыть."""

    current: "DropList | None" = None

    def __init__(self, anchor, entries, run, profile: str = "generic") -> None:
        if DropList.current is not None:
            DropList.current.close()
        # родитель - окно, а не кнопка: перестройка ряда не должна убивать список
        super().__init__(anchor.winfo_toplevel())
        DropList.current = self
        self.overrideredirect(True)
        try:
            self.transient(anchor.winfo_toplevel())
        except tk.TclError:
            pass
        self.run = run
        acc = theme.AMBER if profile == "steampunk" else theme.CYAN
        self.configure(bg=acc)
        box = tk.Frame(self, bg=theme.PANEL)
        box.pack(padx=px(2), pady=px(2))
        self.items: list = []
        self.cur = -1
        for text, b, active, enabled in entries:
            lab = tk.Label(box, text=("✓ " if active else "    ") + text, anchor="w", bg=theme.PANEL,
                           fg=(acc if active else theme.TEXT) if enabled else theme.FAINT,
                           font=theme.font(10, True), padx=px(12), pady=px(5), cursor="hand2")
            lab.pack(fill=tk.X)
            k = len(self.items)
            if enabled:
                lab.bind("<Button-1>", lambda _e, b=b: self.pick(b))
                lab.bind("<Enter>", lambda _e, k=k: self.hi(k))
            self.items.append((lab, b, enabled))
        self.anchor_w = anchor
        # позиция — в момент щелчка, от якоря, в пределах ЕГО монитора (окно могли перетащить)
        monitors.place_below(self, anchor)
        for seq, fn in (("<Escape>", lambda _e: self.close()), ("<Up>", lambda _e: self.step(-1)),
                        ("<Down>", lambda _e: self.step(1)), ("<Return>", lambda _e: self.enter()),
                        ("<space>", lambda _e: self.enter())):
            self.bind(seq, fn)
        # Закрытие не через <FocusOut>: на Windows фокус у overrideredirect-окна ненадёжен,
        # и список закрывался сам сразу после щелчка. Закрываем щелчком мимо, Esc, уходом
        # из программы (опрос), выбором пункта.
        self._top = anchor.winfo_toplevel()
        self._click_id = self._top.bind("<Button-1>", self._outside, add="+")
        self.after(1, self._clamp)
        self.focus_force()
        self.step(1)
        self.after(POLL_MS, self._check_focus)

    def _clamp(self) -> None:
        try:
            x, y = monitors.below_pos(self.anchor_w, self.winfo_reqwidth(), self.winfo_reqheight())
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _outside(self, e) -> None:
        """Щелчок в окне программы (не в списке): закрыть; по своей кнопке - откроется заново."""
        if e.widget is not self.anchor_w:
            self.close()

    def _check_focus(self) -> None:
        """Программа ушла в фон (Alt+Tab, другое окно) - список закрываем."""
        if DropList.current is not self:
            return
        try:
            if self._top.focus_displayof() is None and self.focus_displayof() is None:
                self.close()
                return
            self.after(POLL_MS, self._check_focus)
        except (tk.TclError, KeyError):
            self.close()

    def hi(self, k: int) -> None:
        for n, (lab, _b, _en) in enumerate(self.items):
            lab.configure(bg=blend(theme.PANEL, theme.AMBER, 0.25) if n == k else theme.PANEL)
        self.cur = k

    def step(self, d: int) -> None:
        ok = [n for n, it in enumerate(self.items) if it[2]]
        if not ok:
            return
        if self.cur not in ok:
            self.hi(ok[0] if d > 0 else ok[-1])
        else:
            self.hi(ok[(ok.index(self.cur) + d) % len(ok)])

    def enter(self) -> None:
        if 0 <= self.cur < len(self.items) and self.items[self.cur][2]:
            self.pick(self.items[self.cur][1])

    def pick(self, b) -> None:
        self.close()
        self.run(b)

    def close(self) -> None:
        if DropList.current is self:
            DropList.current = None
        try:
            self._top.unbind("<Button-1>", self._click_id)
        except (tk.TclError, AttributeError):
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass


def _pack_side(w) -> str:
    try:
        return str(w.pack_info().get("side", ""))
    except tk.TclError:
        return ""


def _avail(w) -> int:
    """Ширина, которую ряд реально может занять: своя, но не дальше правого края
    прокручиваемой области экрана (ряд может быть шире родителя и «уезжать» вправо)."""
    try:
        own = w.winfo_width()
        vp = getattr(w.winfo_toplevel(), "_alt_view", None)
        if vp is None or own <= 1:
            return own
        right = vp.canvas.winfo_rootx() + vp.canvas.winfo_width() - px(6)
        return max(1, min(own, right - w.winfo_rootx()))
    except tk.TclError:
        return 1


def _stack_panels(w, kids) -> bool:
    """Ряд крупных панелей бок о бок не влезает — переставить их столбиком (side=top)."""
    packed = [k for k in kids if k.winfo_manager() == "pack"]
    big = [k for k in packed if k.winfo_reqwidth() > px(180) and k.winfo_class() in ("Frame", "Canvas")
           and k.winfo_children()]
    starved = [k for k in packed if k.winfo_width() <= 1 and k.winfo_reqwidth() > px(40)
               and _pack_side(k) in ("left", "right") and not _is_cmd(k)]
    if starved and sum(1 for k in packed if _is_cmd(k)) >= 3:
        return False  # ряд вкладок не ставим столбцом: его свернёт compact() в <текущее ▾>
    if starved:   # сосед-панель «съела» ширину: всё боковое — столбиком
        for k in packed:
            if _pack_side(k) in ("left", "right"):
                k.pack_configure(side=tk.TOP, anchor="w")
        return True
    if len(big) < 2 or any(_pack_side(k) not in ("left", "right") for k in big):
        return False
    for k in big:
        k.pack_configure(side=tk.TOP, fill=tk.X, expand=False)
    return True


def _stack_grid(w) -> bool:
    """Сетка из нескольких колонок крупных панелей не влезает по ширине (первые колонки
    съедают всё, последние получают 1 px) — перестроить в одну колонку, сверху вниз."""
    slaves = w.grid_slaves()
    if len(slaves) < 2 or getattr(w, "_alt_stacked", False):
        return False
    info = [(k, k.grid_info()) for k in slaves]
    cols = {int(i.get("column", 0)) for _k, i in info}
    if len(cols) < 2 or not any(k.winfo_reqwidth() > px(180) for k, _i in info):
        return False
    info.sort(key=lambda t: (int(t[1].get("row", 0)), int(t[1].get("column", 0))))
    ncol, nrow = max(cols) + 1, max(int(i.get("row", 0)) + int(i.get("rowspan", 1)) for _k, i in info)
    for c in range(ncol):
        w.grid_columnconfigure(c, weight=1 if c == 0 else 0, minsize=0, uniform="")
    for r in range(max(nrow, len(info))):
        w.grid_rowconfigure(r, weight=0, minsize=0, uniform="")
    for n, (k, i) in enumerate(info):
        k.grid_configure(row=n, column=0, columnspan=1, rowspan=1, sticky="nsew")
    w._alt_stacked = True
    return True


def _shrink_overflow(root, skip=None) -> int:
    """Ряды, которые в узком окне шире своего места: pack отдаёт последним кнопкам 0 px
    и они пропадают. Ужимаем «резиновых» соседей — поля ввода (они всё равно растянутся
    fill/expand) и длинные подписи (перенос строк). Только конфигурация, без update_idletasks."""
    n = 0
    stack = [root]
    while stack:
        w = stack.pop()
        if skip is not None and w is skip:
            continue
        try:
            kids = w.winfo_children()
            over = w.winfo_width() > 1 and w.winfo_reqwidth() > _avail(w) + 2
        except tk.TclError:
            continue
        stack.extend(k for k in kids if not isinstance(k, (tk.Text, tk.Listbox)))
        if not over:
            continue
        try:
            if _stack_grid(w) or _stack_panels(w, kids):
                n += 1
                continue
        except tk.TclError:
            pass
        for k in kids:
            try:
                cls = k.winfo_class()
                if cls in ("Entry", "TEntry", "Spinbox", "TCombobox") and int(k.cget("width")) > ENTRY_MIN:
                    k.configure(width=ENTRY_MIN); n += 1
                elif cls == "Text" and int(k.cget("width")) > 20:
                    k.configure(width=20); n += 1
                elif cls == "Label" and len(str(k.cget("text"))) > 16 and not int(k.cget("wraplength") or 0):
                    k.configure(wraplength=max(px(160), w.winfo_width() // 3)); n += 1
            except (tk.TclError, ValueError):
                pass
    return n


NAV_SIDES = ("left", "right", "top", "bottom")
ENTRY_MIN = 20          # поле ввода не уже 20 знаков: подсказка (<СКАНИРОВАТЬ СЛОВО>) видна целиком


def compact(root, profile: str = "generic", skip=None) -> int:
    """Пройти по дереву ``root`` и свернуть длинные строки кнопок. Возвращает число строк.
    ``skip`` — рабочая страница: её не трогаем (правило «глубинных окон»)."""
    n = 0
    stack = [root]
    while stack:
        w = stack.pop()
        if skip is not None and w is skip:
            continue
        try:
            kids = w.winfo_children()
        except tk.TclError:
            continue
        rc = getattr(w, "_alt_row", None)
        if rc is not None:
            new = [k for k in kids if _is_cmd(k) and k not in rc.buttons and k.winfo_manager() == "pack"
                   and _pack_side(k) in NAV_SIDES]
            if new:   # экран дорисовал кнопки — пересобрать строку
                for b in new:
                    i = dict(b.pack_info()); i.pop("in", None)
                    rc.info[b] = i
                rc.buttons = [k for k in kids if k in rc.info]
            rc.apply()
            n += 1
        else:
            # ряд (left/right) или столбец (top/bottom) вкладок - сворачиваются одинаково
            btns = [k for k in kids if _is_cmd(k) and k.winfo_manager() == "pack" and _pack_side(k) in NAV_SIDES]
            nact = sum(1 for b in btns if getattr(b, "_active", False))
            try:
                side_kids = [k for k in kids if k.winfo_manager() == "pack" and _pack_side(k) in ("left", "right")]
                over = len(btns) >= 2 and w.winfo_width() > 1 and \
                    sum(k.winfo_reqwidth() + px(8) for k in side_kids) > _avail(w)
            except tk.TclError:
                over = False
            if len(btns) > ROW_MAX or (len(btns) >= 3 and nact == 1) or over:
                RowCompactor(w, btns, profile)
                n += 1
        stack.extend(k for k in kids if not isinstance(k, (tk.Text, tk.Listbox)))
    return n


def hidden_commands(root) -> list[tuple[str, object]]:
    """Все команды, убранные в «⋯ ЕЩЁ» под ``root``: (подпись, кнопка)."""
    out = []
    stack = [root]
    while stack:
        w = stack.pop()
        rc = getattr(w, "_alt_row", None)
        if rc is not None:
            out += [(t, b) for t, b, _a, _e in rc.entries()]
        try:
            stack.extend(w.winfo_children())
        except tk.TclError:
            pass
    return out


# ---------------------------------------------------------------------------
# Правило «глубинных окон»: рабочая страница (сеанс карточек, урок, читалка) видна
# целиком, как в классике — без прокрутки поверх, без баннера, без сворачивания её
# кнопок в «ещё»; ширина ограничена и по центру. Экран сообщает о ней методом
# ``alt_working() -> (страница, макс. ширина px) | None``. Классика этот метод не вызывает.
# ---------------------------------------------------------------------------

def working_page(scr):
    fn = getattr(scr, "alt_working", None)
    if fn is None:
        return None
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


def card_width(avail: int, maxw: int) -> int:
    """Ширина рабочей страницы: не шире maxw; в узком окне — всё окно (минимум не режем)."""
    return max(0, min(avail, maxw))


def apply_working(app, scr) -> bool:
    wp = working_page(scr)
    ban = getattr(app, "_alt_banner", None)
    if ban is not None:
        try:
            if not hasattr(ban, "_alt_h"):
                ban._alt_h = int(ban.cget("height"))
            ban.configure(height=1 if wp else ban._alt_h)
        except tk.TclError:
            pass
    app._alt_working = wp is not None
    if wp:
        page, maxw = wp
        try:
            avail = page.master.winfo_width()
            if avail > 4:
                pad = max(0, (avail - card_width(avail, px(maxw))) // 2)
                if page.grid_info() and int(str(page.grid_info().get("padx", 0)).split()[0]) != pad:
                    page.grid_configure(padx=pad)
        except (tk.TclError, ValueError):
            pass
    return wp is not None


def refresh_screen(app) -> None:
    """Свернуть строки кнопок текущего экрана и подменю, пересчитать прокрутку."""
    if DropList.current is not None or getattr(app, "_alt_pressing", False):
        _later(app)            # открыт список или кнопка мыши зажата: не трогаем экран (иначе он теряет фокус и закрывается)
        return
    prof = getattr(app, "_alt_profile", "generic")
    scr = (getattr(app, "screens", None) or {}).get(getattr(app, "current", None))
    try:
        if scr is not None:
            apply_working(app, scr)
            wp = working_page(scr)
            skip = wp[0] if wp else None
            if _shrink_overflow(scr, skip):
                _later(app, 80)       # пересчитать после того, как Tk разложит ужатые ряды
            compact(scr, prof, skip)
        if getattr(app, "subnav", None) is not None:
            compact(app.crumbs, prof)
    except tk.TclError:
        pass
    vp = getattr(app, "_alt_view", None)
    if vp is not None:
        vp.relayout()


def _later(app, delay: int = 250) -> None:
    job = getattr(app, "_alt_refresh_job", None)
    if job is not None:
        try:
            app.after_cancel(job)
        except tk.TclError:
            pass

    def run():
        app._alt_refresh_job = None
        if DropList.current is not None:
            # список открыт: пересборка экрана отняла бы фокус и закрыла его -
            # откладываем до закрытия
            app._alt_refresh_job = app.after(delay, run)
            return
        refresh_screen(app)
    app._alt_refresh_job = app.after(delay, run)


def make_content(app, host) -> tk.Frame:
    """``app.content`` для alt: внутренняя рамка окна с прокруткой."""
    vp = ScrollViewport(host, app, theme.BG, getattr(app, "_alt_profile", "generic"))
    vp.pack(fill=tk.BOTH, expand=True)
    app._alt_view = vp
    app._alt_page_hook = lambda: _later(app, 1)   # экран сменил внутреннюю страницу
    # после любого щелчка экран мог дорисовать кнопки (вкладка, список) — свернуть их
    app._alt_pressing = False

    def _press(_e):
        app._alt_pressing = True

    def _release(_e):
        app._alt_pressing = False
        _later(app)
    app.bind_all("<ButtonPress-1>", _press, add="+")
    app.bind_all("<ButtonRelease-1>", _release, add="+")
    return vp.inner


# ---------------------------------------------------------------------------
# Сборка рамы
# ---------------------------------------------------------------------------

def build_chrome(app) -> tk.Frame:
    """Собрать раму альтернативного вида на ``app`` (Cockpit). Возвращает рамку,
    в которую кабина кладёт ``content`` (справа от дока)."""
    from stamina.hud import HudButton as HB
    prof = profile_id()
    pdata = PROFILES[prof]
    app._alt_profile = prof
    st = app.store.settings
    BG, PANEL = theme.BG, theme.PANEL
    head_bg = blend(BG, theme.AMBER, 0.06) if prof == "steampunk" else BG
    app._compact = True

    OrnamentBand(app, prof, "top", height=12 if prof == "steampunk" else 10).pack(fill=tk.X)
    head = tk.Frame(app, bg=head_bg)
    head.pack(fill=tk.X, padx=0)
    logo = tk.Canvas(head, bg=head_bg, highlightthickness=0, width=px(200), height=px(44))
    logo.pack(side=tk.LEFT, padx=(px(10), 0), pady=px(4))
    app._draw_logo(logo)

    right = tk.Frame(head, bg=head_bg)
    right.pack(side=tk.RIGHT, padx=(0, px(10)))
    app.clock = tk.Label(right, text="", bg=head_bg, fg=theme.CYAN, font=theme.font(14, True, mono=True))
    app.clock.pack(side=tk.RIGHT, padx=(px(10), 0))
    app.rank_label = tk.Canvas(right, bg=head_bg, highlightthickness=0, height=px(44), width=px(190),
                               cursor="hand2")
    app.rank_label.pack(side=tk.RIGHT, padx=px(6))
    app.rank_label.bind("<Button-1>", lambda _e: app.pilot_menu())
    app.btn_tools = HB(right, f"☰ {tr_(pdata['drawer'])} · F8", lambda: toggle_drawer(app), height=36,
                       font_size=9, color=theme.CYAN)
    app.btn_tools.pack(side=tk.RIGHT, padx=px(4))
    # СЛАЙДЫ — прямо в шапке: запуск слайдшоу не прячется в полку (PgUp — то же)
    app.btn_slides = HB(right, tr_("СЛАЙДЫ"), lambda: app.idle.open(), height=36, font_size=9, width=90,
                        color=theme.CYAN)
    app.btn_slides.pack(side=tk.RIGHT, padx=px(4))
    app.btn_help = HB(right, "? F1", app.open_help, height=36, font_size=9, width=60, color=theme.AMBER)
    app.btn_help.pack(side=tk.RIGHT, padx=px(4))
    app.btn_orion = HB(right, tr_("ОРИОН"), app._call_orion, height=36, font_size=9, width=90,
                       color=theme.GREEN)
    app.btn_orion.pack(side=tk.RIGHT, padx=px(4))

    mid = tk.Frame(head, bg=head_bg)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(16))
    app._alt_title = tk.Label(mid, text="", bg=head_bg, fg=theme.TEXT, font=theme.font(16, True), anchor="w")
    app._alt_title.pack(side=tk.TOP, anchor="w")
    # подзаголовок переносится по словам, а не обрезается (узкая шапка, шрифт с засечками)
    sub = tk.Label(mid, text=tr_(pdata["subtitle"]), bg=head_bg, fg=theme.CYAN_DIM, font=theme.font(7, True),
                   anchor="w", justify="left", wraplength=px(260))
    sub.pack(side=tk.TOP, anchor="w", fill=tk.X)
    app._alt_subtitle = sub
    app._alt_logo = logo
    app._alt_head_level = 0
    app.bind("<Configure>", lambda e: _fit_head(app, e) if e.widget is app else None, add="+")

    def _wrap_sub(e, lbl=sub):
        wl = max(px(80), int(e.width) - px(4))
        if abs(int(lbl.cget("wraplength")) - wl) > 4:
            lbl.configure(wraplength=wl)
    mid.bind("<Configure>", _wrap_sub)

    # «ПРИБОРЫ» — выдвижная полка (по умолчанию спрятана, F8)
    app._mini_row = tk.Frame(app, bg=blend(BG, theme.CYAN, 0.05))
    app._alt_drawer_open = False
    drawer_bg = app._mini_row["bg"]
    tk.Label(app._mini_row, text=tr_(pdata["drawer"]) + ":", bg=drawer_bg, fg=theme.MUTED,
             font=theme.font(8, True)).pack(side=tk.LEFT, padx=(px(12), px(6)), pady=px(4))
    app.btn_sound = HB(app._mini_row, tr_("♪ ЗВУК ВЫКЛ"), app.toggle_sound, height=32, font_size=9, width=116)
    app.btn_sound.pack(side=tk.LEFT, padx=px(3), pady=px(4))
    app.btn_screen = HB(app._mini_row, tr_("⛶ ЭКРАН"), app.toggle_fullscreen, height=32, font_size=9, width=104,
                        color=theme.CYAN)
    app.btn_screen.pack(side=tk.LEFT, padx=px(3))
    HB(app._mini_row, tr_("? СПРАВКА"), app.open_help, height=32, font_size=9, width=104,
       color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    # звание в узкой шапке скрывается — меню пилота всегда есть здесь
    HB(app._mini_row, tr_("★ ПИЛОТ"), lambda: app.pilot_menu(), height=32, font_size=9, width=104,
       color=theme.AMBER).pack(side=tk.LEFT, padx=px(3))
    tk.Label(app._mini_row, text=tr_("F9 звук · PgDn экран"), bg=drawer_bg, fg=theme.MUTED,
             font=theme.font(8)).pack(side=tk.LEFT, padx=px(8))
    app._radio_mini = None
    try:
        from stamina.radio.minibark import RadioMiniBar
        app._radio_mini = RadioMiniBar(app._mini_row, app)
    except Exception:  # noqa: BLE001
        app._radio_mini = None
    app._alt_band = OrnamentBand(app, prof, "bottom", height=10)
    app._alt_band.pack(fill=tk.X)

    body = tk.Frame(app, bg=BG)
    body.pack(fill=tk.BOTH, expand=True)
    app._alt_body = body   # статус-строка кабины встаёт ниже этой рамки
    app._alt_wall = Wallpaper(body, prof, float(st.get("alt_wallpaper_dim", WALL_DIM)), wall_interval(st))
    # поля: широкие на большом экране (видны обои), узкие на маленьком — экран важнее
    _mw, _mh = monitors.area_size(app)
    small = _mw <= 1366 or _mh <= 800
    gap = px(10 if small else 22)   # щедрые поля: обои видны вокруг панелей
    rail_bg = blend(BG, theme.AMBER, 0.05) if prof == "steampunk" else blend(BG, theme.CYAN, 0.03)
    rail_box = wrap(body, prof, bg=rail_bg, title=tr_(pdata["rail"]) if prof != "generic" else "", edge=10)
    rail_box.pack(side=tk.LEFT, fill=tk.Y, padx=(gap, 0), pady=gap)
    app._alt_frames = [rail_box]
    rail = AltRail(rail_box.inner, prof, rail_bg)
    rail.pack(fill=tk.BOTH, expand=True)
    app.nav_strip = rail
    app._alt_rail = rail
    hdr = tk.Frame(rail.inner, bg=rail_bg)
    hdr.pack(fill=tk.X, pady=(px(6), px(4)))
    app._alt_rail_label = tk.Label(hdr, text=tr_(pdata["rail"]), bg=rail_bg, fg=theme.MUTED,
                                   font=theme.font(8, True))
    app._alt_rail_label.pack(side=tk.LEFT, padx=px(10))
    app._alt_rail_toggle = HB(hdr, "◂", lambda: toggle_rail(app), width=28, height=24, font_size=9)
    app._alt_rail_toggle.pack(side=tk.RIGHT, padx=px(6))
    app.nav_buttons = {}
    for i, (name, title) in enumerate(app.SCREENS, 1):
        b = AltNavButton(rail.inner, title, lambda n=name: app.show_zone(n), profile=prof,
                         glyph_char=glyph(prof, name), width=RAIL_WIDE, height=38, font_size=9)
        if name == "bridge":
            b.bind("<Button-3>", lambda _e: app.bridge_menu())
        b.pack(side=tk.TOP, padx=px(6), pady=px(2), anchor="w")
        b.nav_menu = True
        app.nav_buttons[name] = b
    app._alt_rail_hint = tk.Label(rail.inner, text=tr_("Ctrl+1…{0} — отсеки").format(len(app.SCREENS)), bg=rail_bg,
                                  fg=theme.FAINT, font=theme.font(7))
    app._alt_rail_hint.pack(side=tk.TOP, pady=(px(4), 0))
    app._alt_gauge = None
    if prof in ("starship", "steampunk"):
        app._alt_gauge = GaugeCanvas(rail, prof, size=150)
        app._alt_gauge.pack(side=tk.BOTTOM, pady=px(8))
        app._alt_gauge_label = tk.Label(rail, text=tr_(pdata["gauge"]), bg=rail_bg, fg=theme.FAINT,
                                        font=theme.font(7, True))
        app._alt_gauge_label.pack(side=tk.BOTTOM)

    win = wrap(body, prof, bg=BG, edge=12)
    win.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=gap, pady=gap)
    app._alt_frames.append(win)
    col = win.inner
    app.crumbs = tk.Frame(col, bg=BG)
    app.crumbs.pack(fill=tk.X, padx=px(14), pady=(px(4), 0))
    app.crumb_path = tk.Frame(app.crumbs, bg=BG)
    app.crumb_path.pack(side=tk.LEFT)
    tk.Frame(app.crumbs, bg=BG, width=px(16)).pack(side=tk.LEFT)
    app.subnav = tk.Frame(app.crumbs, bg=BG)
    app.subnav.pack(side=tk.LEFT)
    app.subnav_buttons = {}
    app._alt_banner = None
    if prof in COMPARTMENTS:
        app._alt_banner = CompartmentBanner(col, prof, height=96, transition=bool(st.get("alt_transition", True)))
        app._alt_banner.pack(fill=tk.X, padx=px(14), pady=(px(4), 0))
    for i, (key, title) in enumerate(nav.BRIDGE_LEAVES, 1):
        b = HB(app.subnav, tr_(title), lambda k=key: app.show(k), height=26, font_size=8)
        b.pack(side=tk.LEFT, padx=px(2))
        b.nav_menu = True
        app.subnav_buttons[key] = b

    app.bind("<F8>", lambda _e: toggle_drawer(app) or "break")
    if st.get("alt_rail_narrow", True):
        toggle_rail(app, narrow=True, save=False)
    return col


HEAD_LEVELS = (1700, 1400, 1150)   # логическая ширина окна (до px), ниже которой шапка ужимается


def _fit_head(app, e) -> None:
    """Шапка без обрезки на 1024×768 / 1280×720: по мере сужения окна — короткая
    подпись «☰ F8», без звания (оно на полке «ПРИБОРЫ» → «ПИЛОТ»), без часов и
    подсказки в статус-строке, узкий логотип. Только pack/forget — без update_idletasks."""
    w = int(e.width) / max(0.01, px(100) / 100)
    level = sum(1 for t in HEAD_LEVELS if w < t)
    if level == getattr(app, "_alt_head_level", 0):
        return
    app._alt_head_level = level
    pdata = PROFILES[getattr(app, "_alt_profile", "generic")]
    try:
        app.btn_tools.set_text(f"☰ {tr_(pdata['drawer'])} · F8" if level < 1 else "☰ F8")
        if level >= 2:
            app.rank_label.pack_forget()
        elif not app.rank_label.winfo_manager():
            app.rank_label.pack(side=tk.RIGHT, padx=px(6), before=app.btn_tools)
        if level >= 3:
            app.clock.pack_forget()
            app.btn_help.pack_forget()          # F1 и «? СПРАВКА» на полке остаются
            app._alt_logo.configure(width=px(100))
            app._alt_title.configure(font=theme.font(11, True))
        else:
            if not app.btn_help.winfo_manager():
                app.btn_help.pack(side=tk.RIGHT, padx=px(4), before=app.btn_orion)
            app._alt_title.configure(font=theme.font(16, True))
            if not app.clock.winfo_manager():
                app.clock.pack(side=tk.RIGHT, padx=(px(10), 0), before=app.rank_label if app.rank_label.winfo_manager() else app.btn_tools)
            app._alt_logo.configure(width=px(200))
        hint = getattr(app, "_status_hint", None)
        if hint is not None:
            if level >= 2:
                hint.pack_forget()
            elif not hint.winfo_manager():
                hint.pack(side=tk.RIGHT, padx=px(10))
    except tk.TclError:
        pass


def toggle_drawer(app, open_: bool | None = None) -> None:
    """Показать / спрятать полку «ПРИБОРЫ» (звук, экран, слайды, приёмник)."""
    want = (not getattr(app, "_alt_drawer_open", False)) if open_ is None else open_
    try:
        if want:
            app._mini_row.pack(fill=tk.X, before=app._alt_band)
        else:
            app._mini_row.pack_forget()
        app._alt_drawer_open = want
        app.btn_tools.set_active(want)
    except (tk.TclError, AttributeError):
        pass


def toggle_rail(app, narrow: bool | None = None, save: bool = True) -> None:
    """Свернуть док до значков / развернуть обратно (запоминается у пилота)."""
    want = (not app.store.settings.get("alt_rail_narrow", True)) if narrow is None else narrow
    for b in app.nav_buttons.values():
        if isinstance(b, AltNavButton):
            b.set_narrow(want)
            b.configure(width=px(RAIL_NARROW if want else RAIL_WIDE))
    try:
        app._alt_rail_toggle.set_text("▸" if want else "◂")
        if want:
            app._alt_rail_label.pack_forget()
            app._alt_rail_hint.pack_forget()
        else:
            app._alt_rail_label.pack(side=tk.LEFT, padx=px(10))
            app._alt_rail_hint.pack(side=tk.TOP, pady=(px(4), 0))
        if getattr(app, "_alt_gauge", None) is not None:
            if want:
                app._alt_gauge.pack_forget()
                app._alt_gauge_label.pack_forget()
            else:
                app._alt_gauge.pack(side=tk.BOTTOM, pady=px(8))
                app._alt_gauge_label.pack(side=tk.BOTTOM)
    except (tk.TclError, AttributeError):
        pass
    app.store.settings["alt_rail_narrow"] = want
    if save:
        try:
            app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass


def on_screen(app) -> None:
    """После смены экрана: крупное имя отсека в шапке."""
    ban = getattr(app, "_alt_banner", None)
    if ban is not None:
        ban.set_zone(nav.zone_of(app.current))
    _later(app, 60)
    wall = getattr(app, "_alt_wall", None)
    if wall is not None:
        wall.set_zone(nav.zone_of(app.current))
    lbl = getattr(app, "_alt_title", None)
    if lbl is None:
        return
    segs = nav.path(app.current)
    text = " › ".join(s for s, _ in segs) if segs else ""
    try:
        lbl.configure(text=f"{glyph(app._alt_profile, nav.zone_of(app.current) or '')}  {text}" if text else "")
    except tk.TclError:
        pass


def status_hint(n: int) -> str:
    return tr_("F1 справка и все клавиши · F8 приборы · Home Орион · Ctrl+1…{0} отсеки").format(n)


# Подписи профилей идут в tr_() не литералом — перечисляем их здесь, чтобы
# i18n-сборщик видел ключи (функция не вызывается).
def _i18n_keys() -> None:  # pragma: no cover
    tr_("БОРТОВОЙ КОМПЬЮТЕР · ОТСЕКИ КОРАБЛЯ"); tr_("МАСТЕРСКАЯ ИЗОБРЕТАТЕЛЯ · СМОТРОВЫЕ СТЁКЛА")
    tr_("ПУЛЬТ ПИЛОТА"); tr_("ОТСЕКИ"); tr_("РЫЧАГИ"); tr_("ПРИБОРЫ"); tr_("МАНОМЕТРЫ")
    tr_("РАДАР"); tr_("ДАВЛЕНИЕ"); tr_("⋯ КОНСОЛЬ"); tr_("⚙ ЯЩИК"); tr_("⋯ ЕЩЁ"); tr_("★ ПИЛОТ"); tr_("? СПРАВКА")
    for prof in COMPARTMENTS.values():
        for title, _tok in prof.values():
            tr_(title)
