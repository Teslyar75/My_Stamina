"""Главное окно Stamina — визуальная копия ``Stamina2_XAML/MainWindow.xaml``.

Отличие от оригинала только в источнике текста: вместо случайной
последовательности символов используется текст, подготовленный
пользователем в окне-редакторе (см. :mod:`stamina.text_editor`).
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from stamina.keyboard import VirtualKeyboard
from stamina.session_storage import (
    SessionState,
    clear_session,
    save_session,
)
from stamina.theme import (
    WINDOW_BG,
    WINDOW_MIN,
    WINDOW_SIZE,
)
from stamina.widgets import SequencePanel, StatsPanel

if TYPE_CHECKING:
    from stamina.app import StaminaApp


class MainWindow(tk.Tk):
    """Окно тренировки — повторяет грид из MainWindow.xaml."""

    def __init__(self, app: StaminaApp) -> None:
        super().__init__()
        self.app = app
        self.title("MainWindow")
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN)
        self.configure(bg=WINDOW_BG)

        # Состояние сессии набора.
        self._text: str = ""
        self._index: int = 0
        self._errors: int = 0
        self._typed: int = 0
        self._started_at: float | None = None
        self._prior_elapsed: float = 0.0
        self._session_active: bool = False

        self._build_ui()
        self.bind("<Key>", self._on_key)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after_idle(self._refresh_display)

    # -- Построение UI -----------------------------------------------

    def _build_ui(self) -> None:
        self._build_menu()

        root = tk.Frame(self, bg=WINDOW_BG)
        root.pack(fill=tk.BOTH, expand=True)
        # 0: статистика (узкая полоска), 1: строка набора, 2: клавиатура.
        root.grid_rowconfigure(0, weight=0, minsize=24)
        root.grid_rowconfigure(1, weight=0, minsize=72)
        root.grid_rowconfigure(2, weight=1, minsize=260)
        root.grid_columnconfigure(0, weight=1)

        self.stats = StatsPanel(root)
        self.stats.grid(row=0, column=0, sticky="ew", padx=3, pady=(6, 0))

        self.sequence = SequencePanel(root)
        self.sequence.grid(row=1, column=0, sticky="nsew", padx=3, pady=(2, 3))

        self.keyboard = VirtualKeyboard(root)
        self.keyboard.grid(row=2, column=0, sticky="nsew", padx=3, pady=(0, 6))

        self.bind("<F5>", lambda _e: self._start_session())
        self.after(500, self._stats_tick)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Редактор текста…",
            command=self._open_editor,
            accelerator="Ctrl+E",
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Начать / перезапустить",
            command=self._start_session,
            accelerator="F5",
        )
        file_menu.add_command(label="Сбросить прогресс", command=self._reset_progress)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self._on_close)
        menubar.add_cascade(label="Файл", menu=file_menu)
        self.config(menu=menubar)
        self.bind("<Control-e>", lambda _e: self._open_editor())
        self.bind("<Control-E>", lambda _e: self._open_editor())

    # -- Связь с приложением ----------------------------------------

    def _open_editor(self) -> None:
        self.app.open_text_editor()

    def set_practice_text(self, text: str) -> None:
        """Получить адаптированный текст из редактора и сбросить сессию."""
        self.app.practice_text = text
        self._text = ""
        self._index = 0
        self._typed = 0
        self._errors = 0
        self._prior_elapsed = 0.0
        self._session_active = False
        # Новый текст — старая сохранённая сессия больше не актуальна.
        clear_session()
        self.stats.reset()
        self._refresh_display()

    # -- Отображение -------------------------------------------------

    def _refresh_display(self) -> None:
        practice = self.app.practice_text

        if self._session_active and self._text:
            self.sequence.set_progress(self._text, self._index)
            current = self._text[self._index] if self._index < len(self._text) else None
            self.keyboard.highlight(current)
            return

        # Сессия не активна — показываем превью или подсказку.
        self.keyboard.highlight(None)
        if practice.strip():
            preview = practice if len(practice) <= 80 else practice[:80] + "…"
            self.sequence.show_placeholder(preview)
        else:
            self.sequence.show_placeholder("Ctrl+E — редактор · F5 — старт")

    # -- Сессия набора ----------------------------------------------

    def start_session(self, *, resume: SessionState | None = None) -> None:
        """Начать тренировку — с нуля или продолжить ``resume``."""
        text = (resume.text if resume else self.app.practice_text).strip()
        if not text:
            messagebox.showwarning(
                "Нет текста",
                "Откройте «Файл → Редактор текста…» (Ctrl+E), "
                "подготовьте и сохраните текст.",
                parent=self,
            )
            return
        self._text = text
        self.app.practice_text = text
        if resume is not None:
            self._index = max(0, min(resume.index, len(text)))
            self._typed = resume.typed
            self._errors = resume.errors
            self._prior_elapsed = resume.elapsed
        else:
            self._index = 0
            self._typed = 0
            self._errors = 0
            self._prior_elapsed = 0.0
        self._started_at = time.perf_counter()
        self._session_active = True
        self._persist()
        self._update_stats()
        self._refresh_display()
        self.lift()
        self.focus_force()
        self.focus_set()

    # Сохраняем приватный алиас на случай старых обработчиков.
    _start_session = start_session

    # -- Пауза по Esc -----------------------------------------------

    def _pause_and_prompt(self) -> None:
        """Зафиксировать прошедшее время и спросить «продолжить или выйти»."""
        was_active = self._session_active
        if was_active and self._started_at is not None:
            self._prior_elapsed += time.perf_counter() - self._started_at
            self._started_at = None
        self._session_active = False
        self._update_stats()
        self._persist()
        # Подсветку текущей буквы убираем, чтобы было ясно «пауза».
        self.keyboard.highlight(None)

        resume = messagebox.askyesno(
            "Пауза",
            "Продолжить упражнение?\n«Нет» — закрыть программу.",
            parent=self,
        )
        if not resume:
            self.destroy()
            return
        if not was_active:
            return
        # Возобновляем: засекаем новую точку отсчёта поверх _prior_elapsed.
        self._started_at = time.perf_counter()
        self._session_active = True
        self._refresh_display()
        self.focus_set()

    # -- Статистика -------------------------------------------------

    def _current_elapsed(self) -> float:
        elapsed = self._prior_elapsed
        if self._session_active and self._started_at is not None:
            elapsed += time.perf_counter() - self._started_at
        return elapsed

    def _update_stats(self) -> None:
        elapsed = self._current_elapsed()
        # CPM считаем по правильно набранным символам (self._index),
        # а не по всем нажатиям — иначе ошибки задирали бы скорость.
        cpm = (self._index / elapsed) * 60 if elapsed > 0.1 else 0.0
        self.stats.update_stats(cpm=cpm, errors=self._errors, elapsed=elapsed)

    def _stats_tick(self) -> None:
        if self._session_active:
            self._update_stats()
        self.after(500, self._stats_tick)

    # -- Сохранение состояния --------------------------------------

    def _persist(self) -> None:
        if not self._session_active or not self._text:
            return
        elapsed = getattr(self, "_prior_elapsed", 0.0)
        if self._started_at is not None:
            elapsed += time.perf_counter() - self._started_at
        save_session(SessionState(
            text=self._text,
            index=self._index,
            typed=self._typed,
            errors=self._errors,
            elapsed=elapsed,
        ))

    def _reset_progress(self) -> None:
        if self.app.practice_text.strip():
            self._start_session()
        else:
            messagebox.showinfo(
                "Сброс",
                "Сначала сохраните текст в редакторе.",
                parent=self,
            )

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym == "Escape":
            self._pause_and_prompt()
            return

        if not self._session_active or self._index >= len(self._text):
            return

        char = event.char
        if not char or len(char) != 1:
            return

        expected = self._text[self._index]
        # Сравнение без учёта регистра — текст уже адаптирован к нижнему,
        # но пользователь может печатать с Caps Lock или Shift.
        if char.lower() == expected.lower():
            self._typed += 1
            self._index += 1
            if self._index >= len(self._text):
                self._finish_session()
            else:
                self._persist()
                self._update_stats()
                self._refresh_display()
        else:
            self._errors += 1
            self._typed += 1
            self._persist()
            self._update_stats()

    def _finish_session(self) -> None:
        self._session_active = False
        clear_session()
        elapsed = max(self._current_elapsed(), 0.001)
        cpm = (self._index / elapsed) * 60
        self.stats.update_stats(cpm=cpm, errors=self._errors, elapsed=elapsed)

        self.sequence.show_placeholder("Готово!")
        self.keyboard.highlight(None)

        accuracy = (self._index / self._typed * 100) if self._typed else 100.0
        result = messagebox.askyesnocancel(
            "Текст завершён",
            "Поздравляем! Вы завершили текст.\n\n"
            f"Правильно набрано: {self._index} симв.\n"
            f"Всего нажатий:    {self._typed}\n"
            f"Ошибки:           {self._errors}\n"
            f"Точность:         {accuracy:.1f}%\n"
            f"Скорость:         {cpm:.1f} симв./мин\n\n"
            "Да — пройти этот же текст ещё раз\n"
            "Нет — выйти из программы\n"
            "Отмена — остаться на экране результата",
            parent=self,
        )
        if result is True:
            self._start_session()
        elif result is False:
            self.destroy()

    def _on_close(self) -> None:
        if messagebox.askokcancel("Выход", "Закрыть программу?", parent=self):
            # На случай если последнее сохранение пропустили — допишем.
            self._persist()
            self.destroy()
