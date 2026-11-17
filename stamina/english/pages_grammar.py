"""Вкладка грамматики английского языка со всеми уровнями A1-C2."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from tkinter import ttk

from stamina import theme
from stamina.hud import HudButton, HudPanel
from stamina.theme import AMBER, BG, BG2, CYAN, LINE_HI, MUTED, PANEL, RED, TEXT, px


def _load_grammar_engine():
    """Lazy import to avoid circular imports."""
    from . import grammar_engine  # noqa: F811
    return grammar_engine


def _level_frame(parent, level_key: str) -> tk.Frame:
    """Create a frame showing a level's topics and exercises."""
    frame = tk.Frame(parent, bg=BG)
    frame.grid_columnconfigure(0, weight=1)

    lbl = tk.Label(frame, text=_LEVEL_TITLES[level_key], fg=AMBER, bg=BG, font=("", 12, "bold"))
    lbl.grid(row=0, column=0, sticky="w", padx=px(12), pady=px(8))

    grammar_engine = _load_grammar_engine()
    level_data = grammar_engine.load_grammar(level_key)
    topics = level_data.get("topics", [])

    canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
    canvas.grid(row=1, column=0, sticky="nsew", padx=px(12), pady=px(4))
    vsb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    vsb.grid(row=1, column=1, sticky="ns")
    canvas.configure(yscrollcommand=vsb.set)

    inner = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.grid_columnconfigure(0, weight=1)

    for t in topics:
        ttl = tk.Label(inner, text=t["name"], fg=TEXT, bg=BG, font=("", 10, "underline"))
        ttl.grid(row=t["name"].__hash__() % 1000, column=0, sticky="w", padx=px(8), pady=px(2))
        exp = tk.Label(inner, text=f"Упражнений: {t.get('total_exercises', 0)}", fg=MUTED, bg=BG, font=("", 9))
        exp.grid(row=t["name"].__hash__() % 1000 + 1, column=0, sticky="w", padx=px(8), pady=px(1))

    # Exercise generation section
    gen_frame = tk.LabelFrame(inner, text=_t("Генерировать упражнение"), bg=BG, fg=AMBER)
    gen_frame.grid(row=len(topics) + 2, column=0, sticky="w", padx=px(8), pady=px(8))

    level_var = tk.StringVar(value=level_key)
    topic_var = tk.StringVar(value=level_data["topics"][0]["name"] if level_data["topics"] else "")

    lbl_level = tk.Label(gen_frame, text=_t("Уровень:"), bg=BG, fg=TEXT, font=("", 9))
    lbl_level.grid(row=0, column=0, padx=px(4), pady=px(2))
    cb_level = ttk.Combobox(gen_frame, textvariable=level_var, values=["a1", "a2", "b1", "b2", "c1", "c2"], state="readonly", width=12, font=("", 9))
    cb_level.grid(row=0, column=1, padx=px(4), pady=px(2))

    lbl_topic = tk.Label(gen_frame, text=_t("Тема:"), bg=BG, fg=TEXT, font=("", 9))
    lbl_topic.grid(row=1, column=0, padx=px(4), pady=px(2))
    cb_topic = ttk.Combobox(gen_frame, textvariable=topic_var, values=[t["name"] for t in level_data.get("topics", [])], state="readonly", width=25, font=("", 9))
    cb_topic.grid(row=1, column=1, padx=px(4), pady=px(2))

    btn_gen = tk.Button(gen_frame, text=_t("Сгенерировать"), bg=BG, fg=AMBER,
                        command=lambda: _gen_exercise(level_var.get(), topic_var.get()), font=("", 9))
    btn_gen.grid(row=2, column=0, columnspan=2, pady=px(4), sticky="w")

    result_lbl = tk.Label(gen_frame, text="", bg=BG, fg=CYAN, font=("", 9, "bold"))
    result_lbl.grid(row=3, column=0, columnspan=2, pady=px(2))

    def _gen_exercise(lvl: str, topic: str) -> None:
        try:
            ex = grammar_engine.generate_exercise(lvl, topic)
            result_lbl.config(
                text=f"Уровень: {ex['level']}, Тема: {ex['topic']}, Тип: {ex['type']}, Кол-во: {ex['exercise_count']}"
            )
        except Exception as e:
            result_lbl.config(text=_t("Ошибка: {0}").format(e), fg=AMBER)

    # Update inner scroll region
    def _update_scroll(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _update_scroll)
    canvas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    return frame


