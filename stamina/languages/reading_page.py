"""Отработка качественного чтения на языках, кроме английского.

Карточка: слово, перевод и его фразы. Пилот читает фразу вслух, распознавание
считает балл теми же функциями, что английский сканер. Слот качества
загорается по баллу, фраза сменяется сама через паузу. Карточки можно
листать в любую сторону — пройденные остаются доступны.
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.english.mic import MicPanel
from stamina.english.ui import Flow, L, MatchReadout
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.languages.core import reading
from stamina.languages.ctx import LangCtx
from stamina.languages.speech import asr_for, ensure_model, model_ready, speak, stop_speak
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px

VCOL = {"green": GREEN, "amber": AMBER, "red": AMBER}


class ReadingPage(tk.Frame):
    """Чтение вслух: слово, фразы, балл и слоты качества."""

    def __init__(self, master, plugin, progress, vocab, app, on_back) -> None:
        super().__init__(master, bg=BG)
        self.plugin = plugin
        self.progress = progress
        self.vocab = vocab
        self.app = app
        self.on_back = on_back
        self.ctx = LangCtx(progress, asr_for(plugin.code), app)
        self.slugs = reading.card_slugs(progress, vocab, plugin) if progress else []
        self.slugs = reading.queue(progress, self.slugs) if progress else self.slugs
        self.index = 0
        self.si = 0
        self.show_tr = False
        self._advance_job = None
        self.index = self._start_index()

        ensure_model(plugin.code, on_done=lambda: self.after(0, self._model_ready))
        if model_ready(plugin.code):
            self.ctx.asr.load_async()

        self._build()
        self._render()

    # -- сборка ---------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(10), pady=(px(4), px(2)))
        HudButton(top, _t("← ОБЗОР"), self.on_back, color=MUTED, height=28, font_size=9).pack(side=tk.LEFT)
        tk.Label(top, text=_t("ОТРАБОТКА ЧТЕНИЯ"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(side=tk.LEFT, padx=px(10))
        tk.Label(top, text=f"{self.plugin.flag_emoji} {self.plugin.name_target}", bg=BG, fg=MUTED,
                 font=theme.font(10)).pack(side=tk.LEFT)
        self.btn_prev = HudButton(top, "◀", lambda: self._move_card(-1), width=32, height=26, font_size=8)
        self.btn_prev.pack(side=tk.RIGHT, padx=px(2))
        self.pos = L(top, "", fg=CYAN, size=9, bold=True, bg=BG)
        self.pos.pack(side=tk.RIGHT, padx=px(6))
        self.btn_next = HudButton(top, "▶", lambda: self._move_card(1), width=32, height=26, font_size=8)
        self.btn_next.pack(side=tk.RIGHT, padx=px(2))

        self.panel = HudPanel(self, _t("КАРТОЧКА ЧТЕНИЯ"))
        self.panel.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(4))

        head = tk.Frame(self.panel.body, bg=PANEL)
        head.pack(fill=tk.X)
        self.word = L(head, "", fg=TEXT, size=22, bold=True, mono=True)
        self.word.pack(side=tk.LEFT)
        self.meta = L(head, "", fg=MUTED, size=8, mono=True)
        self.meta.pack(side=tk.LEFT, padx=px(10))
        self.quality = L(head, "", fg=CYAN, size=9, bold=True)
        self.quality.pack(side=tk.RIGHT)

        self.gloss = L(self.panel.body, "", fg=AMBER, size=12, bold=True)
        self.gloss.pack(anchor="w")

        self.slots = tk.Canvas(self.panel.body, bg=PANEL, height=px(14), highlightthickness=0, bd=0)
        self.slots.pack(fill=tk.X, pady=(px(4), px(2)))
        self.slots.bind("<Configure>", lambda _e: self._paint_slots())

        self.snum = L(self.panel.body, "", fg=MUTED, size=8, bold=True)
        self.snum.pack(anchor="w", pady=(px(4), 0))
        self.sent = L(self.panel.body, "", fg=TEXT, size=16, bold=True, wraplength=px(900), justify="left")
        self.sent.pack(anchor="w", pady=(px(2), 0))
        self.tr = L(self.panel.body, "", fg=MUTED, size=12, wraplength=px(900), justify="left")
        self.tr.pack(anchor="w")

        tools = Flow(self.panel.body, gap=3)
        tools.pack(fill=tk.X, pady=(px(6), px(2)))
        tools.add(HudButton(tools, _t("🔊 ФРАЗА"), lambda: self._say(False), height=28, font_size=8))
        tools.add(HudButton(tools, _t("🐢 МЕДЛЕННО"), lambda: self._say(True), height=28, font_size=8))
        tools.add(HudButton(tools, _t("ПЕРЕВОД"), self._toggle_tr, height=28, font_size=8))
        tools.add(HudButton(tools, _t("◀ ФРАЗА"), lambda: self._step_sent(-1), height=28, font_size=8))
        tools.add(HudButton(tools, _t("ФРАЗА ▶"), lambda: self._step_sent(1), height=28, font_size=8))

        self.match = MatchReadout(self.panel.body, height=48)
        self.match.pack(fill=tk.X, pady=(px(4), 0))
        self.mic = MicPanel(self.panel.body, self.ctx, self._on_speech, compact=True, live_master=self.panel.body)
        self.mic.pack(anchor="w", pady=px(2))
        self.fb = L(self.panel.body, "", fg=MUTED, size=10, wraplength=px(900), justify="left")
        self.fb.pack(anchor="w", pady=(px(2), 0))

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(10), pady=(0, px(6)))
        HudButton(bot, _t("◀ КАРТОЧКА"), lambda: self._move_card(-1), height=30, font_size=9).pack(
            side=tk.LEFT, padx=px(2))
        HudButton(bot, _t("КАРТОЧКА ▶"), lambda: self._move_card(1), height=30, font_size=9).pack(
            side=tk.LEFT, padx=px(2))
        self.tip = L(bot, _t("Читай вслух: зачёт от 80%. ←/→ — карточки, ↑/↓ — фразы."),
                     fg=MUTED, size=8, bg=BG)
        self.tip.pack(side=tk.RIGHT, padx=px(6))

    # -- данные ---------------------------------------------------------------
    def _word(self):
        if not self.slugs:
            return None
        return self.vocab.get_word(self.slugs[self.index])

    def _sentences(self) -> list:
        word = self._word()
        return reading.sentences(word) if word is not None else []

    def _start_index(self) -> int:
        """Открыть первую незакрытую карточку, а не ту, что уже отработана."""
        for i, slug in enumerate(self.slugs):
            word = self.vocab.get_word(slug)
            if word is None:
                continue
            count = reading.counts(self.progress, slug, len(reading.sentences(word)))
            if count["filled"] < count["goal"]:
                return i
        return 0

    def _render(self) -> None:
        self._cancel_advance()
        word = self._word()
        items = self._sentences()
        if word is None or not items:
            self.pos.configure(text="0 / 0")
            self.word.configure(text=_t("Нет карточек для чтения"))
            self.meta.configure(text="")
            self.gloss.configure(text=_t("Отметь слово «знаю» или подожди порцию A1."))
            self.quality.configure(text="")
            self.snum.configure(text="")
            self.sent.configure(text="")
            self.tr.configure(text="")
            self.fb.configure(text="")
            self.match.clear()
            self.slots.delete("all")
            return

        self.si %= len(items)
        done = reading.counts(self.progress, word.slug, len(items)) if self.progress else {}
        mark = "✓" if done and done["filled"] >= done["goal"] else "·"
        self.pos.configure(text=f"{mark} {self.index + 1} / {len(self.slugs)}")
        shown = self.vocab.get_word(word.slug)
        self.word.configure(text=getattr(shown, "lemma", word.lemma))
        self.meta.configure(text=f"#{word.frequency_rank or 0} · {(word.pos or '').upper()}")
        from stamina.languages.core.sqlite_vocab import gloss_lang, glosses
        ru = ", ".join(glosses(word, gloss_lang(self.progress.settings if self.progress else None))) \
            or _t("перевода нет")
        self.gloss.configure(text=ru)
        if done:
            self.quality.configure(text=_t("КАЧЕСТВО {0}/{1}").format(done["filled"], done["goal"]))
            self._draw_slots(done, word.slug)
        self.snum.configure(text=_t("ФРАЗА {0:02d} / {1:02d}").format(self.si + 1, len(items)))
        passage = items[self.si]
        self.sent.configure(text=(passage.text or "").strip())
        self.tr.configure(text=(passage.translation or "") if self.show_tr else
                          (_t("Перевод спрятан — нажми «ПЕРЕВОД».") if passage.translation else _t("перевода нет")))
        self.fb.configure(text="")
        self.match.clear()
        self._update_nav()

    def _update_nav(self) -> None:
        self.btn_prev.set_enabled(self.index > 0)
        self.btn_next.set_enabled(self.index + 1 < len(self.slugs))

    def _draw_slots(self, counts: dict, slug: str) -> None:
        self._slot_state = (counts, slug)
        self._paint_slots()

    def _paint_slots(self) -> None:
        self.slots.delete("all")
        state = getattr(self, "_slot_state", None)
        if not state:
            return
        counts, slug = state
        width = self.slots.winfo_width()
        if width < 40:
            return
        from stamina.english import quality
        raw = (quality.get(self.progress, slug) or {}).get("slots") or {}
        slots = counts.get("slots") or []
        if not slots:
            return
        gap = px(2)
        cell = (width - gap * (len(slots) - 1)) / len(slots)
        nxt = next((s["key"] for s in slots if s["key"] not in raw), None)
        for i, slot in enumerate(slots):
            x = i * (cell + gap)
            if slot["key"] in raw:
                color = CYAN if raw[slot["key"]][0] is None else GREEN
                self.slots.create_rectangle(x, px(1), x + cell, px(12), fill=color, outline=color)
            else:
                edge = AMBER if slot["key"] == nxt else LINE
                self.slots.create_rectangle(x, px(1), x + cell, px(12), fill=BG2, outline=edge)

    # -- движение карточек ----------------------------------------------------
    def _move_card(self, delta: int) -> None:
        if not self.slugs:
            return
        new = self.index + delta
        if new < 0 or new >= len(self.slugs):
            return
        self._stop_voice()
        self.index = new
        self.si = 0
        self.show_tr = False
        self._render()

    def _step_sent(self, delta: int) -> None:
        items = self._sentences()
        if not items:
            return
        self._stop_voice()
        self.si = (self.si + delta) % len(items)
        self._render()

    def _toggle_tr(self) -> None:
        self.show_tr = not self.show_tr
        self._render()

    # -- озвучка --------------------------------------------------------------
    def _say(self, slow: bool) -> None:
        items = self._sentences()
        if not items:
            return
        speak((items[self.si].text or "").strip(), self.plugin.code, slow=slow, on_error=self._voice_error)

    def _stop_voice(self) -> None:
        stop_speak()
        self.ctx.asr.stop()

    def _voice_error(self, message: str) -> None:
        self.after(0, lambda message=message: self.fb.configure(text=message) if self.winfo_exists() else None)

    # -- проверка чтения ------------------------------------------------------
    def _on_speech(self, alts, self_score) -> None:
        word = self._word()
        items = self._sentences()
        if word is None or not items:
            return
        passage = items[self.si]
        level = self.progress.settings.get("speech_strictness", "normal") if self.progress else "normal"
        marks = None
        heard = ""
        if self_score is not None:
            score = int(self_score)
        else:
            if not alts:
                return
            score, marks, heard = reading.score_passage(word, passage, alts, strictness=level)
        self.match.set(score, marks, heard, False, self_rated=self_score is not None)
        passed = score >= reading.PASS or self_score is not None
        if not passed:
            self.fb.configure(text=_t("Совпадение {0}% · нужно ≥ {1}% — ещё раз.").format(score, reading.PASS),
                              fg=AMBER)
            self.ctx.sfx("error")
            return
        res, _key = reading.record(
            self.progress, word.slug, score, self.si, len(items),
            self_rated=self_score is not None,
        )
        if res == "ok":
            self.ctx.sfx("click")
            self.fb.configure(text=_t("Зачёт: {0}% · слот качества +1").format(score), fg=GREEN)
        elif res == "self":
            self.ctx.sfx("click")
            self.fb.configure(text=_t("Самооценка записана · слот качества +1"), fg=GREEN)
        elif res == "filled":
            self.fb.configure(text=_t("Этот слот уже зачтён — читаем дальше."), fg=CYAN)
        elif res == "low":
            self.fb.configure(text=_t("Для слота нужно ≥ {0}% (сейчас {1}%).").format(
                self._needed(), score), fg=AMBER)
        elif res == "cap":
            from stamina.english import quality
            self.fb.configure(
                text=_t("На сегодня хватит: {0} повторения карточки — продолжим завтра").format(
                    quality.daily_cap(self.progress)),
                fg=AMBER,
            )
            return
        self._refresh_quality()
        self._schedule_advance()

    def _needed(self) -> int:
        word = self._word()
        if word is None:
            return reading.PASS
        n = len(reading.sentences(word))
        from stamina.english import quality
        key = quality.next_slot(self.progress, word.slug, "B", si=self.si, n_sents=n)
        if not key:
            return reading.PASS
        return int(quality.slot_map("word", n)[key]["threshold"])

    def _refresh_quality(self) -> None:
        word = self._word()
        items = self._sentences()
        if word is None or not items or self.progress is None:
            return
        done = reading.counts(self.progress, word.slug, len(items))
        self.quality.configure(text=_t("КАЧЕСТВО {0}/{1}").format(done["filled"], done["goal"]))
        self._draw_slots(done, word.slug)
        if done["filled"] >= done["goal"]:
            self.pos.configure(text=f"✓ {self.index + 1} / {len(self.slugs)}")

    def _schedule_advance(self) -> None:
        self._cancel_advance()
        self._advance_job = self.after(reading.PAUSE_MS, self._auto_next)

    def _cancel_advance(self) -> None:
        if self._advance_job is not None:
            try:
                self.after_cancel(self._advance_job)
            except tk.TclError:
                pass
            self._advance_job = None

    def _auto_next(self) -> None:
        self._advance_job = None
        items = self._sentences()
        word = self._word()
        if word is None or not items:
            return
        done = reading.counts(self.progress, word.slug, len(items))
        # следующая фраза, которую ещё не читали, либо следующая карточка
        from stamina.english import quality
        raw = (quality.get(self.progress, word.slug) or {}).get("slots") or {}
        for slot in quality.slot_map("word", len(items)).values():
            if slot["group"] != "B" or slot["key"] in raw:
                continue
            self.si = min(int(slot.get("n", 0) or 0), len(items) - 1)
            self._render()
            return
        if done["filled"] >= done["goal"] or self.index + 1 < len(self.slugs):
            self._move_card(1)

    # -- клавиши --------------------------------------------------------------
    def on_key(self, event) -> None:
        key = event.keysym
        if key == "Left":
            self._move_card(-1)
        elif key == "Right":
            self._move_card(1)
        elif key == "Up":
            self._step_sent(-1)
        elif key == "Down":
            self._step_sent(1)
        elif key == "Escape":
            self.on_back()

    def _model_ready(self) -> None:
        if self.winfo_exists() and model_ready(self.plugin.code):
            self.ctx.asr.load_async()
            self.mic.refresh_mode()

    def destroy(self) -> None:
        self._stop_voice()
        super().destroy()
