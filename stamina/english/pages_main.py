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

from .speech_std import advance_later, passed
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
    """Сектор-группа на Обзоре: код, название, счётчик, мини-график и шкала."""

    def __init__(self, master, ctx, group: dict, compact: bool = False, height: int = 150) -> None:
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, height=px(height), width=px(200),
                         cursor="hand2")
        self.ctx, self.g = ctx, group
        self.compact = compact
        self.hover = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._h(True))
        self.bind("<Leave>", lambda _e: self._h(False))
        self.bind("<Button-1>", lambda _e: self.g["open"]())

    def _h(self, v) -> None:
        self.hover = v
        self.redraw()

    def redraw(self, fresh: bool = False) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        g = self.g
        st = None if fresh else getattr(self, "_stats", None)
        if st is None:
            try:
                st = self._stats = g["stats"]()
            except Exception:  # noqa: BLE001
                st = self._stats = (0, 0)
        total, known = st
        frac = known / total if total else 0
        col = GREEN if frac >= 1 and total else (AMBER if known else (CYAN if self.hover else LINE_HI))
        self.create_polygon(chamfer(1, 1, w - 2, h - 2, px(12)), fill=PANEL_HI if self.hover else PANEL,
                            outline=col, width=2 if known else 1)
        self.create_text(px(12), px(14), text=g["code"], anchor="w", fill=col if known else CYAN,
                         font=theme.font(9, True, mono=True))
        self.create_text(w - px(12), px(14), text=g["sub"], anchor="e", fill=MUTED, font=theme.font(8, True))
        name_y = px(40) if h >= px(120) else px(32)
        note_y = px(62) if h >= px(120) else px(54)
        self.create_text(px(12), name_y, text=g["name"], anchor="w", fill=TEXT, font=theme.font(13, True))
        note = g.get("note")() if callable(g.get("note")) else (g.get("note") or "")
        self.create_text(px(12), note_y, text=note, anchor="w", fill=MUTED, font=theme.font(8))
        if not self.compact:
            rng = random.Random(g["code"])
            pts = [(px(14) + i * (w - px(28)) / 5, px(78) + rng.random() * px(30)) for i in range(6)]
            for a, b in zip(pts, pts[1:]):
                self.create_line(*a, *b, fill=blend(col, BG, 0.5))
            for x, y in pts:
                self.create_polygon(x, y - px(3), x + px(3), y, x, y + px(3), x - px(3), y, fill=col if known else CYAN_DIM)
        n, gap = (12, px(2)) if self.compact else (16, px(3))
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
        # секторы + плашка книги
        left_col = tk.Frame(grid, bg=BG)
        left_col.grid(row=1, column=0, sticky="nsew", padx=(0, px(6)))
        left_col.grid_rowconfigure(1, weight=0)
        left_col.grid_columnconfigure(0, weight=1)
        self.left_col = left_col

        sec = tk.Frame(left_col, bg=BG)
        sec.pack(fill=tk.X)
        self.sec = sec
        L(sec, _t("СЕКТОРЫ · НАБОРЫ"), fg=MUTED, size=9, bold=True, bg=BG).pack(anchor="w", pady=(px(2), px(4)))
        row = tk.Frame(sec, bg=BG)
        row.pack(fill=tk.X)
        self.cards = []
        for i, g in enumerate(self._group_defs()):
            c = SectorCard(row, ctx, g)
            c.grid(row=0, column=i, sticky="nsew", padx=px(3))
            row.grid_columnconfigure(i, weight=1, uniform="sec")
            self.cards.append(c)

        # частотные наборы: те самые плашки 1000 / 3000 / 10 000 / 20 000,
        # каждая открывает свой набор в СТАНДАРТЕ (листание блоками по 24)
        L(sec, "ЧАСТОТНЫЕ НАБОРЫ · БЛОКИ ПО 24", fg=MUTED, size=9, bold=True, bg=BG).pack(
            anchor="w", pady=(px(10), px(4)))
        frow = tk.Frame(sec, bg=BG)
        frow.pack(fill=tk.X)
        self.freq_cards = []
        for i, (sid, lim, name, sub, code) in enumerate(SETS[:4]):
            def fstats(sid=sid):
                ws = ctx.vocab.in_set(sid)
                return len(ws), ctx.progress.known_or_learned([w["slug"] for w in ws])

            def fnote(sid=sid):
                ws = ctx.vocab.in_set(sid)
                return "знаю {0} / {1}".format(ctx.progress.known_or_learned([w["slug"] for w in ws]), len(ws))

            g = {"code": code, "name": name, "sub": sub, "stats": fstats, "note": fnote,
                 "open": lambda s=sid: self._open_set(s)}
            c = SectorCard(frow, ctx, g, compact=True, height=112)
            c.grid(row=0, column=i, sticky="nsew", padx=px(3))
            frow.grid_columnconfigure(i, weight=1, uniform="freq")
            self.freq_cards.append(c)

        # плашка: предложения из читаемой книги (под секторами)
        self.book_panel = HudPanel(left_col, _t("ИЗ ЧИТАЕМОЙ КНИГИ · ПРЕДЛОЖЕНИЯ"), accent=CYAN)
        self.book_panel.pack(fill=tk.X, pady=(px(10), 0))
        bb = self.book_panel.body
        book_row = tk.Frame(bb, bg=PANEL)
        book_row.pack(fill=tk.X)
        book_info = tk.Frame(book_row, bg=PANEL)
        book_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.book_title = L(book_info, _t("Книга не выбрана"), fg=TEXT, size=14, bold=True, bg=PANEL)
        self.book_title.pack(anchor="w")
        self.book_meta = L(book_info, "", fg=MUTED, size=9, bg=PANEL)
        self.book_meta.pack(anchor="w", pady=(px(2), 0))
        self.book_sample = L(book_info, "", fg=FAINT, size=9, bg=PANEL, wraplength=px(520), justify="left")
        self.book_sample.pack(anchor="w", pady=(px(4), 0))
        book_acts = tk.Frame(book_row, bg=PANEL)
        book_acts.pack(side=tk.RIGHT, padx=(px(8), 0))
        HudButton(book_acts, _t("СФОРМИРОВАТЬ"), self._sync_book_plate, color=CYAN, height=34,
                  font_size=9, width=150).pack(pady=px(2))
        HudButton(book_acts, _t("▶ ПРАКТИКА"), self._practice_book_plate, color=AMBER, height=34,
                  font_size=9, width=150).pack(pady=px(2))
        HudButton(book_acts, _t("ОТКРЫТЬ РАЗДЕЛ"), lambda: self.ctx.open_book_cards(self._book_tid),
                  height=30, font_size=8, width=150).pack(pady=px(2))
        self._book_tid: str | None = None

        self.footnote = L(left_col, _t("Голосвязь (видео с субтитрами) — позже.  Аудирование, диктант и письменная проверка не делаются."),
                           fg=FAINT, size=8, bg=BG)
        self.footnote.pack(anchor="w", pady=(px(6), 0))
        # высота левой колонки известна только после раскладки: подгоняем плашки,
        # чтобы и секторы, и частотные наборы влезали в окно без прокрутки
        self._fit_state: tuple | None = None
        left_col.bind("<Configure>", lambda _e: self._fit_cards(), add="+")

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

    def _group_defs(self) -> list[dict]:
        """Сектора-группы: CEFR, глаголы, книга. Частотные наборы — отдельными плашками ниже."""
        from . import book_sentences as bs, cefr as cefrmod, paths as en_paths
        p, v = self.ctx.progress, self.ctx.vocab

        def hub():
            return getattr(self.ctx, "pages", {}).get("sets")

        def cefr_stats():
            total = known = 0
            for lv in cefrmod.available():
                for w in cefrmod.prepared(lv):
                    total += 1
                    if p.is_known(w["slug"]) or p.is_learned(w["slug"]):
                        known += 1
            return total, known

        def cefr_note():
            lv = cefrmod.available()
            total, known = cefr_stats()
            return (_t("{0} ур. · {1} слов · знаю {2}").format(len(lv), total, known)
                    if total else _t("набор готовится"))

        def verbs_data() -> list[dict]:
            try:
                import json
                d = json.loads((en_paths.DATA_DIR / "irregular_verbs.json").read_text(encoding="utf-8"))
                return d.get("verbs") or []
            except (OSError, ValueError):
                return []

        def verb_stats():
            ws = verbs_data()
            return len(ws), sum(1 for w in ws if p.is_known("verb:" + str(w.get("verb", ""))))

        def verb_note():
            total, known = verb_stats()
            return _t("{0} глаголов · знаю {1}").format(total, known) if total else _t("готовится · этап 3")

        def book_stats():
            ready, due = bs.count_ready(p), bs.count_due(p)
            return ready, max(0, ready - due)

        def book_note():
            ready, due = bs.count_ready(p), bs.count_due(p)
            return _t("готово {0} · к повторению {1}").format(ready, due) if ready else _t("книга не выбрана")

        def open_group(key: str) -> None:
            h = hub()
            if h is None:
                return
            if key == "cefr":
                h.open_cefr("A1")
            else:
                h.show_tab(key)
                self.ctx.show("sets")

        return [
            {"code": "S-CEFR", "name": "A1 → C2", "sub": "CEFR",
             "stats": cefr_stats, "note": cefr_note, "open": lambda: open_group("cefr")},
            {"code": "S-VRB", "name": "Irregular", "sub": _t("ГЛАГОЛЫ"),
             "stats": verb_stats, "note": verb_note, "open": lambda: open_group("verbs")},
            {"code": "S-BOOK", "name": _t("Из книги"), "sub": _t("ПРЕДЛОЖЕНИЯ"),
             "stats": book_stats, "note": book_note, "open": lambda: open_group("book")},
        ]

    def _open_set(self, sid: str) -> None:
        """Плашка частотного набора: открыть СТАНДАРТ с этим набором."""
        hub = getattr(self.ctx, "pages", {}).get("sets")
        if hub is None:
            return
        hub.open_set(sid)

    def _fit_cards(self) -> None:
        """Подогнать высоту плашек под окно: обе группы карточек должны влезать целиком.

        На низком окне книга и примечание уезжают в НАБОРЫ/ИЗ КНИГИ, а карточки
        становятся компактнее — без прокрутки и обрезанных рядов.
        """
        try:
            avail = self.left_col.winfo_height()
        except tk.TclError:
            return
        if avail < px(60):
            return
        if avail >= px(560):
            gh, fh, book, foot = 150, 112, True, True
        elif avail >= px(470):
            gh, fh, book, foot = 128, 100, True, False
        elif avail >= px(330):
            gh, fh, book, foot = 128, 100, False, False
        else:
            gh, fh, book, foot = 108, 88, False, False
        state = (gh, fh, book, foot)
        if state == self._fit_state:
            return
        self._fit_state = state
        for c in self.cards:
            c.compact = gh < 145
            c.configure(height=px(gh))
        for c in self.freq_cards:
            c.compact = True
            c.configure(height=px(fh))
        if book:
            if not self.book_panel.winfo_manager():
                self.book_panel.pack(fill=tk.X, pady=(px(10), 0), after=self.sec)
        elif self.book_panel.winfo_manager():
            self.book_panel.pack_forget()
        if foot:
            if not self.footnote.winfo_manager():
                self.footnote.pack(anchor="w", pady=(px(6), 0))
        elif self.footnote.winfo_manager():
            self.footnote.pack_forget()
        self.after_idle(self._redraw_cards)

    def _redraw_cards(self) -> None:
        for c in self.cards + self.freq_cards:
            c.redraw(fresh=True)

    def _active_book_info(self) -> dict | None:
        """Текущая книга из библиотеки / уже синхронизированных карточек."""
        from . import book_sentences as bs
        try:
            from stamina import library as libmod
            lib = libmod.Library()
        except Exception:
            lib = None
        tid = None
        meta = None
        if lib is not None:
            tid = lib.index.get("active_reading")
            if tid:
                meta = lib.meta(tid)
            if not meta:
                # первая английская с позицией чтения
                for m in lib.all():
                    if (m.get("lang") or "").lower() not in ("", "en"):
                        continue
                    rw = int(m.get("positions", {}).get("reading", {}).get("word", 0) or 0)
                    if rw > 0:
                        tid, meta = m["id"], m
                        break
        books = {b["id"]: b for b in bs.list_books(self.ctx.progress)}
        if tid and tid in books:
            b = books[tid]
            return {**b, "meta_title": (meta or {}).get("title") or b["title"]}
        if tid and meta:
            return {
                "id": tid,
                "title": meta.get("title") or _t("Без названия"),
                "author": meta.get("author") or "",
                "word_pos": int(meta.get("positions", {}).get("reading", {}).get("word", 0) or 0),
                "total": 0, "ready": 0, "due": 0,
                "meta_title": meta.get("title") or _t("Без названия"),
            }
        # любая уже синхронизированная
        if books:
            b = max(books.values(), key=lambda x: (x["ready"], x["total"], x["word_pos"]))
            return {**b, "meta_title": b["title"]}
        return None

    def _refresh_book_plate(self) -> None:
        from . import book_sentences as bs
        info = self._active_book_info()
        self._book_tid = info["id"] if info else None
        if not info:
            self.book_title.configure(text=_t("Книга не выбрана"))
            self.book_meta.configure(
                text=_t("Откройте английскую книгу в СКОРОЧТЕНИИ и полистайте — затем «СФОРМИРОВАТЬ»."))
            self.book_sample.configure(text="")
            return
        title = info.get("meta_title") or info.get("title") or _t("Без названия")
        if info.get("author"):
            title = f"{title} — {info['author']}"
        self.book_title.configure(text=title)
        self.book_meta.configure(
            text=_t("предложений из прочитанного: {0} · с переводом: {1} · к повтору: {2} · позиция слова: {3}").format(
                info.get("total", 0), info.get("ready", 0), info.get("due", 0), info.get("word_pos", 0)))
        sample = ""
        for s in bs.ready_sentences(self.ctx.progress, info["id"])[:1]:
            ru = (s.get("ru") or "").strip()
            en = (s.get("en") or "").strip()
            sample = f"«{ru}»" if ru else f"«{en}»"
        if not sample and info.get("total"):
            sample = _t("Есть предложения без перевода — ждём UPLINK или нажмите «СФОРМИРОВАТЬ».")
        elif not sample:
            sample = _t("Пока пусто: нажмите «СФОРМИРОВАТЬ», чтобы собрать карточки из прочитанного.")
        self.book_sample.configure(text=sample)

    def _sync_book_plate(self) -> None:
        from . import book_sentences as bs
        try:
            from stamina import library as libmod
            lib = libmod.Library()
        except Exception:
            self.ctx.status(_t("Библиотека недоступна"), AMBER)
            return
        tid = self._book_tid
        if tid:
            book = bs.sync_book(self.ctx.progress, lib, tid)
            n = len((book or {}).get("sentences") or [])
        else:
            _bn, n = bs.sync_all(self.ctx.progress, lib)
        try:
            tr = self.ctx.app.get_translator()
        except Exception:
            tr = None
        tl = bs.uplink_tl(self.ctx.app)
        filled = bs.fill_ru_from_cache(self.ctx.progress, tr, tl)
        bs.request_missing_ru(self.ctx.progress, tr, tl)
        self.ctx.sfx("click")
        self.ctx.status(
            _t("Собрано {0} предложений из прочитанного").format(n) + (
                _t(" · переводов из кэша: {0}").format(filled) if filled else ""),
            GREEN if n else AMBER)
        self._refresh_book_plate()
        self.ctx.changed()

    def _practice_book_plate(self) -> None:
        self.ctx.open_book_cards(self._book_tid)

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
            c.redraw(fresh=True)
        for c in self.freq_cards:
            c.redraw(fresh=True)
        lvl, lo, hi = p.level()
        self.lvl.configure(text=str(lvl))
        self.lvl_txt.configure(text=_t("УРОВЕНЬ · {0} XP · ДО {1}: {2} XP").format(p.xp_total, lvl + 1, hi - p.xp_total))
        self.lvl_bar.set((p.xp_total - lo) / max(1, hi - lo))
        try:
            xp = self.ctx.app.store.stats["xp"]
            rank, _lo, nxt = missions.rank_for(xp)
            from stamina import theme as _th
            rank = _th.skin_rank(rank)
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
        self._refresh_book_plate()


