"""Точка сборки приложения Stamina."""

from __future__ import annotations

from tkinter import messagebox

from stamina.main_window import MainWindow
from stamina.session_storage import clear_session, load_session
from stamina.text_editor import TextEditorWindow


class StaminaApp:
    def __init__(self) -> None:
        self.practice_text: str = ""
        self._editor: TextEditorWindow | None = None
        self.main = MainWindow(self)

    # -- Редактор ---------------------------------------------------

    def open_text_editor(self) -> None:
        if self._editor is not None and self._editor.winfo_exists():
            self._editor.lift()
            self._editor.focus_force()
            return
        self._editor = TextEditorWindow(
            self.main,
            app=self,
            on_saved=self._on_text_saved,
            on_start=self._on_text_start,
        )

    def _close_editor(self) -> None:
        if self._editor is not None and self._editor.winfo_exists():
            self._editor.destroy()
        self._editor = None

    def _on_text_saved(self, adapted_text: str) -> None:
        """Кнопка «Сохранить» — запомнить текст, без авто-старта."""
        self.practice_text = adapted_text
        self.main.set_practice_text(adapted_text)
        self._close_editor()
        self.main.lift()
        self.main.focus_force()

    def _on_text_start(self, adapted_text: str) -> None:
        """Кнопка «Старт» — сохранить и сразу начать тренировку."""
        self.practice_text = adapted_text
        self.main.set_practice_text(adapted_text)
        self._close_editor()
        self.main.lift()
        self.main.focus_force()
        self.main.after(50, self.main.start_session)

    # -- Запуск приложения -----------------------------------------

    def _bootstrap(self) -> None:
        """Решает, что показать первым: продолжение, редактор или ничего."""
        saved = load_session()
        if saved is not None:
            done = saved.index
            total = len(saved.text)
            preview = saved.text[: min(60, total)]
            if total > 60:
                preview += "…"
            answer = messagebox.askyesno(
                "Продолжить упражнение?",
                "Найдена незавершённая сессия:\n\n"
                f"«{preview}»\n\n"
                f"Прогресс: {done} из {total} символов "
                f"({done / total * 100:.0f}%).\n\n"
                "Продолжить с того же места?",
                parent=self.main,
            )
            if answer:
                self.practice_text = saved.text
                self.main.set_practice_text(saved.text)
                # set_practice_text вызвал clear_session — это нормально,
                # сразу же стартуем заново с правильным индексом.
                self.main.start_session(resume=saved)
                return
            clear_session()

        if not self.practice_text.strip():
            self.open_text_editor()

    def run(self) -> None:
        self.main.after(120, self._bootstrap)
        self.main.mainloop()


def run_app() -> None:
    StaminaApp().run()
