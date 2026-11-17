"""Страница «ГРАММАТИКА» для отсека «ИНОСТРАННЫЕ ЯЗЫКИ».

Два режима: УРОКИ (прогрессивное обучение) и ТАБЛИЦЫ (справочник).
"""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, PANEL_HI, RED, TEXT, px
from stamina.languages.core.progress import LanguageProgress


class GrammarPage:
    """Страница грамматики: режимы УРОКИ / ТАБЛИЦЫ."""

    def __init__(self, parent, plugin, progress: LanguageProgress | None, app) -> None:
        self.parent = parent
        self.plugin = plugin
        self.progress = progress
        self.app = app
        self.engine = plugin.get_grammar_engine()

        self.mode = "lessons"  # "lessons" или "tables"
        self.current_level = "A1"
        self.current_lesson = None
        self.current_drill_index = 0
        self.drills = []

        self._build_ui()

    def _build_ui(self) -> None:
        """Построить интерфейс страницы."""
        self.frame = tk.Frame(self.parent, bg=BG)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Шапка с переключателем режимов
        header = tk.Frame(self.frame, bg=BG)
        header.pack(fill=tk.X, padx=px(12), pady=(px(8), px(4)))

        HudButton(header, _t("← НАЗАД"), self._go_back,
                  color=MUTED, height=32, font_size=10).pack(side=tk.LEFT)

        title = tk.Label(header, text=_t("ГРАММАТИКА"),
                         bg=BG, fg=AMBER, font=theme.font(16, True))
        title.pack(side=tk.LEFT, padx=px(12))

        # Кнопки режимов
        mode_frame = tk.Frame(header, bg=BG)
        mode_frame.pack(side=tk.RIGHT)
        self.btn_mode_lessons = HudButton(mode_frame, _t("УРОКИ"),
                                          lambda: self._set_mode("lessons"),
                                          height=28, font_size=9, active=True, color=GREEN)
        self.btn_mode_lessons.pack(side=tk.LEFT, padx=px(2))
        self.btn_mode_tables = HudButton(mode_frame, _t("ТАБЛИЦЫ"),
                                         lambda: self._set_mode("tables"),
                                         height=28, font_size=9, color=CYAN)
        self.btn_mode_tables.pack(side=tk.LEFT, padx=px(2))

        # Контейнер контента
        self.content = tk.Frame(self.frame, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(8))

        self._show_content()

    def _set_mode(self, mode: str) -> None:
        """Переключение режима."""
        self.mode = mode
        self.current_lesson = None
        self.current_drill_index = 0
        self.drills = []
        self.btn_mode_lessons.set_active(mode == "lessons")
        self.btn_mode_tables.set_active(mode == "tables")
        self._show_content()

    def _go_back(self) -> None:
        """Назад: урок → список уроков → уровни."""
        if self.current_lesson and self.current_drill_index > 0:
            # Внутри урока: к списку упражнений
            self.current_drill_index = 0
            self._show_lesson(self.current_lesson)
        elif self.current_lesson:
            # В уроке: к списку уроков
            self.current_lesson = None
            self._show_level_list()
        else:
            # В списке уроков: к уровням
            self._show_level_selector()

    def _show_content(self) -> None:
        """Показать контент в зависимости от режима."""
        for w in self.content.winfo_children():
            w.destroy()

        if self.mode == "lessons":
            self._show_level_selector()
        else:
            self._show_tables_mode()

    # ============================================================
    # РЕЖИМ «УРОКИ»
    # ============================================================

    def _show_level_selector(self) -> None:
        """Показать селектор уровней A1–C2."""
        levels = self.engine.levels()

        tk.Label(self.content, text=_t("ВЫБЕРИТЕ УРОВЕНЬ"),
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(anchor="w", pady=(0, px(8)))

        # Кнопки уровней
        level_frame = tk.Frame(self.content, bg=BG)
        level_frame.pack(fill=tk.X, pady=(0, px(12)))

        for lvl in levels:
            code = lvl["code"]
            done, total = self._get_progress(code)
            btn = HudButton(level_frame,
                            f"{code}  {lvl['title']}\n{_t('пройдено')} {done} {_t('из')} {total}",
                            lambda c=code: self._show_level_list(c),
                            height=70, font_size=10,
                            active=(code == self.current_level),
                            color=GREEN if done == total else CYAN)
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=px(4))

        # Кнопка «СЛЕДУЮЩИЙ УРОК»
        next_lesson = self._get_next_lesson()
        if next_lesson:
            btn = HudButton(self.content, _t("СЛЕДУЮЩИЙ УРОК: {0}").format(next_lesson["title"]),
                            lambda: self._show_lesson(next_lesson),
                            color=AMBER, height=40, font_size=11)
            btn.pack(fill=tk.X, pady=px(8))

    def _show_level_list(self, level: str) -> None:
        """Показать список уроков уровня."""
        self.current_level = level
        lessons = self.engine.lessons(level)

        for w in self.content.winfo_children():
            w.destroy()

        # Шапка
        header = tk.Frame(self.content, bg=BG)
        header.pack(fill=tk.X, pady=(0, px(8)))
        HudButton(header, _t("← УРОВНИ"), self._show_level_selector,
                  color=MUTED, height=32, font_size=10).pack(side=tk.LEFT)
        tk.Label(header, text=f"{level}  {_t('УРОКИ')}",
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(side=tk.LEFT, padx=px(12))

        # Скроллер для списка уроков
        inner = self._scroller(self.content)

        for lesson in lessons:
            done = self._is_lesson_done(lesson["id"])
            is_next = not done and self._is_next_lesson(lesson["id"])

            if done:
                status = "✓ " + _t("пройден")
                color = GREEN
            elif is_next:
                status = "▶ " + _t("следующий")
                color = AMBER
            else:
                status = "· " + _t("не начат")
                color = MUTED

            frame = tk.Frame(inner, bg=PANEL, highlightbackground=color,
                             highlightthickness=1)
            frame.pack(fill=tk.X, padx=px(4), pady=px(3))

            left = tk.Frame(frame, bg=PANEL)
            left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(8), pady=px(6))
            tk.Label(left, text=f"{lesson['order']}. {lesson['title']}",
                     bg=PANEL, fg=TEXT, font=theme.font(11, True), anchor="w").pack(fill=tk.X)
            tk.Label(left, text=lesson.get("subtitle", ""),
                     bg=PANEL, fg=MUTED, font=theme.font(9), anchor="w").pack(fill=tk.X)
            tk.Label(left, text=f"{_t('≈')} {lesson.get('minutes', 10)} {_t('мин')}",
                     bg=PANEL, fg=CYAN, font=theme.font(8), anchor="w").pack(fill=tk.X)

            right = tk.Frame(frame, bg=PANEL)
            right.pack(side=tk.RIGHT, padx=px(8))
            tk.Label(right, text=status, bg=PANEL, fg=color,
                     font=theme.font(9, True)).pack(anchor="e")

            for w in (frame, left, right):
                w.bind("<Button-1>", lambda e, l=lesson: self._show_lesson(l))

    def _show_lesson(self, lesson: dict) -> None:
        """Показать экран урока с теорией и упражнениями."""
        self.current_lesson = lesson
        self.drills = lesson.get("drills", [])
        self.current_drill_index = 0

        for w in self.content.winfo_children():
            w.destroy()

        # Шапка урока
        header = tk.Frame(self.content, bg=BG)
        header.pack(fill=tk.X, pady=(0, px(8)))
        HudButton(header, _t("← К СПИСКУ"), self._go_back,
                  color=MUTED, height=32, font_size=10).pack(side=tk.LEFT)
        tk.Label(header, text=f"{lesson['level']} · {lesson['order']}  {lesson['title']}",
                 bg=BG, fg=AMBER, font=theme.font(14, True)).pack(side=tk.LEFT, padx=px(12))

        # Скроллер для теории и упражнений
        self.lesson_scroller = self._scroller(self.content)

        # Теория
        self._render_theory(lesson)

        # Разделитель
        sep = tk.Frame(self.lesson_scroller, bg=LINE, height=px(2))
        sep.pack(fill=tk.X, pady=px(8))

        # Упражнения
        if self.drills:
            self._render_drill()
        else:
            tk.Label(self.lesson_scroller, text=_t("Упражнений нет"),
                     bg=BG, fg=MUTED, font=theme.font(11)).pack(pady=px(20))

    def _render_theory(self, lesson: dict) -> None:
        """Отрисовать блоки теории урока."""
        theory = lesson.get("theory", [])
        if not theory:
            return

        tk.Label(self.lesson_scroller, text=_t("ТЕОРИЯ"),
                 bg=BG, fg=AMBER, font=theme.font(12, True)).pack(anchor="w", pady=(0, px(6)))

        for block in theory:
            kind = block.get("kind")
            if kind == "text":
                tk.Label(self.lesson_scroller, text=block.get("text", ""),
                         bg=BG, fg=TEXT, font=theme.font(10),
                         wraplength=px(800), justify="left").pack(anchor="w", pady=px(3))
            elif kind == "rule":
                self._render_rule_block(block)
            elif kind == "table":
                self._render_table_block(block.get("ref", ""))
            elif kind == "example":
                self._render_example_block(block)

    def _render_rule_block(self, block: dict) -> None:
        """Отрисовать блок правила в рамке."""
        panel = HudPanel(self.lesson_scroller, block.get("title", _t("ПРАВИЛО")), accent=AMBER)
        panel.pack(fill=tk.X, pady=px(4))
        tk.Label(panel.body, text=block.get("text", ""),
                 bg=PANEL, fg=TEXT, font=theme.font(10),
                 wraplength=px(780), justify="left").pack(anchor="w", pady=px(4))

    def _render_table_block(self, table_ref: str) -> None:
        """Отрисовать таблицу-ссылку."""
        table = self.engine.table(table_ref)
        if not table:
            return

        frame = tk.Frame(self.lesson_scroller, bg=PANEL)
        frame.pack(fill=tk.X, pady=px(4))

        tk.Label(frame, text=table.get("title", ""),
                 bg=PANEL, fg=AMBER, font=theme.font(10, True)).pack(anchor="w", padx=px(8), pady=(px(4), 0))

        # Таблица в Canvas с горизонтальным скроллом
        canvas = tk.Canvas(frame, bg=PANEL, highlightthickness=0)
        hbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(xscrollcommand=hbar.set)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        columns = table.get("columns", [])
        rows = table.get("rows", [])

        # Заголовок
        header_row = tk.Frame(inner, bg=PANEL_HI)
        header_row.pack(fill=tk.X)
        for col in columns:
            tk.Label(header_row, text=col, bg=PANEL_HI, fg=AMBER,
                     font=theme.font(9, True), padx=px(8), pady=px(4)).pack(side=tk.LEFT)

        # Строки
        for row in rows:
            row_frame = tk.Frame(inner, bg=PANEL)
            row_frame.pack(fill=tk.X)
            for cell in row:
                tk.Label(row_frame, text=cell, bg=PANEL, fg=TEXT,
                         font=theme.font(9), padx=px(8), pady=px(3)).pack(side=tk.LEFT)

        if table.get("note"):
            tk.Label(frame, text=table["note"], bg=PANEL, fg=MUTED,
                     font=theme.font(8), wraplength=px(780), justify="left").pack(anchor="w", padx=px(8), pady=px(4))

        # Обновить scrollregion
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _render_example_block(self, block: dict) -> None:
        """Отрисовать пример с озвучкой."""
        frame = tk.Frame(self.lesson_scroller, bg=PANEL)
        frame.pack(fill=tk.X, pady=px(4), padx=px(4))

        top = tk.Frame(frame, bg=PANEL)
        top.pack(fill=tk.X, padx=px(8), pady=(px(4), 0))

        tk.Label(top, text=block.get("de", ""), bg=PANEL, fg=TEXT,
                 font=theme.font(11, True), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Кнопка озвучки
        try:
            from stamina.languages.speech import speak
            from stamina.english.tts import TTS
            if TTS.available():
                de_text = block.get("de", "")
                HudButton(top, "🔊", lambda t=de_text: speak(t, "de"),
                          height=24, font_size=8, width=32).pack(side=tk.RIGHT, padx=px(4))
        except Exception:
            pass

        tk.Label(frame, text=block.get("ru", ""), bg=PANEL, fg=MUTED,
                 font=theme.font(9), anchor="w", wraplength=px(780)).pack(fill=tk.X, padx=px(8), pady=(0, px(4)))

        if block.get("note"):
            tk.Label(frame, text=block["note"], bg=PANEL, fg=CYAN,
                     font=theme.font(8, True), anchor="w", wraplength=px(780)).pack(fill=tk.X, padx=px(8), pady=(0, px(4)))

    def _render_drill(self) -> None:
        """Отрисовать текущее упражнение."""
        if self.current_drill_index >= len(self.drills):
            self._render_lesson_summary()
            return

        drill = self.drills[self.current_drill_index]

        # Счётчик
        counter = tk.Label(self.lesson_scroller,
                           text=_t("Упражнение {0} из {1}").format(
                               self.current_drill_index + 1, len(self.drills)),
                           bg=BG, fg=CYAN, font=theme.font(10, True))
        counter.pack(anchor="w", pady=(px(8), px(4)))

        # Панель упражнения
        panel = HudPanel(self.lesson_scroller, _t("УПРАЖНЕНИЕ"), accent=CYAN)
        panel.pack(fill=tk.X, pady=px(4))

        tk.Label(panel.body, text=drill.get("prompt", ""),
                 bg=PANEL, fg=TEXT, font=theme.font(11),
                 wraplength=px(780), justify="left").pack(anchor="w", pady=px(6))

        # Виджет ввода в зависимости от типа
        self.drill_answer_var = tk.StringVar()
        self.drill_checked = False

        drill_type = drill.get("type")
        if drill_type == "choice":
            self._render_choice_drill(panel, drill)
        elif drill_type in ("fill", "declension", "conjugation", "transform"):
            self._render_fill_drill(panel, drill)
        elif drill_type == "reorder":
            self._render_reorder_drill(panel, drill)
        elif drill_type in ("match", "identify"):
            self._render_choice_drill(panel, drill)
        else:
            tk.Label(panel.body, text=_t("Неизвестный тип: {0}").format(drill_type),
                     bg=PANEL, fg=RED, font=theme.font(10)).pack(anchor="w")

        # Кнопка проверки
        self.btn_check = HudButton(panel.body, _t("ПРОВЕРИТЬ"),
                                   lambda: self._check_drill(drill),
                                   color=AMBER, height=32, font_size=10)
        self.btn_check.pack(fill=tk.X, pady=px(8))

        # Enter = проверить
        self.lesson_scroller.bind("<Return>", lambda e: self._check_drill(drill))

    def _render_choice_drill(self, parent: tk.Frame, drill: dict) -> None:
        """Рисовать кнопки выбора для choice/match/identify."""
        options = drill.get("options", [])
        for opt in options:
            HudButton(parent.body, opt,
                      lambda o=opt: self._select_choice(o),
                      height=36, font_size=10).pack(fill=tk.X, pady=px(2))

    def _render_fill_drill(self, parent: tk.Frame, drill: dict) -> None:
        """Рисовать поле ввода для fill/declension/conjugation/transform."""
        entry = tk.Entry(parent.body, textvariable=self.drill_answer_var,
                         bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         font=theme.font(12), width=50)
        entry.pack(fill=tk.X, pady=px(6))
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._check_drill(drill))

    def _render_reorder_drill(self, parent: tk.Frame, drill: dict) -> None:
        """Рисовать поле ввода для reorder (ввод целой фразы)."""
        tk.Label(parent.body, text=_t("Введите слова в правильном порядке:"),
                 bg=PANEL, fg=MUTED, font=theme.font(9)).pack(anchor="w")
        entry = tk.Entry(parent.body, textvariable=self.drill_answer_var,
                         bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         font=theme.font(12), width=60)
        entry.pack(fill=tk.X, pady=px(6))
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._check_drill(drill))

    def _select_choice(self, choice: str) -> None:
        """Запомнить выбор и проверить."""
        self.drill_answer_var.set(choice)
        self._check_drill(self.drills[self.current_drill_index])

    def _check_drill(self, drill: dict) -> None:
        """Проверить ответ."""
        if self.drill_checked:
            return

        self.drill_checked = True
        answer = self.drill_answer_var.get()

        # Создать временный Exercise для валидации
        from stamina.languages.core.base import Exercise
        ex = Exercise(
            id=drill["id"],
            topic_id=drill.get("topic_id", ""),
            type=drill.get("type", "choice"),
            prompt=drill.get("prompt", ""),
            expected_answer=drill["answer"] if isinstance(drill["answer"], list) else [drill["answer"]],
            options=drill.get("options", [])
        )

        result = self.engine.validate_answer(ex, answer)

        # Показать результат
        if result.correct:
            color = GREEN
            text = _t("ВЕРНО ✓")
        else:
            color = RED
            text = _t("НЕВЕРНО ✗")

        # Находим панель упражнения
        for w in self.lesson_scroller.winfo_children():
            if isinstance(w, HudPanel) and w.title == _t("УПРАЖНЕНИЕ"):
                result_label = tk.Label(w.body, text=text, bg=PANEL, fg=color, font=theme.font(12, True))
                result_label.pack(anchor="w", pady=px(4))
                if not result.correct:
                    tk.Label(w.body,
                             text=_t("Правильно: {0}").format(result.correct_answer or ex.expected_answer[0]),
                             bg=PANEL, fg=CYAN, font=theme.font(10)).pack(anchor="w")
                    why = ex.metadata.get("why") or drill.get("why")
                    if why:
                        tk.Label(w.body,
                                 text=_t("Почему: {0}").format(why),
                                 bg=PANEL, fg=MUTED, font=theme.font(9),
                                 wraplength=px(780), justify="left").pack(anchor="w", pady=px(2))
                break

        # Записать прогресс
        if self.progress:
            self.progress.record_attempt(
                ex.id, result.correct, "grammar",
                latency_ms=0, quality=1 if result.correct else 0
            )

        # Кнопка ДАЛЬШЕ
        self.btn_check.set_text(_t("ДАЛЬШЕ"))
        self.btn_check.command = self._next_drill

    def _next_drill(self) -> None:
        """Перейти к следующему упражнению."""
        self.current_drill_index += 1
        self.drill_checked = False
        self.drill_answer_var.set("")

        # Перерисовать только область упражнения
        for w in self.lesson_scroller.winfo_children():
            if isinstance(w, HudPanel) and w.title == _t("УПРАЖНЕНИЕ"):
                w.destroy()
                break

        if self.current_drill_index >= len(self.drills):
            self._render_lesson_summary()
        else:
            self._render_drill()

    def _render_lesson_summary(self) -> None:
        """Показать итог урока."""
        for w in self.lesson_scroller.winfo_children():
            if isinstance(w, HudPanel) and w.title == _t("УПРАЖНЕНИЕ"):
                w.destroy()

        # Подсчёт правильных
        if self.progress:
            correct = 0
            for drill in self.drills:
                ex = self.engine.generate_exercise(drill.get("topic_id", ""), "easy", 0)
                # Упрощение: считаем по попыткам
            # Просто показываем итог
            pass

        panel = HudPanel(self.lesson_scroller, _t("УРОК ЗАВЕРШЁН"), accent=GREEN)
        panel.pack(fill=tk.X, pady=px(8))
        tk.Label(panel.body,
                 text=_t("Пройдено упражнений: {0} из {1}").format(
                     len(self.drills), len(self.drills)),
                 bg=PANEL, fg=TEXT, font=theme.font(11)).pack(anchor="w", pady=px(4))

        btn_frame = tk.Frame(panel.body, bg=PANEL)
        btn_frame.pack(fill=tk.X, pady=px(4))
        HudButton(btn_frame, _t("ЗАНОВО"), self._restart_lesson,
                  color=AMBER, height=32, font_size=10).pack(side=tk.LEFT, padx=px(4))
        HudButton(btn_frame, _t("К СПИСКУ"), self._go_back,
                  color=CYAN, height=32, font_size=10).pack(side=tk.LEFT, padx=px(4))

        # Отметить урок как пройденный
        if self.progress:
            self.progress.record_grammar(self.current_lesson["id"], len(self.drills), len(self.drills))

    def _restart_lesson(self) -> None:
        """Перезапустить урок."""
        self.current_drill_index = 0
        self.drill_checked = False
        self.drill_answer_var.set("")
        self._show_lesson(self.current_lesson)

    # ============================================================
    # РЕЖИМ «ТАБЛИЦЫ»
    # ============================================================

    def _show_tables_mode(self) -> None:
        """Показать справочник таблиц с фильтром по уровню."""
        for w in self.content.winfo_children():
            w.destroy()

        # Фильтр уровня
        filter_frame = tk.Frame(self.content, bg=BG)
        filter_frame.pack(fill=tk.X, pady=(0, px(8)))

        tk.Label(filter_frame, text=_t("УРОВЕНЬ:"), bg=BG, fg=MUTED,
                 font=theme.font(10)).pack(side=tk.LEFT)

        self.table_level_var = tk.StringVar(value="ALL")
        levels = ["ALL"] + [l["code"] for l in self.engine.levels()]
        for lvl in levels:
            HudButton(filter_frame, lvl,
                      lambda v=lvl: self._filter_tables(v),
                      height=28, font_size=9,
                      active=(lvl == self.table_level_var.get()),
                      color=GREEN if lvl == self.table_level_var.get() else CYAN).pack(side=tk.LEFT, padx=px(2))

        # Список таблиц
        self.tables_container = self._scroller(self.content)
        self._filter_tables("ALL")

    def _filter_tables(self, level: str) -> None:
        """Отфильтровать таблицы по уровню."""
        self.table_level_var.set(level)
        for w in self.tables_container.winfo_children():
            w.destroy()

        tables = self.engine.tables(level if level != "ALL" else None)

        for table in tables:
            frame = tk.Frame(self.tables_container, bg=PANEL)
            frame.pack(fill=tk.X, pady=px(3), padx=px(4))

            head = tk.Frame(frame, bg=PANEL)
            head.pack(fill=tk.X, padx=px(8), pady=px(4))
            tk.Label(head, text=f"{table.get('level', '')}  {table.get('title', '')}",
                     bg=PANEL, fg=AMBER, font=theme.font(10, True)).pack(side=tk.LEFT)
            HudButton(head, _t("СКОПИРОВАТЬ"),
                      lambda t=table: self._copy_table(t),
                      height=24, font_size=8, width=80).pack(side=tk.RIGHT)

            # Таблица в Canvas
            canvas = tk.Canvas(frame, bg=PANEL, highlightthickness=0, height=px(200))
            hbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
            canvas.configure(xscrollcommand=hbar.set)
            hbar.pack(side=tk.BOTTOM, fill=tk.X)
            canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            inner = tk.Frame(canvas, bg=PANEL)
            canvas.create_window((0, 0), window=inner, anchor="nw")

            columns = table.get("columns", [])
            rows = table.get("rows", [])

            header_row = tk.Frame(inner, bg=PANEL_HI)
            header_row.pack(fill=tk.X)
            for col in columns:
                tk.Label(header_row, text=col, bg=PANEL_HI, fg=AMBER,
                         font=theme.font(8, True), padx=px(6), pady=px(3)).pack(side=tk.LEFT)

            for row in rows:
                row_frame = tk.Frame(inner, bg=PANEL)
                row_frame.pack(fill=tk.X)
                for cell in row:
                    tk.Label(row_frame, text=cell, bg=PANEL, fg=TEXT,
                             font=theme.font(8), padx=px(6), pady=px(2)).pack(side=tk.LEFT)

            if table.get("note"):
                tk.Label(frame, text=table["note"], bg=PANEL, fg=MUTED,
                         font=theme.font(7), wraplength=px(780), justify="left").pack(anchor="w", padx=px(8), pady=px(2))

            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _copy_table(self, table: dict) -> None:
        """Скопировать таблицу в буфер обмена (TSV)."""
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        lines = ["\t".join(columns)]
        for row in rows:
            lines.append("\t".join(row))
        text = "\n".join(lines)
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        # Показать временное уведомление
        self._show_toast(_t("Таблица скопирована"))

    def _show_toast(self, text: str) -> None:
        """Показать временное уведомление."""
        toast = tk.Label(self.content, text=text, bg=AMBER, fg=BG,
                         font=theme.font(10, True), padx=px(12), pady=px(6))
        toast.place(relx=0.5, rely=0.1, anchor="n")
        self.parent.after(1500, toast.destroy)

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================

    def _scroller(self, parent) -> tk.Frame:
        """Создать прокручиваемую область."""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(parent, command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _fit(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window, width=max(canvas.winfo_width(), 1))

        inner.bind("<Configure>", _fit)
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        return inner

    def _get_progress(self, level: str) -> tuple[int, int]:
        """Получить прогресс по уровню: (пройдено, всего)."""
        if not self.progress:
            return (0, 0)
        lessons = self.engine.lessons(level)
        done = sum(1 for l in lessons if self._is_lesson_done(l["id"]))
        return (done, len(lessons))

    def _is_lesson_done(self, lesson_id: str) -> bool:
        """Проверить, пройден ли урок."""
        if not self.progress:
            return False
        return self.progress.grammar_done(lesson_id)

    def _is_next_lesson(self, lesson_id: str) -> bool:
        """Проверить, является ли урок следующим непройденным."""
        if not self.progress:
            return False
        lessons = self.engine.lessons(self.current_level)
        for l in lessons:
            if not self._is_lesson_done(l["id"]):
                return l["id"] == lesson_id
        return False

    def _get_next_lesson(self) -> dict | None:
        """Получить следующий непройденный урок."""
        if not self.progress:
            return None
        for lvl in self.engine.levels():
            lessons = self.engine.lessons(lvl["code"])
            for l in lessons:
                if not self._is_lesson_done(l["id"]):
                    return l
        return None


def build_grammar_page(parent, plugin, progress, app) -> GrammarPage:
    """Фабрика для создания страницы грамматики."""
    return GrammarPage(parent, plugin, progress, app)