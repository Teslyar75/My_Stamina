"""Экраны «Миссии», «Свой текст», «Бортжурнал», «Настройки»."""

from __future__ import annotations

from stamina.i18n import t as _t

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from stamina import missions, theme
from stamina.bridge import fmt_int, fmt_time
from stamina.hud import HudButton, HudKeyboard, HudPanel, LineChart
from stamina.session_storage import load_session
from stamina.storage import DATA_DIR
from stamina.text_processing import process_text
from stamina.theme import (
    AMBER, BG, BG2, CYAN, CYAN_DIM, FAINT, GREEN, LINE, MUTED, PANEL, PANEL_HI,
    RED, TEXT, blend, chamfer, px,
)

if TYPE_CHECKING:
    from stamina.cockpit import Cockpit


def _label(master, text, *, fg=TEXT, size=10, bold=False, mono=False, bg=PANEL, **kw):
    return tk.Label(master, text=text, fg=fg, bg=bg, font=theme.font(size, bold, mono), **kw)


# ===========================================================================
# Миссии
# ===========================================================================

class MissionCard(tk.Canvas):
    def __init__(self, master, app: "Cockpit", mission: dict) -> None:
        super().__init__(master, bg=PANEL, highlightthickness=0, bd=0,
                         width=px(180), height=px(118), cursor="hand2")
        self.app, self.m = app, mission
        self._hover = False
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<Button-1>", lambda _e: self.app.start_mission(self.m))

    def _set_hover(self, v):
        self._hover = v
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        store = self.app.store
        rec = store.mission_record(self.m["id"])
        stars = rec.get("stars", 0)
        unlocked = store.is_unlocked(self.m)
        if not unlocked:
            col = FAINT
        elif stars:
            col = GREEN
        else:
            col = AMBER
        fill = blend(col, BG, 0.88) if self._hover and unlocked else BG2
        c = px(12)
        self.create_polygon(chamfer(2, 2, w - 3, h - 3, c), fill=fill,
                            outline=col if unlocked else LINE, width=2 if self._hover else 1)
        self.create_line(2, 2 + c, 2, 2 + c + px(20), fill=col, width=3)
        num = f"{self.m['lang'].upper()}-{self.m['num']:02d}"
        self.create_text(px(14), px(14), text=num, anchor="w", fill=col,
                         font=theme.font(9, True, mono=True))
        self.create_text(w - px(10), px(14), text=self.m["sector"].upper(), anchor="e",
                         fill=MUTED, font=theme.font(7, True))
        self.create_text(px(14), px(38), text=self.m["title"], anchor="w",
                         fill=TEXT if unlocked else MUTED, font=theme.font(12, True))
        if self.m["new"]:
            keys = " ".join(self.m["new"].upper()) if not self.m["new"].isdigit() else "0–9"
            info = _t("новые клавиши: {0}").format(keys)
        else:
            info = _t("все буквы, настоящие слова")
        self.create_text(px(14), px(60), text=info, anchor="w", fill=MUTED, font=theme.font(8),
                         width=w - px(24))
        new = self.m["new"]
        if not new:
            caps = ["A–Z"] if self.m["lang"] == "en" else [_t("А–Я")]
        elif new.isdigit():
            caps = ["0–9"]
        else:
            caps = list(new.upper())
        size = min(px(30), (w - px(28)) / max(1, len(caps)) - px(4))
        top_y = px(76)
        avail = h - px(36) - top_y
        if avail > size * 0.8 and size > px(12):
            y1 = top_y + (avail - size) / 2
            total = len(caps) * (size + px(4)) - px(4) if len(caps[0]) == 1 else size * 2
            x = (w - total) / 2
            for cap in caps:
                cw = size if len(cap) == 1 else size * 2
                kc = col if unlocked else FAINT
                self.create_polygon(chamfer(x, y1, x + cw, y1 + size, size * 0.2),
                                    fill=blend(kc, BG, 0.82), outline=kc)
                self.create_text(x + cw / 2, y1 + size / 2, text=cap, fill=TEXT if unlocked else MUTED,
                                 font=theme.font(max(7, int(size / theme.S * 0.42)), True))
                x += cw + px(4)
        self.create_text(px(14), h - px(20), text=_t("цель {0} зн/мин").format(self.m['goal']), anchor="w",
                         fill=CYAN_DIM, font=theme.font(8, True))
        if not unlocked:
            self.create_text(w - px(12), h - px(20), text=_t("⊘ ЗАКРЫТО"), anchor="e", fill=FAINT,
                             font=theme.font(8, True))
        else:
            self.create_text(w - px(12), h - px(21), text="★" * stars + "☆" * (3 - stars),
                             anchor="e", fill=AMBER, font=theme.font(13))
            if rec.get("best_cpm"):
                self.create_text(w - px(12), h - px(40), text=_t("рекорд {0:.0f}").format(rec['best_cpm']),
                                 anchor="e", fill=MUTED, font=theme.font(7))


class MissionsScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.lang = app.store.settings.get("lang", "en")
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("ЗВЁЗДНАЯ КАРТА МИССИЙ"), fg=TEXT, size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        self.btn_ru = HudButton(top, _t("РУССКИЙ  ЙЦУКЕН"), lambda: self.set_lang("ru"), height=32)
        self.btn_ru.pack(side=tk.RIGHT, padx=(0, px(8)))
        self.btn_en = HudButton(top, "ENGLISH  QWERTY", lambda: self.set_lang("en"), height=32)
        self.btn_en.pack(side=tk.RIGHT, padx=px(8))
        _label(self, _t("Каждая миссия добавляет новые клавиши. Пройдите с точностью от {0:.0f}%, чтобы открыть следующую. Звёзды дают за точность и скорость.").format(missions.PASS_ACCURACY),
               fg=MUTED, size=9, bg=BG, wraplength=px(900)).pack(anchor="w", padx=px(16))
        self.grid_frame = tk.Frame(self, bg=BG)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(8))
        special = tk.Frame(self, bg=BG)
        special.pack(fill=tk.X, padx=px(10), pady=(0, px(10)))
        self.repair_panel = HudPanel(special, _t("РЕМОНТ СИСТЕМ — АДАПТИВНАЯ ТРЕНИРОВКА"), accent=AMBER)
        self.repair_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(4), px(6)))
        self.repair_info = _label(self.repair_panel.body, "", fg=TEXT, size=10, justify="left",
                                  anchor="w", wraplength=px(360))
        self.repair_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(self.repair_panel.body, _t("⚙ ЗАПУСТИТЬ"), lambda: self.app.start_repair(self.lang),
                  color=AMBER).pack(side=tk.RIGHT)
        self.cargo_panel = HudPanel(special, _t("СВОЙ ТЕКСТ — ГРУЗ НА БОРТУ"))
        self.cargo_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(6), px(4)))
        self.cargo_info = _label(self.cargo_panel.body, "", fg=TEXT, size=10, justify="left",
                                 anchor="w", wraplength=px(360))
        self.cargo_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_cargo = HudButton(self.cargo_panel.body, _t("▶ ПРОДОЛЖИТЬ"), self.app.resume_cargo,
                                   color=GREEN)
        self.btn_cargo.pack(side=tk.RIGHT)
        self.cards: list[MissionCard] = []
        self.set_lang(self.lang)

    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self.app.store.settings["lang"] = lang
        self.btn_en.set_active(lang == "en")
        self.btn_ru.set_active(lang == "ru")
        for c in self.cards:
            c.destroy()
        self.cards = []
        for i, m in enumerate(missions.missions_for(lang)):
            card = MissionCard(self.grid_frame, self.app, m)
            card.grid(row=i // 5, column=i % 5, sticky="nsew", padx=px(4), pady=px(4))
            self.cards.append(card)
        for col in range(5):
            self.grid_frame.grid_columnconfigure(col, weight=1, uniform="mc")
        for row in range(2):
            self.grid_frame.grid_rowconfigure(row, weight=1, uniform="mr")
        self.refresh()

    def refresh(self) -> None:
        for c in self.cards:
            c.redraw()
        weak = self.app.store.weakest_keys(self.lang)
        if weak:
            keys = "  ".join(f"«{ch}» {r * 100:.0f}%" for ch, r in weak)
            self.repair_info.configure(text=_t("Слабые клавиши: {0}\nУпражнение из слов с этими буквами.").format(keys))
        else:
            self.repair_info.configure(text=_t("Пока мало данных: пройдите пару миссий,\nи бортовой компьютер найдёт слабые клавиши."))
        saved = load_session()
        if saved:
            preview = saved.text[:48] + ("…" if len(saved.text) > 48 else "")
            self.cargo_info.configure(
                text=_t("«{0}»\nпройдено {1} из {2} ({3:.0f}%)").format(preview, fmt_int(saved.index), fmt_int(len(saved.text)), saved.index / len(saved.text) * 100))
            self.btn_cargo.set_text(_t("▶ ПРОДОЛЖИТЬ"))
        else:
            self.cargo_info.configure(text=_t("Загрузите книгу или статью и печатайте её\nс переводом предложений (UPLINK)."))
            self.btn_cargo.set_text(_t("ЗАГРУЗИТЬ ТЕКСТ"))


# ===========================================================================
# Свой текст
# ===========================================================================

class CargoScreen(tk.Frame):
    """Подготовка своего текста: загрузка, опции обработки, предпросмотр, старт."""

    OPTIONS = (
        ("lower", _t("Убрать заглавные буквы"),
         _t("«Дом» → «дом». Выключите, чтобы тренировать Shift: тогда регистр учитывается.")),
        ("punct", _t("Убрать знаки препинания"),
         _t("Точки, запятые, кавычки, тире и другие знаки удаляются.")),
        ("spaces", _t("Один пробел между словами"),
         _t("Лишние пробелы, табуляции и переводы строк схлопываются в один пробел.")),
        ("yo", _t("Ё → Е"),
         _t("«Ёлка» → «елка», если привычнее печатать без буквы ё. По умолчанию выкл.")),
        ("translit", _t("Без умлаутов: ä ö ü ß → ae oe ue ss"),
         _t("Для немецких и других книг, если на клавиатуре нет немецкой раскладки. По умолчанию выкл.: буквы как в книге, подсказка — раскладка QWERTZ.")),
    )

    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self._original: str | None = None
        self._readonly = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(2)))
        _label(top, _t("ПОДГОТОВКА ТЕКСТА — ЗАГРУЗКА ГРУЗА"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, "?", lambda: self.app.open_help(), height=30, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        _label(self, _t("1) Откройте файл или вставьте текст  →  2) выберите обработку справа  →  3) проверьте предпросмотр  →  4) «Сохранить на борт» или «Старт». Оригинал текста сохраняется: по нему работает переводчик UPLINK."),
               fg=MUTED, size=9, bg=BG, wraplength=px(900), justify="left").pack(anchor="w", padx=px(16))
        from stamina.adapt import FlowFrame

        tools = FlowFrame(self, bg=BG, padx=6, pady=4)
        tools.pack(fill=tk.X, padx=px(12), pady=px(8))
        for text, cmd, col in (
            (_t("ПОЛКА КНИГ"), self._open_shelf, AMBER),
            (_t("СВОБОДНЫЕ КНИГИ"), self._open_free_books, CYAN),
            (_t("ОТКРЫТЬ ФАЙЛ…"), self._open_file, CYAN),
            (_t("ОТКРЫТЬ PDF…"), self._open_pdf, CYAN),
            (_t("ВСТАВИТЬ ИЗ БУФЕРА"), self._paste, CYAN),
            (_t("ОЧИСТИТЬ"), self._clear, MUTED),
        ):
            tools.add(HudButton(tools, text, cmd, color=col, height=32, font_size=9))
        self.btn_ro = HudButton(tools, _t("ЗАЩИТА ОТ ПРАВКИ: ВЫКЛ"), self._toggle_readonly, color=MUTED,
                                height=32, font_size=9, width=210)
        tools.add(self.btn_ro)
        tools.add(HudButton(tools, _t("ЭКСПОРТ .TXT"), self._export, color=MUTED, height=32, font_size=9))

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill=tk.X, side=tk.BOTTOM, padx=px(12), pady=px(8))
        self.btn_start = HudButton(bottom, _t("▶ НА БОРТ И СТАРТ С НАЧАЛА"), self._start_new,
                                   color=AMBER, height=40, font_size=11)
        self.btn_start.pack(side=tk.RIGHT)
        self.btn_resume = HudButton(bottom, _t("▶ ПРОДОЛЖИТЬ С МЕСТА"), self.app.resume_cargo,
                                    color=GREEN, height=40, font_size=11, width=250)
        self.btn_resume.pack(side=tk.RIGHT, padx=px(8))
        HudButton(bottom, _t("СОХРАНИТЬ НА БОРТ"), lambda: self._start_new(switch=False), color=CYAN,
                  height=40, font_size=11).pack(side=tk.RIGHT)
        self.status = _label(bottom, "", fg=MUTED, size=9, bg=BG, justify="left", anchor="w")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        middle = tk.Frame(self, bg=BG)
        middle.pack(fill=tk.BOTH, expand=True, padx=px(12))
        side = HudPanel(middle, _t("ОБРАБОТКА ТЕКСТА"), accent=AMBER)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(px(8), 0))
        side.configure(width=px(360))
        sb_body = side.body
        self.opt_btns: dict[str, HudButton] = {}
        for key, title, desc in self.OPTIONS:
            row = tk.Frame(sb_body, bg=PANEL)
            row.pack(fill=tk.X, pady=(0, px(8)))
            b = HudButton(row, _t("● ВКЛ"), lambda k=key: self._toggle_opt(k), width=86, height=30, font_size=9)
            b.pack(side=tk.LEFT, anchor="n")
            txt = tk.Frame(row, bg=PANEL)
            txt.pack(side=tk.LEFT, fill=tk.X, padx=(px(8), 0))
            _label(txt, title, size=10, bold=True, anchor="w").pack(anchor="w")
            _label(txt, desc, fg=MUTED, size=8, wraplength=px(240), justify="left").pack(anchor="w")
            self.opt_btns[key] = b
        HudButton(sb_body, _t("✦ ПРИМЕНИТЬ К ТЕКСТУ В ПОЛЕ"), self._apply_to_field, color=AMBER,
                  height=32, font_size=9).pack(fill=tk.X, pady=(0, px(10)))
        tk.Frame(sb_body, bg=LINE, height=1).pack(fill=tk.X)
        _label(sb_body, _t("ПРЕДПРОСМОТР ДЛЯ ТРЕНАЖЁРА"), fg=blend(CYAN, TEXT, 0.3), size=9,
               bold=True).pack(anchor="w", pady=(px(8), px(2)))
        self.preview_info = _label(sb_body, "", fg=AMBER, size=9, bold=True, justify="left", anchor="w")
        self.preview_info.pack(anchor="w")
        self.preview = _label(sb_body, "", fg=TEXT, size=10, mono=True, wraplength=px(330),
                              justify="left", anchor="nw", bg=BG2, padx=px(8), pady=px(6))
        self.preview.pack(fill=tk.BOTH, expand=True, pady=(px(4), 0))

        panel = HudPanel(middle, _t("ТЕКСТ"))
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Hud.Vertical.TScrollbar", background=PANEL_HI, troughcolor=BG2,
                        bordercolor=PANEL, arrowcolor=CYAN, lightcolor=PANEL_HI, darkcolor=PANEL_HI)
        sb = ttk.Scrollbar(panel.body, orient=tk.VERTICAL, style="Hud.Vertical.TScrollbar")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(panel.body, wrap=tk.WORD, undo=True, bg=BG2, fg=TEXT,
                            insertbackground=CYAN, selectbackground=CYAN_DIM, relief=tk.FLAT,
                            font=theme.font(12, mono=True), padx=px(10), pady=px(8),
                            yscrollcommand=sb.set, highlightthickness=1,
                            highlightbackground=LINE, highlightcolor=CYAN_DIM, width=40)
        self.text.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=self.text.yview)
        self.text.bind("<<Modified>>", self._on_modified)
        self._refresh_opts()

    # -- опции --------------------------------------------------------------
    def _opts(self) -> dict:
        opts = self.app.store.settings.setdefault("cargo_opts", {})
        for k in ("lower", "punct", "spaces"):
            opts.setdefault(k, True)
        opts.setdefault("translit", False)
        opts.setdefault("yo", False)
        return opts

    def _toggle_opt(self, key: str) -> None:
        opts = self._opts()
        opts[key] = not opts[key]
        self.app.store.save_settings()
        self._refresh_opts()
        self._update_preview()

    def _refresh_opts(self) -> None:
        opts = self._opts()
        for key, b in self.opt_btns.items():
            on = opts[key]
            b.set_text(_t("● ВКЛ") if on else _t("○ ВЫКЛ"))
            b.set_color(GREEN if on else MUTED)
            b.set_active(on)

    def _process(self, text: str) -> str:
        o = self._opts()
        return process_text(text, lower=o["lower"], punct=o["punct"], spaces=o["spaces"], translit=o["translit"], yo=o["yo"])

    def _toggle_readonly(self) -> None:
        self._readonly = not self._readonly
        self.text.configure(state=tk.DISABLED if self._readonly else tk.NORMAL)
        self.btn_ro.set_text(_t("ЗАЩИТА ОТ ПРАВКИ: ВКЛ") if self._readonly else _t("ЗАЩИТА ОТ ПРАВКИ: ВЫКЛ"))
        self.btn_ro.set_color(AMBER if self._readonly else MUTED)
        self.btn_ro.set_active(self._readonly)

    # -- данные -------------------------------------------------------------
    def refresh(self) -> None:
        self._refresh_opts()
        self._update_preview()

    def load_initial(self, adapted: str, original: str) -> None:
        text = original if original and self._process(original) == adapted else adapted
        self._original = original or None
        self._set(text)

    def _set(self, text: str) -> None:
        ro = self._readonly
        if ro:
            self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", text)
        self.text.edit_modified(False)
        if ro:
            self.text.configure(state=tk.DISABLED)
        self._update_preview()

    def _get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _on_modified(self, _e=None) -> None:
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.after_idle(self._update_preview)

    def _update_preview(self) -> None:
        adapted = self._process(self._get())
        saved = load_session()
        same = bool(saved) and saved.text == adapted
        self.btn_resume.set_enabled(same)
        self.btn_resume.set_text(_t("▶ ПРОДОЛЖИТЬ С {0:.0f}%").format(saved.index / len(saved.text) * 100)
                                 if same else _t("▶ ПРОДОЛЖИТЬ С МЕСТА"))
        if saved and not same:
            self.status.configure(text=_t("На борту другой незаконченный текст."))
        elif same:
            self.status.configure(text=_t("Этот текст уже на борту: пройдено {0} из {1}.").format(fmt_int(saved.index), fmt_int(len(saved.text))))
        else:
            self.status.configure(text="")
        if not adapted:
            self.preview_info.configure(text=_t("Текст пуст"))
            self.preview.configure(text=_t("Откройте файл или вставьте текст."))
            return
        runs = [r for r in self.app.store.stats["runs"][-20:] if r.get("cpm")]
        avg = sum(r["cpm"] for r in runs) / len(runs) if runs else 150
        eta = fmt_time(len(adapted) / max(avg, 30) * 60)
        from stamina import langdetect
        lang = langdetect.name(langdetect.detect(self._original or adapted))
        self.preview_info.configure(text=_t("{0} знаков · {1} · ≈ {2}").format(fmt_int(len(adapted)), lang, eta))
        self.preview.configure(text=adapted[:260] + ("…" if len(adapted) > 260 else ""))

    def _library(self):
        from stamina import library as libmod
        return libmod.Library()

    def _open_shelf(self) -> None:
        from stamina.book_shelf import ShelfDialog, start_typing_from_library
        lib = self._library()
        ShelfDialog(self, lib, opts=self._opts(),
                    on_pick=lambda tid: start_typing_from_library(self.app, lib, tid, parent=self))

    def _open_free_books(self) -> None:
        from stamina.book_shelf import BookSearchDialog, start_typing_from_library
        lib = self._library()

        def after_add(tid: str) -> None:
            if messagebox.askyesno(_t("Печать"),
                                   _t("Книга на полке. Начать набор сейчас?"),
                                   parent=self):
                start_typing_from_library(self.app, lib, tid, parent=self)

        BookSearchDialog(self, lib, opts=self._opts(), on_added=after_add)

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title=_t("Открыть текст"),
                                          filetypes=[(_t("Текст или PDF"), "*.txt *.pdf"),
                                                     (_t("Текстовые файлы"), "*.txt"), ("PDF", "*.pdf"),
                                                     (_t("Все файлы"), "*.*")])
        if not path:
            return
        if path.lower().endswith(".pdf"):
            self._open_pdf(path)
            return
        content = None
        for enc in ("utf-8-sig", "cp1251"):
            try:
                with open(path, encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                messagebox.showerror(_t("Ошибка"), _t("Не удалось открыть файл:\n{0}").format(exc), parent=self)
                return
        if content is None:
            messagebox.showerror(_t("Ошибка"), _t("Не удалось определить кодировку файла."), parent=self)
            return
        self._original = content
        self._set(content)

    def _open_pdf(self, path: str | None = None) -> None:
        """PDF → предпросмотр → текст как из файла (оригинал сохранится в библиотеку при «Сохранить на борт»)."""
        from stamina.pdf_dialog import import_pdf
        res = import_pdf(self, path)
        if res:
            self._original = res[0]
            self._set(res[0])

    def _paste(self) -> None:
        try:
            content = self.clipboard_get()
        except tk.TclError:
            return
        self._original = content
        self._set(content)

    def _clear(self) -> None:
        if self._get().strip() and not messagebox.askyesno(_t("Очистить"), _t("Очистить поле текста?"), parent=self):
            return
        self._original = None
        self._set("")

    def _apply_to_field(self) -> None:
        """Как «Применить все правки» в исходной версии, но по выбранным опциям."""
        if self._original is None:
            self._original = self._get()
        self._set(self._process(self._get()))

    def _export(self) -> None:
        adapted = self._process(self._get())
        if not adapted:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".txt",
                                            title=_t("Сохранить подготовленный текст"),
                                            filetypes=[(_t("Текстовые файлы"), "*.txt")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(adapted)
            except OSError as exc:
                messagebox.showerror(_t("Ошибка"), _t("Не удалось сохранить:\n{0}").format(exc), parent=self)

    def _start_new(self, switch: bool = True) -> None:
        current = self._get()
        adapted = self._process(current)
        if not adapted.strip():
            messagebox.showwarning(_t("Пустой текст"), _t("Введите текст или откройте файл."), parent=self)
            return
        saved = load_session()
        if saved and saved.index > 0:
            pct = saved.index / len(saved.text) * 100
            msg = (_t("Этот текст уже пройден на {0:.0f}%.\nНачать его с самого начала? (Чтобы продолжить — кнопка «Продолжить с места».)").format(pct)) if saved.text == adapted else (
                   _t("На борту незаконченный текст (пройдено {0:.0f}%).\nЗаменить его новым? Прогресс старого текста будет потерян.").format(pct))
            if not messagebox.askyesno(_t("Заменить текст?"), msg, parent=self):
                return
        original = current
        if self._original and self._process(self._original) == adapted:
            original = self._original
        self.app.start_cargo(adapted, original, switch=switch)
        if not switch:
            self._update_preview()
            self.status.configure(text=_t("Текст сохранён на борт. Таймер стартует с первой клавиши на Мостике (Ctrl+1)."), fg=GREEN)
            self.after(5000, lambda: self.status.configure(fg=MUTED))


# ===========================================================================
# Бортжурнал
# ===========================================================================

class LogScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.heat_lang = "en"
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("БОРТЖУРНАЛ — СТАТИСТИКА ПОЛЁТОВ"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, "?", lambda: self.app.open_help(), height=32, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        HudButton(top, _t("★ ДОСКА ПОЧЁТА"), lambda: app.show("honor"), color=AMBER, height=34).pack(
            side=tk.RIGHT, padx=(0, px(8)))
        self.summary = tk.Frame(self, bg=BG)
        self.summary.pack(fill=tk.X, padx=px(10))
        self.cells = []
        for i in range(5):
            p = HudPanel(self.summary, pad=8)
            p.grid(row=0, column=i, sticky="nsew", padx=px(4), pady=px(4))
            self.summary.grid_columnconfigure(i, weight=1, uniform="sum")
            cap = _label(p.body, "", fg=MUTED, size=8, bold=True)
            cap.pack(anchor="w")
            val = _label(p.body, "", fg=CYAN, size=18, bold=True, mono=True)
            val.pack(anchor="w")
            sub = _label(p.body, "", fg=MUTED, size=8)
            sub.pack(anchor="w")
            self.cells.append((cap, val, sub))

        mid = HudPanel(self, _t("ДИНАМИКА — ПОСЛЕДНИЕ 30 ПОЛЁТОВ"))
        mid.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(4))
        self.chart = LineChart(mid.body)
        self.chart.pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=(px(4), px(10)))
        heat = HudPanel(bottom, _t("ТЕПЛОВАЯ КАРТА ОШИБОК (ЗА ВСЁ ВРЕМЯ)"), accent=AMBER)
        heat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(4))
        self.kb = HudKeyboard(heat.body)
        self.kb.pack(fill=tk.BOTH, expand=True)
        row = tk.Frame(heat.body, bg=PANEL)
        row.pack(fill=tk.X)
        self.heat_btns = {}
        for code in ("en", "de", "ru", "uk"):       # раскладка карты: QWERTY / QWERTZ / ЙЦУКЕН RU / ЙЦУКЕН UA
            b = HudButton(row, code.upper().replace("UK", "UA"), lambda c=code: self._heat_lang(c),
                          height=26, font_size=9, width=44)
            b.pack(side=tk.LEFT, padx=(0, px(4)))
            self.heat_btns[code] = b
        # шкала как в веб-версии: цвет вместо цифр на клавишах
        _label(row, "0%", fg=MUTED, size=8).pack(side=tk.LEFT, padx=(px(8), px(2)))
        legend = tk.Canvas(row, bg=PANEL, highlightthickness=0, width=px(160), height=px(12))
        legend.pack(side=tk.LEFT)
        steps = 32
        for i in range(steps):
            x0 = i * px(160) / steps
            legend.create_rectangle(x0, 0, x0 + px(160) / steps + 1, px(12), outline="",
                                    fill=theme.heat_color(i / (steps - 1)))
        _label(row, "≥25%", fg=MUTED, size=8).pack(side=tk.LEFT, padx=(px(2), px(8)))
        _label(row, _t("зелёный — хорошо, янтарный — внимание, красный — нужен ремонт"),
               fg=MUTED, size=8).pack(side=tk.LEFT)

        side = HudPanel(bottom, _t("СЛАБЫЕ КЛАВИШИ"))
        side.pack(side=tk.LEFT, fill=tk.BOTH, padx=px(4))
        # Порт из веб-версии: мини-клавиши с цветом тепловой карты, 2 колонки, до 12 клавиш
        self.weak_canvas = tk.Canvas(side.body, bg=PANEL, highlightthickness=0, bd=0,
                                     width=px(300), height=px(60))
        self.weak_canvas.pack(fill=tk.BOTH, expand=True)
        self.weak_canvas.bind("<Configure>", lambda _e: self._draw_weak())
        self._weak_rows: list[tuple[str, float, int, int]] = []
        HudButton(side.body, _t("⚙ РЕМОНТ СЛАБЫХ КЛАВИШ"), lambda: self.app.start_repair(self.heat_lang),
                  color=AMBER).pack(fill=tk.X, pady=(px(6), 0))
        HudButton(side.body, _t("СБРОСИТЬ СТАТИСТИКУ"), self._reset, color=RED, height=28,
                  font_size=8).pack(fill=tk.X, pady=(px(6), 0))

    def _heat_lang(self, lang: str) -> None:
        self.heat_lang = lang
        self.refresh()

    def _reset(self) -> None:
        if messagebox.askyesno(_t("Сброс статистики"),
                               _t("Удалить всю статистику: историю полётов, звёзды миссий, звание и тепловую карту?\nЭто нельзя отменить."), parent=self):
            self.app.store.reset_stats()
            self.app.update_rank()
            self.refresh()
            self.app.screens["missions"].refresh()

    def refresh(self) -> None:
        st = self.app.store.stats
        runs = [r for r in st["runs"] if r.get("typed", 0) > 0]
        last10 = runs[-10:]
        best = max((r.get("cpm", 0) for r in runs), default=0)
        avg_acc = sum(r.get("acc", 0) for r in last10) / len(last10) if last10 else 0
        avg_cpm = sum(r.get("cpm", 0) for r in last10) / len(last10) if last10 else 0
        rank, lo, hi = missions.rank_for(st["xp"])
        rank = theme.skin_rank(rank)
        done = sum(1 for v in st["missions"].values() if v.get("stars"))
        stars = sum(v.get("stars", 0) for v in st["missions"].values())
        data = [
            (_t("ВРЕМЯ В ПОЛЁТЕ"), fmt_time(st["total_time"]), _t("{0} полётов").format(len(runs)), CYAN),
            (_t("НАБРАНО ЗНАКОВ"), fmt_int(st["total_chars"]), _t("правильно набранных"), CYAN),
            (_t("ЛУЧШАЯ СКОРОСТЬ"), f"{best:.0f}", _t("средняя (10 последних): {0:.0f}").format(avg_cpm), GREEN),
            (_t("ТОЧНОСТЬ"), f"{avg_acc:.1f}%", _t("средняя за 10 полётов"), AMBER),
            (_t("ЗВАНИЕ"), rank.upper(), f"{st['xp']} XP" + (_t(" · до след. {0}").format(hi - st['xp']) if hi else "")
             + _t(" · миссий {0}/20 · ★{1}").format(done, stars), AMBER),
        ]
        for (cap, val, sub), (c, v, s, col) in zip(self.cells, data):
            cap.configure(text=c)
            val.configure(text=v, fg=col, font=theme.font(18 if len(v) < 12 else 12, True, mono=True))
            sub.configure(text=s)
        self.chart.set_runs(runs)
        for code, b in self.heat_btns.items():
            b.set_active(self.heat_lang == code)
        self.kb.set_lang(self.heat_lang)
        self.kb.set_heat(self.app.store.key_error_rates(min_total=5))
        weak = self.app.store.weakest_keys(self.heat_lang, count=12)
        self._weak_rows = []
        for ch, r in weak:
            hits, misses = st["keys"].get(ch, [0, 0])
            self._weak_rows.append((ch, r, misses, hits + misses))
        self._draw_weak()

    def _draw_weak(self) -> None:
        c = self.weak_canvas
        c.delete("all")
        w = max(c.winfo_width(), px(200))
        if not self._weak_rows:
            c.create_text(px(4), px(4), anchor="nw", fill=MUTED, font=theme.font(10),
                          width=w - px(8),
                          text=_t("Данных пока мало.\nПечатайте —\nкомпьютер считает\nошибки по каждой\nклавише."))
            return
        col_w = w / 2
        key, gap = px(30), px(8)
        for i, (ch, r, misses, total) in enumerate(self._weak_rows):
            per_col = max(1, int((c.winfo_height() - px(4)) / (key + gap)))  # без обрезки и прокрутки
            if i >= per_col * 2:
                break
            col, row = i // per_col, i % per_col       # сначала левая колонка, потом правая
            x = col * col_w + px(2)
            y = row * (key + gap) + px(2)
            fill = theme.heat_fill(r)
            c.create_polygon(theme.chamfer(x, y, x + key, y + key, px(5)), fill=fill,
                             outline=blend(fill, "#FFFFFF", 0.35))
            c.create_text(x + key / 2, y + key / 2, text="␣" if ch == " " else ch.upper(),
                          fill="#FFFFFF", font=theme.font(11, True, mono=True))
            c.create_text(x + key + px(6), y + key * 0.32, anchor="w", fill=TEXT,
                          font=theme.font(10, True, mono=True), text=f"{r * 100:.0f}%")
            c.create_text(x + key + px(6), y + key * 0.76, anchor="w", fill=MUTED,
                          font=theme.font(8), text=_t("({0} из {1})").format(misses, total))


