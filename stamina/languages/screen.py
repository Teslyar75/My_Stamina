"""Отсек «ИНОСТРАННЫЕ ЯЗЫКИ» — селектор языков и под-страницы."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from typing import Callable

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, TEXT, px
from stamina.languages.core import get_registry, LanguageProgress
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
        self.current_lang = lang_code
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
        known = progress.known_or_learned(vocab.get_all_slugs())
        total_words = len(vocab.get_all_slugs())

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

    def _build_sets(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))

        tk.Label(frame, text=_t("Частотные наборы"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(anchor="w", pady=(0, px(8)))

        for fs in plugin.freq_sets:
            set_id, size, name_en, name_target, short = fs
            slugs = vocab.get_slugs_by_freq_band(set_id)[:size]
            known = progress.known_or_learned(slugs) if progress else 0
            pct = int(known * 100 / len(slugs)) if slugs else 0

            card = HudPanel(frame, f"{name_target} ({short})", accent=CYAN)
            card.pack(fill=tk.X, pady=px(4))
            tk.Label(card.body, text=_t("{0} / {1} слов  ({2}%)").format(known, len(slugs), pct),
                     bg=PANEL, fg=TEXT, font=theme.font(11)).pack(anchor="w", pady=px(4))
            HudButton(card.body, _t("ОТКРЫТЬ"), lambda s=set_id: self._open_set(s, vocab, progress),
                      color=CYAN, height=30, font_size=10).pack(side=tk.BOTTOM, fill=tk.X, pady=px(4))

    def _open_set(self, set_id: str, vocab: VocabSource, progress) -> None:
        pass

    def _build_practice(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))

        if not progress:
            tk.Label(frame, text=_t("Прогресс не загружен"), bg=BG, fg=MUTED).pack(expand=True)
            return

        from stamina.languages.core import MissionGenerator
        generator = MissionGenerator(vocab, progress, progress.settings)
        slugs = vocab.get_all_slugs()
        missions = generator.generate_session(slugs)

        tk.Label(frame, text=_t("МИССИЯ: {0} заданий").format(len(missions)),
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(anchor="w")

        for m in missions[:5]:
            card = HudPanel(frame, m.prompt, accent=GREEN)
            card.pack(fill=tk.X, pady=px(2))
            if m.options:
                for opt in m.options:
                    tk.Label(card.body, text=opt, bg=PANEL, fg=TEXT,
                             font=theme.font(10)).pack(anchor="w")

    def _build_review(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Качественная проверка (скоро)"), bg=BG, fg=MUTED).pack(expand=True)

    def _build_warehouse(self, plugin, progress, vocab) -> None:
        frame = tk.Frame(self.page_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(8))
        tk.Label(frame, text=_t("Склад карточек (скоро)"), bg=BG, fg=MUTED).pack(expand=True)

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