"""Вкладка «СКЛАД КАРТОЧЕК»: список → карточка.

На карточке — русский текст; пользователь говорит английский.
ПОДСКАЗКА: удерживай — виден английский; отпустил — снова русский.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import random
import tkinter as tk

from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, PANEL_HI, RED, TEXT, px

from .mic import MicPanel
from .textutil import score_sentence, score_word, verdict
from .ui import L, MatchReadout, ScrollFrame, Strip, target_missed
from . import warehouse as wh
from .vocab import POS_SHORT

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}
WORD_KEY = wh.WORD_KEY


def _clear(frame) -> None:
    for c in frame.winfo_children():
        c.destroy()


class WarehousePage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.cards: list[dict] = []
        self.diff_filter: int | None = None
        self.list_mode = "shelf"  # shelf = на складе · away = возвращены в работу
        self.open_slug: str | None = None
        self.active_si = WORD_KEY
        self.scores: dict[int, int] = {}
        self._vars: list[tk.BooleanVar] = []
        # удержание подсказки: key → (label, ru, en, size)
        self._faces: dict[int, tuple[tk.Label, str, str, int]] = {}
        self._active_face: tk.Label | None = None
        self._active_ru = ""
        self._active_en = ""
        self._holding: int | None = None

        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))

        self.filt = tk.Frame(self, bg=BG)
        self.filt.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        self._mode_btns: dict[str, HudButton] = {}
        for mode, label in (("shelf", _t("НА СКЛАДЕ")), ("away", _t("В РАБОТЕ")),
                            ("done", _t("ОТРАБОТАНО"))):
            b = HudButton(self.filt, label, lambda m=mode: self.set_list_mode(m), height=28, font_size=9, width=120)
            b.pack(side=tk.LEFT, padx=px(2))
            self._mode_btns[mode] = b
        L(self.filt, _t("СЛОЖНОСТЬ"), fg=MUTED, size=8, bold=True, bg=BG).pack(side=tk.LEFT, padx=(px(12), px(6)))
        self._filt_btns: dict[int | None, HudButton] = {}
        for key, label in ((None, _t("ВСЕ")), (1, "★"), (2, "★★"), (3, "★★★")):
            b = HudButton(self.filt, label, lambda k=key: self.set_filter(k), height=28, font_size=9, width=70)
            b.pack(side=tk.LEFT, padx=px(2))
            self._filt_btns[key] = b

        self.panel = HudPanel(self, _t("СКЛАД КАРТОЧЕК"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(40), pady=px(8))
        self.body = self.panel.body

        self.btns = tk.Frame(self, bg=BG)
        self.btns.pack(pady=(0, px(12)))

        self.mic: MicPanel | None = None
        self.match: MatchReadout | None = None
        self.fb: tk.Label | None = None

    def _reload_cards(self) -> None:
        if self.list_mode == "away":
            self.cards = wh.collect_away(self.ctx.progress, self.ctx.vocab)
        elif self.list_mode == "done":
            self.cards = wh.collect_done(self.ctx.progress, self.ctx.vocab)
        else:
            self.cards = wh.collect_cards(self.ctx.progress, self.ctx.vocab, difficulty=None)
        if self.diff_filter is not None and self.list_mode != "done":
            self.cards = [c for c in self.cards if c["difficulty"] == self.diff_filter]
        elif self.diff_filter is not None and self.list_mode == "done":
            # в отработанном фильтр ★ = число заработанных звёзд
            self.cards = [c for c in self.cards if int(c.get("stars") or 0) == self.diff_filter]

    def refresh(self) -> None:
        self._reload_cards()
        self.open_slug = None
        self.scores = {}
        self.active_si = WORD_KEY
        self._holding = None
        for k, b in self._filt_btns.items():
            b.set_active(k == self.diff_filter)
        for m, b in self._mode_btns.items():
            b.set_active(m == self.list_mode)
        self.render()
        self.ctx.changed()

    def set_list_mode(self, mode: str) -> None:
        self.list_mode = mode if mode in ("shelf", "away", "done") else "shelf"
        self.refresh()

    def move_to_done_view(self) -> None:
        self.list_mode = "done"
        self.open_slug = None
        self.refresh()

    def reopen_done(self, slug: str) -> None:
        wh.reopen_on_shelf(self.ctx.progress, slug)
        self.ctx.status(_t("«{0}» снова на складе (прохождение сброшено)").format(slug), CYAN)
        self.ctx.sfx("click")
        self.set_list_mode("shelf")

    def send_to_done(self, slug: str) -> None:
        """Вручную в отсек «Отработано»."""
        scores = None
        if self.open_slug == slug and self.scores:
            scores = self.scores
        stars, avg, xp = wh.archive_to_done(self.ctx.progress, self.ctx.vocab, slug, scores)
        msg = _t("«{0}» → ОТРАБОТАНО · {1} · ср. {2}%").format(slug, wh.stars_glyph(stars), avg)
        if xp:
            msg += f"  +{xp} XP"
        self.ctx.status(msg, GREEN)
        self.ctx.sfx("bell")
        self.ctx.changed()
        self.list_mode = "done"
        self.open_slug = None
        self.refresh()

    def set_filter(self, d: int | None) -> None:
        self.diff_filter = d
        self.refresh()

    def send_to_work(self, slug: str) -> None:
        wh.return_to_work(self.ctx.progress, slug)
        self.ctx.status(_t("«{0}» снято со склада → снова в работу (проверка систем)").format(slug), AMBER)
        self.ctx.sfx("click")
        self.ctx.changed()
        self.refresh()

    def restore_to_shelf(self, slug: str) -> None:
        wh.back_to_warehouse(self.ctx.progress, slug)
        self.ctx.status(_t("«{0}» снова на складе").format(slug), GREEN)
        self.ctx.sfx("click")
        self.ctx.changed()
        self.refresh()

    def open_card(self, slug: str) -> None:
        if not any(c["slug"] == slug for c in self.cards):
            return
        self.open_slug = slug
        card = next(c for c in self.cards if c["slug"] == slug)
        self.scores = wh.load_scores(self.ctx.progress, slug, len(card["sentences"]))
        self.active_si = WORD_KEY
        self._holding = None
        # если уже всё ≥80% в best, но ещё не в «Отработано» — засчитать сейчас
        if self.list_mode == "shelf" and not wh.is_done(self.ctx.progress, slug):
            self._maybe_complete(card)
        self.render()

    def close_card(self) -> None:
        self._hint_up(self._holding)
        self.open_slug = None
        self.scores = {}
        self.active_si = WORD_KEY
        self._reload_cards()
        self.render()

    def shuffle_list(self) -> None:
        if len(self.cards) > 1:
            random.shuffle(self.cards)
            self.render()

    def _card(self) -> dict | None:
        if not self.open_slug:
            return None
        return next((c for c in self.cards if c["slug"] == self.open_slug), None)

    def _sel(self) -> list[bool]:
        card = self._card()
        if not card:
            return []
        return wh.selection(self.ctx.progress, card["slug"], len(card["sentences"]))

    def _on_check(self) -> None:
        card = self._card()
        if not card or not self._vars:
            return
        sel = [v.get() for v in self._vars]
        wh.set_selection(self.ctx.progress, card["slug"], sel)
        if self.active_si >= 0 and (self.active_si >= len(sel) or not sel[self.active_si]):
            self.active_si = next((i for i, on in enumerate(sel) if on), WORD_KEY)
        self.render()

    def _pick_active(self, si: int) -> None:
        if self._holding is not None:
            return
        if si == WORD_KEY:
            self.active_si = WORD_KEY
            self.render()
            return
        sel = self._sel()
        if 0 <= si < len(sel) and sel[si]:
            self.active_si = si
            self.render()

    # -- подсказка: удержание ----------------------------------------------------
    def _bind_hint(self, btn: HudButton, key: int) -> None:
        btn.command = None  # не клик, а удержание
        btn.bind("<ButtonPress-1>", lambda _e, k=key: self._hint_down(k), add="+")
        btn.bind("<ButtonRelease-1>", lambda _e, k=key: self._hint_up(k), add="+")
        btn.bind("<Leave>", lambda _e, k=key: self._hint_up(k), add="+")

    def _en_for(self, key: int) -> str:
        face = self._faces.get(key)
        return face[2] if face else ""

    def _speak_en(self, key: int) -> None:
        """Озвучить английский образец (не русский текст на экране)."""
        en = self._en_for(key)
        if not en:
            self.ctx.status(_t("Нет английского образца"), AMBER)
            return
        self.ctx.say(en)
        self.ctx.status(_t("Образец (EN)"), CYAN)

    def _side_controls(self, parent, key: int, bg: str) -> tk.Frame:
        """ПОДСКАЗКА (удерживай) + 🔊 EN рядом."""
        right = tk.Frame(parent, bg=bg)
        right.pack(side=tk.RIGHT, padx=px(6))
        hb = HudButton(right, _t("💡 ПОДСКАЗКА"), None, color=AMBER, height=28, font_size=8, width=110)
        hb.pack(pady=(px(2), 0))
        self._bind_hint(hb, key)
        self.ctx.audio_button(right, _t("🔊 EN"), lambda k=key: self._en_for(k),
                              height=28, font_size=8, width=70).pack(pady=(px(2), 0))
        return right

    def _hint_down(self, key: int) -> None:
        face = self._faces.get(key)
        if not face:
            return
        lab, _ru, en, size = face
        if not en:
            self.ctx.status(_t("Нет английского образца"), AMBER)
            return
        self._holding = key
        try:
            lab.configure(text=en, fg=CYAN, font=lab.cget("font"))  # цвет; шрифт ниже
            from stamina import theme
            lab.configure(font=theme.font(size, True, mono=True), fg=CYAN)
        except tk.TclError:
            return
        if key == self.active_si and self._active_face is not None:
            try:
                self._active_face.configure(text=en, fg=CYAN, font=theme.font(16, True, mono=True))
            except tk.TclError:
                pass
        self.ctx.status(_t("Подсказка (держи) · английский"), AMBER)

    def _hint_up(self, key: int | None) -> None:
        if key is None or self._holding != key:
            return
        self._holding = None
        face = self._faces.get(key)
        if not face:
            return
        lab, ru, _en, size = face
        try:
            from stamina import theme
            lab.configure(text=ru, fg=TEXT, font=theme.font(size, True, mono=False))
        except tk.TclError:
            return
        if key == self.active_si and self._active_face is not None:
            try:
                self._active_face.configure(text=self._active_ru, fg=TEXT, font=theme.font(16, True))
            except tk.TclError:
                pass

    def render(self) -> None:
        self._holding = None
        _clear(self.body)
        _clear(self.btns)
        self.mic = self.match = self.fb = None
        self._faces = {}
        self._active_face = None
        self._vars = []
        stats = wh.ensure_stats(self.ctx.progress)
        n = len(self.cards)
        if self.open_slug is None:
            self._render_list(stats, n)
        else:
            self._render_card(stats, n)

    def _render_list(self, stats: dict, n: int) -> None:
        away_n = len(wh.collect_away(self.ctx.progress, self.ctx.vocab))
        done_n = wh.count_done(self.ctx.progress, self.ctx.vocab)
        shelf_n = wh.count_cards(self.ctx.progress, self.ctx.vocab)
        if self.list_mode == "away":
            self.strip.set(
                _t("В РАБОТЕ · {0}").format(n),
                _t("Сняты со склада для повторения. Можно открыть или вернуть на склад."),
                (stats["ok"] / max(1, stats["flips"])) if stats["flips"] else 0.0,
                _t("склад {0} · отработано {1}").format(shelf_n, done_n),
            )
        elif self.list_mode == "done":
            self.strip.set(
                _t("ОТРАБОТАННЫЙ МАТЕРИАЛ · {0}").format(n),
                _t("Пройденные карточки со звёздами. Можно открыть снова или вернуть на склад."),
                1.0 if n else 0.0,
                _t("склад {0} · в работе {1}").format(shelf_n, away_n),
            )
        else:
            self.strip.set(
                _t("СКЛАД КАРТОЧЕК · {0}").format(n),
                _t("Пройди слово и предложения ≥ 80% — карточка уйдёт в «Отработано» со звёздами."),
                (stats["ok"] / max(1, stats["flips"])) if stats["flips"] else 0.0,
                _t("в работе {0} · отработано {1}").format(away_n, done_n),
            )
        if not self.cards:
            if self.list_mode == "away":
                L(self.body, _t("НЕТ КАРТОЧЕК «В РАБОТЕ»"), fg=AMBER, size=20, bold=True).pack(pady=(px(50), px(8)))
                L(self.body, _t("Сними слово со склада кнопкой «В РАБОТУ»."), fg=MUTED, size=11).pack()
            elif self.list_mode == "done":
                L(self.body, _t("ОТРАБОТАННЫХ КАРТОЧЕК ПОКА НЕТ"), fg=AMBER, size=20, bold=True).pack(
                    pady=(px(50), px(8)))
                L(self.body, _t("Пройди карточку на складе (слово + предложения ≥ 80%)."),
                  fg=MUTED, size=11).pack()
            else:
                L(self.body, _t("СКЛАД ПОКА ПУСТ"), fg=AMBER, size=22, bold=True).pack(pady=(px(50), px(8)))
                L(self.body,
                  _t("Сюда попадают слова «знаю»/выученные с примерами.\nОтметь слово в СКАНЕРЕ и вернись сюда."),
                  fg=MUTED, size=11, justify="center").pack()
            HudButton(self.btns, _t("ОТКРЫТЬ СКАНЕР"), lambda: self.ctx.show("scanner"),
                      color=CYAN, height=36).pack(side=tk.LEFT, padx=px(4))
            if self.list_mode != "shelf":
                HudButton(self.btns, _t("К СКЛАДУ"), lambda: self.set_list_mode("shelf"),
                          color=GREEN, height=36).pack(side=tk.LEFT, padx=px(4))
            return

        sf = ScrollFrame(self.body, bg=PANEL)
        sf.pack(fill=tk.BOTH, expand=True)
        for card in self.cards:
            sel = wh.selection(self.ctx.progress, card["slug"], len(card["sentences"]))
            n_on = sum(1 for x in sel if x)
            row = tk.Frame(sf.inner, bg=PANEL, cursor="hand2",
                           highlightthickness=1, highlightbackground=LINE)
            row.pack(fill=tk.X, pady=px(3), padx=px(2))
            left = tk.Frame(row, bg=PANEL)
            left.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(10), pady=px(8))
            L(left, card["ru"] or card["word"], fg=TEXT, size=14, bold=True, bg=PANEL,
              wraplength=px(480)).pack(anchor="w")
            meta = _t("#{0} · {1} · {2} · предложений: {3}").format(
                card["rank"], POS_SHORT.get(card["pos"], (card["pos"] or "").upper()),
                wh.difficulty_text(n_on or card["difficulty"]), len(card["sentences"]))
            if card.get("passed"):
                meta += _t(" · ПРОЙДЕНО · ср. {0}%").format(card.get("avg") or 0)
            L(left, meta, fg=MUTED, size=8, mono=True, bg=PANEL).pack(anchor="w", pady=(px(2), 0))
            actions = tk.Frame(row, bg=PANEL)
            actions.pack(side=tk.RIGHT, padx=px(8))
            stars = int(card.get("stars") or 0)
            L(actions, wh.stars_glyph(stars) if stars or card.get("passed") else _t("не пройдено"),
              fg=AMBER if stars else MUTED, size=14 if stars else 8, bold=True, bg=PANEL).pack(pady=(0, px(2)))
            if self.list_mode == "away":
                HudButton(actions, _t("НА СКЛАД"), lambda s=card["slug"]: self.restore_to_shelf(s),
                          color=AMBER, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
                HudButton(actions, _t("В ОТРАБОТАНО"), lambda s=card["slug"]: self.send_to_done(s),
                          color=GREEN, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
            elif self.list_mode == "done":
                HudButton(actions, _t("НА СКЛАД"), lambda s=card["slug"]: self.reopen_done(s),
                          color=AMBER, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
            else:
                HudButton(actions, _t("В РАБОТУ"), lambda s=card["slug"]: self.send_to_work(s),
                          color=AMBER, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
                HudButton(actions, _t("В ОТРАБОТАНО"), lambda s=card["slug"]: self.send_to_done(s),
                          color=GREEN, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
            HudButton(actions, _t("ОТКРЫТЬ"), lambda s=card["slug"]: self.open_card(s),
                      color=CYAN, height=30, font_size=8, width=120).pack(side=tk.TOP, pady=px(2))
            for wdg in (left, *left.winfo_children()):
                wdg.bind("<Button-1>", lambda _e, s=card["slug"]: self.open_card(s))
                wdg.bind("<Enter>", lambda _e, r=row: self._hover(r, True))
                wdg.bind("<Leave>", lambda _e, r=row: self._hover(r, False))

        HudButton(self.btns, _t("ПЕРЕМЕШАТЬ СПИСОК"), self.shuffle_list, color=AMBER, height=36).pack(
            side=tk.LEFT, padx=px(4))
        if self.list_mode == "shelf":
            if away_n:
                HudButton(self.btns, _t("В РАБОТЕ ({0})").format(away_n), lambda: self.set_list_mode("away"),
                          height=36).pack(side=tk.LEFT, padx=px(4))
            if done_n:
                HudButton(self.btns, _t("ОТРАБОТАНО ({0})").format(done_n), lambda: self.set_list_mode("done"),
                          color=GREEN, height=36).pack(side=tk.LEFT, padx=px(4))

    def _hover(self, row: tk.Frame, on: bool) -> None:
        try:
            bg = PANEL_HI if on else PANEL
            row.configure(bg=bg, highlightbackground=CYAN if on else LINE)
            for c in row.winfo_children():
                if isinstance(c, tk.Frame):
                    c.configure(bg=bg)
                    for x in c.winfo_children():
                        if isinstance(x, tk.Label):
                            x.configure(bg=bg)
        except tk.TclError:
            pass

    def _render_card(self, stats: dict, n: int) -> None:
        card = self._card()
        if not card:
            self.open_slug = None
            self._render_list(stats, n)
            return
        sents = card["sentences"]
        sel = wh.selection(self.ctx.progress, card["slug"], len(sents))
        if self.active_si >= 0 and (self.active_si >= len(sents) or not sel[self.active_si]):
            self.active_si = WORD_KEY

        n_on = sum(1 for x in sel if x)
        n_ok = sum(1 for i, on in enumerate(sel) if on and self.scores.get(i, 0) >= wh.FLIP_OK)
        word_ok = self.scores.get(WORD_KEY, 0) >= wh.FLIP_OK

        self.strip.set(
            _t("КАРТОЧКА"),
            _t("На экране русский → скажи английский (≥ {0}%). ПОДСКАЗКА (держи) = текст EN · 🔊 EN = озвучка. Затем микрофон.").format(wh.FLIP_OK),
            (stats["ok"] / max(1, stats["flips"])) if stats["flips"] else 0.0,
            _t("слово {0} · предл. {1}/{2}").format(_t("ок") if word_ok else "—", n_ok, max(1, n_on)),
        )

        top = tk.Frame(self.body, bg=PANEL)
        top.pack(fill=tk.X, pady=(px(4), px(2)))
        HudButton(top, _t("← К СПИСКУ"), self.close_card, height=30, font_size=9, width=120).pack(side=tk.LEFT)
        if self.list_mode == "done" or wh.is_done(self.ctx.progress, card["slug"]):
            HudButton(top, _t("НА СКЛАД"), lambda s=card["slug"]: self.reopen_done(s),
                      color=GREEN, height=30, font_size=9, width=110).pack(side=tk.LEFT, padx=px(4))
        elif self.list_mode == "away" or wh.is_away(self.ctx.progress, card["slug"]):
            HudButton(top, _t("НА СКЛАД"), lambda s=card["slug"]: self.restore_to_shelf(s),
                      color=CYAN, height=30, font_size=9, width=110).pack(side=tk.LEFT, padx=px(4))
            HudButton(top, _t("В ОТРАБОТАНО"), lambda s=card["slug"]: self.send_to_done(s),
                      color=GREEN, height=30, font_size=9, width=130).pack(side=tk.LEFT, padx=px(4))
        else:
            HudButton(top, _t("В РАБОТУ"), lambda s=card["slug"]: self.send_to_work(s),
                      color=AMBER, height=30, font_size=9, width=110).pack(side=tk.LEFT, padx=px(4))
            HudButton(top, _t("В ОТРАБОТАНО"), lambda s=card["slug"]: self.send_to_done(s),
                      color=GREEN, height=30, font_size=9, width=130).pack(side=tk.LEFT, padx=px(4))
        L(top, _t("#{0} · {1} · отмечено {2}").format(
            card["rank"], POS_SHORT.get(card["pos"], (card["pos"] or "").upper()),
            wh.difficulty_text(n_on)),
          fg=MUTED, size=8, bold=True, mono=True, bg=PANEL).pack(side=tk.LEFT, padx=px(12))

        sf = ScrollFrame(self.body, bg=PANEL)
        sf.pack(fill=tk.BOTH, expand=True, pady=px(4))

        # слово
        w_active = self.active_si == WORD_KEY
        w_bg = BG2 if w_active else PANEL
        wrow = tk.Frame(sf.inner, bg=w_bg, highlightthickness=1,
                        highlightbackground=CYAN if w_active else LINE, cursor="hand2")
        wrow.pack(fill=tk.X, pady=px(3), padx=px(2))
        mid_w = tk.Frame(wrow, bg=w_bg)
        mid_w.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(10), pady=px(6))
        L(mid_w, _t("СЛОВО · скажи по-английски"), fg=MUTED, size=8, bold=True, bg=w_bg).pack(anchor="w")
        ru_w = card["ru"] or _t("(нет перевода)")
        face_w = L(mid_w, ru_w, fg=TEXT, size=18, bold=True, bg=w_bg, wraplength=px(520))
        face_w.pack(anchor="w")
        self._faces[WORD_KEY] = (face_w, ru_w, card["word"], 18)
        if word_ok:
            L(mid_w, card["word"], fg=GREEN, size=12, bold=True, mono=True, bg=w_bg).pack(anchor="w", pady=(px(2), 0))
        right_w = self._side_controls(wrow, WORD_KEY, w_bg)
        ws = self.scores.get(WORD_KEY)
        if ws is not None:
            col = GREEN if ws >= wh.FLIP_OK else (AMBER if ws >= 60 else RED)
            L(right_w, f"{ws}%", fg=col, size=11, bold=True, mono=True, bg=w_bg).pack()
        else:
            L(right_w, _t("проверка ↓"), fg=MUTED, size=8, bg=w_bg).pack()
        for wdg in (wrow, mid_w, face_w):
            wdg.bind("<Button-1>", lambda _e: self._pick_active(WORD_KEY))

        for si, s in enumerate(sents):
            on = sel[si]
            active = si == self.active_si and on
            score = self.scores.get(si)
            row_bg = BG2 if active else PANEL
            row = tk.Frame(sf.inner, bg=row_bg, highlightthickness=1,
                           highlightbackground=CYAN if active else LINE)
            row.pack(fill=tk.X, pady=px(3), padx=px(2))

            var = tk.BooleanVar(value=on)
            self._vars.append(var)
            tk.Checkbutton(row, variable=var, command=self._on_check, bg=row_bg, activebackground=row_bg,
                           selectcolor=BG, fg=TEXT, activeforeground=TEXT, highlightthickness=0, bd=0).pack(
                side=tk.LEFT, padx=(px(6), px(4)))

            mid = tk.Frame(row, bg=row_bg, cursor="hand2")
            mid.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(4))
            ru = s.get("ru") or _t("(нет перевода)")
            face = L(mid, ru, fg=TEXT if on else MUTED, size=13, bold=active, bg=row_bg,
                     wraplength=px(560), justify="left")
            face.pack(anchor="w")
            self._faces[si] = (face, ru, s["en"], 13)
            if score is not None and score >= wh.FLIP_OK:
                L(mid, s["en"], fg=GREEN, size=10, mono=True, bg=row_bg, wraplength=px(560)).pack(anchor="w")

            right = self._side_controls(row, si, row_bg)
            if score is not None:
                col = GREEN if score >= wh.FLIP_OK else (AMBER if score >= 60 else RED)
                L(right, f"{score}%", fg=col, size=11, bold=True, mono=True, bg=row_bg).pack()
            elif on:
                L(right, _t("проверка ↓"), fg=MUTED, size=8, bg=row_bg).pack()
            else:
                L(right, _t("выкл"), fg=MUTED, size=8, bg=row_bg).pack()

            for wdg in (mid, face):
                wdg.bind("<Button-1>", lambda _e, i=si: self._pick_active(i))

        box = tk.Frame(self.body, bg=PANEL)
        box.pack(fill=tk.X, pady=(px(6), 0))
        en_target = ""
        if self.active_si == WORD_KEY:
            label = _t("АКТИВНО · скажи по-английски:")
            show = card["ru"] or _t("(нет перевода)")
            en_target = card["word"]
        elif 0 <= self.active_si < len(sents) and sel[self.active_si]:
            label = _t("АКТИВНО · скажи по-английски:")
            show = sents[self.active_si].get("ru") or _t("(нет перевода)")
            en_target = sents[self.active_si]["en"]
        else:
            label = _t("Выбери слово или отмеченное предложение")
            show = ""

        L(box, label, fg=MUTED, size=8, bg=PANEL).pack(anchor="w")
        self._active_ru = show
        self._active_en = en_target
        if show:
            self._active_face = L(box, show, fg=TEXT, size=16, bold=True, bg=PANEL, wraplength=px(700))
            self._active_face.pack(anchor="w", pady=px(2))
        else:
            self._active_face = None

        if en_target:
            tools = tk.Frame(box, bg=PANEL)
            tools.pack(anchor="w", pady=(px(2), 0))
            hb = HudButton(tools, _t("💡 ПОДСКАЗКА"), None, color=AMBER, height=30, font_size=9, width=120)
            hb.pack(side=tk.LEFT, padx=(0, px(4)))
            self._bind_hint(hb, self.active_si)
            self.ctx.audio_button(tools, _t("🔊 ОЗВУЧИТЬ EN"), lambda t=en_target: t,
                                  height=30, font_size=9, width=140).pack(side=tk.LEFT)
            L(tools, _t("→ затем проверка микрофоном"), fg=MUTED, size=8, bg=PANEL).pack(
                side=tk.LEFT, padx=px(10))

            mic_row = tk.Frame(box, bg=PANEL)
            mic_row.pack(anchor="w", pady=px(4))
            self.mic = MicPanel(mic_row, self.ctx, self.on_speech)
            self.mic.pack(side=tk.LEFT)
            self.match = MatchReadout(box)
            self.match.pack(fill=tk.X, pady=(px(4), 0))
            self.fb = L(box, "", fg=MUTED, size=10, bg=PANEL)
            self.fb.pack(anchor="w")

        done = wh.card_record(self.ctx.progress, card["slug"])
        if word_ok and n_on and n_ok >= n_on:
            st = int((done or {}).get("stars") or wh.stars_for_avg(wh.run_average(self.scores, sel)))
            avg = float((done or {}).get("avg") or wh.run_average(self.scores, sel))
            banner = tk.Frame(self.body, bg=PANEL)
            banner.pack(fill=tk.X, pady=px(6))
            L(banner, _t("✓ КАРТОЧКА ПРОЙДЕНА"), fg=GREEN, size=14, bold=True, bg=PANEL).pack()
            L(banner, wh.stars_glyph(st), fg=AMBER, size=28, bold=True, bg=PANEL).pack()
            L(banner, _t("средняя точность {0}% · ★≥60% · ★★≥80% · ★★★≥95%").format(avg),
              fg=MUTED, size=8, bg=PANEL).pack()
        elif done:
            L(self.body,
              _t("Лучший результат: {0} · ср. {1}%").format(wh.stars_glyph(done.get("stars", 0)), done.get("avg", 0)),
              fg=AMBER, size=11, bold=True).pack(pady=px(4))

        HudButton(self.btns, _t("← К СПИСКУ"), self.close_card, color=CYAN, height=36, width=140).pack(
            side=tk.LEFT, padx=px(4))
        HudButton(self.btns, _t("СЛЕДУЮЩАЯ В СПИСКЕ"), self._open_next, color=GREEN, height=36, width=180).pack(
            side=tk.LEFT, padx=px(4))

    def _maybe_complete(self, card: dict) -> None:
        sel = wh.selection(self.ctx.progress, card["slug"], len(card["sentences"]))
        if not wh.is_run_complete(self.scores, sel):
            return
        stars, avg, xp, improved = wh.complete_card(self.ctx.progress, card["slug"], self.scores, sel)
        if improved:
            self.ctx.sfx("bell")
            msg = _t("Пройдено → ОТРАБОТАНО · {0} · ср. {1}%").format(wh.stars_glyph(stars), avg)
            if xp:
                msg += f"  +{xp} XP"
            self.ctx.status(msg, GREEN)
            self.ctx.changed()
            # сразу в отсек отработанного материала
            self.list_mode = "done"
            self._reload_cards()
            self.open_slug = card["slug"]

    def _open_next(self) -> None:
        if not self.cards or not self.open_slug:
            return
        slugs = [c["slug"] for c in self.cards]
        try:
            i = slugs.index(self.open_slug)
        except ValueError:
            self.close_card()
            return
        self.open_card(slugs[(i + 1) % len(slugs)])

    def on_speech(self, alts, self_score) -> None:
        card = self._card()
        if not card or self._holding is not None:
            return
        w = self.ctx.vocab.get(card["slug"]) or {}
        marks = None
        heard = ""

        if self.active_si == WORD_KEY:
            if self_score is not None:
                score = self_score
            else:
                if not alts:
                    return
                score = score_word(card["word"], alts, w.get("sounds_like"))
                heard = alts[0]
            self.scores[WORD_KEY] = max(self.scores.get(WORD_KEY, 0), score)
            if self.match is not None:
                self.match.set(score, None, heard, False, self_rated=self_score is not None)
            ok = score >= wh.FLIP_OK
            xp = wh.record_sentence(self.ctx.progress, card["slug"], WORD_KEY, score, ok=ok)
            text, vk = verdict(score)
            if ok:
                self.ctx.sfx("click")
                msg = _t("Слово: {0}% · {1}").format(score, text)
                if xp:
                    msg += f"  +{xp} XP"
                self.ctx.status(msg, GREEN)
                sel = self._sel()
                for j, on in enumerate(sel):
                    if on and self.scores.get(j, 0) < wh.FLIP_OK:
                        self.active_si = j
                        break
                self._maybe_complete(card)
                self.render()
            else:
                self.ctx.sfx("error")
                if self.fb is not None:
                    self.fb.configure(text=_t("Совпадение {0}% · нужно ≥ {1}%").format(score, wh.FLIP_OK), fg=VCOL[vk])
            return

        sel = self._sel()
        si = self.active_si
        if si < 0 or si >= len(card["sentences"]) or not sel[si]:
            return
        s = card["sentences"][si]
        if self_score is not None:
            score = self_score
        else:
            if not alts:
                return
            res = [(score_sentence(s["en"], a, w.get("word")), a) for a in alts]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        self.scores[si] = max(self.scores.get(si, 0), score)
        if self.match is not None:
            self.match.set(score, marks, heard, bool(marks) and target_missed(marks, w.get("word") or ""),
                           self_rated=self_score is not None)
        ok = score >= wh.FLIP_OK
        xp = wh.record_sentence(self.ctx.progress, card["slug"], si, score, ok=ok)
        text, vk = verdict(score)
        if ok:
            self.ctx.sfx("click")
            msg = _t("Предложение {0}: {1}% · {2}").format(si + 1, score, text)
            if xp:
                msg += f"  +{xp} XP"
            self.ctx.status(msg, GREEN)
            for j, on in enumerate(sel):
                if on and self.scores.get(j, 0) < wh.FLIP_OK:
                    self.active_si = j
                    break
            self._maybe_complete(card)
            self.render()
        else:
            self.ctx.sfx("error")
            if self.fb is not None:
                self.fb.configure(text=_t("Совпадение {0}% · нужно ≥ {1}%").format(score, wh.FLIP_OK), fg=VCOL[vk])
            self.ctx.status(_t("Ещё раз: {0}%").format(score), VCOL[vk])

    def on_key(self, e) -> None:
        k = e.keysym.lower()
        if self.open_slug is None:
            if k == "r":
                self.shuffle_list()
            return
        if k in ("escape", "backspace"):
            self.close_card()
        elif k == "m" and self.mic is not None and self._holding is None:
            self.mic.toggle()
        elif k == "h":
            # клавиша H — тоже удержание: press через KeyPress/KeyRelease
            pass

    def on_key_up(self, e) -> None:
        pass