# ===========================================================================
# Настройки
# ===========================================================================

class SettingsScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, _t("НАСТРОЙКИ БОРТОВЫХ СИСТЕМ"), size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, "?", lambda: self.app.open_help(), height=30, font_size=10,
                  width=32, color=AMBER).pack(side=tk.RIGHT)
        # без прокрутки, как в веб-версии: вкладки СИСТЕМЫ / ЕЩЁ / СКИНЫ / ЭКИПАЖ
        self.tabbar = tk.Frame(self, bg=BG)
        self.tabbar.pack(fill=tk.X, padx=px(14), pady=(px(4), 0))
        host = tk.Frame(self, bg=BG)
        host.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(8))
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        self.tabs: dict[str, tk.Misc] = {}
        self.tab_btns: dict[str, HudButton] = {}
        for key, title in (("systems", _t("СИСТЕМЫ")), ("more", _t("ЕЩЁ")), ("skins", _t("СКИНЫ")),
                           ("crew", _t("ЭКИПАЖ"))):
            pnl = HudPanel(host, title)
            pnl.grid(row=0, column=0, sticky="nsew")
            inner = tk.Frame(pnl.body, bg=PANEL)
            inner.pack(fill=tk.BOTH, expand=True)
            self.tabs[key] = (pnl, inner)
            b = HudButton(self.tabbar, f"{title} · Alt+{len(self.tabs)}", lambda k=key: self.show_tab(k),
                          height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(3))
            b.nav_menu = True
            self.tab_btns[key] = b
        _label(self.tabbar, _t("Ctrl+Tab — следующая вкладка · Tab, стрелки — по кнопкам · Enter/пробел — нажать"),
               fg=MUTED, size=8, bg=BG).pack(side=tk.RIGHT)
        self.body = self.tabs["systems"][1]
        self.toggles: dict[str, HudButton] = {}
        self._row_i = 0
        from stamina import i18n
        lr = self._row(_t("Язык интерфейса"), _t("Русский, українська, English, Deutsch. Меняются надписи программы; тексты для печати, словари и книги остаются как есть. Новый язык включится после перезапуска — кнопка «ПЕРЕЗАПУСТИТЬ» сделает это сразу (прогресс сохранится)."))
        self.lang_btns = {}
        for code, name in i18n.LANGS.items():
            b = HudButton(lr, name, lambda c=code: self._set_lang(c), height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(3))
            self.lang_btns[code] = b
        self.btn_restart = HudButton(lr, _t("⟳ ПЕРЕЗАПУСТИТЬ"), self._restart, color=AMBER, height=30, font_size=9)
        self._toggle_row("sound", _t("Звук клавиш"), _t("Щелчок печатной машинки на верную клавишу, «бззт» — на ошибку, колокольчик — в конце миссии. Горячая клавиша F9."))
        vol = self._row(_t("Громкость"), _t("Звуки синтезированы программой, лежат в stamina/sounds."))
        self.vol_btns = {}
        for lvl in (1, 2, 3, 4):
            b = HudButton(vol, "▮" * lvl, lambda l=lvl: self._set_volume(l), width=64, height=30)
            b.pack(side=tk.LEFT, padx=px(3))
            self.vol_btns[lvl] = b
        HudButton(vol, _t("ПРОВЕРИТЬ"), self._test_sound, color=AMBER, height=30,
                  font_size=9).pack(side=tk.LEFT, padx=px(10))
        self._toggle_row("translator", _t("Переводчик UPLINK"),
                         _t("Перевод текущего предложения своего текста через интернет (Google / MyMemory). Кэш: папка cache рядом с программой."))
        up = self._row(_t("UPLINK: перевод на"), _t("Язык книги определяется сам (немецкий, английский, русский, украинский…). Перевод — на выбранный язык; АВТО — язык интерфейса. Русский или украинский текст переводится на английский. Нужен интернет (Google / MyMemory); без сети — только уже переведённые фразы из кэша."))
        self.up_btns = {}
        for code, name in (("", _t("АВТО")), ("ru", "RU"), ("uk", "UK"), ("en", "EN"), ("de", "DE")):
            b = HudButton(up, name, lambda c=code: self._set_uplink(c), height=30, font_size=9,
                          width=None if code == "" else 52)
            b.pack(side=tk.LEFT, padx=px(3))
            self.up_btns[code] = b
        self._toggle_row("stars", _t("Звёздное поле"), _t("Звёзды в иллюминаторе летят быстрее, когда вы печатаете быстрее. Выключите, если ноутбук греется."))
        self.body = self.tabs["skins"][1]
        sk = self._row(_t("Скин пульта"), _t("Оформление всего корабля: цвета, рамки, настроение. Тот же выбор — на экране «ВХОД В КАБИНУ». Сохраняется у пилота."))
        self.skin_btns: dict[str, HudButton] = {}
        for tmeta in theme.list_themes():
            tid = tmeta["id"]
            label = theme.theme_display_name(tmeta["data"])
            b = HudButton(sk, label, lambda k=tid: self._set_skin(k), height=30, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2), pady=px(1))
            self.skin_btns[tid] = b
        sk.grid_configure(row=1, column=0, sticky="w", padx=0, pady=(px(4), 0))  # кнопки под описанием — без обрезки
        from stamina.idle import IDLE_MINUTES
        idl = self._row(_t("Простой: слайдшоу и радио"),
                        _t("Если долго не трогать клавиатуру, включается слайдшоу в стиле скина и радио той же тематики. Первое нажатие закрывает его и не засчитывается в набор. Работает в скинах со слайдшоу («Старая Англия»); картинки — Wikimedia Commons, без сети — фото скина."))
        self.idle_btns = {}
        for m in IDLE_MINUTES:
            b = HudButton(idl, _t("ВЫКЛ") if m == 0 else _t("{0} мин").format(m),
                          lambda k=m: self._set_idle("idle_minutes", k), width=56, height=30, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            self.idle_btns[m] = b
        HudButton(idl, _t("▶ ПОКАЗАТЬ СЕЙЧАС"), self._idle_now, height=30, font_size=8,
                  color=AMBER).pack(side=tk.LEFT, padx=px(6))
        irr = self._row(_t("Радио под скин"),
                        _t("Станция подбирается по жанрам скина, громкость плавно растёт до ~30 %. Если радио уже играет — его не трогаем."))
        self.idle_radio_btn = HudButton(irr, _t("ВКЛ"), lambda: self._set_idle("idle_radio", None),
                                        width=90, height=30, font_size=8)
        self.idle_radio_btn.pack(side=tk.LEFT, padx=px(2))
        tk.Label(irr, text=_t("После закрытия") + ":", bg=PANEL, fg=MUTED,
                 font=theme.font(8)).pack(side=tk.LEFT, padx=(px(8), px(2)))
        self.idle_after_btns = {}
        for k, name in (("stop", _t("ВЫКЛЮЧИТЬ РАДИО")), ("keep", _t("ОСТАВИТЬ РАДИО"))):
            b = HudButton(irr, name, lambda v=k: self._set_idle("idle_after", v), height=30, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            self.idle_after_btns[k] = b
        self.body = self.tabs["more"][1]
        ls = self._row(_t("Живой космос"), _t("Во всех разделах за стеклянными панелями летят звёзды, кометы, планеты и астероиды. «Лёгкий» (по умолчанию) — меньше объектов и кадров, «Полный» — плавнее (до 24 к/с). Нужен Pillow. При «уменьшении движения» Windows картинка неподвижна."))
        self.ls_btns = {}
        for key, name in (("off", _t("ВЫКЛ")), ("light", _t("ЛЁГКИЙ")), ("full", _t("ПОЛНЫЙ"))):
            b = HudButton(ls, name, lambda k=key: self._set_living(k), width=72, height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(2))
            self.ls_btns[key] = b
        from stamina import living_space as _ls
        if not _ls.available():   # без Pillow — понятная подсказка вместо «ничего не происходит»
            from stamina.deps import pillow_hint
            tk.Label(ls, text=pillow_hint(), fg=AMBER, bg=PANEL, font=theme.font(8, True),
                     wraplength=px(280), justify="left").pack(side=tk.LEFT, padx=px(6))
        typ = self._row(_t("Набор на мостике"),
                        _t("Прицел, мигание буквы, клавиатура, зоны пальцев, размеры, шрифты и цвета строки набора переехали в «МОСТИК → НАСТРОЙКИ»."))
        HudButton(typ, _t("⚙ МОСТИК → НАСТРОЙКИ"), lambda: self.app.show("bridge_settings"), height=30,
                  font_size=9, color=AMBER).pack(side=tk.LEFT)
        self.font_btns = {}
        ui = self._row(_t("Размер интерфейса"),
                      _t("Шрифты и отступы во всём приложении. Новый размер полностью применится после перезапуска — кнопка «ПЕРЕЗАПУСТИТЬ» выше (прогресс сохранится)."))
        self.ui_btns = {}
        for key, name in (("S", _t("МЕЛКИЙ")), ("M", _t("ОБЫЧНЫЙ")), ("L", _t("КРУПНЫЙ")), ("XL", _t("ОЧЕНЬ КРУПНЫЙ"))):
            b = HudButton(ui, name, lambda k=key: self._set_ui_scale(k), height=30, font_size=8)
            b.pack(side=tk.LEFT, padx=px(2))
            self.ui_btns[key] = b
        data = self._row(_t("Данные"), _t("Статистика и прогресс: {0}").format(DATA_DIR))
        HudButton(data, _t("ОТКРЫТЬ ПАПКУ"), self._open_data, height=30, font_size=9).pack(side=tk.LEFT)
        self.body = self.tabs["crew"][1]
        cr = self._row(_t("Пилот"), _t("Смена пилота, личное дело, экспорт и доска почёта — то же меню, что по клику на звание в шапке."))
        HudButton(cr, _t("⇄  СМЕНИТЬ ПИЛОТА   Ctrl+Shift+P"), lambda: self.app.switch_pilot(), height=30,
                  font_size=9).pack(side=tk.LEFT, padx=px(2))
        HudButton(cr, _t("✎  ЛИЧНОЕ ДЕЛО"), lambda: self.app.edit_pilot(), height=30,
                  font_size=9).pack(side=tk.LEFT, padx=px(2))
        cr2 = self._row(_t("Экспорт и почёт"), _t("Файл пилота для переноса на другой компьютер; таблица рекордов экипажа."))
        HudButton(cr2, _t("⇪  ЭКСПОРТ ПИЛОТА"), lambda: self.app.export_pilot(), height=30,
                  font_size=9).pack(side=tk.LEFT, padx=px(2))
        HudButton(cr2, _t("★  ДОСКА ПОЧЁТА"), lambda: self.app.show("honor"), height=30,
                  font_size=9, color=AMBER).pack(side=tk.LEFT, padx=px(2))
        self.body = self.tabs["more"][1]
        _label(self.body, _t("Горячие клавиши:  F1 — справка  ·  F5 — заново  ·  Esc — пауза  ·  F9 — звук  ·  Ctrl+1…6 — разделы · F11 — экран  ·  в отчёте: Enter — повторить, → — следующая, R — ремонт"),
               fg=MUTED, size=9).pack(anchor="w", pady=(px(14), 0))
        self.show_tab("systems")
        self.refresh()

    def page_help_key(self) -> str:
        return "settings." + getattr(self, "current_tab", "systems")

    def tab_keys(self) -> list[str]:
        return list(self.tabs)

    def show_tab(self, key: str) -> None:
        self.current_tab = key
        tk.Misc.tkraise(self.tabs[key][0])
        for k, b in self.tab_btns.items():
            b.set_active(k == key)

    def _row(self, title: str, desc: str) -> tk.Frame:
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=px(5))
        row.columnconfigure(0, weight=1, minsize=px(160))
        left = tk.Frame(row, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew")
        _label(left, title, size=11, bold=True).pack(anchor="w")
        _label(left, desc, fg=MUTED, size=8, wraplength=px(640), justify="left").pack(anchor="w")
        right = tk.Frame(row, bg=PANEL)
        right.grid(row=0, column=1, sticky="ne", padx=(px(10), 0))
        tk.Frame(self.body, bg=LINE, height=1).pack(fill=tk.X)
        return right

    def _toggle_row(self, key: str, title: str, desc: str) -> None:
        right = self._row(title, desc)
        b = HudButton(right, _t("ВКЛ"), lambda: self._toggle(key), width=110, height=30)
        b.pack(side=tk.LEFT)
        self.toggles[key] = b

    def _toggle(self, key: str) -> None:
        st = self.app.store.settings
        st[key] = not st.get(key)
        self.app.apply_settings()
        self.refresh()

    def _set_volume(self, lvl: int) -> None:
        self.app.store.settings["volume"] = lvl
        self.app.apply_settings()
        self.refresh()
        self._test_sound()

    def _set_living(self, key: str) -> None:
        self.app.store.settings["living_space"] = key
        self.app.apply_settings()
        self.refresh()
        for k, b in self.ls_btns.items():
            b.set_active(k == key)

    def _set_skin(self, key: str) -> None:
        self.app.store.settings["skin"] = key
        self.app.apply_settings()
        self.refresh()
        for k, b in getattr(self, "skin_btns", {}).items():
            b.set_active(k == key)

    def _set_idle(self, key: str, val) -> None:
        st = self.app.store.settings
        st[key] = (not st.get(key, True)) if val is None else val
        self.app.store.save_settings()
        self.refresh()

    def _idle_now(self) -> None:
        ctl = getattr(self.app, "idle", None)
        if ctl is None:
            return
        from stamina.idle.overlay import skin_slideshow
        if not skin_slideshow():
            messagebox.showinfo(_t("Простой: слайдшоу и радио"),
                                _t("У этого скина нет слайдшоу — выберите «Старую Англию»."), parent=self)
            return
        self.after(150, ctl.open)

    def _set_uplink(self, code: str) -> None:
        self.app.store.settings["uplink_target"] = code
        self.app.store.save_settings()
        self.refresh()

    def _set_lang(self, code: str) -> None:
        from stamina import i18n
        try:
            i18n.save_language(code)
        except OSError as exc:
            messagebox.showerror(_t("Язык интерфейса"), str(exc), parent=self)
            return
        self.refresh()

    def _restart(self) -> None:
        from stamina.app import relaunch
        self.app._save_all()
        if relaunch():
            self.app.destroy()

    def _set_ui_scale(self, key: str) -> None:
        from stamina import theme as th
        key = th.set_ui_scale(key)
        self.app.store.settings["ui_scale"] = key
        self.app.apply_settings()
        self.refresh()
        self.btn_restart.pack(side=tk.LEFT, padx=px(8))  # как при смене языка — нужен перезапуск

    def _test_sound(self) -> None:
        snd = self.app.sound
        if not snd.available:
            messagebox.showinfo(_t("Звук"), _t("Звук недоступен: в Windows он встроен, в Linux нужен aplay или paplay (пакет alsa-utils)."), parent=self)
            return
        snd.enabled = True
        snd.click()
        self.after(160, snd.click)
        self.after(320, snd.error)
        self.after(650, lambda: setattr(snd, "enabled", self.app.store.settings["sound"]))

    def _open_data(self) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(str(DATA_DIR))  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(DATA_DIR)])
        except (AttributeError, OSError):
            messagebox.showinfo(_t("Данные"), str(DATA_DIR), parent=self)

    def refresh(self) -> None:
        st = self.app.store.settings
        for key, b in self.toggles.items():
            on = bool(st.get(key))
            b.set_text(_t("● ВКЛ") if on else _t("○ ВЫКЛ"))
            b.set_color(GREEN if on else MUTED)
            b.set_active(on)
        for lvl, b in self.vol_btns.items():
            b.set_active(st.get("volume") == lvl)
        for k, b in getattr(self, "ls_btns", {}).items():
            b.set_active(k == st.get("living_space", "light"))
        for k, b in getattr(self, "skin_btns", {}).items():
            b.set_active(k == st.get("skin", "spaceship"))
        for k, b in self.font_btns.items():
            b.set_active(st.get("font") == k)
        for k, b in getattr(self, "ui_btns", {}).items():
            b.set_active(st.get("ui_scale", "M") == k)
        for k, b in getattr(self, "up_btns", {}).items():
            b.set_active(k == (st.get("uplink_target") or ""))
        from stamina.idle import settings_of
        idl = settings_of(st)
        for k, b in getattr(self, "idle_btns", {}).items():
            b.set_active(k == idl["idle_minutes"])
        if hasattr(self, "idle_radio_btn"):
            on = bool(idl["idle_radio"])
            self.idle_radio_btn.set_text(_t("● ВКЛ") if on else _t("○ ВЫКЛ"))
            self.idle_radio_btn.set_active(on)
        for k, b in getattr(self, "idle_after_btns", {}).items():
            b.set_active(k == idl["idle_after"])
        from stamina import i18n
        chosen = i18n.saved_language() or i18n.language()
        for k, b in getattr(self, "lang_btns", {}).items():
            b.set_active(k == chosen)
        if chosen != i18n.language():
            self.btn_restart.pack(side=tk.LEFT, padx=(px(10), 0))
        else:
            self.btn_restart.pack_forget()


