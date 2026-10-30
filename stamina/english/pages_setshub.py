"""НАБОРЫ: хаб с внутренними вкладками СТАНДАРТ · CEFR · ГЛАГОЛЫ · ИЗ КНИГИ.

Логика переходов: ОБЗОР → сектор-группа → сюда → набор → карточка → СКАНЕР/СКЛАД.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px

from stamina.i18n import t as _t

from . import access, cefr, quality
from .pages_main import SetsPage
from .pages_verbs import VerbsTab
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
        self.standard = self._page("std", SetsPage)
        self.cefr = self._page("cefr", CefrPage)
        self.verbs = self._page("verbs", VerbsTab)
        self.book = self._page("book", BookTab)
        self.show_tab("std")

    def _page(self, key: str, cls) -> tk.Frame:
        """Кадр-держатель + сама страница, растянутая на весь кадр.

        Без pack() страница живёт невидимой: хаб показывал только вкладки и
        подсказку, а тело оставалось пустым.
        """
        holder = tk.Frame(self.body, bg=BG)
        holder.grid(row=0, column=0, sticky="nsew")
        page = cls(holder, self.ctx)
        page.pack(fill=tk.BOTH, expand=True)
        self.pages[key] = holder
        return page

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
            "verbs": "12 времён · примеры с переводом и проверкой речи",
            "book": "предложения из читаемой книги · RU → EN",
        }.get(key, ""))

    def open_set(self, sid: str, tab: str = "std") -> None:
        self.show_tab(tab)
        if tab == "std":
            self.standard.open_set(sid)
        self.ctx.show("sets")

    def focus_standard(self) -> None:
        self.show_tab("std")

    def open_cefr(self, level: str = "A1") -> None:
        self.show_tab("cefr")
        self.cefr.select(level)
        self.ctx.show("sets")

    def on_key(self, e) -> None:
        """Клавиши открытой вкладки (M — микрофон, T — подсказка, где она есть)."""
        page = {"std": self.standard, "cefr": self.cefr, "verbs": self.verbs, "book": self.book}.get(self.current)
        if page is not None and hasattr(page, "on_key"):
            page.on_key(e)

    def on_key_up(self, e) -> None:
        page = {"std": self.standard, "cefr": self.cefr, "verbs": self.verbs, "book": self.book}.get(self.current)
        if page is not None and hasattr(page, "on_key_up"):
            page.on_key_up(e)

    def refresh(self) -> None:
        page = {"std": self.standard, "cefr": self.cefr, "verbs": self.verbs, "book": self.book}.get(self.current)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()


class CefrPage(tk.Frame):
    COLS, ROWS = 6, 4          # страница = 24 карточки, как в СТАНДАРТЕ

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.level = "A1"
        self.page = 0
        self.block = 0
        self.max_open = 0
        self.rows = self.ROWS
        self.blocks: list[list[dict]] = []
        self.items: list[dict] = []
        self._reset_block = True
        self._done_counts: dict[str, int] = {}
        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        lev = HudPanel(self, "УРОВНИ · CEFR")
        lev.pack(fill=tk.X, padx=px(12), pady=px(4))
        row = tk.Frame(lev.body, bg=PANEL)
        row.pack(fill=tk.X)
        self.lv_btns: dict[str, HudButton] = {}
        for lv, title, _d in cefr.LEVELS:
            b = HudButton(row, lv, lambda l=lv: self.select(l),
                          height=28, font_size=9, width=66,
                          active=(lv == self.level), color=GREEN)
            b.pack(side=tk.LEFT, padx=px(2))
            self.lv_btns[lv] = b
        # порции уровня: 50 слов; следующая открывается сама, когда закрыта текущая
        self.block_row = tk.Frame(lev.body, bg=PANEL)
        self.block_row.pack(fill=tk.X, pady=(px(4), 0))
        self.block_btns: list[HudButton] = []
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
        # высоту задаёт окно: иначе четыре ряда плиток «просят» больше, чем есть,
        # и нижняя панель с листалкой уезжает за край на низком окне
        self.gridf.grid_propagate(False)
        self.bind("<Configure>", self._fit_rows)
        self.empty = L(self, "", fg=AMBER, size=16, bold=True, bg=BG)
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))
        HudButton(bot, "◀ 24", lambda: self.go(-1), width=58, height=30).pack(side=tk.LEFT)
        self.pg = L(bot, "", fg=TEXT, size=9, bold=True, mono=True, bg=BG)
        self.pg.pack(side=tk.LEFT, padx=px(8))
        HudButton(bot, "24 ▶", lambda: self.go(1), width=58, height=30).pack(side=tk.LEFT)
        self.tip = L(bot, "", fg=AMBER, size=8, bg=BG)
        self.tip.pack(side=tk.LEFT, padx=px(14))
        HudButton(bot, "УЧИТЬ КАРТОЧКАМИ", self.learn, color=AMBER, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        HudButton(bot, "МИССИЯ ПО НАБОРУ", lambda: self.mission(), height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        self.tiles: list[Tile] = []
        self._sync_level_buttons()
        # ←/→ листают страницы по 24, когда открыта вкладка CEFR
        self.bind_all("<Left>", self._key_page, add="+")
        self.bind_all("<Right>", self._key_page, add="+")

    def _key_page(self, event) -> None:
        if isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        hub = getattr(self.ctx, "pages", {}).get("sets")
        if getattr(self.ctx, "current", "") != "sets" or getattr(hub, "current", "") != "cefr":
            return
        self.go(-1 if event.keysym == "Left" else 1)

    def _fit_rows(self, event) -> None:
        """На низком окне меньше рядов, чтобы плитки не сжимались в полоску."""
        n = 4 if event.height >= 680 else (3 if event.height >= 480 else 2)
        if n != self.rows:
            self.rows = n
            for r in range(self.ROWS):
                self.gridf.grid_rowconfigure(
                    r, weight=1 if r < n else 0, uniform="r" if r < n else "")
            self.page = 0
            self.render()

    # -- прогресс ------------------------------------------------------------
    def _done(self, slug: str) -> bool:
        """Слово пройдено: качество закрыто или стоит ручная отметка."""
        p = self.ctx.progress
        return (p.is_known(slug) or p.is_learned(slug)
                or quality.is_complete(p, slug))

    def _block_done(self, words: list[dict]) -> bool:
        return bool(words) and all(self._done(w["slug"]) for w in words)

    def _frontier(self) -> int:
        """Первый незакрытый блок; если закрыто всё — последний."""
        for i, ws in enumerate(self.blocks):
            if not self._block_done(ws):
                return i
        return max(0, len(self.blocks) - 1)

    @staticmethod
    def _slugs(level: str) -> list[str]:
        return [w["slug"] for w in cefr.prepared(level)]

    def _captain(self) -> bool:
        return access.is_captain(self.ctx.progress)

    def _level_open(self, level: str) -> bool:
        """Правило в access.level_open: капитану всё, иначе ≥ N % предыдущего уровня."""
        return access.level_open(self.ctx.progress, level, cefr.available(),
                                 self._slugs, self._done)

    def _level_hint(self, level: str) -> str:
        prev, need, now = access.level_need(self.ctx.progress, level, cefr.available(),
                                            self._slugs, self._done)
        return _t("🔒 {0} откроется, когда пройдёшь {1}% уровня {2} (сейчас {3}%)").format(
            level, need, prev, now)

    def _level_complete(self, level: str) -> bool:
        ws = cefr.prepared(level)
        return bool(ws) and all(self._done(w["slug"]) for w in ws)

    def _sync_level_buttons(self) -> None:
        have = set(cefr.available())
        for lv, b in self.lv_btns.items():
            if lv not in have:
                b.set_text(f"{lv} ·")
                b.set_color(MUTED)
                b.set_enabled(False)
            elif not self._level_open(lv):
                b.set_text(f"🔒 {lv}")
                b.set_color(MUTED)
                b.set_enabled(True)
            else:
                b.set_text(lv)
                b.set_color(GREEN)
                b.set_enabled(True)
            b.set_active(lv == self.level)

    # -- данные --------------------------------------------------------------
    def select(self, level: str) -> None:
        if level not in cefr.available():
            self.level = level
            self.block = 0
            self.page = 0
            self._sync_level_buttons()
            self.refresh()
            return
        if not self._level_open(level):
            self.ctx.status(self._level_hint(level), AMBER)
            return
        if level != self.level:
            self.page = 0
        self.level = level
        self._reset_block = True
        self._sync_level_buttons()
        self.refresh()

    def _set_id(self) -> str:
        return cefr.SET_ID.get(self.level, "cefr-a1")

    def refresh(self) -> None:
        self.items = []
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        self.blocks = []
        self.max_open = 0
        self._sync_level_buttons()
        if self.level not in cefr.available():
            self._render_blocks()
            self.empty.configure(text=f"{cefr.LEVEL_TITLE.get(self.level, self.level)} — НАБОР ГОТОВИТСЯ")
            self.empty.pack(fill=tk.BOTH, expand=True)
            self.info.configure(text="Уровень появится после проверки A1")
            self.credit.configure(text="")
            self.pg.configure(text="")
            self.tip.configure(text="")
            self.strip.set("CEFR", "Выбери доступный уровень", 0.0, "")
            return
        self.empty.pack_forget()
        cefr.merge_into(self.ctx.vocab, self.level)
        words = self.ctx.vocab.in_set(self._set_id())
        self.blocks = [words[i:i + cefr.BLOCK_SIZE]
                       for i in range(0, len(words), cefr.BLOCK_SIZE)]
        self._front = self._frontier()
        # капитану открыты все порции; ученику — до первой незакрытой
        self.max_open = (max(0, len(self.blocks) - 1) if self._captain() else self._front)
        done_n = sum(1 for ws in self.blocks if self._block_done(ws))
        prev = self._done_counts.get(self.level)
        self._done_counts[self.level] = done_n
        if self._reset_block:
            self.block = self._front
            self._reset_block = False
        elif prev is not None and done_n > prev:
            if self._auto_next(done_n):
                return
        self.block = max(0, min(self.block, max(0, len(self.blocks) - 1)))
        self._render_blocks()
        self._update_texts()
        self.render()

    def _auto_next(self, done_n: int) -> bool:
        """Ученик закрыл порцию — сразу грузим следующую. True: сменили уровень."""
        if not self.blocks:
            return False
        if done_n < len(self.blocks):
            self.block = self._front
            self.ctx.status(f"Блок {done_n} пройден · открыт блок {done_n + 1}", GREEN)
            return False
        avail = cefr.available()
        i = avail.index(self.level) if self.level in avail else -1
        if 0 <= i < len(avail) - 1 and self._level_open(avail[i + 1]):
            nxt = avail[i + 1]
            self.ctx.status(f"Уровень {self.level} пройден · открыт {nxt}", GREEN)
            self.level = nxt
            self.block = 0
            self.page = 0
            self._reset_block = True
            self.refresh()
            return True
        self.ctx.status(f"Уровень {self.level} пройден", GREEN)
        return False

    def _render_blocks(self) -> None:
        for b in self.block_btns:
            b.destroy()
        self.block_btns = []
        for i, ws in enumerate(self.blocks):
            done = self._block_done(ws)
            open_ = i <= self.max_open
            label = str(i + 1) + (" ✓" if done else ("" if open_ else " закр"))
            b = HudButton(self.block_row, label, lambda n=i: self.pick_block(n),
                          height=24, font_size=8, width=58,
                          active=(i == self.block),
                          color=GREEN if done else (CYAN if open_ else MUTED))
            b.pack(side=tk.LEFT, padx=px(2))
            self.block_btns.append(b)

    def pick_block(self, n: int) -> None:
        if not self.blocks or n < 0 or n >= len(self.blocks):
            return
        if n > self.max_open:
            self.ctx.status(f"Блок {n + 1} откроется после блока {self.max_open + 1}", AMBER)
            return
        self.block = n
        self.page = 0
        self._render_blocks()
        self._update_texts()
        self.render()

    def _update_texts(self) -> None:
        self.items = self.blocks[self.block] if self.blocks else []
        known = sum(1 for w in self.items if self._done(w["slug"]))
        n_sent = sum(len(self.ctx.vocab.sentences(w)) for w in self.items)
        data = cefr.load(self.level) or {}
        src = data.get("source") or {}
        pos = self.block + 1
        total = max(1, len(self.blocks))
        self.info.configure(text=f"{data.get('name', self.level)} · блок {pos}/{total} · "
                                 f"слов {len(self.items)} · пройдено {known}/{len(self.items)} · "
                                 f"примеров {n_sent}")
        done_level = self._level_complete(self.level)
        extra = [s for k, s in (data.get("sources") or {}).items() if s is not src and s.get("name") != src.get("name")]
        credit = " · ".join(f"{s.get('name', 'unknown')} ({s.get('license', 'unknown')})" for s in [src] + extra)
        topics = sorted({w.get("topic") for w in self.items if w.get("topic")})
        self.credit.configure(text=f"Спасибо: {credit}"
                                  + (f" · темы: {', '.join(topics[:4])}" if topics else "")
                                  + (" · уровень пройден" if done_level else ""))
        self.strip.set(f"CEFR · {self.level} · блок {pos}",
                       "Клик по слову — сканер. ⟳ — перевод. ✓ — знаю.",
                       known / max(1, len(self.items)), f"{known} / {len(self.items)}")
        if done_level:
            avail = cefr.available()
            i = avail.index(self.level) if self.level in avail else -1
            nxt = avail[i + 1] if 0 <= i < len(avail) - 1 else ""
            self.tip.configure(text="УРОВЕНЬ ПРОЙДЕН" + (f" · дальше {nxt}" if nxt else ""))
        else:
            self.tip.configure(text=f"блок {pos} · {len(self.items)} слов · ← → по 24")

    def render(self) -> None:
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        per = self.COLS * self.rows
        pages = max(1, -(-len(self.items) // per))
        self.page = min(self.page, pages - 1)
        chunk = self.items[self.page * per:(self.page + 1) * per]
        for i, w in enumerate(chunk):
            t = Tile(self.gridf, self.ctx, w)
            t.grid(row=i // self.COLS, column=i % self.COLS, sticky="nsew", padx=px(3), pady=px(3))
            self.tiles.append(t)
        a = self.page * per + 1 if chunk else 0
        b = self.page * per + len(chunk)
        self.pg.configure(text="СТР. {0} / {1} · {2}–{3} из {4}".format(
            self.page + 1, pages, a, b, len(self.items)))

    def go(self, d: int) -> None:
        per = self.COLS * self.rows
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
