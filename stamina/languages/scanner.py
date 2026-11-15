"""Сканер слова: тот же экран, что в английском отсеке.

Три колонки (слово, произношение, перевод) и канал предложений.
Русский перевод виден сразу. Озвучка — голосом языка карточки.
"""
from __future__ import annotations

import tkinter as tk
from datetime import date

from stamina.adapt import bind_wraplength
from stamina.english.mic import MicPanel
from stamina.english.speech_std import advance_later, passed
from stamina.english.textutil import score_sentence, score_word
from stamina.english.ui import Flow, L, MatchReadout, WrapEntry, chip
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.languages.speech import asr_for, ensure_model, model_ready, speak, stop_speak
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, px


def _russian(word) -> str:
    return ", ".join(word.translations.get("ru") or [])


class _TTS:
    def stop(self) -> None:
        stop_speak()

    def poll(self):
        return []


class _Ctx:
    def __init__(self, progress, asr, app) -> None:
        self.progress = progress
        self.asr = asr
        self.tts = _TTS()
        self.app = app

    def status(self, text: str, color=None) -> None:
        fn = getattr(self.app, "status", None)
        if callable(fn):
            fn(text, color)

    def sfx(self, name: str) -> None:
        fn = getattr(self.app, "sfx", None)
        if callable(fn):
            fn(name)


