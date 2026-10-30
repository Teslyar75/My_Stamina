"""Вкладка ГЛАГОЛЫ: один глагол и 12 времён с переводом и проверкой речи."""
from __future__ import annotations

import tkinter as tk

from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

from . import quality, verbs
from .check import SpeechCheck
from .speech_std import is_hint_key, is_mic_key, passed
from .ui import L, ScrollFrame, Strip

VCOL = {"green": GREEN, "amber": AMBER, "red": RED}


class VerbsTab(tk.Frame):
    """Слева — глаголы, справа — 12 времён и микрофон для активного примера."""

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.slug = verbs.entries()[0]["slug"]
        self.active_si = 0
        self.show_ru = True
        self._scores: dict[str, int] = {}
        self._build()
        self.refresh()

    # -- сборка ---------------------------------------------------------------
    def _build(self) -> None:
        self.strip = Strip(self)
        self.strip.pack(fill=tk.X, padx=px(12), pady=(px(6), 0))
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)
        self.body = body
        self.reference = None  # Справочник (pages_reference) создаём по первому открытию
        self.after_idle(self._bind_reference_key)

        left = tk.Frame(body, bg=BG, width=px(270))
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(px(12), px(6)), pady=px(6))
        left.pack_propagate(False)
        lp = HudPanel(left, _t("ГЛАГОЛЫ"))
        lp.pack(fill=tk.BOTH, expand=True)
        self.verb_sf = ScrollFrame(lp.body, bg=PANEL)
        self.verb_sf.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(body, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(6), px(12)), pady=px(6))

        head = tk.Frame(right, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        head.pack(fill=tk.X)
        self.word_lbl = L(head, "", fg=CYAN, size=22, bold=True, mono=True, bg=PANEL)
        self.word_lbl.pack(anchor="w", padx=px(12), pady=(px(8), 0))
        self.ru_lbl = L(head, "", fg=TEXT, size=12, bg=PANEL)
        self.ru_lbl.pack(anchor="w", padx=px(12))
        self.forms_lbl = L(head, "", fg=MUTED, size=9, mono=True, bg=PANEL)
        self.forms_lbl.pack(anchor="w", padx=px(12), pady=(px(2), px(6)))

        tools = tk.Frame(head, bg=PANEL)
        tools.pack(fill=tk.X, padx=px(10), pady=(0, px(8)))
        self.ctx.audio_button(tools, _t("🔊 СЛОВО"), lambda: self._verb()["word"],
                              height=28, font_size=8).pack(side=tk.LEFT, padx=px(2))
        self.ctx.audio_button(tools, _t("🔊 ПРИМЕР"), lambda: self._active_sent()["en"],
                              height=28, font_size=8).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, _t("ПЕРЕВОД"), self.toggle_ru, active=self.show_ru,
                  height=28, font_size=8).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, _t("СЛУЧАЙНЫЙ"), self.random_verb, height=28, font_size=8,
                  color=AMBER).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, _t("СПРАВОЧНИК"), self.open_reference, height=28, font_size=8,
                  color=GREEN).pack(side=tk.LEFT, padx=px(2))
        self.count_lbl = L(head, "", fg=MUTED, size=8, bg=PANEL)
        self.count_lbl.pack(anchor="w", padx=px(12), pady=(0, px(8)))

        self.rows_sf = ScrollFrame(right, bg=PANEL)
        self.rows_sf.pack(fill=tk.BOTH, expand=True, pady=(px(4), 0))

        bottom = tk.Frame(right, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        bottom.pack(fill=tk.X, pady=(px(4), 0))
        # единый блок проверки — как в сканере (check.SpeechCheck)
        self.check = SpeechCheck(bottom, self.ctx, self.on_speech, bg=PANEL)
        self.check.pack(fill=tk.X, padx=px(10), pady=px(6))
        self.mic = self.check.mic
        self.status = self.check.note
        self.status.configure(text=_t("Выберите пример и проверьте произношение."))

    # -- данные ---------------------------------------------------------------
    def _verb(self) -> dict:
        return verbs.find(self.slug) or verbs.entries()[0]

    def _sents(self) -> list[dict]:
        return verbs.sentences(self._verb())

    def _active_sent(self) -> dict:
        sents = self._sents()
        return sents[min(self.active_si, len(sents) - 1)]

    def _score_key(self, i: int) -> str:
        return f"{self.slug}:{i}"

    def _best(self, i: int) -> int | None:
        return self._scores.get(self._score_key(i))

    # -- отрисовка ------------------------------------------------------------
    def refresh(self) -> None:
        if verbs.find(self.slug) is None:
            self.slug = verbs.entries()[0]["slug"]
        self._scores = dict(self.ctx.progress.data.get("verb_scores") or {})
        verb = self._verb()
        sents = self._sents()
        self.active_si = max(0, min(self.active_si, len(sents) - 1))
        self.strip.set(
            _t("ГЛАГОЛЫ · 12 ВРЕМЁН"),
            _t("Выберите глагол слева, прочитайте пример и проверьте произношение микрофоном. "
               "Перевод можно скрыть кнопкой ПЕРЕВОД."),
        )
        self.word_lbl.configure(text=verb["word"])
        self.ru_lbl.configure(text=verb["ru"])
        f = verb["forms"]
        self.forms_lbl.configure(text=f"{f['base']}  ·  {f['past']}  ·  {f['pp']}  ·  {f['ing']}")
        self._render_verbs()
        self._render_rows()
        self._render_counts()
        if not self.status.cget("text"):
            self.status.configure(text=_t("Выберите пример и проверьте произношение."), fg=MUTED)

    def _render_verbs(self) -> None:
        for c in self.verb_sf.inner.winfo_children():
            c.destroy()
        for v in verbs.entries():
            on = v["slug"] == self.slug
            b = HudButton(self.verb_sf.inner, f"{v['word']}  ·  {v['ru']}",
                          lambda s=v["slug"]: self.select_verb(s), height=32, font_size=9,
                          width=228, active=on, color=CYAN if on else None)
            b.pack(fill=tk.X, padx=px(4), pady=px(3))

    def _render_rows(self) -> None:
        top = self.rows_sf.canvas.yview()[0]
        for c in self.rows_sf.inner.winfo_children():
            c.destroy()
        sents = self._sents()
        for i, sent in enumerate(sents):
            active = i == self.active_si
            bg = BG2 if active else PANEL
            row = tk.Frame(self.rows_sf.inner, bg=bg, highlightthickness=1,
                           highlightbackground=CYAN if active else LINE, cursor="hand2")
            row.pack(fill=tk.X, pady=px(3), padx=px(2))

            left = tk.Frame(row, bg=bg, width=px(176))
            left.pack(side=tk.LEFT, fill=tk.Y, padx=(px(8), px(4)), pady=px(5))
            left.pack_propagate(False)
            L(left, f"{i + 1:02d} · {sent['tense']}", fg=CYAN if active else TEXT, size=9, bold=True,
              bg=bg, wraplength=px(170), justify="left").pack(anchor="w")
            L(left, sent["tense_ru"], fg=MUTED, size=8, bg=bg, wraplength=px(170),
              justify="left").pack(anchor="w")
            L(left, sent["hint"], fg=MUTED, size=7, bg=bg, wraplength=px(170),
              justify="left").pack(anchor="w")

            mid = tk.Frame(row, bg=bg)
            mid.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(5))
            en = L(mid, sent["en"], fg=TEXT if active else TEXT, size=11, bold=active, bg=bg,
                   wraplength=px(560), justify="left")
            en.pack(anchor="w")
            if self.show_ru:
                L(mid, sent["ru"], fg=MUTED, size=9, bg=bg, wraplength=px(560),
                  justify="left").pack(anchor="w", pady=(px(1), 0))

            right = tk.Frame(row, bg=bg)
            right.pack(side=tk.RIGHT, padx=px(6), pady=px(4))
            best = self._best(i)
            if best is not None:
                col = GREEN if best >= 80 else (AMBER if best >= 60 else RED)
                L(right, f"{best}%", fg=col, size=10, bold=True, mono=True, bg=bg).pack()
            else:
                L(right, "—", fg=MUTED, size=9, bg=bg).pack()
            self.ctx.audio_button(right, _t("🔊"), lambda t=sent["en"]: t, height=24,
                                  font_size=8, width=34).pack(pady=(px(2), 0))

            for wdg in (row, left, mid, en):
                wdg.bind("<Button-1>", lambda _e, n=i: self.select_row(n))
            row.bind("<Enter>", lambda _e, w=row, b=bg: self._hover(w, True, b))
            row.bind("<Leave>", lambda _e, w=row, b=bg: self._hover(w, False, b))
        self.rows_sf.canvas.yview_moveto(top)

    @staticmethod
    def _hover(row, on: bool, bg: str) -> None:
        try:
            row.configure(highlightbackground=CYAN if on else LINE) if bg == PANEL else None
        except tk.TclError:
            pass

    def _render_counts(self) -> None:
        c = quality.counts(self.ctx.progress, "verb:" + self.slug, "verb", 12)
        done = sum(1 for i in range(12) if (self._best(i) or 0) >= 80)
        self.count_lbl.configure(
            text=_t("Проверено примеров: {0}/12 · качество: {1}/{2}").format(done, c["filled"], c["goal"])
        )

    # -- справочник -----------------------------------------------------------
    def open_reference(self) -> None:
        """Справочник неправильных и частых глаголов вместо 12 примеров."""
        from .pages_reference import ReferencePanel
        if self.reference is None:
            self.reference = ReferencePanel(self, self.ctx, on_back=self.close_reference)
        self.body.pack_forget()
        self.reference.pack(fill=tk.BOTH, expand=True)
        self.strip.set(_t("ГЛАГОЛЫ · СПРАВОЧНИК"),
                       _t("Начните вводить глагол — список фильтруется сразу. Enter открывает, ←/→ — время, ↑/↓ — лицо, Ctrl+Enter — «→ в карточку», F2 — назад."))
        self.reference.search.focus_set()

    def _bind_reference_key(self) -> None:
        """F2 — открыть/закрыть справочник, пока вкладка ГЛАГОЛЫ на экране."""
        def on_f2(_e):
            try:
                if not self.winfo_ismapped():
                    return None
            except tk.TclError:
                return None
            if self.reference is not None and self.reference.winfo_ismapped():
                self.close_reference()
            else:
                self.open_reference()
            return "break"
        try:
            self.winfo_toplevel().bind("<F2>", on_f2, add="+")
        except tk.TclError:
            pass

    def close_reference(self) -> None:
        if self.reference is not None:
            self.reference.pack_forget()
        self.body.pack(fill=tk.BOTH, expand=True)
        self.refresh()

    # -- действия -------------------------------------------------------------
    def select_verb(self, slug: str) -> None:
        if slug == self.slug:
            return
        if self.mic is not None:
            try:
                self.mic.reset()
            except Exception:  # noqa: BLE001
                pass
        self.slug = slug
        self.active_si = 0
        self.status.configure(text=_t("Выберите пример и проверьте произношение."), fg=MUTED)
        self.rows_sf.canvas.yview_moveto(0)
        self.refresh()

    def select_row(self, i: int) -> None:
        if i != self.active_si:
            self.check.clear()
        self.active_si = i
        self._scores = dict(self.ctx.progress.data.get("verb_scores") or {})
        self._render_rows()
        self._render_counts()

    def toggle_ru(self) -> None:
        self.show_ru = not self.show_ru
        self._render_rows()

    def random_verb(self) -> None:
        import random
        choices = [v["slug"] for v in verbs.entries() if v["slug"] != self.slug]
        if choices:
            self.select_verb(random.choice(choices))

    def on_speech(self, alts, self_score) -> None:
        sent = self._active_sent()
        verb = self._verb()
        res = self.check.evaluate(sent["en"], alts, self_score, verb["word"])
        if res is None:
            return
        score = res[0]
        key = self._score_key(self.active_si)
        self._scores[key] = max(self._scores.get(key, 0), score)
        self.ctx.progress.data.setdefault("verb_scores", {})[key] = self._scores[key]
        self.ctx.progress.save()
        if passed(score):
            quality.auto(self.ctx.progress, "verb:" + self.slug, "B", score,
                         si=self.active_si, kind="verb", n_sents=12)
        self.status.configure(text=_t("Пример {0}: {1}%").format(self.active_si + 1, score),
                              fg=GREEN if passed(score) else MUTED)
        self._render_rows()
        self._render_counts()
        here = (self.slug, self.active_si)
        self.check.judge(score, self.next_item, lambda: (self.slug, self.active_si) == here)
        self._scroll_to_active()

    def _hint_text(self) -> str:
        s = self._active_sent()
        return f"{s.get('ru') or ''}  ·  {s.get('tense_ru') or ''}: {s.get('hint') or ''}"

    def next_item(self) -> None:
        if self.active_si < len(self._sents()) - 1:
            self.select_row(self.active_si + 1)
        else:
            slugs = [v["slug"] for v in verbs.entries()]
            i = slugs.index(self.slug) if self.slug in slugs else -1
            self.select_verb(slugs[(i + 1) % len(slugs)])
        self._scroll_to_active()

    def on_key(self, e) -> None:
        """M — микрофон (как во всех режимах), ↑/↓ — строка времени. Пробел не занят."""
        if self.reference is not None and self.reference.winfo_ismapped():
            self.reference.on_key(e)
            return
        k = (e.keysym or "").lower()
        if is_mic_key(e):
            self.check.toggle()
        elif is_hint_key(e):
            self.check.hint_down(self._hint_text())   # T — держать, как во всех проверках
        elif k == "down":
            self.select_row(min(self.active_si + 1, len(self._sents()) - 1))
            self._scroll_to_active()
        elif k == "up":
            self.select_row(max(self.active_si - 1, 0))
            self._scroll_to_active()

    def on_key_up(self, e) -> None:
        if self.reference is not None and self.reference.winfo_ismapped():
            self.reference.on_key_up(e)
        elif is_hint_key(e):
            self.check.hint_up()

    def _scroll_to_active(self) -> None:
        try:
            self.rows_sf.canvas.yview_moveto(
                max(0.0, min(1.0, self.rows_sf.inner.winfo_height() and
                              (self.rows_sf.inner.winfo_children()[self.active_si].winfo_y() /
                               max(1, self.rows_sf.inner.winfo_height())))))
        except (IndexError, tk.TclError, ZeroDivisionError):
            pass
