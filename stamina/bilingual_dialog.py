"""Окно «＋ 2 ЯЗЫКА»: оригинал + готовый перевод → Library.add_bilingual."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from stamina import library as libmod
from stamina import theme
from stamina import monitors
from stamina.hud import HudButton
from stamina.i18n import t
from stamina.library import BILINGUAL_SOURCES, Library
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, LINE_HI, MUTED, TEXT, px


def _label(master, text="", fg=None, size=10, bold=False, **kw):
    fg = TEXT if fg is None else fg  # токен скина — в момент вызова, не при импорте
    return tk.Label(master, text=text, fg=fg, bg=BG, font=theme.font(size, bold),
                    anchor="w", justify="left", **kw)


def _entry(master, width=40) -> tk.Entry:
    return tk.Entry(master, width=width, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat",
                    font=theme.font(11), highlightthickness=1,
                    highlightbackground=LINE_HI, highlightcolor=CYAN)


class BilingualImportDialog(tk.Toplevel):
    """Модальное окно. После успеха: .result = meta книги; иначе None."""

    def __init__(self, parent, lib: Library) -> None:
        super().__init__(parent, bg=BG)
        self.title(t("Импорт двуязычной книги"))
        self.transient(parent.winfo_toplevel())
        self.lib = lib
        self.result = None
        self._source = "mt"
        self._src_btns: dict[str, HudButton] = {}
        pad = px(12)

        _label(self, t("ИМПОРТ · 2 ЯЗЫКА"), fg=AMBER, size=13, bold=True).pack(
            fill=tk.X, padx=pad, pady=(pad, 0))
        _label(self,
               t("Готовый перевод в файл. Без правки, без печати, без UPLINK. "
                 "В гипердрайве — выбор языка потока."),
               fg=MUTED, size=8, wraplength=px(720)).pack(fill=tk.X, padx=pad, pady=(px(2), 0))

        meta = tk.Frame(self, bg=BG)
        meta.pack(fill=tk.X, padx=pad, pady=(px(8), 0))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=1)

        _label(meta, t("Название:")).grid(row=0, column=0, sticky="w", padx=(0, px(6)))
        self.e_title = _entry(meta, 36)
        self.e_title.grid(row=0, column=1, sticky="ew", padx=(0, px(12)))
        _label(meta, t("Автор:")).grid(row=0, column=2, sticky="w", padx=(0, px(6)))
        self.e_author = _entry(meta, 28)
        self.e_author.grid(row=0, column=3, sticky="ew")

        _label(meta, t("Язык оригинала:")).grid(row=1, column=0, sticky="w", pady=(px(6), 0))
        self.e_lang_a = _entry(meta, 8)
        self.e_lang_a.insert(0, "en")
        self.e_lang_a.grid(row=1, column=1, sticky="w", pady=(px(6), 0))
        _label(meta, t("Язык перевода:")).grid(row=1, column=2, sticky="w", pady=(px(6), 0))
        self.e_lang_b = _entry(meta, 8)
        self.e_lang_b.insert(0, "ru")
        self.e_lang_b.grid(row=1, column=3, sticky="w", pady=(px(6), 0))

        src_fr = tk.Frame(self, bg=BG)
        src_fr.pack(fill=tk.X, padx=pad, pady=(px(8), 0))
        _label(src_fr, t("Источник перевода:")).pack(side=tk.LEFT)
        for code, lab in (("pd", "PD"), ("mt", "MT"), ("mixed", "PD+MT")):
            b = HudButton(src_fr, lab, lambda c=code: self._set_source(c), height=26,
                          font_size=8, width=56, active=(code == self._source),
                          color=CYAN if code != "mt" else GREEN)
            b.pack(side=tk.LEFT, padx=(px(6), 0))
            self._src_btns[code] = b
        HudButton(src_fr, t("★ СВОБОДНЫЕ КНИГИ"), self._open_free_catalog, color=AMBER,
                  height=26, font_size=8, width=160).pack(side=tk.LEFT, padx=(px(12), 0))
        _label(src_fr, t("PD — public domain · MT — машинный · PD+MT — смешанный"),
               fg=MUTED, size=7).pack(side=tk.LEFT, padx=(px(10), 0))

        cols = tk.Frame(self, bg=BG)
        cols.pack(fill=tk.BOTH, expand=True, padx=pad, pady=px(8))
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)
        cols.rowconfigure(1, weight=1)

        self.t_orig = self._text_col(cols, 0, t("ОРИГИНАЛ"), self._load_orig)
        self.t_tr = self._text_col(cols, 1, t("ПЕРЕВОД"), self._load_tr)

        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=pad, pady=(0, pad))
        HudButton(bot, t("► СОХРАНИТЬ 2ЯЗ"), self.ok, color=GREEN, height=38).pack(side=tk.LEFT)
        HudButton(bot, t("ОТМЕНА"), self.destroy, height=38).pack(side=tk.RIGHT)
        _label(bot, t("Оба текста обязательны. Абзацы лучше выровнять один к одному."),
               fg=MUTED, size=8).pack(side=tk.LEFT, padx=px(12))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        try:
            self.geometry(monitors.center_geometry(parent, px(900), px(620)))
        except tk.TclError:
            pass
        self.e_title.focus_set()
        self.grab_set()

    def _text_col(self, parent, col: int, title: str, load_cmd) -> tk.Text:
        head = tk.Frame(parent, bg=BG)
        head.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else px(6), 0 if col == 1 else px(6)))
        _label(head, title, fg=CYAN, size=10, bold=True).pack(side=tk.LEFT)
        HudButton(head, t("ИЗ ФАЙЛА…"), load_cmd, height=26, font_size=8, width=90).pack(
            side=tk.RIGHT)
        box = tk.Text(parent, width=40, height=18, bg=BG2, fg=TEXT, insertbackground=CYAN,
                      relief="flat", wrap="word", font=theme.font(10), padx=px(8), pady=px(6))
        box.grid(row=1, column=col, sticky="nsew",
                 padx=(0 if col == 0 else px(6), 0 if col == 1 else px(6)), pady=(px(4), 0))
        return box

    def _set_source(self, code: str) -> None:
        if code not in BILINGUAL_SOURCES:
            code = "mt"
        self._source = code
        for c, b in self._src_btns.items():
            b.set_active(c == code)

    def _open_free_catalog(self) -> None:
        """Тот же каталог, что «Свободные книги», в режиме 2ЯЗ — заполняет поля при выборе."""
        from stamina.book_shelf import BookSearchDialog

        def on_added(tid: str) -> None:
            # книга уже на полке — закрываем ручной диалог с результатом
            m = self.lib.meta(tid)
            if m:
                self.result = m
                self.destroy()

        BookSearchDialog(self, self.lib, bilingual=True, on_added=on_added)

    def _ask_txt(self, title: str) -> str:
        return filedialog.askopenfilename(
            parent=self, title=title,
            filetypes=[(t("Текст"), "*.txt"), (t("Все файлы"), "*.*")])

    def _load_into(self, widget: tk.Text, title: str) -> None:
        path = self._ask_txt(title)
        if not path:
            return
        try:
            text, _enc = libmod.read_text_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(t("Импорт двуязычной книги"),
                                 t("Не удалось прочитать файл:\n{0}").format(exc), parent=self)
            return
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        if not self.e_title.get().strip():
            guess, author = libmod.guess_title(text, Path(path).stem)
            self.e_title.insert(0, guess)
            if author and not self.e_author.get().strip():
                self.e_author.insert(0, author)

    def _load_orig(self) -> None:
        self._load_into(self.t_orig, t("Файл оригинала"))

    def _load_tr(self) -> None:
        self._load_into(self.t_tr, t("Файл перевода"))

    def ok(self) -> None:
        original = self.t_orig.get("1.0", tk.END).strip()
        translation = self.t_tr.get("1.0", tk.END).strip()
        if not original or not translation:
            messagebox.showwarning(
                t("Импорт двуязычной книги"),
                t("Нужны оба текста: оригинал и перевод."), parent=self)
            return
        title = self.e_title.get().strip()
        author = self.e_author.get().strip()
        lang_a = self.e_lang_a.get().strip().lower()[:8]
        lang_b = self.e_lang_b.get().strip().lower()[:8]
        try:
            m = self.lib.add_bilingual(
                original, translation,
                title=title, author=author,
                lang_a=lang_a, lang_b=lang_b or "ru",
                source_kind=self._source,
                source={"kind": "bilingual_import", "bilingual_source": self._source},
            )
        except ValueError as exc:
            messagebox.showwarning(t("Импорт двуязычной книги"), str(exc), parent=self)
            return
        except OSError as exc:
            messagebox.showerror(t("Импорт двуязычной книги"),
                                 t("Не удалось сохранить:\n{0}").format(exc), parent=self)
            return
        self.result = m
        self.destroy()


def import_bilingual(parent, lib: Library):
    """Показать диалог; вернуть meta или None."""
    dlg = BilingualImportDialog(parent, lib)
    parent.wait_window(dlg)
    return dlg.result