def _LEVEL_TITLES() -> dict:
    return {
        "a1": "A1 (Elementary)",
        "a2": "A2 (Pre-intermediate)",
        "b1": "B1 (Intermediate)",
        "b2": "B2 (Upper-intermediate)",
        "c1": "C1 (Advanced)",
        "c2": "C2 (Proficiency)",
    }


def _build_grammar_page(parent) -> tk.Frame:
    """Build the full grammar page with all levels."""
    from . import grammar_engine  # lazy

    frame = tk.Frame(parent, bg=BG)
    frame.grid_columnconfigure(0, weight=1)

    # Header
    header = tk.Frame(frame, bg=BG)
    header.grid(row=0, column=0, sticky="ew", padx=px(12), pady=px(8))
    tk.Label(header, text=_t("ГРАММАТИКА АНГЛИЙСКОГО ЯЗЫКА"), fg=AMBER, bg=BG, font=("", 14, "bold")).pack(side=tk.LEFT)
    tk.Label(header, text=_t("(A1–C2)"), fg=MUTED, bg=BG, font=("", 10)).pack(side=tk.LEFT, padx=px(6))

    # Levels selector
    levels_container = tk.Frame(frame, bg=BG)
    levels_container.grid(row=1, column=0, sticky="nsew", padx=px(12), pady=px(4))
    levels_container.grid_columnconfigure(0, weight=1)

    current_level = tk.StringVar(value="a1")

    for i, level_key in enumerate(["a1", "a2", "b1", "b2", "c1", "c2"]):
        btn = tk.Button(levels_container, text=_LEVEL_TITLES()[level_key], bg=BG, fg=AMBER,
                        font=("", 10, "bold"),
                        command=lambda lk=level_key: _show_level(lk, grammar_engine))
        btn.grid(row=i, column=0, sticky="w", pady=px(4), padx=px(8))

    # Content area
    content_area = tk.Frame(frame, bg=BG)
    content_area.grid(row=2, column=0, sticky="nsew", padx=px(12), pady=px(4))
    content_area.grid_columnconfigure(0, weight=1)

    # Reference tables button
    tbl_btn = tk.Button(frame, text=_t("Справочные таблицы"), bg=BG, fg=CYAN,
                        command=lambda: _show_tables(grammar_engine), font=("", 10))
    tbl_btn.grid(row=3, column=0, sticky="w", padx=px(12), pady=px(8))

    # Initially show A1
    _show_level("a1", grammar_engine)
    return frame


def _show_level(level_key: str, grammar_engine) -> None:
    """Show the frame for the given level, destroying previous content."""
    from .pages_grammar import _content_frames  # lazy

    # Destroy previous level frame if exists
    for key, widget in _content_frames.items():
        widget.grid_remove()
    # Create and show new level frame
    if level_key not in _content_frames:
        _content_frames[level_key] = _level_frame(_content_area, level_key)
    _content_frames[level_key].grid(row=1, column=0, sticky="nsew")


def _content_area_destroy() -> None:
    """Placeholder - will be set by screen integration."""
    pass


def _show_tables(grammar_engine) -> None:
    """Show the reference tables."""
    from .pages_grammar import _content_frames

    for key, widget in _content_frames.items():
        widget.grid_remove()
    # Simple info about tables
    info = tk.Label(_content_area,
                    text=_t("Справочные таблицы есть в файле tables.json: verb tenses, irregular verbs, conditionals, modals"),
                    fg=MUTED, bg=BG, font=("", 10))
    info.pack(padx=px(20), pady=px(20))


# Module-level tracking of content frames - will be replaced by screen integration
_content_frames: dict = {}


def init_grammar_tab(english_screen) -> None:
    """Initialize and add the Grammar tab to the English screen navigation."""
    global _content_area

    # Build the grammar page content
    global _content_area
    _content_area = tk.Frame(english_screen, bg=BG)
    _content_area.place(relx=0, rely=0, relwidth=1, relheight=1)

    grammar_page = _build_grammar_page(english_screen)

    # Add "grammar" to SUBPAGES if not already there
    subpage_names = [name for name, _ in english_screen.SUBPAGES]
    if "grammar" not in subpage_names:
        english_screen.SUBPAGES += (("grammar", _t("ГРАММАТИКА")),)

    # Register the page in english_screen.pages
    english_screen.pages["grammar"] = grammar_page

    # Mark screen as built and show grammar tab
    english_screen._built = True
    english_screen.show("grammar")