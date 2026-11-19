"""Отсек «ИНОСТРАННЫЕ ЯЗЫКИ» — селектор языков и под-страницы."""
from __future__ import annotations

from pathlib import Path

from stamina.i18n import t as _t

import tkinter as tk
import time

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, TEXT, px
from stamina.languages.core import get_registry, LanguageProgress
from stamina.languages.core.sqlite_vocab import word_line
from stamina.languages.migrate import migrate_english_progress
from stamina import pilots


SUBPAGES = [
    ("overview", _t("ОБЗОР")),
    ("sets", _t("НАБОРЫ")),
    ("practice", _t("МИССИИ")),
    ("reading", _t("ЧТЕНИЕ")),
    ("review", _t("ПРОВЕРКА")),
    ("warehouse", _t("СКЛАД")),
    ("book", _t("ИЗ КНИГИ")),
    ("log", _t("ЖУРНАЛ")),
    ("settings", _t("НАСТРОЙКИ")),
    ("grammar", _t("ГРАММАТИКА")),
]


class LanguagesScreen(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.registry = get_registry()
        self.registry.discover()
        self.current_lang: str | None = None
        self.current_page: str = "overview"
        self._pool_slugs: list[str] | None = None
        self._pool_title = ""
        self._practice_src = "set"
        self._practice_len: int | None = None
        self._scanner = None
        self._grammar_page = None
        self.pages: dict[str, tk.Frame] = {}
        self.lang_cards: list[dict] = []

        self._run_migration()
        self._build_ui()

    def _run_migration(self) -> None:
        try:
            pilot = pilots.active()
            if pilot:
                migrate_english_progress(pilots.pilot_dir(pilot["id"]))
        except Exception:
            pass

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(12), pady=(px(8), px(4)))

        tk.Label(top, text=_t("ИНОСТРАННЫЕ ЯЗЫКИ"), bg=BG, fg=AMBER,
                 font=theme.font(18, True)).pack(side=tk.LEFT)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(8))

        self._show_language_grid()

    def _show_language_grid(self) -> None:
        self._exit_grammar_focus(remember=False)
        self._grammar_page = None
        for w in self.content.winfo_children():
            w.destroy()

        from stamina.english.pages_main import SectorCard

        host = tk.Frame(self.content, bg=BG)
        host.pack(fill=tk.BOTH, expand=True, anchor="n")
        tk.Label(host, text=_t("СЕКТОРЫ · НАБОРЫ"), bg=BG, fg=MUTED,
                 font=theme.font(9, True), anchor="w").pack(anchor="w", pady=(px(2), px(4)))
        row = tk.Frame(host, bg=BG)
        row.pack(fill=tk.X, anchor="n")

        plugins = self.registry.all()
        pilot = pilots.active()
        pilot_dir = pilots.pilot_dir(pilot["id"]) if pilot else None
        self.lang_cards = []

        for i, plugin in enumerate(plugins):
            level = self._get_current_level(plugin.code, pilot_dir)
            locked = False
            note = _t("Уровень: {0}").format(level or _t("Начальный"))

            def _open(code=plugin.code, is_locked=locked):
                if not is_locked:
                    self._select_language(code)

            def _stats(is_locked=locked, started=bool(level)):
                return (1, 0 if is_locked or not started else 1)

            group = {
                "code": plugin.code.upper(),
                "name": plugin.name_target,
                "sub": plugin.name_native,
                "note": note,
                "stats": _stats,
                "open": _open,
            }
            card = SectorCard(row, self, group, compact=True, height=132)
            card.grid(row=0, column=i, sticky="ew", padx=px(3))
            row.grid_columnconfigure(i, weight=1, uniform="lang")
            self.lang_cards.append({"plugin": plugin, "locked": locked})

    def _get_current_level(self, lang: str, pilot_dir: Path | None) -> str | None:
        if not pilot_dir:
            return None
        prog_file = pilot_dir / f"lang_{lang}.json"
        if not prog_file.exists():
            return None
        try:
            import json
            data = json.loads(prog_file.read_text(encoding="utf-8"))
            xp = data.get("xp", {}).get("total", 0)
            if xp >= 5000:
                return "C2"
            elif xp >= 3000:
                return "C1"
            elif xp >= 1500:
                return "B2"
            elif xp >= 800:
                return "B1"
            elif xp >= 300:
                return "A2"
            elif xp > 0:
                return "A1"
            return "A1"
        except Exception:
            return None

    def _select_language(self, lang_code: str) -> None:
        self._exit_grammar_focus(remember=False)
        self._grammar_page = None
        if lang_code == "en":
            self.app.show("english")
            return
        self.current_lang = lang_code
        self._pool_slugs = None
        self._pool_title = ""
        plugin = self.registry.get(lang_code)
        if not plugin:
            return
        self._build_language_ui(plugin)

    def _build_language_ui(self, plugin) -> None:
        for w in self.content.winfo_children():
            w.destroy()

        top = tk.Frame(self.content, bg=BG)
        top.pack(fill=tk.X, pady=(0, px(8)))

        HudButton(top, _t("← ЯЗЫКИ"), self._show_language_grid,
                  color=MUTED, height=32, font_size=10).pack(side=tk.LEFT)

        tk.Label(top, text=f"{plugin.flag_emoji}  {plugin.name_target}",
                 bg=BG, fg=AMBER, font=theme.font(16, True)).pack(side=tk.LEFT, padx=px(12))

        pilot = pilots.active()
        pilot_dir = pilots.pilot_dir(pilot["id"]) if pilot else None
        level = self._get_current_level(plugin.code, pilot_dir)
        if level:
            tk.Label(top, text=_t("Текущий уровень: {0}").format(level),
                     bg=BG, fg=GREEN, font=theme.font(11)).pack(side=tk.LEFT, padx=px(8))

        tab_bar = tk.Frame(self.content, bg=BG)
        tab_bar.pack(fill=tk.X, pady=(0, px(4)))

        self.page_frames = {}
        for name, title in SUBPAGES:
            btn = HudButton(tab_bar, title, lambda n=name: self._show_page(n),
                          height=28, font_size=9)
            btn.pack(side=tk.LEFT, padx=px(2))

        self.page_container = tk.Frame(self.content, bg=BG)
        self.page_container.pack(fill=tk.BOTH, expand=True)

        self._show_page("overview")

    def _show_page(self, page_name: str, keep_pool: bool = False) -> None:
        self._exit_grammar_focus(remember=False)
        self._grammar_page = None
        self.current_page = page_name
        self._scanner = None
        if page_name == "practice" and not keep_pool:
            self._pool_slugs = None
            self._pool_title = ""
        for w in self.page_container.winfo_children():
            w.destroy()

        plugin = self.registry.get(self.current_lang)
        if not plugin:
            return

        pilot = pilots.active()
        pilot_dir = pilots.pilot_dir(pilot["id"]) if pilot else None
        progress = LanguageProgress(pilot_dir, self.current_lang) if pilot_dir else None
        vocab = plugin.load_vocab()

        if page_name == "overview":
            self._build_overview(plugin, progress, vocab)
        elif page_name == "sets":
            self._build_sets(plugin, progress, vocab)
        elif page_name == "practice":
            self._build_practice(plugin, progress, vocab)
        elif page_name == "reading":
            self._build_reading(plugin, progress, vocab)
        elif page_name == "review":
            self._build_review(plugin, progress, vocab)
        elif page_name == "warehouse":
            self._build_warehouse(plugin, progress, vocab)
        elif page_name == "book":
            self._build_book(plugin, progress, vocab)
        elif page_name == "log":
            self._build_log(plugin, progress, vocab)
        elif page_name == "settings":
            self._build_settings(plugin, progress)
        elif page_name == "grammar":
            self._build_grammar(plugin, progress, vocab)
            page = getattr(self, "_grammar_page", None)
            if page is not None and hasattr(page, "apply_session_focus"):
                try:
                    self.after_idle(page.apply_session_focus)
                except tk.TclError:
                    page.apply_session_focus()

    def _open_sets(self, level: str) -> None:
        self._sets_level = level
        self._show_page("sets")

    def _known_total(self, progress) -> int:
        if progress is None:
            return 0
        seen = set(progress.data.get("cards", {})) | set(progress.data.get("words", {}))
        return sum(1 for slug in seen if progress.is_known(slug) or progress.is_learned(slug))

    def _known_in_band(self, progress, vocab, band_id: str) -> int:
        if progress is None:
            return 0
        seen = set(progress.data.get("cards", {})) | set(progress.data.get("words", {}))
        n = 0
        for slug in seen:
            if not (progress.is_known(slug) or progress.is_learned(slug)):
                continue
            word = vocab.get_word(slug)
            if word is not None and word.frequency_band == band_id:
                n += 1
        return n

    def _study_words(self, plugin, vocab) -> list:
        """Первая порция A1: из неё берутся короткий урок и слово дня."""
        from stamina.languages.core.sqlite_vocab import PORTION, portion_slugs
        from stamina.languages.words_page import level_set
        freq = level_set(plugin, "A1")
        if freq is None:
            return []
        slugs = portion_slugs(vocab, freq.id, 0, min(freq.size, PORTION))
        out = []
        for slug in slugs:
            word = vocab.get_word(slug)
            if word is not None:
                out.append(word)
        return out

    def _glang(self) -> str:
        """Язык перевода в карточках: по умолчанию — язык интерфейса."""
        from stamina.languages.core.sqlite_vocab import gloss_lang
        progress = getattr(self, "_progress_ref", None)
        return gloss_lang(progress.settings if progress is not None else None)

    def _gloss(self, word) -> str:
        from stamina.languages.core.sqlite_vocab import glosses
        values = glosses(word, self._glang())
        return values[0] if values else _t("перевода нет")

    def _pick_lesson(self, plugin, progress, vocab, n: int) -> list[str]:
        import random
        words = self._study_words(plugin, vocab)
        unknown = [w for w in words if not (progress.is_known(w.slug) or progress.is_learned(w.slug))]
        pool = unknown or words
        if not pool:
            return []
        rng = random.Random()
        picked = rng.sample(pool, min(n, len(pool)))
        return [w.slug for w in picked]

    def _start_today(self, plugin, progress, vocab) -> None:
        due = progress.get_due_cards(list(progress.data.get("cards", {})), 200)
        fresh = self._pick_lesson(plugin, progress, vocab, int(progress.settings.get("new_per_day", 20)))
        have = set(due)
        slugs = due + [s for s in fresh if s not in have]
        if not slugs:
            slugs = self._pick_lesson(plugin, progress, vocab, int(progress.settings.get("session_len", 10)))
        self._start_portion(slugs, _t("▶ НАЧАТЬ ЗАНЯТИЕ"))

    def _start_quick(self, plugin, progress, vocab) -> None:
        n = int(progress.settings.get("session_len", 10))
        self._start_portion(self._pick_lesson(plugin, progress, vocab, n),
                            _t("БЫСТРАЯ МИССИЯ · {0}").format(n))

    def _scan_word(self, word, progress, lang: str) -> None:
        from stamina.languages.scanner import WordScanner
        for child in self.page_container.winfo_children():
            child.destroy()
        scanner = WordScanner(
            self.page_container, word, progress, lang, self.app,
            on_back=lambda: self._show_page("overview"),
        )
        self._scanner = scanner
        scanner.pack(fill=tk.BOTH, expand=True)

    def _build_overview(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(8))
        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED,
                     font=theme.font(12)).pack(expand=True)
            return

        import datetime as dt
        import random
        from stamina.english.pages_main import SectorCard
        from stamina.hud import Readouts, RingGauge
        from stamina.languages.core.sqlite_vocab import count_band
        from stamina.languages.speech import speak
        from stamina.languages.words_page import LEVELS, level_set

        grid = tk.Frame(frame, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.grid_columnconfigure(0, weight=3)
        grid.grid_columnconfigure(1, weight=1, minsize=px(330))
        grid.grid_rowconfigure(1, weight=1)

        today = HudPanel(grid, _t("КУРС НА СЕГОДНЯ"), accent=AMBER)
        today.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)), pady=(0, px(6)))
        body = today.body
        goal = int(progress.settings.get("daily_goal", 30)) or 30
        xt = int(progress.data.get("xp", {}).get("by_day", {}).get(dt.date.today().isoformat(), 0))
        ring = RingGauge(body, title=_t("ДНЕВНАЯ ЦЕЛЬ"))
        ring.pack(side=tk.LEFT)
        ring.set(min(100.0, 100 * xt / goal), f"{xt} / {goal} XP")
        words = self._study_words(plugin, vocab)
        unknown = [w for w in words if not (progress.is_known(w.slug) or progress.is_learned(w.slug))]
        due_n = len(progress.get_due_cards(list(progress.data.get("cards", {})), 200))
        new_n = min(int(progress.settings.get("new_per_day", 20)), len(unknown))
        streak = progress.current_streak()
        best = int(progress.data.get("xp", {}).get("best_streak", 0))
        ro = Readouts(body, rows=3)
        ro.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(10))
        ro.set([
            (_t("К ПОВТОРЕНИЮ"), str(due_n), CYAN),
            (_t("НОВЫХ ДОСТУПНО"), str(new_n), GREEN),
            (_t("СЕРИЯ ДНЕЙ / ЛУЧШАЯ"), f"{streak} / {max(streak, best)}", AMBER),
        ])
        acts = tk.Frame(body, bg=PANEL)
        acts.pack(side=tk.LEFT, padx=px(6))
        HudButton(acts, _t("▶ НАЧАТЬ ЗАНЯТИЕ"),
                  lambda: self._start_today(plugin, progress, vocab),
                  color=AMBER, height=42, font_size=11, width=230).pack(pady=px(4))
        HudButton(acts, _t("БЫСТРАЯ МИССИЯ · 10"),
                  lambda: self._start_quick(plugin, progress, vocab),
                  height=42, font_size=11, width=230).pack(pady=px(4))

        left = tk.Frame(grid, bg=BG)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, px(6)))
        tk.Label(left, text=_t("СЕКТОРЫ · НАБОРЫ"), bg=BG, fg=MUTED,
                 font=theme.font(9, True), anchor="w").pack(anchor="w", pady=(px(2), px(4)))
        row = tk.Frame(left, bg=BG)
        row.pack(fill=tk.X)
        shown = 0
        for level in LEVELS:
            freq = level_set(plugin, level)
            if freq is None:
                continue
            have = count_band(vocab, freq.id)
            total = min(have, freq.size) if have else freq.size
            known = self._known_in_band(progress, vocab, freq.id)
            code = freq.short_code

            def stats(t=total, k=known):
                return t, k

            def note(t=total, k=known, c=code):
                return _t("знаю {0} / {1} · {2}").format(k, t, c)

            def open_level(lv=level):
                self._open_sets(lv)

            group = {
                "code": code,
                "name": level,
                "sub": str(freq.size),
                "note": note,
                "stats": stats,
                "open": open_level,
            }
            card = SectorCard(row, self, group, compact=True, height=112)
            card.grid(row=0, column=shown, sticky="ew", padx=px(3))
            row.grid_columnconfigure(shown, weight=1, uniform="lvl")
            shown += 1

        tel = HudPanel(grid, _t("ТЕЛЕМЕТРИЯ ПИЛОТА"))
        tel.grid(row=0, column=1, sticky="nsew", pady=(0, px(6)))
        tb = tel.body
        for label, value, color in (
            (_t("Всего XP"), str(progress.data.get("xp", {}).get("total", 0)), CYAN),
            (_t("Серия дней"), str(streak), GREEN),
            (_t("Изучено слов"), str(self._known_total(progress)), AMBER),
        ):
            line = tk.Frame(tb, bg=PANEL)
            line.pack(fill=tk.X, pady=px(2))
            tk.Label(line, text=label, bg=PANEL, fg=MUTED, font=theme.font(8, True)).pack(side=tk.LEFT)
            tk.Label(line, text=value, bg=PANEL, fg=color, font=theme.font(14, True)).pack(side=tk.RIGHT)

        sig = HudPanel(grid, _t("ПЕРЕХВАЧЕН СИГНАЛ · СЛОВО ДНЯ"), accent=GREEN)
        sig.grid(row=1, column=1, sticky="nsew")
        sb = sig.body
        pool = unknown or words
        word = random.Random(dt.date.today().toordinal()).choice(pool) if pool else None
        if word is None:
            tk.Label(sb, text=_t("Нет слов в наборе"), bg=PANEL, fg=MUTED,
                     font=theme.font(11)).pack(anchor="w")
            return
        meta = f"#{word.frequency_rank or 0} · {(word.pos or '').upper()}"
        tk.Label(sb, text=meta, bg=PANEL, fg=MUTED, font=theme.font(8)).pack(anchor="w")
        wr = tk.Frame(sb, bg=PANEL)
        wr.pack(anchor="w", fill=tk.X)
        tk.Label(wr, text=word.lemma, bg=PANEL, fg=TEXT, font=theme.font(22, True)).pack(side=tk.LEFT)
        HudButton(wr, _t("🔊 ГОЛОС"), lambda w=word: speak(w.lemma, plugin.code),
                  height=32, font_size=9).pack(side=tk.LEFT, padx=px(8))
        tk.Label(sb, text=self._gloss(word), bg=PANEL, fg=TEXT, font=theme.font(10),
                 wraplength=px(300), justify="left").pack(anchor="w", pady=px(4))
        HudButton(sb, _t("СКАНИРОВАТЬ"),
                  lambda w=word: self._scan_word(w, progress, plugin.code),
                  height=32).pack(anchor="w", pady=px(4))

    def _pool(self, plugin, vocab) -> list[str]:
        if self._pool_slugs:
            return list(self._pool_slugs)
        from stamina.languages.core.sqlite_vocab import portion_slugs
        freq = next((item for item in plugin.freq_sets if item.id.endswith("a1")), None)
        if freq is None:
            return []
        return portion_slugs(vocab, freq.id, 0, 50)

    def _scroller(self, parent) -> tk.Frame:
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(parent, command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _fit(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window, width=max(canvas.winfo_width(), 1))

        inner.bind("<Configure>", _fit)
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        return inner

    def _build_sets(self, plugin, progress, vocab) -> None:
        from stamina.languages.words_page import WordsPage
        level = getattr(self, "_sets_level", None) or "A1"
        self._sets_level = None
        page = WordsPage(
            self.page_container, plugin, progress, vocab,
            on_practice=self._start_portion, app=self.app, level=level,
        )
        page.pack(fill=tk.BOTH, expand=True)

    def _start_portion(self, slugs: list[str], title: str) -> None:
        self._pool_slugs = list(slugs)
        self._pool_title = title
        self._practice_src = "set"
        self._show_page("practice", keep_pool=True)

    def _build_reading(self, plugin, progress, vocab) -> None:
        if not progress:
            tk.Label(self.page_container, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED,
                     font=theme.font(12)).pack(expand=True)
            return
        from stamina.languages.reading_page import ReadingPage
        page = ReadingPage(
            self.page_container, plugin, progress, vocab, self.app,
            on_back=lambda: self._show_page("overview"),
        )
        page.pack(fill=tk.BOTH, expand=True)

    def on_key(self, event) -> None:
        """Клавиши отсека: сканер и текущая страница сами решают, что делать."""
        page = getattr(self, "_grammar_page", None)
        if getattr(self, "current_page", None) == "grammar" and page is not None:
            if page.on_key(event) == "break":
                return
        if isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        if self._scanner is not None:
            self._scanner.on_key(event)
            return
        if getattr(self, "current_page", None) == "grammar":
            return
        for child in self.page_container.winfo_children():
            handler = getattr(child, "on_key", None)
            if callable(handler):
                handler(event)
                return

    def _exit_grammar_focus(self, *, remember: bool = False) -> None:
        page = getattr(self, "_grammar_page", None)
        if page is not None and page.in_focus():
            page.toggle_focus(False, remember=remember)

    def focus_active(self) -> bool:
        page = getattr(self, "_grammar_page", None)
        return bool(getattr(self, "current_page", None) == "grammar"
                    and page is not None and page.in_focus())

    def toggle_focus(self, on: bool | None = None, *, remember: bool = True) -> None:
        page = getattr(self, "_grammar_page", None)
        if page is not None:
            page.toggle_focus(on, remember=remember)

    def handle_focus_escape(self) -> bool:
        page = getattr(self, "_grammar_page", None)
        if page is not None:
            return page.handle_focus_escape()
        return False

    def on_leave(self) -> None:
        self._exit_grammar_focus(remember=False)

    def _open_set(self, set_id: str, vocab, progress) -> None:
        plugin = self.registry.get(self.current_lang)
        if not plugin:
            return
        chosen = next((fs for fs in plugin.freq_sets if fs.id == set_id), None)
        if chosen is None:
            return
        slugs = vocab.get_slugs_by_freq_band(set_id)[:chosen.size]
        self._pool_slugs = slugs
        for child in self.page_container.winfo_children():
            child.destroy()
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        top = tk.Frame(frame, bg=BG)
        top.pack(fill=tk.X)
        HudButton(top, _t("НАЗАД"), lambda: self._show_page("sets"),
                  color=MUTED, height=28, font_size=10).pack(side=tk.LEFT)
        HudButton(top, _t("В МИССИИ"), lambda: self._show_page("practice", keep_pool=True),
                  color=CYAN, height=28, font_size=10).pack(side=tk.RIGHT)
        tk.Label(frame, text=_t("Слова: {0}").format(len(slugs)),
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(anchor="w", pady=px(6))
        if not slugs:
            tk.Label(frame, text=_t("Нет слов в наборе"), bg=BG, fg=MUTED).pack(anchor="w")
            return
        shown = slugs[:60]
        if len(slugs) > len(shown):
            tk.Label(
                frame,
                text=_t("Показаны первые {0} из {1}").format(len(shown), len(slugs)),
                bg=BG, fg=MUTED, font=theme.font(10),
            ).pack(anchor="w")
        inner = self._scroller(frame)
        for slug in shown:
            word = vocab.get_word(slug)
            if word is None:
                continue
            tk.Label(inner, text=word_line(word, self._glang()), bg=BG, fg=TEXT,
                     font=theme.font(11), anchor="w").pack(fill=tk.X, pady=1)

    def _build_practice(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        frame.on_key = self._practice_key

        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return

        plan = HudPanel(frame, _t("ПОЛЁТНЫЙ ПЛАН"))
        plan.pack(fill=tk.X)
        row = tk.Frame(plan.body, bg=PANEL)
        row.pack(fill=tk.X)
        tk.Label(row, text=_t("ИСТОЧНИК"), bg=PANEL, fg=MUTED,
                 font=theme.font(8, True)).pack(side=tk.LEFT, padx=(0, px(6)))
        for key, title in (
            ("set", _t("НАБОР · НЕЗНАКОМЫЕ")),
            ("due", _t("НА ПОВТОРЕНИИ")),
            ("mistakes", _t("ОШИБКИ 7 ДН")),
        ):
            HudButton(row, title, lambda k=key: self._set_practice_src(k),
                      height=28, font_size=8, active=(self._practice_src == key),
                      color=GREEN if self._practice_src == key else CYAN).pack(side=tk.LEFT, padx=px(2))
        tk.Label(row, text=_t("ДЛИНА"), bg=PANEL, fg=MUTED,
                 font=theme.font(8, True)).pack(side=tk.LEFT, padx=(px(10), px(6)))
        length = self._practice_length(progress)
        for n in (5, 10, 20):
            HudButton(row, str(n), lambda k=n: self._set_practice_len(k), width=44, height=28,
                      font_size=9, active=(n == length),
                      color=GREEN if n == length else CYAN).pack(side=tk.LEFT, padx=px(2))

        slugs = self._practice_pool(plugin, progress, vocab)
        from stamina.languages.core import MissionGenerator
        try:
            generator = MissionGenerator(vocab, progress, progress.settings)
            missions = generator.generate_session(
                slugs, new_limit=length, review_limit=length,
            )[:length]
            if not missions:
                missions = generator.cards_session(slugs, length)
        except Exception as exc:
            tk.Label(frame, text=str(exc), bg=BG, fg=AMBER, font=theme.font(11),
                     wraplength=px(640)).pack(anchor="w")
            return

        source = {
            "set": getattr(self, "_pool_title", "") or _t("текущий набор"),
            "due": _t("слова на повторении"),
            "mistakes": _t("ошибки за 7 дней"),
        }[self._practice_src]
        tk.Label(frame, text=_t("МИССИИ · ПРАКТИКА"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(anchor="w", pady=(px(6), 0))
        tk.Label(frame, text=_t("Источник: {0} · слов в очереди {1} · заданий {2}").format(
            source, len(slugs), len(missions)),
            bg=BG, fg=CYAN, font=theme.font(9)).pack(anchor="w")
        self._missions = missions
        self._mission_answers: dict[int, dict] = {}
        self._mission_at = 0
        self._progress_ref = progress
        self._vocab_ref = vocab
        self._mission_body = tk.Frame(frame, bg=BG)
        self._mission_body.pack(fill=tk.BOTH, expand=True, pady=px(6))
        self._render_mission()

    def _practice_length(self, progress) -> int:
        if self._practice_len is None:
            try:
                self._practice_len = int(progress.settings.get("session_len", 10))
            except (TypeError, ValueError):
                self._practice_len = 10
        return self._practice_len

    def _practice_pool(self, plugin, progress, vocab) -> list[str]:
        if self._practice_src == "due":
            return progress.get_due_cards(list(progress.data.get("cards", {})), 200)
        if self._practice_src == "mistakes":
            return progress.mistakes(7)
        if self._pool_slugs:
            return list(self._pool_slugs)
        return self._pool(plugin, vocab)

    def _set_practice_src(self, key: str) -> None:
        self._practice_src = key if key in ("set", "due", "mistakes") else "set"
        self._show_page("practice", keep_pool=True)

    def _set_practice_len(self, n: int) -> None:
        self._practice_len = int(n)
        progress = getattr(self, "_progress_ref", None)
        if progress is not None:
            progress.settings["session_len"] = int(n)
            progress.save()
        self._show_page("practice", keep_pool=True)

    def _mission_nav(self) -> tk.Frame:
        """Строка движения по карточкам: пройденные остаются доступны."""
        nav = tk.Frame(self._mission_body, bg=BG)
        nav.pack(fill=tk.X, pady=(0, px(4)))
        missions = getattr(self, "_missions", [])
        HudButton(nav, _t("◀ НАЗАД"), self._prev_mission, height=26, font_size=8,
                  color=MUTED).pack(side=tk.LEFT)
        tk.Label(nav, text=_t("Задание {0} из {1}").format(
            min(self._mission_at + 1, len(missions)), len(missions)),
            bg=BG, fg=MUTED, font=theme.font(9)).pack(side=tk.LEFT, padx=px(8))
        HudButton(nav, _t("ДАЛЕЕ ▶"), self._next_mission, height=26, font_size=8,
                  color=CYAN).pack(side=tk.LEFT)
        if self._mission_at < len(missions) and self._mission_at not in self._mission_answers:
            HudButton(nav, _t("ПРОПУСТИТЬ"), self._next_mission, height=26, font_size=8,
                      color=MUTED).pack(side=tk.RIGHT)
        return nav

    def _render_mission(self) -> None:
        for child in self._mission_body.winfo_children():
            child.destroy()
        missions = getattr(self, "_missions", [])
        if not missions:
            tk.Label(self._mission_body, text=_t("Нет слов в наборе"), bg=BG, fg=MUTED).pack(anchor="w")
            return
        self._mission_nav()
        if self._mission_at >= len(missions):
            self._mission_summary()
            return
        mission = missions[self._mission_at]
        answer = self._mission_answers.get(self._mission_at)
        card = HudPanel(self._mission_body, mission.prompt, accent=GREEN if not answer else (
            GREEN if answer["ok"] else AMBER))
        card.pack(fill=tk.X, pady=px(4))
        if answer is not None:
            color = GREEN if answer["ok"] else AMBER
            tk.Label(card.body, text=_t("ВЕРНО") if answer["ok"] else _t("Мимо"),
                     bg=PANEL, fg=color, font=theme.font(14, True)).pack(anchor="w")
            tk.Label(card.body, text=_t("Твой ответ: {0}").format(answer["given"] or "—"),
                     bg=PANEL, fg=TEXT, font=theme.font(10)).pack(anchor="w")
            if not answer["ok"]:
                expected = mission.expected if isinstance(mission.expected, list) else [str(mission.expected)]
                tk.Label(card.body, text=_t("Правильный ответ: {0}").format(expected[0]),
                         bg=PANEL, fg=CYAN, font=theme.font(10)).pack(anchor="w")
            return
        if mission.options:
            for opt in mission.options:
                HudButton(
                    card.body, opt, lambda o=opt, m=mission: self._grade_mission(m, o),
                    height=30, font_size=10,
                ).pack(fill=tk.X, pady=px(2))
        else:
            box = tk.Entry(card.body, bg=PANEL, fg=TEXT, insertbackground=TEXT, font=theme.font(12))
            box.pack(fill=tk.X, pady=px(4))
            box.focus_set()
            box.bind("<Return>", lambda _e, m=mission, b=box: self._grade_mission(m, b.get()))
            HudButton(
                card.body, _t("ПРОВЕРИТЬ"), lambda m=mission, b=box: self._grade_mission(m, b.get()),
                color=CYAN, height=30, font_size=10,
            ).pack(fill=tk.X, pady=px(2))

    def _mission_summary(self) -> None:
        answered = len(self._mission_answers)
        total = len(self._missions)
        done = answered >= total
        tk.Label(self._mission_body,
                 text=_t("Миссия пройдена") if done else _t("Осталось заданий: {0}").format(total - answered),
                 bg=BG, fg=GREEN if done else AMBER, font=theme.font(14, True)).pack(anchor="w", pady=px(8))
        if not done:
            HudButton(self._mission_body, _t("К НЕЗАВЕРШЁННОМУ"), self._first_unanswered,
                      color=CYAN, height=30, font_size=10).pack(anchor="w", pady=px(4))
        HudButton(self._mission_body, _t("⟲ ЕЩЁ РАЗ"), self._restart_mission,
                  height=30, font_size=10).pack(anchor="w", pady=px(4))

    def _restart_mission(self) -> None:
        self._mission_answers.clear()
        self._mission_at = 0
        self._render_mission()

    def _first_unanswered(self) -> None:
        for i in range(len(self._missions)):
            if i not in self._mission_answers:
                self._mission_at = i
                self._render_mission()
                return

    def _grade_mission(self, mission, given: str) -> None:
        if self._mission_at in self._mission_answers:
            return
        expected = mission.expected if isinstance(mission.expected, list) else [str(mission.expected)]
        ok = given.strip().casefold() in {item.strip().casefold() for item in expected}
        if self._progress_ref is not None:
            self._progress_ref.record_attempt(mission.slug, ok, mission.mode)
        self._mission_answers[self._mission_at] = {"ok": ok, "given": given}
        self._render_mission()

    def _practice_key(self, event) -> None:
        key = event.keysym
        if key == "Left":
            self._prev_mission()
        elif key == "Right":
            self._next_mission()
        elif key == "Return" and (
            self._mission_at in self._mission_answers or self._mission_at >= len(self._missions)
        ):
            self._next_mission()
        elif key in ("1", "2", "3", "4") and self._mission_at < len(self._missions):
            mission = self._missions[self._mission_at]
            if self._mission_at in self._mission_answers or not mission.options:
                return
            idx = int(key) - 1
            if 0 <= idx < len(mission.options):
                self._grade_mission(mission, mission.options[idx])

    def _prev_mission(self) -> None:
        self._mission_at = max(0, self._mission_at - 1)
        self._render_mission()

    def _next_mission(self) -> None:
        self._mission_at = min(len(getattr(self, "_missions", [])), self._mission_at + 1)
        self._render_mission()

    def _build_review(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return
        self._review_queue = progress.get_due_cards(self._pool(plugin, vocab), limit=30)
        self._review_host = frame
        self._progress_ref = progress
        self._vocab_ref = vocab
        self._review_locked = False
        self._render_review()

    def _render_review(self) -> None:
        frame = self._review_host
        for child in frame.winfo_children():
            child.destroy()
        self._review_locked = False
        if not self._review_queue:
            tk.Label(frame, text=_t("Нет карточек на сегодня"), bg=BG, fg=MUTED,
                     font=theme.font(12)).pack(anchor="w")
            return
        slug = self._review_queue[0]
        word = self._vocab_ref.get_word(slug)
        if word is None:
            self._review_queue.pop(0)
            self._render_review()
            return
        card = HudPanel(frame, word.lemma, accent=CYAN)
        card.pack(fill=tk.X, pady=px(4))
        tk.Label(card.body, text=word_line(word, self._glang()), bg=PANEL, fg=TEXT,
                 font=theme.font(14)).pack(anchor="w", pady=px(4))
        if word.examples:
            tk.Label(card.body, text=word.examples[0].text, bg=PANEL, fg=MUTED,
                     font=theme.font(11), wraplength=px(640), justify="left").pack(anchor="w")
        interval = self._progress_ref.get_card(slug).interval
        tk.Label(card.body, text=_t("Интервал: {0} дн.").format(interval),
                 bg=PANEL, fg=MUTED, font=theme.font(10)).pack(anchor="w", pady=px(4))
        row = tk.Frame(card.body, bg=PANEL)
        row.pack(fill=tk.X, pady=px(4))
        for label, quality in (("СНОВА", 0), ("ТРУДНО", 3), ("ХОРОШО", 4), ("ЛЕГКО", 5)):
            HudButton(
                row, _t(label), lambda q=quality, s=slug: self._grade_review(s, q),
                height=30, font_size=10,
            ).pack(side=tk.LEFT, padx=px(2))

    def _grade_review(self, slug: str, quality: int) -> None:
        if self._review_locked:
            return
        self._review_locked = True
        from stamina.languages.core.scheduler import SM2Scheduler
        progress = self._progress_ref
        progress.update_card(slug, SM2Scheduler.next_interval(progress.get_card(slug), quality))
        progress.record_attempt(slug, quality >= 3, "review", quality=quality)
        if self._review_queue and self._review_queue[0] == slug:
            self._review_queue.pop(0)
        self._render_review()

    def _build_warehouse(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return
        top = tk.Frame(frame, bg=BG)
        top.pack(fill=tk.X, pady=(0, px(6)))
        tk.Label(top, text=_t("Поиск слова"), bg=BG, fg=MUTED, font=theme.font(10)).pack(side=tk.LEFT)
        entry = tk.Entry(top, bg=PANEL, fg=TEXT, insertbackground=TEXT, font=theme.font(12))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8))
        HudButton(top, _t("НАЙТИ"), lambda: self._show_warehouse(entry),
                  color=CYAN, height=28, font_size=10).pack(side=tk.RIGHT)
        entry.bind("<Return>", lambda _e: self._show_warehouse(entry))
        self._wh_list = tk.Frame(frame, bg=BG)
        self._wh_list.pack(fill=tk.BOTH, expand=True)
        self._progress_ref = progress
        self._vocab_ref = vocab
        self._show_warehouse(entry)

    def _show_warehouse(self, entry: tk.Entry) -> None:
        for child in self._wh_list.winfo_children():
            child.destroy()
        query = entry.get().strip()
        if query:
            words = self._vocab_ref.search(query)[:40]
            rows = [(word, self._progress_ref.get_card(word.slug).interval) for word in words]
        else:
            rows = []
            for slug in list(self._progress_ref.data.get("cards", {}))[:80]:
                word = self._vocab_ref.get_word(slug)
                if word is not None:
                    rows.append((word, self._progress_ref.get_card(slug).interval))
        tk.Label(self._wh_list, text=_t("Карточек: {0}").format(len(rows)),
                 bg=BG, fg=AMBER, font=theme.font(12, True)).pack(anchor="w", pady=px(4))
        if not rows:
            empty = _t("Ничего не найдено") if query else _t("Нет карточек на сегодня")
            tk.Label(self._wh_list, text=empty, bg=BG, fg=MUTED).pack(anchor="w")
            return
        inner = self._scroller(self._wh_list)
        for word, interval in rows:
            tk.Label(
                inner,
                text=f"{word_line(word, self._glang())}  ·  {interval}",
                bg=BG, fg=TEXT, font=theme.font(11), anchor="w",
            ).pack(fill=tk.X, pady=1)

    def _build_book(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Из книги (скоро)"), bg=BG, fg=MUTED).pack(expand=True)

    def _build_log(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return
        self._progress_ref = progress
        tk.Label(frame, text=_t("ЖУРНАЛ ЯЗЫКА"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(anchor="w")
        attempts = progress.recent_attempts(60)
        wrong = sum(1 for a in attempts if not a.get("correct"))
        row = tk.Frame(frame, bg=BG)
        row.pack(fill=tk.X, pady=px(2))
        tk.Label(row, text=_t("Попыток: {0} · ошибок: {1}").format(len(attempts), wrong),
                 bg=BG, fg=CYAN, font=theme.font(9)).pack(side=tk.LEFT)
        HudButton(row, _t("ПОВТОРИТЬ ОШИБКИ"),
                  lambda: self._set_practice_src("mistakes"),
                  height=26, font_size=8, color=AMBER).pack(side=tk.RIGHT)
        if not attempts:
            tk.Label(frame, text=_t("Записей пока нет"), bg=BG, fg=MUTED).pack(anchor="w", pady=px(8))
            return
        inner = self._scroller(frame)
        for attempt in attempts:
            when = time.strftime("%d.%m %H:%M", time.localtime(attempt.get("ts", 0)))
            word = vocab.get_word(attempt.get("slug", "")) if vocab else None
            title = word.lemma if word else attempt.get("slug", "")
            ok = bool(attempt.get("correct"))
            tk.Label(
                inner,
                text=f"{when}  {'✓' if ok else '✗'}  {title}  ·  {attempt.get('mode', '')}",
                bg=BG, fg=GREEN if ok else AMBER, font=theme.font(9), anchor="w",
            ).pack(fill=tk.X, pady=1)

    def _build_settings(self, plugin, progress) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return
        self._progress_ref = progress
        tk.Label(frame, text=_t("НАСТРОЙКИ · {0}").format(plugin.name_native if plugin else ""),
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(anchor="w")
        tk.Label(frame, text=_t("Изменения сохраняются сразу"), bg=BG, fg=MUTED,
                 font=theme.font(8)).pack(anchor="w", pady=(0, px(4)))
        inner = self._scroller(frame)

        for key, title in (
            ("autoplay", _t("Автовоспроизведение слова")),
            ("asr", _t("Микрофон и распознавание")),
            ("self_assess", _t("Самооценка чтения")),
            ("reverse", _t("Обратные карточки")),
            ("show_tr", _t("Перевод на плитке")),
            ("xp_to_rank", _t("XP идут в звание")),
        ):
            row = tk.Frame(inner, bg=BG)
            row.pack(fill=tk.X, pady=px(2))
            tk.Label(row, text=title, bg=BG, fg=TEXT, font=theme.font(10)).pack(side=tk.LEFT)
            on = bool(progress.settings.get(key, False))
            HudButton(row, _t("ВКЛ") if on else _t("ВЫКЛ"),
                      lambda k=key: self._toggle_setting(k), height=26, font_size=8,
                      active=on, color=GREEN if on else MUTED).pack(side=tk.RIGHT)

        self._choice_row(inner, "daily_goal", _t("ДНЕВНАЯ ЦЕЛЬ"), [10, 20, 30, 50])
        self._choice_row(inner, "new_per_day", _t("НОВЫХ В ДЕНЬ"), [5, 10, 20])
        self._choice_row(inner, "reviews_per_day", _t("ПОВТОРЕНИЙ В ДЕНЬ"), [20, 50, 100, 200])
        self._choice_row(inner, "session_len", _t("ДЛИНА ЗАНЯТИЯ"), [5, 10, 20])
        self._choice_row(inner, "rate", _t("ТЕМП РЕЧИ"), [0, 1, 2],
                         labels={0: _t("медленно"), 1: _t("обычно"), 2: _t("быстро")})
        self._choice_row(inner, "speech_strictness", _t("СТРОГОСТЬ РЕЧИ"),
                         ["soft", "normal", "strict"],
                         labels={"soft": _t("мягко"), "normal": _t("обычно"), "strict": _t("строго")})
        self._choice_row(inner, "gloss_lang", _t("ЯЗЫК ПЕРЕВОДА"),
                         ["ui", "ru", "en", "uk", "de"],
                         labels={"ui": _t("как интерфейс"), "ru": "Русский", "en": "English",
                                 "uk": "Українська", "de": "Deutsch"})
        tk.Label(inner,
                 text=_t("Учите испанский по-английски? Поставьте интерфейс и перевод "
                         "на English — карточки будут переводиться на английский."),
                 bg=BG, fg=MUTED, font=theme.font(8), wraplength=px(760),
                 justify="left").pack(anchor="w", pady=(0, px(4)))
        HudButton(inner, _t("СБРОСИТЬ НАСТРОЙКИ"), self._reset_settings,
                  height=28, font_size=9, color=MUTED).pack(anchor="w", pady=px(8))

    def _choice_row(self, parent, key: str, title: str, values: list, labels: dict | None = None) -> None:
        progress = self._progress_ref
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=px(2))
        tk.Label(row, text=title, bg=BG, fg=MUTED, font=theme.font(8, True), width=20,
                 anchor="w").pack(side=tk.LEFT)
        current = progress.settings.get(key)
        for value in values:
            on = current == value
            text = (labels or {}).get(value, str(value))
            HudButton(row, text, lambda k=key, v=value: self._set_setting(k, v),
                      height=26, font_size=8, active=on,
                      color=GREEN if on else CYAN).pack(side=tk.LEFT, padx=px(2))

    def _toggle_setting(self, key: str) -> None:
        progress = self._progress_ref
        progress.settings[key] = not bool(progress.settings.get(key))
        progress.save()
        self._show_page("settings")

    def _set_setting(self, key: str, value) -> None:
        progress = self._progress_ref
        progress.settings[key] = value
        progress.save()
        self._show_page("settings")

    def _reset_settings(self) -> None:
        from stamina.languages.core.progress import DEFAULT_SETTINGS
        progress = self._progress_ref
        progress.settings.update(dict(DEFAULT_SETTINGS))
        progress.save()
        self._show_page("settings")

    def _build_grammar(self, plugin, progress, vocab) -> None:
        """Построить страницу грамматики."""
        from stamina.languages.grammar_page import build_grammar_page
        page = build_grammar_page(self.page_container, plugin, progress, self.app)
        self._grammar_page = page
        # Страница сама упаковывается в build_grammar_page
