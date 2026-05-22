"""Отдельное окно «Редактор текста» — подготовка текста для тренажёра.

Содержит все кнопки адаптации, как просил пользователь:

* «Один пробел между словами»  — :func:`text_processing.normalize_spaces`
* «Убрать знаки препинания»    — :func:`text_processing.remove_punctuation`
* «Убрать заглавные буквы»     — :func:`text_processing.to_lowercase`
* «Применить все правки»       — :func:`text_processing.adapt_for_typing`
* «Сохранить»                  — передать текст в главное окно тренажёра

Дополнительно: «Открыть файл», «Очистить», переключатель «Редактирование».
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from typing import TYPE_CHECKING, Callable

from stamina.text_processing import (
    adapt_for_typing,
    is_valid_practice_text,
    normalize_spaces,
    remove_punctuation,
    to_lowercase,
)
from stamina.theme import (
    CYAN,
    FONT_UI,
    FONT_UI_BOLD,
    GRAY,
    GREEN,
    MUTED_FG,
    PANEL_BG,
    PINK,
    PURPLE,
    TEXT_FG,
    WINDOW_BG,
    YELLOW,
)

if TYPE_CHECKING:
    from stamina.app import StaminaApp


def _make_button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None],
    *,
    color: str = GRAY,
    bold: bool = False,
) -> tk.Button:
    """Кнопка в стиле клавиш Stamina (плоская, цветная, с курсором-рукой)."""
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_UI_BOLD if bold else FONT_UI,
        bg=color,
        fg=TEXT_FG,
        activebackground=color,
        activeforeground=TEXT_FG,
        relief=tk.FLAT,
        bd=0,
        padx=14,
        pady=9,
        cursor="hand2",
    )


class TextEditorWindow(tk.Toplevel):
    """Окно редактора текста."""

    def __init__(
        self,
        master: tk.Misc,
        app: StaminaApp,
        on_saved: Callable[[str], None],
        on_start: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        self.app = app
        self.on_saved = on_saved
        self.on_start = on_start
        self.title("Редактор текста — Stamina")
        self.geometry("800x600")
        self.minsize(620, 480)
        self.configure(bg=WINDOW_BG)

        self._editable = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_initial_text()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after_idle(lambda: self.text_area.focus_set())

    # -- UI ---------------------------------------------------------

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=PANEL_BG, padx=14, pady=12)
        header.pack(fill=tk.X, padx=10, pady=(10, 6))

        tk.Label(
            header,
            text="Подготовка текста для тренировки",
            font=("Segoe UI", 14, "bold"),
            bg=PANEL_BG,
            fg=TEXT_FG,
        ).pack(anchor=tk.W)
        tk.Label(
            header,
            text=(
                "Загрузите файл или введите текст, затем используйте кнопки "
                "адаптации. Нажмите «Сохранить», чтобы текст стал заданием "
                "для тренажёра."
            ),
            font=FONT_UI,
            bg=PANEL_BG,
            fg=MUTED_FG,
            wraplength=720,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        # --- Панель кнопок ---
        tools = tk.Frame(self, bg=WINDOW_BG, padx=10, pady=2)
        tools.pack(fill=tk.X)

        row1 = tk.Frame(tools, bg=WINDOW_BG)
        row1.pack(fill=tk.X, pady=3)
        _make_button(
            row1, "Один пробел между словами",
            self._apply_normalize_spaces, color=PINK,
        ).pack(side=tk.LEFT, padx=(0, 6))
        _make_button(
            row1, "Убрать знаки препинания",
            self._apply_remove_punctuation, color=YELLOW,
        ).pack(side=tk.LEFT, padx=(0, 6))
        _make_button(
            row1, "Убрать заглавные буквы",
            self._apply_lowercase, color=GREEN,
        ).pack(side=tk.LEFT, padx=(0, 6))
        _make_button(
            row1, "Применить все правки",
            self._apply_all, color=CYAN, bold=True,
        ).pack(side=tk.LEFT, padx=(0, 6))

        row2 = tk.Frame(tools, bg=WINDOW_BG)
        row2.pack(fill=tk.X, pady=3)
        _make_button(row2, "Открыть файл…", self._open_file).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        _make_button(row2, "Очистить", self._clear_text).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        _make_button(
            row2, "Сохранить",
            self._save, color=PURPLE,
        ).pack(side=tk.LEFT, padx=(0, 6))
        # Главная «зелёная» кнопка — сохраняет и сразу запускает тренировку.
        _make_button(
            row2, "▶  Старт",
            self._start, color=GREEN, bold=True,
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Переключатель режима редактирования.
        tk.Checkbutton(
            row2,
            text="Редактирование",
            variable=self._editable,
            command=self._update_editable_state,
            bg=WINDOW_BG,
            fg=TEXT_FG,
            activebackground=WINDOW_BG,
            activeforeground=TEXT_FG,
            font=FONT_UI,
            selectcolor=PANEL_BG,
        ).pack(side=tk.RIGHT, padx=(6, 0))

        # --- Текстовое поле ---
        text_frame = tk.Frame(self, bg=PANEL_BG, padx=2, pady=2)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        self.text_area = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 13),
            undo=True,
            bg=PANEL_BG,
            fg=TEXT_FG,
            insertbackground=TEXT_FG,
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.bind("<<Modified>>", self._on_text_modified)

        # --- Предпросмотр результата адаптации ---
        preview = tk.LabelFrame(
            self,
            text=" Предпросмотр для тренировки ",
            font=FONT_UI,
            fg=TEXT_FG,
            bg=WINDOW_BG,
            padx=12,
            pady=10,
        )
        preview.pack(fill=tk.X, padx=10, pady=(2, 10))

        self.preview_label = tk.Label(
            preview,
            text="",
            font=("Segoe UI", 11),
            fg=MUTED_FG,
            bg=WINDOW_BG,
            wraplength=720,
            justify=tk.LEFT,
            anchor="w",
        )
        self.preview_label.pack(fill=tk.X, anchor=tk.W)

        self._update_editable_state()
        self._update_preview()

    # -- Состояние --------------------------------------------------

    def _load_initial_text(self) -> None:
        if self.app.practice_text:
            self.text_area.insert("1.0", self.app.practice_text)
        self.text_area.edit_modified(False)
        self._update_preview()

    def _get_text(self) -> str:
        return self.text_area.get("1.0", "end-1c")

    def _set_text(self, text: str) -> None:
        was_editable = self.text_area.cget("state") == tk.NORMAL
        if not was_editable:
            self.text_area.configure(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", text)
        if not was_editable:
            self.text_area.configure(state=tk.DISABLED)
        self.text_area.edit_modified(False)
        self._update_preview()

    def _update_editable_state(self) -> None:
        if self._editable.get():
            self.text_area.configure(state=tk.NORMAL)
        else:
            self.text_area.configure(state=tk.DISABLED)

    def _on_text_modified(self, _event: tk.Event | None = None) -> None:
        if self.text_area.edit_modified():
            self._update_preview()
            self.text_area.edit_modified(False)

    def _update_preview(self) -> None:
        adapted = adapt_for_typing(self._get_text())
        if not adapted.strip():
            self.preview_label.configure(text="(пусто — введите или загрузите текст)")
            return
        shown = adapted if len(adapted) <= 160 else adapted[:160] + "…"
        self.preview_label.configure(
            text=f"{shown}\n\nСимволов для набора: {len(adapted)}"
        )

    # -- Действия кнопок -------------------------------------------

    def _ensure_editable(self) -> bool:
        if not self._editable.get():
            messagebox.showinfo(
                "Редактирование выключено",
                "Включите флажок «Редактирование», чтобы изменять текст.",
                parent=self,
            )
            return False
        return True

    def _apply_normalize_spaces(self) -> None:
        if not self._ensure_editable():
            return
        self._set_text(normalize_spaces(self._get_text()))

    def _apply_remove_punctuation(self) -> None:
        if not self._ensure_editable():
            return
        self._set_text(remove_punctuation(self._get_text()))

    def _apply_lowercase(self) -> None:
        if not self._ensure_editable():
            return
        self._set_text(to_lowercase(self._get_text()))

    def _apply_all(self) -> None:
        if not self._ensure_editable():
            return
        self._set_text(adapt_for_typing(self._get_text()))

    def _clear_text(self) -> None:
        if not self._ensure_editable():
            return
        if not self._get_text().strip():
            return
        if messagebox.askyesno(
            "Очистить",
            "Удалить весь текст?",
            parent=self,
        ):
            self._set_text("")

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Открыть текстовый файл",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(path, encoding="cp1251") as f:
                    content = f.read()
            except OSError as exc:
                messagebox.showerror(
                    "Ошибка", f"Не удалось открыть файл:\n{exc}", parent=self,
                )
                return
        except OSError as exc:
            messagebox.showerror(
                "Ошибка", f"Не удалось открыть файл:\n{exc}", parent=self,
            )
            return
        # На время загрузки временно включаем редактирование.
        prev = self._editable.get()
        self._editable.set(True)
        self._update_editable_state()
        self._set_text(content)
        self._editable.set(prev)
        self._update_editable_state()

    def _prepare_adapted(self) -> str | None:
        """Адаптировать текст. Если пусто — предупредить и вернуть None."""
        raw = self._get_text()
        if not is_valid_practice_text(raw):
            messagebox.showwarning(
                "Пустой текст",
                "Введите текст или откройте файл перед сохранением.",
                parent=self,
            )
            return None
        return adapt_for_typing(raw)

    def _maybe_save_to_file(self, adapted: str) -> bool:
        """Спросить и при согласии сохранить адаптированный текст на диск."""
        if not messagebox.askyesno(
            "Сохранить в файл",
            "Сохранить адаптированный текст также в файл на диске?",
            parent=self,
        ):
            return True
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить адаптированный текст",
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
        )
        if not path:
            return True
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(adapted)
            return True
        except OSError as exc:
            messagebox.showerror(
                "Ошибка", f"Не удалось сохранить:\n{exc}", parent=self,
            )
            return False

    def _save(self) -> None:
        """Передать текст в тренажёр (без авто-старта)."""
        adapted = self._prepare_adapted()
        if adapted is None:
            return
        if not self._maybe_save_to_file(adapted):
            return
        self.on_saved(adapted)

    def _start(self) -> None:
        """Передать текст в тренажёр и сразу начать тренировку."""
        adapted = self._prepare_adapted()
        if adapted is None:
            return
        self.on_start(adapted)

    def _on_close(self) -> None:
        self.destroy()
