"""Портал «Слепой печати» (дзен-режим, Ctrl+M): экран набора в духе известного
минималистичного тренажёра — шапка, панель режимов, строка языка, три строки слов,
подсказки клавиш и подвал. Своя реализация на Tk; логотип и название — Star Typing.

Текст — с текущей позиции мостика (слова берутся из текста «Полёта», сам мостик не
трогается). Поведение набора — stamina/zen_engine.py. Вход/выход — мгновенно:
Ctrl+M, двойной Esc (одиночный — заново), значок «⟵ на борт» в углу. Итоги теста
пишутся локально (stamina/portal_stats.py); профиль сайта подтягивается только на
чтение (monkeytype.auto_sync), не чаще раза в 5 минут.
"""
from __future__ import annotations

import time
import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.account_view import blend, rrect
from stamina.i18n import t
from stamina.zen_engine import COUNTS, PortalTest, prepare_words, quote_slice

HOTKEY_LABEL = "Ctrl+M"
ESC_DOUBLE_MS = 400   # Esc Esc быстрее этого — выход на борт

SERIKA_DARK = {   # палитра «serika dark»
    "bg": "#323437", "sub": "#646669", "subalt": "#2c2e31", "text": "#d1d0c5",
    "main": "#e2b714", "caret": "#e2b714", "error": "#ca4754", "extra": "#7e2a33",
}
PALETTES = ("serika", "skin")
FONT_FILE = "stamina/assets/fonts/roboto_mono/RobotoMono-VariableFont_wght.ttf"
FALLBACK_WORDS = ("the of and to in is you that it he was for on are as with his they at be this have "
                  "from or one had by word but not what all were we when your can said there use an each "
                  "which she do how their if will up other about out many then them these so some her "
                  "would make like him into time has look two more write go see number no way could people "
                  "my than first water been call who oil its now find long down day did get come made may part").split()


def _palette(name: str = "serika") -> dict[str, str]:
    if name != "skin":
        return dict(SERIKA_DARK)
    bg = theme.c("bg")
    return {"bg": bg, "sub": theme.blend(theme.c("muted"), bg, 0.25), "subalt": theme.blend(theme.c("panel"), bg, 0.5),
            "text": theme.c("text"), "main": theme.c("accent"), "caret": theme.c("accent"),
            "error": theme.c("error"), "extra": theme.blend(theme.c("error"), bg, 0.45)}


def _mono_family() -> str:
    theme._register_font_files({"fonts": {"files": [FONT_FILE]}})
    try:
        fams = set(tkfont.families())
    except tk.TclError:
        fams = set()
    for f in ("Roboto Mono", "Consolas", theme.MONO_FAMILY, "DejaVu Sans Mono"):
        if f in fams:
            return f
    return theme.MONO_FAMILY


def is_zen_hotkey(e) -> bool:
    """Ctrl+M в любой раскладке (код клавиши M = 77 на Windows; keysym m/M/ь)."""
    if not (getattr(e, "state", 0) & 0x4) or (getattr(e, "state", 0) & 0x8):
        return False
    return getattr(e, "keysym", "") in ("m", "M", "Cyrillic_softsign", "Cyrillic_SOFTSIGN") \
        or getattr(e, "keycode", 0) == 77


LANGS = {"en": "english", "ru": "russian", "uk": "ukrainian", "de": "german"}