class WordScanner(tk.Frame):
    """Одно слово: перевод, образец голоса, проверка фразы."""

    def __init__(self, master, word, progress, lang: str, app, on_back, neighbors=None) -> None:
        super().__init__(master, bg=BG)
        self.word = word
        self.progress = progress
        self.lang = lang
        self.on_back = on_back
        self.neighbors = list(neighbors or [word])
        self.index = 0
        for i, item in enumerate(self.neighbors):
            if item.slug == word.slug:
                self.index = i
                break
        self.si = 0
        self.ctx = _Ctx(progress, asr_for(lang), app)
        ensure_model(lang, on_done=lambda: self.after(0, self._model_ready))

        nav = tk.Frame(self, bg=BG)
        nav.pack(fill=tk.X, padx=px(8), pady=(px(4), 0))
        HudButton(nav, "←", self._back, width=30, height=22, font_size=8).pack(side=tk.LEFT)
        HudButton(nav, "◀", lambda: self._neighbor(-1), width=28, height=22, font_size=7).pack(
            side=tk.LEFT, padx=(px(3), 0))
        HudButton(nav, "▶", lambda: self._neighbor(1), width=28, height=22, font_size=7).pack(
            side=tk.LEFT, padx=px(3))
        self.where = L(nav, "", fg=MUTED, size=8, bg=BG)
        self.where.pack(side=tk.LEFT, padx=px(6))

        win = HudPanel(self, _t("СКАНЕР ОБЪЕКТА"), pad=4)
        win.pack(fill=tk.X, padx=px(8), pady=(px(2), px(2)))
        body = win.body
        for col, weight in ((0, 6), (2, 7), (4, 9)):
            body.grid_columnconfigure(col, weight=weight, uniform="sc")
        for col in (1, 3):
            body.grid_columnconfigure(col, weight=0)
            tk.Frame(body, bg=LINE, width=1).grid(row=0, column=col, sticky="ns", padx=px(6))

        left = tk.Frame(body, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew")
        self.rank = chip(left, "", CYAN, size=7)
        self.rank.pack(anchor="w")
        self.lemma = L(left, "", fg=TEXT, size=20, bold=True, mono=True)
        self.lemma.pack(anchor="w")
        self.meta = Flow(left, gap=2)
        self.meta.pack(fill=tk.X, pady=(0, px(2)))
        voices = Flow(left, gap=3)
        voices.pack(fill=tk.X)
        voices.add(HudButton(voices, _t("🔊 ГОЛОС"), lambda: self._say(False), height=22, font_size=7))
        voices.add(HudButton(voices, _t("🐢 МЕДЛЕННО"), lambda: self._say(True), height=22, font_size=7))
        self.voice_note = L(left, "", fg=AMBER, size=8, wraplength=px(240), justify="left")
        self.voice_note.pack(anchor="w")

        mid = tk.Frame(body, bg=PANEL)
        mid.grid(row=0, column=2, sticky="nsew")
        L(mid, _t("АНАЛИЗ ПРОИЗНОШЕНИЯ"), fg=MUTED, size=7, bold=True).pack(anchor="w")
        self.heard = L(mid, "", fg=CYAN, size=13, bold=True, mono=True)
        self.heard.pack(anchor="w")
        self.ptabs = {}
        tabs = Flow(mid, gap=2)
        tabs.pack(fill=tk.X, pady=px(2))
        for key, title in (("ipa", "IPA"), ("guide", _t("КАК ПРОИЗНОСИТЬ"))):
            self.ptabs[key] = tabs.add(HudButton(tabs, title, lambda k=key: self._ptab(k), height=19, font_size=7))
        self.ptext = L(mid, "", fg=TEXT, size=10, wraplength=px(280), justify="left")
        self.ptext.pack(anchor="w")
        self.ptab = "ipa"

        right = tk.Frame(body, bg=PANEL)
        right.grid(row=0, column=4, sticky="nsew")
        L(right, _t("ДАННЫЕ ОБЪЕКТА"), fg=MUTED, size=7, bold=True).pack(anchor="w")
        self.defn = L(right, "", fg=TEXT, size=14, bold=True, wraplength=px(360), justify="left")
        self.defn.pack(anchor="w")
        self.example = L(right, "", fg=MUTED, size=9, wraplength=px(360), justify="left")
        self.example.pack(anchor="w", pady=(px(2), 0))
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill=tk.X, pady=px(2))
        L(row, _t("МОЙ ПЕРЕВОД"), fg=MUTED, size=7, bold=True).pack(side=tk.LEFT)
        self.tr = WrapEntry(row, size=10)
        self.tr.pack(side=tk.LEFT, padx=(px(4), 0), fill=tk.X, expand=True)
        self.tr.bind("<FocusOut>", lambda _e: self._save_tr())
        self.tr.bind("<Return>", lambda _e: (self._save_tr(), self.focus_set()))
        acts = Flow(right, gap=3)
        acts.pack(fill=tk.X, pady=(px(2), 0))
        self.btn_known = acts.add(HudButton(acts, _t("✓ ЗНАЮ"), self._toggle_known, color=GREEN, height=22, font_size=7))
        bind_wraplength(self.ptext, mid, margin=4)
        bind_wraplength(self.defn, right, margin=4)
        bind_wraplength(self.example, right, margin=4)

        chan = HudPanel(self, _t("КАНАЛ СВЯЗИ · ПРАКТИКА ПРЕДЛОЖЕНИЙ"), pad=4)
        chan.pack(fill=tk.BOTH, expand=True, padx=px(8), pady=(0, px(4)))
        box = chan.body
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)
        sentence = tk.Frame(box, bg=PANEL)
        sentence.grid(row=0, column=0, sticky="nsew")
        self.snum = L(sentence, "", fg=MUTED, size=7, bold=True)
        self.snum.pack(anchor="w")
        self.sent = L(sentence, "", fg=TEXT, size=14, bold=True, wraplength=px(640), justify="left")
        self.sent.pack(anchor="w", pady=(px(2), 0))
        self.str_ = L(sentence, "", fg=MUTED, size=12, wraplength=px(640), justify="left")
        self.str_.pack(anchor="w")
        buttons = Flow(sentence, gap=3)
        buttons.pack(fill=tk.X, pady=(px(4), 0))
        buttons.add(HudButton(buttons, "◀", lambda: self._step_sent(-1), width=30, height=22))
        buttons.add(HudButton(buttons, "▶", lambda: self._step_sent(1), width=30, height=22))
        buttons.add(HudButton(buttons, _t("🔊 ГОЛОС"), lambda: self._say_sentence(False), height=22, font_size=7))
        buttons.add(HudButton(buttons, _t("🐢 МЕДЛЕННО"), lambda: self._say_sentence(True), height=22, font_size=7))
        buttons.add(HudButton(buttons, _t("ПЕРЕВОД"), self._show_tr, height=22, font_size=7))
        self.match = MatchReadout(sentence, height=48)
        self.match.pack(fill=tk.X, pady=(px(4), 0))
        self.mic = MicPanel(box, self.ctx, self.on_speech, compact=True, live_master=sentence)
        self.mic.grid(row=0, column=1, sticky="n", padx=(px(8), 0))
        bind_wraplength(self.sent, sentence, margin=4)
        bind_wraplength(self.str_, sentence, margin=4)

        if model_ready(lang):
            self.ctx.asr.load_async()
        self._show()
        if progress is not None and progress.settings.get("autoplay", True):
            self.after(300, lambda: self._say(False))

    def _model_ready(self) -> None:
        if self.winfo_exists() and model_ready(self.lang):
            self.ctx.asr.load_async()
            self.mic.refresh_mode()

    def _sentences(self):
        return [ex for ex in self.word.examples if (ex.text or "").strip()]

    def _show(self) -> None:
        word = self.word
        ru = _russian(word)
        self.where.configure(text=f"{self.index + 1} / {len(self.neighbors)}")
        rank = word.frequency_rank or 0
        self.rank.configure(text=_t(" ЧАСТОТНОСТЬ #{0} ").format(rank) if rank else word.cefr_level or word.pos)
        self.lemma.configure(text=word.lemma)
        for child in self.meta.winfo_children():
            child.destroy()
        self.meta.items.clear()
        if word.pos:
            self.meta.add(L(self.meta, word.pos.upper(), fg=MUTED, size=9, bold=True))
        if word.cefr_level:
            self.meta.add(chip(self.meta, word.cefr_level, CYAN))
        self._ptab(self.ptab)
        self.defn.configure(text=ru or _t("перевода нет"))
        own = ""
        if self.progress is not None:
            own = self.progress.my_tr(word.slug)
        self.tr.delete()
        self.tr.insert(0, own or ru)
        known = self.progress is not None and self.progress.is_known(word.slug)
        self.btn_known.set_text(_t("✓ ЗНАЮ") if known else _t("○ НЕ ЗНАЮ"))
        self.btn_known.set_active(known)
        self.btn_known.set_color(GREEN if known else MUTED)
        self._render_sentence()
        try:
            self.mic.reset()
        except Exception:  # noqa: BLE001
            pass

    def _ptab(self, key: str) -> None:
        self.ptab = key
        self.heard.configure(text="")
        self.ptext.configure(text=_t("нет данных"), fg=MUTED)
        for name, button in self.ptabs.items():
            button.set_active(name == key)

    def _render_sentence(self) -> None:
        items = self._sentences()
        if not items:
            self.snum.configure(text=_t("ПРЕДЛОЖЕНИЙ ДЛЯ ЭТОГО СЛОВА НЕТ"))
            self.sent.configure(text=self.word.lemma)
            self.str_.configure(text=_russian(self.word) or _t("перевода нет"))
            self.example.configure(text="")
            self.match.clear()
            return
        self.si %= len(items)
        cur = items[self.si]
        self.snum.configure(text=_t("КАРТОЧКА ПРЕДЛОЖЕНИЯ {0:02d} / {1:02d}").format(self.si + 1, len(items)))
        self.sent.configure(text=cur.text.strip())
        self.str_.configure(text=cur.translation or _russian(self.word) or _t("перевода нет"))
        self.example.configure(text=f"“{cur.text.strip()}”")
        self.match.clear()

    def _show_tr(self) -> None:
        items = self._sentences()
        if not items:
            self.str_.configure(text=_russian(self.word) or _t("перевода нет"))
            return
        text = items[self.si % len(items)].translation or _russian(self.word)
        self.str_.configure(text=text or _t("перевода нет"))

    def _step_sent(self, delta: int) -> None:
        items = self._sentences()
        if not items:
            return
        self.si = (self.si + delta) % len(items)
        self._render_sentence()

    def _neighbor(self, delta: int) -> None:
        if not self.neighbors:
            return
        self._save_tr()
        self.index = (self.index + delta) % len(self.neighbors)
        self.word = self.neighbors[self.index]
        self.si = 0
        self.voice_note.configure(text="")
        self._show()

    def _say(self, slow: bool) -> None:
        speak(self.word.lemma, self.lang, slow=slow, on_error=self._voice_error)

    def _say_sentence(self, slow: bool) -> None:
        items = self._sentences()
        text = items[self.si % len(items)].text if items else self.word.lemma
        speak(text, self.lang, slow=slow, on_error=self._voice_error)

    def _voice_error(self, message: str) -> None:
        self.after(0, lambda message=message: self.voice_note.configure(text=message) if self.winfo_exists() else None)

    def _save_tr(self) -> None:
        if self.progress is None:
            return
        text = self.tr.get().strip()
        if text == (self.progress.my_tr(self.word.slug) or _russian(self.word)):
            return
        self.progress.set_my_tr(self.word.slug, text)

    def _toggle_known(self) -> None:
        if self.progress is None:
            return
        self.progress.set_known(self.word.slug, not self.progress.is_known(self.word.slug))
        self._show()

    def on_speech(self, alts, self_score) -> None:
        items = self._sentences()
        if items:
            target = items[self.si % len(items)].text.strip()
        else:
            target = self.word.lemma
        level = "normal"
        if self.progress is not None:
            level = self.progress.settings.get("speech_strictness", "normal")
        heard = ""
        marks = None
        if self_score is not None:
            score = int(self_score)
        elif not alts:
            return
        elif not items:
            score = score_word(target, list(alts), strictness=level)
            heard = alts[0]
            marks = [(target, score >= 60)]
        else:
            ranked = [
                (score_sentence(target, alt, self.word.lemma, strictness=level), alt)
                for alt in alts
            ]
            (score, marks), heard = max(ranked, key=lambda item: item[0][0])
        self.match.set(score, marks, heard, False, self_rated=self_score is not None)
        self._store(score)
        if passed(score) and items and self.si + 1 < len(items):
            here = self.si
            advance_later(self, lambda: self._step_sent(1), lambda: self.si == here)

    def _store(self, score: int) -> None:
        if self.progress is None:
            return
        key = f"{self.word.slug}:sent:{self.si}"
        best = self.progress.data.setdefault("speech_best", {})
        best[key] = max(int(best.get(key, 0) or 0), int(score))
        xp = 5 if score >= 85 else (3 if score >= 60 else 0)
        if xp:
            self.progress.award_once(f"speech:{key}:{date.today().isoformat()}", xp)
        quality = 5 if score >= 85 else 4 if score >= 60 else 3 if score >= 40 else 2
        self.progress.record_attempt(self.word.slug, score >= 60, "speaking", 0, quality)

    def _back(self) -> None:
        self._save_tr()
        self.shutdown()
        self.on_back()

    def shutdown(self) -> None:
        stop_speak()
        try:
            self.mic.reset()
        except Exception:  # noqa: BLE001
            pass
