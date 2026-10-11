"""UI: поиск книг в интернете (Project Gutenberg) и полка локальной библиотеки."""
from __future__ import annotations

from stamina.i18n import t as _t

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

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
        im.thumbnail((w, h), Image.LANCZOS)
        # холст фиксированного размера
        canvas = Image.new("RGB", (w, h), (8, 18, 33))
        x = (w - im.width) // 2
        y = (h - im.height) // 2
        canvas.paste(im, (x, y))
        return ImageTk.PhotoImage(canvas)
    except Exception:  # noqa: BLE001
        try:
            return tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None


def _placeholder_cover(parent, w: int = COVER_W, h: int = COVER_H) -> tk.Canvas:
    c = tk.Canvas(parent, width=w, height=h, bg=blend(CYAN, BG, 0.85), highlightthickness=1,
                  highlightbackground=LINE, bd=0)
    c.create_text(w // 2, h // 2, text=_t("нет\nобложки"), fill=MUTED, font=theme.font(7, True),
                  justify="center")
    return c


class BookSearchDialog(tk.Toplevel):
    """Поиск по названию/автору + лента свободных книг → скачать в библиотеку."""

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_added=None) -> None:
        super().__init__(master, bg=BG)
        self.title(_t("Свободные книги · Project Gutenberg"))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lib = lib
        self.opts = opts or {}
        self.on_added = on_added
        self.results: list[dict] = []
        self.sel: int | None = None
        self._busy = False
        self._photos: list[tk.PhotoImage] = []  # удержать ссылки
        self._lang = "en"
        self._page = 1
        self._mode = "browse"  # browse | search
        self._next_url = None

        self.geometry(f"{px(900)}x{px(620)}")
        HudPanel(self, _t("PROJECT GUTENBERG · ОБЩЕСТВЕННОЕ ДОСТОЯНИЕ")).pack(
            fill=tk.X, padx=px(12), pady=(px(10), 0))
        L(self, _t("Поиск по названию и/или автору. Список — бесплатные книги в свободном доступе. "
                   "С обложкой или без (заглушка). Авторские современные книги сюда не входят."),
          fg=MUTED, size=8, bg=BG, wraplength=px(860), justify="left").pack(
            anchor="w", padx=px(14), pady=(px(4), 0))

        form = tk.Frame(self, bg=BG)
        form.pack(fill=tk.X, padx=px(14), pady=px(8))
        L(form, _t("НАЗВАНИЕ"), fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=0, sticky="w")
        L(form, _t("АВТОР"), fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=1, sticky="w", padx=(px(8), 0))
        L(form, _t("ЯЗЫК"), fg=MUTED, size=8, bold=True, bg=BG).grid(row=0, column=2, sticky="w", padx=(px(8), 0))
        self.e_title = entry(form, width=32, size=11)
        self.e_title.grid(row=1, column=0, sticky="ew", padx=(0, px(8)))
        self.e_author = entry(form, width=24, size=11)
        self.e_author.grid(row=1, column=1, sticky="ew", padx=(0, px(8)))
        lang_fr = tk.Frame(form, bg=BG)
        lang_fr.grid(row=1, column=2, sticky="w")
        self._lang_btns = {}
        for code, name in LANG_CHOICES:
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
        self.e_title.bind("<Return>", lambda _e: self.search())
        self.e_author.bind("<Return>", lambda _e: self.search())

        self.status = L(self, "", fg=MUTED, size=9, bg=BG)
        self.status.pack(anchor="w", padx=px(14))

        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(6))
        self.list = ScrollFrame(body, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True)

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(0, px(12)))
        self.btn_more = HudButton(bot, _t("ЕЩЁ…"), self.load_more, height=36, font_size=9, width=90)
        self.btn_more.pack(side=tk.LEFT)
        self.btn_dl = HudButton(bot, _t("⇩ СКАЧАТЬ В БИБЛИОТЕКУ"), self.download, color=GREEN,
                                height=36, font_size=10, width=220)
        self.btn_dl.pack(side=tk.LEFT, padx=px(8))
        HudButton(bot, _t("ЗАКРЫТЬ"), self.destroy, height=36, font_size=9, width=110).pack(side=tk.RIGHT)

        self.after(80, self.browse_free)

    def _set_lang(self, code: str) -> None:
        self._lang = code
        for c, b in self._lang_btns.items():
            b.set_active(c == code)

    def _lang_param(self) -> str | None:
        return self._lang or None

    def browse_free(self) -> None:
        if self._busy:
            return
        self._mode = "browse"
        self._page = 1
        # по умолчанию EN; «ВСЕ» — без фильтра языка
        lang = self._lang_param() if self._lang_param() is not None else "en"
        if self._lang == "":
            lang = None
        self._run_fetch(lambda: catalog.list_free_books(page=1, languages=lang))

    def search(self) -> None:
        if self._busy:
            return
        title = self.e_title.get().strip()
        author = self.e_author.get().strip()
        if not title and not author:
            self.status.configure(text=_t("Введите название или автора — или откройте «Свободные»."), fg=AMBER)
            return
        self._mode = "search"
        self._page = 1
        self._run_fetch(lambda: catalog.search_books(
            title=title, author=author, languages=self._lang_param(), page=1))

    def load_more(self) -> None:
        if self._busy or not self._next_url:
            return
        self._page += 1
        if self._mode == "browse":
            lang = None if self._lang == "" else (self._lang_param() or "en")
            self._run_fetch(lambda: catalog.list_free_books(page=self._page, languages=lang),
                            append=True)
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
            self.status.configure(
                text=_t("Ничего не найдено. Попробуйте английское название или другой язык."),
                fg=AMBER)
        else:
            self.status.configure(
                text=_t("В каталоге: {0} · на экране: {1} · с обложкой: {2}").format(
                    n, len(self.results), sum(1 for b in self.results if b.get("has_cover"))),
                fg=GREEN)
        self._render_list()
        # подтянуть обложки в фоне
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
            if path and not path.exists() and b.get("cover_url"):
                path = None  # ещё качается
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
            L(mid, b["title"], fg=TEXT, size=12, bold=True, bg=mid["bg"], wraplength=px(620)).pack(anchor="w")
            L(mid, b.get("author") or _t("автор не указан"), fg=MUTED, size=9, bg=mid["bg"]).pack(anchor="w")
            L(mid, _t("{0} · {1} · скачиваний ≈ {2}").format(langs, cover_note, b.get("download_count") or 0),
              fg=CYAN if on else MUTED, size=8, bg=mid["bg"]).pack(anchor="w", pady=(px(2), 0))
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
        self._busy = True
        self.status.configure(text=_t("Скачиваю «{0}»…").format(book["title"][:48]), fg=CYAN)

        def work():
            try:
                text = catalog.download_text(book)
                catalog.download_cover(book)
                err = None
            except catalog.BookCatalogError as exc:
                text, err = None, str(exc)
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
            },
        )
        self.status.configure(text=_t("Сохранено на полку: «{0}»").format(m["title"]), fg=GREEN)
        if self.on_added:
            try:
                self.on_added(m["id"])
            except Exception:  # noqa: BLE001
                pass
        if messagebox.askyesno(_t("Книга загружена"),
                               _t("«{0}» добавлена на полку.\nЗакрыть каталог?").format(m["title"]),
                               parent=self):
            self.destroy()


