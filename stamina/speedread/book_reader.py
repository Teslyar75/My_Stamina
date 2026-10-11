"""Читалка «КНИГА»: нормальный текст (без лесенок Gutenberg), 1 стр / разворот / прокрутка.

Образец режимов — Readest. Текст: оригинал из библиотеки + normalize_book_text.
"""
from __future__ import annotations

from stamina.i18n import t as _t

import re
import time
import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, CYAN, GREEN, MUTED, PANEL, blend, px

from .paper_tex import paper_photo
from .text_norm import normalize_book_text, paragraphs
from .ui import L

THEMES = {
    "paper": {
        "variant": "paper", "fg": "#2A2218", "dim": "#7A6E5C", "bar": "#1A1520",
        "bar_fg": "#E8DCC4", "accent": "#C4A35A", "fallback": "#F0E6D2", "desk": "#2A2218",
    },
    "night": {
        "variant": "dark", "fg": "#E6E0D4", "dim": "#8A8490", "bar": "#0C0E14",
        "bar_fg": "#D8DEE9", "accent": CYAN, "fallback": "#12151C", "desk": "#0A0C10",
    },
    "sepia": {
        "variant": "sepia", "fg": "#3B2A14", "dim": "#8A7048", "bar": "#2A2218",
        "bar_fg": "#E8D4B0", "accent": "#C49A5A", "fallback": "#E8D4B0", "desk": "#2A2218",
    },
}
# обратная совместимость ключа dark → night
THEME_ALIASES = {"dark": "night"}

MODES = ("page", "spread", "scroll")  # 1 стр / разворот / прокрутка
DEFAULT_LINE_SPACE = 1.45
DEFAULT_MODE = "spread"
WPM_ESTIMATE = 230  # для «времени до конца»


