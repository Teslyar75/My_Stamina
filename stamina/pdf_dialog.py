"""Окно «ОТКРЫТЬ PDF»: выбор файла, диапазон страниц, предпросмотр очищенного текста, импорт."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from stamina import pdf_import, theme
from stamina.hud import HudButton
from stamina.i18n import t
from stamina.theme import AMBER, BG, BG2, CYAN, GREEN, MUTED, RED, TEXT, px

PREVIEW_CHARS = 6000


def _label(master, text="", fg=TEXT, size=10, bold=False):
    return tk.Label(master, text=text, fg=fg, bg=BG, font=theme.font(size, bold), anchor="w", justify="left")


def ask_pdf_path(parent) -> str:
    return filedialog.askopenfilename(parent=parent, title=t("Открыть PDF"),
                                      filetypes=[("PDF", "*.pdf *.PDF"), (t("Все файлы"), "*.*")])


def pdf_missing_message(parent) -> None:
    messagebox.showinfo(
        t("Импорт PDF"),
        t("Для чтения PDF нужен пакет pypdf.\n\nУстановите его кнопкой «УСТАНОВИТЬ ВСЁ» "
          "(НАСТРОЙКИ → Проверка систем) или командой:\npip install pypdf\n\nWindows: можно снова "
          "запустить install.bat, Linux: bash install.sh."), parent=parent)


class PdfImportDialog(tk.Toplevel):
    """Модальное окно. После закрытия: .result = (текст, путь, (первая, последняя страница)) или None."""

    def __init__(self, parent, path: str) -> None:
        super().__init__(parent, bg=BG)
        self.title(t("Импорт PDF"))
        self.transient(parent.winfo_toplevel())
        self.path = path
        self.result = None
        self._q: queue.Queue = queue.Queue()
        self._busy = False
        self._res = None
        pad = px(12)
        _label(self, t("ИМПОРТ PDF"), fg=AMBER, size=13, bold=True).pack(fill=tk.X, padx=pad, pady=(pad, 0))
        self.info = _label(self, Path(path).name, fg=MUTED, size=9)
        self.info.pack(fill=tk.X, padx=pad)
        rng = tk.Frame(self, bg=BG)
        rng.pack(fill=tk.X, padx=pad, pady=(px(8), 0))
        _label(rng, t("Страницы с")).pack(side=tk.LEFT)
        self.e_first = self._entry(rng, "1")
        _label(rng, t("по")).pack(side=tk.LEFT, padx=(px(6), 0))
        self.e_last = self._entry(rng, "")
        HudButton(rng, t("ОБНОВИТЬ"), self.reload, height=30, font_size=9).pack(side=tk.LEFT, padx=px(10))
        _label(rng, t("(пусто — до конца)"), fg=MUTED, size=8).pack(side=tk.LEFT)
        self.status = _label(self, t("Извлекаю текст…"), fg=CYAN, size=9)
        self.status.pack(fill=tk.X, padx=pad, pady=(px(6), 0))
        self.text = tk.Text(self, width=90, height=22, bg=BG2, fg=TEXT, relief="flat", wrap="word",
                            font=theme.font(10), padx=px(8), pady=px(6))
        self.text.pack(fill=tk.BOTH, expand=True, padx=pad, pady=px(8))
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill=tk.X, padx=pad, pady=(0, pad))
        self.btn_ok = HudButton(bot, t("► ИМПОРТИРОВАТЬ"), self.ok, color=GREEN, height=38)
        self.btn_ok.pack(side=tk.LEFT)
        self.btn_ok.set_enabled(False)
        HudButton(bot, t("ОТМЕНА"), self.destroy, height=38).pack(side=tk.RIGHT)
        _label(bot, t("Текст станет обычной книгой библиотеки: печать, скорочтение, перевод."),
               fg=MUTED, size=8).pack(side=tk.LEFT, padx=px(12))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda e: None if isinstance(e.widget, tk.Text) else self.ok())
        self.reload()
        self.grab_set()

    def _entry(self, master, value):
        e = tk.Entry(master, width=6, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat",
                     font=theme.font(11, mono=True))
        e.insert(0, value)
        e.pack(side=tk.LEFT, padx=(px(6), 0), ipady=px(3))
        e.bind("<Return>", lambda _e: (self.reload(), "break")[1])
        return e

    def _range(self):
        def num(e, default):
            s = e.get().strip()
            return int(s) if s.isdigit() and int(s) > 0 else default
        return num(self.e_first, 1), num(self.e_last, None)

    def reload(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_ok.set_enabled(False)
        self.status.configure(text=t("Извлекаю текст…"), fg=CYAN)
        first, last = self._range()

        def work():
            try:
                self._q.put(("ok", pdf_import.load(self.path, first, last)))
            except pdf_import.PdfError as exc:
                self._q.put(("err", str(exc)))
            except Exception as exc:  # noqa: BLE001 — любая ошибка файла → сообщение, не падение
                self._q.put(("err", repr(exc)))
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self) -> None:
        try:
            kind, val = self._q.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, self._poll)
            return
        self._busy = False
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        if kind == "err":
            self.status.configure(text=t("Не удалось прочитать PDF: {0}").format(val), fg=RED)
            return
        res: pdf_import.PdfResult = val
        self._res = res
        self.info.configure(text=t("{0} · страниц в файле: {1}").format(Path(self.path).name, res.total_pages))
        if not self.e_last.get().strip():
            self.e_last.insert(0, str(res.total_pages))
        if res.scanned:
            self.status.configure(text=t("Похоже, это скан: в PDF нет текстового слоя."), fg=AMBER)
            self.text.insert("1.0", t(
                "В выбранных страницах почти нет текста — это картинки (сканы).\n\n"
                "Что можно сделать:\n"
                "• распознать PDF в программе с OCR (например, бесплатные OCRmyPDF, Tesseract, "
                "или «Сохранить как текст» в Adobe Reader / ABBYY) и открыть получившийся .txt или PDF;\n"
                "• если текст есть только на части страниц — укажите другой диапазон.\n\n"
                "Встроенное распознавание сканов (OCR) — в планах."))
            self.text.configure(state="disabled")
            return
        rm = res.removed
        self.status.configure(text=t("Страницы {0}–{1}: {2} знаков · убрано номеров страниц: {3}, "
                                     "колонтитулов: {4}").format(res.first, res.last, f"{len(res.text):,}".replace(",", " "),
                                                                rm.get("page_numbers", 0), rm.get("headers", 0)),
                              fg=GREEN)
        shown = res.text[:PREVIEW_CHARS]
        if len(res.text) > PREVIEW_CHARS:
            shown += "\n\n" + t("… (в предпросмотре — начало текста, импортируется всё)")
        self.text.insert("1.0", shown)
        self.text.configure(state="disabled")
        self.btn_ok.set_enabled(bool(res.text.strip()))

    def ok(self) -> None:
        if self._busy or not self._res or self._res.scanned or not self._res.text.strip():
            return
        self.result = (self._res.text, self.path, (self._res.first, self._res.last))
        self.destroy()


def import_pdf(parent, path: str | None = None):
    """Полный сценарий: проверить pypdf → выбрать файл → предпросмотр. → (текст, путь, страницы) или None."""
    if not pdf_import.available():
        pdf_missing_message(parent)
        return None
    path = path or ask_pdf_path(parent)
    if not path:
        return None
    dlg = PdfImportDialog(parent, path)
    parent.wait_window(dlg)
    return dlg.result
