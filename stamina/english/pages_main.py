"""Обзор (мостик), звёздные карты (наборы слов), сканер объекта (карточка слова)."""
from __future__ import annotations

from stamina.i18n import t as _t

import datetime as dt
import random
import tkinter as tk

from stamina import missions, theme
from stamina.hud import HudButton, HudPanel, Readouts, RingGauge, SegmentBar
from stamina.theme import (AMBER, BG, BG2, CYAN, CYAN_DIM, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL,
                           PANEL_HI, RED, TEXT, blend, chamfer, px)

from . import tasks
from .mic import MicPanel
from .textutil import score_sentence, verdict, word_forms
from .ui import DIFF_COLOR, TIPS, Bar, L, MatchReadout, ScrollFrame, Segments, Strip, Tile, chip, entry, target_missed
from .vocab import DIFF_RU, POS_FILTER, POS_SHORT, SETS

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}


# =============================================================================
# ОБЗОР
# =============================================================================

class SectorCard(tk.Canvas):
    def __init__(self, master, ctx, set_def) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, height=px(150), width=px(200), cursor="hand2")
        self.ctx, self.s = ctx, set_def
        self.hover = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._h(True))
        self.bind("<Leave>", lambda _e: self._h(False))
        self.bind("<Button-1>", lambda _e: self.ctx.pages["sets"].open_set(self.s[0]))

    def _h(self, v) -> None:
        self.hover = v
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        sid, lim, name, sub, code = self.s
        words = self.ctx.vocab.in_set(sid)
        total = len(words)
        known = self.ctx.progress.known_or_learned([x["slug"] for x in words])
        frac = known / total if total else 0
        col = GREEN if frac >= 1 else (AMBER if known else (CYAN if self.hover else LINE_HI))
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(12)), fill=PANEL_HI if self.hover else PANEL,
                            outline=col, width=2 if known else 1)
        self.create_text(px(12), px(14), text=code, anchor="w", fill=col if known else CYAN,
                         font=theme.font(9, True, mono=True))
        self.create_text(w - px(12), px(14), text=sub, anchor="e", fill=MUTED, font=theme.font(8, True))
        self.create_text(px(12), px(40), text=name, anchor="w", fill=TEXT, font=theme.font(13, True))
        status = _t("пройден") if frac >= 1 else (_t("в процессе") if known else _t("не начат"))
        self.create_text(px(12), px(62), text=_t("знаю {0} / {1} · {2}").format(known, total, status), anchor="w", fill=MUTED,
                         font=theme.font(8))
        rng = random.Random(sid)
        pts = [(px(14) + i * (w - px(28)) / 5, px(78) + rng.random() * px(30)) for i in range(6)]
        for a, b in zip(pts, pts[1:]):
            self.create_line(*a, *b, fill=blend(col, BG, 0.5))
        for x, y in pts:
            self.create_polygon(x, y - px(3), x + px(3), y, x, y + px(3), x - px(3), y, fill=col if known else CYAN_DIM)
        n, gap = 16, px(3)
        sw = (w - px(24) - gap * (n - 1)) / n
        filled = round(frac * n) if known == 0 else max(1, round(frac * n))
        for i in range(n):
            x1 = px(12) + i * (sw + gap)
            c = col if i < filled and known else None
            self.create_rectangle(x1, h - px(22), x1 + sw, h - px(12), fill=c or BG2, outline=c or LINE)


class OverviewPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        grid = tk.Frame(self, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(6))
        grid.grid_columnconfigure(0, weight=3)
        grid.grid_columnconfigure(1, weight=1, minsize=px(330))
        grid.grid_rowconfigure(1, weight=1)
        # курс на сегодня
        today = HudPanel(grid, _t("КУРС НА СЕГОДНЯ"), accent=AMBER)
        today.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)), pady=(0, px(6)))
        b = today.body
        self.ring = RingGauge(b, title=_t("ДНЕВНАЯ ЦЕЛЬ"))
        self.ring.pack(side=tk.LEFT)
        self.ro = Readouts(b, rows=3)
        self.ro.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(10))
        acts = tk.Frame(b, bg=PANEL)
        acts.pack(side=tk.LEFT, padx=px(6))
        HudButton(acts, _t("▶ НАЧАТЬ ЗАНЯТИЕ"), lambda: self.ctx.start_review(), color=AMBER, height=42,
                  font_size=11, width=230).pack(pady=px(4))
        HudButton(acts, _t("БЫСТРАЯ МИССИЯ · 10"), lambda: self.ctx.start_session("random", source="set"),
                  height=42, font_size=11, width=230).pack(pady=px(4))
        L(acts, _t("сначала проверка систем, потом новые слова"), fg=MUTED, size=8).pack()
        # секторы
        sec = tk.Frame(grid, bg=BG)
        sec.grid(row=1, column=0, sticky="nsew", padx=(0, px(6)))
        L(sec, _t("СЕКТОРЫ · НАБОРЫ СЛОВ ПО ЧАСТОТЕ"), fg=MUTED, size=9, bold=True, bg=BG).pack(anchor="w", pady=(px(2), px(4)))
        row = tk.Frame(sec, bg=BG)
        row.pack(fill=tk.X)
        self.cards = []
        for i, s in enumerate(SETS):
            c = SectorCard(row, ctx, s)
            c.grid(row=0, column=i, sticky="nsew", padx=px(3))
            row.grid_columnconfigure(i, weight=1, uniform="sec")
            self.cards.append(c)
        L(sec, _t("Голосвязь (видео с субтитрами) — позже.  Аудирование, диктант и письменная проверка не делаются."),
          fg=FAINT, size=8, bg=BG).pack(anchor="w", pady=(px(8), 0))
        # телеметрия
        tel = HudPanel(grid, _t("ТЕЛЕМЕТРИЯ ПИЛОТА"))
        tel.grid(row=0, column=1, sticky="nsew", pady=(0, px(6)))
        tb = tel.body
        top = tk.Frame(tb, bg=PANEL)
        top.pack(fill=tk.X)
        self.lvl = L(top, "1", fg=TEXT, size=28, bold=True, mono=True)
        self.lvl.pack(side=tk.LEFT, padx=(px(4), px(10)))
        info = tk.Frame(top, bg=PANEL)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lvl_txt = L(info, "", fg=MUTED, size=8, bold=True)
        self.lvl_txt.pack(anchor="w")
        self.lvl_bar = Bar(info, color=CYAN)
        self.lvl_bar.pack(fill=tk.X, pady=px(3))
        self.rank_txt = L(info, "", fg=AMBER, size=9, bold=True)
        self.rank_txt.pack(anchor="w")
        self.streak = Segments(tb, _t("СЕРИЯ · 14 ДНЕЙ"))
        self.streak.pack(fill=tk.X, pady=(px(8), 0))
        self.learned = SegmentBar(tb, _t("ВЫУЧЕНО В ТЕКУЩЕМ НАБОРЕ"), color=GREEN)
        self.learned.pack(fill=tk.X)
        # слово дня
        self.sig = HudPanel(grid, _t("ПЕРЕХВАЧЕН СИГНАЛ · СЛОВО ДНЯ"), accent=GREEN)
        self.sig.grid(row=1, column=1, sticky="nsew")
        sb = self.sig.body
        self.sig_meta = L(sb, "", fg=MUTED, size=8, mono=True)
        self.sig_meta.pack(anchor="w")
        wr = tk.Frame(sb, bg=PANEL)
        wr.pack(anchor="w", fill=tk.X)
        self.sig_word = L(wr, "", fg=TEXT, size=26, bold=True, mono=True)
        self.sig_word.pack(side=tk.LEFT)
        self.ctx.audio_button(wr, _t("🔊 ГОЛОС"), lambda: self.sig_word.cget("text"), height=32, font_size=9).pack(
            side=tk.LEFT, padx=px(8))
        self.sig_def = L(sb, "", fg=TEXT, size=10, wraplength=px(300), justify="left")
        self.sig_def.pack(anchor="w", pady=px(4))
        HudButton(sb, _t("СКАНИРОВАТЬ"), lambda: self.ctx.open_word(self._wod), height=32).pack(anchor="w", pady=px(4))
        self._wod = None

    def refresh(self) -> None:
        p, v = self.ctx.progress, self.ctx.vocab
        goal = p.settings["daily_goal"]
        xt = p.xp_today()
        self.ring.set(min(100.0, 100 * xt / goal) if goal else None, f"{xt} / {goal} XP")
        due = len(p.due_cards())
        cur = v.in_set(p.settings["current_set"])
        new_left = max(0, p.settings["new_per_day"] - p.new_today_count())
        avail = sum(1 for w in cur if not p.is_known(w["slug"]) and not p.has_card(w["slug"]))
        st = p.streak()
        self.ro.set([(_t("К ПОВТОРЕНИЮ"), str(due), CYAN), (_t("НОВЫХ ДОСТУПНО"), str(min(new_left, avail)), GREEN),
                     (_t("СЕРИЯ ДНЕЙ / ЛУЧШАЯ"), f"{st} / {max(st, p.data['xp'].get('best_streak', 0))}", AMBER)])
        for c in self.cards:
            c.redraw()
        lvl, lo, hi = p.level()
        self.lvl.configure(text=str(lvl))
        self.lvl_txt.configure(text=_t("УРОВЕНЬ · {0} XP · ДО {1}: {2} XP").format(p.xp_total, lvl + 1, hi - p.xp_total))
        self.lvl_bar.set((p.xp_total - lo) / max(1, hi - lo))
        try:
            xp = self.ctx.app.store.stats["xp"]
            rank, _lo, nxt = missions.rank_for(xp)
            self.rank_txt.configure(text=_t("★ {0} · общий XP Star Typing {1}").format(rank.upper(), xp) + (f" / {nxt}" if nxt else ""))
        except Exception:
            self.rank_txt.configure(text="")
        self.streak.set(p.day_flags(14), _t("{0} дн.").format(st))
        n = p.known_or_learned([w["slug"] for w in cur])
        self.learned.set(n / max(1, len(cur)), f"{n} / {len(cur)}")
        pool = [w for w in cur if not p.is_known(w["slug"])] or cur
        rnd = random.Random(dt.date.today().toordinal())
        w = rnd.choice(pool) if pool else None
        if w:
            self._wod = w["slug"]
            self.sig_meta.configure(text=f"#{w['rank']} · {POS_SHORT.get(w['pos'], w['pos'].upper())}")
            self.sig_word.configure(text=w["word"])
            self.sig_def.configure(text=w.get("definition", ""))


