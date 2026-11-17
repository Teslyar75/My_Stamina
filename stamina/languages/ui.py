"""Плитка слова в отсеке «Иностранные языки» — тот же вид, что Tile в английском.

Разница только в данных: вместо сложности easy/medium/tricky — уровень CEFR,
вместо готового словаря — WordEntry из базы языка. Ничего нового не рисуем:
цвета, шрифты и формы берём из stamina.theme (DESIGN.md).
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.i18n import t as _t
from stamina.theme import (AMBER, BG, CYAN, GREEN, LINE, LINE_HI, MUTED, PANEL, PANEL_HI,
                           RED, TEXT, blend, chamfer, px)

#: Плашка уровня: от «лёгкого» к «трудному».
LEVEL_COLOR = {"A1": GREEN, "A2": GREEN, "B1": CYAN, "B2": CYAN, "C1": AMBER, "C2": RED}

POS_SHORT = {
    "noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADV",
    "pronoun": "PRON", "preposition": "PREP", "conjunction": "CONJ",
    "interjection": "INT", "numeral": "NUM", "article": "ART", "particle": "PART",
}

W, H = 186, 112


def head_text(word, lang: str = "ru") -> str:
    """Слово с артиклем или родом, если язык их показывает (der Baum, el árbol)."""
    from stamina.languages.core.sqlite_vocab import word_line
    return word_line(word, lang).partition(" — ")[0]


def gloss_text(word, lang: str = "ru") -> str:
    """Перевод — то, что английская плитка прячет на обороте."""
    from stamina.languages.core.sqlite_vocab import glosses
    return ", ".join(glosses(word, lang))


def pos_short(word) -> str:
    pos = (getattr(word, "pos", "") or "").casefold()
    return POS_SHORT.get(pos, pos.upper())


def level_text(word) -> str:
    return (getattr(word, "cefr_level", "") or "").upper()


class WordTile(tk.Canvas):
    """Плитка слова: #ранг, слово, часть речи, уровень, ⟳, ✓ ЗНАЮ, ⊞ В ОТСЕКЕ."""

    W, H = W, H

    def __init__(self, master, word, *, is_known=None, in_lists=None, on_open=None,
                 on_known=None, on_list=None, on_menu=None, index: int = 0,
                 lang: str = "ru") -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0,
                         width=px(self.W), height=px(self.H), cursor="hand2")
        self.w = word
        self.index = index
        self.lang = lang
        self._is_known = is_known or (lambda _slug: False)
        self._in_lists = in_lists or (lambda _slug: False)
        self._on_open = on_open
        self._on_known = on_known
        self._on_list = on_list
        self._on_menu = on_menu
        self.flipped = False
        self.hover = False
        self.focused = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        self.bind("<Button-1>", self._click)
        self.bind("<Button-3>", self._menu)

    # -- состояние ---------------------------------------------------------
    def set_focus(self, on: bool) -> None:
        """Обводка AMBER для клавиатурного фокуса (вместо configure(highlight...))."""
        if self.focused == bool(on):
            return
        self.focused = bool(on)
        self.redraw()

    def _hover(self, value: bool) -> None:
        self.hover = value
        self.redraw()

    def _slug(self) -> str:
        return getattr(self.w, "slug", "")

    # -- клики -------------------------------------------------------------
    def _click(self, e) -> None:
        tags = {tag for item in self.find_overlapping(e.x, e.y, e.x, e.y)
                for tag in self.gettags(item)}
        if "flip" in tags:
            self.flipped = not self.flipped
            self.redraw()
            return
        if "known" in tags:
            if self._on_known:
                self._on_known(self._slug())
            return
        if "list" in tags:
            if self._on_list:
                self._on_list(self._slug(), e)
            return
        if self._on_open:
            self._on_open(self.w, self.index)

    def _menu(self, e) -> None:
        if self._on_menu:
            self._on_menu(e, self.w)

    # -- рисование ---------------------------------------------------------
    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        slug = self._slug()
        known = bool(self._is_known(slug))
        if self.focused:
            col = AMBER
        elif known:
            col = GREEN
        elif self.hover:
            col = CYAN
        else:
            col = LINE_HI
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(9)),
                            fill=PANEL_HI if self.hover else PANEL,
                            outline=col, width=2 if (known or self.focused) else 1)
        rank = int(getattr(self.w, "frequency_rank", 0) or 0)
        if rank:
            self.create_text(px(9), px(8), text=f"#{rank}", anchor="nw", fill=MUTED,
                             font=theme.font(8, True, mono=True))
        self.create_text(w - px(10), px(7), text="⟳", anchor="ne", fill=CYAN,
                         font=theme.font(11, True), tags="flip")
        head = head_text(self.w, self.lang)
        if self.flipped:
            back = gloss_text(self.w, self.lang) or head
            self.create_text(w / 2, px(52), text=back, width=w - px(18), fill=TEXT,
                             font=theme.font(9), justify="center", tags="flip")
        elif h < px(96):
            # низкая плитка (2-3 ряда): только слово
            self.create_text(w / 2, max(px(22), (h - px(28)) / 2 + px(6)), text=head, fill=TEXT,
                             font=theme.font(12 if h >= px(64) else 10, True))
        else:
            self.create_text(w / 2, px(40), text=head, fill=TEXT, font=theme.font(13, True),
                             width=w - px(14), justify="center")
            pos = pos_short(self.w)
            lvl = level_text(self.w)
            if pos or lvl:
                fg_level = LEVEL_COLOR.get(lvl, CYAN)
                half = px(4)
                t1 = None
                t2 = None
                if pos:
                    t1 = self.create_text(w / 2 - half, px(64), text=pos, anchor="e", fill=MUTED,
                                          font=theme.font(7, True))
                if lvl:
                    t2 = self.create_text(w / 2 + half, px(64), text=lvl, anchor="w",
                                          fill=fg_level, font=theme.font(7, True))
                for item, color in ((t1, MUTED), (t2, fg_level)):
                    if item is None:
                        continue
                    x1, y1, x2, y2 = self.bbox(item)
                    self.create_rectangle(x1 - px(4), y1 - px(1), x2 + px(4), y2 + px(1),
                                          outline=blend(color, BG, 0.4))
        by = h - px(28)
        self.create_line(px(8), by - px(4), w - px(8), by - px(4), fill=LINE)
        kc = GREEN if known else blend(MUTED, BG, 0.1)
        self.create_text(w * 0.28, by + px(10), text=_t("✓ ЗНАЮ") if known else _t("✓ знаю"),
                         fill=kc, font=theme.font(8, True), tags="known")
        in_list = bool(self._in_lists(slug))
        self.create_text(w * 0.72, by + px(10),
                         text=_t("⊞ В ОТСЕКЕ") if in_list else _t("⊞ В отсек"),
                         fill=AMBER if in_list else blend(MUTED, BG, 0.1),
                         font=theme.font(8, True), tags="list")