# =============================================================================
# ЗВЁЗДНЫЕ КАРТЫ (наборы слов)
# =============================================================================

STRIP_HIDE_H = 420   # альт: высота области (до масштаба), ниже которой заголовок сектора скрыт


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
        r2._alt_toggle = r3._alt_toggle = True  # альт: ряды открываются кнопкой «ФИЛЬТРЫ ▾»
        self._frows = (r2, r3)          # альт: свёрнуты под кнопкой «ФИЛЬТРЫ», чтобы 24 карты влезли в окно
        self._fopen = False
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
        # альт-режим: плитки компактные, колонок столько, сколько влезает (как миссии мостика)
        self.gridf._alt_responsive = True
        self._ncols = self.COLS
        self.gridf.bind("<Configure>", self._reflow, add="+")
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))
        HudButton(bot, "◀ 24", lambda: self.go(-1), width=58, height=30).pack(side=tk.LEFT)
        self.pg = L(bot, "", fg=TEXT, size=9, bold=True, mono=True, bg=BG)
        self.pg.pack(side=tk.LEFT, padx=px(8))
        HudButton(bot, "24 ▶", lambda: self.go(1), width=58, height=30).pack(side=tk.LEFT)
        self.tip = L(bot, "", fg=AMBER, size=8, bg=BG)
        self.tip.pack(side=tk.LEFT, padx=px(14))
        HudButton(bot, _t("МИССИЯ ПО НАБОРУ"), lambda: self.ctx.start_session("random", source="filtered",
                  ids=[w["slug"] for w in self.items]), height=30, font_size=9).pack(side=tk.RIGHT, padx=px(3))
        HudButton(bot, _t("УЧИТЬ КАРТОЧКАМИ"), self.learn_cards, color=AMBER, height=30, font_size=9).pack(
            side=tk.RIGHT, padx=px(3))
        self.tiles: list[Tile] = []
        # --- альт-вид: лента карт с догрузкой по 24 (классика не затрагивается) ---
        self._bot = bot
        self.alt_grid = tk.Frame(self, bg=BG)
        self.alt_grid.bind("<Configure>", self._reflow, add="+")
        # кнопки альта — в той же нижней строке, что ◀ ▶ (одна строка, без лишней высоты)
        self._next_btn = bot.winfo_children()[2]
        self.btn_more = HudButton(bot, _t("ЕЩЁ 24"), self.load_more, color=AMBER, height=30, font_size=8)
        self.btn_all = HudButton(bot, _t("ВСЕ"), self.load_all, height=30, font_size=8)
        self.btn_rnd = HudButton(bot, _t("⤨ СЛУЧАЙНЫЕ 24"), self.random24, height=30, font_size=8)
        self.btn_flt = HudButton(bot, _t("ФИЛЬТРЫ ▾"), self.toggle_filters, height=30, font_size=8)
        self.shown_lbl = L(bot, "", fg=CYAN, size=8, bold=True, mono=True, bg=BG)
        self._alt_btns = (self.btn_more, self.btn_all, self.btn_rnd, self.btn_flt, self.shown_lbl)
        self._tile_h = 0
        self.shown = self.COLS * self.ROWS
        self._per = self.COLS * self.ROWS     # альт: карт на страницу — по высоте окна (12–24)
        self._alt_on = False
        self._busy = False
        self._arm = False      # автодогрузка — только после того, как пилот сам докрутил вниз
        # ←/→ листают блоки по 24, когда открыт СТАНДАРТ (в полях поиска не мешаем)
        self.bind_all("<Left>", self._key_page, add="+")
        self.bind_all("<Right>", self._key_page, add="+")

    def _key_page(self, event) -> None:
        if isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        hub = getattr(self.ctx, "pages", {}).get("sets")
        if getattr(self.ctx, "current", "") != "sets" or getattr(hub, "current", "std") != "std":
            return
        self.go(-1 if event.keysym == "Left" else 1)

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
        self.shown = self._page_size()
        self.apply()

    def open_set(self, sid: str) -> None:
        self.f["set"] = sid
        self.ctx.progress.settings["current_set"] = sid
        self.ctx.progress.save()
        self.page = 0
        hub = self.ctx.pages.get("sets")
        if hasattr(hub, "focus_standard"):
            hub.focus_standard()
        else:
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
        per = self._page_size()
        pages = max(1, -(-len(self.items) // per))
        self.page = max(0, min(pages - 1, self.page + d))
        self.shown = per
        self.render()

    def render(self) -> None:
        if self._alt():
            self._render_alt()
            return
        self._alt_layout(False)
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        per = self.COLS * self.ROWS
        pages = max(1, -(-len(self.items) // per))
        self.page = min(self.page, pages - 1)
        chunk = self.items[self.page * per:(self.page + 1) * per]
        for w in chunk:
            self.tiles.append(Tile(self.gridf, self.ctx, w))
        self._place()
        a = self.page * per + 1 if chunk else 0
        b = self.page * per + len(chunk)
        self.pg.configure(text="СТР. {0} / {1} · {2}–{3} из {4}".format(
            self.page + 1, pages, a, b, len(self.items)))
        self.tip.configure(text=_t("БОРТОВОЙ СОВЕТ: ") + TIPS[self.page % len(TIPS)])

    # ---------------------------------------------------------------- альт-вид
    # Та же логика групп, что в классике (◀ ▶ = страница по 24, page), плюс догрузка:
    # от начала выбранной группы показываются shown карт; «ЕЩЁ 24», «ВСЕ», колесо до
    # низа или End добавляют следующие 24. Фильтры/поиск работают по всему набору.
    def _alt_layout(self, on: bool) -> None:
        if on == self._alt_on:
            return
        self._alt_on = on
        if on:
            self.gridf.pack_forget()
            self._bot.pack_forget()
            # без растягивающегося пустого поля: сетка 24, сразу под ней строка управления
            self.alt_grid.pack(fill=tk.X, anchor="n", padx=px(10))
            self._bot.pack(fill=tk.X, anchor="n", padx=px(12), pady=(px(4), px(2)))
            self.tip.pack_forget()
            self._show_frows(self._fopen)
            prev = self._next_btn
            for wdg in self._alt_btns:
                wdg.pack(side=tk.LEFT, padx=px(3), after=prev)
                prev = wdg
            self.after(400, self._watch_bottom)
            vp = self._viewport()
            if vp is not None and not getattr(self, "_vp_bound", False):
                self._vp_bound = True      # смена высоты окна — пересчитать карт на страницу
                vp.canvas.bind("<Configure>", lambda _e: self._alt_on and self.after_idle(self._fit_tiles), add="+")
        else:
            self.alt_grid.pack_forget()
            for wdg in self._alt_btns:
                wdg.pack_forget()
            self.tip.pack(side=tk.LEFT, padx=px(14), after=self._next_btn)
            self._strip_show(True)
            self._show_frows(True)
            self._bot.pack_forget()
            self.gridf.pack(fill=tk.BOTH, expand=True, padx=px(10))
            self._bot.pack(fill=tk.X, padx=px(12), pady=(px(2), px(6)))

    def _show_frows(self, on: bool) -> None:
        for r in self._frows:
            if on and not r.winfo_manager():
                r.pack(fill=tk.X, pady=(px(6), 0))
            elif not on and r.winfo_manager():
                r.pack_forget()

    def toggle_filters(self) -> None:
        self._fopen = not self._fopen
        self._show_frows(self._fopen)
        self._tile_h = 0
        self.after_idle(self._fit_tiles)

    def _alt_tile(self, w: dict) -> Tile:
        t = Tile(self.alt_grid, self.ctx, w)
        if self._tile_h:
            t.configure(height=self._tile_h)
        return t

    def _strip_show(self, on: bool) -> None:
        if on and not self.strip.winfo_manager():
            first = next((c for c in self.pack_slaves() if c is not self.strip), None)
            self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0), before=first)
        elif not on and self.strip.winfo_manager():
            self.strip.pack_forget()

    def _page_size(self) -> int:
        """Карт на страницу: классика — всегда COLS×ROWS; альт — сколько влезает в окно."""
        return self._per if self._alt_on else self.COLS * self.ROWS

    def _alt_bounds(self) -> tuple[int, int]:
        start = self.page * self._per
        return start, min(len(self.items), start + self.shown)

    def _render_alt(self) -> None:
        self._alt_layout(True)
        for t in self.tiles:
            t.destroy()
        self.tiles = []
        per = self._per
        pages = max(1, -(-len(self.items) // per))
        self.page = min(self.page, pages - 1)
        a, b = self._alt_bounds()
        for w in self.items[a:b]:
            self.tiles.append(self._alt_tile(w))
        self._place()
        self._arm = False
        vp = self._viewport()
        if vp is not None:
            vp.canvas.yview_moveto(0)
        self.pg.configure(text=_t("ГРУППА {0} / {1}").format(self.page + 1, pages))
        self.tip.configure(text=_t("БОРТОВОЙ СОВЕТ: ") + TIPS[self.page % len(TIPS)])
        self._alt_status()

    def _alt_status(self) -> None:
        a, b = self._alt_bounds()
        n = len(self.items)
        self.shown_lbl.configure(text=_t("ПОКАЗАНО {0}–{1} ИЗ {2}").format(a + 1 if b > a else 0, b, n))
        self.btn_more.set_text(_t("ЕЩЁ {0}").format(self._per))
        self.btn_rnd.set_text(_t("⤨ СЛУЧАЙНЫЕ {0}").format(self._per))
        self.btn_more.set_enabled(b < n)
        self.btn_all.set_enabled(b < n)
        self.after_idle(self._fit_tiles)
        self._viewport_relayout()

    READ_H = 72     # альт: ниже этой высоты плитка нечитаема — тогда меньше карт на страницу

    def _fit_tiles(self) -> None:
        """Альт: сколько рядов читаемых плиток влезает в окно под шапкой и строкой управления —
        столько карт и на странице (12–24); высота плиток растягивается по остатку."""
        vp = self._viewport()
        if vp is None or not self.tiles or not self._alt_on:
            return
        try:
            self.update_idletasks()
            n = max(1, self._ncols)
            overhead = vp.required() - self.alt_grid.winfo_reqheight()
            pad = px(6)
            avail = vp.canvas.winfo_height() - overhead - 2
        except tk.TclError:
            return
        # низкое окно: заголовок сектора прячем (прогресс набора — в счётчике), карт больше
        short = vp.canvas.winfo_height() < px(STRIP_HIDE_H)
        if short == bool(self.strip.winfo_manager()):
            self._strip_show(not short)
            self.after_idle(self._fit_tiles)
            return
        full = self.COLS * self.ROWS
        rows_fit = max(1, (avail + pad) // (px(self.READ_H) + pad))
        per = max(n, min(full, rows_fit * n))
        if per >= full - n + 1:
            per = full
        if per != self._per:
            first = self.page * self._per       # сохранить первую видимую карту
            self._per = per
            self.page = first // per
            self.shown = per
            self._tile_h = 0
            self._render_alt()
            return
        rows = -(-min(len(self.tiles), per) // n)
        h = max(px(44), min(px(Tile.H), int(avail / max(1, rows)) - pad))
        if abs(h - (self._tile_h or 0)) <= 1:
            return
        self._tile_h = h
        for t in self.tiles:
            t.configure(height=h)
        self._place()
        self._viewport_relayout()

    def _viewport_relayout(self) -> None:
        vp = self._viewport()
        if vp is not None:
            self.after_idle(vp.relayout)

    def _viewport(self):
        w = self.master
        while w is not None:
            if hasattr(w, "relayout") and hasattr(w, "canvas"):
                return w
            w = w.master
        return None

    def load_more(self, n: int | None = None) -> None:
        """Догрузить следующие n (по умолчанию 24) карт, не пересоздавая показанные."""
        if not self._alt() or self._busy:
            return
        a, b = self._alt_bounds()
        if b >= len(self.items):
            return
        self._busy = True
        try:
            self.shown += n or self._per
            _a, nb = self._alt_bounds()
            for w in self.items[b:nb]:
                self.tiles.append(self._alt_tile(w))
            self._place()
            self._alt_status()
        finally:
            self.after(250, self._unbusy)

    def random24(self) -> None:
        """Новые случайные 24 из всего набора (с учётом фильтров) — логика ⤨ ПЕРЕМЕШАТЬ."""
        self.page = 0
        self.shown = self._per
        self.shuffle()

    def load_all(self) -> None:
        a, _b = self._alt_bounds()
        self.load_more(len(self.items) - a)

    def _unbusy(self) -> None:
        self._busy = False

    def _watch_bottom(self) -> None:
        """Пилот докрутил колесом/полосой до низа ленты — догрузить ещё 24."""
        if not self._alt_on:
            return
        try:
            vp = self._viewport()
            if vp is not None and self.winfo_ismapped() and vp.need > vp.canvas.winfo_height() + 1:
                at_bottom = vp.canvas.yview()[1] >= 0.995
                if at_bottom and self._arm:
                    self._arm = False
                    self.load_more()
                elif not at_bottom:
                    self._arm = True
        except tk.TclError:
            return
        self.after(400, self._watch_bottom)

    def _alt(self) -> bool:
        return getattr(self.winfo_toplevel(), "_alt_view", None) is not None

    def cols_for(self, width: int) -> int:
        """Сколько плиток в ряд: в классике — всегда COLS, в альт-режиме — по ширине."""
        if not self._alt() or width <= 1:
            return self.COLS
        return max(2, min(self.COLS, (width + px(6)) // px(int(Tile.W * 0.5) + 6)))

    def _reflow(self, e) -> None:
        n = self.cols_for(e.width)
        if n != self._ncols:
            self._ncols = n
            self._place()
            if self._alt_on:
                self._tile_h = 0
                self.after_idle(self._fit_tiles)

    def _place(self) -> None:
        """Разложить уже созданные плитки по сетке (без пересоздания — дёшево)."""
        n = self._ncols if self._alt() else self.COLS
        g = self.alt_grid if self._alt_on else self.gridf
        for c in range(self.COLS):
            g.grid_columnconfigure(c, weight=1 if c < n else 0, uniform="t" if c < n else "",
                                   minsize=0)
        if self._alt():
            rows = -(-len(self.tiles) // max(1, n)) if self._alt_on else -(-self.COLS * self.ROWS // 2)
            for r in range(rows):
                g.grid_rowconfigure(r, weight=0, uniform="",
                                    minsize=(self._tile_h or px(Tile.H)) if self._alt_on else px(Tile.H))
            if self._alt_on:     # лишние ряды от прошлой раскладки — без высоты
                for r in range(rows, max(rows, g.grid_size()[1], self.COLS * self.ROWS)):
                    g.grid_rowconfigure(r, minsize=0)
        for i, t in enumerate(self.tiles):
            t.grid(row=i // n, column=i % n, sticky="nsew", padx=px(3), pady=px(3))

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
        elif e.keysym == "End" and self._alt():
            self.load_more()


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
        self.ptext = L(pb, "", fg=TEXT, size=11, wraplength=px(420), justify="left")
        self.ptext.pack(anchor="w", pady=px(4))
        da = HudPanel(cols, _t("ДАННЫЕ ОБЪЕКТА"))
        da.grid(row=0, column=1, sticky="nsew", padx=(px(4), 0))
        db = da.body
        self.defn = L(db, "", fg=TEXT, size=12, wraplength=px(420), justify="left")
        self.defn.pack(anchor="w")
        self.example = tk.Text(db, height=2, bg=PANEL, fg=MUTED, relief="flat", wrap="word", bd=0,
                               font=theme.font(10), highlightthickness=0, cursor="arrow")
        self.example.tag_configure("t", foreground=CYAN, font=theme.font(10, True))
        self.example.pack(fill=tk.X, pady=px(4))
        trr = tk.Frame(db, bg=PANEL)
        trr.pack(fill=tk.X, pady=px(2))
        L(trr, _t("МОЙ ПЕРЕВОД"), fg=MUTED, size=8, bold=True).pack(side=tk.LEFT)
        self.tr = entry(trr, width=16, size=11)
        self.tr.pack(side=tk.LEFT, padx=px(6), fill=tk.X, expand=True, ipady=px(3))
        self.tr.bind("<FocusOut>", lambda _e: self._save_tr())
        self.tr.bind("<Return>", lambda _e: (self._save_tr(), self.focus_set()))
        acts = tk.Frame(db, bg=PANEL)
        acts.pack(fill=tk.X, pady=px(6))
        self.btn_known = HudButton(acts, _t("✓ ЗНАЮ"), self.toggle_known, color=GREEN, height=30, font_size=8)
        self.btn_known.pack(side=tk.LEFT, padx=(0, px(3)))
        self.btn_list = HudButton(acts, _t("⊞ В ОТСЕК"), lambda: self.ctx.list_menu(self.btn_list, self.slug, None, self.refresh),
                                  height=30, font_size=8)
        self.btn_list.pack(side=tk.LEFT, padx=px(3))
        self.btn_card = HudButton(acts, _t("В ПРОВЕРКУ"), self.add_card, color=AMBER, height=30, font_size=8)
        self.btn_card.pack(side=tk.LEFT, padx=(px(3), 0))
        # миссии по слову
        mrow = tk.Frame(root, bg=BG)
        mrow.pack(pady=px(6))
        for mode, icon in (("random", "⤨"), ("speaking", "🎤"), ("reading", "▤"), ("questions", "?")):
            HudButton(mrow, f"{icon} {tasks.MODES[mode][0]}",
                      lambda m=mode: self.ctx.start_session(m, single=self.slug),
                      height=32, font_size=9).pack(side=tk.LEFT, padx=px(4))
        # канал связи — практика предложений
        self.chan = HudPanel(root, _t("КАНАЛ СВЯЗИ · ПРАКТИКА ПРЕДЛОЖЕНИЙ"))
        self.chan.pack(fill=tk.X, padx=px(12), pady=(px(2), px(10)))
        self.chan._alt_nocompact = True   # альт: кнопки канала — в ряд, как в классике
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
        self.str_ = L(left, "", fg=MUTED, size=11, wraplength=px(560), justify="left")
        self.str_.pack(anchor="w")
        self.hint = L(left, "", fg=AMBER, size=9, wraplength=px(560), justify="left")
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
        root.bind("<Configure>", lambda _e: self._alt_unnest(), add="+")

    def _alt_unnest(self) -> None:
        """Альт: без вложенной прокрутки — канал связи виден целиком, листает внешний вьюпорт."""
        try:
            alt = bool(getattr(self.winfo_toplevel(), "_alt_view", None))
            if not alt:
                if self.sf.pack_info().get("expand") in (0, "0", False):
                    self.sf.pack_configure(fill=tk.BOTH, expand=True)
                if not self.sf.bar.winfo_manager():
                    self.sf.bar.pack(side=tk.RIGHT, fill=tk.Y)
                return
            if self.sf.bar.winfo_manager():
                self.sf.bar.pack_forget()
            if self.sf.pack_info().get("expand") not in (0, "0", False):
                self.sf.pack_configure(fill=tk.X, expand=False, anchor="n")
            h = self.sf.inner.winfo_reqheight()
            if getattr(self, "_unh", None) != h:
                self._unh = h
                self.sf.canvas.configure(height=h)
                self.sf.canvas.yview_moveto(0)
            self.chan.pack_configure(pady=(px(2), px(4)))
        except tk.TclError:
            pass

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
        self.btn_list.set_text(_t("⊞ {0}").format(len(inl)) if inl else _t("⊞ В ОТСЕК"))
        c = p.card(self.slug)
        if c and c.get("reps", 0) > 0:
            self.btn_card.set_text(_t("ПОВТОР {0}").format(c['due']))
        elif c:
            self.btn_card.set_text(_t("В ОЧЕРЕДИ"))
        else:
            self.btn_card.set_text(_t("В ПРОВЕРКУ"))
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
            level = self.ctx.progress.settings.get("speech_strictness", "normal")
            res = [(score_sentence(s["en"], a, w["word"], strictness=level), a) for a in alts]
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
        if passed(score) and len(self._sents()) > 1:
            here = (self.slug, self.si)
            advance_later(self, lambda: self.step_sent(1), lambda: (self.slug, self.si) == here)

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
        from .speech_std import is_mic_key
        if is_mic_key(e):
            self.mic.toggle()           # единый стандарт: M — микрофон
        elif k == "s":
            self.ctx.say(self._sent()["en"] or self._cur_word().get("word", ""))
        elif k == "right":
            self.step_sent(1)
        elif k == "left":
            self.step_sent(-1)
