"""Сканер слова: тот же экран, что в английском отсеке.

Структура повторяет английский компактный `ScannerPage`: прокрутка с
автоскрытием, строка действий в заголовке панели, три колонки (слово,
произношение, перевод), канал предложений с микрофоном. Озвучка — голосом
языка карточки, кнопки подсвечиваются, пока звучит фраза.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from tkinter import simpledialog

from stamina import theme
from stamina.adapt import bind_wraplength
from stamina.english.mic import MicPanel
from stamina.english.speech_std import advance_later, is_hint_key, is_mic_key, passed
from stamina.english.textutil import score_sentence, score_word
from stamina import zen_mode
from stamina.english.ui import Flow, L, MatchReadout, ScrollFrame, WrapEntry, chip
from stamina.grammar_ui.focus import is_grammar_focus_key
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.languages.ctx import LangCtx
from stamina.languages.speech import asr_for, ensure_model, model_ready, stop_speak
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, LINE_HI, MUTED, PANEL, RED, TEXT, px

# Масштаб шрифтов — те же числа, что в английском сканере (english/pages_main.py).
FOCUS_FONT_GAIN = 0.8
NORMAL_FONT_GAIN = 0.6
NORMAL_FONT_CAP = 3.0
NORMAL_FONT_MIN = 0.66


def _gloss_text(word, progress) -> str:
    """Перевод в сканере: на языке интерфейса (или выбранном в настройках)."""
    from stamina.languages.core.sqlite_vocab import glosses, gloss_lang
    return ", ".join(glosses(word, gloss_lang(getattr(progress, "settings", None))))


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
        self._bar_mode = None
        self._focus = None           # фокус-режим: панели на всю высоту окна (см. ui.FocusMode)
        self._k = 1.0                # масштаб шрифтов: 1 — обычно, больше — в фокус-режиме
        self._word_px = 20
        self._grow_saved = []
        self._fit_job = None
        self._fit_settle_job = None
        self.ctx = LangCtx(progress, asr_for(lang), app, lang=lang, voice_error=self._voice_error)
        ensure_model(lang, on_done=lambda: self.after(0, self._model_ready))

        self.sf = ScrollFrame(self, bg=BG)
        self.sf.pack(fill=tk.BOTH, expand=True)
        self.sf.autohide = True       # полоса прокрутки — только если не влезает
        self._build(self.sf.inner)
        # то же, что в английском сканере: обычный режим заполняет высоту окна,
        # а внутренние блоки (микрофон, подсказки) могут менять высоту без Configure
        self.sf.canvas.bind("<Configure>", self._queue_fit, add="+")
        self.sf.inner.bind("<Configure>", self._queue_fit, add="+")
        self.bind("<Map>", lambda _e: self.after_idle(lambda: self._fit_normal(force=True)), add="+")
        self.bind("<Unmap>", self._on_unmap, add="+")

        if model_ready(lang):
            self.ctx.asr.load_async()
        self._show()
        if progress is not None and progress.settings.get("autoplay", True):
            self.after(300, lambda: self._say(False))

    # -- раскладка: как в английском компактном сканере --------------------
    def _build(self, root) -> None:
        win = HudPanel(root, _t("СКАНЕР ОБЪЕКТА"), pad=4)
        win.pack(fill=tk.X, padx=px(8), pady=(px(1), px(2)))
        self.scan_panel = win
        bar = tk.Frame(root, bg=PANEL)
        self.actbar = bar
        HudButton(bar, "←", self._back, width=30, height=22, font_size=8).pack(side=tk.LEFT)
        HudButton(bar, "◀", lambda: self._neighbor(-1), width=28, height=22, font_size=7).pack(
            side=tk.LEFT, padx=(px(3), 0))
        HudButton(bar, "▶", lambda: self._neighbor(1), width=28, height=22, font_size=7).pack(
            side=tk.LEFT, padx=px(3))
        self.btn_focus = HudButton(bar, _t("⛶ ФОКУС  O"), lambda: self.toggle_focus(),
                                   height=22, font_size=7)
        self.btn_focus.pack(side=tk.LEFT, padx=(px(3), 0))
        self.where = L(bar, "", fg=MUTED, size=8, bg=PANEL)
        self.where.pack(side=tk.LEFT, padx=px(6))
        win.bind("<Configure>", lambda e: self._place_actbar(e.width), add="+")
        self._place_actbar(0)

        wb = win.body
        for gc, wt in ((0, 6), (2, 7), (4, 9)):
            wb.grid_columnconfigure(gc, weight=wt, uniform="sc", minsize=0)
        for gc in (1, 3):
            wb.grid_columnconfigure(gc, weight=0)
            tk.Frame(wb, bg=LINE, width=1).grid(row=0, column=gc, sticky="ns", padx=px(6))

        c0 = tk.Frame(wb, bg=PANEL)
        c0.grid(row=0, column=0, sticky="nsew")
        self.rank = chip(c0, "", CYAN, size=7)
        self.rank.pack(anchor="w")
        self.lemma = L(c0, "", fg=TEXT, size=20, bold=True, mono=True)
        self.lemma.pack(anchor="w")

        def fit_word(_e=None):      # длинное слово уменьшает шрифт, а не вылезает из колонки
            avail = c0.winfo_width() - px(4)
            txt = self.lemma.cget("text")
            if avail <= 1 or not txt:
                return
            size = round(20 * self._k)
            while size > 11 and tkfont.Font(font=theme.font(size, True, True)).measure(txt) > avail:
                size -= 1
            if size != self._word_px:
                self._word_px = size
                self.lemma.configure(font=theme.font(size, True, True))
        self._fit_word = fit_word
        c0.bind("<Configure>", fit_word, add="+")
        self.meta = Flow(c0, gap=2)
        self.meta.pack(fill=tk.X, pady=(0, px(2)))
        sens = Flow(c0, gap=3)
        sens.pack(fill=tk.X)
        sens.add(self.ctx.audio_button(sens, _t("🔊 ГОЛОС"), lambda: self.word.lemma,
                                       height=22, font_size=7))
        sens.add(self.ctx.audio_button(sens, _t("🐢 МЕДЛЕННО"), lambda: self.word.lemma, slow=True,
                                       height=22, font_size=7))

        c1 = tk.Frame(wb, bg=PANEL)
        c1.grid(row=0, column=2, sticky="nsew")
        L(c1, _t("АНАЛИЗ ПРОИЗНОШЕНИЯ"), fg=MUTED, size=7, bold=True).pack(anchor="w")
        self.heard = L(c1, "", fg=CYAN, size=13, bold=True, mono=True)
        self.heard.pack(anchor="w")
        self.verdict = L(c1, "", fg=MUTED, size=9)
        self.verdict.pack(anchor="w")
        self.phint = L(c1, "Прочитайте предложение вслух — 🎤 справа покажет, что услышано.",
                      fg=MUTED, size=9, wraplength=px(260), justify="left")
        self.phint.pack(anchor="w", pady=(px(4), 0))
        bind_wraplength(self.phint, c1, margin=4)

        c2 = tk.Frame(wb, bg=PANEL)
        c2.grid(row=0, column=4, sticky="nsew")
        L(c2, _t("ДАННЫЕ ОБЪЕКТА"), fg=MUTED, size=7, bold=True).pack(anchor="w")
        self.defn = L(c2, "", fg=TEXT, size=10, wraplength=px(360), justify="left")
        self.defn.pack(anchor="w")
        self.example = tk.Text(c2, height=1, width=10, bg=PANEL, fg=MUTED, relief="flat",
                               wrap="word", bd=0, font=theme.font(9), highlightthickness=0,
                               cursor="arrow")
        self.example.tag_configure("t", foreground=CYAN, font=theme.font(9, True))
        self.example.pack(fill=tk.X, pady=px(1))
        trr = tk.Frame(c2, bg=PANEL)
        trr.pack(fill=tk.X, pady=px(1))
        L(trr, _t("МОЙ ПЕРЕВОД"), fg=MUTED, size=7, bold=True).pack(side=tk.LEFT)
        self.tr = WrapEntry(trr, size=10)
        self.tr.on_resize = lambda: self.after(20, self.sf.sync)
        self.tr.pack(side=tk.LEFT, padx=(px(4), 0), fill=tk.X, expand=True)
        self.tr.bind("<FocusOut>", lambda _e: self._save_tr())
        self.tr.bind("<Return>", lambda _e: (self._save_tr(), self.focus_set()))
        acts = Flow(c2, gap=3)
        acts.pack(fill=tk.X, pady=(px(1), 0))
        self.btn_known = acts.add(HudButton(acts, _t("✓ ЗНАЮ"), self._toggle_known, color=GREEN,
                                            height=22, font_size=7))
        self.btn_shelf = acts.add(HudButton(acts, _t("⊞ В ОТСЕК"), self._list_menu,
                                            height=22, font_size=7))
        bind_wraplength(self.defn, c2, margin=4)

        # канал связи — практика предложений
        self.chan = HudPanel(root, _t("КАНАЛ СВЯЗИ · ПРАКТИКА ПРЕДЛОЖЕНИЙ"), pad=4)
        self.chan.pack(fill=tk.X, padx=px(8), pady=0)
        cb = self.chan.body
        cb.grid_columnconfigure(0, weight=1, minsize=0)
        cb.grid_columnconfigure(1, weight=0)
        left = tk.Frame(cb, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew")
        self.sent = tk.Text(left, height=2, width=10, bg=PANEL, fg=TEXT, relief="flat",
                            wrap="word", bd=0, font=theme.font(12, False, True),
                            highlightthickness=0, cursor="arrow")
        self.sent.tag_configure("t", foreground=CYAN, font=theme.font(12, True, True))
        self.sent.tag_configure("ok", foreground=GREEN)
        self.sent.tag_configure("bad", foreground=RED, underline=True)
        self.sent.pack(fill=tk.X)
        self.sent.bind("<Configure>", lambda _e: self.after_idle(self._fit_sent), add="+")
        self.str_ = L(left, "", fg=MUTED, size=10, wraplength=px(400), justify="left")
        self.str_.pack(anchor="w")
        self.hint = L(left, "", fg=AMBER, size=9, wraplength=px(400), justify="left")
        self.hint.pack(anchor="w")
        bind_wraplength(self.str_, left, margin=4)
        bind_wraplength(self.hint, left, margin=4)
        sbtn = Flow(left, gap=3)
        sbtn.pack(fill=tk.X, pady=(px(1), 0))
        # пустые строки перевода/подсказки не занимают высоту: показываем их только с текстом
        for lbl in (self.str_, self.hint):
            lbl.pack_forget()
            self._autohide(lbl, sbtn)
        sbtn.add(HudButton(sbtn, "◀", lambda: self._step_sent(-1), width=30, height=22))
        sbtn.add(HudButton(sbtn, "▶", lambda: self._step_sent(1), width=30, height=22))
        sbtn.add(self.ctx.audio_button(sbtn, _t("🔊 ГОЛОС"), self._sentence_text,
                                       height=22, font_size=7))
        sbtn.add(self.ctx.audio_button(sbtn, _t("🐢 МЕДЛЕННО"), self._sentence_text, slow=True,
                                       height=22, font_size=7))
        b = sbtn.add(HudButton(sbtn, _t("ПЕРЕВОД  T"), self._show_tr, height=22, font_size=7))
        b._audit_label = _t("ПЕРЕВОД")
        sbtn.add(HudButton(sbtn, _t("💡 ПОДСКАЗКА"), self._show_hint, height=22, font_size=7,
                           color=AMBER))
        # номер карточки — в полосе заголовка канала, справа: отдельная строка не нужна
        chip_bar = tk.Frame(root, bg=PANEL)
        self.chip_bar = chip_bar
        self.snum = L(chip_bar, "", fg=MUTED, size=7, bold=True)
        self.snum.pack(side=tk.LEFT)
        chip_bar.place(in_=self.chan, relx=1.0, x=-px(12), y=px(4), anchor="ne")
        # итог проверки появляется только когда он есть
        self.match = MatchReadout(left, height=48)
        m_set, m_clear = self.match.set, self.match.clear

        def _mset(*a, **k):
            if not self.match.winfo_manager():
                self.match.pack(fill=tk.X, pady=(px(2), 0))
            m_set(*a, **k)

        def _mclear():
            m_clear()
            self.match.pack_forget()
        self.match.set, self.match.clear = _mset, _mclear
        # микрофон — всегда справа, на одном месте
        self.mic = MicPanel(cb, self.ctx, self.on_speech, compact=True, live_master=left)
        bind_wraplength(self.mic.live, left, margin=4)
        self.mic.grid(row=0, column=1, sticky="n", padx=(px(8), 0))

    def _autohide(self, lbl, before) -> None:
        """Пустой текст не занимает высоту: строка появляется вместе с текстом."""
        orig = lbl.configure

        def _cfg(cnf=None, _l=lbl, _orig=orig, **kw):
            result = _orig(cnf, **kw)
            if "text" in kw or (isinstance(cnf, dict) and "text" in cnf):
                if _l.cget("text"):
                    if not _l.winfo_manager():
                        _l.pack(anchor="w", before=before)
                elif _l.winfo_manager():
                    _l.pack_forget()
            return result
        lbl.configure = lbl.config = _cfg

    def _place_actbar(self, width: int) -> None:
        """Строка действий: в полосе заголовка панели, если помещается; иначе — рядом."""
        win, bar = self.scan_panel, self.actbar
        title_w = tkfont.Font(font=theme.font(round(9 * getattr(win, "_hk", 1.0)), True)).measure(
            win.title) + px(36)
        fits = width > 1 and bar.winfo_reqwidth() + title_w + px(10) <= width
        mode = "title" if fits else "row"
        if mode == self._bar_mode:
            return
        self._bar_mode = mode
        if fits:
            bar.pack_forget()
            bar.place(in_=win, relx=1.0, x=-px(10), y=px(2), anchor="ne")
        else:
            bar.place_forget()
            bar.configure(bg=BG)
            bar.pack(fill=tk.X, padx=px(8), pady=(px(2), 0), before=win)
        bar.configure(bg=PANEL if fits else BG)
        bar.lift()

    def _fit_sent(self) -> None:
        """Поле предложения ровно по высоте текста (1–3 строки)."""
        try:
            n = self.sent.count("1.0", "end-1c", "displaylines")
        except tk.TclError:
            return
        if isinstance(n, tuple):
            n = n[0] if n else 0
        h = max(1, min(3, (n or 0) + 1))
        if int(self.sent.cget("height")) != h:
            self.sent.configure(height=h)
            if getattr(self.sf, "autohide", False):
                self.after(20, self.sf.sync)

    # -- общий зенид и масштаб: те же правила, что в английском сканере -----
    def toggle_focus(self, on: bool | None = None, **_kw) -> None:
        """Развернуть рабочие панели на всё окно (O/Щ или Ctrl+O), двойной Esc — выход."""
        active = zen_mode.is_active(self)
        on = (not active) if on is None else on
        if on and not active:
            zen_mode.enter(self)
        elif not on and active:
            zen_mode.exit_zen(self)

    def after_zen_toggle(self, on: bool) -> None:
        """Один путь раскладки для кнопки, O/Щ и Ctrl+O из cockpit."""
        self._focus = zen_mode.mode_of(self) if on else None
        self._grow(on)
        if not on:
            self.after_idle(self._fit_normal)
        btn = getattr(self, "btn_focus", None)
        if btn is not None:
            btn.set_text(_t("✕ ФОКУС  Esc") if on else _t("⛶ ФОКУС  O"))
            btn.set_active(on)
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _grow(self, on: bool) -> None:
        """Фокус-режим: панели на всю высоту, шрифт по окну (FOCUS_FONT_GAIN)."""
        if on:
            self._fill(FOCUS_FONT_GAIN, 4.0)
        else:
            self._fill(None)

    def scale_for(self, cw: int, chh: int, gain: float, cap: float) -> float:
        """Общая формула масштаба для фокуса и обычного режима."""
        return max(1.0, min(cap, cw / 512, chh / 270) * gain)

    def _fill(self, gain: float | None, cap: float = 4.0, calm: bool = False) -> None:
        """Растянуть панели сканера и канала связи по высоте окна и масштабировать шрифт.

        gain=None — вернуть исходную компактную раскладку. calm — обычный режим:
        каждая панель получает не меньше своего содержимого, остаток высоты 55/45.
        """
        panels = [w for w in (getattr(self, "scan_panel", None), getattr(self, "chan", None))
                  if w is not None]
        if len(panels) != 2:
            return
        sp, ch_ = panels
        try:
            if gain is not None:
                if not self._grow_saved:
                    self._grow_saved = [(w, dict(w.pack_info())) for w in panels
                                        if w.winfo_manager() == "pack"]
                self._center(True)
                for w in panels:
                    w.pack_propagate(False)
                    w.pack_configure(fill=tk.BOTH, expand=False)
                self.update_idletasks()
                cw = max(1, self.sf.canvas.winfo_width())
                chh = max(1, self.sf.canvas.winfo_height())
                k = self.scale_for(cw, chh, gain, cap)
                if not calm:
                    k = max(1.0, k * 0.98)  # запас: фокус не должен упираться в потолок окна
                min_k = NORMAL_FONT_MIN if calm else 1.0
                for _ in range(12):         # защита от дребезга layout/scrollbar на границе
                    self._scale(k)
                    if not calm:
                        self.update_idletasks()
                    other = self.sf.inner.winfo_reqheight() - sp.winfo_reqheight() - ch_.winfo_reqheight()
                    avail = chh - max(0, other) - (0 if calm else px(4))
                    h1 = int(avail * 0.55)
                    h2 = avail - h1
                    need = lambda p: p.body.winfo_reqheight() + px(26) + px(4) + px(6)
                    over = lambda p, hh: need(p) > hh
                    if calm:
                        n1, n2 = need(sp), need(ch_)
                        if n1 + n2 > avail and k > min_k + 0.01:
                            k = max(min_k, k * 0.92)
                            continue
                        h1 = n1 + int((avail - n1 - n2) * 0.55)
                        h2 = avail - h1
                    sp.configure(height=h1)
                    ch_.configure(height=h2)
                    if calm:
                        overflow = self.sf.inner.winfo_reqheight() - chh
                        if overflow > 0 and k > min_k + 0.01:
                            k = max(min_k, k * 0.92)
                            continue
                    if k <= min_k or not (over(sp, h1) or over(ch_, h2)):
                        break
                    nk = max(min_k, k * 0.92)
                    if abs(nk - k) < 0.005:
                        break
                    k = nk
            else:
                self._scale(1.0)
                self._center(False)
                for w, info in self._grow_saved or []:
                    w.pack_propagate(True)
                    w.configure(height=1)
                    w.pack_configure(fill=info.get("fill", tk.X), expand=info.get("expand", 0))
                self._grow_saved = []
            self.sf.sync()
        except tk.TclError:
            pass

    def _visible_for_fit(self) -> bool:
        """Сканер показывается вместо страницы отсека — пересчитывать fit только когда видно."""
        try:
            return bool(self.winfo_ismapped())
        except tk.TclError:
            return False

    def _cancel_fit_jobs(self) -> None:
        for attr in ("_fit_job", "_fit_settle_job"):
            job = getattr(self, attr, None)
            if job is None:
                continue
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            setattr(self, attr, None)

    def _fit_normal(self, force: bool = False) -> None:
        """Обычный режим: заполнить высоту окна, шрифт — NORMAL_FONT_GAIN / NORMAL_FONT_CAP."""
        self._fit_job = None
        if (self._focus is not None or not self.winfo_ismapped() or not self._visible_for_fit()):
            return
        cv = self.sf.canvas
        width, height = cv.winfo_width(), cv.winfo_height()
        if width < 50 or height < 50:
            return
        self._fill(NORMAL_FONT_GAIN, NORMAL_FONT_CAP, calm=True)
        if height <= px(360) and self._k > NORMAL_FONT_MIN + 0.001:
            self._scale(NORMAL_FONT_MIN)
            self.sf.sync()
        for _ in range(4):          # метрики Tk могут дать небольшой overflow после первого fit
            try:
                y1 = self.sf.canvas.yview()[1]
            except tk.TclError:
                break
            if y1 >= 0.995 or self._k <= NORMAL_FONT_MIN + 0.001:
                break
            self._scale(max(NORMAL_FONT_MIN, self._k * 0.92))
            self.sf.sync()
        if not force and self._fit_settle_job is None:
            self._fit_settle_job = self.after_idle(self._fit_settle)

    def _queue_fit(self, _e=None) -> None:
        """Trailing debounce: считать fit в финальной геометрии, а не в середине каскада."""
        if not self._visible_for_fit():
            self._cancel_fit_jobs()
            return
        if self._fit_job is not None:
            try:
                self.after_cancel(self._fit_job)
            except tk.TclError:
                pass
        self._fit_job = self.after(60, self._fit_normal)

    def _fit_settle(self) -> None:
        self._fit_settle_job = None
        self._fit_normal(force=True)

    def _center(self, on: bool) -> None:
        """Фокус-режим: колонки панелей тянутся по ширине, микрофон остаётся сверху."""
        wb, cb = self.scan_panel.body, self.chan.body
        wb.grid_rowconfigure(0, weight=1 if on else 0)
        cb.grid_rowconfigure(0, weight=1 if on else 0)
        for w in wb.grid_slaves(row=0):
            if int(w.grid_info()["column"]) in (0, 2, 4):
                w.grid_configure(sticky="ew" if on else "nsew")
        for w in cb.grid_slaves(row=0):
            col = int(w.grid_info()["column"])
            if col == 0:
                w.grid_configure(sticky="ew" if on else "nsew")
            elif w is self.mic:
                w.grid_configure(sticky="" if on else "n")

    def _scale(self, k: float) -> None:
        if abs(k - self._k) < 0.01:
            return
        self._k = k
        kb = 1 + (k - 1) * 0.6
        km = 1 + (k - 1) * 0.8
        kh = 1 + (k - 1) * 0.45          # заголовки панелей и строка действий — умеренно
        for p in (self.scan_panel, self.chan):
            p.rescale(kh)
        for w in self.chip_bar.winfo_children():
            self._sfont(w, kh)
        for root in (self.scan_panel, self.chan, getattr(self, "actbar", None)):
            if root is None:
                continue
            stack = [root]
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                if w is self.lemma:
                    continue
                if isinstance(w, HudButton):
                    w.rescale(kh if root is self.actbar
                              else (min(km * 1.25, 1 + (k - 1) * 0.55) if w is self.mic.btn else kb))
                    if w is self.mic.btn and k <= 1.0:
                        w.rescale(1.0)
                    continue
                if isinstance(w, (tk.Label, tk.Text, tk.Entry)) and root is not self.actbar:
                    self._sfont(w, k)
        self._fit_sent()
        self._word_px = 0
        self._fit_word()
        for fl in self._flows():
            fl.relayout(fl.winfo_width(), force=True)
        self._bar_mode = None
        self._place_actbar(self.scan_panel.winfo_width())
        self.chip_bar.place_configure(y=px(round(4 * kh)))

    def _flows(self):
        out, stack = [], [self.scan_panel, self.chan]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if isinstance(w, Flow):
                out.append(w)
        return out

    def _sfont(self, w, k: float) -> None:
        """Подобрать шрифт элемента и его тегов под масштаб (как в английском сканере)."""
        if not hasattr(w, "_base_font"):
            try:
                w._base_font = tkfont.Font(font=w.cget("font")).actual()
            except tk.TclError:
                return
            if isinstance(w, tk.Text):
                w._base_tags = {}
                for t in w.tag_names():
                    tf = w.tag_cget(t, "font")
                    if tf:
                        w._base_tags[t] = tkfont.Font(font=tf).actual()

        def mk(a):
            sz = a["size"]
            size = round(abs(sz) * k)
            return (a["family"], -size if sz < 0 else size,
                    a.get("weight", "normal"), a.get("slant", "roman"))

        try:
            w.configure(font=mk(w._base_font))
            for t, a in getattr(w, "_base_tags", {}).items():
                w.tag_configure(t, font=mk(a))
        except tk.TclError:
            pass

    def _on_unmap(self, e) -> None:
        """Страницу спрятали (другая вкладка/отсек) — фокус-режим снять."""
        self._cancel_fit_jobs()
        if self._focus is not None and e.widget in (self, self.winfo_toplevel()):
            self.after_idle(lambda: self.toggle_focus(False))

    def destroy(self) -> None:
        self._cancel_fit_jobs()
        super().destroy()


    # -- данные на экране ---------------------------------------------------
    def _model_ready(self) -> None:
        if self.winfo_exists() and model_ready(self.lang):
            self.ctx.asr.load_async()
            self.mic.refresh_mode()

    def _sentences(self):
        return [ex for ex in self.word.examples if (ex.text or "").strip()]

    def _sentence_text(self) -> str:
        items = self._sentences()
        return items[self.si % len(items)].text.strip() if items else self.word.lemma

    def _set_text(self, box: tk.Text, text: str, mark: bool = True) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        lemma = (self.word.lemma or "").lower()
        if mark and lemma:
            low, start = text.lower(), 0
            while True:
                hit = low.find(lemma, start)
                if hit < 0:
                    break
                box.tag_add("t", f"1.{hit}", f"1.{hit + len(lemma)}")
                start = hit + len(lemma)
        box.configure(state="disabled")

    def _show(self) -> None:
        word = self.word
        ru = _gloss_text(word, self.progress)
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
        self.heard.configure(text="")
        self.verdict.configure(text="")
        self._render_sentence()
        self._word_px = 0
        self._fit_word()
        self.sf.top()
        try:
            self.mic.reset()
        except Exception:  # noqa: BLE001
            pass

    # -- перевод: скрыт, пока не нажали ПЕРЕВОД/T (как в английском сканере) --
    def _tr_visible(self) -> bool:
        settings = getattr(self.progress, "settings", None)
        get = getattr(settings, "get", None)
        return bool(get("show_tr", False)) if callable(get) else False

    def _tr_text(self) -> str:
        items = self._sentences()
        if not items:
            return _gloss_text(self.word, self.progress) or _t("перевода нет")
        return (items[self.si % len(items)].translation
                or _gloss_text(self.word, self.progress) or _t("перевода нет"))

    def _apply_tr(self, show: bool) -> None:
        self.str_.configure(text=self._tr_text() if show else "")

    def _render_sentence(self) -> None:
        items = self._sentences()
        self.match.clear()
        if not items:
            self.snum.configure(text=_t("ПРЕДЛОЖЕНИЙ ДЛЯ ЭТОГО СЛОВА НЕТ"))
            self._set_text(self.sent, self.word.lemma)
            self._set_text(self.example, "")
            self._apply_tr(self._tr_visible())
            return
        self.si %= len(items)
        cur = items[self.si]
        self.snum.configure(text=_t("КАРТОЧКА ПРЕДЛОЖЕНИЯ {0:02d} / {1:02d}").format(
            self.si + 1, len(items)))
        self._set_text(self.sent, cur.text.strip())
        self._set_text(self.example, f"“{cur.text.strip()}”")
        self._apply_tr(self._tr_visible())

    def _show_tr(self) -> None:
        self._apply_tr(True)

    def _show_hint(self) -> None:
        gloss = _gloss_text(self.word, self.progress)
        self.hint.configure(text=gloss or _t("перевода нет"))

    def _step_sent(self, delta: int) -> None:
        items = self._sentences()
        if not items:
            return
        self.si = (self.si + delta) % len(items)
        self.hint.configure(text="")
        self._render_sentence()

    def _neighbor(self, delta: int) -> None:
        if not self.neighbors:
            return
        self._save_tr()
        self.index = (self.index + delta) % len(self.neighbors)
        self.word = self.neighbors[self.index]
        self.si = 0
        self._show()

    # -- голос --------------------------------------------------------------
    def _say(self, slow: bool) -> None:
        self.ctx.say(self.word.lemma, slow=slow)

    def _voice_error(self, message: str) -> None:
        def show() -> None:
            if self.winfo_exists():
                self.hint.configure(text=message)
        self.after(0, show)

    # -- правки пилота ------------------------------------------------------
    def _save_tr(self) -> None:
        if self.progress is None:
            return
        text = self.tr.get().strip()
        if text == (self.progress.my_tr(self.word.slug) or _gloss_text(self.word, self.progress)):
            return
        self.progress.set_my_tr(self.word.slug, text)

    def _toggle_known(self) -> None:
        if self.progress is None:
            return
        self.progress.set_known(self.word.slug, not self.progress.is_known(self.word.slug))
        self._show()

    # -- отсеки (именованные списки), как в английском сканере ----------------
    def _list_menu(self) -> None:
        if self.progress is None:
            return
        menu = tk.Menu(
            self, tearoff=0, bg=PANEL, fg=TEXT,
            activebackground=LINE_HI, activeforeground=CYAN, font=theme.font(10),
        )
        current = set(self.progress.lists_of(self.word.slug))
        for item in self.progress.lists:
            mark = "✓ " if item["id"] in current else "   "
            menu.add_command(
                label=f"{mark}{item['name']}  ({len(item['slugs'])})",
                command=lambda lid=item["id"]: self._toggle_in_list(lid),
            )
        menu.add_separator()
        menu.add_command(label=_t("+ Новый отсек…"), command=self._new_list)
        x = self.btn_shelf.winfo_rootx() + px(6)
        y = self.btn_shelf.winfo_rooty() + self.btn_shelf.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _toggle_in_list(self, lid: str) -> None:
        added = self.progress.toggle_in_list(lid, self.word.slug)
        item = self.progress.list_by_id(lid)
        name = item["name"] if item else "?"
        self.ctx.status(
            _t("«{0}» {1} отсек «{2}»").format(
                self.word.lemma, _t("добавлено в") if added else _t("убрано из"), name,
            ),
            CYAN,
        )

    def _new_list(self) -> None:
        name = simpledialog.askstring(_t("Новый отсек"), _t("Название отсека:"), parent=self)
        if not name:
            return
        item = self.progress.create_list(name)
        self._toggle_in_list(item["id"])

    # -- проверка произношения ---------------------------------------------
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
        self.heard.configure(text=(heard or "").strip() or _t("Ничего не разобрал — повторите"))
        self.verdict.configure(text=f"{_t('СОВПАДЕНИЕ')} {score}%")
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

    def in_focus(self) -> bool:
        """Открыт ли общий зенид (панели на всё окно)."""
        return zen_mode.is_active(self)

    def wants_key(self, event) -> bool:
        """Аккорд фокуса (Ctrl+O) — его можно нажимать и из поля ввода: это не буква."""
        return is_grammar_focus_key(event)

    def on_key(self, event):
        """Клавиши как в английском сканере: ←/→ — предложения, T — перевод, O — фокус."""
        if zen_mode.was_handled(event):
            return "break"
        if zen_mode.is_active(self) is False and isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        key = (event.keysym or "").lower()
        if zen_mode.is_escape(event) and zen_mode.is_active(self):
            zen_mode.handle_key(event, self)   # двойной Esc: первый держит, второй выходит
            return "break"
        if is_mic_key(event):
            self.mic.toggle()            # единый стандарт: M — микрофон
        elif is_grammar_focus_key(event):
            if zen_mode.is_zen_hotkey(event):
                return "break"           # Ctrl+O уже обработан cockpit
            self.toggle_focus()          # O/Щ — развернуть/свернуть панели
        elif is_hint_key(event):
            self._apply_tr(True)         # T держим — перевод
        elif key == "s":
            self.ctx.say(self._sentence_text())
        elif key in ("left", "prior"):
            self._step_sent(-1)
        elif key in ("right", "next"):
            self._step_sent(1)
        elif key == "escape":
            self._back()

    def on_key_up(self, event) -> None:
        if is_hint_key(event):
            self._apply_tr(self._tr_visible())

    def _back(self) -> None:
        self._save_tr()
        self.shutdown()
        self.on_back()

    def shutdown(self) -> None:
        self._cancel_fit_jobs()
        if zen_mode.is_active(self):
            try:
                self.toggle_focus(False)
            except tk.TclError:
                pass
        stop_speak()
        try:
            self.mic.reset()
        except Exception:  # noqa: BLE001
            pass
