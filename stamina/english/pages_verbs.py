"""Вкладка ГЛАГОЛЫ: один глагол и 12 времён с переводом и проверкой речи."""
from __future__ import annotations

import tkinter as tk

from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT, px

from . import quality, verbs
from .mic import MicPanel
from .textutil import score_sentence, verdict
from .ui import L, ScrollFrame, Strip, target_missed

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
        self.count_lbl = L(head, "", fg=MUTED, size=8, bg=PANEL)
        self.count_lbl.pack(anchor="w", padx=px(12), pady=(0, px(8)))

        self.rows_sf = ScrollFrame(right, bg=PANEL)
        self.rows_sf.pack(fill=tk.BOTH, expand=True, pady=(px(4), 0))

        bottom = tk.Frame(right, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        bottom.pack(fill=tk.X, pady=(px(4), 0))
        self.status = L(bottom, _t("Выберите пример и проверьте произношение."), fg=MUTED, size=9,
                        bg=PANEL, wraplength=px(420), justify="left")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(10), pady=px(8))
        self.mic = None
        if hasattr(self.ctx, "asr"):
            self.mic = MicPanel(bottom, self.ctx, self.on_speech, bg=PANEL)
            self.mic.pack(side=tk.RIGHT, padx=px(8), pady=px(6))
        else:
            L(bottom, _t("Микрофон доступен в приложении"), fg=MUTED, size=8,
              bg=PANEL).pack(side=tk.RIGHT, padx=px(8))

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
        if self_score is not None:
            score = self_score
            marks = None
            heard = ""
        else:
            if not alts:
                return
            level = self.ctx.progress.settings.get("speech_strictness", "normal")
            res = [(score_sentence(sent["en"], a, verb["word"], strictness=level), a) for a in alts]
            (score, marks), heard = max(res, key=lambda r: r[0][0])
        key = self._score_key(self.active_si)
        self._scores[key] = max(self._scores.get(key, 0), score)
        self.ctx.progress.data.setdefault("verb_scores", {})[key] = self._scores[key]
        self.ctx.progress.save()
        text, vk = verdict(score)
        if score >= 80:
            quality.auto(self.ctx.progress, "verb:" + self.slug, "B", score,
                         si=self.active_si, kind="verb", n_sents=12)
            self.ctx.sfx("click")
            msg = _t("Пример {0}: {1}% · {2}").format(self.active_si + 1, score, text)
            if heard:
                msg += _t(" · услышано: «{0}»").format(heard)
            self.status.configure(text=msg, fg=GREEN)
            self.ctx.status(msg, GREEN)
        else:
            self.ctx.sfx("error")
            msg = _t("Пример {0}: {1}% · {2}").format(self.active_si + 1, score, text)
            if marks and target_missed(marks, verb["word"]):
                msg += _t(" · не найдено слово «{0}»").format(verb["word"])
            if heard:
                msg += _t(" · услышано: «{0}»").format(heard)
            self.status.configure(text=msg, fg=VCOL[vk])
            self.ctx.status(msg, VCOL[vk])
        self._render_rows()
        self._render_counts()
        try:
            self.rows_sf.canvas.yview_moveto(
                max(0.0, min(1.0, self.rows_sf.inner.winfo_height() and
                              (self.rows_sf.inner.winfo_children()[self.active_si].winfo_y() /
                               max(1, self.rows_sf.inner.winfo_height())))))
        except (IndexError, tk.TclError, ZeroDivisionError):
            pass
