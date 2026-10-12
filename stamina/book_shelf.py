"""Полка книг и каталог Gutenberg — встроенные экраны (не модальные окна)."""
from __future__ import annotations

from stamina.i18n import t as _t

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable

from stamina import bilinguis_catalog as bilinguis
from stamina import book_catalog as catalog
from stamina import library as libmod
from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE, MUTED, PANEL, RED, TEXT, blend, px

try:
    from stamina.speedread.ui import L, ScrollFrame, entry
except Exception:  # noqa: BLE001
    from stamina.english.ui import L, ScrollFrame, entry

COVER_W, COVER_H = 72, 108
LANG_CHOICES = [
    ("", _t("ВСЕ")),
    ("en", "EN"),
    ("de", "DE"),
    ("fr", "FR"),
    ("es", "ES"),
    ("it", "IT"),
    ("ru", "RU"),
]


def _cover_photo(path: Path | None, w: int = COVER_W, h: int = COVER_H) -> tk.PhotoImage | None:
    if path is None or not path.exists():
        return None
    try:
        from PIL import Image, ImageTk
        im = Image.open(path).convert("RGB")
    except Exception:  # noqa: BLE001
        try:
            return tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None
    im.thumbnail((w, h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (8, 18, 33))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return ImageTk.PhotoImage(canvas)


def _placeholder_cover(parent, w: int = COVER_W, h: int = COVER_H) -> tk.Canvas:
    c = tk.Canvas(parent, width=w, height=h, bg=blend(CYAN, BG, 0.85), highlightthickness=1,
                  highlightbackground=LINE, bd=0)
    c.create_text(w // 2, h // 2, text=_t("нет\nобложки"), fill=MUTED, font=theme.font(7, True),
                  justify="center")
    return c


class BookCatalogPanel(tk.Frame):
    """Каталог Gutenberg внутри основного окна (список + кнопки всегда внизу экрана).

    bilingual=True — тот же UI, но только книги с PD-переводом; скачивание → kind=bilingual.
    """

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_added: Callable[[str], None] | None = None,
                 on_back: Callable[[], None] | None = None,
                 bilingual: bool = False,
                 on_manual: Callable[[], None] | None = None) -> None:
        super().__init__(master, bg=BG)
        self.lib = lib
        self.opts = opts or {}
        self.on_added = on_added
        self.on_back = on_back
        self.on_manual = on_manual
        self.bilingual = bool(bilingual)
        self.results: list[dict] = []
        self.sel: int | None = None
        self._busy = False
        self._photos: list[tk.PhotoImage] = []
        self._lang = "en"
        # приоритет EN→RU / EN→UK (bilinguis); DE/FR — Gutenberg
        self._lang_b = "ru" if self.bilingual else ""
        self._page = 1
        self._mode = "browse"  # browse | search | cefr
        self._cefr: str | None = None
        self._next_url = None
        self._started = False
        self._cefr_btns: dict[str, HudButton] = {}
        self._lang_b_btns: dict[str, HudButton] = {}

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=px(12), pady=(px(8), 0))
        if on_back:
            HudButton(head, _t("← НАЗАД"), on_back, height=30, font_size=9, width=100).pack(
                side=tk.LEFT, padx=(0, px(10)))
        head_title = (_t("СВОБОДНЫЕ КНИГИ · 2 ЯЗЫКА") if self.bilingual
                      else _t("СВОБОДНЫЕ КНИГИ · PROJECT GUTENBERG"))
        tk.Label(head, text=head_title, bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(side=tk.LEFT)
        head_sub = (_t("EN→RU/UK — bilinguis.com · DE/FR — Gutenberg · PD")
                    if self.bilingual else _t("общественное достояние · обложки или заглушки"))
        tk.Label(head, text=head_sub, bg=BG, fg=MUTED, font=theme.font(8)).pack(
            side=tk.LEFT, padx=px(12))

        hint = (_t("Для RU и UK — готовые пары bilinguis (Alice, Том Сойер, Баскервили…). "
                   "Для DE/FR — поиск пар в Gutenberg. Скачивание → книга 2ЯЗ на полке.")
                if self.bilingual else
                _t("Поиск по названию/автору или «По категориям» (CEFR A1–C2). "
                   "Каталог — Project Gutenberg (общественное достояние). "
                   "Коммерческие адаптированные readers сюда не входят."))
        L(self, hint, fg=MUTED, size=8, bg=BG, wraplength=px(1100), justify="left").pack(
            anchor="w", padx=px(14), pady=(px(2), 0))

        form = tk.Frame(self, bg=BG)
        form.pack(fill=tk.X, padx=px(12), pady=px(6))
        L(form, _t("НАЗВАНИЕ"), fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=0, sticky="w")
        L(form, _t("АВТОР"), fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=1, sticky="w",
                                                                       padx=(px(8), 0))
        L(form, _t("ЯЗЫК") if not self.bilingual else _t("ОРИГИНАЛ"),
          fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=2, sticky="w", padx=(px(8), 0))
        self.e_title = entry(form, width=28, size=11)
        self.e_title.grid(row=1, column=0, sticky="ew", padx=(0, px(8)))
        self.e_author = entry(form, width=22, size=11)
        self.e_author.grid(row=1, column=1, sticky="ew", padx=(0, px(8)))
        lang_fr = tk.Frame(form, bg=BG)
        lang_fr.grid(row=1, column=2, sticky="w")
        self._lang_btns = {}
        lang_choices = LANG_CHOICES if not self.bilingual else [
            ("en", "EN"), ("de", "DE"), ("fr", "FR"), ("es", "ES"), ("it", "IT"), ("ru", "RU")]
        for code, name in lang_choices:
            b = HudButton(lang_fr, name, lambda c=code: self._set_lang(c), height=28, font_size=8,
                          width=44, active=(code == self._lang))
            b.pack(side=tk.LEFT, padx=px(1))
            self._lang_btns[code] = b
        form.grid_columnconfigure(0, weight=2)
        form.grid_columnconfigure(1, weight=1)
        btns = tk.Frame(form, bg=BG)
        btns.grid(row=1, column=3, padx=(px(8), 0))
        HudButton(btns, _t("🔍 НАЙТИ"), self.search, color=CYAN, height=30, font_size=9, width=100).pack(
            side=tk.LEFT, padx=px(2))
        HudButton(btns, _t("★ СВОБОДНЫЕ"), self.browse_free, color=AMBER, height=30, font_size=9,
                  width=120).pack(side=tk.LEFT, padx=px(2))
        HudButton(btns, _t("▤ ПО КАТЕГОРИЯМ"), self.toggle_cefr, color=GREEN, height=30, font_size=9,
                  width=150).pack(side=tk.LEFT, padx=px(2))
        self.e_title.bind("<Return>", lambda _e: self.search())
        self.e_author.bind("<Return>", lambda _e: self.search())

        if self.bilingual:
            tr_row = tk.Frame(self, bg=BG)
            tr_row.pack(fill=tk.X, padx=px(12), pady=(0, px(4)))
            L(tr_row, _t("ПЕРЕВОД"), fg=MUTED, size=8, bold=True, bg=BG).pack(
                side=tk.LEFT, padx=(0, px(8)))
            for code, name in (("ru", "RU"), ("uk", "UK"), ("de", "DE"), ("fr", "FR"),
                               ("es", "ES"), ("it", "IT")):
                b = HudButton(tr_row, name, lambda c=code: self._set_lang_b(c), height=26,
                              font_size=8, width=44, active=(code == self._lang_b), color=GREEN)
                b.pack(side=tk.LEFT, padx=px(1))
                self._lang_b_btns[code] = b
            L(tr_row, _t("RU/UK — bilinguis · DE/FR — Gutenberg"),
              fg=MUTED, size=8, bg=BG).pack(side=tk.LEFT, padx=px(10))

        self.cefr_bar = tk.Frame(self, bg=BG)
        # скрыта, пока не нажали «ПО КАТЕГОРИЯМ»
        cefr_inner = tk.Frame(self.cefr_bar, bg=BG)
        cefr_inner.pack(fill=tk.X, padx=px(12), pady=(0, px(4)))
        L(cefr_inner, _t("УРОВЕНЬ CEFR"), fg=MUTED, size=8, bold=True, bg=BG).pack(
            side=tk.LEFT, padx=(0, px(8)))
        for lv in catalog.cefr_levels():
            b = HudButton(cefr_inner, lv, lambda c=lv: self.search_cefr(c), height=28, font_size=9,
                          width=44)
            b.pack(side=tk.LEFT, padx=px(2))
            self._cefr_btns[lv] = b
        L(cefr_inner,
          _t("подборка PD под уровень · не коммерческие graded readers"),
          fg=MUTED, size=8, bg=BG).pack(side=tk.LEFT, padx=px(10))

        self.status = L(self, "", fg=MUTED, size=9, bg=BG)
        self.status.pack(anchor="w", padx=px(14))

        # низ: кнопки всегда видны (pack side=BOTTOM до expand-списка)
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, side=tk.BOTTOM, padx=px(12), pady=(px(4), px(10)))
        self.btn_more = HudButton(bot, _t("ЕЩЁ…"), self.load_more, height=38, font_size=9, width=90)
        self.btn_more.pack(side=tk.LEFT)
        dl_lab = _t("⇩ СКАЧАТЬ 2ЯЗ") if self.bilingual else _t("⇩ СКАЧАТЬ В БИБЛИОТЕКУ")
        self.btn_dl = HudButton(bot, dl_lab, self.download, color=GREEN,
                                height=38, font_size=11, width=220 if self.bilingual else 240)
        self.btn_dl.pack(side=tk.LEFT, padx=px(8))
        if self.bilingual and on_manual:
            HudButton(bot, _t("＋ ВРУЧНУЮ"), on_manual, height=38, font_size=9, width=120).pack(
                side=tk.LEFT, padx=px(4))
        if on_back:
            HudButton(bot, _t("← К ПОДГОТОВКЕ") if not self.bilingual else _t("← НАЗАД"),
                      on_back, height=38, font_size=9, width=140).pack(side=tk.RIGHT)

        body = HudPanel(self, _t("КАТАЛОГ"), accent=CYAN)
        body.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(px(4), 0))
        self.list = ScrollFrame(body.body, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True)

    def activate(self) -> None:
        """Показать панель и при первом заходе подгрузить ленту."""
        if not self._started:
            self._started = True
            self.after(60, self.browse_free)

    def _set_lang(self, code: str) -> None:
        self._lang = code
        for c, b in self._lang_btns.items():
            b.set_active(c == code)

    def _set_lang_b(self, code: str) -> None:
        if not self.bilingual:
            return
        self._lang_b = code
        for c, b in self._lang_b_btns.items():
            b.set_active(c == code)
        if self._started and not self._busy:
            self.browse_free()

    def _lang_param(self) -> str | None:
        return self._lang or None

    def _lang_b_param(self) -> str:
        return (self._lang_b or "ru").strip().lower()

    def _use_bilinguis(self) -> bool:
        """EN→RU / EN→UK (и обратные) — полка bilinguis, не Gutenberg."""
        if not self.bilingual:
            return False
        la = (self._lang_param() or "en").lower()
        lb = self._lang_b_param()
        return {la, lb} <= {"en", "ru", "uk"} and la != lb and ("en" in (la, lb))

    def browse_free(self) -> None:
        if self._busy:
            return
        self._mode = "browse"
        self._cefr = None
        self._sync_cefr_btns()
        self._page = 1
        lang = None if self._lang == "" else (self._lang_param() or "en")
        if self.bilingual:
            la = lang or "en"
            lb = self._lang_b_param()
            if self._use_bilinguis():
                self._run_fetch(lambda: bilinguis.list_bilingual_pairs(lang_a=la, lang_b=lb))
            else:
                self._run_fetch(lambda: catalog.list_bilingual_free(lang_a=la, lang_b=lb, page=1))
        else:
            self._run_fetch(lambda: catalog.list_free_books(page=1, languages=lang))

    def toggle_cefr(self) -> None:
        if self.cefr_bar.winfo_ismapped():
            self.cefr_bar.pack_forget()
            return
        self.cefr_bar.pack(fill=tk.X, before=self.status)
        if not self._cefr:
            self.status.configure(
                text=_t("Выберите уровень A1…C2 — книги общественного достояния под этот уровень."),
                fg=CYAN)

    def search_cefr(self, level: str) -> None:
        if self._busy:
            return
        if not self.cefr_bar.winfo_ismapped():
            self.cefr_bar.pack(fill=tk.X, before=self.status)
        self._mode = "cefr"
        self._cefr = level.upper()
        self._sync_cefr_btns()
        self._page = 1
        lang = None if self._lang == "" else (self._lang_param() or "en")
        if self.bilingual:
            la = lang or "en"
            lb = self._lang_b_param()
            self._run_fetch(lambda: catalog.list_bilingual_by_cefr(
                self._cefr, lang_a=la, lang_b=lb, page=1))
        else:
            self._run_fetch(lambda: catalog.list_by_cefr(self._cefr, page=1, languages=lang))

    def _sync_cefr_btns(self) -> None:
        for lv, b in self._cefr_btns.items():
            b.set_active(lv == self._cefr)

    def search(self) -> None:
        if self._busy:
            return
        title = self.e_title.get().strip()
        author = self.e_author.get().strip()
        if not title and not author:
            self.status.configure(text=_t("Введите название или автора — или откройте «Свободные» / «По категориям»."),
                                  fg=AMBER)
            return
        self._mode = "search"
        self._cefr = None
        self._sync_cefr_btns()
        self._page = 1
        if self.bilingual:
            la = self._lang_param() or "en"
            lb = self._lang_b_param()
            if self._use_bilinguis():
                q_title, q_author = title.lower(), author.lower()

                def _bili_search():
                    data = bilinguis.list_bilingual_pairs(lang_a=la, lang_b=lb)
                    rows = []
                    for b in data.get("results") or []:
                        if q_title and q_title not in (b.get("title") or "").lower():
                            continue
                        if q_author and q_author not in (b.get("author") or "").lower():
                            continue
                        rows.append(b)
                    data = dict(data)
                    data["results"] = rows
                    data["count"] = len(rows)
                    return data

                self._run_fetch(_bili_search)
            else:
                self._run_fetch(lambda: catalog.search_bilingual(
                    title=title, author=author, lang_a=la, lang_b=lb, page=1))
        else:
            self._run_fetch(lambda: catalog.search_books(
                title=title, author=author, languages=self._lang_param(), page=1))

    def load_more(self) -> None:
        if self._busy or not self._next_url:
            return
        nxt = self._next_url
        # продолжение bilingual-ленты: bifree:la:lb:popular_page / biseed:...
        if self.bilingual and isinstance(nxt, str) and nxt.startswith("bifree:"):
            parts = nxt.split(":")
            if len(parts) >= 4:
                la, lb, pp = parts[1], parts[2], int(parts[3])
                self._run_fetch(
                    lambda: catalog.list_bilingual_free(
                        lang_a=la, lang_b=lb, page=1, popular_page=pp),
                    append=True)
                return
        if self.bilingual and isinstance(nxt, str) and nxt.startswith("biseed:"):
            parts = nxt.split(":")
            if len(parts) >= 4:
                la, lb, pg = parts[1], parts[2], int(parts[3])
                self._page = pg
                self._run_fetch(
                    lambda: catalog.list_bilingual_seed(lang_a=la, lang_b=lb, page=pg),
                    append=True)
                return
        self._page += 1
        if self._mode == "browse":
            lang = None if self._lang == "" else (self._lang_param() or "en")
            if self.bilingual:
                la = lang or "en"
                lb = self._lang_b_param()
                self._run_fetch(lambda: catalog.list_bilingual_free(
                    lang_a=la, lang_b=lb, page=self._page), append=True)
            else:
                self._run_fetch(lambda: catalog.list_free_books(page=self._page, languages=lang),
                                append=True)
        elif self._mode == "cefr" and self._cefr:
            lang = None if self._lang == "" else (self._lang_param() or "en")
            if self.bilingual:
                self._run_fetch(lambda: catalog.list_bilingual_by_cefr(
                    self._cefr, lang_a=lang or "en", lang_b=self._lang_b_param(),
                    page=self._page), append=True)
            else:
                self._run_fetch(lambda: catalog.list_by_cefr(
                    self._cefr, page=self._page, languages=lang), append=True)
        else:
            if self.bilingual:
                self._run_fetch(lambda: catalog.search_bilingual(
                    title=self.e_title.get().strip(), author=self.e_author.get().strip(),
                    lang_a=self._lang_param() or "en", lang_b=self._lang_b_param(),
                    page=self._page), append=True)
            else:
                self._run_fetch(lambda: catalog.search_books(
                    title=self.e_title.get().strip(), author=self.e_author.get().strip(),
                    languages=self._lang_param(), page=self._page), append=True)

    def _run_fetch(self, fn, *, append: bool = False) -> None:
        self._busy = True
        self.status.configure(text=_t("Загрузка каталога…"), fg=CYAN)
        if not append:
            self.results = []
            self.sel = None
            self._render_list()

        def work():
            try:
                data = fn()
                err = None
            except catalog.BookCatalogError as exc:
                data, err = None, str(exc)
            self.after(0, lambda: self._on_fetch(data, err, append))

        threading.Thread(target=work, daemon=True).start()

    def _on_fetch(self, data: dict | None, err: str | None, append: bool) -> None:
        self._busy = False
        if err:
            self.status.configure(text=err, fg=RED)
            return
        batch = list((data or {}).get("results") or [])
        self._next_url = (data or {}).get("next")
        if append:
            self.results.extend(batch)
        else:
            self.results = batch
        n = int((data or {}).get("count") or 0)
        if not self.results:
            if self.bilingual:
                la = (self._lang_param() or "en").upper()
                lb = self._lang_b_param().upper()
                if self._use_bilinguis():
                    msg = _t("В bilinguis нет пар {0}→{1}. Попробуйте EN→RU или EN→UK.").format(la, lb)
                else:
                    msg = _t("Пар {0}→{1} в Gutenberg нет. Для RU/UK выберите перевод RU или UK "
                             "(bilinguis), либо «＋ ВРУЧНУЮ».").format(la, lb)
            else:
                msg = _t("Ничего не найдено. Попробуйте английское название или другой язык.")
            self.status.configure(text=msg, fg=AMBER)
        else:
            extra = ""
            if self.bilingual:
                extra = _t(" · с переводом: {0}").format(len(self.results))
            self.status.configure(
                text=_t("В каталоге: {0} · на экране: {1} · с обложкой: {2}").format(
                    n, len(self.results), sum(1 for b in self.results if b.get("has_cover")))
                + extra,
                fg=GREEN)
        self._render_list()
        threading.Thread(target=self._prefetch_covers, daemon=True).start()

    def _prefetch_covers(self) -> None:
        changed = False
        for b in list(self.results):
            if b.get("has_cover") and not catalog.cover_cache_path(b["id"]).exists():
                if catalog.download_cover(b):
                    changed = True
        if changed:
            self.after(0, self._render_list)

    def _render_list(self) -> None:
        for w in self.list.inner.winfo_children():
            w.destroy()
        self._photos.clear()
        if not self.results:
            L(self.list.inner, _t("Результаты появятся здесь."), fg=MUTED, size=10, bg=PANEL).pack(
                anchor="w", padx=px(10), pady=px(12))
            return
        for i, b in enumerate(self.results):
            on = i == self.sel
            row = tk.Frame(self.list.inner, bg=BG2 if on else PANEL, cursor="hand2",
                           highlightthickness=1, highlightbackground=CYAN if on else LINE)
            row.pack(fill=tk.X, pady=px(3), padx=px(4))

            cover_box = tk.Frame(row, bg=row["bg"], width=COVER_W, height=COVER_H)
            cover_box.pack(side=tk.LEFT, padx=px(8), pady=px(6))
            cover_box.pack_propagate(False)
            path = catalog.cover_cache_path(b["id"]) if b.get("has_cover") else None
            if path and not path.exists():
                path = None
            photo = _cover_photo(path if path and path.exists() else None)
            if photo is not None:
                self._photos.append(photo)
                lab = tk.Label(cover_box, image=photo, bg=row["bg"], bd=0)
                lab.pack()
                lab.bind("<Button-1>", lambda _e, idx=i: self._pick(idx))
            else:
                ph = _placeholder_cover(cover_box)
                ph.pack()
                ph.bind("<Button-1>", lambda _e, idx=i: self._pick(idx))

            mid = tk.Frame(row, bg=row["bg"])
            mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(6), pady=px(6))
            langs = ", ".join((b.get("languages") or [])[:3]).upper() or "—"
            cover_note = _t("есть обложка") if b.get("has_cover") else _t("без обложки")
            title_bits = b["title"]
            if b.get("cefr"):
                title_bits = f"[{b['cefr']}] {title_bits}"
            if self.bilingual or b.get("bilingual"):
                title_bits = "2ЯЗ · " + title_bits
            L(mid, title_bits, fg=TEXT, size=12, bold=True, bg=mid["bg"],
              wraplength=px(720)).pack(anchor="w")
            L(mid, b.get("author") or _t("автор не указан"), fg=MUTED, size=9, bg=mid["bg"]).pack(
                anchor="w")
            meta = _t("{0} · {1} · скачиваний ≈ {2}").format(
                langs, cover_note, b.get("download_count") or 0)
            if b.get("cefr"):
                meta = _t("уровень {0}").format(b["cefr"]) + " · " + meta
            tr = b.get("translation") if isinstance(b.get("translation"), dict) else None
            if tr:
                la = catalog.primary_lang(b, "?").upper()
                lb = catalog.primary_lang(tr, (b.get("lang_b") or "?")).upper()
                # защита UI: не показывать «перевод» того же языка
                if la == lb:
                    meta = _t("⚠ ложная пара (один язык) — не скачивать") + " · " + meta
                else:
                    meta = _t("перевод {0}→{1}: {2}").format(
                        la, lb, (tr.get("title") or "")[:42]) + " · " + meta
            L(mid, meta, fg=CYAN if on else MUTED, size=8, bg=mid["bg"]).pack(
                anchor="w", pady=(px(2), 0))
            for w in (row, mid, *mid.winfo_children()):
                w.bind("<Button-1>", lambda _e, idx=i: self._pick(idx))

    def _pick(self, idx: int) -> None:
        self.sel = idx
        self._render_list()

    def download(self) -> None:
        if self._busy:
            return
        if self.sel is None or self.sel >= len(self.results):
            self.status.configure(text=_t("Сначала выберите книгу в списке."), fg=AMBER)
            return
        book = self.results[self.sel]
        if self.bilingual:
            tr_book = book.get("translation") if isinstance(book.get("translation"), dict) else None
            lb = self._lang_b_param()
            if bilinguis.is_bilinguis_book(book):
                if not tr_book or (book.get("lang_a") or "") == (book.get("lang_b") or ""):
                    self.status.configure(
                        text=_t("Для этой книги нет готового перевода на выбранный язык."),
                        fg=AMBER)
                    return
            elif not tr_book or not catalog.is_language_pair(book, tr_book, lb):
                self.status.configure(
                    text=_t("Для этой книги нет готового перевода на выбранный язык "
                            "(нельзя скачать пару одного языка, напр. EN→EN)."),
                    fg=AMBER)
                return
        self._busy = True
        self.status.configure(text=_t("Скачиваю «{0}»…").format(book["title"][:48]), fg=CYAN)

        def work():
            try:
                if self.bilingual:
                    tr_book = book.get("translation") or {}
                    if bilinguis.is_bilinguis_book(book):
                        text_a, text_b = bilinguis.download_pair(book)
                        err = None
                        self.after(0, lambda: self._on_download_bilingual(
                            book, tr_book, text_a, text_b, err, source="bilinguis"))
                        return
                    text_a = catalog.download_text(book)
                    text_b = catalog.download_text(tr_book)
                    catalog.download_cover(book)
                    err = None
                    self.after(0, lambda: self._on_download_bilingual(
                        book, tr_book, text_a, text_b, err))
                    return
                text = catalog.download_text(book)
                catalog.download_cover(book)
                err = None
            except (catalog.BookCatalogError, bilinguis.BilinguisError) as exc:
                text, err = None, str(exc)
                if self.bilingual:
                    self.after(0, lambda: self._on_download_bilingual(
                        book, book.get("translation") or {}, None, None, err,
                        source="bilinguis" if bilinguis.is_bilinguis_book(book) else "gutenberg"))
                    return
            self.after(0, lambda: self._on_download(book, text, err))

        threading.Thread(target=work, daemon=True).start()

    def _on_download(self, book: dict, text: str | None, err: str | None) -> None:
        self._busy = False
        if err or not text:
            self.status.configure(text=err or _t("Ошибка загрузки."), fg=RED)
            return
        m = self.lib.add(
            text,
            title=book["title"],
            author=book.get("author") or "",
            opts=self.opts,
            source={
                "kind": "gutenberg",
                "gutenberg_id": book.get("id"),
                "url": book.get("page_url"),
                "text_url": book.get("text_url"),
                "cover_url": book.get("cover_url"),
                **({"cefr": book["cefr"]} if book.get("cefr") else {}),
            },
        )
        self.status.configure(text=_t("Сохранено на полку: «{0}»").format(m["title"]), fg=GREEN)
        if self.on_added:
            try:
                self.on_added(m["id"])
            except Exception:  # noqa: BLE001
                pass

    def _on_download_bilingual(self, book: dict, tr_book: dict,
                               text_a: str | None, text_b: str | None, err: str | None,
                               *, source: str = "gutenberg") -> None:
        self._busy = False
        if err or not text_a or not text_b:
            self.status.configure(text=err or _t("Ошибка загрузки."), fg=RED)
            return
        lb_want = self._lang_b_param()
        from_bilinguis = source == "bilinguis" or bilinguis.is_bilinguis_book(book)
        if not from_bilinguis and not catalog.is_language_pair(book, tr_book, lb_want):
            self.status.configure(
                text=_t("Отклонено: это не пара разных языков (часто ложный EN→EN). "
                        "Для RU/UK откройте перевод RU или UK (bilinguis)."),
                fg=RED)
            return
        if from_bilinguis:
            la = bilinguis.normalize_lang(book.get("lang_a") or "en")
            lb = bilinguis.normalize_lang(book.get("lang_b") or lb_want)
        else:
            la = catalog.primary_lang(book, "en")
            lb = lb_want if lb_want in catalog.book_langs(tr_book) else catalog.primary_lang(tr_book, lb_want)
        # финальная проверка по самому тексту
        try:
            from stamina.library import detect_lang
            da = detect_lang(text_a[:8000])
            db = detect_lang(text_b[:8000])
        except Exception:
            da, db = la, lb
        if da and db and da == db:
            self.status.configure(
                text=_t("Отклонено: оба файла на языке {0} (не перевод).").format(da.upper()),
                fg=RED)
            return
        if da and da != la:
            la = da
        if db and db != lb:
            lb = db
        if la == lb:
            self.status.configure(
                text=_t("Отклонено: оригинал и перевод — один язык ({0}).").format(la.upper()),
                fg=RED)
            return
        src = {
            "kind": "bilinguis" if from_bilinguis else "gutenberg_bilingual",
            "url": book.get("page_url"),
            "url_tr": tr_book.get("page_url"),
            "text_url": book.get("text_url"),
            "bilingual_source": "pd",
            "slug": book.get("slug"),
        }
        if not from_bilinguis:
            src.update({
                "gutenberg_id": book.get("id"),
                "gutenberg_id_tr": tr_book.get("id"),
                "text_url_tr": tr_book.get("text_url"),
                "cover_url": book.get("cover_url"),
                **({"cefr": book["cefr"]} if book.get("cefr") else {}),
            })
        try:
            m = self.lib.add_bilingual(
                text_a, text_b,
                title=book.get("title") or "",
                author=book.get("author") or "",
                lang_a=la, lang_b=lb, source_kind="pd",
                source=src,
            )
        except ValueError as exc:
            self.status.configure(text=str(exc), fg=RED)
            return
        self.status.configure(
            text=_t("2ЯЗ на полке: «{0}» ({1}→{2})").format(m["title"], la.upper(), lb.upper()),
            fg=GREEN)
        if self.on_added:
            try:
                self.on_added(m["id"])
            except Exception:  # noqa: BLE001
                pass


