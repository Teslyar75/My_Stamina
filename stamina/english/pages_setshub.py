"""НАБОРЫ: хаб с внутренними вкладками СТАНДАРТ · CEFR · ГЛАГОЛЫ · ИЗ КНИГИ.

Логика переходов: ОБЗОР → сектор-группа → сюда → набор → карточка → СКАНЕР/СКЛАД.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px

from . import cefr
from .pages_main import SetsPage
from .ui import L, Strip, Tile

TABS = [("std", "СТАНДАРТ"), ("cefr", "CEFR"), ("verbs", "ГЛАГОЛЫ"), ("book", "ИЗ КНИГИ")]


class SetsHubPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.current = "std"
        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X, padx=px(12), pady=(px(6), 0))
        self.tab_btns: dict[str, HudButton] = {}
        for key, title in TABS:
            b = HudButton(row, title, lambda k=key: self.show_tab(k), height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(2))
            self.tab_btns[key] = b
        self.hint = L(row, "", fg=MUTED, size=8, bg=BG)
        self.hint.pack(side=tk.RIGHT)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.pages: dict[str, tk.Frame] = {}
        self.standard = SetsPage(self._holder("std"), self.ctx)
        self.cefr = CefrPage(self._holder("cefr"), self.ctx)
        self.verbs = VerbsTab(self._holder("verbs"), self.ctx)
        self.book = BookTab(self._holder("book"), self.ctx)
        self.show_tab("std")

    def _holder(self, key: str) -> tk.Frame:
        f = tk.Frame(self.body, bg=BG)
        f.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = f
        return f

    # -- навигация -----------------------------------------------------------
    def show_tab(self, key: str) -> None:
        if key not in self.pages:
            return
        self.current = key
        self.pages[key].tkraise()
        for k, b in self.tab_btns.items():
            b.set_active(k == key)
        page = {"std": self.standard, "cefr": self.cefr, "verbs": self.verbs, "book": self.book}[key]
        if hasattr(page, "refresh"):
            page.refresh()
        self.hint.configure(text={
            "std": "частотные наборы: 1000 · 3000 · 10 000 · 20 000",
            "cefr": "уровни A1–C2 · у каждого слова пять примеров",
            "verbs": "три формы + примеры (готовится)",
            "book": "предложения из читаемой книги · RU → EN",
        }.get(key, ""))

    def open_set(self, sid: str, tab: str = "std") -> None:
        self.show_tab(tab)
        if tab == "std":
            self.standard.open_set(sid)

    def focus_standard(self) -> None:
        self.show_tab("std")

    def open_cefr(self, level: str = "A1") -> None:
        self.show_tab("cefr")
        self.cefr.select(level)

    def refresh(self) -> None:
        page = {"std": self.standard, "cefr": self.cefr, "verbs": self.verbs, "book": self.book}.get(self.current)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()


class CefrPage(tk.Frame):
    COLS, ROWS = 6, 3

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.level = "A1"
        self.page = 0
        self.items: list[dict] = []
        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        lev = HudPanel(self, "УРОВНИ · CEFR")
        lev.pack(fill=tk.X, padx=px(12), pady=px(4))
        row = tk.Frame(lev.body, bg=PANEL)
        row.pack(fill=tk.X)
        self.lv_btns: dict[str, HudButton] = {}
        have = set(cefr.available())
        for lv, title, _d in cefr.LEVELS:
            b = HudButton(row, lv if lv in have else f"{lv} ·", lambda l=lv: self.select(l),
                          height=28, font_size=9, width=64,
                          active=(lv == self.level), color=GREEN if lv in have else MUTED)
            b.pack(side=tk.LEFT, padx=px(2))
            self.lv_btns[lv] = b
        self.info = L(lev.body, "", fg=CYAN, size=9, bg=PANEL)
        self.info.pack(anchor="w", pady=(px(5), 0))
        self.credit = L(lev.body, "", fg=MUTED, size=8, bg=PANEL)
        self.credit.pack(anchor="w")
        self.gridf = tk.Frame(self, bg=BG)
        self.gridf.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))
        for c in range(self.COLS):
            self.gridf.grid_columnconfigure(c, weight=1, uniform="c")
        for r in range(self.ROWS):
            self.gridf.grid_rowconfigure(r, weight=1, uniform="r")
        self.empty = L(self, "", fg=AMBER, size=16, bold=True, bg=BG)
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))
        HudButton(bot, "◀", lambda: self.go(-1), width=44, height=30).pack(side=tk.LEFT)
        self.pg = L(bot, "", fg=TEXT, size=9, bold=True, mono=True, bg=BG)
        self.pg.pack(side=tk.LEFT, padx=px(8))
        HudButton(bot, "▶", lambda: self.go(1), width=44, height=30).pack(side=tk.LEFT)
        self.tip = L(bot, "", fg=AMBER, size=8, bg=BG)
        self.tip.pack(side=tk.LEFT, padx=px(14))
        HudButton(bot, "УЧИТЬ КАРТОЧКАМИ", self.learn, color=AMBER, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        HudButton(bot, "МИССИЯ ПО НАБОРУ", lambda: self.mission(), height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        self.tiles: list[Tile] = []

    # -- данные --------------------------------------------------------------
    def select(self, level: str) -> None:
        self.level = level
        self.page = 0
        for lv, b in self.lv_btns.items():
            b.set_active(lv == level)
        self.refresh()

    def _set_id(self) -> str:
        return cefr.SET_ID.get(self.level, "cefr-a1")

    def refresh(self) -> None:
        self.items = []
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        if self.level not in cefr.available():
            self.empty.configure(text=f"{cefr.LEVEL_TITLE.get(self.level, self.level)} — НАБОР ГОТОВИТСЯ")
            self.empty.pack(fill=tk.BOTH, expand=True)
            self.info.configure(text="Уровень появится после проверки A1")
            self.credit.configure(text="")
            self.pg.configure(text="")
            self.strip.set("CEFR", "Выбери доступный уровень", 0.0, "")
            return
        self.empty.pack_forget()
        cefr.merge_into(self.ctx.vocab, self.level)
        self.items = self.ctx.vocab.in_set(self._set_id())
        known = self.ctx.progress.known_or_learned([w["slug"] for w in self.items])
        n_sent = sum(len(self.ctx.vocab.sentences(w)) for w in self.items)
        data = cefr.load(self.level) or {}
        src = data.get("source") or {}
        self.info.configure(text=f"{data.get('name', self.level)} · слов {len(self.items)} · "
                                 f"примеров {n_sent} · знаю {known}/{len(self.items)}")
        self.credit.configure(text=f"Данные: {src.get('name', 'original')} · {src.get('license', 'CC BY-SA 4.0')}"
                                  + (" · пять предложений на слово" if self.items else ""))
        self.strip.set(f"CEFR · {self.level}", "Клик по слову — сканер. ⟳ — перевод. ✓ — знаю.",
                       known / max(1, len(self.items)), f"{known} / {len(self.items)}")
        self.render()

    def render(self) -> None:
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        per = self.COLS * self.ROWS
        pages = max(1, -(-len(self.items) // per))
        self.page = min(self.page, pages - 1)
        chunk = self.items[self.page * per:(self.page + 1) * per]
        for i, w in enumerate(chunk):
            t = Tile(self.gridf, self.ctx, w)
            t.grid(row=i // self.COLS, column=i % self.COLS, sticky="nsew", padx=px(3), pady=px(3))
            self.tiles.append(t)
        self.pg.configure(text=f"СТР. {self.page + 1} / {pages}")
        self.tip.configure(text=f"{len(self.items)} слов · {self.level}")

    def go(self, d: int) -> None:
        per = self.COLS * self.ROWS
        pages = max(1, -(-len(self.items) // per))
        self.page = max(0, min(pages - 1, self.page + d))
        self.render()

    # -- учение --------------------------------------------------------------
    def learn(self) -> None:
        ids = [w["slug"] for w in self.items]
        if not ids:
            self.ctx.status("В наборе пока нет слов", AMBER)
            return
        self.ctx.start_session("random", source="filtered", ids=ids)

    def mission(self) -> None:
        ids = [w["slug"] for w in self.items]
        if not ids:
            self.ctx.status("В наборе пока нет слов", AMBER)
            return
        self.ctx.start_session("speaking", source="filtered", ids=ids)


class VerbsTab(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        p = HudPanel(self, "НЕПРАВИЛЬНЫЕ ГЛАГОЛЫ")
        p.pack(fill=tk.BOTH, expand=True, padx=px(40), pady=px(12))
        b = p.body
        L(b, "ТРИ ФОРМЫ · ПРИМЕРЫ · СПРЯЖЕНИЕ", fg=CYAN, size=11, bold=True, bg=PANEL).pack(anchor="w")
        L(b, "Карточка глагола: base · past · past participle, по пять предложений на форму,\n"
             "плюс таблица спряжения по временам в УРОКАХ → СПРАВОЧНИК.\n\n"
             "Набор готовится на этапе 3: сначала A1-глаголы (go, come, see, eat…),\n"
             "затем остальные. Пока учи словарные наборы — они уже работают.",
          fg=TEXT, size=10, justify="left", bg=PANEL).pack(anchor="w", pady=px(10))
        HudButton(b, "К СТАНДАРТУ", lambda: self.ctx.pages["sets"].open_set("top-1000"),
                  color=AMBER, height=34).pack(anchor="w", pady=px(6))

    def refresh(self) -> None:
        pass


class BookTab(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        p = HudPanel(self, "ИЗ КНИГИ · ПРЕДЛОЖЕНИЯ")
        p.pack(fill=tk.BOTH, expand=True, padx=px(40), pady=px(12))
        self.info = L(p.body, "", fg=TEXT, size=11, justify="left", bg=PANEL, wraplength=px(760))
        self.info.pack(anchor="w", pady=px(8))
        row = tk.Frame(p.body, bg=PANEL)
        row.pack(anchor="w", pady=px(8))
        HudButton(row, "ОТКРЫТЬ РАЗДЕЛ", lambda: self.ctx.open_book_cards(), color=AMBER, height=34).pack(
            side=tk.LEFT, padx=px(3))
        HudButton(row, "СФОРМИРОВАТЬ", self._sync, color=CYAN, height=34).pack(side=tk.LEFT, padx=px(3))

    def _sync(self) -> None:
        try:
            from . import book_sentences as bs
            from stamina import library as libmod
            n_books, n_sents = bs.sync_all(self.ctx.progress, libmod.Library())
            self.ctx.status(f"Книг: {n_books} · предложений: {n_sents}", GREEN)
        except Exception as exc:  # noqa: BLE001
            self.ctx.status(f"Не удалось: {type(exc).__name__}", AMBER)
        self.refresh()

    def refresh(self) -> None:
        try:
            from . import book_sentences as bs
            books = bs.list_books(self.ctx.progress)
            ready = bs.count_ready(self.ctx.progress)
            due = bs.count_due(self.ctx.progress)
        except Exception:  # noqa: BLE001
            books, ready, due = [], 0, 0
        if not books:
            self.info.configure(text="Книга ещё не выбрана.\n"
                                     "Открой читалку, выбери книгу — предложения появятся здесь и на Обзоре.")
            return
        lines = [f"Книг в карточках: {len(books)} · готовых предложений: {ready} · к повторению: {due}", ""]
        for b in books[:6]:
            lines.append(f"· {b.get('title') or b.get('id')} — {b.get('ready', 0)}/{b.get('total', 0)} предл.")
        self.info.configure(text="\n".join(lines))