class ZenOverlay(tk.Frame):
    """Весь экран портала. Статичные элементы — на одном Canvas, слова — в Text."""

    def __init__(self, app, palette: str = "serika") -> None:
        self.pal_name = palette
        self.pal = _palette(palette)
        super().__init__(app, bg=self.pal["bg"], highlightthickness=0, bd=0)
        self.app = app
        p = self.pal
        self.fam = _mono_family()
        self.f_words = tkfont.Font(family=self.fam, size=-28)
        self.f_ui = tkfont.Font(family=self.fam, size=-13)
        self.f_small = tkfont.Font(family=self.fam, size=-11)
        self.cv = tk.Canvas(self, bg=p["bg"], highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.words = tk.Text(self.cv, bg=p["bg"], fg=p["sub"], bd=0, highlightthickness=0, wrap="word",
                             height=3, font=self.f_words, cursor="arrow", padx=0, pady=0, takefocus=0,
                             spacing1=0, spacing3=0, state="disabled")
        self.words.tag_configure("correct", foreground=p["text"])
        self.words.tag_configure("incorrect", foreground=p["error"])
        self.words.tag_configure("extra", foreground=p["extra"])
        self.words.tag_configure("untyped", foreground=p["sub"])
        self.words.tag_configure("errword", underline=True)
        self.caret = tk.Frame(self, bg=p["caret"], width=3, height=30)
        self.result = tk.Canvas(self, bg=p["bg"], highlightthickness=0, bd=0)
        self.account = None
        self.back = tk.Label(self, text=t("⟵ на борт"), bg=p["bg"], fg=p["sub"], cursor="hand2",
                             font=self.f_small, padx=6, pady=3)
        self.back.bind("<Button-1>", lambda _e: (self.app.zen.toggle(False), "break")[1])
        self._back_job = None
        self.nick_entry = None
        # состояние теста
        self.test: PortalTest | None = None
        self.src_words: list[str] = []
        self.src_pos = 0               # первое слово следующего теста
        self.top_word = 0              # первое слово на верхней видимой строке
        self.focus_mode = False
        self.tab_armed = False
        self._caret_x = self._caret_y = None
        self._caret_target = (0, 0)
        self._caret_job = None
        self._loop_job = None
        self._last_key = 0.0
        self._blink = True
        self._layout_wh = (0, 0)
        self._started_marked = False
        self.cv.bind("<Configure>", lambda _e: self._layout())
        for w in (self, self.cv, self.words, self.result):
            w.bind("<Motion>", self._motion, add="+")
            w.bind("<Button-1>", lambda _e: (self.app.focus_set(), "break")[1], add="+")
        self.load_source()
        self.new_test()

    # -- настройки -------------------------------------------------------
    @property
    def st(self) -> dict:
        return self.app.store.settings

    def mode(self) -> str:
        m = self.st.get("zen_mt_mode", "words")
        return m if m in ("time", "words", "quote", "zen", "custom") else "words"

    def count(self, mode: str | None = None) -> int:
        mode = mode or self.mode()
        d = self.st.get("zen_mt_counts") or {}
        default = {"time": 30, "words": 10, "custom": 50}.get(mode, 0)
        try:
            return max(1, int(d.get(mode, default)))
        except (TypeError, ValueError):
            return default

    def _save(self, **kw) -> None:
        self.st.update(kw)
        try:
            self.app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass

    # -- источник слов ---------------------------------------------------
    def _bridge(self):
        return getattr(self.app, "screens", {}).get("bridge")

    def lang(self) -> str:
        br = self._bridge()
        meta = getattr(br, "meta", None) or {}
        return LANGS.get(meta.get("text_lang") or meta.get("lang") or "en", "english")

    def load_source(self) -> None:
        br = self._bridge()
        full, pos = "", 0
        if br is not None and getattr(br, "engine", None) is not None:
            full = getattr(br, "_full_text", "") or br.engine.text
            try:
                pos = br._full_index()
            except Exception:  # noqa: BLE001
                pos = br.engine.index
            if not getattr(br, "_full_text", ""):
                pos = br.engine.index
            # с начала текущего слова
            while pos > 0 and not full[pos - 1].isspace():
                pos -= 1
        self.src_raw = full[pos:pos + 60000]
        self.src_words = prepare_words(self.src_raw, punctuation=bool(self.st.get("zen_punct")),
                                       numbers=bool(self.st.get("zen_numbers")))
        self.src_fallback = not self.src_words
        if self.src_fallback:
            self.src_words = list(FALLBACK_WORDS)
        self.src_pos = 0

    def _take(self, n: int) -> list[str]:
        out = []
        while len(out) < n:
            if self.src_pos >= len(self.src_words):
                self.src_pos = 0           # текст кончился — по кругу
            out.append(self.src_words[self.src_pos])
            self.src_pos += 1
        return out

    def new_test(self, *, same: bool = False) -> None:
        """Новый тест. same=True — те же слова (перезапуск)."""
        mode = self.mode()
        if same and self.test is not None:
            words, start = self.test.words, self._test_start
            self.src_pos = start
        else:
            start = self.src_pos
        self._test_start = start
        if mode == "time":
            n, limit = 300, self.count("time")
        elif mode == "words":
            n = limit = self.count("words")
        elif mode == "custom":
            n = limit = self.count("custom")
        elif mode == "quote":
            n = quote_slice(" ".join(self.src_words), start) or 25
            limit = n
        else:
            n, limit = min(400, max(1, len(self.src_words) - start)), 0
        words = self._take(n)
        self.test = PortalTest(words, mode=mode if mode in ("time", "words") else "words", limit=limit)
        self.test.ui_mode = mode
        self.top_word = 0
        self.focus_mode = False
        self.tab_armed = False
        self._started_marked = False
        self.result.place_forget()
        self._caret_x = None
        self.render()
        self._draw_chrome()

    def finished_test(self) -> None:
        te = self.test
        res = te.result()
        res["mode"] = te.ui_mode if te.ui_mode in ("time", "words") else te.ui_mode
        res["mode2"] = te.limit
        res["language"] = self.lang()
        try:
            from stamina import portal_stats
            portal_stats.add_result(res)
        except Exception:  # noqa: BLE001
            pass
        self.last_result = res
        self.app.zen.sync()
        self.focus_mode = False
        self.show_result(res)

    # -- раскладка -------------------------------------------------------
    def _layout(self) -> None:
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        if W < 50 or H < 50:
            return
        self._layout_wh = (W, H)
        self.colw = int(min(W * 0.84, max(W * 0.6, 1400)))
        self.col0 = (W - self.colw) // 2
        self.f_words.configure(size=-max(16, int(H * 0.042)))
        self.f_ui.configure(size=-max(11, int(H * 0.0215)))
        self.f_small.configure(size=-max(9, int(H * 0.018)))
        lh = self.f_words.metrics("linespace")
        self.words.configure(spacing3=int(lh * 0.25))
        self.words_y = int(H * 0.435)
        self.words.place(x=self.col0, y=self.words_y, width=self.colw, height=int(lh * 1.25 * 3))
        self.caret.configure(width=max(2, int(lh * 0.08)), height=int(lh * 0.95))
        self._draw_chrome()
        self.render()
        if self.account is not None:
            self.show_account()

    # -- отрисовка шапки, панели режимов и подвала ------------------------
    def _draw_chrome(self) -> None:
        cv, p = self.cv, self.pal
        cv.delete("chrome")
        if not self._layout_wh[0]:
            return
        W, H = self._layout_wh
        x0, x1 = self.col0, self.col0 + self.colw
        hide = self.focus_mode
        st = "normal"            # скрытие при наборе — в конце (bbox нужен видимым элементам)
        ui, sm = self.f_ui, self.f_small
        tags = ("chrome",)

        def text(x, y, s, fill=None, font=None, anchor="w", tag=None, hover=True, state=st):
            tg = tags + ((tag,) if tag else ())
            i = cv.create_text(x, y, text=s, fill=fill or p["sub"], font=font or ui, anchor=anchor, tags=tg, state=state)
            if tag and hover:
                cv.tag_bind(tag, "<Enter>", lambda _e, i=i, f=fill: (cv.itemconfigure(i, fill=p["text"]),
                                                                     cv.configure(cursor="hand2")))
                cv.tag_bind(tag, "<Leave>", lambda _e, i=i, f=fill: (cv.itemconfigure(i, fill=f or p["sub"]),
                                                                     cv.configure(cursor="")))
            return i

        # логотип: «клавиатура» + star typing
        hy = int(H * 0.094)
        lh = int(H * 0.036)
        lw = int(lh * 1.45)
        mid_state = "normal"
        rrect(cv, x0, hy - lh / 2, x0 + lw, hy + lh / 2, lh * 0.22, outline=p["main"], fill="",
              width=max(2, lh // 9), tags=tags + ("logo",), state=mid_state)
        kx, ky, ks = x0 + lw * 0.2, hy - lh * 0.18, lw * 0.6 / 4
        for j in range(3):
            cv.create_rectangle(kx + j * ks * 1.33, ky, kx + j * ks * 1.33 + ks * 0.8, ky + lh * 0.12,
                                fill=p["main"], outline="", tags=tags + ("logo",))
        cv.create_text(x0 + lw / 2, hy + lh * 0.16, text="✦", fill=p["main"], font=(self.fam, -int(lh * 0.42)),
                       tags=tags + ("logo",))
        logo_font = (theme.HUD_FAMILY if theme.HUD_FAMILY else self.fam, -int(H * 0.046))
        tx = x0 + lw + int(lh * 0.25)
        lid = cv.create_text(tx, hy + 1, text="star typing", anchor="w", fill=p["text"] if not hide else p["sub"],
                             font=(self.fam, -int(H * 0.044)), tags=tags + ("logo",))
        bb = cv.bbox(lid) or (tx, hy, tx + 200, hy)
        cv.create_text(bb[0] + lh * 0.1, hy - lh * 0.62, text="pilot see", anchor="w", fill=p["sub"],
                       font=(self.fam, -max(8, int(H * 0.013))), tags=tags + ("logo",), state=st)
        del logo_font
        ix = bb[2] + int(H * 0.035)
        for i, (glyph, cmd) in enumerate((("⌨", None), ("♛", self.show_account), ("ⓘ", None), ("⚙", None))):
            tag = f"nav{i}"
            text(ix, hy, glyph, font=(self.fam, -int(H * 0.026)), tag=tag)
            if cmd:
                cv.tag_bind(tag, "<Button-1>", lambda _e, c=cmd: (c(), "break")[1])
            ix += int(H * 0.055)
        # справа: колокольчик, пользователь, уровень
        nick = (self.st.get("mt_username") or "").strip() or self._pilot_name()
        lvl = self.app.zen.level()
        rx = x1
        if lvl:
            bid = cv.create_text(rx - 6, hy, text=str(lvl), anchor="e", fill=p["bg"], font=sm, tags=tags + ("user",), state=st)
            b = cv.bbox(bid)
            rrect(cv, b[0] - 5, b[1] - 1, b[2] + 5, b[3] + 1, 4, fill=p["sub"], outline="", tags=tags + ("user",), state=st)
            cv.tag_raise(bid)
            rx = b[0] - 12
        nid = text(rx, hy, nick, anchor="e", tag="user", font=sm)
        b = cv.bbox(nid)
        ux = b[0] - int(H * 0.022)
        r = int(H * 0.007)
        cv.create_oval(ux - r, hy - r * 2.2, ux + r, hy - r * 0.2, fill=p["sub"], outline="", tags=tags + ("user",), state=st)
        cv.create_arc(ux - r * 1.7, hy + r * 0.2, ux + r * 1.7, hy + r * 3.4, start=0, extent=180, fill=p["sub"],
                      outline="", tags=tags + ("user",), state=st)
        cv.tag_bind("user", "<Button-1>", lambda _e: (self.show_account(), "break")[1])
        bx = ux - int(H * 0.045)
        cv.create_polygon(bx - r * 1.4, hy + r * 1.1, bx - r, hy - r * 0.6, bx - r * 0.5, hy - r * 1.6,
                          bx + r * 0.5, hy - r * 1.6, bx + r, hy - r * 0.6, bx + r * 1.4, hy + r * 1.1,
                          smooth=True, fill=p["sub"], outline="", tags=tags, state=st)
        cv.create_oval(bx - r * 0.45, hy + r * 1.2, bx + r * 0.45, hy + r * 2.0, fill=p["sub"], outline="", tags=tags, state=st)
        if not (self.st.get("mt_username") or "").strip() and not self.st.get("mt_prompt_done"):
            text(bx - int(H * 0.03), hy, t("ваш ник на Monkeytype? ›"), anchor="e", tag="nickprompt",
                 fill=p["main"], font=sm)
            cv.tag_bind("nickprompt", "<Button-1>", lambda _e: (self.ask_nick(), "break")[1])
        # панель режимов
        cy = int(H * 0.18)
        mode = self.mode()
        groups = [[("punct", "@", "punctuation", bool(self.st.get("zen_punct"))),
                   ("numbers", "#", "numbers", bool(self.st.get("zen_numbers")))],
                  [(m, g, m, m == mode) for m, g in (("time", "◷"), ("words", "A"), ("quote", "❝"),
                                                       ("zen", "▲"), ("custom", "⚒"))]]
        if mode in COUNTS:
            groups.append([(f"n{v}", "", str(v), self.count() == v) for v in COUNTS[mode]] +
                          [("ncustom", "", "⚒", self.count() not in COUNTS[mode])])
        elif mode == "custom":
            groups.append([("ncustom", "", f"{self.count()}  ⚒", True)])
        elif mode == "quote":
            groups.append([("qall", "", "all", True)])
        pad, gsp, isp = int(H * 0.02), int(H * 0.035), int(H * 0.024)
        widths = []
        for g in groups:
            w = sum(ui.measure(((ic + " ") if ic else "") + lab) for _k, ic, lab, _a in g) + isp * (len(g) - 1) + pad * 2
            widths.append(w)
        total = sum(widths) + gsp * (len(groups) - 1)
        gx = (W - total) / 2
        bh = int(H * 0.048)
        for g, w in zip(groups, widths):
            rrect(cv, gx, cy - bh / 2, gx + w, cy + bh / 2, bh * 0.22, fill=p["subalt"], outline="", tags=tags, state=st)
            x = gx + pad
            for k, ic, lab, act in g:
                s = ((ic + " ") if ic else "") + lab
                col = p["main"] if act else p["sub"]
                text(x, cy, s, fill=col, tag=f"cfg_{k}")
                cv.tag_bind(f"cfg_{k}", "<Button-1>", lambda _e, k=k: (self._cfg(k), "break")[1])
                x += ui.measure(s) + isp
            gx += w + gsp
        # строка языка / счётчик
        ly = int(H * 0.40)
        typing = self.test is not None and self.test.started and not self.test.finished
        if typing:
            te = self.test
            cv.create_text(x0, ly, text=te.progress_label(), anchor="w", fill=p["main"],
                           font=(self.fam, -int(H * 0.04)), tags=tags + ("counter",))
        else:
            pace = self.app.zen.average_pace(mode, self.count())
            s = f"◍  {self.lang()}" + (f"      ◔  average pace {pace} wpm" if pace else "")
            text(W / 2, ly, s, anchor="center", tag="lang", hover=False, state="normal")
        # подсказки
        hy2 = int(H * 0.877)
        self._keyline(W / 2, hy2, [("esc", True), (" - restart test", False)], st)
        self._keyline(W / 2, hy2 + int(H * 0.03), [("tab", True), ("  or  ", False), ("ctrl + shift + p", True),
                                                   (" - command line", False)], st)
        self._keyline(W / 2, hy2 + int(H * 0.06), [("esc esc", True), (" / ", False), (HOTKEY_LABEL.lower(), True),
                                                   (" - " + t("на борт"), False)], st)
        # подвал
        fy = int(H * 0.963)
        fx = x0
        for glyph, lab in (("✉", "contact"), ("♡", "support"), ("‹›", "github"), ("◎", "discord"),
                           ("✦", "twitter"), ("☰", "terms"), ("⛨", "security"), ("◐", "privacy")):
            i = text(fx, fy, f"{glyph} {lab}", font=sm, tag=f"foot_{lab}")
            fx = (cv.bbox(i) or (0, 0, fx + 60, 0))[2] + int(H * 0.018)
        from stamina import __version__
        vid = text(x1, fy, f"⑂ v{__version__}", anchor="e", font=sm, tag="ver")
        vb = cv.bbox(vid)
        pid = text(vb[0] - int(H * 0.03), fy, "◐ " + ("serika dark" if self.pal_name != "skin" else t("скин")),
                   anchor="e", font=sm, tag="pal")
        cv.tag_bind("pal", "<Button-1>", lambda _e: (self.app.zen.set_palette(
            "skin" if self.pal_name != "skin" else "serika"), "break")[1])
        del pid
        if hide:
            keep = set(cv.find_withtag("counter")) | set(cv.find_withtag("logo"))
            for i in cv.find_withtag("chrome"):
                if i not in keep:
                    cv.itemconfigure(i, state="hidden")

    def _keyline(self, cx, y, parts, st) -> None:
        cv, p, sm = self.cv, self.pal, self.f_small
        widths = [sm.measure(s) + (10 if key else 0) for s, key in parts]
        x = cx - sum(widths) / 2
        for (s, key), w in zip(parts, widths):
            if key:
                h = sm.metrics("linespace")
                rrect(cv, x, y - h / 2 - 1, x + w, y + h / 2 + 1, 3, fill=p["sub"], outline="", tags=("chrome",), state=st)
                cv.create_text(x + w / 2, y, text=s, fill=p["bg"], font=sm, tags=("chrome",), state=st)
            else:
                cv.create_text(x, y, text=s, anchor="w", fill=p["sub"], font=sm, tags=("chrome",), state=st)
            x += w

    def _pilot_name(self) -> str:
        pl = getattr(self.app, "pilot", None) or {}
        return str(pl.get("callsign") or pl.get("name") or "pilot")

    # -- клики по панели режимов ------------------------------------------
    def _cfg(self, k: str) -> None:
        if k in ("punct", "numbers"):
            key = "zen_punct" if k == "punct" else "zen_numbers"
            self._save(**{key: not self.st.get(key)})
            pos = self._test_start
            self.load_source()
            self.src_pos = min(pos, max(0, len(self.src_words) - 1))
            self.new_test()
        elif k in ("time", "words", "quote", "zen", "custom"):
            self._save(zen_mt_mode=k)
            self.src_pos = self._test_start
            self.new_test()
        elif k.startswith("n") and k[1:].isdigit():
            d = dict(self.st.get("zen_mt_counts") or {})
            d[self.mode()] = int(k[1:])
            self._save(zen_mt_counts=d)
            self.src_pos = self._test_start
            self.new_test()
        elif k == "ncustom":
            self.ask_count()

    def _inline_entry(self, x, y, initial: str, on_ok, width=8) -> tk.Entry:
        p = self.pal
        e = tk.Entry(self, width=width, bg=p["subalt"], fg=p["text"], insertbackground=p["caret"], relief="flat",
                     font=self.f_ui, highlightthickness=1, highlightcolor=p["main"], highlightbackground=p["sub"])
        e.insert(0, initial)
        e.select_range(0, "end")
        e.place(x=x, y=y, anchor="center")
        e.focus_set()
        self.nick_entry = e

        def done(ok: bool):
            val = e.get().strip()
            e.destroy()
            self.nick_entry = None
            self.app.focus_set()
            if ok:
                on_ok(val)
            return "break"

        e.bind("<Return>", lambda _e: done(True))
        e.bind("<KP_Enter>", lambda _e: done(True))
        e.bind("<Escape>", lambda _e: done(False))
        e.bind("<FocusOut>", lambda _e: done(False) if self.nick_entry is e else None)
        return e

    def ask_count(self) -> None:
        W, H = self._layout_wh
        mode = self.mode() if self.mode() in ("time", "words", "custom") else "words"

        def ok(v: str):
            try:
                n = max(5 if mode != "time" else 5, min(1000 if mode != "time" else 3600, int(v)))
            except ValueError:
                return
            d = dict(self.st.get("zen_mt_counts") or {})
            d[mode] = n
            self._save(zen_mt_counts=d)
            self.src_pos = self._test_start
            self.new_test()

        self._inline_entry(W / 2, int(H * 0.25), str(self.count(mode)), ok)

    def ask_nick(self) -> None:
        W, H = self._layout_wh

        def ok(v: str):
            self._save(mt_username=v, mt_prompt_done=True)
            self.app.zen.sync(force=True)
            self._draw_chrome()

        self._inline_entry(self.col0 + self.colw - int(W * 0.12), int(H * 0.135), "", ok, width=18)

    # -- слова -----------------------------------------------------------
    def render(self) -> None:
        te = self.test
        if te is None or not self._layout_wh[0]:
            return
        tx = self.words
        tx.configure(state="normal")
        tx.delete("1.0", "end")
        self._wstart = {}
        pos = 0
        caret = 0
        end = min(len(te.words), self.top_word + 160)
        parts = []
        for k in range(self.top_word, end):
            w = te.words[k]
            inp = te.inputs[k] if k < len(te.inputs) else ""
            self._wstart[k] = pos
            typed_word = k < te.wi
            err = typed_word and inp != w
            for j in range(max(len(w), len(inp))):
                if j < len(inp):
                    if j >= len(w):
                        parts.append((inp[j], ("extra",)))
                    elif inp[j] == w[j]:
                        parts.append((w[j], ("correct",) + (("errword",) if err else ())))
                    else:
                        parts.append((w[j], ("incorrect",) + (("errword",) if err else ())))
                else:
                    parts.append((w[j], ("untyped",) + (("errword",) if err else ())))
            if k == te.wi:
                caret = pos + len(inp)
            pos += max(len(w), len(inp))
            parts.append((" ", ()))
            pos += 1
        for s, tg in parts:
            tx.insert("end", s, tg)
        tx.configure(state="disabled")
        self._caret_index = caret
        # прокрутка строками: курсор не ниже второй строки — верхняя строка уходит
        try:
            tx.update_idletasks()
            n = tx.count("1.0", f"1.0+{caret}c", "displaylines")
            n = (n[0] if isinstance(n, tuple) else n) or 0
        except tk.TclError:
            n = 0
        if n >= 2 and te.wi > self.top_word:
            # первое слово второй строки
            line2 = tx.index("1.0+1displaylines linestart")
            off = int(tx.count("1.0", line2, "chars")[0]) if tx.count("1.0", line2, "chars") else 0
            nk = next((k for k, s in sorted(self._wstart.items()) if s >= off), None)
            if nk is not None and nk > self.top_word:
                self.top_word = nk
                self.render()
                return
        self._place_caret()

    def _place_caret(self, animate: bool = True) -> None:
        tx = self.words
        try:
            bb = tx.bbox(f"1.0+{self._caret_index}c")
        except tk.TclError:
            bb = None
        if not bb:
            self.caret.place_forget()
            return
        lh = self.f_words.metrics("linespace")
        x = tx.winfo_x() + bb[0] - 1
        y = tx.winfo_y() + bb[1] + int(lh * 0.05)
        self._caret_target = (x, y)
        if self._caret_x is None or not animate or abs(y - (self._caret_y or y)) > lh * 2:
            self._caret_x, self._caret_y = x, y
        if self._caret_job is None:
            self._caret_step()

    def _caret_step(self) -> None:
        self._caret_job = None
        tx_, ty_ = self._caret_target
        cx, cy = self._caret_x, self._caret_y
        cx += (tx_ - cx) * 0.55
        cy += (ty_ - cy) * 0.55
        if abs(tx_ - cx) < 1 and abs(ty_ - cy) < 1:
            cx, cy = tx_, ty_
        self._caret_x, self._caret_y = cx, cy
        if self._blink and self.result.winfo_ismapped() is False and self.account is None:
            self.caret.place(x=int(cx), y=int(cy))
            self.caret.lift()
        if (cx, cy) != (tx_, ty_):
            self._caret_job = self.after(12, self._caret_step)

    # -- итоги -----------------------------------------------------------
    def show_result(self, res: dict) -> None:
        W, H = self._layout_wh
        self.caret.place_forget()
        rc, p = self.result, self.pal
        x0, cw = self.col0, self.colw
        y0 = int(H * 0.26)
        hgt = int(H * 0.56)
        rc.place(x=x0, y=y0, width=cw, height=hgt)
        tk.Misc.tkraise(rc)
        rc.delete("all")
        big = (self.fam, -int(H * 0.09))
        lab = (self.fam, -int(H * 0.033))
        sm = self.f_ui
        rc.create_text(0, int(H * 0.03), text="wpm", anchor="w", fill=p["sub"], font=lab)
        rc.create_text(0, int(H * 0.10), text=f"{res['wpm']:.0f}", anchor="w", fill=p["main"], font=big)
        rc.create_text(0, int(H * 0.19), text="acc", anchor="w", fill=p["sub"], font=lab)
        rc.create_text(0, int(H * 0.26), text=f"{res['acc']:.0f}%", anchor="w", fill=p["main"], font=big)
        # график wpm / raw по секундам
        gx0, gx1, gy0, gy1 = int(cw * 0.2), cw - 10, int(H * 0.02), int(H * 0.30)
        samples = self.test.samples or [(res["wpm"], res["raw"], 0)]
        mx = max(10, max(max(w, r) for w, r, _e in samples)) * 1.15
        for k in range(5):
            yy = gy1 - (gy1 - gy0) * k / 4
            rc.create_line(gx0, yy, gx1, yy, fill=p["subalt"])
            rc.create_text(gx0 - 6, yy, text=f"{mx * k / 4:.0f}", anchor="e", fill=p["sub"], font=self.f_small)
        n = len(samples)

        def pt(i, v):
            return gx0 + (gx1 - gx0) * (i / max(1, n - 1)), gy1 - (gy1 - gy0) * v / mx

        if n > 1:
            rc.create_line(*[c for i, s in enumerate(samples) for c in pt(i, s[1])], fill=p["sub"], width=2, smooth=True)
            rc.create_line(*[c for i, s in enumerate(samples) for c in pt(i, s[0])], fill=p["main"], width=3, smooth=True)
        for i, (_w, _r, e) in enumerate(samples):
            if e:
                x, _y = pt(i, 0)
                yy = gy1 - (gy1 - gy0) * min(mx, e * mx / 6) / mx
                rc.create_text(x, yy, text="×", fill=p["error"], font=self.f_ui)
        rc.create_text(gx1, gy0, text="wpm / raw", anchor="ne", fill=p["sub"], font=self.f_small)
        # нижняя строка
        c = res["chars"]
        mode = getattr(self.test, "ui_mode", res["mode"])
        cols = [("test type", f"{mode} {res['mode2'] or ''}".strip() + f"\n{res.get('language', '')}"),
                ("raw", f"{res['raw']:.0f}"),
                ("characters", f"{c['correct']}/{c['incorrect']}/{c['extra']}/{c['missed']}"),
                ("consistency", f"{res['consistency']:.0f}%"),
                ("time", f"{res['time']:.0f}s")]
        pb = self.app.zen.mt_pb(mode, res["mode2"])
        if pb:
            cols.append(("Monkeytype pb", f"{pb:.0f}"))
        yb = int(H * 0.38)
        colw = cw / len(cols)
        for i, (cap, val) in enumerate(cols):
            x = i * colw
            rc.create_text(x, yb, text=cap, anchor="w", fill=p["sub"], font=sm)
            vals = val.split("\n")
            rc.create_text(x, yb + int(H * 0.04), text=vals[0], anchor="w", fill=p["main"],
                           font=(self.fam, -int(H * (0.04 if len(vals) == 1 else 0.026))))
            if len(vals) > 1:
                rc.create_text(x, yb + int(H * 0.072), text=vals[1], anchor="w", fill=p["main"], font=sm)
        rc.create_text(cw / 2, hgt - int(H * 0.04), text="tab / enter - next test   ·   ↺ esc - restart",
                       fill=p["sub"], font=self.f_small)
        self._draw_chrome()

    # -- страница прогресса ------------------------------------------------
    def show_account(self) -> None:
        from stamina import account_view
        W, H = self._layout_wh
        if self.account is None:
            self.account = tk.Canvas(self, bg=self.pal["bg"], highlightthickness=0, bd=0)
            self.account.bind("<Button-1>", lambda _e: None)
            self.account.bind("<MouseWheel>", lambda e: self.account.yview_scroll(-int(e.delta / 120), "units"))
            self.account.bind("<Button-4>", lambda _e: self.account.yview_scroll(-3, "units"))
            self.account.bind("<Button-5>", lambda _e: self.account.yview_scroll(3, "units"))
        acc = self.account
        top = int(H * 0.15)
        acc.place(x=self.col0, y=top, width=self.colw, height=H - top - int(H * 0.06))
        tk.Misc.tkraise(acc)
        self.caret.place_forget()
        src = self.st.get("zen_acct_src", "all")
        acc.delete("all")
        tabs = (("all", t("общая")), ("st", "Star Typing"), ("mt", "Monkeytype"))
        x = 0
        for key, lab in tabs:
            i = acc.create_text(x, 12, text=lab, anchor="w", fill=self.pal["main"] if key == src else self.pal["sub"],
                                font=self.f_ui, tags=(f"tab_{key}",))
            acc.tag_bind(f"tab_{key}", "<Button-1>", lambda _e, k=key: (self._save(zen_acct_src=k), self.show_account()))
            x = acc.bbox(i)[2] + 24
        acc.create_text(self.colw, 12, text="esc - " + t("назад к тесту"), anchor="e", fill=self.pal["sub"], font=self.f_small)
        data = self.app.zen.account_summary(src)
        acc.configure(scrollregion=(0, 0, self.colw, 2000))
        sub = tk.Canvas(acc, bg=self.pal["bg"], highlightthickness=0, bd=0)
        # рисуем прямо на acc со сдвигом: проще — отдельный слой через move
        h = account_view.draw(acc, data, self.pal, self.fam, self.colw, scale=max(0.8, H / 760),
                              empty=t("Пока нет данных — пройдите тест или укажите ник Monkeytype"))
        acc.move("acct", 0, 32)
        acc.configure(scrollregion=(0, 0, self.colw, h + 40))
        sub.destroy()

    def hide_account(self) -> None:
        if self.account is not None:
            self.account.destroy()
            self.account = None
            self._place_caret(animate=False)

    # -- мышь / цикл -------------------------------------------------------
    def _motion(self, _e=None) -> None:
        if self.focus_mode:
            self.focus_mode = False
            self._draw_chrome()
        if not self.back.winfo_ismapped():
            self.back.place(x=8, y=6)
            self.back.lift()
        if self._back_job:
            self.after_cancel(self._back_job)
        self._back_job = self.after(2000, self._hide_back)

    def _hide_back(self) -> None:
        self._back_job = None
        self.back.place_forget()

    def show(self) -> None:
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.app.focus_set()
        if self._loop_job is None:
            self._loop()

    def hide(self) -> None:
        if self._loop_job:
            try:
                self.after_cancel(self._loop_job)
            except tk.TclError:
                pass
            self._loop_job = None
        if self.nick_entry is not None:
            self.nick_entry.destroy()
            self.nick_entry = None
        self.place_forget()

    def _loop(self) -> None:
        self._loop_job = self.after(100, self._loop)
        br = self._bridge()
        if getattr(br, "debrief", None) is not None:
            return
        self.lift()
        te = self.test
        if te is None:
            return
        if te.started and not te.finished:
            te.tick()
            if te.finished:
                self.finished_test()
                return
            self._update_counter()
        # мигание курсора, пока не печатают
        idle = time.monotonic() - self._last_key > 1.0
        vis = (not idle) or int(time.monotonic() * 2) % 2 == 0
        if vis != self._blink:
            self._blink = vis
            if vis and not self.result.winfo_ismapped() and self.account is None:
                self._place_caret(animate=False)
            elif not vis:
                self.caret.place_forget()

    def _update_counter(self) -> None:
        if self.test is not None and self.cv.find_withtag("counter"):
            self.cv.itemconfigure("counter", text=self.test.progress_label())

    # -- клавиши ---------------------------------------------------------
    def key(self, e) -> str:
        """Клавиша в портале. Возвращает "break"; None — пропустить кабине."""
        ks = getattr(e, "keysym", "")
        state = getattr(e, "state", 0)
        ch = getattr(e, "char", "")
        ctrl = bool(state & 0x4)
        if self.account is not None:
            if ks in ("Escape", "Tab", "Return"):
                self.hide_account()
            return "break"
        te = self.test
        if ks == "Tab":
            if te is not None and te.finished:
                self.new_test()
            else:
                self.tab_armed = True
            return "break"
        if ks in ("Return", "KP_Enter"):
            if te is not None and te.finished:
                self.new_test()
            elif self.tab_armed:
                self.new_test(same=True)
            elif state & 0x1 and te is not None and te.started:
                te.finish()
                self.finished_test()
            return "break"
        self.tab_armed = False
        if te is None or te.finished:
            return "break"
        if ks == "BackSpace":
            te.backspace(word=ctrl)
            self._after_input()
            return "break"
        if ctrl or (state & 0x8):
            return None                  # Ctrl+… / Alt+… — горячие клавиши кабины
        if ks.startswith("F") and ks[1:].isdigit():
            return None
        if not ch or len(ch) != 1 or not ch.isprintable():
            return "break"
        was = te.started
        te.type_char(ch)
        if te.started and not was and not self._started_marked:
            self._started_marked = True
            try:
                from stamina import portal_stats
                portal_stats.mark_started()
            except Exception:  # noqa: BLE001
                pass
        self._after_input()
        if te.finished:
            self.finished_test()
        return "break"

    def _after_input(self) -> None:
        self._last_key = time.monotonic()
        self._blink = True
        first = not self.focus_mode and self.test.started
        if first:
            self.focus_mode = True
        self.render()
        if first or self.cv.find_withtag("lang"):
            self._draw_chrome()
        else:
            self._update_counter()


class ZenController:
    """Состояние режима и связь с кабиной."""

    def __init__(self, app) -> None:
        self.app = app
        self.overlay: ZenOverlay | None = None
        self.on = False
        self._esc_job = None
        self._mt_cache = None

    def _wanted(self) -> bool:
        return bool(self.app.store.settings.get("zen_mode"))

    def toggle(self, on: bool | None = None) -> None:
        on = (not self.on) if on is None else on
        self.app.store.settings["zen_mode"] = on
        try:
            self.app.store.save_settings()
        except Exception:  # noqa: BLE001
            pass
        self.apply()

    def set_palette(self, name: str) -> None:
        if name in PALETTES:
            self.app.store.settings["zen_palette"] = name
            try:
                self.app.store.save_settings()
            except Exception:  # noqa: BLE001
                pass
            self.apply()

    def apply(self) -> None:
        """Показать/скрыть портал: он виден только на «Полёте» мостика."""
        show = self._wanted() and getattr(self.app, "current", None) == "bridge"
        was = self.on
        if show:
            pal = self.app.store.settings.get("zen_palette", "serika")
            if self.overlay is None or self.overlay.pal_name != pal or self.overlay.pal != _palette(pal):
                if self.overlay is not None:
                    self.overlay.destroy()
                self.overlay = ZenOverlay(self.app, pal)
            elif not was:
                self.overlay.load_source()       # текст мостика мог продвинуться
                self.overlay.new_test()
            self.overlay.show()
            if not was:
                self.sync()
        elif self.overlay is not None:
            self.overlay.hide()
            st = self.app.store.settings
            if self.on and not st.get("mt_prompt_done"):
                st["mt_prompt_done"] = True       # подсказку про ник показываем один раз
            try:
                self.app.focus_set()
            except tk.TclError:
                pass
        self.on = show
        br = getattr(self.app, "screens", {}).get("bridge")
        btn = getattr(br, "btn_zen", None)
        if btn is not None:
            try:
                btn.set_active(self._wanted())
            except Exception:  # noqa: BLE001
                pass

    # -- данные сайта (только чтение) -------------------------------------
    def mt_data(self) -> dict | None:
        from stamina import monkeytype
        nick = (self.app.store.settings.get("mt_username") or "").strip()
        if not nick:
            return None
        d = monkeytype.load_cache()
        return d if d and str(d.get("username", "")).lower() == nick.lower() else None

    def sync(self, force: bool = False) -> None:
        from stamina import monkeytype
        st = self.app.store.settings
        if force:
            monkeytype._sync["last"] = 0.0

        def done(_data):
            try:
                self.app.after(0, self._synced)
            except Exception:  # noqa: BLE001
                pass

        try:
            monkeytype.auto_sync(st.get("mt_username", ""), st.get("mt_apekey", ""), on_done=done)
        except Exception:  # noqa: BLE001
            pass

    def _synced(self) -> None:
        if self.overlay is not None and self.on:
            self.overlay._draw_chrome()

    def level(self) -> int:
        d = self.mt_data()
        s = (d or {}).get("summary") or {}
        return int(s.get("level") or 0)

    def average_pace(self, mode: str, n: int) -> int | None:
        from stamina import monkeytype, portal_stats
        v = monkeytype.average_pace(self.mt_data(), mode, n) if self.mt_data() else None
        return v if v else portal_stats.average_pace()

    def mt_pb(self, mode: str, n) -> float | None:
        s = (self.mt_data() or {}).get("summary") or {}
        for pb in s.get("pbs") or []:
            if pb["mode"] == mode and str(pb["mode2"]) == str(n) and pb.get("wpm"):
                return pb["wpm"]
        return None

    def account_summary(self, src: str = "all") -> dict | None:
        from stamina import portal_stats
        d = portal_stats.load()
        name = (self.app.store.settings.get("mt_username") or "").strip() or \
            (self.overlay._pilot_name() if self.overlay else t("пилот"))
        ours = portal_stats.summarize(d, name=name)
        mt = (self.mt_data() or {}).get("summary")
        if src == "st":
            return ours
        if src == "mt":
            return mt
        return portal_stats.merge(ours, mt)

    # -- клавиши ---------------------------------------------------------
    def handle_key(self, e) -> str | None:
        """Вызывается первым в Cockpit._on_key. "break" — клавиша съедена."""
        if is_zen_hotkey(e):
            if getattr(self.app, "current", None) == "bridge" or self.on:
                self.toggle()
                return "break"
            return None
        if not self.on or self.overlay is None:
            return None
        br = self.app.screens.get("bridge")
        if br is not None and getattr(br, "debrief", None) is not None:
            return None
        ov = self.overlay
        if ov.nick_entry is not None:
            return "break"               # печать идёт в поле ввода ника/числа
        if getattr(e, "keysym", "") == "Escape":
            if ov.account is not None:
                ov.hide_account()
                return "break"
            # Esc — заново; Esc Esc (≤400 мс) — назад на борт
            if self._esc_job is not None:
                self.app.after_cancel(self._esc_job)
                self._esc_job = None
                self.toggle(False)
            else:
                self._esc_job = self.app.after(ESC_DOUBLE_MS, self._esc_restart)
            return "break"
        return ov.key(e)

    def _esc_restart(self) -> None:
        self._esc_job = None
        if self.on and self.overlay is not None:
            te = self.overlay.test
            self.overlay.new_test(same=not (te is not None and te.finished))

    def after_key(self) -> None:
        pass
