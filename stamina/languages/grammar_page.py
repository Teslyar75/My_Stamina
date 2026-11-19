"""Страница «ГРАММАТИКА» для отсека «ИНОСТРАННЫЕ ЯЗЫКИ».

Два режима: УРОКИ (цель → мостик RU/UA → DE → теория по шагам → упражнения → итог)
и ТАБЛИЦЫ (справочник: список названий, одна таблица на экран).

Материал грузится порциями: манифест уровней читается из courses.json, файл уровня —
только при входе в уровень, таблицы — только в режиме ТАБЛИЦЫ; длинные списки
рисуются порциями по CHUNK элементов через after(), поэтому окно не замирает.
"""
from __future__ import annotations

import random
import re
import tkinter as tk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.i18n import t as _t
from stamina.languages.core.progress import GRAMMAR_PASS, LanguageProgress
from stamina.theme import AMBER, BG, CYAN, GREEN, LINE, MUTED, PANEL, PANEL_HI, RED, TEXT, px

#: Порог «урок засчитан» — тот же, что в LanguageProgress.record_grammar.
PASS_SCORE = GRAMMAR_PASS
#: Сколько карточек списка рисуем за один шаг after(): окно успевает перерисоваться.
CHUNK = 6

#: Типы упражнений, где ответ выбирают из готовых вариантов.
CHOICE_TYPES = {"choice", "match", "identify"}
#: Типы, где нужен ввод слова или предложения.
FILL_TYPES = {"fill", "declension", "conjugation"}
#: Типы, где предложение собирают из слов.
REORDER_TYPES = {"reorder"}

INSTRUCTION_CHOICE = "Выберите один правильный вариант."
INSTRUCTION_FILL = "Впишите пропущенное слово в нужной форме."
INSTRUCTION_TRANSFORM = "Перепишите предложение по заданию."
INSTRUCTION_REORDER = "Составьте предложение: нажимайте на слова по порядку."
INSTRUCTION_TRANSLATE = "Переведите на немецкий."
INSTRUCTION_TRANSLATE_WRITE = "Переведите на немецкий и впишите ответ."

#: Сколько упражнений в самопроверке «ПРОВЕРЬ СЕБЯ» (как «Teste dich!» в Grammatik aktiv).
SELF_CHECK_SIZE = 12
#: Кириллица в задании — значит, переводим с русского/украинского на немецкий.
_CYRILLIC = re.compile(r"[а-яА-ЯёЁіІїЇєЄґҐ]")


def _normalize_sentence(text: str) -> str:
    """Убрать разницу в пробелах вокруг знаков: «regnet , bleibe» → «regnet, bleibe»."""
    text = re.sub(r"\s+([,.;:!?])", r"\1", text.strip())
    return re.sub(r"\s+", " ", text)


def _lower(text: str) -> str:
    """Нижний регистр с раскрытыми умлаутами: ä → ae, ß → ss (как пишут на клавиатуре)."""
    return (text or "").lower().replace("ä", "ae").replace("ö", "oe") \
        .replace("ü", "ue").replace("ß", "ss")


def _canon(text: str) -> str:
    """Ответ без крайних знаков и лишних пробелов — для «впишите слово»."""
    return re.sub(r"\s+", " ", _lower(text).strip()).strip(" .,;:!?…—–-")


def _canon_plain(text: str) -> str:
    """Ответ без крайних знаков, но с точным написанием — для выбора вариантов.

    В вариантах «Straße» и «Strasse», «zu Hause» и «zu hause» — разные ответы,
    поэтому здесь не раскрываем умлауты и не понижаем регистр.
    """
    return re.sub(r"\s+", " ", (text or "").strip()).strip(" .,;:!?…—–-")


def _words(text: str) -> list[str]:
    """Слова без знаков препинания — порядок слов важнее запятых."""
    return re.findall(r"[^\W_]+", _lower(text))


def _answer_matches(kind: str, value: str, expected: list[str]) -> bool:
    """Сверить ответ по правилам типа упражнения.

    • «соберите предложение» и «перепишите» — порядок слов, знаки не требуем;
    • выбор из вариантов — точное написание, иначе «Strasse» сошло бы за «Straße»;
    • вписанное слово — умлаут можно набрать как ae/oe/ue, ß как ss.
    """
    if kind in REORDER_TYPES or kind == "transform":
        got = _words(value)
        return bool(got) and any(got == _words(item) for item in expected)
    if kind in CHOICE_TYPES:
        return any(_canon_plain(value) == _canon_plain(item) for item in expected)
    return any(_canon(value) == _canon(item) for item in expected)


def _prompt_words(prompt: str) -> list[str]:
    """Слова из подсказки упражнения: Wörter ordnen: 'ist / mein / Bruder'."""
    match = re.search(r"'([^']+)'", prompt or "")
    if not match:
        return []
    return [w.strip() for w in match.group(1).split("/") if w.strip()]


def _word_bank(drill: dict) -> list[str]:
    """Слова для сборки предложения.

    Если подсказка перечисляет те же слова, что и ответ, берём её (там слова в
    исходной форме и с маленькой буквы). Если списки расходятся (например,
    'Hand / Schuh / der' → 'der Handschuh'), собираем банк из ответа — иначе
    упражнение нерешаемо.
    """
    answer = drill.get("answer") or [""]
    expected = answer[0] if isinstance(answer, (list, tuple)) else str(answer)
    words = _prompt_words(drill.get("prompt", ""))
    expected_tokens = [w for w in re.split(r"\s+", expected.strip()) if w]

    def key(token: str) -> str:
        return token.strip(".,;:!?").lower()

    if words and sorted(map(key, words)) == sorted(map(key, expected_tokens)):
        return words
    return [w for w in expected_tokens if w]


def _shuffled(words: list[str], seed_text: str) -> list[str]:
    """Детерминированное перемешивание: один и тот же урок даёт один и тот же банк."""
    rng = random.Random(seed_text)
    out = list(words)
    rng.shuffle(out)
    return out


