"""«Мостик → Настройки» — порт BridgeSettingsPage из веб-версии.

Четыре блока: ПРИЦЕЛ, НАБОР, ЦВЕТА, ОКОШКО ПРИЦЕЛА. Всё применяется сразу
(apply_settings мостика) и видно в живом превью сверху.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser
from typing import TYPE_CHECKING

from stamina import theme, typing_style as ts
from stamina.hud import HudButton, HudPanel, TranslatorPanel, Viewport
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, CYAN_DIM, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

if TYPE_CHECKING:  # pragma: no cover
    from stamina.cockpit import Cockpit

PREVIEW_TEXT = "the quick brown fox jumps over the lazy dog"
PREVIEW_INDEX = 16


def _label(master, text, *, fg=None, size=10, bold=False, bg=None, **kw):
    fg = TEXT if fg is None else fg  # токен скина — в момент вызова, не при импорте
    bg = PANEL if bg is None else bg  # токен скина — в момент вызова, не при импорте
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold), **kw)


def font_label(key: str) -> str:
    return {"": _t("КАК ОСН."), "S": "S", "M": "M", "L": "L", "XL": "XL", "XXL": "XXL"}[key]


FACE_LABELS = (("mono", "Моно"), ("sans", "Без засечек"), ("serif", "С засечками"), ("system", "Системный"))


class BridgeSettingsScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.groups: dict[str, dict[str, HudButton]] = {}
        self.toggles: dict[str, HudButton] = {}
        self.swatches: dict[str, tuple[tk.Label, tk.Label, str]] = {}

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("МОСТИК · НАСТРОЙКИ НАБОРА"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, _t("⟲ СБРОСИТЬ ВСЁ"), self.reset_all, height=30, font_size=9,
                  color=AMBER).pack(side=tk.RIGHT, padx=px(4))
        HudButton(top, "?", lambda: self.app.open_help(), height=30, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        _label(self, _t("Меняется сразу — смотрите превью. Общие настройки (звук, язык, скин) — в разделе «НАСТРОЙКИ»."),
               fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(16))

        prev = HudPanel(self, _t("ПРЕВЬЮ"))
        prev.pack(fill=tk.X, padx=px(14), pady=(px(6), 0))
        self.preview = Viewport(prev.body, 26)
        self.preview.configure(height=px(96))
        self.preview.pack(fill=tk.X)
        self.preview_box = TranslatorPanel(prev.body)
        self.preview_box.configure(height=px(86))
        self.preview_box.pack(fill=tk.X, pady=(px(4), 0))

        # без прокрутки (как в вебе): четыре блока — вкладки, превью всегда видно
        self.tabbar = tk.Frame(self, bg=BG)
        self.tabbar.pack(fill=tk.X, padx=px(14), pady=(px(6), 0))
        _label(self.tabbar, _t("Ctrl+Tab — следующая вкладка · Tab, стрелки — по кнопкам · Enter/пробел — нажать"),
               fg=MUTED, size=8, bg=BG).pack(side=tk.RIGHT)
        self.tab_host = tk.Frame(self, bg=BG)
        self.tab_host.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(6))
        self.tab_host.grid_rowconfigure(0, weight=1)
        self.tab_host.grid_columnconfigure(0, weight=1)
        self.tabs: dict[str, tk.Misc] = {}
        self.tab_btns: dict[str, HudButton] = {}
        grid = None
        sight = self._panel(grid, _t("ПРИЦЕЛ"), "ПРИЦЕЛ")
        self._toggle(sight, "sight", _t("Прицел на букве"), _t("Вкл — рамка с треугольниками. Выкл — только подчёркивание."))
        self._chips(sight, "cursor_font", _t("Размер буквы в прицеле"), [(k, font_label(k)) for k in ("",) + ts.FONT_KEYS])
        self._color(sight, "cursor_color", _t("Цвет буквы в прицеле"), "#FFFFFF")
        self._chips(sight, "cursor_blink", _t("Мигание целевой буквы"),
                    [("off", _t("ВЫКЛ")), ("on", _t("ВКЛ")), ("fast", _t("БЫСТРОЕ"))])
        self._toggle(sight, "keyboard", _t("Экранная клавиатура"), _t("Подсветка следующей клавиши и пальца."))
        self._toggle(sight, "zones", _t("Цветные зоны пальцев"), _t("Клавиши окрашены по пальцам, как в прежнем Stamina."))

        typ = self._panel(grid, _t("НАБОР"), "НАБОР")
        self._chips(typ, "font", _t("Размер шрифта строки"), [(k, font_label(k)) for k in ts.FONT_KEYS])
        self._chips(typ, "typed_font", _t("Размер набранного"), [(k, font_label(k)) for k in ("",) + ts.FONT_KEYS])
        self._chips(typ, "ahead_font", _t("Размер текста впереди"), [(k, font_label(k)) for k in ("",) + ts.FONT_KEYS])
        self._chips(typ, "typing_face", _t("Шрифт строки набора"), [(k, _t(v)) for k, v in FACE_LABELS])

        col = self._panel(grid, _t("ЦВЕТА"), "ЦВЕТА")
        self._color(col, "typed_color", _t("Цвет набранного"), CYAN_DIM)
        self._color(col, "ahead_color", _t("Цвет текста впереди"), TEXT)

        box = self._panel(grid, _t("ОКОШКО ПРИЦЕЛА"), "ОКОШКО ПРИЦЕЛА")
        _label(box.cols[0], _t("Крупное слово под иллюминатором (видно, когда включён UPLINK)."), fg=MUTED,
               size=8, wraplength=px(500), justify="left").pack(anchor="w")
        self._chips(box, "sight_box_font", _t("Размер слова"), [(k, font_label(k)) for k in ts.FONT_KEYS])
        self._chips(box, "sight_box_face", _t("Шрифт слова"), [(k, _t(v)) for k, v in FACE_LABELS])
        self._color(box, "sight_on_color", _t("Цвет текущей буквы"), RED)
        self.show_tab("ПРИЦЕЛ")
        self.refresh()

    HELP_IDS = {"ПРИЦЕЛ": "sight", "НАБОР": "typing", "ЦВЕТА": "colors", "ОКОШКО ПРИЦЕЛА": "box"}

    def page_help_key(self) -> str:
        return "bridge_settings." + self.HELP_IDS.get(getattr(self, "current_tab", ""), "sight")

    def tab_keys(self) -> list[str]:
        return list(self.tabs)

    def show_tab(self, name: str) -> None:
        self.current_tab = name
        tk.Misc.tkraise(self.tabs[name])
        for k, b in self.tab_btns.items():
            b.set_active(k == name)

    # -- построение ---------------------------------------------------------
    def _panel(self, _grid, title: str, key: str) -> tk.Misc:
        b = HudButton(self.tabbar, f"{_t(key)} · Alt+{len(self.tab_btns) + 1}", lambda k=key: self.show_tab(k),
                      height=30, font_size=9)
        b.pack(side=tk.LEFT, padx=px(3))
        b.nav_menu = True
        self.tab_btns[key] = b
        p = HudPanel(self.tab_host, title)
        p.grid(row=0, column=0, sticky="nsew")
        self.tabs[key] = p
        inner = tk.Frame(p.body, bg=PANEL)
        inner.pack(fill=tk.BOTH, expand=True)
        # две колонки — чтобы вкладка помещалась на экран без прокрутки
        inner.cols = [tk.Frame(inner, bg=PANEL), tk.Frame(inner, bg=PANEL)]
        inner.cols[0].pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, px(10)))
        inner.cols[1].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner.n = 0
        return inner

    def _row(self, parent, title: str, desc: str = "") -> tk.Frame:
        if hasattr(parent, "cols"):
            col = parent.cols[parent.n % 2]
            parent.n += 1
            parent = col
        _label(parent, title, size=10, bold=True).pack(anchor="w", pady=(px(6), 0))
        if desc:
            _label(parent, desc, fg=MUTED, size=8, wraplength=px(480), justify="left").pack(anchor="w")
        row = tk.Frame(parent, bg=PANEL)
        row.pack(anchor="w", pady=(px(2), px(4)))
        tk.Frame(parent, bg=LINE, height=1).pack(fill=tk.X)
        return row

    def _chips(self, parent, key: str, title: str, items) -> None:
        row = self._row(parent, title)
        btns = {}
        for val, lab in items:
            b = HudButton(row, lab, lambda v=val: self.set(key, v), height=28, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            btns[val] = b
        self.groups[key] = btns

    def _toggle(self, parent, key: str, title: str, desc: str) -> None:
        row = self._row(parent, title, desc)
        b = HudButton(row, _t("ВКЛ"), lambda: self.set(key, not self.app.store.settings.get(key, True)),
                      width=110, height=28)
        b.pack(side=tk.LEFT)
        self.toggles[key] = b

    def _color(self, parent, key: str, title: str, default: str) -> None:
        row = self._row(parent, title)
        sw = tk.Label(row, text="", width=4, bg=default, relief=tk.FLAT, cursor="hand2")
        sw.pack(side=tk.LEFT, ipady=px(4), padx=(0, px(6)))
        sw.bind("<Button-1>", lambda _e: self._pick(key, default))
        val = _label(row, default, fg=MUTED, size=9)
        val.pack(side=tk.LEFT, padx=(0, px(8)))
        HudButton(row, _t("ВЫБРАТЬ"), lambda: self._pick(key, default), height=28,
                  font_size=8).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("ИЗ СКИНА"), lambda: self.set(key, ""), height=28, font_size=8,
                  color=MUTED).pack(side=tk.LEFT, padx=px(2))
        self.swatches[key] = (sw, val, default)

    # -- действия -----------------------------------------------------------
    def _pick(self, key: str, default: str) -> None:
        cur = ts.color(self.app.store.settings, key, default)
        res = colorchooser.askcolor(color=cur, parent=self, title=_t("Цвет"))
        if res and res[1]:
            self.set(key, str(res[1]).upper())

    def set(self, key: str, value) -> None:
        self.app.store.settings[key] = value
        self.app.apply_settings()
        self.refresh()

    def reset_all(self) -> None:
        st = self.app.store.settings
        for k, v in ts.DEFAULTS.items():
            st[k] = v
        st.update({"font": "M", "cursor_blink": "on", "keyboard": True, "zones": True})
        self.app.apply_settings()
        self.refresh()

    def refresh(self) -> None:
        st = self.app.store.settings
        for key, btns in self.groups.items():
            cur = st.get(key, ts.DEFAULTS.get(key, ""))
            if key == "cursor_blink":
                cur = cur or "on"
            for v, b in btns.items():
                b.set_active(v == (cur or ""))
        for key, b in self.toggles.items():
            on = bool(st.get(key, True))
            b.set_text(_t("● ВКЛ") if on else _t("○ ВЫКЛ"))
            b.set_color(GREEN if on else MUTED)
            b.set_active(on)
        for key, (sw, val, default) in self.swatches.items():
            c = ts.color(st, key, default)
            sw.configure(bg=c)
            val.configure(text=c if st.get(key) else f"{c} · " + _t("скин"))
        self._update_preview()

    def _update_preview(self) -> None:
        st = self.app.store.settings
        self.preview.set_style(st)
        self.preview.set_blink(st.get("cursor_blink", "on"))
        self.preview.set_state(text=PREVIEW_TEXT, index=PREVIEW_INDEX, mode="run",
                               status=_t("ПРЕВЬЮ"), status_color=AMBER)
        self.preview_box.set_style(st)
        self.preview_box.set(direction="EN → RU", source=PREVIEW_TEXT, translation="быстрая бурая лиса прыгает через ленивую собаку",
                             word="fox", word_tr="лиса", word_cursor=0, status="✓", status_color=GREEN)
