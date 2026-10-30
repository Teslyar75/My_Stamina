"""Окно «ЗАГРУЗИТЬ НА БОРТ» для отсека Документы — общий Modal пульта.

Выбрать файл (кнопка или недавние), затем «ЧИТАТЬ» (просмотр) или
«РЕДАКТИРОВАТЬ». Перетаскивание файлов — если в Tk есть tkdnd.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from stamina import docs_import, theme
from stamina.hud import HudButton
from stamina.i18n import t as _t
from stamina.pilot_screens import Modal
from stamina.theme import AMBER, CYAN, GREEN, MUTED, PANEL, TEXT, px


class OpenDocDialog(Modal):
    """result = (путь, "read" | "edit") или None."""

    def __init__(self, master, recent: list[str]) -> None:
        super().__init__(master, _t("Загрузить на борт"), accent=CYAN)
        self.path: str | None = None
        b = self.body
        tk.Label(b, text=_t("Документ с компьютера: .txt, .md, .docx (со снимками), .stdoc"),
                 bg=PANEL, fg=MUTED, font=theme.font(9), anchor="w").pack(fill=tk.X)
        row = tk.Frame(b, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(8), px(6)))
        HudButton(row, _t("ВЫБРАТЬ ФАЙЛ…"), self.browse, height=32, font_size=9,
                  color=AMBER).pack(side=tk.LEFT)
        self.picked = tk.Label(row, text=_t("файл не выбран"), bg=PANEL, fg=MUTED,
                               font=theme.font(9), anchor="w", width=44)
        self.picked.pack(side=tk.LEFT, padx=(px(8), 0))
        self.recent = [p for p in recent if Path(p).is_file()]
        tk.Label(b, text=_t("НЕДАВНИЕ"), bg=PANEL, fg=CYAN, font=theme.font(9, True),
                 anchor="w").pack(fill=tk.X, pady=(px(4), px(2)))
        self.listbox = tk.Listbox(b, height=7, bg=theme.BG2, fg=TEXT, selectbackground=CYAN,
                                  relief=tk.FLAT, highlightthickness=0, font=theme.font(9),
                                  activestyle="none")
        self.listbox.pack(fill=tk.BOTH, expand=True)
        for p in self.recent:
            self.listbox.insert(tk.END, f"{Path(p).name}   —   {Path(p).parent}")
        if not self.recent:
            self.listbox.insert(tk.END, _t("пока пусто"))
            self.listbox.configure(fg=MUTED)
        self.listbox.bind("<<ListboxSelect>>", self._on_recent)
        self.listbox.bind("<Double-Button-1>", lambda _e: self.done("edit"))
        self.dnd = self._enable_dnd()
        if self.dnd:
            tk.Label(b, text=_t("…или перетащите файл в это окно"), bg=PANEL, fg=MUTED,
                     font=theme.font(8), anchor="w").pack(fill=tk.X, pady=(px(4), 0))
        btns = tk.Frame(b, bg=PANEL)
        btns.pack(fill=tk.X, pady=(px(10), 0))
        self.edit_btn = HudButton(btns, _t("РЕДАКТИРОВАТЬ"), lambda: self.done("edit"), height=32,
                                  font_size=9, color=GREEN)
        self.edit_btn.pack(side=tk.RIGHT)
        self.read_btn = HudButton(btns, _t("ЧИТАТЬ"), lambda: self.done("read"), height=32,
                                  font_size=9, color=CYAN)
        self.read_btn.pack(side=tk.RIGHT, padx=(0, px(6)))
        HudButton(btns, _t("ОТМЕНА"), self.cancel, height=32, font_size=9,
                  color=MUTED).pack(side=tk.LEFT)
        self.bind("<Return>", lambda _e: self.done("edit"))

    def _enable_dnd(self) -> bool:
        try:
            self.tk.call("package", "require", "tkdnd")
            self.tk.call("tkdnd::drop_target", "register", self._w, "DND_Files")
            self.tk.call("bind", self._w, "<<Drop:DND_Files>>",
                         self.register(lambda d: self.choose(self.tk.splitlist(d)[0]) or "copy") + " %D")
            return True
        except tk.TclError:
            return False

    def choose(self, path: str) -> None:
        if not docs_import.supported(path):
            self.picked.configure(text=_t("этот формат пока не открывается"), fg=AMBER)
            self.path = None
            return
        self.path = str(path)
        self.picked.configure(text=Path(path).name, fg=TEXT)

    def browse(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self, title=_t("Загрузить на борт"),
            filetypes=[(_t("Документы"), "*.txt *.md *.markdown *.docx *.stdoc"), (_t("Все"), "*.*")])
        if path:
            self.choose(path)

    def _on_recent(self, _e=None) -> None:
        sel = self.listbox.curselection()
        if sel and sel[0] < len(self.recent):
            self.choose(self.recent[sel[0]])

    def done(self, mode: str) -> None:
        if not self.path:
            self.picked.configure(text=_t("сначала выберите файл"), fg=AMBER)
            return
        self.result = (self.path, mode)
        self.destroy()
