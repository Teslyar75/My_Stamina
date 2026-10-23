"""Читалка «КНИГА»: нормальный текст (без лесенок Gutenberg), 1 стр / разворот / прокрутка / 2 языка.

Образец режимов — Readest. Текст: оригинал из библиотеки + normalize_book_text.
Двуязычный режим: слева страница оригинала, справа — перевод (тот же дизайн разворота).
"""
from __future__ import annotations

from stamina.i18n import t as _t

import re
import time
import tkinter as tk
import tkinter.font as tkfont

from stamina import theme
from stamina import monitors
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

MODES = ("page", "spread", "scroll", "bilingual")  # + двуязычная: оригинал | перевод
DEFAULT_LINE_SPACE = 1.45
DEFAULT_MODE = "spread"
WPM_ESTIMATE = 230  # для «времени до конца»
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")
# куски для UPLINK: GET Google/MyMemory ломаются на длинных URL (особенно fullscreen-страницы)
_TR_CHUNK = 800  # крупнее куски = меньше запросов = меньше 429
_TR_BOOK_INFLIGHT = 10  # одновременно в сети (fullscreen-страница длиннее)
_TR_PREFETCH_AHEAD = 2   # запас страниц вперёд (текущая вёрстка)
_TR_PREFETCH_BEHIND = 2  # запас страниц назад
# запас по символам текста — переживает смену окна ↔ FS (страницы «перекраиваются»)
_TR_SPAN_AHEAD = 14000
_TR_SPAN_BEHIND = 4000
_TR_WARM_MAX = 400  # предложений при фоновом прогреве книги


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


def _measure_cached(font: tkfont.Font, s: str, cache: dict[str, int]) -> int:
    """font.measure дорогой — кэш по строке (для одного шрифта на проход)."""
    w = cache.get(s)
    if w is None:
        w = font.measure(s)
        cache[s] = w
    return w


def _wrap_para(para: str, font: tkfont.Font, width: int, *, first_indent: int,
               cache: dict[str, int] | None = None) -> list[str]:
    """Перенос абзаца: накопление ширин слов, без measure всей строки."""
    lines, _offs = _wrap_para_offs(para, font, width, first_indent=first_indent,
                                   cache=cache, origin=0)
    return lines


def _wrap_para_offs(para: str, font: tkfont.Font, width: int, *, first_indent: int,
                    cache: dict[str, int] | None = None,
                    origin: int = 0) -> tuple[list[str], list[int]]:
    """Строки абзаца + смещения начала каждой строки в полном тексте."""
    if width < 40:
        width = 40
    if cache is None:
        cache = {}
    spans = list(re.finditer(r"\S+", para))
    if not spans:
        return [""], [origin]
    space_w = _measure_cached(font, " ", cache)
    words = [m.group() for m in spans]
    starts = [m.start() for m in spans]
    widths = [_measure_cached(font, w, cache) for w in words]

    lines: list[str] = []
    offsets: list[int] = []
    i = 0
    n = len(words)
    limit = max(40, width - first_indent)
    while i < n:
        used = 0
        start = i
        while i < n:
            add = widths[i] if i == start else widths[i] + space_w
            if i > start and used + add > limit:
                break
            used += add
            i += 1
            if i == start + 1 and used > limit:
                # слишком длинное слово — режем по символам (редко)
                w = words[start]
                chunk = ""
                lines_long: list[str] = []
                offs_long: list[int] = []
                for ci, ch in enumerate(w):
                    cw = _measure_cached(font, chunk + ch, cache)
                    if chunk and cw > limit:
                        lines_long.append(chunk)
                        offs_long.append(origin + starts[start] + (ci - len(chunk)))
                        chunk = ch
                        limit = width
                    else:
                        chunk += ch
                if chunk:
                    lines_long.append(chunk)
                    offs_long.append(origin + starts[start] + len(w) - len(chunk))
                if lines_long:
                    lines.extend(lines_long)
                    offsets.extend(offs_long)
                start = i  # уже i == start+1
                break
        if start < i:
            lines.append(" ".join(words[start:i]))
            offsets.append(origin + starts[start])
        limit = width
    return (lines or [""]), (offsets or [origin])


def _paginate_spread(flat: list[tuple[str, str]], *, cols: int, col_h: int,
                     lh: int, para_gap: int) -> list[dict]:
    """Разворот: сначала заполняется левая колонка сверху вниз, затем правая
    (текст перетекает L→R), потом следующий разворот. Не две независимые страницы.
    """
    cols = 2 if cols >= 2 else 1
    pages: list[dict] = []
    i = 0
    n = len(flat)
    while i < n or not pages:
        col_data: list[list[tuple[str, str]]] = []
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
                    col_lines.append((text, kind))
                    i += 1
                    break
                used += need
                col_lines.append((text, kind))
                i += 1
            col_data.append(col_lines)
        pages.append({"cols": col_data, "start_line": start_line})
        if n == 0:
            break
    return pages


def _sentence_spans(para: str, origin: int) -> list[tuple[int, str]]:
    """Абсолютные смещения предложений внутри абзаца."""
    para_s = para.strip()
    if not para_s:
        return []
    bits = [b.strip() for b in _SENT_SPLIT.split(para_s) if b.strip()] or [para_s]
    out: list[tuple[int, str]] = []
    pos = 0
    # ищем в исходном para (с возможными пробелами в начале)
    base = para
    for b in bits:
        idx = base.find(b, pos)
        if idx < 0:
            idx = pos
        out.append((origin + idx, b))
        pos = idx + len(b)
    return out


