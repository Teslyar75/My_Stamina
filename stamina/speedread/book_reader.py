"""Режим «КНИГА» — обычная читалка (не RSVP): прокрутка, страницы, шрифт, прогресс."""
from __future__ import annotations

from stamina.i18n import t as _t

import re
import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, TEXT, blend, px

from .ui import L

# темы чтения
THEMES = {
    "dark": {"bg": BG2, "fg": TEXT, "sel": CYAN, "panel": PANEL},
    "paper": {"bg": "#F4EFE4", "fg": "#1A1520", "sel": "#8B6914", "panel": "#E8E0D0"},
    "sepia": {"bg": "#E8D9C0", "fg": "#3B2F2F", "sel": "#6B4F2A", "panel": "#D9C8A8"},
}


def _split_words(text: str) -> list[tuple[int, int]]:
    """Список (start, end) слов в тексте — для синхронизации с гипердрайвом."""
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _detect_chapters(text: str) -> list[tuple[int, str]]:
    """Грубый оглавление: (символьный offset, заголовок)."""
    pat = re.compile(
        r"(?m)^(chapter\s+\d+|part\s+\d+|book\s+\d+|глава\s+\d+|часть\s+\d+|"
        r"prologue|epilogue|пролог|эпилог|"
        r"CHAPTER\s+[IVXLC]+|[IVXLC]+\.\s+\w.{0,40})$",
        re.I,
    )
    out = []
    for m in pat.finditer(text):
        title = " ".join(m.group(0).split())[:60]
        out.append((m.start(), title))
        if len(out) >= 80:
            break
    return out


