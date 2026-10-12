"""ГИПЕРДРАЙВ — RSVP-читалка: слово с красной буквой в центре, разгон, пауза с контекстом."""
from __future__ import annotations

from stamina.i18n import t as _t

import bisect
import re
import time
import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.theme import (AMBER, BG, BG2, CYAN, CYAN_DIM, FAINT, GREEN, LINE, LINE_HI, MUTED,
                           PANEL, RED, TEXT, blend, chamfer, px)

from . import rsvp
from .quiz import make_quiz
from .ui import Choice, HudButton, HudPanel, L, Toggle

WARMUP_FRAMES = 5
_EDGE_PUNCT = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def _bare(token: str) -> str:
    """Слово/фраза без краевой пунктуации — ключ для переводчика."""
    return _EDGE_PUNCT.sub("", token).strip() or token.strip()


class ReaderPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.tid: str | None = None
        self.title = ""
        self.text = ""
        self.words: list[rsvp.Word] = []
        self.starts: list[int] = []
        self.pos = 0
        self.state = "idle"          # idle | run | pause | quiz | done
        self.ramp: rsvp.Ramp | None = None
        self._job = None
        self._next_t = 0.0
        self._warm = 0
        self._frame: list[int] = []
        self.sess = None
        self._quiz_from = 0
        self._tr_key: str | None = None
        self._tr_src: str = ""
        self._tr_text: str = ""
        self._tr_poll_job = None
        self._tr_dir: tuple[str, str] = ("en", "ru")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.run_view = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.run_view.grid(row=0, column=0, sticky="nsew")
        self.run_view.bind("<Configure>", lambda _e: self._draw_run(full=True))
        self.run_view.bind("<Button-1>", lambda _e: self.toggle())
        self.pause_view = tk.Frame(self, bg=BG)
        self.pause_view.grid(row=0, column=0, sticky="nsew")
        self.quiz_view = tk.Frame(self, bg=BG)
        self.quiz_view.grid(row=0, column=0, sticky="nsew")
        self._build_pause()
        tk.Misc.tkraise(self.run_view)

    def _book_meta(self) -> dict | None:
        return self.ctx.lib.meta(self.tid) if self.tid else None

    def _is_bilingual_book(self) -> bool:
        from stamina.library import is_bilingual
        return is_bilingual(self._book_meta())

    def _translate_on(self) -> bool:
        from stamina.library import allows_rsvp_word_tr
        if not allows_rsvp_word_tr(self._book_meta()):
            return False
        return bool(self.st.get("rsvp_translate"))

    def _rsvp_stream(self) -> str:
        """a = оригинал, b = готовый перевод (только kind=bilingual)."""
        if not self._is_bilingual_book():
            return "a"
        s = self.st.get("rsvp_bilingual_stream") or "a"
        return "b" if s == "b" else "a"

    def _refresh_tr_dir(self) -> None:
        from stamina.translator import direction
        lang = ""
        if self.tid:
            m = self.ctx.lib.meta(self.tid) or {}
            if self._is_bilingual_book():
                bi = m.get("bilingual") or {}
                lang = bi.get("lang_b" if self._rsvp_stream() == "b" else "lang_a") or m.get("lang") or ""
            else:
                lang = m.get("lang") or ""
        if not lang and self.text:
            from stamina.langdetect import detect
            lang = detect(self.text[:4000])
        target = None
        try:
            target = self.ctx.app.store.settings.get("uplink_target")
        except Exception:
            pass
        self._tr_dir = direction(lang or "en", target)

    # ------------------------------------------------------------------ settings
    @property
    def st(self) -> dict:
        return self.ctx.sstore.settings

    def _font(self, size: int | None = None) -> tkfont.Font:
        return tkfont.Font(family=theme.MONO_FAMILY, size=size or int(self.st["font_pt"]), weight="bold")

    # ------------------------------------------------------------------ open / close
    def open(self, tid: str, *, word: int | None = None) -> None:
        self.stop_session(save=True)
        lib = self.ctx.lib
        m = lib.meta(tid)
        if not m:
            return
        self.tid = tid
        self.title = f"{m['title']}" + (f" · {m['author']}" if m.get("author") else "")
        self.text = lib.reading_text(tid, stream=self._rsvp_stream())
        self.no_original = not lib.original(tid)
        self.words = rsvp.tokenize(self.text)
        self.starts = [w.start for w in self.words]
        if word is None:
            word = int(m["positions"]["reading"].get("word", 0))
        self.pos = max(0, min(word, max(0, len(self.words) - 1)))
        lib.set_active("reading", tid)
        s = self.st
        self.ramp = rsvp.Ramp(s["wpm_start"], s["wpm_target"], s["ramp_step"], s["ramp_every_s"], s["ramp"])
        last = self.ctx.sstore.data.get("last_wpm", {}).get(tid)
        if last:
            self.ramp.wpm = max(float(s["wpm_start"]), min(float(last), float(s["wpm_target"])))
        self._quiz_from = self.pos
        self.state = "pause"
        self.sess = None
        self._refresh_tr_dir()
        # панель паузы зависит от kind книги (поток языка / перевод под словом)
        for w in self.pause_view.winfo_children():
            w.destroy()
        self._build_pause()
        self._show_pause()

    def stop_session(self, save: bool = True) -> None:
        self._cancel()
        self._stop_tr_poll()
        if self.tid and save:
            self._save_pos()
        if self.sess and self.sess["words"] >= 20:
            self._record_session(comp=None)
        self.sess = None

    def _save_pos(self) -> None:
        if self.tid:
            self.ctx.lib.set_position(self.tid, "reading", self.pos)
            if self.ramp:
                self.ctx.sstore.data.setdefault("last_wpm", {})[self.tid] = int(self.ramp.wpm)
                self.ctx.sstore.save()
            try:
                from stamina.english.book_sentences import notify_reading
                notify_reading(self.ctx.app, self.ctx.lib, self.tid)
            except Exception:
                pass

    def _cancel(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    # ------------------------------------------------------------------ run loop
    def toggle(self) -> None:
        if self.state == "run":
            self.pause()
        elif self.state in ("pause", "idle") and self.words:
            self.resume()

    def resume(self) -> None:
        if not self.words:
            return
        if self.pos >= len(self.words):
            self.pos = 0
        if self.sess is None:
            self.sess = {"t0": time.time(), "secs": 0.0, "words": 0, "start": self.pos, "max": 0.0}
        self.state = "run"
        self.ctx.set_focus_mode(True)
        self._refresh_tr_dir()
        tk.Misc.tkraise(self.run_view)
        self._warm = WARMUP_FRAMES
        self._next_t = time.perf_counter()
        self._draw_run(full=True)
        self._start_tr_poll()
        self._step()

    def pause(self, reason: str = "") -> None:
        if self.state != "run":
            return
        self._cancel()
        self._stop_tr_poll()
        self.state = "pause"
        self._save_pos()
        self.ctx.set_focus_mode(False)
        self._show_pause(reason)

    def _step(self) -> None:
        self._job = None
        if self.state != "run":
            return
        if self.pos >= len(self.words):
            self.finish(end=True)
            return
        n = int(self.st["chunk"])
        frame = rsvp.frame_at(self.words, self.pos, n, int(self.st["chunk_max_chars"]))
        self._frame = frame
        wpm = self.ramp.wpm
        ms = rsvp.frame_ms(self.words, frame, wpm, bool(self.st["punct_pauses"]))
        if self._warm > 0:
            ms *= 1.5
            self._warm -= 1
        self._draw_word()
        self._draw_hud()
        dt = ms / 1000.0
        self.ramp.tick(dt, len(frame))
        self.sess["secs"] += dt
        self.sess["words"] += len(frame)
        self.sess["max"] = max(self.sess["max"], wpm)
        self.pos = frame[-1] + 1
        self._next_t += dt
        # проверка понимания после порции слов (на конце предложения)
        if (self.st["quiz"] == "always" and self.pos - self._quiz_from >= int(self.st["quiz_words"])
                and self.words[frame[-1]].sent_end):
            self._job = self.after(max(1, int(ms)), lambda: self.finish(end=False))
            return
        delay = max(1, int((self._next_t - time.perf_counter()) * 1000))
        self._job = self.after(delay, self._step)

    # ------------------------------------------------------------------ drawing (run)
    def _geom(self):
        c = self.run_view
        w, h = c.winfo_width(), c.winfo_height()
        # с переводом слово чуть выше — пара «слово + перевод» в центре
        cy = h * (0.38 if self._translate_on() else 0.44)
        return w, h, w / 2, cy

    def _draw_run(self, full: bool = False) -> None:
        c = self.run_view
        c.delete("all")
        w, h, cx, cy = self._geom()
        if w < 50:
            return
        m = px(40)
        top, bot = px(50), h - px(130)
        c.create_polygon(chamfer(m, top, w - m, bot, px(12)), fill=BG2, outline=LINE_HI)
        c.create_line(m, top + px(12), m, top + px(34), fill=LINE_HI, width=2)
        c.create_line(m + px(12), top, m + px(52), top, fill=LINE_HI, width=2)
        fs = int(self.st["font_pt"])
        half = self._font().metrics("linespace") / 2 + px(18)
        tr_on = self._translate_on()
        guide_bot = cy + half + (px(52) if tr_on else 0)
        if self.st.get("guides", True):
            c.create_line(w * 0.12, cy - half, w * 0.88, cy - half, fill=LINE)
            c.create_line(w * 0.12, guide_bot, w * 0.88, guide_bot, fill=LINE)
            c.create_line(cx, cy - half - px(36), cx, cy - half - px(4), fill=CYAN, width=2)
            c.create_line(cx, guide_bot + px(4), cx, guide_bot + px(36), fill=CYAN, width=2)
        mode = _t("С ПЕРЕВОДОМ") if tr_on else _t("РЕЖИМ ФОКУСА")
        c.create_text(px(46), px(22), text=_t("ГИПЕРДРАЙВ · {0}").format(self.title.upper()), anchor="w",
                      fill=blend(CYAN, BG, 0.35), font=theme.font(9, True))
        c.create_text(w - px(46), px(22), text=f"{mode} · {_t('ЩЕЛЧОК / ПРОБЕЛ — ПАУЗА')}", anchor="e",
                      fill=AMBER if tr_on else FAINT, font=theme.font(8, True))
        c.create_text(cx, h - px(28), text=_t("ПРОБЕЛ — ПАУЗА · ↑ ↓ — СКОРОСТЬ · ← — НАЗАД НА ПРЕДЛОЖЕНИЕ · 1–5 — СЛОВ ЗА КАДР · + − ШРИФТ · ENTER — ФИНИШ · ESC — ВЫХОД"),
                      fill=FAINT, font=theme.font(8, True))
        f = self._font(fs)
        for tag, anchor in (("wl", "e"), ("wc", "center"), ("wr", "w")):
            c.create_text(cx, cy, text="", anchor=anchor, font=f, tags=tag,
                          fill=RED if tag == "wc" and self.st["orp"] else TEXT)
        tr_sz = max(14, int(fs * 0.42))
        c.create_text(cx, cy + half + px(8), text="", anchor="n", fill=CYAN,
                      font=theme.font(tr_sz, True), tags="wtr")
        c.create_text(w - m - px(16), bot - px(42), text="", anchor="e", fill=CYAN,
                      font=theme.font(24, True, mono=True), tags="wpm")
        c.create_text(w - m - px(16), bot - px(18), text="", anchor="e", fill=MUTED,
                      font=theme.font(8, True), tags="wpmsub")
        c.create_text(m, bot + px(22), text="", anchor="w", fill=MUTED, font=theme.font(8, True), tags="route")
        c.create_text(w - m, bot + px(22), text="", anchor="e", fill=AMBER, font=theme.font(8, True),
                      tags="ramp")
        c.create_rectangle(m, bot + px(36), w - m, bot + px(42), fill=BG2, outline=LINE)
        c.create_rectangle(m, bot + px(36), m, bot + px(42), fill=CYAN, outline="", tags="bar")
        if self.state == "run" and self._frame:
            self._draw_word()
            self._draw_hud()

    def _draw_word(self) -> None:
        c = self.run_view
        if not self._frame:
            return
        text, k = rsvp.frame_text(self.words, self._frame)
        _w, _h, cx, cy = self._geom()
        f = self._font()
        left, mid, right = text[:k], text[k:k + 1], text[k + 1:]
        if not self.st["orp"]:
            wid = f.measure(text)
            left, mid, right = "", "", text
            c.coords("wr", cx - wid / 2, cy)
        else:
            half = f.measure(mid) / 2
            c.coords("wl", cx - half, cy)
            c.coords("wc", cx, cy)
            c.coords("wr", cx + half, cy)
        c.itemconfigure("wl", text=left)
        c.itemconfigure("wc", text=mid)
        c.itemconfigure("wr", text=right)
        if self._translate_on():
            self._request_word_tr()
            # гипердрайв: не ждём и не мигаем «…» — пусто или готовый перевод
            shown = self._tr_text if self._tr_text and self._tr_text not in ("…", "?") else ""
            if len(shown) > 72:
                shown = shown[:69].rstrip() + "…"
            c.itemconfigure("wtr", text=shown)
            half = f.metrics("linespace") / 2 + px(8)
            c.coords("wtr", cx, cy + half)
        else:
            c.itemconfigure("wtr", text="")

    def _draw_hud(self) -> None:
        c = self.run_view
        w, _h, _cx, _cy = self._geom()
        r = self.ramp
        c.itemconfigure("wpm", text=f"{int(r.wpm)}")
        c.itemconfigure("wpmsub", text=_t("СЛОВ / МИН") + (_t(" · ↗ К {0}").format(int(r.target)) if r.ramping else ""))
        n = len(self.words)
        pct = self.pos / n * 100 if n else 0
        c.itemconfigure("route", text=_t("МАРШРУТ  {0:,} / {1:,} СЛОВ · {2:.0f}%").format(self.pos, n, pct).replace(",", " "))
        st = self.st
        if st["ramp"] == "smooth":
            rt = _t("РАЗГОН +{0} СЛОВ/МИН КАЖДЫЕ {1} С").format(st['ramp_step'], st['ramp_every_s'])
        elif st["ramp"] == "steps":
            rt = _t("РАЗГОН +50 КАЖДЫЕ 500 СЛОВ")
        else:
            rt = _t("ПОСТОЯННАЯ СКОРОСТЬ")
        if r.mode != "off" and not r.ramping and r.wpm < r.target:
            rt = _t("ПЛАТО · РАЗГОН НА ПАУЗЕ 2 МИН")
        c.itemconfigure("ramp", text=rt)
        m = px(40)
        c.coords("bar", m, c.coords("bar")[1], m + (w - 2 * m) * pct / 100, c.coords("bar")[3])

    # ------------------------------------------------------------------ pause view
    def _build_pause(self) -> None:
        pv = self.pause_view
        pv.grid_rowconfigure(0, weight=1)
        pv.grid_columnconfigure(0, weight=1)
        pv.grid_columnconfigure(1, weight=1)
        left = HudPanel(pv, _t("ОРИГИНАЛ · ПАУЗА"), accent=AMBER)
        left.grid(row=0, column=0, sticky="nsew", padx=(px(14), px(4)), pady=(px(6), px(6)))
        self.ctx_panel = left
        self.ctx_title = L(left.body, "", fg=MUTED, size=8, bold=True)
        self.ctx_title.pack(anchor="e")
        self.ctx_text = tk.Text(left.body, wrap=tk.WORD, bg=BG2, fg=MUTED, relief=tk.FLAT, padx=px(18),
                                pady=px(12), font=theme.font(12), highlightthickness=0, cursor="hand2",
                                spacing1=px(2), spacing3=px(6))
        self.ctx_text.pack(fill=tk.BOTH, expand=True)
        t = self.ctx_text
        for tag, kw in (("far", {"foreground": FAINT}), ("near", {"foreground": MUTED}),
                        ("sent", {"foreground": TEXT}),
                        ("cur", {"foreground": TEXT, "background": blend(RED, BG, 0.80), "underline": True}),
                        ("orp", {"foreground": RED}),
                        ("mark", {"foreground": AMBER, "font": theme.font(10, True), "justify": "center"})):
            t.tag_configure(tag, **kw)
        t.bind("<Button-1>", self._ctx_click)
        t.bind("<Key>", lambda _e: "break")

        mid = HudPanel(pv, _t("ПЕРЕВОД"), accent=CYAN)
        mid.grid(row=0, column=1, sticky="nsew", padx=(px(4), px(4)), pady=(px(6), px(6)))
        self.tr_panel = mid
        self.tr_title = L(mid.body, "", fg=MUTED, size=8, bold=True)
        self.tr_title.pack(anchor="e")
        self.tr_text = tk.Text(mid.body, wrap=tk.WORD, bg=BG2, fg=MUTED, relief=tk.FLAT, padx=px(18),
                               pady=px(12), font=theme.font(12), highlightthickness=0,
                               spacing1=px(2), spacing3=px(6))
        self.tr_text.pack(fill=tk.BOTH, expand=True)
        self.tr_text.tag_configure("body", foreground=TEXT)
        self.tr_text.tag_configure("wait", foreground=AMBER)
        self.tr_text.tag_configure("mark", foreground=CYAN, font=theme.font(10, True), justify="center")
        self.tr_text.bind("<Key>", lambda _e: "break")

        right = tk.Frame(pv, bg=BG, width=px(300))
        right.grid(row=0, column=2, sticky="ns", padx=(px(4), px(14)), pady=(px(6), px(6)))
        right.grid_propagate(False)
        self._pause_side = right
        sp = HudPanel(right, _t("СКОРОСТЬ"))
        sp.pack(fill=tk.X)
        sp.configure(height=px(140))
        sp.pack_propagate(False)
        row = tk.Frame(sp.body, bg=PANEL)
        row.pack(pady=(px(4), 0))
        HudButton(row, "▼", lambda: self.speed(-25), width=50, height=46, font_size=15).pack(side=tk.LEFT)
        midf = tk.Frame(row, bg=PANEL)
        midf.pack(side=tk.LEFT, padx=px(10))
        self.lbl_wpm = L(midf, "300", fg=CYAN, size=28, bold=True, mono=True)
        self.lbl_wpm.pack()
        L(midf, _t("СЛОВ / МИН"), fg=MUTED, size=8, bold=True).pack()
        HudButton(row, "▲", lambda: self.speed(25), width=50, height=46, font_size=15).pack(side=tk.LEFT)
        self.lbl_ramp = L(sp.body, "", fg=AMBER, size=8, bold=True)
        self.lbl_ramp.pack(pady=(px(4), 0))
        fp = HudPanel(right, _t("НАСТРОЙКИ ПОЛЁТА"))
        fp.pack(fill=tk.X, pady=(px(8), 0))
        fb = fp.body

        def line(title):
            r = tk.Frame(fb, bg=PANEL)
            r.pack(fill=tk.X, pady=px(2))
            L(r, title, fg=MUTED, size=8, bold=True).pack(side=tk.LEFT)
            return r
        r = line(_t("ШРИФТ"))
        HudButton(r, "A+", lambda: self.font_size(+4), height=26, font_size=9, width=40).pack(side=tk.RIGHT)
        self.lbl_font = L(r, "", fg=CYAN, size=11, bold=True, mono=True, width=4)
        self.lbl_font.pack(side=tk.RIGHT)
        HudButton(r, "A−", lambda: self.font_size(-4), height=26, font_size=9, width=40).pack(side=tk.RIGHT)
        r = line(_t("СЛОВ ЗА КАДР"))
        self.chunk_btns = {}
        for n in (5, 4, 3, 2, 1):
            b = HudButton(r, str(n), lambda n=n: self.set_chunk(n), height=26, font_size=9, width=30)
            b.pack(side=tk.RIGHT, padx=1)
            self.chunk_btns[n] = b
        self.toggles = {}
        self._stream_btns = {}
        toggle_keys = [("orp", _t("КРАСНАЯ БУКВА (ORP)")), ("punct_pauses", _t("ПАУЗЫ НА ЗНАКАХ")),
                       ("ramp", _t("ПЛАВНЫЙ РАЗГОН")), ("guides", _t("ПРИЦЕЛ"))]
        if not self._is_bilingual_book():
            toggle_keys.append(("rsvp_translate", _t("ПЕРЕВОД ПОД СЛОВОМ")))
        for key, title in toggle_keys:
            r = line(title)
            val = self.st[key] != "off" if key == "ramp" else bool(self.st.get(key))
            tg = Toggle(r, val, lambda v, k=key: self._toggle(k, v), width=70)
            tg.pack(side=tk.RIGHT)
            self.toggles[key] = tg
        if self._is_bilingual_book():
            r = line(_t("ЯЗЫК ПОТОКА"))
            m = self._book_meta() or {}
            bi = m.get("bilingual") or {}
            la = (bi.get("lang_a") or "A").upper()
            lb = (bi.get("lang_b") or "B").upper()
            # если в метаданных ошибочно один код — подписи «ОРИГ / ПЕР», чтобы потоки различались
            if la == lb:
                lab_a, lab_b = _t("ОРИГ"), _t("ПЕР")
            else:
                lab_a, lab_b = la, lb
            for stream, lab in (("a", lab_a), ("b", lab_b)):
                b = HudButton(r, lab, lambda s=stream: self._set_rsvp_stream(s), height=26,
                              font_size=9, width=48, active=(self._rsvp_stream() == stream))
                b.pack(side=tk.RIGHT, padx=1)
                self._stream_btns[stream] = b
        tp = HudPanel(right, _t("ТЕЛЕМЕТРИЯ СЕССИИ"), accent=LINE_HI)
        tp.pack(fill=tk.BOTH, expand=True, pady=(px(8), 0))
        self.lbl_tele = L(tp.body, "", fg=TEXT, size=9, mono=True, justify="left", anchor="nw")
        self.lbl_tele.pack(fill=tk.BOTH, expand=True)
        acts = tk.Frame(pv, bg=BG)
        acts.grid(row=1, column=0, columnspan=3, sticky="w", padx=px(14), pady=(0, px(8)))
        self.btn_go = HudButton(acts, _t("▶ ПРОДОЛЖИТЬ  ·  ПРОБЕЛ"), self.resume, color=AMBER, height=42,
                                font_size=11, active=True)
        self.btn_go.pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("⟲ НАЗАД  ←"), lambda: self.jump("sent", -1), height=42, font_size=10).pack(side=tk.LEFT, padx=px(3))
        HudButton(acts, _t("⇤ В НАЧАЛО ГЛАВЫ  HOME"), lambda: self.jump("chapter", -1), height=42,
                  font_size=10).pack(side=tk.LEFT, padx=px(3))
        HudButton(acts, _t("✓ ФИНИШ + ТЕСТ  ENTER"), lambda: self.finish(end=False), color=GREEN, height=42,
                  font_size=10).pack(side=tk.LEFT, padx=px(3))
        HudButton(acts, _t("📖 КНИГА"), lambda: self.ctx.open_current_book(), color=GREEN, height=42,
                  font_size=10).pack(side=tk.LEFT, padx=px(3))
        HudButton(acts, _t("БИБЛИОТЕКА"), lambda: self.ctx.show("library"), height=42,
                  font_size=10).pack(side=tk.LEFT, padx=px(3))
        self.lbl_sync = L(acts, "", fg=AMBER, size=9, bold=True, bg=BG)
        self.lbl_sync.pack(side=tk.LEFT, padx=px(10))
        self._layout_pause_panels()

    def _layout_pause_panels(self) -> None:
        """Один столбец контекста или оригинал | перевод."""
        pv = self.pause_view
        if self._translate_on():
            pv.grid_columnconfigure(0, weight=1)
            pv.grid_columnconfigure(1, weight=1)
            self.ctx_panel.title = _t("ОРИГИНАЛ · ПАУЗА")
            self.tr_panel.grid()
        else:
            pv.grid_columnconfigure(0, weight=1)
            pv.grid_columnconfigure(1, weight=0)
            self.ctx_panel.title = _t("ОБЗОР КОНТЕКСТА · ПАУЗА")
            self.tr_panel.grid_remove()
        self.ctx_panel._draw()
        self.tr_panel._draw()

    def _show_pause(self, reason: str = "") -> None:
        self.state = "pause" if self.words else "idle"
        self._layout_pause_panels()
        self.pause_view.tkraise()
        self._fill_context()
        self._update_controls()
        self._update_sync_hint()
        if self._translate_on():
            self._start_tr_poll()
            self._fill_pause_translation()
        else:
            self._stop_tr_poll()

    def _fill_context(self) -> None:
        t = self.ctx_text
        t.configure(state=tk.NORMAL)
        t.delete("1.0", tk.END)
        self._ctx_base = 0
        self._ctx_chunk = ""
        if not self.words:
            t.insert(tk.END, _t("Текст не выбран. Откройте БИБЛИОТЕКУ и нажмите «ЧИТАТЬ»."), "near")
            return
        i = min(self.pos, len(self.words) - 1)
        a = max(0, rsvp.paragraph_start(self.words, max(0, i - 160)))
        b = min(len(self.words) - 1, i + 160)
        while b < len(self.words) - 1 and not self.words[b].para_end:
            b += 1
        s0, s1 = self.words[a].start, self.words[b].end
        self._ctx_base = s0
        sent_a = rsvp.sentence_start(self.words, i)
        sent_b = rsvp.next_sentence(self.words, i)
        chunk = self.text[s0:s1]
        self._ctx_chunk = chunk
        t.insert(tk.END, chunk)

        def idx(ch):  # абсолютный символ → индекс Text
            return f"1.0 + {ch - s0} chars"
        near_a = self.words[max(a, i - 60)].start
        near_b = self.words[min(b, i + 60)].end
        t.tag_add("far", "1.0", tk.END)
        t.tag_add("near", idx(near_a), idx(near_b))
        sb_end = self.words[sent_b - 1].end if sent_b > sent_a else self.words[i].end
        t.tag_add("sent", idx(self.words[sent_a].start), idx(sb_end))
        w = self.words[i]
        t.tag_add("cur", idx(w.start), idx(w.end))
        if self.st["orp"]:
            k = rsvp.orp_index(w.text)
            t.tag_add("orp", idx(w.start + k), idx(w.start + k + 1))
        t.tag_raise("cur")
        t.tag_raise("orp")
        line_start = t.index(f"{idx(self.words[sent_a].start)} linestart")
        t.insert(line_start, _t("❚❚  ПАУЗА · ОСТАНОВКА НА СЛОВЕ {0:,}\n").format(i + 1).replace(",", " "), "mark")
        t.see(idx(w.start))
        t.yview_scroll(-3, "units")
        n = len(self.words)
        self.ctx_title.configure(text=f"{self.title.upper()} · {self.pos / n * 100:.0f}%"
                                 + (_t("  · ⚠ БЕЗ ОРИГИНАЛА (текст без заглавных и знаков)") if self.no_original else ""))
        if self._translate_on():
            self._fill_pause_translation()

    def _ctx_click(self, e) -> str:
        if not self.words:
            return "break"
        t = self.ctx_text
        idx = t.index(f"@{e.x},{e.y}")
        before = t.get("1.0", idx)
        mark = t.tag_ranges("mark")
        off = len(before)
        if mark:
            mlen = len(t.get(mark[0], mark[1]))
            if t.compare(idx, ">=", mark[1]):
                off -= mlen
        ch = self._ctx_base + off
        j = bisect.bisect_right(self.starts, ch) - 1
        self.pos = max(0, min(j, len(self.words) - 1))
        self.resume()
        return "break"

    def _update_controls(self) -> None:
        if self.ramp:
            self.lbl_wpm.configure(text=str(int(self.ramp.wpm)))
            st = self.st
            self.lbl_ramp.configure(text=_t("СТАРТ {0} → ЦЕЛЬ {1} · ШАГ ±25  ↑ ↓").format(st['wpm_start'], st['wpm_target']))
        self.lbl_font.configure(text=str(self.st["font_pt"]))
        for n, b in self.chunk_btns.items():
            b.set_active(n == int(self.st["chunk"]))
        s = self.sess
        if s:
            avg = s["words"] / s["secs"] * 60 if s["secs"] else 0
            mm, ss = divmod(int(s["secs"]), 60)
            self.lbl_tele.configure(text=_t("ВРЕМЯ В ПОЛЁТЕ   {0:02d}:{1:02d}\nСРЕДНЯЯ СКОРОСТЬ {2:5.0f}\nПРОЧИТАНО СЛОВ   {3:5d}").format(mm, ss, avg, s['words']))
        else:
            self.lbl_tele.configure(text=_t("СЕССИЯ ЕЩЁ НЕ НАЧАТА\nПРОБЕЛ — СТАРТ"))

    def _update_sync_hint(self) -> None:
        self.lbl_sync.configure(text="")
        self._sync_word = None
        if not self.tid or self.st.get("sync") == "off":
            return
        tw = self.ctx.lib.typing_word(self.tid)
        if tw is not None and tw > self.pos + 5:
            pct = tw / max(1, len(self.words)) * 100
            if self.st.get("sync") == "auto":
                self.pos = tw
                self._fill_context()
                return
            self._sync_word = tw
            self.lbl_sync.configure(text=_t("В ПЕЧАТИ ВЫ ДАЛЬШЕ: {0:.0f}% · S — ПРОДОЛЖИТЬ С ЭТОГО МЕСТА").format(pct),
                                    cursor="hand2")
            self.lbl_sync.bind("<Button-1>", lambda _e: self.sync_from_typing())

    def sync_from_typing(self) -> None:
        if getattr(self, "_sync_word", None) is not None:
            self.pos = self._sync_word
            self._save_pos()
            self._show_pause()

    # ------------------------------------------------------------------ controls
    def speed(self, delta: int) -> None:
        if self.ramp:
            self.ramp.manual(delta)
            self._update_controls()
            if self.state == "run":
                self._draw_hud()

    def font_size(self, delta: int) -> None:
        self.st["font_pt"] = max(24, min(120, int(self.st["font_pt"]) + delta))
        self.ctx.sstore.save()
        self._update_controls()
        self._draw_run(full=True)

    def set_chunk(self, n: int) -> None:
        self.st["chunk"] = n
        self.ctx.sstore.save()
        self._update_controls()

    def _toggle(self, key: str, value: bool) -> None:
        if key == "ramp":
            self.st["ramp"] = "smooth" if value else "off"
            if self.ramp:
                self.ramp.mode = self.st["ramp"]
        else:
            self.st[key] = value
        self.ctx.sstore.save()
        if key == "rsvp_translate":
            self._refresh_tr_dir()
            self._layout_pause_panels()
        self._draw_run(full=True)
        if self.state == "pause":
            self._show_pause()

    def _set_rsvp_stream(self, stream: str) -> None:
        """Переключить язык потока для двуязычной книги (перезагрузка текста)."""
        stream = "b" if stream == "b" else "a"
        if self.st.get("rsvp_bilingual_stream") == stream and self.tid:
            for s, b in getattr(self, "_stream_btns", {}).items():
                b.set_active(s == stream)
            return
        self.st["rsvp_bilingual_stream"] = stream
        self.ctx.sstore.save()
        if self.tid:
            pos = self.pos
            self.open(self.tid, word=pos)

    # ------------------------------------------------------------------ translation
    def _translator(self):
        try:
            return self.ctx.app.get_translator()
        except Exception:
            return None

    def _request_word_tr(self) -> None:
        """Перевод текущего кадра (слово/фраза) — короткий ключ, успевает к следующему кадру."""
        if not self._frame:
            return
        frame_text, _ = rsvp.frame_text(self.words, self._frame)
        src = _bare(frame_text)
        if not src:
            return
        tr = self._translator()
        if tr is None:
            self._tr_text = ""
            return
        sl, tl = self._tr_dir
        # тот же кадр — только обновить из кэша
        if src == self._tr_src:
            hit = tr.cached(src, sl, tl)
            if hit:
                self._tr_text = hit
            return
        self._tr_src = src
        self._tr_key = tr.key(src, sl, tl)
        cached = tr.cached(src, sl, tl)
        self._tr_text = cached or ""
        # сначала срочный текущий кадр, потом prefetch — иначе cancel снесёт живое
        if not cached:
            tr.request(src, sl, tl, priority=0, group="rsvp")
        keep = {self._tr_key}
        pos = self._frame[-1] + 1
        n = int(self.st.get("chunk") or 1)
        max_ch = int(self.st.get("chunk_max_chars") or 24)
        for pref_i in range(4):
            if pos >= len(self.words):
                break
            nxt = rsvp.frame_at(self.words, pos, n, max_ch)
            if not nxt:
                break
            nxt_src = _bare(rsvp.frame_text(self.words, nxt)[0])
            if nxt_src:
                keep.add(tr.key(nxt_src, sl, tl))
                if not tr.cached(nxt_src, sl, tl):
                    tr.request(nxt_src, sl, tl, priority=1 + pref_i, group="rsvp")
            pos = nxt[-1] + 1
        tr.cancel_group("rsvp", keep=keep)

    def _show_word_tr(self, text: str) -> None:
        if self.state != "run" or not text:
            return
        shown = text if len(text) <= 72 else text[:69].rstrip() + "…"
        try:
            self.run_view.itemconfigure("wtr", text=shown)
        except tk.TclError:
            pass

    def _start_tr_poll(self) -> None:
        self._stop_tr_poll()
        if not self._translate_on():
            return
        self._tr_poll_tick()

    def _stop_tr_poll(self) -> None:
        if self._tr_poll_job is not None:
            try:
                self.after_cancel(self._tr_poll_job)
            except tk.TclError:
                pass
            self._tr_poll_job = None

    def _tr_poll_tick(self) -> None:
        self._tr_poll_job = None
        if not self._translate_on() or self.state not in ("run", "pause"):
            return
        tr = self._translator()
        if tr is not None:
            results = tr.poll()
            if self._tr_src:
                sl, tl = self._tr_dir
                hit = tr.cached(self._tr_src, sl, tl)
                if hit and hit != self._tr_text:
                    self._tr_text = hit
                    self._show_word_tr(hit)
                elif not hit:
                    for key, result in results:
                        if key == self._tr_key and result:
                            self._tr_text = result
                            self._show_word_tr(result)
                            break
            if self.state == "pause" and results:
                self._fill_pause_translation()
        self._tr_poll_job = self.after(80, self._tr_poll_tick)

    def _fill_pause_translation(self) -> None:
        tt = self.tr_text
        tt.configure(state=tk.NORMAL)
        tt.delete("1.0", tk.END)
        sl, tl = self._tr_dir
        self.tr_title.configure(text=f"{sl.upper()} → {tl.upper()}")
        chunk = getattr(self, "_ctx_chunk", "") or ""
        if not chunk.strip():
            tt.insert(tk.END, _t("Нет текста для перевода."), "wait")
            return
        tr = self._translator()
        if tr is None:
            tt.insert(tk.END, _t("Переводчик недоступен."), "wait")
            return
        parts = [p.strip() for p in _SENT_SPLIT.split(chunk.replace("\n", " ")) if p.strip()]
        if not parts:
            parts = [chunk.strip()]
        waiting = False
        lines = []
        keep: set[str] = set()
        for i, p in enumerate(parts[:24]):
            src = p[:500]
            keep.add(tr.key(src, sl, tl))
            cached = tr.cached(src, sl, tl)
            if cached:
                lines.append(cached)
            else:
                tr.request(src, sl, tl, priority=(0 if i < 3 else 4), group="rsvp")
                waiting = True
                lines.append("…")
        tr.cancel_group("rsvp", keep=keep)
        tt.insert(tk.END, _t("❚❚  ПЕРЕВОД КОНТЕКСТА\n"), "mark")
        tt.insert(tk.END, "\n\n".join(lines), "body" if not waiting else "wait")
        if waiting:
            tt.insert(tk.END, "\n\n" + _t("(идёт перевод — появится по сети или из кэша)"), "wait")

    def jump(self, kind: str, direction: int) -> None:
        if not self.words:
            return
        i = min(self.pos, len(self.words) - 1)
        if kind == "sent":
            self.pos = rsvp.prev_sentence(self.words, i) if direction < 0 else rsvp.next_sentence(self.words, i)
        elif kind == "para":
            if direction < 0:
                self.pos = rsvp.paragraph_start(self.words, max(0, rsvp.paragraph_start(self.words, i) - 1))
            else:
                j = i
                while j < len(self.words) - 1 and not self.words[j].para_end:
                    j += 1
                self.pos = min(len(self.words) - 1, j + 1)
        elif kind == "chapter":
            c = rsvp.chapter_start(self.words, i)
            self.pos = rsvp.paragraph_start(self.words, i) if c == 0 else c
        self._save_pos()
        if self.state == "run":
            self._frame = rsvp.frame_at(self.words, self.pos, int(self.st["chunk"]))
            self._draw_word()
            self._cancel()
            self._next_t = time.perf_counter() + 1.0
            self._job = self.after(1000, self._step)
        else:
            self._fill_context()

    # ------------------------------------------------------------------ keys
    def on_key(self, e) -> None:
        k = e.keysym
        if self.state in ("quiz", "done"):
            if k in ("1", "2", "3", "4") and getattr(self, "_quiz_choices", None):
                i = int(k) - 1
                if i < len(self._quiz_choices):
                    self._quiz_answer(i)
            elif k == "Return" and getattr(self, "_quiz_next", None):
                self._quiz_next()
            elif k == "Escape":
                self._end_quiz(skip=True)
            return
        if k == "space":
            self.toggle()
        elif k == "Up":
            self.speed(25)
        elif k == "Down":
            self.speed(-25)
        elif k in ("Left", "Right"):
            shift = bool(e.state & 0x0001)
            self.jump("para" if shift else "sent", -1 if k == "Left" else 1)
        elif k == "Home":
            self.jump("chapter", -1)
        elif k in ("1", "2", "3", "4", "5"):
            self.set_chunk(int(k))
        elif k in ("plus", "equal", "KP_Add"):
            self.font_size(+4)
        elif k in ("minus", "KP_Subtract"):
            self.font_size(-4)
        elif k in ("r", "R", "Cyrillic_ka", "Cyrillic_KA"):
            self.toggles["orp"].set(not self.st["orp"])
            self._toggle("orp", not self.st["orp"])
        elif k in ("s", "S", "Cyrillic_yeru", "Cyrillic_YERU") and self.state != "run":
            self.sync_from_typing()
        elif k == "Return":
            self.finish(end=False)
        elif k == "Escape":
            if self.state == "run":
                self.pause()
            else:
                self.stop_session(save=True)
                self.ctx.show("overview")

    # ------------------------------------------------------------------ finish / quiz
    def finish(self, end: bool) -> None:
        self._cancel()
        self.ctx.set_focus_mode(False)
        if not self.sess or self.sess["words"] < 20:
            self.state = "pause"
            self._show_pause()
            return
        self._save_pos()
        start = max(self._quiz_from, self.pos - int(self.st["quiz_words"]) * 2)
        items = []
        if self.st["quiz"] != "never":
            from stamina.langdetect import detect      # язык самого куска: книги бывают смешанные
            lang = detect(" ".join(w.text for w in self.words[start:self.pos][:800]))
            items = make_quiz(self.words, start, self.pos, lang)
        self._quiz_from = self.pos
        self._end_reached = end
        if not items:
            self._record_session(comp=None)
            self._debrief(None)
            return
        self.state = "quiz"
        self._quiz = items
        self._quiz_i = 0
        self._quiz_ok = 0
        self.quiz_view.tkraise()
        self._quiz_render()

    def _clear_quiz(self) -> None:
        for w in self.quiz_view.winfo_children():
            w.destroy()

    def _quiz_render(self) -> None:
        self._clear_quiz()
        self._quiz_next = None
        q = self._quiz[self._quiz_i]
        p = HudPanel(self.quiz_view, _t("ДЕБРИФИНГ · ПРОВЕРКА ПОНИМАНИЯ · {0} / {1}").format(self._quiz_i + 1, len(self._quiz)),
                     accent=AMBER)
        p.pack(fill=tk.BOTH, expand=True, padx=px(120), pady=px(30))
        L(p.body, q["question"], fg=TEXT, size=14, justify="left", wraplength=px(760)).pack(anchor="w", pady=(px(16), px(16)))
        self._quiz_choices = []
        for i, opt in enumerate(q["options"]):
            ch = Choice(p.body, i + 1, opt, lambda i=i: self._quiz_answer(i))
            ch.pack(fill=tk.X, pady=px(4))
            self._quiz_choices.append(ch)
        self._quiz_status = L(p.body, _t("1–4 — ответ · ESC — пропустить проверку"), fg=MUTED, size=9, bold=True)
        self._quiz_status.pack(anchor="w", pady=(px(14), 0))

    def _quiz_answer(self, i: int) -> None:
        q = self._quiz[self._quiz_i]
        if self._quiz_next is not None:
            return
        ok = i == q["answer"]
        self._quiz_ok += ok
        for j, ch in enumerate(self._quiz_choices):
            ch.mark("ok" if j == q["answer"] else ("bad" if j == i else "dim"))

        def nxt():
            self._quiz_i += 1
            if self._quiz_i >= len(self._quiz):
                self._end_quiz()
            else:
                self._quiz_render()
        self._quiz_next = nxt
        self._quiz_status.configure(text=(_t("✓ ВЕРНО") if ok else _t("✕ НЕВЕРНО")) + _t(" · ENTER — ДАЛЕЕ"),
                                    fg=GREEN if ok else RED)
        self.after(900 if ok else 1600, lambda: self._quiz_next is nxt and nxt())

    def _end_quiz(self, skip: bool = False) -> None:
        comp = None if skip else self._quiz_ok / max(1, len(self._quiz))
        rec = self._record_session(comp)
        self._debrief(comp, rec)

    def _record_session(self, comp):
        s = self.sess
        if not s or s["words"] < 20 or not self.tid:
            self.sess = None
            return None
        avg = s["words"] / s["secs"] * 60 if s["secs"] else 0
        rec = {"text": self.tid, "title": self.title, "words": s["words"], "secs": round(s["secs"], 1),
               "avg_wpm": round(avg), "max_wpm": round(s["max"]), "comp": comp}
        self.ctx.sstore.add_session(rec)
        rec = self.ctx.sstore.last_sessions(1)[-1]   # с полями stars, eff_wpm, xp
        self.sess = None
        self.ctx.changed()
        return rec

    def _debrief(self, comp, rec=None) -> None:
        self.state = "done"
        self._clear_quiz()
        self.quiz_view.tkraise()
        rec = rec or (self.ctx.sstore.last_sessions(1) or [None])[-1]
        ok = comp is None or comp >= 0.6
        p = HudPanel(self.quiz_view, _t("ОТЧЁТ О ПОЛЁТЕ · ГИПЕРДРАЙВ"), accent=GREEN if ok else AMBER)
        p.pack(fill=tk.BOTH, expand=True, padx=px(160), pady=px(40))
        L(p.body, _t("МИССИЯ ВЫПОЛНЕНА") if ok else _t("ПОВТОРИТЕ ЗАХОД"), fg=GREEN if ok else AMBER, size=24,
          bold=True).pack(pady=(px(20), px(6)))
        if rec:
            stars = rec.get("stars", 0)
            L(p.body, "★" * stars + "☆" * (3 - stars), fg=AMBER, size=22).pack()
            rows = [(_t("СРЕДНЯЯ СКОРОСТЬ"), _t("{0} сл/мин").format(rec['avg_wpm'])), (_t("МАКС. СКОРОСТЬ"), _t("{0} сл/мин").format(rec['max_wpm'])),
                    (_t("ПРОЧИТАНО СЛОВ"), str(rec["words"])),
                    (_t("ПОНИМАНИЕ"), f"{comp * 100:.0f}%" if comp is not None else _t("— (без проверки)")),
                    (_t("ЭФФЕКТИВНАЯ СКОРОСТЬ"), f"{rec.get('eff_wpm') or '—'}"),
                    (_t("ОПЫТ"), f"+{rec.get('xp', 0)} XP")]
            g = tk.Frame(p.body, bg=PANEL)
            g.pack(pady=px(14))
            for i, (a, b) in enumerate(rows):
                L(g, a, fg=MUTED, size=9, bold=True).grid(row=i, column=0, sticky="w", padx=px(10), pady=px(3))
                L(g, b, fg=AMBER if a == _t("ОПЫТ") else CYAN, size=13, bold=True, mono=True).grid(
                    row=i, column=1, sticky="e", padx=px(10))
            if comp is not None and comp < 0.6:
                L(p.body, _t("Совет: понимание ниже 60% — снизьте целевую скорость на 50 и повторите."),
                  fg=AMBER, size=10).pack()
        acts = tk.Frame(p.body, bg=PANEL)
        acts.pack(pady=px(14))
        if not getattr(self, "_end_reached", False):
            HudButton(acts, _t("▶ ЧИТАТЬ ДАЛЬШЕ"), self._continue_after, color=AMBER, height=40,
                      font_size=11, active=True).pack(side=tk.LEFT, padx=px(4))
        HudButton(acts, _t("ОБЗОР"), lambda: self.ctx.show("overview"), height=40).pack(side=tk.LEFT, padx=px(4))
        HudButton(acts, _t("БИБЛИОТЕКА"), lambda: self.ctx.show("library"), height=40).pack(side=tk.LEFT, padx=px(4))
        self._quiz_next = self._continue_after if not getattr(self, "_end_reached", False) else None

    def _continue_after(self) -> None:
        self.state = "pause"
        self._show_pause()
        self.resume()