# =============================================================================
# ЗВЁЗДНЫЕ КАРТЫ (наборы слов)
# =============================================================================

class SetsPage(tk.Frame):
    COLS, ROWS = 6, 4

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.f = {"set": ctx.progress.settings["current_set"], "q": "", "status": "all", "len": "all",
                  "pos": "all", "diff": "all", "sort": "random", "seed": random.randint(1, 10 ** 6)}
        self.page = 0
        self.items: list[dict] = []
        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        fp = HudPanel(self, _t("ПАРАМЕТРЫ СКАНИРОВАНИЯ"))
        fp.pack(fill=tk.X, padx=px(12), pady=px(4))
        b = fp.body
        r1 = tk.Frame(b, bg=PANEL)
        r1.pack(fill=tk.X)
        self.btn_set = {}
        for sid, lim, name, sub, code in SETS:
            bt = HudButton(r1, code, lambda s=sid: self.open_set(s), height=28, font_size=9)
            bt.pack(side=tk.LEFT, padx=px(2))
            self.btn_set[sid] = bt
        L(r1, _t("   ПОИСК"), fg=MUTED, size=8, bold=True).pack(side=tk.LEFT)
        self.q = entry(r1, width=18, size=10)
        self.q.pack(side=tk.LEFT, padx=px(6), ipady=px(3))
        self.q.bind("<KeyRelease>", lambda _e: self._set("q", self.q.get()))
        self.count = L(r1, "", fg=CYAN, size=9, bold=True, mono=True)
        self.count.pack(side=tk.RIGHT)
        HudButton(r1, _t("✕ СБРОС"), self.reset, color=RED, height=28, font_size=8).pack(side=tk.RIGHT, padx=px(4))
        HudButton(r1, _t("⤨ ПЕРЕМЕШАТЬ"), self.shuffle, height=28, font_size=8).pack(side=tk.RIGHT, padx=px(4))
        r2 = tk.Frame(b, bg=PANEL)
        r2.pack(fill=tk.X, pady=(px(6), 0))
        self.groups: dict[str, dict] = {}
        self._group(r2, "status", _t("СТАТУС"), [("all", _t("ВСЕ")), ("known", _t("ЗНАЮ")), ("unknown", _t("НЕ ЗНАЮ")),
                                              ("review", _t("НА ПОВТОРЕНИИ"))])
        self._group(r2, "len", _t("ДЛИНА"), [("all", _t("ВСЕ")), ("short", "1–4"), ("mid", "5–7"), ("long", "8+")])
        self._group(r2, "diff", _t("СЛОЖНОСТЬ"), [("all", _t("ВСЕ")), ("easy", _t("ЛЁГК.")), ("medium", _t("СРЕД.")), ("tricky", _t("ТРУД."))])
        r3 = tk.Frame(b, bg=PANEL)
        r3.pack(fill=tk.X, pady=(px(6), 0))
        self._group(r3, "sort", _t("СОРТИРОВКА"), [("random", _t("СЛУЧАЙНО")), ("freq", _t("ЧАСТОТА")), ("alpha", "A→Z"),
                                               ("difficulty", _t("СЛОЖНОСТЬ"))])
        self._group(r3, "pos", _t("ЧАСТЬ РЕЧИ"), POS_FILTER)
        # сетка
        self.gridf = tk.Frame(self, bg=BG)
        self.gridf.pack(fill=tk.BOTH, expand=True, padx=px(10))
        for c in range(self.COLS):
            self.gridf.grid_columnconfigure(c, weight=1, uniform="t")
        for r in range(self.ROWS):
            self.gridf.grid_rowconfigure(r, weight=1, uniform="r")
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))
        HudButton(bot, "◀", lambda: self.go(-1), width=44, height=30).pack(side=tk.LEFT)
        self.pg = L(bot, "", fg=TEXT, size=9, bold=True, mono=True, bg=BG)
        self.pg.pack(side=tk.LEFT, padx=px(8))
        HudButton(bot, "▶", lambda: self.go(1), width=44, height=30).pack(side=tk.LEFT)
        self.tip = L(bot, "", fg=AMBER, size=8, bg=BG)
        self.tip.pack(side=tk.LEFT, padx=px(14))
        HudButton(bot, _t("МИССИЯ ПО НАБОРУ"), lambda: self.ctx.start_session("random", source="filtered",
                  ids=[w["slug"] for w in self.items]), height=30, font_size=9).pack(side=tk.RIGHT, padx=px(3))
        HudButton(bot, _t("УЧИТЬ КАРТОЧКАМИ"), self.learn_cards, color=AMBER, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        self.tiles: list[Tile] = []

    def _group(self, parent, key, title, options) -> None:
        L(parent, title, fg=MUTED, size=8, bold=True).pack(side=tk.LEFT, padx=(px(6), px(4)))
        btns = {}
        for val, text in options:
            bt = HudButton(parent, text, lambda v=val: self._set(key, v), height=26, font_size=8)
            bt.pack(side=tk.LEFT, padx=px(1))
            btns[val] = bt
        self.groups[key] = btns

    def _set(self, key, val) -> None:
        if self.f.get(key) == val and key != "q":
            return
        self.f[key] = val
        self.page = 0
        self.apply()

    def open_set(self, sid: str) -> None:
        self.f["set"] = sid
        self.ctx.progress.settings["current_set"] = sid
        self.ctx.progress.save()
        self.page = 0
        self.ctx.show("sets")

    def reset(self) -> None:
        self.f.update(q="", status="all", len="all", pos="all", diff="all", sort="random")
        self.q.delete(0, tk.END)
        self.page = 0
        self.apply()

    def shuffle(self) -> None:
        self.f["seed"] = random.randint(1, 10 ** 6)
        self.f["sort"] = "random"
        self.apply()

    def refresh(self) -> None:
        self.apply(keep_page=True)

    def apply(self, keep_page=False) -> None:
        f = self.f
        self.items = self.ctx.vocab.filtered(f["set"], query=f["q"], status=f["status"], length=f["len"], pos=f["pos"],
                                             diff=f["diff"], sort=f["sort"], seed=f["seed"], progress=self.ctx.progress)
        for sid, bt in self.btn_set.items():
            bt.set_active(sid == f["set"])
        for key, btns in self.groups.items():
            for val, bt in btns.items():
                bt.set_active(f[key] == val)
        name = next(s for s in SETS if s[0] == f["set"])
        words = self.ctx.vocab.in_set(f["set"])
        known = self.ctx.progress.known_or_learned([w["slug"] for w in words])
        self.strip.set(_t("СЕКТОР {0} · {1} · ЗВЁЗДНАЯ КАРТА").format(name[4], name[2].upper()),
                       _t("Клик по слову — сканер. ⟳ — перевернуть, ✓ — знаю, ⊞ — в отсек."),
                       known / max(1, len(words)), f"{known} / {len(words)} · {100 * known // max(1, len(words))}%")
        self.count.configure(text=_t("НАЙДЕНО: {0}").format(len(self.items)))
        self.render()

    def go(self, d: int) -> None:
        pages = max(1, -(-len(self.items) // (self.COLS * self.ROWS)))
        self.page = max(0, min(pages - 1, self.page + d))
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
        self.pg.configure(text=_t("СТР. {0} / {1}").format(self.page + 1, pages))
        self.tip.configure(text=_t("БОРТОВОЙ СОВЕТ: ") + TIPS[self.page % len(TIPS)])

    def learn_cards(self) -> None:
        p = self.ctx.progress
        fresh = [w["slug"] for w in self.items if not p.is_known(w["slug"]) and not p.has_card(w["slug"])]
        due = [w["slug"] for w in self.items if p.has_card(w["slug"]) and w["slug"] in set(p.due_cards())]
        self.ctx.start_review(due + fresh[: p.settings["new_per_day"]])

    def on_key(self, e) -> None:
        if e.keysym in ("Right", "Next"):
            self.go(1)
        elif e.keysym in ("Left", "Prior"):
            self.go(-1)


# =============================================================================
# СКАНЕР ОБЪЕКТА (карточка слова)
# =============================================================================

class ScannerPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.slug = None
        self.back = None
        self.si = 0
        self.ptab = "ipa"
        self.sf = ScrollFrame(self, bg=BG)
        self.sf.pack(fill=tk.BOTH, expand=True)
        root = self.sf.inner
        self.strip = Strip(root)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        nav = tk.Frame(root, bg=BG)
        nav.pack(fill=tk.X, padx=px(12))
        self.btn_back = HudButton(nav, _t("← НАЗАД"), self.go_back, height=28, font_size=8)
        self.btn_back.pack(side=tk.LEFT)
        HudButton(nav, _t("◀ ПРЕДЫДУЩЕЕ"), lambda: self.neighbor(-1), height=28, font_size=8).pack(side=tk.LEFT, padx=px(4))
        HudButton(nav, _t("СЛЕДУЮЩЕЕ ▶"), lambda: self.neighbor(1), height=28, font_size=8).pack(side=tk.LEFT)
        # окно сканера
        win = HudPanel(root, _t("ОКНО СКАНЕРА"))
        win.pack(fill=tk.X, padx=px(12), pady=px(4))
        wb = win.body
        self.rank = chip(wb, "", CYAN)
        self.rank.pack(pady=(px(2), px(4)))
        self.word = L(wb, "", fg=TEXT, size=36, bold=True, mono=True)
        self.word.pack()
        self.meta = tk.Frame(wb, bg=PANEL)
        self.meta.pack(pady=px(4))
        sens = tk.Frame(wb, bg=PANEL)
        sens.pack(pady=px(2))
        self.ctx.audio_button(sens, _t("🔊 ГОЛОС"), lambda: self._cur_word()["word"], height=30, font_size=9).pack(side=tk.LEFT, padx=px(3))
        self.ctx.audio_button(sens, _t("🐢 МЕДЛЕННО"), lambda: self._cur_word()["word"], slow=True, height=30, font_size=9).pack(side=tk.LEFT, padx=px(3))
        # две колонки
        cols = tk.Frame(root, bg=BG)
        cols.pack(fill=tk.X, padx=px(12))
        cols.grid_columnconfigure(0, weight=1, uniform="c")
        cols.grid_columnconfigure(1, weight=1, uniform="c")
        pr = HudPanel(cols, _t("АНАЛИЗ ПРОИЗНОШЕНИЯ"))
        pr.grid(row=0, column=0, sticky="nsew", padx=(0, px(4)))
        pb = pr.body
        self.resp = L(pb, "", fg=CYAN, size=22, bold=True, mono=True)
        self.resp.pack()
        self.pchips = tk.Frame(pb, bg=PANEL)
        self.pchips.pack(pady=px(2))
        tabs = tk.Frame(pb, bg=PANEL)
        tabs.pack(pady=px(4))
        self.ptabs = {}
        for key, title in (("ipa", "IPA"), ("syl", _t("СЛОГИ")), ("guide", _t("КАК ПРОИЗНОСИТЬ")), ("notes", _t("ЗАМЕТКИ"))):
            bt = HudButton(tabs, title, lambda k=key: self.set_ptab(k), height=26, font_size=8)
            bt.pack(side=tk.LEFT, padx=px(2))
            self.ptabs[key] = bt
        self.ptext = L(pb, "", fg=TEXT, size=11, wraplength=px(480), justify="left")
        self.ptext.pack(anchor="w", pady=px(4))
        da = HudPanel(cols, _t("ДАННЫЕ ОБЪЕКТА"))
        da.grid(row=0, column=1, sticky="nsew", padx=(px(4), 0))
        db = da.body
        self.defn = L(db, "", fg=TEXT, size=12, wraplength=px(480), justify="left")
        self.defn.pack(anchor="w")
        self.example = tk.Text(db, height=2, bg=PANEL, fg=MUTED, relief="flat", wrap="word", bd=0,
                               font=theme.font(10), highlightthickness=0, cursor="arrow")
        self.example.tag_configure("t", foreground=CYAN, font=theme.font(10, True))
        self.example.pack(fill=tk.X, pady=px(4))
        trr = tk.Frame(db, bg=PANEL)
        trr.pack(fill=tk.X, pady=px(2))
        L(trr, _t("МОЙ ПЕРЕВОД"), fg=MUTED, size=8, bold=True).pack(side=tk.LEFT)
        self.tr = entry(trr, width=26, size=11)
        self.tr.pack(side=tk.LEFT, padx=px(6), fill=tk.X, expand=True, ipady=px(3))
        self.tr.bind("<FocusOut>", lambda _e: self._save_tr())
        self.tr.bind("<Return>", lambda _e: (self._save_tr(), self.focus_set()))
        acts = tk.Frame(db, bg=PANEL)
        acts.pack(fill=tk.X, pady=px(6))
        self.btn_known = HudButton(acts, _t("✓ ЗНАЮ"), self.toggle_known, color=GREEN, height=30, font_size=9, width=120)
        self.btn_known.pack(side=tk.LEFT, padx=(0, px(4)))
        self.btn_list = HudButton(acts, _t("⊞ В ОТСЕК"), lambda: self.ctx.list_menu(self.btn_list, self.slug, None, self.refresh),
                                  height=30, font_size=9, width=150)
        self.btn_list.pack(side=tk.LEFT, padx=px(4))
        self.btn_card = HudButton(acts, _t("В ПРОВЕРКУ СИСТЕМ"), self.add_card, color=AMBER, height=30, font_size=9, width=190)
        self.btn_card.pack(side=tk.LEFT, padx=px(4))
        # миссии по слову
        mrow = tk.Frame(root, bg=BG)
        mrow.pack(pady=px(6))
        for mode, icon in (("random", "⤨"), ("speaking", "🎤"), ("reading", "▤"), ("questions", "?")):
            HudButton(mrow, f"{icon} {tasks.MODES[mode][0]}", lambda m=mode: self.ctx.start_session(m, single=self.slug),
                      height=32, font_size=9).pack(side=tk.LEFT, padx=px(4))
        # канал связи — практика предложений
        self.chan = HudPanel(root, _t("КАНАЛ СВЯЗИ · ПРАКТИКА ПРЕДЛОЖЕНИЙ"))
        self.chan.pack(fill=tk.X, padx=px(12), pady=(px(2), px(10)))
        cb = self.chan.body
        cb.grid_columnconfigure(0, weight=1)
        left = tk.Frame(cb, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew")
        self.snum = L(left, "", fg=MUTED, size=8, bold=True)
        self.snum.pack(anchor="w")
        self.sent = tk.Text(left, height=2, bg=PANEL, fg=TEXT, relief="flat", wrap="word", bd=0,
                            font=theme.font(18, False, True), highlightthickness=0, cursor="arrow")
        self.sent.tag_configure("t", foreground=CYAN, font=theme.font(18, True, True))
        self.sent.tag_configure("ok", foreground=GREEN)
        self.sent.tag_configure("bad", foreground=RED, underline=True)
        self.sent.pack(fill=tk.X)
        self.str_ = L(left, "", fg=MUTED, size=11, wraplength=px(700), justify="left")
        self.str_.pack(anchor="w")
        self.hint = L(left, "", fg=AMBER, size=9, wraplength=px(700), justify="left")
        self.hint.pack(anchor="w")
        sbtn = tk.Frame(left, bg=PANEL)
        sbtn.pack(anchor="w", pady=px(6))
        HudButton(sbtn, "◀", lambda: self.step_sent(-1), width=40, height=28).pack(side=tk.LEFT)
        HudButton(sbtn, "▶", lambda: self.step_sent(1), width=40, height=28).pack(side=tk.LEFT, padx=px(4))
        self.ctx.audio_button(sbtn, _t("🔊 ГОЛОС"), lambda: self._sent()["en"], height=28, font_size=8).pack(side=tk.LEFT, padx=px(4))
        self.ctx.audio_button(sbtn, _t("🐢 МЕДЛЕННО"), lambda: self._sent()["en"], slow=True, height=28, font_size=8).pack(side=tk.LEFT)
        HudButton(sbtn, _t("ПЕРЕВОД"), self.show_tr, height=28, font_size=8).pack(side=tk.LEFT, padx=px(4))
        HudButton(sbtn, _t("💡 ПОДСКАЗКА"), self.show_hint, height=28, font_size=8, color=AMBER).pack(side=tk.LEFT)
        self.result = L(left, "", fg=MUTED, size=11, bold=True)
        self.result.pack(anchor="w")
        self.match = MatchReadout(left)  # «СОВПАДЕНИЕ: 86%» + шкала + пропущенные слова
        self.match.pack(fill=tk.X, pady=(px(4), 0))
        self.mic = MicPanel(cb, ctx, self.on_speech)
        self.mic.grid(row=0, column=1, sticky="n", padx=px(10))

    # -- данные -------------------------------------------------------------------
    def _cur_word(self) -> dict:
        return self.ctx.vocab.get(self.slug) or {}

    def _sents(self) -> list[dict]:
        return self.ctx.vocab.sentences(self._cur_word())

    def _sent(self) -> dict:
        s = self._sents()
        return s[self.si % len(s)] if s else {"en": "", "ru": None}

    def set_word(self, slug: str, back=None) -> None:
        self._save_tr()
        self.slug = slug
        if back:
            self.back = back
        self.si = 0
        self.sf.top()

    def go_back(self) -> None:
        self.ctx.show(self.back or "sets")

    def neighbor(self, d: int) -> None:
        items = self.ctx.pages["sets"].items or self.ctx.vocab.in_set(self.ctx.progress.settings["current_set"])
        slugs = [w["slug"] for w in items]
        if self.slug in slugs:
            i = (slugs.index(self.slug) + d) % len(slugs)
        else:
            w = self._cur_word()
            i = 0
            if w:
                ranks = [x["rank"] for x in items]
                i = min(range(len(ranks)), key=lambda k: abs(ranks[k] - w["rank"] - d)) if ranks else 0
        if slugs:
            self.set_word(slugs[i])
            self.refresh()

    def refresh(self) -> None:
        if not self.slug:
            w = self.ctx.vocab.in_set(self.ctx.progress.settings["current_set"])
            if not w:
                return
            self.slug = w[0]["slug"]
        w, p = self._cur_word(), self.ctx.progress
        self.strip.set(_t("СКАНЕР ОБЪЕКТА · {0}").format(w['word'].upper()),
                       _t("Набор: {0} · частотность #{1}").format(w.get('level', ''), w['rank']))
        self.rank.configure(text=_t(" ЧАСТОТНОСТЬ #{0} ").format(w['rank']))
        self.word.configure(text=w["word"])
        for c in self.meta.winfo_children():
            c.destroy()
        L(self.meta, " · ".join(POS_SHORT.get(x, x.upper()) for x in (w.get("pos_all") or [w["pos"]])),
          fg=MUTED, size=9, bold=True).pack(side=tk.LEFT, padx=px(4))
        d = w.get("difficulty", "medium")
        chip(self.meta, DIFF_RU.get(d, d), DIFF_COLOR.get(d, CYAN)).pack(side=tk.LEFT, padx=px(2))
        for t in (w.get("tags") or [])[:4]:
            chip(self.meta, t, MUTED).pack(side=tk.LEFT, padx=px(2))
        self.resp.configure(text=f"[ {w['respelling']} ]" if w.get("respelling") else (w.get("ipa") or "—"))
        for c in self.pchips.winfo_children():
            c.destroy()
        if w.get("syllables"):
            chip(self.pchips, _t("{0} слог(а)").format(w['syllables']), MUTED).pack(side=tk.LEFT, padx=px(2))
        self.set_ptab(self.ptab)
        self.defn.configure(text=w.get("definition", ""))
        self._fill_text(self.example, f"“{w['example']}”" if w.get("example") else "", w["word"])
        self.tr.delete(0, tk.END)
        self.tr.insert(0, p.tr(self.slug))  # свой перевод или словарный
        known = p.is_known(self.slug)
        self.btn_known.set_text(_t("✓ ЗНАЮ") if known else _t("○ НЕ ЗНАЮ"))
        self.btn_known.set_active(known)
        self.btn_known.set_color(GREEN if known else MUTED)
        inl = p.lists_of(self.slug)
        self.btn_list.set_text(_t("⊞ В ОТСЕКАХ: {0}").format(len(inl)) if inl else _t("⊞ В ОТСЕК"))
        c = p.card(self.slug)
        if c and c.get("reps", 0) > 0:
            self.btn_card.set_text(_t("ПОВТОР {0}").format(c['due']))
        elif c:
            self.btn_card.set_text(_t("В ОЧЕРЕДИ ПРОВЕРКИ"))
        else:
            self.btn_card.set_text(_t("В ПРОВЕРКУ СИСТЕМ"))
        self.render_sentence()
        self.mic.reset()
        if p.settings.get("autoplay"):
            self.after(250, lambda: self.ctx.say(w["word"]))

    def set_ptab(self, key: str) -> None:
        self.ptab = key
        w = self._cur_word()
        txt = {
            "ipa": w.get("ipa") or _t("нет данных"),
            "syl": w.get("syllable_breakdown") or _t("нет данных"),
            "guide": (w.get("guide") or _t("нет данных")) + (_t("\nзвучит как: {0}").format(', '.join(w['sounds_like']))
                                                         if w.get("sounds_like") else ""),
            "notes": "\n".join(f"• {n}" for n in (w.get("notes") or [])) +
                     (_t("\nЧастые ошибки:\n") + "\n".join(f"• {n}" for n in w["common_mistakes"])
                      if w.get("common_mistakes") else "") or _t("нет данных"),
        }[key]
        self.ptext.configure(text=txt, font=theme.font(14 if key == "ipa" else 10, False, key in ("ipa", "syl")),
                             fg=CYAN if key in ("ipa", "syl") else TEXT)
        for k, bt in self.ptabs.items():
            bt.set_active(k == key)

    def _fill_text(self, widget: tk.Text, text: str, word: str, marks=None) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        forms = word_forms(word)
        import re
        for m in re.finditer(r"[A-Za-z']+", text):
            if m.group(0).lower() in forms:
                widget.tag_add("t", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        lines = max(1, int(widget.count("1.0", "end", "displaylines")[0]) if widget.winfo_ismapped() else
                    1 + len(text) // 60)
        widget.configure(height=min(4, lines), state="disabled")

    def render_sentence(self) -> None:
        s = self._sents()
        if not s:
            self.snum.configure(text=_t("ПРЕДЛОЖЕНИЙ ДЛЯ ЭТОГО СЛОВА НЕТ"))
            self._fill_text(self.sent, "", "")
            self.str_.configure(text="")
            self.hint.configure(text="")
            self.result.configure(text="")
            self.match.clear()
            return
        cur = self._sent()
        best = self.ctx.progress.data["speech_best"].get(f"{self.slug}:{self.si % len(s)}")
        self.snum.configure(text=_t("КАРТОЧКА ПРЕДЛОЖЕНИЯ {0:02d} / {1:02d}").format(self.si % len(s) + 1, len(s))
                                 + (_t("   · лучший результат {0}").format(best) if best is not None else ""))
        self._fill_text(self.sent, cur["en"], self._cur_word()["word"])
        self.str_.configure(text=cur.get("ru") or "" if self.ctx.progress.settings.get("show_tr") else "")
        self.hint.configure(text="")
        self.result.configure(text="")
        self.match.clear()

    def step_sent(self, d: int) -> None:
        self.si += d
        self.render_sentence()
        self.mic.reset()

    def show_tr(self) -> None:
        self.str_.configure(text=self._sent().get("ru") or _t("перевода нет"))

    def show_hint(self) -> None:
        s = self._sent()
        self.hint.configure(text=s.get("context_ru") or s.get("context") or
                            "\n".join(self._cur_word().get("notes") or []) or _t("подсказки нет"))

    def on_speech(self, alts, self_score) -> None:
        s = self._sent()
        if not s.get("en"):
            return
        w = self._cur_word()
        heard = ""
        if self_score is not None:
            score, marks = self_score, None
        else:
            if not alts:
                return
            res = [(score_sentence(s["en"], a, w["word"]), a) for a in alts]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        text, vk = verdict(score)
        self.result.configure(text="")
        self.match.set(score, marks, heard, bool(marks) and target_missed(marks, w["word"]),
                       self_rated=self_score is not None)
        self.after(50, lambda: self.sf.canvas.yview_moveto(1.0))  # итог виден без прокрутки
        if marks:
            self.sent.configure(state="normal")
            self.sent.delete("1.0", tk.END)
            for i, (tok, ok) in enumerate(marks):
                self.sent.insert(tk.END, ("" if i == 0 else " ") + tok, "ok" if ok else "bad")
            self.sent.configure(state="disabled")
        key = f"{self.slug}:{self.si % len(self._sents())}"
        best = self.ctx.progress.data["speech_best"]
        best[key] = max(best.get(key, 0), score)
        xp = 5 if score >= 85 else (3 if score >= 60 else 0)
        if xp and self.ctx.progress.award_once(f"sent:{key}:{dt.date.today().isoformat()}", xp):
            self.ctx.status(_t("Совпадение: {0}% · +{1} XP").format(score, xp), VCOL[vk])
        self.ctx.progress.record_attempt(self.slug, "speaking", "sentence", score >= 60,
                                         5 if score >= 85 else 4 if score >= 60 else 3 if score >= 40 else 2, score)
        self.ctx.sfx("click" if score >= 60 else "error")

    def toggle_known(self) -> None:
        p = self.ctx.progress
        p.set_known(self.slug, not p.is_known(self.slug))
        self.refresh()
        self.ctx.changed()

    def add_card(self) -> None:
        self.ctx.progress.add_card(self.slug)
        self.ctx.status(_t("«{0}» добавлено в проверку систем").format(self._cur_word()['word']), CYAN)
        self.refresh()
        self.ctx.changed()

    def _save_tr(self) -> None:
        if not self.slug:
            return
        p, text = self.ctx.progress, self.tr.get().strip()
        if text == p.my_tr(self.slug):
            return
        if not p.my_tr(self.slug) and text == (p.dict_tr(self.slug) or "").strip():
            return  # словарный перевод не трогали — не сохраняем как «свой»
        p.set_my_tr(self.slug, text)

    def on_key(self, e) -> None:
        k = e.keysym.lower()
        if k == "m":
            self.mic.toggle()
        elif k == "space":
            self.ctx.say(self._sent()["en"] or self._cur_word().get("word", ""))
        elif k == "right":
            self.step_sent(1)
        elif k == "left":
            self.step_sent(-1)