def _paginate_bilingual_sentences(
    paras: list[str],
    para_origins: list[int],
    *,
    font: tkfont.Font,
    text_w: int,
    indent: int,
    col_h: int,
    lh: int,
    para_gap: int,
    cache: dict,
) -> tuple[list[dict], list[int]]:
    """Страницы 2 ЯЗЫКА: колонка не режет предложение посередине (если оно влезает целиком).

    Слева и справа — один и тот же смысловой объём; UPLINK-ключи стабильны при смене FS.
    """
    # unit: lines [(text, kind)], offs [...], height с учётом para_gap в начале
    units: list[dict] = []
    for para, origin in zip(paras, para_origins):
        spans = _sentence_spans(para, origin)
        for si, (s_origin, sent) in enumerate(spans):
            first_indent = indent if si == 0 else 0
            wrapped, offs = _wrap_para_offs(
                sent, font, text_w, first_indent=first_indent, cache=cache, origin=s_origin)
            lines: list[tuple[str, str]] = []
            for i, ln in enumerate(wrapped):
                if si == 0 and i == 0:
                    kind = "first"
                else:
                    kind = "cont"
                lines.append((ln, kind))
            h = 0
            for i, (_ln, kind) in enumerate(lines):
                h += lh + (para_gap if kind == "first" and i == 0 else 0)
            h_no_gap = h - (para_gap if lines and lines[0][1] == "first" else 0)
            units.append({
                "lines": lines,
                "offs": list(offs),
                "height": h,
                "height_no_gap": max(lh, h_no_gap),
                "para_start": si == 0,
            })

    pages: list[dict] = []
    line_starts: list[int] = []
    i = 0
    n = len(units)
    while i < n or not pages:
        col_lines: list[tuple[str, str]] = []
        used = 0
        start_line = len(line_starts)
        while i < n:
            u = units[i]
            need = u["height"] if (col_lines and u["para_start"]) else u["height_no_gap"]
            if not col_lines:
                need = u["height"] if u["para_start"] else u["height_no_gap"]
            if col_lines and used + need > col_h:
                break
            if not col_lines and need > col_h:
                # одно гигантское предложение — режем по строкам (редко)
                for (ln, kind), off in zip(u["lines"], u["offs"]):
                    row_need = lh + (para_gap if kind == "first" and col_lines else 0)
                    if col_lines and used + row_need > col_h:
                        pages.append({"cols": [col_lines], "start_line": start_line})
                        col_lines, used, start_line = [], 0, len(line_starts)
                    used += row_need
                    col_lines.append((ln, kind))
                    line_starts.append(off)
                i += 1
                continue
            used += need
            for (ln, kind), off in zip(u["lines"], u["offs"]):
                col_lines.append((ln, kind))
                line_starts.append(off)
            i += 1
        pages.append({"cols": [col_lines], "start_line": start_line})
        if n == 0:
            break
    return pages, line_starts


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
        # page_i -> (cache_key, lines, font_pt, indent_px)
        self._page_tr_cache: dict = {}
        self._tr_poll_job = None
        self._tr_dir: tuple[str, str] = ("en", "ru")
        self._tr_pending_pages: set[int] = set()
        self._bilingual_right_pt: int | None = None
        self._tr_wait_until: float = 0.0   # monotonic: ETA перевода страницы
        self._tr_wait_missing: int = 0
        self._tr_eta_job = None
        self._tr_poll_busy = False
        self._paint_busy = False
        self._tr_last_drawn_missing: int = -1
        self._size_relayout_job = None
        # готовый перевод страницы по тексту оригинала (переживает fullscreen и ← →)
        self._plain_tr_mem: dict[tuple[str, str, str], list[str]] = {}
        # предложение → перевод (не зависит от нарезки страницы / fullscreen)
        self._tr_sent_mem: dict[tuple[str, str, str], str] = {}
        # после входа в FS не cancel_group и дольше debounce — иначе срывает UPLINK
        self._tr_fs_guard_until: float = 0.0

        # ---- чтение вслух ----------------------------------------------------
        self.tts = None                     # ReaderQueue (создаётся лениво)
        self._tts_job = None                # опрос событий движка
        self._hl_span: tuple[int, int] | None = None   # границы читаемой фразы
        self._line_boxes: list[tuple[int, int, int, int, int]] = []  # строки страницы
        self._aa_frame: tk.Frame | None = None         # панель «Aa»

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
        self._build_bot_bar(self.bot_bar)

        self.read_shell.bind("<Configure>", self._on_area_configure)
        self.read_shell.bind("<Motion>", self._on_motion)
        self.bind_all("<Escape>", self._esc_global, add="+")
        self.bind("<Destroy>", self._on_destroy_speech, add="+")
        self._bind_speech_keys()
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
        pt = self._font_pt()
        spec = _reading_font(pt)
        key = (spec[0], pt)
        if getattr(self, "_font_cache_key", None) != key:
            self._font_cache_key = key
            self._font_cache = tkfont.Font(font=spec)
            self._measure_cache: dict[str, int] = {}
        return self._font_cache

    def _line_h(self) -> int:
        f = self._font_obj()
        return max(1, int(round(f.metrics("linespace") * self._line_space())))

    # ------------------------------------------------------------------ chrome
    def _tip(self, widget, text: str) -> None:
        widget.tooltip = text  # type: ignore[attr-defined]

        def enter(_e):
            self.ctx.app.set_status(text, MUTED)

        widget.bind("<Enter>", enter, add="+")

    def _build_bot_bar(self, bar: tk.Frame) -> None:
        th = self._theme()
        for w in bar.winfo_children():
            w.destroy()
        self.lbl_pct = tk.Label(bar, text="0%", bg=th["bar"], fg=th["bar_fg"],
                                font=theme.font(9, True, mono=True))
        self.lbl_pct.pack(side=tk.LEFT, padx=px(12))
        # чтение вслух: одна кнопка-переключатель + стоп + скорость
        self.btn_read = HudButton(bar, _t("▶ ЧИТАТЬ"), self.speech_toggle, height=26,
                                  font_size=8, width=96, color=GREEN)
        self.btn_read.pack(side=tk.LEFT, padx=(0, px(3)), pady=px(4))
        self._tip(self.btn_read, _t("Читать вслух с этого места (пробел — пауза)"))
        self.btn_stop = HudButton(bar, "■", self.speech_stop, height=26, font_size=8,
                                  width=26, color=th["accent"])
        self.btn_stop.pack(side=tk.LEFT, padx=px(1), pady=px(4))
        self._tip(self.btn_stop, _t("Остановить чтение (Esc)"))
        self.btn_slow = HudButton(bar, "−", lambda: self.speech_rate_delta(-1), height=26,
                                  font_size=8, width=24, color=th["accent"])
        self.btn_slow.pack(side=tk.LEFT, padx=px(1), pady=px(4))
        self._tip(self.btn_slow, _t("Голос медленнее"))
        self.btn_fast = HudButton(bar, "+", lambda: self.speech_rate_delta(+1), height=26,
                                  font_size=8, width=24, color=th["accent"])
        self.btn_fast.pack(side=tk.LEFT, padx=px(1), pady=px(4))
        self._tip(self.btn_fast, _t("Голос быстрее"))
        # выбор чтеца: «по языку текста» → голоса OneCore → голоса SAPI
        self.btn_voice = HudButton(bar, self._voice_btn_text(), self.speech_voice_cycle,
                                   height=26, font_size=8, width=94, color=th["accent"])
        self.btn_voice.pack(side=tk.LEFT, padx=px(1), pady=px(4))
        self._tip(self.btn_voice, _t("Голос чтеца: следующий в списке"))
        # «СФОРМИРОВАТЬ КАРТОЧКИ» убрана: та же кнопка есть в верхней панели («→ КАРТОЧКИ»)
        self.scale = tk.Scale(bar, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=0,
                              bg=th["bar"], fg=th["accent"], troughcolor=blend(th["bar"], "#000000", 0.3),
                              highlightthickness=0, activebackground=th["accent"],
                              command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(8), pady=px(6))
        self.lbl_speech = tk.Label(bar, text="", bg=th["bar"], fg=th["dim"],
                                   font=theme.font(8, True, mono=True))
        self.lbl_speech.pack(side=tk.LEFT, padx=px(6))
        self.lbl_page = tk.Label(bar, text="", bg=th["bar"], fg=th["dim"],
                                 font=theme.font(9, True, mono=True))
        self.lbl_page.pack(side=tk.LEFT, padx=px(8))
        self.lbl_eta = tk.Label(bar, text="", bg=th["bar"], fg=th["dim"],
                                font=theme.font(9, True))
        self.lbl_eta.pack(side=tk.RIGHT, padx=px(12))
        self._speech_status()

    def _build_top_bar(self, bar: tk.Frame) -> None:
        th = self._theme()
        for w in bar.winfo_children():
            w.destroy()

        def btn(text, cmd, tip, *, color=None, width=None, active=False):
            b = HudButton(bar, text, cmd, height=30, font_size=8,
                          width=width or max(50, 10 + len(text) * 7),
                          color=color or th["accent"], active=active)
            b.pack(side=tk.LEFT, padx=px(1), pady=px(6))
            self._tip(b, tip)
            return b

        btn(_t("← БИБЛИОТЕКА"), lambda: self._go_library(), _t("Вернуться в библиотеку"),
            width=110)
        btn("◀", self.page_prev, _t("Предыдущая страница (← / PgUp)"), width=34)
        btn("▶", self.page_next, _t("Следующая страница (→ / PgDn)"), width=34)
        btn(_t("Aa"), self.toggle_aa, _t("Шрифт, интерлиньяж, тема, чтение вслух"), width=40)

        self.mode_btns = {}
        bi_tip = _t("Слева оригинал, справа готовый перевод книги") if self._fixed_bilingual() else (
            _t("Слева оригинал книги, справа перевод UPLINK"))
        for key, lab, tip, w in (
            ("page", _t("1 СТР"), _t("Одна страница по центру"), 64),
            ("spread", _t("РАЗВОРОТ"), _t("Две страницы, как открытая книга"), 88),
            ("bilingual", _t("2 ЯЗЫКА"), bi_tip, 80),
            ("scroll", _t("ПРОКРУТКА"), _t("Непрерывный текст"), 88),
        ):
            b = btn(lab, lambda k=key: self.set_mode(k), tip, width=w)
            self.mode_btns[key] = b

        # темы и шрифт живут в панели «Aa» (верхняя панель иначе не влезает на узком окне)
        btn(_t("ОГЛ."), self.show_toc, _t("Оглавление"), width=52)
        btn(_t("⚡ RSVP"), self.to_hyperdrive, _t("Открыть в гипердрайве с этого места"),
            color=AMBER, width=72)
        # Сразу после RSVP — иначе на узле/с DPI кнопка справа пропадала за краем.
        if self._fullscreen:
            btn(_t("✕"), self.exit_fullscreen, _t("Выйти из полного экрана (Esc)"),
                color=AMBER, width=40)
        else:
            btn(_t("ЭКРАН"), self.enter_fullscreen, _t("На весь экран (F11)"),
                color=GREEN, width=72)

        # справа — нельзя пропустить: карточки из прочитанного
        cards = HudButton(bar, _t("→ КАРТОЧКИ"), self.to_book_cards, height=30, font_size=9,
                          width=120, color=AMBER, active=True)
        cards.pack(side=tk.RIGHT, padx=px(8), pady=px(6))
        self._tip(cards, _t("Собрать карточки из уже прочитанного текста и открыть АНГЛИЙСКИЙ → ИЗ КНИГИ"))

        self.lbl_title = tk.Label(bar, text=_t("КНИГА"), bg=th["bar"], fg=th["bar_fg"],
                                  font=theme.font(9, True))
        self.lbl_title.pack(side=tk.LEFT, padx=px(6))

    def _go_library(self) -> None:
        if self._fullscreen:
            self.exit_fullscreen()
        self.speech_stop()
        self.save_pos()
        self.ctx.show("library")

    def to_book_cards(self) -> None:
        """Синхронизировать прочитанное и открыть АНГЛИЙСКИЙ → ИЗ КНИГИ."""
        if self._fullscreen:
            self.exit_fullscreen()
        self.save_pos()
        tid = self.tid
        app = self.ctx.app
        try:
            app.set_status(_t("Формирую карточки из прочитанного…"), AMBER)
        except Exception:
            pass
        try:
            app.show("english")
        except Exception:
            try:
                app.set_status(_t("Не удалось открыть АНГЛИЙСКИЙ"), AMBER)
            except Exception:
                pass
            return

        def go(attempt: int = 0) -> None:
            eng = (getattr(app, "screens", None) or {}).get("english")
            if eng is None:
                try:
                    app.set_status(_t("Вкладка АНГЛИЙСКИЙ недоступна"), AMBER)
                except Exception:
                    pass
                return
            if not getattr(eng, "_built", False):
                if attempt < 50:
                    self.after(200, lambda: go(attempt + 1))
                else:
                    try:
                        app.set_status(_t("Словарь ещё загружается — нажмите «→ КАРТОЧКИ» снова"), AMBER)
                    except Exception:
                        pass
                return
            try:
                eng.open_book_cards(tid)
            except Exception:
                try:
                    eng.show("book")
                    app.set_status(_t("Откройте вкладку ИЗ КНИГИ и нажмите «СФОРМИРОВАТЬ ИЗ ПРОЧИТАННОГО»"),
                                   AMBER)
                except Exception:
                    pass

        go()

    def _schedule_hide_chrome(self) -> None:
        if self._hide_job:
            try:
                self.after_cancel(self._hide_job)
            except tk.TclError:
                pass
        if self.mode in ("scroll",):
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
            # page / spread / bilingual — canvas-книга
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
            try:
                b.set_active(k == self._theme_key())
            except tk.TclError:
                pass  # панель «Aa» закрыта — кнопки уже уничтожены

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            return
        char = self._page_start_char()
        self.st["book_mode"] = mode
        self.st["book_columns"] = 2 if mode in ("spread", "bilingual") else 1
        self.ctx.sstore.save()
        self._layout_key = None
        self._page_tr_cache = {}
        if mode != "bilingual":
            self._stop_tr_timers()
            self._tr_pending_pages.clear()
            self._tr_wait_until = 0.0
            self._tr_last_drawn_missing = -1
        if mode == "bilingual":
            self._refresh_tr_dir()
            self._tr_last_drawn_missing = -1
            if not self._fixed_bilingual():
                self.after(400, self._warm_book_translation)
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
        if getattr(self, "lbl_aa_font", None) is not None and self.lbl_aa_font.winfo_exists():
            self.lbl_aa_font.configure(text=str(self._font_pt()))
        self._layout_key = None
        self.after(20, lambda: self._relayout(keep_char=char))

    def _apply_theme(self) -> None:
        th = self._theme()
        self.top_bar.configure(bg=th["bar"])
        self.bot_bar.configure(bg=th["bar"])
        for lab in (self.lbl_pct, self.lbl_page, self.lbl_eta, self.lbl_speech):
            lab.configure(bg=th["bar"], fg=th["dim"] if lab is not self.lbl_pct else th["bar_fg"])
        self.lbl_title.configure(bg=th["bar"], fg=th["bar_fg"])
        self.scale.configure(bg=th["bar"], fg=th["accent"],
                             troughcolor=blend(th["bar"], "#000000", 0.3),
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
        if self._aa_frame is not None:
            if self._aa_visible():
                self._aa_build()
            else:
                self._aa_frame.configure(bg=th["bar"])

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
        self.speech_stop()
        self.tid = tid
        self.title = m["title"] + (f" · {m['author']}" if m.get("author") else "")
        self.lbl_title.configure(text=self.title[:72])
        # оригинал (не prepared для печати)
        self.raw_text = lib.reading_text(tid) or ""
        self.text = normalize_book_text(self.raw_text)
        self.paras = paragraphs(self.text)
        self.words = _split_words(self.text)
        self.chapters = _detect_chapters(self.text)
        self._hl_span = None
        lib.set_active("reading", tid)
        if word is None:
            word = int(m["positions"]["reading"].get("word", 0))
        char = self.words[word][0] if self.words and 0 <= word < len(self.words) else 0
        self._layout_key = None
        self._page_tr_cache = {}
        self._refresh_tr_dir()
        self._apply_theme()
        self._bind_speech_keys()
        if self.tts is not None:
            self.tts.set_lang(self._speech_lang())
            self.tts.load(self.text, char)
        self.after(30, lambda: self._relayout(keep_char=char))
        self.focus_set()
        # фоновый UPLINK только для обычных книг; у bilingual перевод уже в файле
        if self.mode == "bilingual" and not self._fixed_bilingual():
            self.after(600, self._warm_book_translation)

    def _book_meta(self) -> dict | None:
        return self.ctx.lib.meta(self.tid) if self.tid else None

    def _fixed_bilingual(self) -> bool:
        """Книга с готовым translation.txt — без UPLINK."""
        from stamina.library import is_bilingual
        if not is_bilingual(self._book_meta()):
            return False
        return bool(self.ctx.lib.translation(self.tid or ""))

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
        try:
            from stamina.english.book_sentences import notify_reading
            notify_reading(self.ctx.app, self.ctx.lib, self.tid)
        except Exception:
            pass

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

    # ------------------------------------------------------ чтение вслух
    RATE_MIN, RATE_MAX = -4, 6

    # -- настройки ---------------------------------------------------------
    def speech_rate(self) -> int:
        try:
            v = int(self.st.get("book_speech_rate", 0))
        except (TypeError, ValueError):
            v = 0
        return max(self.RATE_MIN, min(self.RATE_MAX, v))

    @staticmethod
    def _rate_word(rate: int) -> str:
        return f"×{1 + int(rate) * 0.15:.2f}".replace(".", ",")

    def _speech_minutes(self, chars: int) -> int:
        cpm = max(200, 1000 + self.speech_rate() * 120)
        return int(round(max(0, chars) / cpm))

    def _speech_auto_turn(self) -> bool:
        return bool(self.st.get("book_speech_auto_turn", True))

    def _speech_lang(self) -> str:
        v = str(self.st.get("book_speech_lang", "") or "")
        if v:
            return v
        lang = (self._tr_dir or ("", ""))[0]
        if lang:
            return lang
        try:
            from stamina.voice.engine import guess_lang
            return guess_lang(self.text[:4000])
        except Exception:  # noqa: BLE001
            return ""

    def _speech_voice(self) -> str:
        """Выбор пилота: `хранилище:имя` или пусто — голос по языку текста."""
        return str(self.st.get("book_speech_voice", "") or "")

    @staticmethod
    def _voice_short(spec: str) -> str:
        name = spec.split(":", 1)[-1] if ":" in spec else ""
        return name.split()[-1] if name else ""

    def _voice_btn_text(self) -> str:
        short = self._voice_short(self._speech_voice())
        return _t("ГОЛОС: {0}").format(short.upper()) if short else _t("ГОЛОС: ЯЗЫК")

    # -- запуск движка ------------------------------------------------------
    def _ensure_tts(self):
        if self.tts is not None:
            if self.tts.text != self.text:
                self.tts.load(self.text, self._page_start_char())
            return self.tts
        try:
            from stamina.voice.engine import make_engine_for
            from stamina.voice.reader_tts import ReaderQueue
        except Exception as exc:  # noqa: BLE001
            self._speech_status(_t("Озвучка недоступна: {0}").format(exc))
            return None
        eng, voice = make_engine_for(self._speech_voice())
        if not getattr(eng, "available", False):
            self._speech_status(eng.why_unavailable() or _t("Движок озвучки недоступен"))
            return None
        self.tts = ReaderQueue(eng, self.text, rate=self.speech_rate(),
                               lang=self._speech_lang(), voice=voice or "",
                               duck_radio=bool(self.st.get("book_speech_duck_radio", True)))
        return self.tts

    # -- команды интерфейса --------------------------------------------------
    def speech_toggle(self) -> None:
        q = self._ensure_tts()
        if q is None:
            return
        if q.state == "playing":
            q.pause()
        elif q.state == "paused":
            q.resume()
        else:
            start = self._page_start_char()
            if q.text != self.text:
                q.load(self.text, start)
            q.play(from_char=start)
            self._ensure_tts_tick()
        self._sync_speech_btn()
        self._speech_status()

    def speech_stop(self) -> None:
        if self.tts is None:
            self._speech_status()
            return
        self.tts.stop()
        self._hl_span = None
        self._paint_speech_marks()
        self.save_pos()
        self._sync_speech_btn()
        self._speech_status()

    def speech_rate_delta(self, d: int) -> None:
        self.st["book_speech_rate"] = max(self.RATE_MIN, min(self.RATE_MAX, self.speech_rate() + d))
        self.ctx.sstore.save()
        if self.tts is not None:
            self.tts.set_rate(self.speech_rate())
            if self.tts.state == "playing":
                self.tts.step(0)  # перечитать текущую фразу новым темпом
        if getattr(self, "lbl_aa_rate", None) is not None and self.lbl_aa_rate.winfo_exists():
            self.lbl_aa_rate.configure(text=self._rate_word(self.speech_rate()))
        self._speech_status()

    def speech_voice_cycle(self) -> None:
        """Перебрать голоса чтеца: «по языку текста» → OneCore → SAPI. Выбор запоминается."""
        try:
            from stamina.voice.engine import voice_options
            opts = voice_options()
        except Exception as exc:  # noqa: BLE001
            self._speech_status(_t("Голоса недоступны: {0}").format(exc))
            return
        if not opts:
            return
        specs = [spec for _label, spec in opts]
        cur = self._speech_voice()
        spec = specs[(specs.index(cur) + 1) % len(specs)] if cur in specs else specs[1 % len(specs)]
        self.st["book_speech_voice"] = spec
        self.ctx.sstore.save()
        if self.tts is not None:
            self.speech_stop()      # остановиться по-честному, запомнив место
            self.tts = None         # новый голос — новый движок
        if getattr(self, "btn_voice", None) is not None and self.btn_voice.winfo_exists():
            self.btn_voice.set_text(self._voice_btn_text())
        label = dict((s, l) for l, s in opts).get(spec, spec)
        self._speech_status(_t("Голос: {0}").format(label))

    def _sync_speech_btn(self) -> None:
        if getattr(self, "btn_read", None) is None or not self.btn_read.winfo_exists():
            return
        state = self.tts.state if self.tts is not None else "idle"
        if state == "playing":
            self.btn_read.set_text(_t("❚❚ ПАУЗА"))
        elif state == "paused":
            self.btn_read.set_text(_t("▶ ДАЛЬШЕ"))
        else:
            self.btn_read.set_text(_t("▶ ЧИТАТЬ"))
        self.btn_read.set_active(state == "playing")

    def _speech_status(self, extra: str = "") -> None:
        lbl = getattr(self, "lbl_speech", None)
        if lbl is None or not lbl.winfo_exists():
            return
        q = self.tts
        state = q.state if q is not None else "idle"
        if extra:
            txt = extra
        elif q is None or state == "idle":
            txt = _t("вслух выкл · {0}").format(self._rate_word(self.speech_rate()))
        else:
            done, total = q.progress()
            pct = int(100 * done / total) if total else 0
            left = self._speech_minutes(total - done)
            key = _t("пауза · {0}% · ≈ {1} мин") if state == "paused" else _t("вслух · {0}% · ≈ {1} мин")
            txt = key.format(pct, left)
        lbl.configure(text=txt)

    # -- события очереди -----------------------------------------------------
    def _ensure_tts_tick(self) -> None:
        if self._tts_job is None:
            self._tts_job = self.after(250, self._tts_tick)

    def _tts_tick(self) -> None:
        self._tts_job = None
        q = self.tts
        if q is None:
            return
        for kind, payload in q.poll():
            if kind == "segment" and payload is not None:
                self._on_speech_segment(payload)
            elif kind == "finished":
                self._hl_span = None
                self._paint_speech_marks()
                self.save_pos()
                self._speech_status(_t("Книга прочитана"))
            elif kind == "error" and payload:
                self._speech_status(str(payload)[:48])
        self._sync_speech_btn()
        self._speech_status()
        if q.state != "idle":
            self._tts_job = self.after(250, self._tts_tick)

    def _on_speech_segment(self, seg) -> None:
        self._hl_span = (int(seg.start), int(seg.end))
        if self.mode == "scroll":
            if self.scroll_view is not None:
                try:
                    self.scroll_view.see(self._char_to_tk(seg.start))
                except tk.TclError:
                    pass
        elif self._speech_auto_turn():
            start, end = self._page_range()
            if not (start <= seg.start < end):
                self._goto_char(seg.start, save=False)
        self._paint_speech_marks()

    # -- подсветка -----------------------------------------------------------
    def _page_range(self) -> tuple[int, int]:
        """[первый символ страницы, первый символ следующей) — для автоперевода."""
        if not self._pages or not self._line_starts:
            return 0, len(self.text)
        i = max(0, min(self._page_i, len(self._pages) - 1))
        sl = int(self._pages[i].get("start_line", 0))
        start = self._line_starts[sl] if 0 <= sl < len(self._line_starts) else 0
        nsl = int(self._pages[i + 1].get("start_line", 0)) if i + 1 < len(self._pages) else -1
        end = self._line_starts[nsl] if 0 <= nsl < len(self._line_starts) else len(self.text)
        return start, end

    def _hl_lines(self) -> set[int]:
        span = self._hl_span
        starts = self._line_starts
        if not span or not starts:
            return set()
        start, end = span
        out = set()
        for i, sc in enumerate(starts):
            nxt = starts[i + 1] if i + 1 < len(starts) else len(self.text) + 1
            if sc < end and nxt > start:
                out.add(i)
        return out

    def _paint_speech_marks(self) -> None:
        """Подсветка читаемой фразы: поверх текста, штриховкой — буквы остаются видны."""
        th = self._theme()
        span = self._hl_span
        if self.mode == "scroll":
            view = self.scroll_view
            if view is None:
                return
            try:
                view.tag_remove("speech", "1.0", "end")
                if span:
                    view.tag_configure("speech",
                                       background=blend(th["accent"], th["fallback"], 0.55))
                    view.tag_add("speech", self._char_to_tk(span[0]), self._char_to_tk(span[1]))
            except tk.TclError:
                pass
            return
        c = self.spread
        if c is None:
            return
        try:
            c.delete("speech")
        except tk.TclError:
            return
        lines = self._hl_lines()
        if not lines or not self._line_boxes:
            return
        over = blend(th["accent"], th["fallback"], 0.55)
        for ln, x0, y0, x1, y1 in self._line_boxes:
            if ln not in lines:
                continue
            c.create_rectangle(x0 - px(3), y0 - px(1) - 1, x1 + px(3), y1 - 2,
                               fill=over, outline="", stipple="gray25", tags="speech")
            c.create_rectangle(x0 - px(6), y0 - 1, x0 - px(4), y1 - 2,
                               fill=th["accent"], outline="", tags="speech")

    # -- горячие клавиши -----------------------------------------------------
    def _bind_speech_keys(self) -> None:
        for w in (self, self.spread, self.scroll_view):
            if w is None or getattr(w, "_speech_keys", False):
                continue
            try:
                w._speech_keys = True  # type: ignore[attr-defined]
                w.bind("<space>", self._on_space, add="+")
                w.bind("<Escape>", self._on_esc_speech, add="+")
            except tk.TclError:
                pass

    def _on_space(self, _e=None):
        if self._aa_visible():
            self._aa_hide()
            return "break"
        self.speech_toggle()
        return "break"

    def _on_esc_speech(self, _e=None):
        if self._aa_visible():
            self._aa_hide()
            return "break"
        if self.tts is not None and self.tts.state != "idle":
            self.speech_stop()
            return "break"
        return None

    def _on_destroy_speech(self, e=None) -> None:
        if e is not None and getattr(e, "widget", None) is not self:
            return
        if self._tts_job is not None:
            try:
                self.after_cancel(self._tts_job)
            except tk.TclError:
                pass
            self._tts_job = None
        if self.tts is not None:
            try:
                self.tts.stop()
                self.tts.engine.close()
            except Exception:  # noqa: BLE001
                pass
            self.tts = None

    # -- панель «Aa» ---------------------------------------------------------
    def _aa_visible(self) -> bool:
        return bool(self._aa_frame is not None and self._aa_frame.winfo_ismapped())

    def toggle_aa(self) -> None:
        if self._aa_visible():
            self._aa_hide()
        else:
            self._aa_show()

    def _aa_show(self) -> None:
        self._aa_build()
        if self._aa_frame is not None:
            self._aa_frame.place(relx=1.0, rely=0.0, x=-px(16), y=px(50), anchor="ne")
            self._aa_frame.lift()

    def _aa_hide(self) -> None:
        if self._aa_frame is not None:
            self._aa_frame.place_forget()

    def _aa_build(self) -> None:
        if self._aa_frame is None:
            self._aa_frame = tk.Frame(self.read_shell, bd=0, highlightthickness=1)
        f = self._aa_frame
        for w in f.winfo_children():
            w.destroy()
        th = self._theme()
        f.configure(bg=th["bar"], highlightbackground=th["accent"], highlightcolor=th["accent"])

        def row(label: str) -> tk.Frame:
            fr = tk.Frame(f, bg=th["bar"])
            fr.pack(fill=tk.X, padx=px(10), pady=px(3))
            tk.Label(fr, text=label, bg=th["bar"], fg=th["dim"],
                     font=theme.font(8, True)).pack(side=tk.LEFT, padx=(0, px(8)))
            return fr

        def small(parent, text, cmd, tip, width=30, color=None) -> HudButton:
            b = HudButton(parent, text, cmd, height=24, font_size=8, width=width,
                          color=color or th["accent"])
            b.pack(side=tk.LEFT, padx=px(1))
            self._tip(b, tip)
            return b

        r = row(_t("AA ШРИФТ"))
        small(r, "A−", lambda: self.font_delta(-1), _t("Мельче шрифт (−)"))
        small(r, "A+", lambda: self.font_delta(+1), _t("Крупнее шрифт (+)"))
        self.lbl_aa_font = tk.Label(r, text=str(self._font_pt()), bg=th["bar"], fg=th["bar_fg"],
                                    font=theme.font(8, True, mono=True))
        self.lbl_aa_font.pack(side=tk.LEFT, padx=px(4))
        r = row(_t("ИНТЕРЛИНЬЯЖ"))
        small(r, "−", lambda: self.line_delta(-0.05), _t("Плотнее строки"))
        small(r, "+", lambda: self.line_delta(+0.05), _t("Просторнее строки"))
        r = row(_t("ТЕМА"))
        self.theme_btns = {}
        for key, lab, tip in (
            ("paper", _t("БУМАГА"), _t("Светлая бумага")),
            ("sepia", _t("СЕПИЯ"), _t("Тёплая сепия")),
            ("night", _t("НОЧЬ"), _t("Тёмная тема")),
        ):
            self.theme_btns[key] = small(r, lab, lambda k=key: self.set_theme(k), tip, width=68)
        r = row(_t("ВСЛУХ"))
        small(r, "−", lambda: self.speech_rate_delta(-1), _t("Голос медленнее"))
        self.lbl_aa_rate = tk.Label(r, text=self._rate_word(self.speech_rate()), bg=th["bar"],
                                    fg=th["bar_fg"], font=theme.font(8, True, mono=True))
        self.lbl_aa_rate.pack(side=tk.LEFT, padx=px(4))
        small(r, "+", lambda: self.speech_rate_delta(+1), _t("Голос быстрее"))
        small(r, _t("▶/❚❚"), self.speech_toggle, _t("Читать вслух / пауза"), width=46, color=GREEN)
        small(r, "■", self.speech_stop, _t("Остановить чтение"), width=26)
        r = row(_t("ПАНЕЛЬ"))
        small(r, _t("✕"), self._aa_hide, _t("Скрыть панель (Esc)"), width=26, color=AMBER)
        self._sync_mode_btns()

    def line_delta(self, d: float) -> None:
        char = self._page_start_char()
        self.st["book_line_space"] = round(max(1.3, min(1.7, self._line_space() + d)), 2)
        self.ctx.sstore.save()
        self._layout_key = None
        self.after(20, lambda: self._relayout(keep_char=char))

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
        # при входе в fullscreen размер «прыгает» — не дёргать вёрстку каждые 180 мс
        delay = 480 if time.monotonic() < self._tr_fs_guard_until else 180
        self._relayout_job = self.after(delay, lambda: self._relayout(keep_char=char))

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
        cache = getattr(self, "_measure_cache", None)
        if cache is None:
            self._measure_cache = cache = {}
        lh = self._line_h()
        indent = _measure_cached(font, "    ", cache)
        # bilingual: листаем по одной колонке оригинала, рисуем как разворот (оригинал|перевод)
        paginate_cols = 2 if self.mode == "spread" else 1
        draw_cols = 2 if self.mode in ("spread", "bilingual") else 1

        # геометрия книги
        outer = max(px(12), int(sw * 0.025))
        top = max(px(10), int(sh * 0.03))
        bottom = max(px(12), int(sh * 0.035))
        spine = px(10) if draw_cols == 2 else 0
        book_w = max(160, sw - outer * 2)
        book_h = max(120, sh - top - bottom)
        page_w = (book_w - spine) // draw_cols
        pad_x = max(px(16), int(page_w * 0.07))
        pad_y = max(px(14), int(book_h * 0.045))
        # ограничить ширину одной страницы ~75 символов
        avg = max(4.0, _measure_cached(font, "abcdefghijklmnopqrstuvwxyz", cache) / 26)
        max_text = int(avg * 72)
        text_w = min(max(80, page_w - pad_x * 2), max_text if draw_cols == 1 else max(80, page_w - pad_x * 2))
        if draw_cols == 1:
            text_w = min(text_w, max_text)

        col_h = max(40, book_h - pad_y * 2)
        para_gap = max(2, int(lh * 0.35))
        space_w = _measure_cached(font, " ", cache)

        key = (text_w, col_h, paginate_cols, draw_cols, self._font_pt(), self._theme_key(),
               len(self.text), lh, para_gap, self.mode)
        geom = dict(outer=outer, top=top, book_w=book_w, book_h=book_h,
                    page_w=page_w, spine=spine, pad_x=pad_x, pad_y=pad_y,
                    text_w=text_w, lh=lh, indent=indent, para_gap=para_gap,
                    cols=paginate_cols, draw_cols=draw_cols, col_h=col_h, space_w=space_w)
        if key == self._layout_key and self._pages:
            self._geom = geom
            self._goto_char(keep_char, save=False)
            return
        self._layout_key = key
        self._geom = geom

        if not self.paras:
            self._pages = [{"cols": [[] for _ in range(paginate_cols)], "start_line": 0}]
            self._line_starts = [0]
            self._page_i = 0
            self._show_page()
            return

        # смещения абзацев одним проходом
        para_origins: list[int] = []
        pos = 0
        for para in self.paras:
            idx = self.text.find(para, pos)
            if idx < 0:
                idx = pos
            para_origins.append(idx)
            pos = idx + len(para)

        if self.mode == "bilingual":
            # целые предложения на странице — стабильные ключи TR при смене окна/FS
            self._pages, self._line_starts = _paginate_bilingual_sentences(
                self.paras, para_origins, font=font, text_w=text_w, indent=indent,
                col_h=col_h, lh=lh, para_gap=para_gap, cache=cache)
        else:
            self._line_starts = []
            flat: list[tuple[str, str]] = []
            for para, origin in zip(self.paras, para_origins):
                wrapped, offs = _wrap_para_offs(para, font, text_w, first_indent=indent,
                                                cache=cache, origin=origin)
                for i, (ln, off) in enumerate(zip(wrapped, offs)):
                    self._line_starts.append(off)
                    flat.append((ln, "first" if i == 0 else "cont"))
            self._pages = _paginate_spread(flat, cols=paginate_cols, col_h=col_h, lh=lh,
                                          para_gap=para_gap)
        self._page_tr_cache = {}
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
        if self.paras:
            t.insert(tk.END, "\n\n".join("    " + p for p in self.paras))
        t.configure(state=tk.DISABLED)
        self._pages = [{"cols": [[]]}]
        self._line_starts = [0]

    def _show_page(self) -> None:
        self._bind_speech_keys()
        if self.mode == "scroll":
            self._update_progress()
            self._paint_speech_marks()
            return
        if not self._pages:
            return
        self._page_i = max(0, min(self._page_i, len(self._pages) - 1))
        if self.spread is None:
            self._build_surface(self._page_host())
        self._paint_book(self._pages[self._page_i])
        self._update_progress()
        self._paint_speech_marks()

    def _paint_book(self, page: dict) -> None:
        c = self.spread
        if c is None or not hasattr(self, "_geom"):
            return
        if self._paint_busy:
            return
        self._paint_busy = True
        try:
            self._paint_book_impl(page)
        except Exception:
            # не оставлять чёрный холст после delete("all")
            try:
                if self.spread is not None:
                    self.spread.create_text(
                        40, 40, text=_t("Ошибка отрисовки страницы"),
                        anchor="nw", fill="#C4A35A", font=theme.font(11, True))
            except tk.TclError:
                pass
        finally:
            self._paint_busy = False

    def _paint_book_impl(self, page: dict) -> None:
        c = self.spread
        c.update_idletasks()
        W, H = max(c.winfo_width(), 80), max(c.winfo_height(), 80)
        c.delete("all")
        self._paper_refs.clear()
        self._line_boxes.clear()
        line_base0 = int(page.get("start_line", 0))
        th = self._theme()
        font = _reading_font(self._font_pt())
        font_obj = self._font_obj()
        g = self._geom
        draw_cols = int(g.get("draw_cols") or g["cols"])
        book_w, book_h = g["book_w"], g["book_h"]
        page_w, spine = g["page_w"], g["spine"]
        pad_x, pad_y = g["pad_x"], g["pad_y"]
        lh, indent, para_gap = g["lh"], g["indent"], g["para_gap"]
        text_w = g["text_w"]

        cache = getattr(self, "_measure_cache", {})
        # fullscreen: холст может быть уже другого размера, чем при _relayout
        if book_w > W - 2 or book_h > H - 2:
            # холст ещё не готов (часто при входе в fullscreen) — не рисовать «в никуда»
            book_w = max(160, min(book_w, W - 2))
            book_h = max(120, min(book_h, H - 2))
            page_w = max(80, (book_w - spine) // max(1, draw_cols))
            text_w = min(text_w, max(40, page_w - pad_x * 2))
            if W < 120 or H < 120:
                c.create_text(W // 2, H // 2, text=_t("Загрузка…"),
                              fill=th["dim"], font=theme.font(12, True))
                if not getattr(self, "_size_relayout_job", None):
                    char = self._page_start_char()
                    self._size_relayout_job = self.after(
                        150, lambda: self._deferred_size_relayout(char))
                return

        bx = max(0, (W - book_w) // 2)
        by = max(0, (H - book_h) // 2)
        c.create_rectangle(bx + px(5), by + px(7), bx + book_w + px(3), by + book_h + px(5),
                           fill="#1A140E", outline="")

        def paint_col2(x0, y0, pw, ph, lines: list[tuple[str, str]], *,
                       cont_from_prev: bool = False, label: str = "",
                       use_font=None, use_font_obj=None, use_lh=None, use_gap=None,
                       use_indent=None, use_text_w=None, use_cache=None,
                       justify: bool = True, line_base: int = -1):
            """cont_from_prev: первая строка — продолжение абзаца с левой страницы.
            justify=False — без растягивания пробелов (режим 2 ЯЗЫКА: важен смысл, не «залить» лист).
            """
            fnt = use_font if use_font is not None else font
            fobj = use_font_obj if use_font_obj is not None else font_obj
            line_h = use_lh if use_lh is not None else lh
            gap = use_gap if use_gap is not None else para_gap
            ind = use_indent if use_indent is not None else indent
            # не шире бумаги: в fullscreen geom иногда обгоняет реальный pw
            tw = min(use_text_w if use_text_w is not None else text_w,
                     max(40, pw - pad_x * 2))
            mcache = use_cache if use_cache is not None else cache
            spw = _measure_cached(fobj, " ", mcache)

            photo = paper_photo(c, pw, ph, th["variant"])
            if photo is not None:
                self._paper_refs.append(photo)
                c.create_image(x0, y0, image=photo, anchor="nw")
            else:
                c.create_rectangle(x0, y0, x0 + pw, y0 + ph, fill=th["fallback"], outline="")
            c.create_rectangle(x0, y0, x0 + pw - 1, y0 + ph - 1,
                               outline=blend(th["fg"], th["fallback"], 0.85), width=1)
            if label:
                c.create_text(x0 + pad_x, y0 + px(6), text=label, anchor="nw",
                              fill=th["dim"], font=theme.font(8, True))
            tx0 = x0 + max(pad_x, (pw - tw) // 2)
            y = y0 + pad_y + (px(14) if label else 0)
            for i, (text, kind) in enumerate(lines):
                if kind == "first" and i > 0:
                    y += gap
                x = tx0 + (ind if kind == "first" else 0)
                width = tw - (ind if kind == "first" else 0)
                if not justify:
                    is_last = True
                elif i + 1 < len(lines):
                    is_last = lines[i + 1][1] == "first"
                else:
                    is_last = not cont_from_prev
                if line_base >= 0:
                    # геометрия строки — по ней рисуется подсветка читаемой фразы
                    self._line_boxes.append((line_base + i, x, y, x + width, y + line_h))
                self._draw_justified(c, x, y, text, fnt, fobj, width, th["fg"],
                                     last=is_last, space_w=spw, cache=mcache)
                y += line_h

        col_lists = page["cols"]
        space_w = int(g.get("space_w") or _measure_cached(font_obj, " ", cache))

        def draw_spine(mid: int) -> None:
            c.create_rectangle(mid, by, mid + spine, by + book_h, fill="#1E1810", outline="")
            c.create_line(mid + spine // 2, by + px(4), mid + spine // 2, by + book_h - px(4),
                          fill="#3A3020", width=max(2, spine // 3))
            for i in range(6):
                col = blend("#000000", th["fallback"], 0.93 + 0.01 * i)
                c.create_line(mid - i, by, mid - i, by + book_h, fill=col)
                c.create_line(mid + spine + i, by, mid + spine + i, by + book_h, fill=col)

        if self.mode == "bilingual":
            left = col_lists[0] if col_lists else []
            # пересобираем перевод под фактическую ширину колонки (fullscreen/DPI)
            col_text_w = max(40, page_w - pad_x * 2)
            right, right_pt, right_indent = self._bilingual_right_lines(
                left, text_w=col_text_w, col_h=max(40, book_h - pad_y * 2))
            sl, tl = self._tr_dir
            # без выключки: одинаковое число предложений важнее «заливки» листа
            paint_col2(bx, by, page_w, book_h, left, line_base=line_base0,
                       label=_t("ОРИГИНАЛ · {0}").format(sl.upper()), justify=False)
            rx = bx + page_w + spine
            r_spec = _reading_font(right_pt)
            r_font_obj = tkfont.Font(font=r_spec)
            r_lh = max(1, int(round(r_font_obj.metrics("linespace") * self._line_space())))
            r_gap = max(1, int(r_lh * (0.35 if right_pt >= self._font_pt() - 2 else 0.2)))
            paint_col2(rx, by, page_w, book_h, right,
                       label=_t("ПЕРЕВОД · {0}").format(tl.upper()),
                       use_font=r_spec, use_font_obj=r_font_obj, use_lh=r_lh, use_gap=r_gap,
                       use_indent=right_indent, use_text_w=col_text_w, use_cache={},
                       justify=False)
            if not self._fixed_bilingual():
                self._paint_tr_countdown(c, rx, by, page_w, book_h, th)
                self._ensure_tr_poll()
                self._ensure_tr_eta_tick()
            draw_spine(bx + page_w)
        elif draw_cols == 2:
            left = col_lists[0] if col_lists else []
            right = col_lists[1] if len(col_lists) > 1 else []
            left_continues = bool(right) and right[0][1] == "cont"
            paint_col2(bx, by, page_w, book_h, left, cont_from_prev=left_continues,
                       line_base=line_base0)
            rx = bx + page_w + spine
            paint_col2(rx, by, page_w, book_h, right, cont_from_prev=False,
                       line_base=line_base0 + len(left))
            draw_spine(bx + page_w)
        else:
            # одна страница по центру
            pw = min(book_w, text_w + pad_x * 2 + px(8))
            px0 = bx + (book_w - pw) // 2
            paint_col2(px0, by, pw, book_h, col_lists[0] if col_lists else [],
                       line_base=line_base0)

    # ------------------------------------------------------------------ bilingual
    def _refresh_tr_dir(self) -> None:
        from stamina.translator import direction
        lang = ""
        if self.tid:
            m = self.ctx.lib.meta(self.tid)
            lang = (m or {}).get("lang") or ""
        if not lang and self.text:
            from stamina.langdetect import detect
            lang = detect(self.text[:4000])
        target = None
        try:
            target = self.ctx.app.store.settings.get("uplink_target")
        except Exception:
            pass
        self._tr_dir = direction(lang or "en", target)

    @staticmethod
    def _lines_to_plain(lines: list[tuple[str, str]]) -> str:
        parts: list[str] = []
        for text, kind in lines:
            if not text:
                continue
            if kind == "first" and parts:
                parts.append("\n\n")
            elif parts:
                parts.append(" ")
            parts.append(text)
        return "".join(parts)

    @staticmethod
    def _tr_chunks(src: str) -> list[str]:
        """Одно предложение = один ключ кэша (дырки в переводе видны как «…», а не «съедаются»)."""
        src = src.strip()
        if not src:
            return []
        bits = [b.strip() for b in _SENT_SPLIT.split(src) if b.strip()] or [src]
        chunks: list[str] = []
        for b in bits:
            if len(b) <= _TR_CHUNK:
                chunks.append(b)
            else:
                for i in range(0, len(b), _TR_CHUNK):
                    chunks.append(b[i:i + _TR_CHUNK])
        return chunks

    @staticmethod
    def _tr_fuzzy_near(chunk: str, src: str) -> bool:
        """Край страницы / старый ключ: короткий — префикс длинного, длины близки.

        Иначе короткое предложение из кэша подставлялось вместо целого абзаца
        (справа «пропадает» половина текста).
        """
        if not chunk or not src or chunk == src:
            return bool(chunk and src)
        short, long = (chunk, src) if len(chunk) <= len(src) else (src, chunk)
        if len(short) < 24 or not long.startswith(short):
            return False
        delta = len(long) - len(short)
        # край страницы: не хватает хвоста; абзац vs одно предложение — delta огромный
        return delta <= max(48, int(0.25 * len(long)))

    def _tr_fuzzy_bucket(self, tr, sl: str, tl: str, head: str) -> list:
        """Кандидаты fuzzy: ключи кэша с тем же 24-символьным префиксом (индекс вместо полного перебора)."""
        try:
            n = len(tr.cache)
        except Exception:
            return []
        idx = getattr(self, "_tr_fuzzy_idx", None)
        if idx is None or idx[0] is not tr or idx[1] != (sl, tl) or idx[2] != n:
            prefix = f"{sl}|{tl}|"
            buckets: dict[str, list] = {}
            try:
                items = list(tr.cache.items())
            except Exception:
                return []
            for k, v in items:
                if not v or not isinstance(k, str) or not k.startswith(prefix):
                    continue
                src = k[len(prefix):]
                if len(src) >= 24:
                    buckets.setdefault(src[:24], []).append((src, v))
            idx = (tr, (sl, tl), n, buckets)
            self._tr_fuzzy_idx = idx
        return idx[3].get(head, [])

    def _lookup_tr(self, tr, chunk: str, sl: str, tl: str, *, fuzzy: bool = True) -> str | None:
        """Найти перевод куска: кэш UPLINK → локальный mem → нечёткий (край страницы)."""
        chunk = (chunk or "").strip()
        if not chunk:
            return None
        hit = tr.cached(chunk, sl, tl) if tr is not None else None
        if hit:
            self._tr_sent_mem[(sl, tl, chunk)] = hit
            return hit
        mem = self._tr_sent_mem.get((sl, tl, chunk))
        if mem:
            return mem
        if not fuzzy or tr is None or len(chunk) < 24:
            return None
        best_v, best_n = None, 0
        for src, v in self._tr_fuzzy_bucket(tr, sl, tl, chunk[:24]):
            if src == chunk:
                self._tr_sent_mem[(sl, tl, chunk)] = v
                return v
            if self._tr_fuzzy_near(chunk, src) and len(src) > best_n:
                best_v, best_n = v, len(src)
        if best_v:
            # в mem — только почти точная длина; иначе длинный ключ «прилипает» к короткому TR
            if abs(best_n - len(chunk)) <= max(24, int(0.1 * max(len(chunk), 1))):
                self._tr_sent_mem[(sl, tl, chunk)] = best_v
            return best_v
        return None

    def _ingest_tr_results(self, results: list) -> None:
        """Сложить ответы UPLINK в sentence-mem (нарезка страницы больше не важна)."""
        if not results:
            return
        sl, tl = self._tr_dir
        prefix = f"{sl}|{tl}|"
        for k, result in results:
            if not result or not isinstance(k, str) or not k.startswith(prefix):
                continue
            src = k[len(prefix):].strip()
            if src:
                self._tr_sent_mem[(sl, tl, src)] = result
        if len(self._tr_sent_mem) > 400:
            for old in list(self._tr_sent_mem.keys())[:80]:
                self._tr_sent_mem.pop(old, None)

    def _assemble_para_tr(self, tr, text: str, sl: str, tl: str) -> tuple[str, bool, int]:
        """Собрать перевод абзаца из кэша (без новых HTTP). Частичный — с «…» на пропуски."""
        text = (text or "").strip()
        if not text:
            return "", False, 0
        # целиком абзац — только точный кэш (fuzzy/mem здесь съедали хвост абзаца)
        whole = tr.cached(text, sl, tl) if tr is not None else None
        if whole:
            self._tr_sent_mem[(sl, tl, text)] = whole
            return whole, False, 0
        chunks = self._tr_chunks(text)
        if not chunks:
            return "", False, 0
        out, missing = [], 0
        for chunk in chunks:
            hit = self._lookup_tr(tr, chunk, sl, tl, fuzzy=True)
            if hit:
                out.append(hit)
            else:
                missing += 1
                out.append("…")
        if missing == len(chunks):
            return "", True, missing
        return " ".join(out).strip(), missing > 0, missing

    def _page_src_chunks(self, page_i: int) -> list[str]:
        """Все куски оригинала страницы для UPLINK."""
        if not self._pages or page_i < 0 or page_i >= len(self._pages):
            return []
        cols = self._pages[page_i].get("cols") or []
        left = cols[0] if cols else []
        plain = self._lines_to_plain(left)
        if not plain.strip():
            return []
        paras = [p.strip() for p in plain.split("\n\n") if p.strip()] or [plain.strip()]
        chunks: list[str] = []
        for para in paras:
            chunks.extend(self._tr_chunks(para))
        return chunks

    def _span_src_chunks(self, start_char: int, end_char: int) -> list[str]:
        """Предложения из диапазона символов книги (не зависят от текущей вёрстки)."""
        if not self.text:
            return []
        a = max(0, min(int(start_char), len(self.text)))
        b = max(a, min(int(end_char), len(self.text)))
        snippet = self.text[a:b].strip()
        if not snippet:
            return []
        chunks: list[str] = []
        for para in ([p.strip() for p in snippet.split("\n\n") if p.strip()] or [snippet]):
            chunks.extend(self._tr_chunks(para))
        return chunks

    def _queue_book_window(self, tr, sl: str, tl: str) -> None:
        """Текущая страница + соседние + запас по символам (для перехода окно↔FS)."""
        if not self._pages:
            return
        cur = self._page_i
        start = max(0, cur - _TR_PREFETCH_BEHIND)
        end = min(len(self._pages), cur + 1 + _TR_PREFETCH_AHEAD)
        keep: set[str] = set()
        already = tr.inflight("book")
        slots = max(0, _TR_BOOK_INFLIGHT - already)
        guard = time.monotonic() < self._tr_fs_guard_until

        def enqueue_chunks(chunks: list[str], priority: int, *, unlimited: bool = False) -> None:
            nonlocal slots
            for chunk in chunks:
                k = tr.key(chunk, sl, tl)
                keep.add(k)
                if self._lookup_tr(tr, chunk, sl, tl):
                    continue
                if not unlimited and slots <= 0:
                    continue
                tr.request(chunk, sl, tl, priority=priority, group="book")
                if not unlimited:
                    slots -= 1

        def enqueue_page(page_i: int, priority: int, *, unlimited: bool = False) -> None:
            enqueue_chunks(self._page_src_chunks(page_i), priority, unlimited=unlimited)

        # текущая — все куски, приоритет 0 (fullscreen: длинная колонка)
        enqueue_page(cur, 0, unlimited=True)
        # запас по тексту вокруг позиции — покрывает FS, где «страница» длиннее
        try:
            anchor = self._page_start_char()
        except Exception:
            anchor = 0
        span_chunks = self._span_src_chunks(anchor - _TR_SPAN_BEHIND, anchor + _TR_SPAN_AHEAD)
        enqueue_chunks(span_chunks, 1, unlimited=True)
        already = tr.inflight("book")
        slots = max(0, _TR_BOOK_INFLIGHT - already)
        for dist, pi in enumerate(range(cur - 1, start - 1, -1), start=1):
            enqueue_page(pi, 2)
        for dist, pi in enumerate(range(cur + 1, end), start=1):
            enqueue_page(pi, 3 + dist)
        # во время перехода FS не отменять — иначе рвёт уже идущие запросы
        # book_warm не трогаем — фоновый прогрев книги
        if not guard:
            tr.cancel_group("book", keep=keep)

    def _warm_book_translation(self) -> None:
        """Фоновый прогрев: предложения книги в кэш UPLINK (низкий приоритет)."""
        if self.mode != "bilingual" or not self.text.strip() or self._fixed_bilingual():
            return
        try:
            tr = self.ctx.app.get_translator()
        except Exception:
            return
        if tr is None:
            return
        sl, tl = self._tr_dir
        n = 0
        for para in self.paras or [self.text]:
            for chunk in self._tr_chunks(para):
                if self._lookup_tr(tr, chunk, sl, tl, fuzzy=False):
                    continue
                tr.request(chunk, sl, tl, priority=8, group="book_warm")
                n += 1
                if n >= _TR_WARM_MAX:
                    return

    def _wrap_fit_column(self, paras: list[str], *, text_w: int, col_h: int
                         ) -> tuple[list[tuple[str, str]], int, int]:
        """Уместить весь перевод: кегль↓ при необходимости. Возврат (lines, pt, indent_px)."""
        budget = max(40, col_h - px(20))
        best: list[tuple[str, str]] = []
        best_pt = self._font_pt()
        best_ind = 0
        for shrink in range(0, 12):
            pt = max(9, self._font_pt() - shrink)
            font = tkfont.Font(font=_reading_font(pt))
            cache: dict[str, int] = {}
            ind = _measure_cached(font, "    ", cache)
            lh = max(1, int(round(font.metrics("linespace") * self._line_space())))
            para_gap = max(1, int(lh * (0.35 if shrink < 3 else 0.2)))
            flat: list[tuple[str, str]] = []
            for para in paras:
                if not para or para == "…":
                    if para == "…":
                        flat.append(("…", "first"))
                    continue
                wrapped = _wrap_para(para, font, text_w, first_indent=ind, cache=cache)
                for i, ln in enumerate(wrapped):
                    flat.append((ln, "first" if i == 0 else "cont"))
            used = 0
            for i, item in enumerate(flat):
                used += lh + (para_gap if item[1] == "first" and i > 0 else 0)
            best, best_pt, best_ind = flat, pt, ind
            if used <= budget:
                return flat, pt, ind
        return best, best_pt, best_ind

    def _fixed_bilingual_paras(self, left_plain: str) -> list[str]:
        """Сопоставить абзацы оригинала на странице с translation.txt (по индексу)."""
        from stamina.speedread.text_norm import paragraphs as _paras
        tr_text = self.ctx.lib.translation(self.tid or "") if self.tid else ""
        if not tr_text.strip():
            return [_t("(нет файла перевода)")]
        orig_paras = [p.strip() for p in (self.paras or _paras(self.text)) if p.strip()]
        tr_paras = [p.strip() for p in _paras(tr_text) if p.strip()]
        if not orig_paras or not tr_paras:
            return tr_paras[:3] or [_t("(пустой перевод)")]
        left_paras = [p.strip() for p in left_plain.split("\n\n") if p.strip()] or [left_plain.strip()]
        # индекс первого абзаца страницы в книге
        start = 0
        head = " ".join((left_paras[0] or "").split())[:48]
        if head:
            for i, p in enumerate(orig_paras):
                if " ".join(p.split()).startswith(head[:32]) or head[:32] in " ".join(p.split()):
                    start = i
                    break
        n = max(1, len(left_paras))
        chunk = tr_paras[start:start + n]
        if not chunk and start < len(tr_paras):
            chunk = tr_paras[start:start + 1]
        return chunk or [_t("(нет абзаца перевода)")]

    def _bilingual_right_lines(self, left: list[tuple[str, str]], *,
                               text_w: int | None = None,
                               col_h: int | None = None
                               ) -> tuple[list[tuple[str, str]], int, int]:
        """Перевод текста левой колонки. (lines, font_pt, indent_px)."""
        g = self._geom
        tw = int(text_w if text_w is not None else g["text_w"])
        ch = int(col_h if col_h is not None else g["col_h"])
        pi = self._page_i
        plain = self._lines_to_plain(left)
        src_paras = [p.strip() for p in plain.split("\n\n") if p.strip()]
        if not src_paras and plain.strip():
            src_paras = [plain.strip()]

        if not plain.strip():
            empty: list[tuple[str, str]] = []
            self._bilingual_right_pt = self._font_pt()
            return empty, self._font_pt(), 0

        # готовая двуязычная книга — без UPLINK
        if self._fixed_bilingual():
            self._tr_pending_pages.discard(pi)
            self._tr_wait_until = 0.0
            self._tr_wait_missing = 0
            out_paras = self._fixed_bilingual_paras(plain)
            flat, pt, ind = self._wrap_fit_column(out_paras, text_w=tw, col_h=ch)
            self._bilingual_right_pt = pt
            return flat, pt, ind

        tr = None
        try:
            tr = self.ctx.app.get_translator()
        except Exception:
            pass
        sl, tl = self._tr_dir

        waiting = False
        missing_total = 0
        out_paras: list[str] = []
        mem_key = (sl, tl, plain)
        if tr is None:
            out_paras = [_t("Переводчик недоступен.")]
        else:
            self._queue_book_window(tr, sl, tl)
            for para in src_paras:
                piece, wait, miss = self._assemble_para_tr(tr, para, sl, tl)
                waiting = waiting or wait
                missing_total += miss
                if piece:
                    out_paras.append(piece)
            # полный перевод этой страницы уже был — отдать сразу (← и смена экрана)
            if waiting and mem_key in self._plain_tr_mem and not out_paras:
                out_paras = list(self._plain_tr_mem[mem_key])
            if not waiting and out_paras:
                self._plain_tr_mem[mem_key] = list(out_paras)
                # ограничить память ~80 страниц
                if len(self._plain_tr_mem) > 80:
                    for old in list(self._plain_tr_mem.keys())[:20]:
                        self._plain_tr_mem.pop(old, None)
            if waiting:
                self._tr_pending_pages.add(pi)
                self._tr_wait_missing = missing_total
                eta = min(25.0, max(4.0, missing_total * 2.0 + 2.0))
                now = time.monotonic()
                if self._tr_wait_until < now or self._tr_wait_until > now + eta + 3:
                    self._tr_wait_until = now + eta
                if not out_paras:
                    # частичный mem по тому же тексту
                    if mem_key in self._plain_tr_mem:
                        out_paras = list(self._plain_tr_mem[mem_key])
                    else:
                        out_paras = [_t("Загрузка перевода…")]
            else:
                self._tr_pending_pages.discard(pi)
                self._tr_wait_until = 0.0
                self._tr_wait_missing = 0

        flat, pt, ind = self._wrap_fit_column(out_paras, text_w=tw, col_h=ch)
        self._bilingual_right_pt = pt
        return flat, pt, ind

    def _paint_tr_countdown(self, c: tk.Canvas, x0: int, y0: int, pw: int, ph: int, th: dict) -> None:
        """Плашка «перевод через N с» на правой странице, пока куски грузятся."""
        if self._page_i not in self._tr_pending_pages or self._tr_wait_until <= 0:
            return
        left = int(self._tr_wait_until - time.monotonic() + 0.999)
        online = True
        try:
            online = self.ctx.app.get_translator().online is not False
        except Exception:
            pass
        if left <= 0:
            self._tr_wait_until = time.monotonic() + 4.0
            left = 4
            if not online:
                msg = _t("Сеть занята — повтор через {0} с").format(left)
            else:
                msg = _t("Перевод почти готов… {0} с").format(left)
        else:
            msg = _t("Перевод страницы через {0} с").format(left)
        if self._tr_wait_missing:
            msg = f"{msg} · {self._tr_wait_missing}"
        pad = px(10)
        c.create_rectangle(x0 + pad, y0 + ph - px(36), x0 + pw - pad, y0 + ph - pad,
                           fill=blend(th["fallback"], "#000000", 0.12), outline=th["dim"],
                           width=1, tags="tr_wait")
        c.create_text(x0 + pw // 2, y0 + ph - px(23), text=msg, anchor="center",
                      fill=th["dim"], font=theme.font(9, True), tags="tr_wait")

    def _stop_tr_timers(self) -> None:
        for attr in ("_tr_poll_job", "_tr_eta_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

    def _deferred_size_relayout(self, char: int) -> None:
        self._size_relayout_job = None
        self._layout_key = None
        self._page_tr_cache.clear()
        self._relayout(keep_char=char)

    def _ensure_tr_eta_tick(self) -> None:
        """Только планирует тик — никогда не вызывать синхронно из paint."""
        if self.mode != "bilingual":
            return
        if self._tr_eta_job is not None:
            return
        if self._page_i not in self._tr_pending_pages:
            return
        self._tr_eta_job = self.after(450, self._tr_eta_tick)

    def _tr_eta_tick(self) -> None:
        self._tr_eta_job = None
        if self.mode != "bilingual":
            return
        if self._page_i not in self._tr_pending_pages:
            return
        c = self.spread
        if c is None:
            self._tr_eta_job = self.after(450, self._tr_eta_tick)
            return
        try:
            # если холст пуст (сбой/fullscreen) — не рисовать одну плашку на чёрном
            if not c.find_all() and self._pages:
                self._paint_book(self._pages[self._page_i])
            else:
                c.delete("tr_wait")
                g = self._geom
                W = max(c.winfo_width(), 80)
                H = max(c.winfo_height(), 80)
                book_w, book_h = g["book_w"], g["book_h"]
                page_w, spine = g["page_w"], g["spine"]
                book_w = min(book_w, max(160, W - 2))
                book_h = min(book_h, max(120, H - 2))
                page_w = max(80, (book_w - spine) // 2)
                bx = max(0, (W - book_w) // 2)
                by = max(0, (H - book_h) // 2)
                self._paint_tr_countdown(c, bx + page_w + spine, by, page_w, book_h, self._theme())
        except tk.TclError:
            pass
        if self._page_i in self._tr_pending_pages:
            self._tr_eta_job = self.after(450, self._tr_eta_tick)

    def _ensure_tr_poll(self) -> None:
        """Только планирует poll — синхронный вызов из paint давал рекурсию и чёрный экран."""
        if self.mode != "bilingual":
            return
        if self._tr_poll_job is not None:
            return
        self._tr_poll_job = self.after(300, self._tr_poll_tick)

    def _tr_poll_tick(self) -> None:
        """Слить UPLINK, дозапросить окно (текущая+3), перерисовать при прогрессе."""
        self._tr_poll_job = None
        if self.mode != "bilingual":
            return
        if self._tr_poll_busy or self._paint_busy:
            self._tr_poll_job = self.after(350, self._tr_poll_tick)
            return
        self._tr_poll_busy = True
        try:
            tr = None
            try:
                tr = self.ctx.app.get_translator()
            except Exception:
                pass
            results = tr.poll() if tr is not None else []
            self._ingest_tr_results(results)
            if tr is not None and self._pages:
                sl, tl = self._tr_dir
                self._queue_book_window(tr, sl, tl)
            need_paint = bool(results)
            if self._pages and (self._page_i in self._tr_pending_pages or results):
                prev_m = self._tr_last_drawn_missing
                page = self._pages[self._page_i]
                left = page["cols"][0] if page.get("cols") else []
                g = getattr(self, "_geom", None)
                if g:
                    self._bilingual_right_lines(
                        left,
                        text_w=max(40, int(g.get("page_w", 200)) - int(g["pad_x"]) * 2),
                        col_h=max(40, int(g["book_h"]) - int(g["pad_y"]) * 2),
                    )
                missing = self._tr_wait_missing
                done = self._page_i not in self._tr_pending_pages
                if need_paint or done or prev_m < 0 or missing != prev_m:
                    self._tr_last_drawn_missing = 0 if done else missing
                    self._paint_book(self._pages[self._page_i])
        finally:
            self._tr_poll_busy = False
        if self.mode == "bilingual":
            # fullscreen / идёт загрузка — чаще; сразу после ЭКРАН ещё чаще
            if time.monotonic() < self._tr_fs_guard_until:
                delay = 200
            elif self._fullscreen or self._tr_pending_pages:
                delay = 280
            else:
                delay = 450
            self._tr_poll_job = self.after(delay, self._tr_poll_tick)

    def _draw_justified(self, c: tk.Canvas, x: int, y: int, text: str, font, font_obj: tkfont.Font,
                        width: int, fill: str, *, last: bool,
                        space_w: int = 0, cache: dict | None = None) -> None:
        """Выключка одним create_text (лишние пробелы) — без сотен measure на страницу."""
        words = text.split()
        if not words:
            return
        # один и тот же Font-объект для measure и draw — иначе в fullscreen плывут поля
        draw_font = font_obj
        if last or len(words) == 1:
            c.create_text(x, y, text=text, anchor="nw", fill=fill, font=draw_font)
            return
        cache = cache if cache is not None else getattr(self, "_measure_cache", {})
        if space_w <= 0:
            space_w = _measure_cached(font_obj, " ", cache)
        widths = [_measure_cached(font_obj, w, cache) for w in words]
        natural = sum(widths) + space_w * (len(words) - 1)
        extra = width - natural
        if extra < space_w or space_w <= 0:
            c.create_text(x, y, text=text, anchor="nw", fill=fill, font=draw_font)
            return
        gaps = len(words) - 1
        add = extra // space_w
        base, rem = divmod(add, gaps)
        parts: list[str] = []
        for i, w in enumerate(words):
            parts.append(w)
            if i < gaps:
                parts.append(" " * (1 + base + (1 if i < rem else 0)))
        c.create_text(x, y, text="".join(parts), anchor="nw", fill=fill, font=draw_font)

    def page_next(self) -> None:
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_scroll(1, "pages")
            self.save_pos()
            self._update_progress()
            return
        if self._page_i < len(self._pages) - 1:
            self._page_i += 1
            self._tr_last_drawn_missing = -1
            self._show_page()
            self._bump_book_window()
            self.save_pos()

    def page_prev(self) -> None:
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_scroll(-1, "pages")
            self.save_pos()
            self._update_progress()
            return
        if self._page_i > 0:
            self._page_i -= 1
            self._tr_last_drawn_missing = -1
            self._show_page()
            self._bump_book_window()
            self.save_pos()

    def _bump_book_window(self) -> None:
        """После листания сразу сдвинуть окно предзагрузки перевода."""
        if self.mode != "bilingual":
            return
        try:
            tr = self.ctx.app.get_translator()
        except Exception:
            return
        if tr is None:
            return
        sl, tl = self._tr_dir
        self._queue_book_window(tr, sl, tl)
        self._ensure_tr_poll()

    def _on_scale(self, val) -> None:
        if self._applying or not self.text:
            return
        # Tk Scale зовёт command отложенно (в idle), когда _applying уже снят:
        # эхо собственного scale.set() - не перелистывание, иначе двойная перерисовка
        try:
            if int(round(float(val))) == getattr(self, "_scale_echo", None):
                self._scale_echo = None
                return
        except (TypeError, ValueError):
            pass
        frac = float(val) / 100.0
        if self.mode == "scroll" and self.scroll_view is not None:
            self.scroll_view.yview_moveto(frac)
            self.save_pos()
            self._update_progress()
            return
        if not self._pages:
            return
        self._page_i = int(round(frac * max(0, len(self._pages) - 1)))
        self._tr_last_drawn_missing = -1
        self._show_page()
        self._bump_book_window()
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
            if int(round(float(self.scale.get()))) != pct:
                self._scale_echo = pct
            self.scale.set(pct)
        except (tk.TclError, TypeError, ValueError):
            pass
        self._applying = False
        self.lbl_pct.configure(text=f"{pct}%")
        if self.mode == "scroll":
            self.lbl_page.configure(text=_t("прокрутка"))
        elif self.mode == "spread":
            left = self._page_i * 2 + 1
            total = len(self._pages) * 2
            self.lbl_page.configure(text=_t("{0}–{1} / {2}").format(left, left + 1, total))
        elif self.mode == "bilingual":
            sl, tl = self._tr_dir
            self.lbl_page.configure(
                text=_t("{0} / {1} · {2}→{3}").format(self._page_i + 1, len(self._pages),
                                                       sl.upper(), tl.upper()))
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
        # зафиксировать уже известные переводы текущей страницы до смены вёрстки
        if self.mode == "bilingual" and self._pages:
            try:
                tr = self.ctx.app.get_translator()
                sl, tl = self._tr_dir
                if tr is not None:
                    self._ingest_tr_results(tr.poll())
                for chunk in self._page_src_chunks(self._page_i):
                    self._lookup_tr(tr, chunk, sl, tl)
            except Exception:
                pass
        th = self._theme()
        # остановить poll/eta — иначе рисуют в уничтожаемый canvas и гасят экран
        self._stop_tr_timers()
        self._page_tr_cache.clear()
        self._tr_last_drawn_missing = -1
        # mem предложений / Translator не трогаем — иначе FS теряет уже загруженный перевод
        self._tr_fs_guard_until = time.monotonic() + 4.5
        self._fullscreen = True
        self.ctx.set_focus_mode(True)
        self._layout_key = None
        self._fs = tk.Frame(self.ctx.app, bg=th["desk"])
        self._fs.place(x=0, y=0, relwidth=1, relheight=1)
        self._fs.lift()

        self.top_bar_fs = tk.Frame(self._fs, bg=th["bar"], height=px(44))
        self.top_bar_fs.pack(fill=tk.X)
        self.top_bar_fs.pack_propagate(False)
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
        self._build_bot_bar(self.bot_bar_fs)
        self.bot_bar = self.bot_bar_fs
        self._chrome_visible = True

        self._fs_area.bind("<Configure>", self._on_area_configure)
        self._fs_area.bind("<Motion>", self._on_motion)
        self._fs.bind("<Key>", self.on_key)
        self._fs.focus_set()
        self._sync_mode_btns()
        char = self._page_start_char()
        try:
            self._fs.update_idletasks()
            self._fs_area.update_idletasks()
        except tk.TclError:
            pass
        # дождаться реального размера, потом одна стабильная вёрстка + перевод
        self.after(280, lambda c=char: self._fullscreen_ready(c, tries=0))
        self._schedule_hide_chrome()

    def _fullscreen_ready(self, char: int, tries: int = 0) -> None:
        if not self._fullscreen:
            return
        try:
            self._fs.update_idletasks()
            self._fs_area.update_idletasks()
            w = self._fs_area.winfo_width()
            h = self._fs_area.winfo_height()
        except (tk.TclError, AttributeError):
            w = h = 0
        # холст ещё крошечный — подождать, иначе перевод соберётся «в никуда»
        if (w < 360 or h < 240) and tries < 8:
            self.after(120, lambda: self._fullscreen_ready(char, tries + 1))
            return
        self._layout_key = None
        self._page_tr_cache.clear()
        self._relayout(keep_char=char)
        if self.mode == "bilingual":
            self._tr_last_drawn_missing = -1
            self._tr_fs_guard_until = max(self._tr_fs_guard_until, time.monotonic() + 1.6)
            self._bump_book_window()
            self._ensure_tr_poll()
            self._ensure_tr_eta_tick()
            if self._pages:
                self._paint_book(self._pages[self._page_i])
                # второй проход — подтянуть то, что успело прийти из сети
                self.after(400, self._fs_tr_refresh)

    def _fs_tr_refresh(self) -> None:
        if not self._fullscreen or self.mode != "bilingual" or not self._pages:
            return
        try:
            tr = self.ctx.app.get_translator()
            if tr is not None:
                self._ingest_tr_results(tr.poll())
                sl, tl = self._tr_dir
                self._queue_book_window(tr, sl, tl)
        except Exception:
            pass
        self._tr_last_drawn_missing = -1
        self._paint_book(self._pages[self._page_i])
        self._ensure_tr_poll()

    def exit_fullscreen(self) -> None:
        if not self._fullscreen:
            return
        self.save_pos()
        char = self._page_start_char()
        # сохранить переводы FS-страницы перед сменой вёрстки
        if self.mode == "bilingual" and self._pages:
            try:
                tr = self.ctx.app.get_translator()
                sl, tl = self._tr_dir
                if tr is not None:
                    self._ingest_tr_results(tr.poll())
                for chunk in self._page_src_chunks(self._page_i):
                    self._lookup_tr(tr, chunk, sl, tl)
            except Exception:
                pass
        self._stop_tr_timers()
        self._page_tr_cache.clear()
        self._tr_last_drawn_missing = -1
        self._tr_fs_guard_until = time.monotonic() + 1.8
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
        self._build_bot_bar(self.bot_bar)
        self.read_shell.bind("<Configure>", self._on_area_configure)
        self.read_shell.bind("<Motion>", self._on_motion)
        self._chrome_visible = True
        self._sync_mode_btns()
        self._apply_theme()
        self.after(40, lambda c=char: self._after_exit_fs(c))
        self.focus_set()

    def _after_exit_fs(self, char: int) -> None:
        self._relayout(keep_char=char)
        if self.mode == "bilingual":
            self._tr_last_drawn_missing = -1
            self._bump_book_window()
            self._ensure_tr_poll()
            self._ensure_tr_eta_tick()
            if self._pages:
                self.after(50, lambda: self._paint_book(self._pages[self._page_i]))

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
        dlg.geometry(monitors.center_geometry(self, px(440), px(400)))
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
