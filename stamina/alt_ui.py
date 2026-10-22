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


def wallpaper_path(profile: str, zone: str | None) -> Path | None:
    if not zone:
        return None
    for ext in ("jpg", "png"):
        p = WALL_DIR / profile / f"{zone}.{ext}"
        if p.is_file():
            return p
    return None


def _wall_image(profile, zone, w, h, dim):
    """PIL-картинка cover под размер (w, h) с затемнением токеном BG; None — нет."""
    p = wallpaper_path(profile, zone)
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

    Перерисовка — только при смене отсека или размера (с задержкой 150 мс,
    без update_idletasks — см. docs/HANG_100_CPU_2026-10-20.md)."""

    def __init__(self, body: tk.Frame, profile: str, dim: float = WALL_DIM) -> None:
        self.body, self.profile, self.dim = body, profile, max(0.0, min(0.9, dim))
        self.zone: str | None = None
        self.size = (0, 0)
        self.photo = None
        self.label = tk.Label(body, bg=body.cget("bg"), bd=0, highlightthickness=0)
        self.label.living_skip = True
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.label.lower()
        self._job = None
        body.bind("<Configure>", self._on_size, add="+")

    @property
    def available(self) -> bool:
        return wallpaper_path(self.profile, self.zone) is not None

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
            self._schedule(0)

    def _schedule(self, delay: int = 150) -> None:
        if self._job is not None:
            try:
                self.body.after_cancel(self._job)
            except tk.TclError:
                pass
        try:
            self._job = self.body.after(delay, self._paint)
        except tk.TclError:
            self._job = None

    def _paint(self) -> None:
        self._job = None
        im = _wall_image(self.profile, self.zone, *self.size, self.dim)
        try:
            if im is None:
                self.photo = None
                self.label.configure(image="")
                return
            from PIL import ImageTk
            self.photo = ImageTk.PhotoImage(im, master=self.body)
            self.label.configure(image=self.photo)
            self.label.lower()
        except Exception:  # noqa: BLE001
            self.photo = None



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
    app.btn_help = HB(right, "? F1", app.open_help, height=36, font_size=9, width=60, color=theme.AMBER)
    app.btn_help.pack(side=tk.RIGHT, padx=px(4))
    app.btn_orion = HB(right, tr_("ОРИОН"), app._call_orion, height=36, font_size=9, width=90,
                       color=theme.GREEN)
    app.btn_orion.pack(side=tk.RIGHT, padx=px(4))

    mid = tk.Frame(head, bg=head_bg)
    mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(16))
    app._alt_title = tk.Label(mid, text="", bg=head_bg, fg=theme.TEXT, font=theme.font(16, True), anchor="w")
    app._alt_title.pack(side=tk.TOP, anchor="w")
    tk.Label(mid, text=tr_(pdata["subtitle"]), bg=head_bg, fg=theme.CYAN_DIM, font=theme.font(7, True),
             anchor="w").pack(side=tk.TOP, anchor="w")

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
    app.btn_slides = HB(app._mini_row, tr_("СЛАЙДЫ"), lambda: app.idle.open(), height=32, font_size=9, width=90,
                        color=theme.CYAN)
    app.btn_slides.pack(side=tk.LEFT, padx=px(3))
    tk.Label(app._mini_row, text=tr_("F9 звук · PgDn экран · PgUp слайды"), bg=drawer_bg, fg=theme.MUTED,
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
    app._alt_wall = Wallpaper(body, prof, float(st.get("alt_wallpaper_dim", WALL_DIM)))
    gap = px(26)   # щедрые поля: обои видны вокруг панелей
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
    tr_("РАДАР"); tr_("ДАВЛЕНИЕ")
    for prof in COMPARTMENTS.values():
        for title, _tok in prof.values():
            tr_(title)