class BookReaderPage(tk.Frame):
    """Читалка книги: непрерывный текст + «страницы» по высоте окна."""

    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.tid: str | None = None
        self.title = ""
        self.text = ""
        self.words: list[tuple[int, int]] = []
        self.chapters: list[tuple[int, str]] = []
        self._applying = False
        self._pages_cache: list[str] = []  # index marks "1.0" style

        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(12), pady=(px(4), 0))
        self.lbl_title = L(top, _t("КНИГА"), fg=AMBER, size=12, bold=True, bg=BG)
        self.lbl_title.pack(side=tk.LEFT)
        self.lbl_prog = L(top, "", fg=MUTED, size=9, bold=True, mono=True, bg=BG)
        self.lbl_prog.pack(side=tk.RIGHT)

        tools = tk.Frame(self, bg=BG)
        tools.pack(fill=tk.X, padx=px(12), pady=px(4))
        HudButton(tools, _t("◀ СТР."), self.page_prev, height=28, font_size=8, width=70).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, _t("СТР. ▶"), self.page_next, height=28, font_size=8, width=70).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, "A−", lambda: self.font_delta(-1), height=28, font_size=9, width=40).pack(side=tk.LEFT, padx=px(2))
        HudButton(tools, "A+", lambda: self.font_delta(+1), height=28, font_size=9, width=40).pack(side=tk.LEFT, padx=px(2))
        self.theme_btns = {}
        for key, name in (("dark", _t("ТЁМНАЯ")), ("paper", _t("БУМАГА")), ("sepia", _t("СЕПИЯ"))):
            b = HudButton(tools, name, lambda k=key: self.set_theme(k), height=28, font_size=8, width=80)
            b.pack(side=tk.LEFT, padx=px(2))
            self.theme_btns[key] = b
        HudButton(tools, _t("ОГЛАВЛЕНИЕ"), self.show_toc, height=28, font_size=8, width=110).pack(
            side=tk.LEFT, padx=px(6))
        HudButton(tools, _t("⚡ ГИПЕРДРАЙВ"), self.to_hyperdrive, color=AMBER, height=28, font_size=8,
                  width=120).pack(side=tk.RIGHT, padx=px(2))
        HudButton(tools, _t("БИБЛИОТЕКА"), lambda: self.ctx.show("library"), height=28, font_size=8,
                  width=110).pack(side=tk.RIGHT, padx=px(2))

        jump = tk.Frame(self, bg=BG)
        jump.pack(fill=tk.X, padx=px(12), pady=(0, px(2)))
        L(jump, _t("ПОЗИЦИЯ"), fg=MUTED, size=8, bold=True, bg=BG).pack(side=tk.LEFT)
        self.scale = tk.Scale(jump, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=0,
                              bg=BG, fg=CYAN, troughcolor=PANEL, highlightthickness=0,
                              activebackground=CYAN, command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8))
        self.lbl_pct = L(jump, "0%", fg=CYAN, size=9, bold=True, mono=True, bg=BG, width=5)
        self.lbl_pct.pack(side=tk.RIGHT)

        wrap = HudPanel(self, _t("ТЕКСТ КНИГИ"))
        wrap.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(0, px(8)))
        self.panel = wrap
        body = wrap.body
        self.text_w = tk.Text(
            body, wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=px(28), pady=px(18),
            insertbackground=CYAN, selectbackground=blend(CYAN, BG, 0.5),
            undo=False, cursor="arrow",
        )
        self.text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(body, orient=tk.VERTICAL, command=self.text_w.yview, width=px(12),
                          bg=PANEL, troughcolor=BG, activebackground=CYAN)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_w.configure(yscrollcommand=sb.set)
        self.text_w.configure(state=tk.DISABLED)
        self.text_w.bind("<Key>", self._on_key)
        self.text_w.bind("<MouseWheel>", self._on_scroll)
        self.text_w.bind("<<Modified>>", lambda _e: self.text_w.edit_modified(False))
        # клик по тексту — фокус для клавиш
        self.text_w.bind("<Button-1>", lambda _e: self.text_w.focus_set())

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill=tk.X, padx=px(12), pady=(0, px(8)))
        L(foot, _t("← → / PgUp PgDn — страница · Home/End — начало/конец · +/− — шрифт · пробел — вниз"),
          fg=MUTED, size=8, bg=BG).pack(side=tk.LEFT)
        self.lbl_page = L(foot, "", fg=MUTED, size=8, mono=True, bg=BG)
        self.lbl_page.pack(side=tk.RIGHT)

        self._apply_theme()
        self._apply_font()

    # -- settings ------------------------------------------------------------------
    @property
    def st(self) -> dict:
        return self.ctx.sstore.settings

    def _theme(self) -> dict:
        return THEMES.get(self.st.get("book_theme", "dark"), THEMES["dark"])

    def _apply_theme(self) -> None:
        th = self._theme()
        self.text_w.configure(bg=th["bg"], fg=th["fg"], insertbackground=th["sel"],
                              selectbackground=blend(th["sel"], th["bg"], 0.45))
        for k, b in self.theme_btns.items():
            b.set_active(k == self.st.get("book_theme", "dark"))

    def _apply_font(self) -> None:
        pt = int(self.st.get("book_font_pt", 16))
        spacing = float(self.st.get("book_line_space", 1.35))
        f = theme.font(pt, mono=False)
        # spacing1/spacing3 в tk — пиксели между строками
        extra = max(0, int(round(pt * (spacing - 1.0))))
        self.text_w.configure(font=f, spacing1=0, spacing2=extra, spacing3=extra)

    def set_theme(self, key: str) -> None:
        if key not in THEMES:
            return
        self.st["book_theme"] = key
        self.ctx.sstore.save()
        self._apply_theme()

    def font_delta(self, d: int) -> None:
        pt = max(11, min(36, int(self.st.get("book_font_pt", 16)) + d))
        self.st["book_font_pt"] = pt
        self.ctx.sstore.save()
        self._apply_font()
        self._update_progress()

    # -- open / close --------------------------------------------------------------
    def open(self, tid: str, *, word: int | None = None) -> None:
        lib = self.ctx.lib
        m = lib.meta(tid)
        if not m:
            return
        self.save_pos()
        self.tid = tid
        self.title = m["title"] + (f" · {m['author']}" if m.get("author") else "")
        self.lbl_title.configure(text=self.title.upper()[:80])
        self.text = lib.reading_text(tid) or ""
        self.words = _split_words(self.text)
        self.chapters = _detect_chapters(self.text)
        lib.set_active("reading", tid)
        self._load_text_widget()
        if word is None:
            word = int(m["positions"]["reading"].get("word", 0))
        self.goto_word(word)
        self._apply_theme()
        self._apply_font()
        self.text_w.focus_set()

    def _load_text_widget(self) -> None:
        self._applying = True
        self.text_w.configure(state=tk.NORMAL)
        self.text_w.delete("1.0", tk.END)
        self.text_w.insert("1.0", self.text)
        self.text_w.configure(state=tk.DISABLED)
        self._applying = False

    def refresh(self) -> None:
        if self.tid is None:
            tid = self.ctx.lib.index.get("active_reading") or (self.ctx.lib.ids() or [None])[0]
            if tid:
                self.open(tid)
            else:
                self.lbl_title.configure(text=_t("КНИГА"))
                self._applying = True
                self.text_w.configure(state=tk.NORMAL)
                self.text_w.delete("1.0", tk.END)
                self.text_w.insert("1.0", _t("Библиотека пуста. Добавьте книгу или скачайте свободную."))
                self.text_w.configure(state=tk.DISABLED)
                self._applying = False
        else:
            self._update_progress()

    def save_pos(self) -> None:
        if not self.tid or not self.words:
            return
        w = self.current_word()
        self.ctx.lib.set_position(self.tid, "reading", w)

    def current_word(self) -> int:
        if not self.words:
            return 0
        try:
            idx = self.text_w.index("@%d,%d" % (px(40), px(40)))
            char = self._index_to_char(idx)
        except tk.TclError:
            char = 0
        # ближайшее слово ≤ char
        lo, hi = 0, len(self.words) - 1
        ans = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.words[mid][0] <= char:
                ans = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return ans

    def _index_to_char(self, index: str) -> int:
        """Tk index → offset в self.text."""
        line, col = map(int, str(index).split("."))
        # строки 1-based
        lines = self.text.split("\n")
        off = sum(len(lines[i]) + 1 for i in range(min(line - 1, len(lines))))
        return off + col

    def _char_to_index(self, char: int) -> str:
        char = max(0, min(char, len(self.text)))
        lines = self.text.split("\n")
        rem = char
        for i, line in enumerate(lines):
            if rem <= len(line):
                return f"{i + 1}.{rem}"
            rem -= len(line) + 1
        return "end"

    def goto_word(self, word: int) -> None:
        if not self.words:
            return
        word = max(0, min(word, len(self.words) - 1))
        char = self.words[word][0]
        idx = self._char_to_index(char)
        self.text_w.configure(state=tk.NORMAL)
        self.text_w.see(idx)
        # подсветка текущей строки
        self.text_w.tag_remove("here", "1.0", tk.END)
        self.text_w.tag_add("here", f"{idx} linestart", f"{idx} lineend")
        th = self._theme()
        self.text_w.tag_configure("here", background=blend(th["sel"], th["bg"], 0.75))
        self.text_w.configure(state=tk.DISABLED)
        self._update_progress()

    # -- navigation ----------------------------------------------------------------
    def page_next(self) -> None:
        self.text_w.yview_scroll(1, "pages")
        self._update_progress()
        self.save_pos()

    def page_prev(self) -> None:
        self.text_w.yview_scroll(-1, "pages")
        self._update_progress()
        self.save_pos()

    def _on_scroll(self, _e=None) -> None:
        self.after(50, self._update_progress)

    def _on_scale(self, val) -> None:
        if self._applying or not self.text:
            return
        pct = float(val) / 100.0
        char = int(pct * max(1, len(self.text) - 1))
        # найти слово
        w = 0
        for i, (a, _b) in enumerate(self.words):
            if a <= char:
                w = i
            else:
                break
        self.goto_word(w)
        self.save_pos()

    def _update_progress(self) -> None:
        if not self.text:
            self.lbl_prog.configure(text="")
            self.lbl_pct.configure(text="0%")
            self.lbl_page.configure(text="")
            return
        try:
            top, bot = self.text_w.yview()
        except tk.TclError:
            top, bot = 0.0, 0.0
        pct = int(round(top * 100))
        self._applying = True
        self.scale.set(pct)
        self._applying = False
        self.lbl_pct.configure(text=f"{pct}%")
        w = self.current_word()
        n = len(self.words) or 1
        # оценка «страниц» (~250 слов)
        page = w // 250 + 1
        pages = max(1, (n + 249) // 250)
        self.lbl_prog.configure(text=_t("слово {0}/{1}").format(w + 1, n))
        self.lbl_page.configure(text=_t("≈ стр. {0} / {1}").format(page, pages))

    def show_toc(self) -> None:
        if not self.chapters:
            self.ctx.app.set_status(_t("Оглавление не найдено — листайте шкалой или страницами"), AMBER)
            return
        dlg = tk.Toplevel(self, bg=BG)
        dlg.title(_t("Оглавление"))
        dlg.transient(self.winfo_toplevel())
        dlg.geometry(f"{px(480)}x{px(420)}")
        L(dlg, _t("ОГЛАВЛЕНИЕ"), fg=AMBER, size=12, bold=True, bg=BG).pack(anchor="w", padx=px(12), pady=px(8))
        fr = tk.Frame(dlg, bg=PANEL)
        fr.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(6))
        sb = tk.Scrollbar(fr)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(fr, bg=BG2, fg=TEXT, selectbackground=CYAN, font=theme.font(10),
                        yscrollcommand=sb.set, activestyle="none", highlightthickness=0)
        lb.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=lb.yview)
        for _off, title in self.chapters:
            lb.insert(tk.END, title)

        def go(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            off, _title = self.chapters[sel[0]]
            # слово по offset
            w = 0
            for i, (a, _b) in enumerate(self.words):
                if a <= off:
                    w = i
                else:
                    break
            self.goto_word(w)
            self.save_pos()
            dlg.destroy()

        lb.bind("<Double-Button-1>", go)
        HudButton(dlg, _t("ПЕРЕЙТИ"), go, color=GREEN, height=34).pack(pady=px(8))

    def to_hyperdrive(self) -> None:
        if not self.tid:
            self.ctx.show("library")
            return
        self.save_pos()
        w = self.current_word()
        self.ctx.read(self.tid, w)

    def _on_key(self, e) -> str | None:
        k = e.keysym
        if k in ("Next", "space", "Right", "Down"):
            self.page_next()
            return "break"
        if k in ("Prior", "Left", "Up"):
            self.page_prev()
            return "break"
        if k == "Home":
            self.goto_word(0)
            self.save_pos()
            return "break"
        if k == "End":
            self.goto_word(max(0, len(self.words) - 1))
            self.save_pos()
            return "break"
        if k in ("plus", "equal", "KP_Add"):
            self.font_delta(+1)
            return "break"
        if k in ("minus", "KP_Subtract"):
            self.font_delta(-1)
            return "break"
        return None
