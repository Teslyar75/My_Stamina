"""Наборы слов в том же виде, что уровни CEFR в английском отсеке.

На экране один уровень и одна порция: 50 слов, страница плиток.
Клик по слову открывает сканер: произношение слова и его предложений.
Из базы берётся только эта порция, не весь словарь.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.languages.core.sqlite_vocab import PORTION, count_band, portion_slugs
from stamina.languages.ui import WordTile
from stamina.theme import AMBER, BG, CYAN, GREEN, PANEL, TEXT, px

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
COLS = 6
ROWS = 4


def level_set(plugin, level: str):
    tail = level.casefold()
    for freq in plugin.freq_sets:
        if freq.id.endswith(tail):
            return freq
    return None


class WordsPage(tk.Frame):
    """Уровни, номера порций и сетка слов. Клик по слову — сканер."""

    def __init__(self, master, plugin, progress, vocab, on_practice, app=None, level: str = "A1") -> None:
        super().__init__(master, bg=BG)
        self.plugin = plugin
        self.progress = progress
        self.vocab = vocab
        self.on_practice = on_practice
        self.app = app
        self.level = level if level in LEVELS else "A1"
        self.block = 0
        self.page = 0
        self.rows = ROWS
        self.slugs: list[str] = []
        self.words = []
        self._n_blocks = 0
        self.scanner = None
        self.focus_index = 0
        self._tiles: dict[int, WordTile] = {}

        self.lev = HudPanel(self, _t("УРОВНИ · CEFR"))
        self.lev.pack(fill=tk.X, padx=px(12), pady=px(4))
        self.level_row = tk.Frame(self.lev.body, bg=PANEL)
        self.level_row.pack(fill=tk.X)
        self.block_row = tk.Frame(self.lev.body, bg=PANEL)
        self.block_row.pack(fill=tk.X, pady=(px(4), 0))
        self.info = tk.Label(self.lev.body, text="", bg=PANEL, fg=CYAN, font=theme.font(9), anchor="w")
        self.info.pack(anchor="w", pady=(px(5), 0))

        self.gridf = tk.Frame(self, bg=BG)
        self.gridf.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        for col in range(COLS):
            self.gridf.grid_columnconfigure(col, weight=1, uniform="c")
        for row in range(ROWS):
            self.gridf.grid_rowconfigure(row, weight=1, uniform="r")
        self.gridf.grid_propagate(False)
        self.bind("<Configure>", self._fit_rows)

        self.empty = tk.Label(self, text="", bg=BG, fg=AMBER, font=theme.font(16, True))

        self.bot = tk.Frame(self, bg=BG)
        self.bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))
        HudButton(self.bot, "◀ 24", lambda: self.go(-1), width=58, height=30).pack(side=tk.LEFT)
        self.pg = tk.Label(self.bot, text="", bg=BG, fg=TEXT, font=theme.font(9, True))
        self.pg.pack(side=tk.LEFT, padx=px(8))
        HudButton(self.bot, "24 ▶", lambda: self.go(1), width=58, height=30).pack(side=tk.LEFT)
        self.tip = tk.Label(self.bot, text="", bg=BG, fg=AMBER, font=theme.font(8))
        self.tip.pack(side=tk.LEFT, padx=px(14))
        HudButton(self.bot, _t("УЧИТЬ КАРТОЧКАМИ"), self.learn, color=AMBER, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        HudButton(self.bot, _t("МИССИЯ ПО НАБОРУ"), self.mission, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        self.refresh()

    def _fit_rows(self, event) -> None:
        if self.scanner is not None:
            return
        n = 4 if event.height >= 680 else (3 if event.height >= 480 else 2)
        if n == self.rows:
            return
        self.rows = n
        for row in range(ROWS):
            self.gridf.grid_rowconfigure(row, weight=1 if row < n else 0, uniform="r" if row < n else "")
        self.page = 0
        self._render_grid()

    def select(self, level: str) -> None:
        if level == self.level:
            return
        self.level = level
        self.block = 0
        self.page = 0
        self.refresh()

    def pick_block(self, number: int) -> None:
        if number < 0 or number >= self._n_blocks:
            return
        self.block = number
        self.page = 0
        self.refresh()

    def go(self, step: int) -> None:
        per = COLS * self.rows
        pages = max(1, -(-len(self.words) // per))
        self.page = max(0, min(pages - 1, self.page + step))
        self._render_grid()

    def learn(self) -> None:
        self._start()

    def mission(self) -> None:
        self._start()

    def _start(self) -> None:
        if not self.slugs:
            self.tip.configure(text=_t("Нет слов в наборе"))
            return
        self.on_practice(list(self.slugs), f"{self.level} · блок {self.block + 1}")

    def _done(self, slug: str) -> bool:
        if self.progress is None:
            return False
        return self.progress.is_known(slug) or self.progress.is_learned(slug)

    def _toggle(self, slug: str) -> None:
        if self.progress is None:
            return
        self.progress.set_known(slug, not self.progress.is_known(slug))
        self.refresh()

    def open_scanner(self, word) -> None:
        from stamina.languages.scanner import WordScanner
        self._hide_board()
        if self.scanner is not None:
            self.scanner.shutdown()
            self.scanner.destroy()
        self.scanner = WordScanner(
            self, word, self.progress, self.plugin.code, self.app, self.close_scanner,
            neighbors=self.words,
        )
        self.scanner.pack(fill=tk.BOTH, expand=True)

    def close_scanner(self) -> None:
        if self.scanner is not None:
            self.scanner.destroy()
            self.scanner = None
        self._show_board()
        self.refresh()

    def _hide_board(self) -> None:
        for widget in (self.lev, self.gridf, self.empty, self.bot):
            if widget.winfo_manager():
                widget.pack_forget()

    def _show_board(self) -> None:
        self.lev.pack(fill=tk.X, padx=px(12), pady=px(4))
        self.gridf.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        self.bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))

    def refresh(self) -> None:
        if self.scanner is not None:
            return
        for child in self.level_row.winfo_children():
            child.destroy()
        for child in self.block_row.winfo_children():
            child.destroy()
        freq = level_set(self.plugin, self.level)
        for level in LEVELS:
            HudButton(
                self.level_row, level, lambda lv=level: self.select(lv),
                height=28, font_size=9, width=66,
                active=(level == self.level), color=GREEN,
            ).pack(side=tk.LEFT, padx=px(2))
        if freq is None:
            self._show_empty()
            return
        have = count_band(self.vocab, freq.id)
        learn_n = min(have, freq.size)
        self._n_blocks = (learn_n + PORTION - 1) // PORTION if learn_n else 0
        if not self._n_blocks:
            self._show_empty()
            return
        self.empty.pack_forget()
        self.block = max(0, min(self.block, self._n_blocks - 1))
        self._render_blocks()
        self.slugs = portion_slugs(self.vocab, freq.id, self.block, PORTION)
        self.words = []
        for slug in self.slugs:
            word = self.vocab.get_word(slug)
            if word is not None:
                self.words.append(word)
        known = sum(1 for word in self.words if self._done(word.slug))
        self.info.configure(text=_t("блок {0} из {1} · слов {2} · пройдено {3}").format(
            self.block + 1, self._n_blocks, len(self.words), known))
        self.tip.configure(text=_t("Клик по слову — сканер слова и фразы."))
        self._render_grid()

    def _show_empty(self) -> None:
        self.slugs = []
        self.words = []
        self._n_blocks = 0
        self.info.configure(text="")
        self.pg.configure(text="")
        self.tip.configure(text="")
        for child in self.gridf.winfo_children():
            child.destroy()
        self.empty.configure(text=_t("НАБОР ГОТОВИТСЯ"))
        self.empty.pack(fill=tk.BOTH, expand=True)

    def _render_blocks(self) -> None:
        if self._n_blocks > 16:
            start = (self.block // 12) * 12
            shown = range(start, min(self._n_blocks, start + 12))
            if start > 0:
                HudButton(self.block_row, "‹", lambda s=start: self.pick_block(s - 1),
                          height=24, font_size=8, width=36).pack(side=tk.LEFT, padx=px(2))
        else:
            shown = range(self._n_blocks)
        for number in shown:
            HudButton(
                self.block_row, str(number + 1), lambda n=number: self.pick_block(n),
                height=24, font_size=8, width=48,
                active=(number == self.block), color=CYAN,
            ).pack(side=tk.LEFT, padx=px(2))
        if self._n_blocks > 16 and (self.block // 12) * 12 + 12 < self._n_blocks:
            nxt = min(self._n_blocks - 1, ((self.block // 12) + 1) * 12)
            HudButton(self.block_row, "›", lambda n=nxt: self.pick_block(n),
                      height=24, font_size=8, width=36).pack(side=tk.LEFT, padx=px(2))

    def _render_grid(self) -> None:
        for child in self.gridf.winfo_children():
            child.destroy()
        self._tiles = {}
        per = COLS * self.rows
        pages = max(1, -(-len(self.words) // per)) if self.words else 1
        self.page = min(self.page, pages - 1)
        chunk = self.words[self.page * per:(self.page + 1) * per]
        if chunk:
            self.focus_index = min(self.focus_index, len(chunk) - 1)
        else:
            self.focus_index = 0
        for index, word in enumerate(chunk):
            tile = self._tile(word, index)
            tile.grid(row=index // COLS, column=index % COLS, sticky="nsew", padx=px(3), pady=px(3))
            self._tiles[index] = tile
        self._paint_focus()
        self.pg.configure(text=_t("СТР. {0} / {1}").format(self.page + 1, pages))

    def _paint_focus(self) -> None:
        """Обводку плитки держит она сама: AMBER — фокус, GREEN — выучено."""
        for index, tile in self._tiles.items():
            tile.set_focus(index == self.focus_index)

    def on_key(self, event) -> None:
        """Стрелки водят по плиткам, Enter — сканер, Space — «знаю»."""
        if self.scanner is not None:
            self.scanner.on_key(event)
            return
        if not self.words:
            return
        key = event.keysym
        per = COLS * self.rows
        if key == "Next":
            self.go(1)
            self.focus_index = 0
            return
        if key == "Prior":
            self.go(-1)
            self.focus_index = 0
            return
        total = len(self.words)
        idx = self.page * per + self.focus_index
        if key == "Right":
            idx += 1
        elif key == "Left":
            idx -= 1
        elif key == "Down":
            idx += COLS
        elif key == "Up":
            idx -= COLS
        elif key in ("Return", "KP_Enter"):
            chunk = self.words[self.page * per:(self.page + 1) * per]
            if self.focus_index < len(chunk):
                self.open_scanner(chunk[self.focus_index])
            return
        elif key == "space":
            chunk = self.words[self.page * per:(self.page + 1) * per]
            if self.focus_index < len(chunk):
                self._toggle(chunk[self.focus_index].slug)
            return
        else:
            return
        idx = max(0, min(total - 1, idx))
        self.page = idx // per
        self.focus_index = idx % per
        self._render_grid()

    def _tile(self, word, index: int = 0) -> WordTile:
        """Плитка как в английском отсеке: ранг, часть речи, уровень, оборот, отсеки."""
        return WordTile(
            self.gridf, word, index=index,
            is_known=self._done,
            in_lists=self._in_lists,
            on_open=lambda item, i: self._click_word(item, i),
            on_known=self._toggle,
            on_list=self._tile_list,
            on_menu=self._context_menu,
            lang=self._gloss_lang(),
        )

    def _gloss_lang(self) -> str:
        """Перевод на языке интерфейса (если пилот не выбрал другой в настройках)."""
        from stamina.languages.core.sqlite_vocab import gloss_lang
        return gloss_lang(self.progress.settings if self.progress else None)

    def _in_lists(self, slug: str) -> bool:
        if self.progress is None:
            return False
        try:
            return bool(self.progress.lists_of(slug))
        except Exception:  # noqa: BLE001 — прогресс мог не знать слова
            return False

    def _tile_list(self, slug: str, event) -> None:
        """Клик по «⊞ В ОТСЕКЕ» на лице плитки: быстро положить/убрать слово."""
        if self.progress is None:
            return
        menu = tk.Menu(self, tearoff=0)
        for item in self.progress.lists:
            inside = slug in item.get("slugs", [])
            menu.add_command(
                label=("✓ " if inside else "   ") + (item.get("name") or item.get("id", "")),
                command=lambda lid=item["id"]: self._toggle_list(lid, slug),
            )
        menu.add_separator()
        menu.add_command(label=_t("➕ НОВЫЙ ОТСЕК"), command=lambda: self._new_list_for(slug))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _click_word(self, word, index: int) -> None:
        self.focus_index = index
        self.open_scanner(word)

    def _context_menu(self, event, word) -> None:
        if self.progress is None:
            return
        menu = tk.Menu(self, tearoff=0)
        known = self.progress.is_known(word.slug)
        menu.add_command(label=_t("✓ ЗНАЮ") if known else _t("✓ ЗНАЮ · отметить"),
                         command=lambda: self._toggle(word.slug))
        menu.add_separator()
        for item in self.progress.lists:
            inside = word.slug in item.get("slugs", [])
            menu.add_command(
                label=("✓ " if inside else "   ") + (item.get("name") or item.get("id", "")),
                command=lambda lid=item["id"]: self._toggle_list(lid, word.slug),
            )
        menu.add_separator()
        menu.add_command(label=_t("➕ НОВЫЙ ОТСЕК"), command=lambda: self._new_list_for(word.slug))
        menu.add_command(label=_t("🎧 СКАНИРОВАТЬ"), command=lambda: self.open_scanner(word))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _toggle_list(self, lid: str, slug: str) -> None:
        if self.progress is None:
            return
        self.progress.toggle_in_list(lid, slug)
        self.refresh()

    def _new_list_for(self, slug: str) -> None:
        if self.progress is None:
            return
        name = simpledialog.askstring(_t("Новый отсек"), _t("Название отсека"),
                                      parent=self)
        if not name or not name.strip():
            return
        item = self.progress.create_list(name)
        self.progress.toggle_in_list(item["id"], slug)
        self.refresh()