class ShelfDialog(tk.Toplevel):
    """Полка: выбрать книгу из локальной библиотеки для печати."""

    def __init__(self, master, lib: libmod.Library, *, opts: dict | None = None,
                 on_pick=None) -> None:
        super().__init__(master, bg=BG)
        self.title(_t("Полка книг"))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lib = lib
        self.opts = opts or {}
        self.on_pick = on_pick
        self.sel: str | None = None
        self._photos: list[tk.PhotoImage] = []
        self.geometry(f"{px(760)}x{px(520)}")

        L(self, _t("ПОЛКА КНИГ · ВЫБОР ДЛЯ НАБОРА"), fg=TEXT, size=14, bold=True, bg=BG).pack(
            anchor="w", padx=px(14), pady=(px(12), px(4)))
        L(self, _t("Локальная библиотека. Можно искать свободные книги в интернете (Gutenberg) и скачать на полку."),
          fg=MUTED, size=8, bg=BG, wraplength=px(720)).pack(anchor="w", padx=px(14))

        self.list = ScrollFrame(self, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(8))
        self._render()

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=px(12), pady=(0, px(12)))
        HudButton(bot, _t("🔍 СВОБОДНЫЕ КНИГИ"), self._search_net, color=CYAN, height=34,
                  font_size=9, width=180).pack(side=tk.LEFT)
        HudButton(bot, _t("⌨ ПЕЧАТАТЬ"), self._use, color=GREEN, height=34, font_size=10,
                  width=140).pack(side=tk.RIGHT)
        HudButton(bot, _t("ЗАКРЫТЬ"), self.destroy, height=34, font_size=9, width=100).pack(
            side=tk.RIGHT, padx=px(6))

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
              fg=MUTED, size=10, bg=PANEL, wraplength=px(640), justify="left").pack(
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
        BookSearchDialog(self, self.lib, opts=self.opts, on_added=lambda _t: self._render())

    def _use(self) -> None:
        if not self.sel:
            messagebox.showinfo(_t("Полка"), _t("Выберите книгу."), parent=self)
            return
        if self.on_pick:
            self.on_pick(self.sel)
        self.destroy()


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