class GrammarPage:
    """Страница грамматики: УРОКИ / ТАБЛИЦЫ."""

    def __init__(self, parent, plugin, progress: LanguageProgress | None, app,
                 on_back=None) -> None:
        self.parent = parent
        self.plugin = plugin
        self.progress = progress
        self.app = app
        self.on_back = on_back
        self.engine = plugin.get_grammar_engine()

        self.mode = "lessons"          # "lessons" | "tables"
        self.stage = "levels"
        self.current_level = "A1"      # совместимость со старым API страницы
        self.level = None
        self.level_lessons: list[dict] = []
        self.next_lesson_id: str | None = None

        self.lesson: dict | None = None
        self.theory: list[dict] = []
        self.theory_index = 0
        self.all_drills: list[dict] = []
        self.drills: list[dict] = []
        self.drill_index = 0
        self.answers: dict[str, bool] = {}
        self.checked = False
        self.last_ok = False
        self.run_full = True
        self.recorded = False

        self.answer_text = ""
        self.selected = None
        self.bank: list[str] = []
        self.picked: list[int] = []
        self.hint_shown = False
        self.rule_shown = False

        self.table_level = "ALL"
        self.table_id = None
        self.tables_container = None

        self._wrapped: list[tuple[tk.Label, int, bool]] = []
        self._fonts: dict[tuple, object] = {}
        self._pending: list = []
        self._pump_job = None
        self._last_wrap = 0

        self.drill_answer_var = tk.StringVar()

        self._build_ui()

    # ============================================================
    # Каркас
    # ============================================================

    def _build_ui(self) -> None:
        self.frame = tk.Frame(self.parent, bg=BG)
        self.frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(self.frame, bg=BG)
        header.pack(fill=tk.X, padx=px(12), pady=(px(8), px(4)))

        self.back_btn = HudButton(header, _t("← НАЗАД"), self._go_back,
                                  color=MUTED, height=30, font_size=9)
        self.title_lbl = tk.Label(header, text=_t("ГРАММАТИКА"), bg=BG, fg=AMBER,
                                  font=theme.font(15, True))
        self.title_lbl.pack(side=tk.LEFT, padx=px(10))
        self.crumb = tk.Label(header, text="", bg=BG, fg=MUTED, font=theme.font(9))
        self.crumb.pack(side=tk.LEFT)

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

        self.content = tk.Frame(self.frame, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(6))
        self.content.bind("<Configure>", self._on_content_configure)

        self._render()

    def _render(self) -> None:
        """Перерисовать текущий экран с нуля."""
        self._clear()
        screen = {
            "levels": self._screen_levels,
            "lessons": self._screen_lessons,
            "intro": self._screen_intro,
            "theory": self._screen_theory,
            "practice": self._screen_practice,
            "summary": self._screen_summary,
            "tables": self._screen_tables,
            "table": self._screen_table,
        }.get(self.stage)
        if screen is not None:
            screen()

    def _goto(self, stage: str) -> None:
        self.stage = stage
        self._render()

    def _clear(self) -> None:
        self._cancel_pending()
        self._wrapped.clear()
        for w in self.content.winfo_children():
            w.destroy()

    def destroy(self) -> None:
        """Снять отложенные перерисовки, чтобы after() не бился в мёртвые виджеты."""
        self._cancel_pending()
        try:
            self.frame.destroy()
        except tk.TclError:
            pass

    # ---------- порционная отрисовка ----------

    def _queue(self, builders: list) -> None:
        """Поставить построители карточек в очередь: рисуем по CHUNK за шаг after()."""
        self._pending.extend(builders)
        self._pump()

    def _pump(self) -> None:
        if self._pump_job is not None or not self._pending:
            return

        def step() -> None:
            self._pump_job = None
            try:
                for _ in range(CHUNK):
                    if not self._pending:
                        break
                    self._pending.pop(0)()
            except tk.TclError:
                self._pending.clear()
                return
            if self._pending:
                try:
                    self._pump_job = self.frame.after(1, step)
                except tk.TclError:
                    self._pump_job = None

        try:
            self._pump_job = self.frame.after(1, step)
        except tk.TclError:
            self._pump_job = None

    def _cancel_timer(self) -> None:
        if self._pump_job is not None:
            try:
                self.frame.after_cancel(self._pump_job)
            except tk.TclError:
                pass
            self._pump_job = None

    def _cancel_pending(self) -> None:
        self._cancel_timer()
        self._pending.clear()

    def _flush_pending(self) -> None:
        """Нарисовать очередь сразу — для тестов и для «дальше» после прокрутки."""
        self._cancel_timer()
        while self._pending:
            builder = self._pending.pop(0)
            try:
                builder()
            except tk.TclError:
                break

    # ---------- виджеты ----------

    def _wrap_px(self) -> int:
        width = self.content.winfo_width()
        if width <= 1:
            width = self.frame.winfo_width()
        if width <= 1:
            width = px(760)
        return max(px(220), width - px(56))

    def _measure(self, text: str, size: int = 9, bold: bool = False) -> int:
        """Ширина строки в пикселях — один Font на пару (размер, жирность), с кэшем."""
        key = theme.font(size, bold)
        font = self._fonts.get(key)
        if font is None:
            import tkinter.font as tkfont

            family, scaled, *style = key
            font = tkfont.Font(root=self.frame, family=family, size=scaled,
                               weight="bold" if style else "normal")
            self._fonts[key] = font
        return font.measure(text or "")

    def _needs_wrap(self, text: str, width: int, size: int = 9, bold: bool = False) -> bool:
        """Нужен ли перенос: строка шире доступного места."""
        return self._measure(text, size, bold) > max(width, 1)

    def _on_content_configure(self, _event=None) -> None:
        wrap = self._wrap_px()
        if abs(wrap - self._last_wrap) < px(8):
            return
        self._last_wrap = wrap
        alive = []
        for label, size, bold, inset in self._wrapped:
            width = max(wrap - inset, px(80))
            try:
                needed = self._needs_wrap(label.cget("text"), width, size, bold)
                current = int(label.cget("wraplength") or 0)
                if needed and current != width:
                    label.configure(wraplength=width)
                elif not needed and current:
                    label.configure(wraplength=0)
                alive.append((label, size, bold, inset))
            except tk.TclError:
                pass
        self._wrapped = alive

    def _track(self, label: tk.Label, size: int, bold: bool, inset: int = 0) -> tk.Label:
        """Взять подпись под перенос строки: ширина пересчитывается при ресайзе."""
        self._wrapped.append((label, size, bold, inset))
        width = max(self._wrap_px() - inset, px(80))
        # Перенос включаем только длинным строкам: с ним Tk меряет текст
        # на каждой раскладке, и список из десятков карточек заметно тормозит.
        if self._needs_wrap(label.cget("text"), width, size, bold):
            label.configure(wraplength=width)
        return label

    def _label(self, parent, text: str, size: int = 10, color: str = TEXT, *,
               bold: bool = False, bg: str = BG, wrap: bool = True) -> tk.Label:
        label = tk.Label(parent, text=text, bg=bg, fg=color,
                         font=theme.font(size, bold), anchor="w", justify="left")
        if wrap:
            self._track(label, size, bold)
        label.pack(anchor="w", fill=tk.X, pady=px(1))
        return label

    def _panel(self, parent, title: str, text: str, accent: str,
               size: int = 10) -> HudPanel:
        panel = HudPanel(parent, title, accent=accent)
        panel.pack(fill=tk.X, pady=px(4))
        self._label(panel.body, text, size, TEXT, bg=PANEL)
        return panel

    def _buttons(self, parent) -> tk.Frame:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=(px(6), px(2)))
        return row

    def _scroller(self, parent=None) -> tk.Frame:
        """Прокручиваемая область; колесо обрабатывает общий wheel_router."""
        parent = parent or self.content
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(parent, command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def fit(_event=None) -> None:
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
            canvas.itemconfigure(window, width=max(canvas.winfo_width(), 1))

        inner.bind("<Configure>", fit)
        canvas.bind("<Configure>", fit)
        return inner

    def _set_back(self, text: str | None) -> None:
        if text:
            self.back_btn.set_text(text)
            if not self.back_btn.winfo_ismapped():
                self.back_btn.pack(side=tk.LEFT, before=self.title_lbl)
        else:
            self.back_btn.pack_forget()

    def _set_crumb(self, text: str) -> None:
        self.crumb.configure(text=text)

    # ============================================================
    # Навигация
    # ============================================================

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.btn_mode_lessons.set_active(mode == "lessons")
        self.btn_mode_tables.set_active(mode == "tables")
        if mode == "tables":
            self.stage = "tables"
        else:
            self.stage = "levels"
            self.lesson = None
        self._render()

    def _go_back(self) -> None:
        if self.stage == "table":
            self.stage = "tables"
        elif self.stage == "tables":
            self._set_mode("lessons")
            return
        elif self.stage == "lessons":
            self.stage = "levels"
        elif self.stage == "intro":
            self.stage = "lessons"
        elif self.stage == "theory":
            if self.theory_index > 0:
                self.theory_index -= 1
            else:
                self.stage = "intro"
        elif self.stage == "practice":
            if self.lesson and not self.lesson.get("scored", True):
                self._show_lessons(self.lesson.get("level") or self.level)
                return
            self.stage = "intro"
        elif self.stage == "summary":
            self.stage = "lessons"
        else:
            if self.on_back is not None:
                self.on_back()
            return
        self._render()

    # ============================================================
    # Уровни
    # ============================================================

    def _screen_levels(self) -> None:
        self._set_back(None)
        self._set_crumb("")
        self.btn_mode_lessons.set_active(self.mode == "lessons")
        self.btn_mode_tables.set_active(False)
        inner = self._scroller()

        self._label(inner, _t("ВЫБЕРИТЕ УРОВЕНЬ"), 12, AMBER, bold=True)

        last_level = self._last_level()
        if last_level:
            HudButton(inner, _t("Продолжить · {0}").format(last_level),
                      lambda lvl=last_level: self._show_lessons(lvl),
                      color=AMBER, height=32, font_size=10).pack(fill=tk.X, pady=(px(2), px(6)))

        grid = tk.Frame(inner, bg=BG)
        grid.pack(fill=tk.X)
        for column in range(3):
            grid.columnconfigure(column, weight=1, uniform="level")
        for index, level in enumerate(self.engine.levels()):
            card = self._level_card(grid, level)
            card.grid(row=index // 3, column=index % 3, sticky="nsew",
                      padx=px(3), pady=px(3))

    def _level_card(self, parent, level: dict) -> tk.Frame:
        code = level["code"]
        total = int(level.get("lessons", 0) or 0)
        done = self.progress.grammar_done_count(code) if self.progress else 0
        color = GREEN if total and done >= total else (CYAN if done else MUTED)
        title = level.get("title", "")
        title = title.split("·", 1)[-1].strip() if "·" in title else title

        card = tk.Frame(parent, bg=PANEL, highlightbackground=color, highlightthickness=1)
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill=tk.X, padx=px(8), pady=(px(5), 0))
        code_lbl = tk.Label(head, text=code, bg=PANEL, fg=AMBER, font=theme.font(14, True))
        code_lbl.pack(side=tk.LEFT)
        prog_lbl = tk.Label(head, text=_t("{0} / {1} уроков").format(done, total), bg=PANEL,
                            fg=color, font=theme.font(8, True))
        prog_lbl.pack(side=tk.RIGHT)
        title_lbl = tk.Label(card, text=title, bg=PANEL, fg=TEXT, font=theme.font(8),
                             anchor="w", justify="left", wraplength=px(150))
        title_lbl.pack(fill=tk.X, padx=px(8), pady=(0, px(5)))

        for widget in (card, head, code_lbl, prog_lbl, title_lbl):
            widget.bind("<Button-1>", lambda _e, c=code: self._show_lessons(c))
        return card

    def _last_level(self) -> str | None:
        if not self.progress:
            return None
        lesson_id = self.progress.grammar_last_lesson()
        if not lesson_id:
            return None
        level = lesson_id.split("-", 1)[0].upper()
        known = {lvl["code"] for lvl in self.engine.levels()}
        return level if level in known else None

    # ============================================================
    # Список уроков уровня
    # ============================================================

    def _show_lessons(self, level: str) -> None:
        self.level = level
        self.current_level = level
        self.lesson = None
        self.stage = "lessons"
        self._render()

    def _screen_lessons(self) -> None:
        level = self.level or self.current_level
        manifest = next((lvl for lvl in self.engine.levels() if lvl["code"] == level), {})
        lessons = self.engine.lessons(level)  # читается только файл этого уровня
        self.level_lessons = lessons
        self.next_lesson_id = next(
            (lesson["id"] for lesson in lessons
             if not (self.progress and self.progress.grammar_done(lesson["id"]))), None)

        self._set_back(_t("← УРОВНИ"))
        self._set_crumb(f"{level} · {manifest.get('title', '')}")
        inner = self._scroller()

        done = sum(1 for lesson in lessons
                   if self.progress and self.progress.grammar_done(lesson["id"]))
        self._label(inner, f"{level}  {_t('УРОКИ')}", 12, AMBER, bold=True)
        self._label(inner, f"{_t('пройдено')} {done} {_t('из')} {len(lessons)}", 9, MUTED)

        if done:
            # «Teste dich!» из Grammatik aktiv: короткая проверка по пройденному.
            HudButton(inner, f"{_t('ПРОВЕРЬ СЕБЯ')} · {done}",
                      lambda lvl=level: self._start_self_check(lvl),
                      color=AMBER, height=30, font_size=9).pack(fill=tk.X, pady=(px(2), px(6)))

        self._queue([lambda les=item: self._lesson_card(inner, les) for item in lessons])

    def _start_self_check(self, level: str | None = None) -> None:
        """Смешанная проверка по пройденным урокам уровня — оценка уроков не меняется."""
        level = level or self.level or self.current_level
        if not self.level_lessons or self.level != level:
            self.level_lessons = self.engine.lessons(level)
        self.level = level
        self.current_level = level

        passed = [lesson for lesson in self.level_lessons
                  if self.progress and self.progress.grammar_done(lesson["id"])]
        pool = [drill for lesson in passed for drill in lesson.get("drills", [])]
        if not pool:
            return
        picked = _shuffled(pool, f"check:{level}")[:SELF_CHECK_SIZE]

        self.lesson = {
            "id": f"check:{level}", "title": _t("ПРОВЕРЬ СЕБЯ"), "order": 0,
            "level": level, "scored": False, "subtitle": "", "minutes": 5,
            "topics": [], "prereq": [], "theory": [], "drills": picked,
        }
        self.theory = []
        self.all_drills = picked
        self.drills = list(picked)
        self.answers = {}
        self.drill_index = 0
        self.run_full = True
        self.recorded = False
        self.bank = []
        self.rule_shown = False
        self._reset_answer()
        self._goto("practice")

    def _lesson_card(self, parent, lesson: dict) -> None:
        done = bool(self.progress and self.progress.grammar_done(lesson["id"]))
        is_next = (not done) and lesson["id"] == self.next_lesson_id
        if done:
            status, color = "✓ " + _t("пройден"), GREEN
        elif is_next:
            status, color = "▶ " + _t("следующий"), AMBER
        else:
            status, color = "· " + _t("не начат"), MUTED

        card = tk.Frame(parent, bg=PANEL, highlightbackground=color, highlightthickness=1)
        card.pack(fill=tk.X, padx=px(2), pady=px(3))

        title_lbl = tk.Label(card, text=f"{lesson['order']}. {lesson['title']}",
                             bg=PANEL, fg=TEXT, font=theme.font(10, True),
                             anchor="w", justify="left")
        self._track(title_lbl, 10, True, px(16))
        title_lbl.pack(fill=tk.X, padx=px(8), pady=(px(5), 0))

        # Подзаголовок, время и статус — одной строкой: меньше виджетов,
        # значит раскладка списка не «дёргается» на каждой карточке.
        meta_text = lesson.get("subtitle", "")
        line = f"{meta_text} · " if meta_text else ""
        line += (f"≈ {lesson.get('minutes', 10)} {_t('мин')} · "
                 f"{_t('Упражнений: {0}').format(len(lesson.get('drills', [])))} · {status}")
        meta_lbl = tk.Label(card, text=line, bg=PANEL, fg=color, font=theme.font(8),
                            anchor="w", justify="left")
        self._track(meta_lbl, 8, False, px(16))
        meta_lbl.pack(fill=tk.X, padx=px(8), pady=(0, px(5)))

        for widget in (card, title_lbl, meta_lbl):
            widget.bind("<Button-1>", lambda _e, les=lesson: self._open_lesson(les))

    # ============================================================
    # Урок: цель и мостик
    # ============================================================

    def _open_lesson(self, lesson: dict) -> None:
        """Открыть урок: сначала цель, мостик RU/UA → DE и ловушка."""
        self.lesson = lesson
        self.theory = lesson.get("theory", [])
        self.all_drills = lesson.get("drills", [])
        self.drills = list(self.all_drills)
        self.theory_index = 0
        self.drill_index = 0
        self.answers = {}
        self.checked = False
        self.last_ok = False
        self.run_full = True
        self.recorded = False
        self.rule_shown = False
        self._reset_answer()
        self._goto("intro")

    #: Старое имя входа в урок — оставлено для тестов и внешних вызовов.
    def _show_lesson(self, lesson: dict) -> None:
        self._open_lesson(lesson)

    def _screen_intro(self) -> None:
        lesson = self.lesson
        if not lesson:
            self._show_levels_fallback()
            return
        bridge = self.engine.bridge(lesson["id"])

        self._set_back(_t("← К СПИСКУ"))
        total = len(self.level_lessons)
        crumb = lesson.get("level", "")
        if total:
            crumb = f"{crumb} · {_t('урок {0} из {1}').format(lesson['order'], total)}"
        self._set_crumb(crumb)
        inner = self._scroller()

        self._label(inner, f"{lesson['order']}. {lesson['title']}", 14, AMBER, bold=True)
        self._label(inner, lesson.get("subtitle", ""), 9, MUTED)
        self._label(inner, f"{lesson.get('level', '')} · ≈ {lesson.get('minutes', 10)} "
                           f"{_t('мин')} · {_t('Упражнений: {0}').format(len(self.all_drills))}",
                    9, CYAN)

        can_do = bridge.get("can_do") or lesson.get("subtitle", "")
        self._panel(inner, _t("ЧТО ВЫ ОСВОИТЕ"), can_do, GREEN)
        if bridge.get("bridge"):
            self._panel(inner, _t("МОСТИК RU/UA → DE"), bridge["bridge"], CYAN, size=9)
        if bridge.get("trap"):
            self._panel(inner, _t("ЛОВУШКА"), bridge["trap"], AMBER, size=9)

        missing = self._missing_prereqs(lesson)
        if missing:
            self._label(inner, _t("Сначала пройдите: {0}").format(", ".join(missing)),
                        9, AMBER)

        row = self._buttons(inner)
        HudButton(row, _t("▶ НАЧАТЬ УРОК"), self._start_theory,
                  color=GREEN, height=34, font_size=10).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("К УПРАЖНЕНИЯМ"), self._start_practice,
                  color=CYAN, height=34, font_size=10).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("← К СПИСКУ"),
                  lambda: self._show_lessons(self.level or self.current_level),
                  color=MUTED, height=34, font_size=9).pack(side=tk.RIGHT, padx=px(2))

    def _missing_prereqs(self, lesson: dict) -> list[str]:
        """Названия непройденных уроков-предпосылок (из уже загруженного уровня)."""
        ids = set(lesson.get("prereq") or [])
        if not ids or not self.progress:
            return []
        return [item["title"] for item in self.level_lessons
                if item["id"] in ids and not self.progress.grammar_done(item["id"])]

    def _show_levels_fallback(self) -> None:
        self.stage = "levels"
        self._render()

    # ============================================================
    # Теория: один блок на экран
    # ============================================================

    def _start_theory(self) -> None:
        self.theory_index = 0
        self._goto("theory")

    def _start_practice(self) -> None:
        self.drills = list(self.all_drills)
        self.answers = {}
        self.drill_index = 0
        self.run_full = True
        self.recorded = False
        self._reset_answer()
        self._goto("practice")

    def _screen_theory(self) -> None:
        blocks = self.theory
        if not blocks:
            self._start_practice()
            return
        self.theory_index = max(0, min(self.theory_index, len(blocks) - 1))
        block = blocks[self.theory_index]

        self._set_back(_t("← НАЗАД"))
        self._set_crumb(self.lesson["title"] if self.lesson else "")
        inner = self._scroller()

        head = tk.Frame(inner, bg=BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=_t("ТЕОРИЯ"), bg=BG, fg=AMBER,
                 font=theme.font(11, True)).pack(side=tk.LEFT)
        tk.Label(head, text=_t("Теория {0} из {1}").format(self.theory_index + 1, len(blocks)),
                 bg=BG, fg=CYAN, font=theme.font(9, True)).pack(side=tk.RIGHT)

        kind = block.get("kind")
        if kind == "text":
            self._label(inner, block.get("text", ""), 11, TEXT)
        elif kind == "rule":
            self._panel(inner, block.get("title", _t("ПРАВИЛО")), block.get("text", ""),
                        AMBER, size=10)
        elif kind == "table":
            self._theory_table(inner, block.get("ref", ""))
        elif kind == "example":
            self._theory_example(inner, block)

        row = self._buttons(inner)
        if self.theory_index > 0:
            HudButton(row, _t("◀ НАЗАД"), self._theory_prev,
                      color=MUTED, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))
        if self.theory_index + 1 < len(blocks):
            HudButton(row, _t("ДАЛЬШЕ"), self._theory_next,
                      color=GREEN, height=32, font_size=10).pack(side=tk.LEFT, padx=px(2))
        else:
            HudButton(row, _t("К УПРАЖНЕНИЯМ"), self._start_practice,
                      color=GREEN, height=32, font_size=10).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("ПРОПУСТИТЬ ТЕОРИЮ"), self._start_practice,
                  color=MUTED, height=32, font_size=8).pack(side=tk.RIGHT, padx=px(2))

    def _theory_prev(self) -> None:
        self.theory_index = max(0, self.theory_index - 1)
        self._render()

    def _theory_next(self) -> None:
        self.theory_index += 1
        if self.theory_index >= len(self.theory):
            self._start_practice()
        else:
            self._render()

    def _theory_table(self, parent, table_ref: str) -> None:
        table = self.engine.table(table_ref)
        if not table:
            return
        panel = HudPanel(parent, table.get("title", ""), accent=CYAN)
        panel.pack(fill=tk.X, pady=px(4))
        self._grid_table(panel.body, table)
        if table.get("note"):
            self._label(panel.body, table["note"], 8, MUTED, bg=PANEL)

    def _theory_example(self, parent, block: dict) -> None:
        panel = HudPanel(parent, "", accent=GREEN)
        panel.pack(fill=tk.X, pady=px(4))

        top = tk.Frame(panel.body, bg=PANEL)
        top.pack(fill=tk.X)
        tk.Label(top, text=block.get("de", ""), bg=PANEL, fg=TEXT, font=theme.font(11, True),
                 anchor="w", justify="left", wraplength=self._wrap_px() - px(80)).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        self._speak_button(top, block.get("de", ""))

        if block.get("ru"):
            self._label(panel.body, block["ru"], 9, MUTED, bg=PANEL)
        if block.get("note"):
            self._label(panel.body, block["note"], 8, CYAN, bg=PANEL)

    def _speak_button(self, parent, text: str) -> None:
        """Озвучка примера, если на борту есть TTS."""
        if not text:
            return
        try:
            from stamina.english.tts import TTS
            if not TTS.available():
                return
            from stamina.languages.speech import speak
        except Exception:
            return
        HudButton(parent, "🔊", lambda t=text: speak(t, "de"),
                  height=24, font_size=8, width=32).pack(side=tk.RIGHT, padx=px(2))

    def _grid_table(self, parent, table: dict) -> tk.Frame:
        """Таблица сеткой: колонки выровнены по ширине, без горизонтальной прокрутки."""
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        count = max(1, len(columns))
        wrap = max(px(54), self._wrap_px() // count - px(12))

        grid = tk.Frame(parent, bg=LINE)
        grid.pack(fill=tk.X, pady=px(3))
        for column in range(count):
            grid.columnconfigure(column, weight=1, uniform="table")

        def cell(text: str, row: int, column: int, *, head: bool = False) -> None:
            label = tk.Label(grid, text=str(text),
                             bg=PANEL_HI if head else PANEL,
                             fg=AMBER if (head or column == 0) else TEXT,
                             font=theme.font(8, head or column == 0), anchor="w",
                             justify="left", padx=px(4), pady=px(2))
            # Перенос — только если строка не влезает: иначе Tk меряет каждую
            # ячейку при каждой раскладке, а в таблице их бывает сотня.
            if self._needs_wrap(str(text), wrap, 8, head or column == 0):
                label.configure(wraplength=wrap)
            label.grid(row=row, column=column, sticky="nsew",
                       padx=(0, px(1)), pady=(0, px(1)))

        for column, name in enumerate(columns):
            cell(name, 0, column, head=True)

        for row_index, row in enumerate(rows, start=1):
            for column, value in enumerate(row):
                cell(value, row_index, column)
        return grid

    # ============================================================
    # Упражнения: одно на экран
    # ============================================================

    def _reset_answer(self) -> None:
        self.checked = False
        self.last_ok = False
        self.answer_text = ""
        self.selected = None
        self.picked = []
        self.hint_shown = False
        self.drill_answer_var.set("")

    def _current_drill(self) -> dict | None:
        if 0 <= self.drill_index < len(self.drills):
            return self.drills[self.drill_index]
        return None

    def _instruction(self, drill: dict) -> str:
        kind = drill.get("type")
        prompt = drill.get("prompt", "")
        if kind in REORDER_TYPES:
            return _t(INSTRUCTION_REORDER)
        if _CYRILLIC.search(prompt):
            # Задание по-русски, ответ по-немецки — переводим (подход Нарустранг).
            if kind in FILL_TYPES or kind == "transform":
                return _t(INSTRUCTION_TRANSLATE_WRITE)
            return _t(INSTRUCTION_TRANSLATE)
        if kind == "transform":
            return _t(INSTRUCTION_TRANSFORM)
        if kind in FILL_TYPES:
            return _t(INSTRUCTION_FILL)
        return _t(INSTRUCTION_CHOICE)

    def _correct_count(self) -> int:
        return sum(1 for drill in self.drills if self.answers.get(drill["id"]))

    def _screen_practice(self) -> None:
        drill = self._current_drill()
        if drill is None:
            self.stage = "summary"
            self._render()
            return

        self._set_back(_t("← УРОК"))
        self._set_crumb(self.lesson["title"] if self.lesson else "")
        inner = self._scroller()

        head = tk.Frame(inner, bg=BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=_t("Упражнение {0} из {1}").format(
            self.drill_index + 1, len(self.drills)), bg=BG, fg=CYAN,
            font=theme.font(10, True)).pack(side=tk.LEFT)
        tk.Label(head, text=_t("Правильных: {0} из {1}").format(
            self._correct_count(), len(self.drills)), bg=BG, fg=GREEN if self._correct_count()
            else MUTED, font=theme.font(9, True)).pack(side=tk.RIGHT)

        self._label(inner, self._instruction(drill), 9, MUTED)

        panel = HudPanel(inner, _t("УПРАЖНЕНИЕ"), accent=CYAN)
        panel.pack(fill=tk.X, pady=px(4))
        self._label(panel.body, drill.get("prompt", ""), 11, TEXT, bg=PANEL)

        if not self.checked:
            self._render_answer_input(panel.body, drill)
            if self.hint_shown:
                self._label(panel.body, self._hint_text(drill), 9, AMBER, bg=PANEL)
        else:
            self._render_locked_answer(panel.body, drill)
            self._render_feedback(panel.body, drill)

        # Как в Grammatik aktiv: правило — на соседней странице, не уводя из упражнения.
        if self.rule_shown:
            self._render_rule_peek(inner)

        row = self._buttons(inner)
        if not self.checked:
            HudButton(row, _t("ПРОВЕРИТЬ"), self._check_answer,
                      color=GREEN, height=32, font_size=10).pack(side=tk.LEFT, padx=px(2))
            HudButton(row, _t("ПОДСКАЗКА"), self._toggle_hint,
                      color=CYAN, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))
            if self._rule_blocks():
                HudButton(row, _t("СПРЯТАТЬ ПРАВИЛО") if self.rule_shown else _t("ПРАВИЛО"),
                          self._toggle_rule, color=AMBER, height=32,
                          font_size=9).pack(side=tk.LEFT, padx=px(2))
            HudButton(row, _t("ПРОПУСТИТЬ"), self._skip_drill,
                      color=MUTED, height=32, font_size=9).pack(side=tk.RIGHT, padx=px(2))
        else:
            HudButton(row, _t("ДАЛЬШЕ"), self._next_drill,
                      color=GREEN, height=32, font_size=10).pack(side=tk.LEFT, padx=px(2))
            HudButton(row, _t("ЕЩЁ РАЗ"), self._retry_drill,
                      color=AMBER, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))

    def _rule_blocks(self) -> list[dict]:
        """Правила и таблицы урока — то, что открывается кнопкой «ПРАВИЛО»."""
        return [block for block in self.theory
                if block.get("kind") in ("rule", "table")]

    def _toggle_rule(self) -> None:
        self.rule_shown = not self.rule_shown
        self._render()

    def _render_rule_peek(self, parent) -> None:
        """Короткая шпаргалка под упражнением: правила и таблицы этого урока."""
        panel = HudPanel(parent, _t("ПРАВИЛО"), accent=AMBER)
        panel.pack(fill=tk.X, pady=(px(4), px(2)))
        blocks = self._rule_blocks()
        if not blocks:
            self._label(panel.body, _t("В этом уроке нет правил — только примеры."), 9,
                        MUTED, bg=PANEL)
            return
        for block in blocks:
            if block.get("kind") == "rule":
                self._label(panel.body, block.get("title", ""), 9, AMBER, bold=True, bg=PANEL)
                self._label(panel.body, block.get("text", ""), 9, TEXT, bg=PANEL)
            else:
                table = self.engine.table(block.get("ref", ""))
                if table:
                    self._label(panel.body, table.get("title", ""), 9, AMBER, bold=True,
                                bg=PANEL)
                    self._grid_table(panel.body, table)

    def _render_answer_input(self, parent, drill: dict) -> None:
        kind = drill.get("type")
        if kind in CHOICE_TYPES:
            for option in drill.get("options", []):
                HudButton(parent, option, lambda opt=option: self._choose(opt),
                          height=32, font_size=10).pack(fill=tk.X, pady=px(2))
        elif kind in REORDER_TYPES:
            self._render_word_bank(parent, drill)
        else:
            entry = tk.Entry(parent, textvariable=self.drill_answer_var, bg=PANEL,
                             fg=TEXT, insertbackground=TEXT, font=theme.font(12),
                             relief=tk.FLAT, highlightthickness=1, highlightbackground=LINE)
            entry.pack(fill=tk.X, pady=px(6), ipady=px(4))
            entry.focus_set()
            entry.bind("<Return>", lambda _e: self._check_answer())

    def _render_word_bank(self, parent, drill: dict) -> None:
        if not self.bank:
            self.bank = _shuffled(_word_bank(drill), drill.get("id", drill.get("prompt", "")))
        self.picked = [index for index in self.picked if 0 <= index < len(self.bank)]

        sentence = " ".join(self.bank[index] for index in self.picked) or "…"
        self._label(parent, sentence, 11, TEXT if self.picked else MUTED, bg=PANEL)

        bank_frame = tk.Frame(parent, bg=PANEL)
        bank_frame.pack(fill=tk.X, pady=px(4))
        per_row = 3
        for column in range(per_row):
            bank_frame.columnconfigure(column, weight=1, uniform="bank")
        for index, word in enumerate(self.bank):
            used = index in self.picked
            button = HudButton(bank_frame, word,
                               lambda i=index: self._pick_word(i),
                               height=30, font_size=10,
                               color=MUTED if used else CYAN)
            button.grid(row=index // per_row, column=index % per_row, sticky="nsew",
                        padx=px(2), pady=px(2))
            if used:
                button.set_enabled(False)

        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill=tk.X, pady=(px(2), 0))
        HudButton(row, _t("← УБРАТЬ"), self._unpick_word,
                  color=MUTED, height=26, font_size=8).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("ОЧИСТИТЬ"), self._clear_words,
                  color=MUTED, height=26, font_size=8).pack(side=tk.LEFT, padx=px(2))

    def _render_locked_answer(self, parent, drill: dict) -> None:
        """После проверки: показать, что выбрал ученик, и что было правильно."""
        kind = drill.get("type")
        if kind in CHOICE_TYPES:
            expected = self._expected(drill)
            chosen = self.selected
            for option in drill.get("options", []):
                is_right = self._match(option, expected)
                is_chosen = chosen == option
                if is_right:
                    color = GREEN
                elif is_chosen:
                    color = RED
                else:
                    color = MUTED
                button = HudButton(parent, option, None, height=30, font_size=10,
                                   color=color, active=is_right or is_chosen)
                button.pack(fill=tk.X, pady=px(2))
                button.set_enabled(False)
        elif kind in REORDER_TYPES:
            sentence = self._picked_sentence()
            self._label(parent, sentence or "…", 11, TEXT, bg=PANEL)
            self._label(parent, " ".join(self.bank), 8, MUTED, bg=PANEL)
        else:
            self._label(parent, self.answer_text or "…", 11, TEXT, bg=PANEL)

    def _render_feedback(self, parent, drill: dict) -> None:
        expected = self._expected(drill)
        if self.last_ok:
            self._label(parent, _t("ВЕРНО ✓"), 12, GREEN, bold=True, bg=PANEL)
        else:
            self._label(parent, _t("НЕВЕРНО ✗"), 12, RED, bold=True, bg=PANEL)
            self._label(parent, _t("Правильно: {0}").format(expected[0] if expected else ""),
                        10, CYAN, bg=PANEL)
        if drill.get("why"):
            self._label(parent, _t("Почему: {0}").format(drill["why"]), 9, MUTED, bg=PANEL)

    def _hint_text(self, drill: dict) -> str:
        expected = self._expected(drill)
        answer = expected[0] if expected else ""
        if drill.get("type") in REORDER_TYPES:
            first = answer.split(" ")[0] if answer else ""
            return _t("Подсказка: первое слово — «{0}»").format(first)
        letters = [char for char in answer if char.isalpha()]
        if not letters:
            return _t("Подсказка: в ответе только цифры.")
        return _t("Подсказка: ответ из {0} букв, начинается на «{1}»").format(
            len(letters), letters[0])

    # ---------- ответы ----------

    def _expected(self, drill: dict) -> list[str]:
        answer = drill.get("answer", [])
        return list(answer) if isinstance(answer, (list, tuple)) else [str(answer)]

    def _match(self, answer: str, expected: list[str]) -> bool:
        """Совпадает ли вариант ответа с ожидаемым (для подсветки кнопок)."""
        return _answer_matches("choice", answer, expected)

    def _picked_sentence(self) -> str:
        return " ".join(self.bank[index] for index in self.picked if 0 <= index < len(self.bank))

    def _pick_word(self, index: int) -> None:
        if self.checked or index in self.picked:
            return
        self.picked.append(index)
        self._rerender_practice()

    def _unpick_word(self) -> None:
        if self.checked or not self.picked:
            return
        self.picked.pop()
        self._rerender_practice()

    def _clear_words(self) -> None:
        if self.checked:
            return
        self.picked = []
        self._rerender_practice()

    def _toggle_hint(self) -> None:
        self.hint_shown = not self.hint_shown
        self._rerender_practice()

    def _rerender_practice(self) -> None:
        self._render()

    def _choose(self, option: str) -> None:
        if self.checked:
            return
        self.selected = option
        self._check_answer(option)

    def _check_answer(self, value: str | None = None) -> None:
        """Проверить ответ; в зачёт идёт первая попытка по упражнению."""
        drill = self._current_drill()
        if drill is None or self.checked:
            return
        if value is None:
            if drill.get("type") in REORDER_TYPES:
                value = self._picked_sentence()
            else:
                value = self.drill_answer_var.get()
        value = _normalize_sentence(value or "")

        if not value:
            return

        expected = self._expected(drill)
        ok = _answer_matches(drill.get("type", "choice"), value, expected)
        self.checked = True
        self.last_ok = ok
        self.answer_text = value
        if drill.get("type") in CHOICE_TYPES:
            self.selected = value
        self.answers.setdefault(drill["id"], ok)

        if self.progress and drill.get("id"):
            self.progress.record_attempt(drill["id"], ok, "grammar",
                                         quality=1 if ok else 0)
        self._render()

    #: Старое имя проверки — оставлено для тестов.
    def _check_drill(self, _drill: dict | None = None) -> None:
        self._check_answer()

    def _retry_drill(self) -> None:
        self.checked = False
        self.last_ok = False
        self.selected = None
        self.picked = []
        self.hint_shown = False
        self.answer_text = ""
        self.drill_answer_var.set("")
        self._render()

    def _skip_drill(self) -> None:
        drill = self._current_drill()
        if drill is not None and drill["id"] not in self.answers:
            self.answers[drill["id"]] = False
        self._next_drill()

    def _next_drill(self) -> None:
        self.drill_index += 1
        self._reset_answer()
        self.bank = []
        if self.drill_index >= len(self.drills):
            self.stage = "summary"
            self._render()
        else:
            self._render()

    # ============================================================
    # Итог урока
    # ============================================================

    def _screen_summary(self) -> None:
        drills = self.drills
        total = len(drills)
        correct = self._correct_count()
        percent = round(100 * correct / total) if total else 0
        passed = bool(total) and correct / total >= PASS_SCORE

        if self.run_full and not self.recorded and self.progress and total \
                and self.lesson.get("scored", True):
            self.progress.record_grammar(self.lesson["id"], correct, total)
            self.recorded = True

        self._set_back(_t("← К СПИСКУ"))
        self._set_crumb(self.lesson["title"] if self.lesson else "")
        inner = self._scroller()

        panel = HudPanel(inner, _t("УРОК ЗАВЕРШЁН"), accent=GREEN if passed else AMBER)
        panel.pack(fill=tk.X, pady=px(6))
        self._label(panel.body, _t("Результат: {0} из {1} · {2}%").format(
            correct, total, percent), 12, TEXT, bold=True, bg=PANEL)
        if not self.lesson.get("scored", True):
            self._label(panel.body, _t("Проверка себя: оценки уроков не меняются."),
                        9, MUTED, bg=PANEL)
        elif passed:
            self._label(panel.body, _t("Урок засчитан ✓"), 11, GREEN, bold=True, bg=PANEL)
        elif not self.run_full:
            self._label(panel.body, _t("Повтор ошибок: оценка урока не меняется."),
                        9, MUTED, bg=PANEL)
        else:
            self._label(panel.body, _t("Нужно 80% — разберите ошибки и повторите."),
                        9, AMBER, bg=PANEL)

        wrong = [drill for drill in drills if not self.answers.get(drill["id"])]
        if wrong:
            mistakes = HudPanel(inner, _t("РАЗБОР ОШИБОК"), accent=RED)
            mistakes.pack(fill=tk.X, pady=px(4))
            self._queue([lambda d=drill, parent=mistakes.body: self._mistake_line(parent, d)
                         for drill in wrong])

        row = self._buttons(inner)
        if wrong and self.run_full:
            HudButton(row, _t("ПОВТОРИТЬ ОШИБКИ"), self._retry_mistakes,
                      color=AMBER, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("ЕЩЁ РАЗ"), self._restart_lesson,
                  color=CYAN, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))
        if self._next_lesson() is not None:
            HudButton(row, _t("СЛЕДУЮЩИЙ УРОК"), self._open_next_lesson,
                      color=GREEN, height=32, font_size=9).pack(side=tk.LEFT, padx=px(2))
        HudButton(row, _t("К СПИСКУ"), lambda: self._show_lessons(self.level or self.current_level),
                  color=MUTED, height=32, font_size=9).pack(side=tk.RIGHT, padx=px(2))

    def _mistake_line(self, parent, drill: dict) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill=tk.X, pady=px(2))
        self._label(frame, drill.get("prompt", ""), 9, TEXT, bg=PANEL)
        expected = self._expected(drill)
        self._label(frame, _t("Правильно: {0}").format(expected[0] if expected else ""),
                    9, CYAN, bg=PANEL)
        if drill.get("why"):
            self._label(frame, _t("Почему: {0}").format(drill["why"]), 8, MUTED, bg=PANEL)

    def _retry_mistakes(self) -> None:
        wrong = [drill for drill in self.drills if not self.answers.get(drill["id"])]
        if not wrong:
            return
        self.drills = wrong
        self.answers = {}
        self.drill_index = 0
        self.run_full = False
        self.recorded = True  # повтор ошибок не меняет оценку урока
        self.bank = []
        self._reset_answer()
        self._goto("practice")

    def _restart_lesson(self) -> None:
        if not self.lesson:
            return
        if not self.lesson.get("scored", True):
            self._start_self_check(self.lesson.get("level"))
            return
        self._open_lesson(self.lesson)

    def _next_lesson(self) -> dict | None:
        if not self.level_lessons or not self.lesson:
            return None
        ids = [lesson["id"] for lesson in self.level_lessons]
        try:
            index = ids.index(self.lesson["id"])
        except ValueError:
            return None
        return self.level_lessons[index + 1] if index + 1 < len(self.level_lessons) else None

    def _open_next_lesson(self) -> None:
        nxt = self._next_lesson()
        if nxt is not None:
            self._open_lesson(nxt)

    # ============================================================
    # Таблицы: список → одна таблица
    # ============================================================

    def _screen_tables(self) -> None:
        self._set_back(None)
        self._set_crumb("")
        self.btn_mode_lessons.set_active(False)
        self.btn_mode_tables.set_active(True)

        chips = tk.Frame(self.content, bg=BG)
        chips.pack(fill=tk.X, pady=(0, px(4)))
        tk.Label(chips, text=_t("УРОВЕНЬ:"), bg=BG, fg=MUTED,
                 font=theme.font(9)).pack(side=tk.LEFT, padx=(0, px(4)))
        levels = [_t("ВСЕ")] + [lvl["code"] for lvl in self.engine.levels()]
        for code in levels:
            value = "ALL" if code == _t("ВСЕ") else code
            HudButton(chips, code, lambda v=value: self._filter_tables(v),
                      height=26, font_size=8, active=(value == self.table_level),
                      color=GREEN if value == self.table_level else CYAN).pack(
                side=tk.LEFT, padx=px(2))

        inner = self._scroller()
        self.tables_container = inner
        tables = self.engine.tables(None if self.table_level == "ALL" else self.table_level)
        self._label(inner, f"{_t('ТАБЛИЦЫ')} · {len(tables)}", 9, MUTED)
        self._queue([lambda t=table: self._table_card(inner, t) for table in tables])

    def _filter_tables(self, level: str) -> None:
        self.table_level = level
        self.stage = "tables"
        self._render()

    def _table_card(self, parent, table: dict) -> None:
        card = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill=tk.X, padx=px(2), pady=px(2))
        level = tk.Label(card, text=table.get("level", ""), bg=PANEL, fg=CYAN,
                         font=theme.font(8, True))
        level.pack(side=tk.LEFT, padx=(px(8), px(8)), pady=px(5))
        title = tk.Label(card, text=table.get("title", ""), bg=PANEL, fg=TEXT,
                         font=theme.font(9), anchor="w", justify="left")
        self._track(title, 9, False, px(80))
        title.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=px(5), padx=(0, px(8)))
        for widget in (card, level, title):
            widget.bind("<Button-1>", lambda _e, t=table: self._open_table(t["id"]))

    def _open_table(self, table_id: str) -> None:
        self.table_id = table_id
        self.stage = "table"
        self._render()

    def _screen_table(self) -> None:
        table = self.engine.table(self.table_id)
        if not table:
            self.stage = "tables"
            self._render()
            return
        self._set_back(_t("← ТАБЛИЦЫ"))
        self._set_crumb(table.get("level", ""))
        inner = self._scroller()
        self.tables_container = inner

        head = tk.Frame(inner, bg=BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=table.get("title", ""), bg=BG, fg=AMBER,
                 font=theme.font(12, True)).pack(side=tk.LEFT)
        HudButton(head, _t("СКОПИРОВАТЬ"), lambda: self._copy_table(table),
                  height=26, font_size=8).pack(side=tk.RIGHT)

        self._grid_table(inner, table)
        if table.get("note"):
            self._label(inner, table["note"], 9, MUTED)

    def _copy_table(self, table: dict) -> None:
        """Скопировать таблицу в буфер обмена (TSV: вставляется в таблицу)."""
        lines = ["\t".join(str(cell) for cell in table.get("columns", []))]
        for row in table.get("rows", []):
            lines.append("\t".join(str(cell) for cell in row))
        try:
            self.frame.clipboard_clear()
            self.frame.clipboard_append("\n".join(lines))
        except tk.TclError:
            return
        self._toast(_t("Таблица скопирована"))

    def _toast(self, text: str) -> None:
        toast = tk.Label(self.content, text=text, bg=AMBER, fg=BG,
                         font=theme.font(10, True), padx=px(12), pady=px(6))
        toast.place(relx=0.5, rely=0.08, anchor="n")

        def hide() -> None:
            try:
                toast.destroy()
            except tk.TclError:
                pass

        self.frame.after(1500, hide)


def build_grammar_page(parent, plugin, progress, app) -> GrammarPage:
    """Фабрика страницы грамматики."""
    return GrammarPage(parent, plugin, progress, app)
