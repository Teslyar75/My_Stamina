"""Отсек «ИНОСТРАННЫЕ ЯЗЫКИ» — селектор языков и под-страницы."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import Callable

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
    ("review", _t("ПРОВЕРКА")),
    ("warehouse", _t("СКЛАД")),
    ("book", _t("ИЗ КНИГИ")),
    ("log", _t("ЖУРНАЛ")),
    ("settings", _t("НАСТРОЙКИ")),
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
        for w in self.content.winfo_children():
            w.destroy()

        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill=tk.BOTH, expand=True)

        plugins = self.registry.all()
        for i, plugin in enumerate(plugins):
            grid.grid_columnconfigure(i, weight=1, uniform="lang")
        grid.grid_rowconfigure(0, weight=1)

        pilot = pilots.active()
        pilot_dir = pilots.pilot_dir(pilot["id"]) if pilot else None

        for i, plugin in enumerate(plugins):
            card = HudPanel(grid, plugin.name_target, accent=CYAN)
            card.grid(row=0, column=i, sticky="nsew", padx=px(8), pady=px(8))
            body = card.body

            tk.Label(body, text=plugin.flag_emoji, bg=PANEL, fg=TEXT,
                     font=theme.font(48)).pack(pady=(px(8), px(4)))
            tk.Label(body, text=plugin.name_native, bg=PANEL, fg=MUTED,
                     font=theme.font(10)).pack()

            level = self._get_current_level(plugin.code, pilot_dir)
            locked = level is None and not self._is_captain()

            if locked:
                tk.Label(body, text=_t("🔒 Заблокирован"), bg=PANEL, fg=MUTED,
                         font=theme.font(11, True)).pack(pady=px(4))
                btn_text = _t("Требуется B1+ в другом языке")
            else:
                lvl_text = level or _t("Начальный")
                tk.Label(body, text=_t("Уровень: {0}").format(lvl_text), bg=PANEL, fg=GREEN,
                         font=theme.font(12, True)).pack(pady=px(4))
                btn_text = _t("ВЫБРАТЬ")

            btn = HudButton(body, btn_text,
                          lambda p=plugin.code, l=locked: self._select_language(p) if not l else None,
                          color=CYAN if not locked else MUTED,
                          height=36, font_size=11)
            btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(8), px(4)), padx=px(4))

            self.lang_cards.append({"plugin": plugin, "locked": locked, "btn": btn})

    def _is_captain(self) -> bool:
        try:
            from stamina import pilots
            return pilots.is_captain()
        except Exception:
            return False

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
        if lang_code == "en":
            self.app.show("english")
            return
        self.current_lang = lang_code
        self._pool_slugs = None
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

    def _show_page(self, page_name: str) -> None:
        self.current_page = page_name
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
        elif page_name == "review":
            self._build_review(plugin, progress, vocab)
        elif page_name == "warehouse":
            self._build_warehouse(plugin, progress, vocab)
        elif page_name == "book":
            self._build_book(plugin, progress, vocab)
        elif page_name == "log":
            self._build_log(plugin, progress)
        elif page_name == "settings":
            self._build_settings(plugin, progress)

    def _build_overview(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))

        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED,
                     font=theme.font(12)).pack(expand=True)
            return

        xp = progress.data.get("xp", {}).get("total", 0)
        streak = progress.current_streak()
        slugs = vocab.get_all_slugs()
        known = progress.known_or_learned(slugs)
        total_words = len(slugs)

        stats = [
            (_t("Всего XP"), str(xp), CYAN),
            (_t("Серия дней"), str(streak), GREEN),
            (_t("Изучено слов"), f"{known} / {total_words}", AMBER),
        ]

        for label, value, color in stats:
            card = HudPanel(frame, label, accent=color)
            card.pack(fill=tk.X, pady=px(4))
            tk.Label(card.body, text=value, bg=PANEL, fg=color,
                     font=theme.font(24, True)).pack(pady=px(8))

    def _pool(self, plugin, vocab) -> list[str]:
        if self._pool_slugs:
            return list(self._pool_slugs)
        if plugin.freq_sets:
            first = plugin.freq_sets[0]
            return vocab.get_slugs_by_freq_band(first.id)[:first.size]
        return vocab.get_all_slugs()[:600]

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
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))

        tk.Label(frame, text=_t("Частотные наборы"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(anchor="w", pady=(0, px(8)))

        for fs in plugin.freq_sets:
            slugs = vocab.get_slugs_by_freq_band(fs.id)[:fs.size]
            known = progress.known_or_learned(slugs) if progress else 0
            pct = int(known * 100 / len(slugs)) if slugs else 0

            card = HudPanel(frame, f"{fs.name_target} ({fs.short_code})", accent=CYAN)
            card.pack(fill=tk.X, pady=px(4))
            tk.Label(card.body, text=_t("{0} / {1} слов  ({2}%)").format(known, len(slugs), pct),
                     bg=PANEL, fg=TEXT, font=theme.font(11)).pack(anchor="w", pady=px(4))
            HudButton(card.body, _t("ОТКРЫТЬ"), lambda s=fs.id: self._open_set(s, vocab, progress),
                      color=CYAN, height=30, font_size=10).pack(side=tk.BOTTOM, fill=tk.X, pady=px(4))

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
        HudButton(top, _t("В МИССИИ"), lambda: self._show_page("practice"),
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
            tk.Label(inner, text=word_line(word), bg=BG, fg=TEXT,
                     font=theme.font(11), anchor="w").pack(fill=tk.X, pady=1)

    def _build_practice(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))

        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return

        from stamina.languages.core import MissionGenerator
        slugs = self._pool(plugin, vocab)
        missions = MissionGenerator(vocab, progress, progress.settings).generate_session(slugs)[:20]
        self._missions = missions
        self._mission_at = 0
        self._mission_locked = False
        self._progress_ref = progress
        tk.Label(frame, text=_t("МИССИЯ: {0} заданий").format(len(missions)),
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(anchor="w")
        self._mission_body = tk.Frame(frame, bg=BG)
        self._mission_body.pack(fill=tk.BOTH, expand=True, pady=px(8))
        self._render_mission()

    def _render_mission(self) -> None:
        for child in self._mission_body.winfo_children():
            child.destroy()
        self._mission_locked = False
        missions = getattr(self, "_missions", [])
        if not missions:
            tk.Label(self._mission_body, text=_t("Нет слов в наборе"), bg=BG, fg=MUTED).pack(anchor="w")
            return
        if self._mission_at >= len(missions):
            tk.Label(self._mission_body, text=_t("Миссия пройдена"), bg=BG, fg=GREEN,
                     font=theme.font(14, True)).pack(anchor="w")
            return
        mission = missions[self._mission_at]
        tk.Label(
            self._mission_body,
            text=_t("Задание {0} из {1}").format(self._mission_at + 1, len(missions)),
            bg=BG, fg=MUTED, font=theme.font(10),
        ).pack(anchor="w")
        card = HudPanel(self._mission_body, mission.prompt, accent=GREEN)
        card.pack(fill=tk.X, pady=px(4))
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
        self._result_label = tk.Label(card.body, text="", bg=PANEL, fg=TEXT, font=theme.font(12))
        self._result_label.pack(anchor="w", pady=px(4))

    def _grade_mission(self, mission, given: str) -> None:
        if self._mission_locked:
            return
        self._mission_locked = True
        expected = mission.expected if isinstance(mission.expected, list) else [str(mission.expected)]
        ok = given.strip().casefold() in {item.strip().casefold() for item in expected}
        if self._progress_ref is not None:
            self._progress_ref.record_attempt(mission.slug, ok, mission.mode)
        self._result_label.configure(text=_t("ВЕРНО") if ok else _t("Мимо"), fg=GREEN if ok else AMBER)
        HudButton(self._mission_body, _t("ДАЛЬШЕ"), self._next_mission,
                  color=CYAN, height=30, font_size=10).pack(fill=tk.X, pady=px(6))

    def _next_mission(self) -> None:
        self._mission_at += 1
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
        tk.Label(card.body, text=word_line(word), bg=PANEL, fg=TEXT,
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
                text=f"{word_line(word)}  ·  {interval}",
                bg=BG, fg=TEXT, font=theme.font(11), anchor="w",
            ).pack(fill=tk.X, pady=1)

    def _build_book(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Из книги (скоро)"), bg=BG, fg=MUTED).pack(expand=True)

    def _build_log(self, plugin, progress) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Журнал сессий (скоро)"), bg=BG, fg=MUTED).pack(expand=True)

    def _build_settings(self, plugin, progress) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Настройки языка (скоро)"), bg=BG, fg=MUTED).pack(expand=True)