def _split_words(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _detect_chapters(text: str) -> list[tuple[int, str]]:
    pat = re.compile(
        r"(?m)^(chapter\s+\d+|part\s+\d+|book\s+\d+|глава\s+\d+|часть\s+\d+|"
        r"prologue|epilogue|пролог|эпилог|"
        r"CHAPTER\s+[IVXLC]+|[IVXLC]+\.\s+\w.{0,40})$",
        re.I,
    )
    out = []
    for m in pat.finditer(text):
        out.append((m.start(), " ".join(m.group(0).split())[:60]))
        if len(out) >= 80:
            break
    return out


def _reading_font(pt: int) -> tuple:
    fam = theme.HUD_FAMILY
    try:
        available = set(tkfont.families())
        for name in ("Literata", "Cambria", "Georgia", "Constantia",
                     "Palatino Linotype", "Times New Roman", "Liberation Serif"):
            if name in available:
                fam = name
                break
    except tk.TclError:
        pass
    return (fam, pt)


def _wrap_para(para: str, font: tkfont.Font, width: int, *, first_indent: int) -> list[str]:
    """Перенос абзаца по реальной ширине (font.measure)."""
    if width < 40:
        width = 40
    words = para.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur: list[str] = []
    limit = max(40, width - first_indent)

    def flush(indent_next: bool = False):
        nonlocal cur, limit
        if cur:
            lines.append(" ".join(cur))
            cur = []
        limit = width  # после первой строки — полная ширина

    for w in words:
        trial = w if not cur else (" ".join(cur) + " " + w)
        if font.measure(trial) <= limit:
            cur.append(w)
        else:
            if not cur:
                # очень длинное слово
                chunk = ""
                for ch in w:
                    if font.measure(chunk + ch) <= limit:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                        limit = width
                if chunk:
                    cur = [chunk]
            else:
                flush()
                cur = [w]
    flush()
    return lines or [""]


def _layout_pages(paras: list[str], font: tkfont.Font, col_w: int, lines_per: int,
                  columns: int, *, indent: int, line_h: int, para_gap: int) -> list[dict]:
    """Страницы/развороты: каждая — список колонок со строками {(text, kind)}."""
    # kind: "first" | "cont" | "blank"
    all_lines: list[tuple[str, str, int]] = []  # text, kind, char_hint unused
    for para in paras:
        wrapped = _wrap_para(para, font, col_w, first_indent=indent)
        for i, ln in enumerate(wrapped):
            all_lines.append((ln, "first" if i == 0 else "cont"))
        all_lines.append(("", "blank"))  # интервал между абзацами как пустая «полустрока»

    # blank занимает меньше — моделируем как отдельный слот; при пагинации blank = 1 слот
    # но рисуем gap. Для подсчёта строк blank считаем 0.5 → округлим: каждые 2 blank = 1 line
    # Проще: blank не занимает строку в счётчике, а para_gap учитываем при отрисовке.
    # Тогда lines_per — число текстовых строк. blank между абзацами не ест слот страницы,
    # только вертикальный gap при paint. Уберём trailing blank.
    while all_lines and all_lines[-1][1] == "blank":
        all_lines.pop()

    text_lines = [(t, k) for t, k in all_lines if k != "blank"]
    # вставим маркеры границы абзаца для paint: после last "cont"/"first" before next "first"
    # Храним flat list of text lines only; paragraph starts = kind first
    columns = 2 if columns >= 2 else 1
    per_page = max(1, lines_per) * columns
    pages = []
    i = 0
    n = len(text_lines)
    # char offsets: approximate by joining
    # rebuild with offsets from original joined text later in open()
    while i < n or not pages:
        chunk = text_lines[i:i + per_page]
        if not chunk and pages:
            break
        cols = []
        for c in range(columns):
            part = chunk[c * lines_per:(c + 1) * lines_per]
            cols.append(part)
        pages.append({"cols": cols})
        i += per_page
        if not text_lines:
            break
    return pages or [{"cols": [[]] * columns}]


class BookReaderPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.tid: str | None = None
        self.title = ""
        self.raw_text = ""
        self.text = ""  # нормализованный
        self.paras: list[str] = []
        self.words: list[tuple[int, int]] = []
        self.chapters: list[tuple[int, str]] = []
        self._applying = False
        self._fullscreen = False
        self._fs: tk.Frame | None = None
        self._page_i = 0
        self._pages: list[dict] = []
        self._relayout_job = None
        self._layout_key = None
        self._last_size = (0, 0)
        self._paper_refs: list = []
        self._chrome_visible = True
        self._hide_job = None
        self._line_starts: list[int] = []  # char offset каждой текстовой строки в self.text

        th0 = self._theme()
        self.chrome = tk.Frame(self, bg=BG)
        self.chrome.pack(fill=tk.BOTH, expand=True)

        # ---- top bar ---------------------------------------------------------
        self.top_bar = tk.Frame(self.chrome, bg=th0["bar"], height=px(44))
        self.top_bar.pack(fill=tk.X)
        self.top_bar.pack_propagate(False)
        self._build_top_bar(self.top_bar)

        # ---- reading surface -------------------------------------------------
        self.read_shell = tk.Frame(self.chrome, bg=th0["desk"])
        self.read_shell.pack(fill=tk.BOTH, expand=True)
        self.page_host = tk.Frame(self.read_shell, bg=th0["desk"])
        self.page_host.pack(fill=tk.BOTH, expand=True)
        self.spread: tk.Canvas | None = None
        self.scroll_view: tk.Text | None = None
        self._build_surface(self.page_host)

        # ---- bottom bar ------------------------------------------------------
        self.bot_bar = tk.Frame(self.chrome, bg=th0["bar"], height=px(36))
        self.bot_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.bot_bar.pack_propagate(False)
        self.lbl_pct = tk.Label(self.bot_bar, text="0%", bg=th0["bar"], fg=th0["bar_fg"],
                                font=theme.font(9, True, mono=True))
        self.lbl_pct.pack(side=tk.LEFT, padx=px(12))
        self.scale = tk.Scale(self.bot_bar, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=0,
                              bg=th0["bar"], fg=th0["accent"], troughcolor=blend(th0["bar"], "#000", 0.3),
                              highlightthickness=0, activebackground=th0["accent"],
                              command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8), pady=px(6))
        self.lbl_page = tk.Label(self.bot_bar, text="", bg=th0["bar"], fg=th0["dim"],
                                 font=theme.font(9, True, mono=True))
        self.lbl_page.pack(side=tk.LEFT, padx=px(8))
        self.lbl_eta = tk.Label(self.bot_bar, text="", bg=th0["bar"], fg=th0["dim"],
                                font=theme.font(9, True))
        self.lbl_eta.pack(side=tk.RIGHT, padx=px(12))

        self.read_shell.bind("<Configure>", self._on_area_configure)
        self.read_shell.bind("<Motion>", self._on_motion)
        self.bind_all("<Escape>", self._esc_global, add="+")
        self._sync_mode_btns()
        self._apply_theme()
        self._schedule_hide_chrome()

    # ------------------------------------------------------------------ props
    @property
    def st(self) -> dict:
        return self.ctx.sstore.settings

    @property
    def mode(self) -> str:
        m = self.st.get("book_mode")
        if m in MODES:
            return m
        # миграция со старого book_columns
        cols = int(self.st.get("book_columns", 2))
        return "spread" if cols == 2 else "page"

    def _theme_key(self) -> str:
        k = self.st.get("book_theme", "paper")
        return THEME_ALIASES.get(k, k) if k in THEME_ALIASES or k in THEMES else "paper"

    def _theme(self) -> dict:
        return THEMES[self._theme_key()]

    def _font_pt(self) -> int:
        return int(self.st.get("book_font_pt", 17))

    def _line_space(self) -> float:
        v = float(self.st.get("book_line_space", DEFAULT_LINE_SPACE))
        if v < 1.3 or v > 1.7:
            v = DEFAULT_LINE_SPACE
            self.st["book_line_space"] = v
        return v

    def _font_obj(self) -> tkfont.Font:
        return tkfont.Font(font=_reading_font(self._font_pt()))

    def _line_h(self) -> int:
        f = self._font_obj()
        return max(1, int(round(f.metrics("linespace") * self._line_space())))

    # ------------------------------------------------------------------ chrome
    def _tip(self, widget, text: str) -> None:
        widget.tooltip = text  # type: ignore[attr-defined]

        def enter(_e):
            self.ctx.app.set_status(text, MUTED)

        widget.bind("<Enter>", enter, add="+")

    def _build_top_bar(self, bar: tk.Frame) -> None:
        th = self._theme()
        for w in bar.winfo_children():
            w.destroy()

        def btn(text, cmd, tip, *, color=None, width=None, active=False):
            b = HudButton(bar, text, cmd, height=30, font_size=8,
                          width=width or max(50, 10 + len(text) * 7),
                          color=color or th["accent"], active=active)
            b.pack(side=tk.LEFT, padx=px(2), pady=px(6))
            self._tip(b, tip)
            return b

        btn(_t("← БИБЛИОТЕКА"), lambda: self._go_library(), _t("Вернуться в библиотеку"),
            width=120)
        btn("◀", self.page_prev, _t("Предыдущая страница (← / PgUp)"), width=36)
        btn("▶", self.page_next, _t("Следующая страница (→ / PgDn)"), width=36)
        btn("A−", lambda: self.font_delta(-1), _t("Мельче шрифт (−)"), width=36)
        btn("A+", lambda: self.font_delta(+1), _t("Крупнее шрифт (+)"), width=36)

        self.mode_btns = {}
        for key, lab, tip in (
            ("page", _t("1 СТР"), _t("Одна страница по центру")),
            ("spread", _t("РАЗВОРОТ"), _t("Две страницы, как открытая книга")),
            ("scroll", _t("ПРОКРУТКА"), _t("Непрерывный текст")),
        ):
            b = btn(lab, lambda k=key: self.set_mode(k), tip, width=100 if key != "page" else 70)
            self.mode_btns[key] = b

        self.theme_btns = {}
        for key, lab, tip in (
            ("paper", _t("БУМАГА"), _t("Светлая бумага")),
            ("night", _t("НОЧЬ"), _t("Тёмная тема")),
            ("sepia", _t("СЕПИЯ"), _t("Тёплая сепия")),
        ):
            b = btn(lab, lambda k=key: self.set_theme(k), tip, width=80)
            self.theme_btns[key] = b

        btn(_t("ОГЛ."), self.show_toc, _t("Оглавление"), width=56)
        btn(_t("⚡ RSVP"), self.to_hyperdrive, _t("Открыть в гипердрайве с этого места"),
            color=AMBER, width=80)

        self.lbl_title = tk.Label(bar, text=_t("КНИГА"), bg=th["bar"], fg=th["bar_fg"],
                                  font=theme.font(10, True))
        self.lbl_title.pack(side=tk.LEFT, padx=px(10))

        if self._fullscreen:
            btn(_t("✕"), self.exit_fullscreen, _t("Выйти из полного экрана (Esc)"),
                color=AMBER, width=40).pack_forget()
            b = HudButton(bar, _t("✕"), self.exit_fullscreen, height=30, font_size=9,
                          width=40, color=AMBER)
            b.pack(side=tk.RIGHT, padx=px(8), pady=px(6))
            self._tip(b, _t("Выйти из полного экрана (Esc)"))
        else:
            b = HudButton(bar, _t("⛶ ЭКРАН"), self.enter_fullscreen, height=30, font_size=8,
                          width=90, color=GREEN)
            b.pack(side=tk.RIGHT, padx=px(8), pady=px(6))
            self._tip(b, _t("На весь экран (F11)"))

    def _go_library(self) -> None:
        if self._fullscreen:
            self.exit_fullscreen()
        self.save_pos()
        self.ctx.show("library")

    def _schedule_hide_chrome(self) -> None:
        if self._hide_job:
            try:
                self.after_cancel(self._hide_job)
            except tk.TclError:
                pass
        if self.mode == "scroll":
            return
        self._hide_job = self.after(3500, self._hide_chrome)

    def _hide_chrome(self) -> None:
        if not self._chrome_visible or self._fullscreen is False and self.mode == "scroll":
            return
        # в обычном режиме оставляем тонкую полоску; в fullscreen — прячем
        if self._fullscreen:
            self.top_bar.pack_forget()
            self.bot_bar.pack_forget()
            self._chrome_visible = False

    def _show_chrome(self) -> None:
        if self._chrome_visible:
            self._schedule_hide_chrome()
            return
        th = self._theme()
        self.top_bar.pack(fill=tk.X, before=self.read_shell)
        self.bot_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self._chrome_visible = True
        self._schedule_hide_chrome()

    def _on_motion(self, _e=None) -> None:
        self._show_chrome()

    def _esc_global(self, _e=None):
        if self._fullscreen:
            self.exit_fullscreen()
            return "break"

    # ------------------------------------------------------------------ surface
    def _build_surface(self, parent: tk.Frame) -> None:
        for w in parent.winfo_children():
            w.destroy()
        self.spread = None
        self.scroll_view = None
        self._paper_refs.clear()
        th = self._theme()
        parent.configure(bg=th["desk"])
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        if self.mode == "scroll":
            wrap = tk.Frame(parent, bg=th["fallback"])
            wrap.grid(row=0, column=0, sticky="nsew")
            sb = tk.Scrollbar(wrap)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            t = tk.Text(wrap, wrap=tk.WORD, relief=tk.FLAT, bd=0,
                        padx=px(48), pady=px(24),
                        bg=th["fallback"], fg=th["fg"],
                        font=_reading_font(self._font_pt()),
                        yscrollcommand=sb.set, cursor="arrow")
            t.pack(fill=tk.BOTH, expand=True)
            sb.configure(command=t.yview)
            t.bind("<Key>", self.on_key)
            t.bind("<Button-1>", lambda _e: self._show_chrome())
            self.scroll_view = t
        else:
            c = tk.Canvas(parent, bg=th["desk"], highlightthickness=0, bd=0, cursor="arrow")
            c.grid(row=0, column=0, sticky="nsew")
            c.bind("<Button-1>", self._click_turn)
            c.bind("<Motion>", self._on_motion)
            c.bind("<Key>", self.on_key)
            c.bind("<MouseWheel>", self._on_wheel)
            self.spread = c
            try:
                c.focus_set()
            except tk.TclError:
                pass

    def _click_turn(self, e: tk.Event) -> None:
        self._show_chrome()
        w = max(e.widget.winfo_width(), 1)
        if e.x < w * 0.4:
            self.page_prev()
        elif e.x > w * 0.6:
            self.page_next()
        try:
            e.widget.focus_set()
        except tk.TclError:
            pass

    def _on_wheel(self, e: tk.Event) -> str | None:
        if getattr(e, "delta", 0) > 0:
            self.page_prev()
        else:
            self.page_next()
        return "break"

    def _sync_mode_btns(self) -> None:
        for k, b in getattr(self, "mode_btns", {}).items():
            b.set_active(k == self.mode)
        for k, b in getattr(self, "theme_btns", {}).items():
            b.set_active(k == self._theme_key())

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            return
        char = self._page_start_char()
        self.st["book_mode"] = mode
        self.st["book_columns"] = 2 if mode == "spread" else 1
        self.ctx.sstore.save()
        self._layout_key = None
        self._build_surface(self._page_host())
        self._build_top_bar(self.top_bar)
        self._sync_mode_btns()
        self._apply_theme()
        self.after(20, lambda: self._relayout(keep_char=char))

    def set_theme(self, key: str) -> None:
        key = THEME_ALIASES.get(key, key)
        if key not in THEMES:
            return
        self.st["book_theme"] = key
        self.ctx.sstore.save()
        self._build_top_bar(self.top_bar)
        self._sync_mode_btns()
        self._apply_theme()
        self._show_page()

    def font_delta(self, d: int) -> None:
        char = self._page_start_char()
        self.st["book_font_pt"] = max(12, min(28, self._font_pt() + d))
        self.ctx.sstore.save()
        self._layout_key = None
        self.after(20, lambda: self._relayout(keep_char=char))

    def _apply_theme(self) -> None:
        th = self._theme()
        self.top_bar.configure(bg=th["bar"])
        self.bot_bar.configure(bg=th["bar"])
        for lab in (self.lbl_pct, self.lbl_page, self.lbl_eta):
            lab.configure(bg=th["bar"], fg=th["dim"] if lab is not self.lbl_pct else th["bar_fg"])
        self.lbl_title.configure(bg=th["bar"], fg=th["bar_fg"])
        self.scale.configure(bg=th["bar"], fg=th["accent"],
                             troughcolor=blend(th["bar"], "#000", 0.3),
                             activebackground=th["accent"])
        self.read_shell.configure(bg=th["desk"])
        host = self._page_host()
        host.configure(bg=th["desk"])
        if self.spread is not None:
            self.spread.configure(bg=th["desk"])
        if self.scroll_view is not None:
            self.scroll_view.configure(bg=th["fallback"], fg=th["fg"],
                                       font=_reading_font(self._font_pt()))
        if self._fs is not None:
            self._fs.configure(bg=th["desk"])

    def _page_host(self) -> tk.Frame:
        if self._fullscreen and self._fs is not None and hasattr(self, "_fs_page"):
            return self._fs_page
        return self.page_host

    def _active_shell(self) -> tk.Frame:
        if self._fullscreen and hasattr(self, "_fs_area"):
            return self._fs_area
        return self.read_shell

    # ------------------------------------------------------------------ open
    def open(self, tid: str, *, word: int | None = None) -> None:
        lib = self.ctx.lib
        m = lib.meta(tid)
        if not m:
            return
        self.save_pos()
        self.tid = tid
        self.title = m["title"] + (f" · {m['author']}" if m.get("author") else "")
        self.lbl_title.configure(text=self.title[:72])
        # оригинал (не prepared для печати)
        self.raw_text = lib.reading_text(tid) or ""
        self.text = normalize_book_text(self.raw_text)
        self.paras = paragraphs(self.text)
        self.words = _split_words(self.text)
        self.chapters = _detect_chapters(self.text)
        lib.set_active("reading", tid)
        if word is None:
            word = int(m["positions"]["reading"].get("word", 0))
        char = self.words[word][0] if self.words and 0 <= word < len(self.words) else 0
        self._layout_key = None
        self._apply_theme()
        self.after(30, lambda: self._relayout(keep_char=char))
        self.focus_set()

    def refresh(self) -> None:
        if self.tid is None:
            tid = self.ctx.lib.index.get("active_reading") or (self.ctx.lib.ids() or [None])[0]
            if tid:
                self.open(tid)
            else:
                self.lbl_title.configure(text=_t("КНИГА"))
                self.text = self.raw_text = ""
                self.paras = []
                self.words = []
                self._pages = [{"cols": [[]]}]
                self._page_i = 0
                self._show_page()
        else:
            self._update_progress()

    def save_pos(self) -> None:
        if not self.tid or not self.words:
            return
        self.ctx.lib.set_position(self.tid, "reading", self.current_word())

    def current_word(self) -> int:
        if not self.words:
            return 0
        char = self._page_start_char()
        lo, hi, ans = 0, len(self.words) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.words[mid][0] <= char:
                ans = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return ans

    def _page_start_char(self) -> int:
        if self.mode == "scroll" and self.scroll_view is not None:
            try:
                idx = self.scroll_view.index("@10,10")
                return self._tk_index_to_char(idx)
            except tk.TclError:
                return 0
        if not self._pages or not self._line_starts:
            return 0
        sl = int(self._pages[self._page_i].get("start_line", 0))
        if sl < len(self._line_starts):
            return self._line_starts[sl]
        return max(0, len(self.text) - 1)

    def _tk_index_to_char(self, index: str) -> int:
        line, col = map(int, str(index).split("."))
        lines = self.text.split("\n")
        off = sum(len(lines[i]) + 1 for i in range(min(line - 1, len(lines))))
        return off + col

    def goto_word(self, word: int) -> None:
        if not self.words:
            return
        word = max(0, min(word, len(self.words) - 1))
        self._goto_char(self.words[word][0])

    def _goto_char(self, char: int, *, save: bool = True) -> None:
        if self.mode == "scroll" and self.scroll_view is not None:
            # найти tk index
            idx = self._char_to_tk(char)
            self.scroll_view.see(idx)
            if save:
                self.save_pos()
            self._update_progress()
            return
        if not self._pages or not self._line_starts:
            return
        target = 0
        for pi, page in enumerate(self._pages):
            sl = int(page.get("start_line", 0))
            if sl < len(self._line_starts) and self._line_starts[sl] <= char:
                target = pi
            else:
                break
        self._page_i = target
        self._show_page()
        if save:
            self.save_pos()

    def _char_to_tk(self, char: int) -> str:
        char = max(0, min(char, len(self.text)))
        lines = self.text.split("\n")
        rem = char
        for i, line in enumerate(lines):
            if rem <= len(line):
                return f"{i + 1}.{rem}"
            rem -= len(line) + 1
        return "end"

    # ------------------------------------------------------------------ layout
    def _on_area_configure(self, _e=None) -> None:
        shell = self._active_shell()
        try:
            w, h = shell.winfo_width(), shell.winfo_height()
        except tk.TclError:
            return
        if abs(w - self._last_size[0]) < 12 and abs(h - self._last_size[1]) < 12:
            return
        if self._relayout_job:
            try:
                self.after_cancel(self._relayout_job)
            except tk.TclError:
                pass
        char = self._page_start_char()
        self._relayout_job = self.after(100, lambda: self._relayout(keep_char=char))

    def _relayout(self, keep_char: int | None = None) -> None:
        self._relayout_job = None
        if keep_char is None:
            keep_char = self._page_start_char()
        shell = self._active_shell()
        shell.update_idletasks()
        sw = max(shell.winfo_width(), 200)
        sh = max(shell.winfo_height(), 200)
        self._last_size = (sw, sh)

        if self.mode == "scroll":
            self._fill_scroll()
            self._goto_char(keep_char, save=False)
            return

        font = self._font_obj()
        lh = self._line_h()
        indent = font.measure("    ")  # ~4 пробела — красная строка
        cols = 2 if self.mode == "spread" else 1

        # геометрия книги
        outer = max(px(12), int(sw * 0.025))
        top = max(px(10), int(sh * 0.03))
        bottom = max(px(12), int(sh * 0.035))
        spine = px(10) if cols == 2 else 0
        book_w = max(160, sw - outer * 2)
        book_h = max(120, sh - top - bottom)
        page_w = (book_w - spine) // cols
        pad_x = max(px(16), int(page_w * 0.07))
        pad_y = max(px(14), int(book_h * 0.045))
        # ограничить ширину одной страницы ~75 символов
        avg = max(4.0, font.measure("abcdefghijklmnopqrstuvwxyz") / 26)
        max_text = int(avg * 72)
        text_w = min(max(80, page_w - pad_x * 2), max_text if cols == 1 else max(80, page_w - pad_x * 2))
        if cols == 1:
            # центрируем колонку
            text_w = min(text_w, max_text)

        col_h = max(40, book_h - pad_y * 2)
        para_gap = max(2, int(lh * 0.35))

        key = (text_w, col_h, cols, self._font_pt(), self._theme_key(), len(self.text), lh, para_gap)
        if key == self._layout_key and self._pages:
            self._geom = dict(outer=outer, top=top, book_w=book_w, book_h=book_h,
                              page_w=page_w, spine=spine, pad_x=pad_x, pad_y=pad_y,
                              text_w=text_w, lh=lh, indent=indent, para_gap=para_gap,
                              cols=cols, col_h=col_h)
            self._goto_char(keep_char, save=False)
            return
        self._layout_key = key
        self._geom = dict(outer=outer, top=top, book_w=book_w, book_h=book_h,
                          page_w=page_w, spine=spine, pad_x=pad_x, pad_y=pad_y,
                          text_w=text_w, lh=lh, indent=indent, para_gap=para_gap,
                          cols=cols, col_h=col_h)

        if not self.paras:
            self._pages = [{"cols": [[]] * cols, "start_line": 0}]
            self._line_starts = [0]
            self._page_i = 0
            self._show_page()
            return

        self._line_starts = []
        flat: list[tuple[str, str]] = []
        search_from = 0
        for para in self.paras:
            pos = self.text.find(para, search_from)
            if pos < 0:
                pos = search_from
            wrapped = _wrap_para(para, font, text_w, first_indent=indent)
            cursor = 0
            for i, ln in enumerate(wrapped):
                idx = para.find(ln, cursor)
                if idx < 0:
                    idx = cursor
                self._line_starts.append(pos + idx)
                flat.append((ln, "first" if i == 0 else "cont"))
                cursor = idx + len(ln)
                while cursor < len(para) and para[cursor] == " ":
                    cursor += 1
            search_from = pos + len(para)
            while search_from < len(self.text) and self.text[search_from] in "\n ":
                search_from += 1

        # пагинация по реальной высоте колонки (строка + gap перед first)
        pages: list[dict] = []
        i = 0
        n = len(flat)
        while i < n or not pages:
            col_data: list[list] = []
            start_line = i
            for _c in range(cols):
                used = 0
                col_lines: list[tuple[str, str]] = []
                while i < n:
                    text, kind = flat[i]
                    need = lh + (para_gap if kind == "first" and col_lines else 0)
                    if col_lines and used + need > col_h:
                        break
                    if not col_lines and need > col_h:
                        # хотя бы одна строка, даже если туго
                        col_lines.append((text, kind))
                        i += 1
                        used = lh
                        break
                    used += need
                    col_lines.append((text, kind))
                    i += 1
                col_data.append(col_lines)
            pages.append({"cols": col_data, "start_line": start_line})
            if n == 0:
                break
        self._pages = pages
        self._goto_char(keep_char, save=False)

    def _fill_scroll(self) -> None:
        t = self.scroll_view
        if t is None:
            return
        th = self._theme()
        f = _reading_font(self._font_pt())
        t.configure(state=tk.NORMAL, font=f, bg=th["fallback"], fg=th["fg"],
                    spacing1=0, spacing2=int(self._font_pt() * (self._line_space() - 1.0)),
                    spacing3=int(self._line_h() * 0.35))
        t.delete("1.0", tk.END)
        # абзацы с отступом
        for i, para in enumerate(self.paras):
            t.insert(tk.END, "    " + para + ("\n\n" if i < len(self.paras) - 1 else ""))
        t.configure(state=tk.DISABLED)
        self._pages = [{"cols": [[]]}]
        self._line_starts = [0]

    def _show_page(self) -> None:
        if self.mode == "scroll":
            self._update_progress()
            return
        if not self._pages:
            return
        self._page_i = max(0, min(self._page_i, len(self._pages) - 1))
        if self.spread is None:
            self._build_surface(self._page_host())
        self._paint_book(self._pages[self._page_i])
        self._update_progress()

    def _paint_book(self, page: dict) -> None:
        c = self.spread
        if c is None or not hasattr(self, "_geom"):
            return
        c.update_idletasks()
        W, H = max(c.winfo_width(), 80), max(c.winfo_height(), 80)
        c.delete("all")
        self._paper_refs.clear()
        th = self._theme()
        font = _reading_font(self._font_pt())
        font_obj = self._font_obj()
        g = self._geom
        cols = g["cols"]
        book_w, book_h = g["book_w"], g["book_h"]
        page_w, spine = g["page_w"], g["spine"]
        pad_x, pad_y = g["pad_x"], g["pad_y"]
        lh, indent, para_gap = g["lh"], g["indent"], g["para_gap"]
        text_w = g["text_w"]

        bx = max(0, (W - book_w) // 2)
        by = max(0, (H - book_h) // 2)
        c.create_rectangle(bx + px(5), by + px(7), bx + book_w + px(3), by + book_h + px(5),
                           fill="#1A140E", outline="")

        def paint_col2(x0, y0, pw, ph, lines: list[tuple[str, str]]):
            photo = paper_photo(c, pw, ph, th["variant"])
            if photo is not None:
                self._paper_refs.append(photo)
                c.create_image(x0, y0, image=photo, anchor="nw")
            else:
                c.create_rectangle(x0, y0, x0 + pw, y0 + ph, fill=th["fallback"], outline="")
            c.create_rectangle(x0, y0, x0 + pw - 1, y0 + ph - 1,
                               outline=blend(th["fg"], th["fallback"], 0.85), width=1)
            tx0 = x0 + max(pad_x, (pw - text_w) // 2)
            y = y0 + pad_y
            max_y = y0 + ph - pad_y
            for i, (text, kind) in enumerate(lines):
                if kind == "first" and i > 0:
                    y += para_gap
                if y + lh > max_y:
                    break
                x = tx0 + (indent if kind == "first" else 0)
                width = text_w - (indent if kind == "first" else 0)
                # последняя строка абзаца — без justify
                is_last = (i + 1 >= len(lines)) or (lines[i + 1][1] == "first")
                self._draw_justified(c, x, y, text, font, font_obj, width, th["fg"], last=is_last)
                y += lh

        col_lists = page["cols"]
        if cols == 2:
            paint_col2(bx, by, page_w, book_h, col_lists[0] if col_lists else [])
            rx = bx + page_w + spine
            paint_col2(rx, by, page_w, book_h, col_lists[1] if len(col_lists) > 1 else [])
            mid = bx + page_w
            c.create_rectangle(mid, by, mid + spine, by + book_h, fill="#1E1810", outline="")
            c.create_line(mid + spine // 2, by + px(4), mid + spine // 2, by + book_h - px(4),
                          fill="#3A3020", width=max(2, spine // 3))
            for i in range(6):
                col = blend("#000000", th["fallback"], 0.93 + 0.01 * i)
                c.create_line(mid - i, by, mid - i, by + book_h, fill=col)
                c.create_line(mid + spine + i, by, mid + spine + i, by + book_h, fill=col)
        else:
            # одна страница по центру
            pw = min(book_w, text_w + pad_x * 2 + px(8))
            px0 = bx + (book_w - pw) // 2
            paint_col2(px0, by, pw, book_h, col_lists[0] if col_lists else [])

    def _draw_justified(self, c: tk.Canvas, x: int, y: int, text: str, font, font_obj: tkfont.Font,
                        width: int, fill: str, *, last: bool) -> None:
        words = text.split()
        if not words:
            return
        if last or len(words) == 1:
            c.create_text(x, y, text=text, anchor="nw", fill=fill, font=font)
            return
        natural = font_obj.measure(text)
        extra = width - natural
        if extra <= 0:
            c.create_text(x, y, text=text, anchor="nw", fill=fill, font=font)
            return
        gaps = len(words) - 1
        # распределить лишние пиксели по пробелам
        base = extra // gaps
        rem = extra % gaps
        cx = x
        space_w = font_obj.measure(" ")
        for i, w in enumerate(words):
            c.create_text(cx, y, text=w, anchor="nw", fill=fill, font=font)
            cx += font_obj.measure(w)
            if i < gaps:
                cx += space_w + base + (1 if i < rem else 0)

    def page_next(self) -> None:
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_scroll(1, "pages")
            self.save_pos()
            self._update_progress()
            return
        if self._page_i < len(self._pages) - 1:
            self._page_i += 1
            self._show_page()
            self.save_pos()

    def page_prev(self) -> None:
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_scroll(-1, "pages")
            self.save_pos()
            self._update_progress()
            return
        if self._page_i > 0:
            self._page_i -= 1
            self._show_page()
            self.save_pos()

    def _on_scale(self, val) -> None:
        if self._applying or not self.text:
            return
        frac = float(val) / 100.0
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_moveto(frac)
            self.save_pos()
            self._update_progress()
            return
        if not self._pages:
            return
        self._page_i = int(round(frac * max(0, len(self._pages) - 1)))
        self._show_page()
        self.save_pos()

    def _update_progress(self) -> None:
        if not self.text:
            self.lbl_pct.configure(text="0%")
            self.lbl_page.configure(text="")
            self.lbl_eta.configure(text="")
            return
        w = self.current_word()
        n = len(self.words) or 1
        pct = int(round(w / n * 100))
        self._applying = True
        try:
            self.scale.set(pct)
        except tk.TclError:
            pass
        self._applying = False
        self.lbl_pct.configure(text=f"{pct}%")
        if self.mode == "scroll":
            self.lbl_page.configure(text=_t("прокрутка"))
        elif self.mode == "spread":
            left = self._page_i * 2 + 1
            total = len(self._pages) * 2
            self.lbl_page.configure(text=_t("{0}–{1} / {2}").format(left, left + 1, total))
        else:
            self.lbl_page.configure(text=_t("{0} / {1}").format(self._page_i + 1, len(self._pages)))
        left_words = max(0, n - w)
        mins = max(1, int(round(left_words / WPM_ESTIMATE)))
        self.lbl_eta.configure(text=_t("~{0} мин").format(mins))

    # ------------------------------------------------------------------ fullscreen
    def enter_fullscreen(self) -> None:
        if self._fullscreen:
            return
        self.save_pos()
        th = self._theme()
        self._fullscreen = True
        self.ctx.set_focus_mode(True)
        self._layout_key = None
        self._fs = tk.Frame(self.ctx.app, bg=th["desk"])
        self._fs.place(x=0, y=0, relwidth=1, relheight=1)
        self._fs.lift()

        self.top_bar_fs = tk.Frame(self._fs, bg=th["bar"], height=px(44))
        self.top_bar_fs.pack(fill=tk.X)
        self.top_bar_fs.pack_propagate(False)
        # временно подменить top_bar для builder
        old_top, old_bot = self.top_bar, self.bot_bar
        self.top_bar = self.top_bar_fs
        self._build_top_bar(self.top_bar)

        self._fs_area = tk.Frame(self._fs, bg=th["desk"])
        self._fs_area.pack(fill=tk.BOTH, expand=True)
        self._fs_page = tk.Frame(self._fs_area, bg=th["desk"])
        self._fs_page.pack(fill=tk.BOTH, expand=True)
        self._build_surface(self._fs_page)

        self.bot_bar_fs = tk.Frame(self._fs, bg=th["bar"], height=px(36))
        self.bot_bar_fs.pack(fill=tk.X, side=tk.BOTTOM)
        self.bot_bar_fs.pack_propagate(False)
        # перенести метки — проще пересоздать
        for lab_attr, side in (("lbl_pct", tk.LEFT), ("lbl_page", tk.LEFT), ("lbl_eta", tk.RIGHT)):
            pass
        self.lbl_pct = tk.Label(self.bot_bar_fs, text="0%", bg=th["bar"], fg=th["bar_fg"],
                                font=theme.font(9, True, mono=True))
        self.lbl_pct.pack(side=tk.LEFT, padx=px(12))
        self.scale = tk.Scale(self.bot_bar_fs, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=0,
                              bg=th["bar"], fg=th["accent"], troughcolor=blend(th["bar"], "#000", 0.3),
                              highlightthickness=0, activebackground=th["accent"],
                              command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8), pady=px(6))
        self.lbl_page = tk.Label(self.bot_bar_fs, text="", bg=th["bar"], fg=th["dim"],
                                 font=theme.font(9, True, mono=True))
        self.lbl_page.pack(side=tk.LEFT, padx=px(8))
        self.lbl_eta = tk.Label(self.bot_bar_fs, text="", bg=th["bar"], fg=th["dim"],
                                font=theme.font(9, True))
        self.lbl_eta.pack(side=tk.RIGHT, padx=px(12))
        self.bot_bar = self.bot_bar_fs
        self._chrome_visible = True

        self._fs_area.bind("<Configure>", self._on_area_configure)
        self._fs_area.bind("<Motion>", self._on_motion)
        self._fs.bind("<Key>", self.on_key)
        self._fs.focus_set()
        self._sync_mode_btns()
        char = self._page_start_char()
        self.after(40, lambda: self._relayout(keep_char=char))
        self._schedule_hide_chrome()

    def exit_fullscreen(self) -> None:
        if not self._fullscreen:
            return
        self.save_pos()
        char = self._page_start_char()
        if self._fs is not None:
            try:
                self._fs.destroy()
            except tk.TclError:
                pass
            self._fs = None
        self._fullscreen = False
        self._layout_key = None
        self.ctx.set_focus_mode(False)
        # восстановить chrome в обычном виде
        self.top_bar = [w for w in self.chrome.winfo_children() if isinstance(w, tk.Frame)][0]
        # проще пересобрать bars
        for w in self.chrome.winfo_children():
            w.destroy()
        th = self._theme()
        self.top_bar = tk.Frame(self.chrome, bg=th["bar"], height=px(44))
        self.top_bar.pack(fill=tk.X)
        self.top_bar.pack_propagate(False)
        self._build_top_bar(self.top_bar)
        self.read_shell = tk.Frame(self.chrome, bg=th["desk"])
        self.read_shell.pack(fill=tk.BOTH, expand=True)
        self.page_host = tk.Frame(self.read_shell, bg=th["desk"])
        self.page_host.pack(fill=tk.BOTH, expand=True)
        self._build_surface(self.page_host)
        self.bot_bar = tk.Frame(self.chrome, bg=th["bar"], height=px(36))
        self.bot_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.bot_bar.pack_propagate(False)
        self.lbl_pct = tk.Label(self.bot_bar, text="0%", bg=th["bar"], fg=th["bar_fg"],
                                font=theme.font(9, True, mono=True))
        self.lbl_pct.pack(side=tk.LEFT, padx=px(12))
        self.scale = tk.Scale(self.bot_bar, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=0,
                              bg=th["bar"], fg=th["accent"], troughcolor=blend(th["bar"], "#000", 0.3),
                              highlightthickness=0, activebackground=th["accent"],
                              command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8), pady=px(6))
        self.lbl_page = tk.Label(self.bot_bar, text="", bg=th["bar"], fg=th["dim"],
                                 font=theme.font(9, True, mono=True))
        self.lbl_page.pack(side=tk.LEFT, padx=px(8))
        self.lbl_eta = tk.Label(self.bot_bar, text="", bg=th["bar"], fg=th["dim"],
                                font=theme.font(9, True))
        self.lbl_eta.pack(side=tk.RIGHT, padx=px(12))
        self.read_shell.bind("<Configure>", self._on_area_configure)
        self.read_shell.bind("<Motion>", self._on_motion)
        self._chrome_visible = True
        self._sync_mode_btns()
        self._apply_theme()
        self.after(30, lambda: self._relayout(keep_char=char))
        self.focus_set()

    # ------------------------------------------------------------------ toc / keys
    def show_toc(self) -> None:
        if not self.chapters:
            self.ctx.app.set_status(_t("Оглавление не найдено"), AMBER)
            return
        parent = self._fs if self._fs is not None else self
        th = self._theme()
        dlg = tk.Toplevel(parent, bg=th["fallback"])
        dlg.title(_t("Оглавление"))
        dlg.transient(self.winfo_toplevel())
        dlg.geometry(f"{px(440)}x{px(400)}")
        tk.Label(dlg, text=_t("ОГЛАВЛЕНИЕ"), bg=th["fallback"], fg=th["accent"],
                 font=theme.font(12, True)).pack(anchor="w", padx=px(12), pady=px(8))
        fr = tk.Frame(dlg, bg=th["bar"])
        fr.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(6))
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg=th["fallback"], fg=th["fg"], selectbackground=th["accent"],
                        font=theme.font(10), yscrollcommand=sb.set, activestyle="none",
                        highlightthickness=0, bd=0)
        lb.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=lb.yview)
        for _off, title in self.chapters:
            lb.insert(tk.END, title)

        def go(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            self._goto_char(self.chapters[sel[0]][0])
            dlg.destroy()

        lb.bind("<Double-Button-1>", go)
        HudButton(dlg, _t("ПЕРЕЙТИ"), go, color=GREEN, height=34).pack(pady=px(8))

    def to_hyperdrive(self) -> None:
        if self._fullscreen:
            self.exit_fullscreen()
        if not self.tid:
            self.ctx.show("library")
            return
        self.save_pos()
        self.ctx.read(self.tid, self.current_word())

    def on_key(self, e: tk.Event) -> str | None:
        k = e.keysym
        state = e.state
        if k == "F11":
            (self.exit_fullscreen if self._fullscreen else self.enter_fullscreen)()
            return "break"
        if k == "Escape":
            if self._fullscreen:
                self.exit_fullscreen()
            return "break"
        if k in ("Next", "Right", "Down", "space"):
            self.page_next()
            return "break"
        if k in ("Prior", "Left", "Up"):
            self.page_prev()
            return "break"
        if k == "Home":
            self._goto_char(0)
            return "break"
        if k == "End":
            self._goto_char(max(0, len(self.text) - 1))
            return "break"
        if k in ("plus", "equal", "KP_Add"):
            self.font_delta(+1)
            return "break"
        if k in ("minus", "KP_Subtract"):
            self.font_delta(-1)
            return "break"
        if k.lower() == "j" and (state & 0x1):  # Shift+J
            order = list(MODES)
            self.set_mode(order[(order.index(self.mode) + 1) % len(order)])
            return "break"
        if k == "1":
            self.set_mode("page")
            return "break"
        if k == "2":
            self.set_mode("spread")
            return "break"
        if k == "3":
            self.set_mode("scroll")
            return "break"
        return None