class ShelfPanel(tk.Frame):
    """Локальная полка книг — встроенный экран выбора для печати."""

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_pick: Callable[[str], None] | None = None,
                 on_back: Callable[[], None] | None = None,
                 on_open_catalog: Callable[[], None] | None = None) -> None:
        super().__init__(master, bg=BG)
        self.lib = lib
        self.opts = opts or {}
        self.on_pick = on_pick
        self.on_back = on_back
        self.on_open_catalog = on_open_catalog
        self.sel: str | None = None
        self._photos: list[tk.PhotoImage] = []

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=px(12), pady=(px(8), 0))
        if on_back:
            HudButton(head, _t("← НАЗАД"), on_back, height=30, font_size=9, width=100).pack(
                side=tk.LEFT, padx=(0, px(10)))
        tk.Label(head, text=_t("ПОЛКА КНИГ · ВЫБОР ДЛЯ НАБОРА"), bg=BG, fg=AMBER,
                 font=theme.font(14, True)).pack(side=tk.LEFT)

        L(self, _t("Локальная библиотека. Можно искать свободные книги в интернете (Gutenberg) и скачать на полку."),
          fg=MUTED, size=8, bg=BG, wraplength=px(1100)).pack(anchor="w", padx=px(14), pady=(px(2), 0))

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, side=tk.BOTTOM, padx=px(12), pady=(px(4), px(10)))
        HudButton(bot, _t("🔍 СВОБОДНЫЕ КНИГИ"), self._search_net, color=CYAN, height=38,
                  font_size=9, width=200).pack(side=tk.LEFT)
        HudButton(bot, _t("⌨ ПЕЧАТАТЬ"), self._use, color=GREEN, height=38, font_size=11,
                  width=160).pack(side=tk.RIGHT)
        if on_back:
            HudButton(bot, _t("← К ПОДГОТОВКЕ"), on_back, height=38, font_size=9, width=140).pack(
                side=tk.RIGHT, padx=px(6))

        body = HudPanel(self, _t("НА ПОЛКЕ"), accent=AMBER)
        body.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=(px(6), 0))
        self.list = ScrollFrame(body.body, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True)

    def activate(self) -> None:
        self._render()

    def _cover_for_meta(self, m: dict) -> Path | None:
        src = m.get("source") or {}
        gid = src.get("gutenberg_id")
        if gid:
            p = catalog.cover_cache_path(int(gid))
            if p.exists():
                return p
            if src.get("cover_url"):
                return catalog.download_cover({"id": gid, "cover_url": src["cover_url"]})
        return None

    def _render(self) -> None:
        for w in self.list.inner.winfo_children():
            w.destroy()
        self._photos.clear()
        metas = self.lib.all()
        if not metas:
            L(self.list.inner,
              _t("Полка пуста. Нажмите «Свободные книги» или добавьте файл в Скорочтение → Библиотека."),
              fg=MUTED, size=10, bg=PANEL, wraplength=px(720), justify="left").pack(
                anchor="w", padx=px(12), pady=px(16))
            return
        if self.sel not in [m["id"] for m in metas]:
            self.sel = metas[0]["id"]
        for m in metas:
            on = m["id"] == self.sel
            row = tk.Frame(self.list.inner, bg=BG2 if on else PANEL, cursor="hand2",
                           highlightthickness=1, highlightbackground=CYAN if on else LINE)
            row.pack(fill=tk.X, pady=px(2), padx=px(4))
            box = tk.Frame(row, bg=row["bg"], width=COVER_W, height=COVER_H)
            box.pack(side=tk.LEFT, padx=px(8), pady=px(6))
            box.pack_propagate(False)
            path = self._cover_for_meta(m)
            photo = _cover_photo(path)
            if photo is not None:
                self._photos.append(photo)
                lab = tk.Label(box, image=photo, bg=row["bg"], bd=0)
                lab.pack()
                lab.bind("<Button-1>", lambda _e, i=m["id"]: self._pick(i))
            else:
                ph = _placeholder_cover(box)
                ph.pack()
                ph.bind("<Button-1>", lambda _e, i=m["id"]: self._pick(i))
            mid = tk.Frame(row, bg=row["bg"])
            mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(6), pady=px(6))
            L(mid, m["title"], fg=TEXT, size=12, bold=True, bg=mid["bg"]).pack(anchor="w")
            L(mid, _t("{0} · {1} · {2} сл.").format(
                m.get("author") or "—", (m.get("lang") or "?").upper(),
                m["original"].get("words") or "?"),
              fg=MUTED, size=8, bg=mid["bg"]).pack(anchor="w")
            for w in (row, mid, *mid.winfo_children()):
                w.bind("<Button-1>", lambda _e, i=m["id"]: self._pick(i))

    def _pick(self, tid: str) -> None:
        self.sel = tid
        self._render()

    def _search_net(self) -> None:
        if self.on_open_catalog:
            self.on_open_catalog()

    def _use(self) -> None:
        if not self.sel:
            messagebox.showinfo(_t("Полка"), _t("Выберите книгу."), parent=self)
            return
        if self.on_pick:
            self.on_pick(self.sel)