# ===========================================================================
# Справка (F1)
# ===========================================================================

class HelpScreen(tk.Frame):
    """Показывает ИНСТРУКЦИЯ.md с простой разметкой."""

    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        panel = HudPanel(self, _t("СПРАВКА — ИНСТРУКЦИЯ ПО УПРАВЛЕНИЮ КОСМОЛЁТОМ STAR TYPING"))
        panel.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(10))
        sb = ttk.Scrollbar(panel.body, orient=tk.VERTICAL, style="Hud.Vertical.TScrollbar")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        t = tk.Text(panel.body, wrap=tk.WORD, bg=BG2, fg=TEXT, relief=tk.FLAT, padx=px(18),
                    pady=px(12), yscrollcommand=sb.set, font=theme.font(11),
                    highlightthickness=0, cursor="arrow", spacing1=px(2), spacing3=px(2))
        t.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=t.yview)
        t.tag_configure("h1", font=theme.font(20, True), foreground=CYAN, spacing1=px(6), spacing3=px(8))
        t.tag_configure("h2", font=theme.font(15, True), foreground=AMBER, spacing1=px(14), spacing3=px(4))
        t.tag_configure("h3", font=theme.font(12, True), foreground=CYAN, spacing1=px(8))
        t.tag_configure("table", font=theme.font(10, mono=True), foreground=TEXT)
        t.tag_configure("quote", foreground=AMBER, lmargin1=px(16), lmargin2=px(16))
        t.tag_configure("bullet", lmargin1=px(10), lmargin2=px(26))
        t.tag_configure("muted", foreground=MUTED)
        self.text = t
        self._load()
        t.configure(state=tk.DISABLED)

    def goto(self, chapter: str | None) -> None:
        """Прокрутить к заголовку h2, содержащему chapter (None — в начало)."""
        t = self.text
        if not chapter:
            t.yview_moveto(0)
            return
        rng = t.tag_ranges("h2")
        for i in range(0, len(rng), 2):
            if chapter.lower() in t.get(rng[i], rng[i + 1]).lower():
                t.yview(rng[i])
                return

    def _load(self) -> None:
        from stamina.storage import PROJECT_DIR
        try:
            lines = (PROJECT_DIR / _t("ИНСТРУКЦИЯ.md")).read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = [_t("# Инструкция не найдена"), _t("Файл ИНСТРУКЦИЯ.md должен лежать рядом с main.py.")]
        t = self.text
        buf: list[str] = []
        buf_tag = [""]

        def flush():
            if buf:
                t.insert(tk.END, " ".join(buf) + "\n", buf_tag[0] or ())
                buf.clear()
            buf_tag[0] = ""

        for line in lines:
            raw = line.rstrip()
            clean = raw.replace("**", "").replace("`", "")
            if not raw.strip():
                flush()
                t.insert(tk.END, "\n")
            elif raw.startswith("#"):
                flush()
                level = len(raw) - len(raw.lstrip("#"))
                tag = {1: "h1", 2: "h2"}.get(level, "h3")
                t.insert(tk.END, clean.lstrip("#").strip() + "\n", tag)
            elif raw.startswith("|"):
                flush()
                cells = [c.strip() for c in clean.strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                t.insert(tk.END, "   " + "  │  ".join(cells) + "\n", "table")
            elif raw.strip() == "---":
                flush()
                t.insert(tk.END, "─" * 60 + "\n", "muted")
            elif raw.startswith("- ") or raw[:3].rstrip(".").isdigit() and raw[1:3].startswith(". "):
                flush()
                buf.append(("•  " + clean[2:]) if raw.startswith("- ") else clean)
                buf_tag[0] = "bullet"
            elif raw.startswith("> "):
                if buf_tag[0] != "quote":
                    flush()
                buf.append(clean[2:])
                buf_tag[0] = "quote"
            else:
                buf.append(clean.strip())
        flush()