class BookSearchDialog(tk.Toplevel):
    """Совместимость: модальное окно вокруг BookCatalogPanel (кнопки «Свободные книги»)."""

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_added: Callable[[str], None] | None = None,
                 bilingual: bool = False,
                 on_manual: Callable[[], None] | None = None) -> None:
        super().__init__(master, bg=BG)
        self.title(_t("Свободные книги · 2 языка · Project Gutenberg") if bilingual
                   else _t("Свободные книги · Project Gutenberg"))
        self.transient(master.winfo_toplevel())
        try:
            self.grab_set()
        except tk.TclError:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = min(px(1100), int(sw * 0.92)), min(px(720), int(sh * 0.88))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(20, (sh - h) // 2 - 20)}")
        self.minsize(px(720), px(480))

        def added(tid: str) -> None:
            if on_added:
                on_added(tid)

        def manual() -> None:
            self.destroy()
            if on_manual:
                on_manual()

        panel = BookCatalogPanel(
            self, lib, opts=opts, on_added=added, on_back=self.destroy,
            bilingual=bilingual, on_manual=manual if bilingual and on_manual else None)
        panel.pack(fill=tk.BOTH, expand=True)
        panel.activate()
        self.protocol("WM_DELETE_WINDOW", self.destroy)


class ShelfDialog(tk.Toplevel):
    """Совместимость: модальное окно вокруг ShelfPanel."""

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_pick: Callable[[str], None] | None = None) -> None:
        super().__init__(master, bg=BG)
        self.title(_t("Полка книг"))
        self.transient(master.winfo_toplevel())
        try:
            self.grab_set()
        except tk.TclError:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = min(px(960), int(sw * 0.9)), min(px(640), int(sh * 0.85))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(20, (sh - h) // 2 - 20)}")

        def open_catalog() -> None:
            def after_add(tid: str) -> None:
                panel.activate()
                if on_pick and messagebox.askyesno(
                        _t("Печать"), _t("Книга на полке. Выбрать её для набора?"), parent=self):
                    self.destroy()
                    on_pick(tid)

            BookSearchDialog(self, lib, opts=opts, on_added=after_add)

        def picked(tid: str) -> None:
            self.destroy()
            if on_pick:
                on_pick(tid)

        panel = ShelfPanel(self, lib, opts=opts, on_pick=picked, on_back=self.destroy,
                           on_open_catalog=open_catalog)
        panel.pack(fill=tk.BOTH, expand=True)
        panel.activate()
        self.protocol("WM_DELETE_WINDOW", self.destroy)


def start_typing_from_library(app, lib: libmod.Library, tid: str, parent=None) -> None:
    """Передать книгу с полки в «Свой текст» (как LibraryPage.type_text)."""
    from stamina.session_storage import SessionState, load_session, save_session
    from tkinter import messagebox as mb

    m = lib.meta(tid)
    if not m:
        return
    prep, orig = lib.prepared(tid), lib.original(tid)
    saved = load_session()
    if saved is not None and libmod.sha(saved.text) == m["prepared"]["sha256"]:
        app.resume_cargo()
        return
    if saved is not None:
        if not mb.askyesno(_t("Печать"),
                           _t("Переключить печать на «{0}»?\nПозиция текущего текста сохранится в библиотеке.").format(
                               m["title"]),
                           parent=parent):
            return
        try:
            app.screens["bridge"].leave_current()
        except Exception:  # noqa: BLE001
            pass
        saved = load_session()
        cur = lib.find_by_prepared(saved.text) if saved else None
        if cur is None and saved is not None:
            cur = lib.upsert_from_cargo(saved.text, "", app.store.settings.get("cargo_opts"))
        if cur and saved is not None:
            lib.set_position(cur, "typing", saved.index)
    lib.set_active("typing", tid)
    pos = int(m["positions"]["typing"].get("char", 0))
    good_orig = orig if orig and libmod.processor(m["prepared"]["opts"])(orig) == prep else ""
    app.store.save_cargo(prep, good_orig)
    app.screens["cargo"].load_initial(prep, good_orig)
    if 0 < pos < len(prep):
        save_session(SessionState(text=prep, index=pos,
                                  case_sensitive=not m["prepared"]["opts"].get("lower", True)))
        app.resume_cargo()
    else:
        app.start_cargo(prep, good_orig)
