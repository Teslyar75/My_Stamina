"""Экраны «Миссии», «Свой текст», «Бортжурнал», «Настройки»."""

from __future__ import annotations

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
            info = f"новые клавиши: {keys}"
        else:
            info = "все буквы, настоящие слова"
        self.create_text(px(14), px(60), text=info, anchor="w", fill=MUTED, font=theme.font(8),
                         width=w - px(24))
        new = self.m["new"]
        if not new:
            caps = ["A–Z"] if self.m["lang"] == "en" else ["А–Я"]
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
        self.create_text(px(14), h - px(20), text=f"цель {self.m['goal']} зн/мин", anchor="w",
                         fill=CYAN_DIM, font=theme.font(8, True))
        if not unlocked:
            self.create_text(w - px(12), h - px(20), text="⊘ ЗАКРЫТО", anchor="e", fill=FAINT,
                             font=theme.font(8, True))
        else:
            self.create_text(w - px(12), h - px(21), text="★" * stars + "☆" * (3 - stars),
                             anchor="e", fill=AMBER, font=theme.font(13))
            if rec.get("best_cpm"):
                self.create_text(w - px(12), h - px(40), text=f"рекорд {rec['best_cpm']:.0f}",
                                 anchor="e", fill=MUTED, font=theme.font(7))


class MissionsScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.lang = app.store.settings.get("lang", "en")
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, "ЗВЁЗДНАЯ КАРТА МИССИЙ", fg=TEXT, size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        self.btn_ru = HudButton(top, "РУССКИЙ  ЙЦУКЕН", lambda: self.set_lang("ru"), height=32)
        self.btn_ru.pack(side=tk.RIGHT)
        self.btn_en = HudButton(top, "ENGLISH  QWERTY", lambda: self.set_lang("en"), height=32)
        self.btn_en.pack(side=tk.RIGHT, padx=px(8))
        _label(self, "Каждая миссия добавляет новые клавиши. Пройдите с точностью от "
                     f"{missions.PASS_ACCURACY:.0f}%, чтобы открыть следующую. Звёзды дают за "
                     "точность и скорость.", fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(16))
        self.grid_frame = tk.Frame(self, bg=BG)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(8))
        special = tk.Frame(self, bg=BG)
        special.pack(fill=tk.X, padx=px(10), pady=(0, px(10)))
        self.repair_panel = HudPanel(special, "РЕМОНТ СИСТЕМ — АДАПТИВНАЯ ТРЕНИРОВКА", accent=AMBER)
        self.repair_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(4), px(6)))
        self.repair_info = _label(self.repair_panel.body, "", fg=TEXT, size=10, justify="left",
                                  anchor="w")
        self.repair_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(self.repair_panel.body, "⚙ ЗАПУСТИТЬ", lambda: self.app.start_repair(self.lang),
                  color=AMBER).pack(side=tk.RIGHT)
        self.cargo_panel = HudPanel(special, "СВОЙ ТЕКСТ — ГРУЗ НА БОРТУ")
        self.cargo_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(px(6), px(4)))
        self.cargo_info = _label(self.cargo_panel.body, "", fg=TEXT, size=10, justify="left",
                                 anchor="w")
        self.cargo_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_cargo = HudButton(self.cargo_panel.body, "▶ ПРОДОЛЖИТЬ", self.app.resume_cargo,
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
            self.repair_info.configure(text=f"Слабые клавиши: {keys}\nУпражнение из слов с этими буквами.")
        else:
            self.repair_info.configure(text="Пока мало данных: пройдите пару миссий,\n"
                                            "и бортовой компьютер найдёт слабые клавиши.")
        saved = load_session()
        if saved:
            preview = saved.text[:48] + ("…" if len(saved.text) > 48 else "")
            self.cargo_info.configure(
                text=f"«{preview}»\nпройдено {fmt_int(saved.index)} из {fmt_int(len(saved.text))} "
                     f"({saved.index / len(saved.text) * 100:.0f}%)")
            self.btn_cargo.set_text("▶ ПРОДОЛЖИТЬ")
        else:
            self.cargo_info.configure(text="Загрузите книгу или статью и печатайте её\n"
                                           "с переводом предложений (UPLINK).")
            self.btn_cargo.set_text("ЗАГРУЗИТЬ ТЕКСТ")


# ===========================================================================
# Свой текст
# ===========================================================================

class CargoScreen(tk.Frame):
    """Подготовка своего текста: загрузка, опции обработки, предпросмотр, старт."""

    OPTIONS = (
        ("lower", "Убрать заглавные буквы",
         "«Дом» → «дом». Выключите, чтобы тренировать Shift: тогда регистр учитывается."),
        ("punct", "Убрать знаки препинания",
         "Точки, запятые, кавычки, тире и другие знаки удаляются."),
        ("spaces", "Один пробел между словами",
         "Лишние пробелы, табуляции и переводы строк схлопываются в один пробел."),
    )

    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self._original: str | None = None
        self._readonly = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(2)))
        _label(top, "ПОДГОТОВКА ТЕКСТА — ЗАГРУЗКА ГРУЗА", size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        _label(self, "1) Откройте файл или вставьте текст  →  2) выберите обработку справа  →  "
                     "3) проверьте предпросмотр  →  4) «Сохранить на борт» или «Старт». "
                     "Оригинал текста сохраняется: по нему работает переводчик UPLINK.",
               fg=MUTED, size=9, bg=BG, wraplength=px(1150), justify="left").pack(anchor="w", padx=px(16))

        tools = tk.Frame(self, bg=BG)
        tools.pack(fill=tk.X, padx=px(12), pady=px(8))
        for text, cmd, col in (
            ("ОТКРЫТЬ ФАЙЛ…", self._open_file, CYAN),
            ("ВСТАВИТЬ ИЗ БУФЕРА", self._paste, CYAN),
            ("ОЧИСТИТЬ", self._clear, MUTED),
        ):
            HudButton(tools, text, cmd, color=col, height=32, font_size=9).pack(side=tk.LEFT, padx=(0, px(6)))
        self.btn_ro = HudButton(tools, "ЗАЩИТА ОТ ПРАВКИ: ВЫКЛ", self._toggle_readonly, color=MUTED,
                                height=32, font_size=9, width=210)
        self.btn_ro.pack(side=tk.LEFT, padx=(px(10), 0))
        HudButton(tools, "ЭКСПОРТ .TXT", self._export, color=MUTED, height=32,
                  font_size=9).pack(side=tk.RIGHT)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill=tk.X, side=tk.BOTTOM, padx=px(12), pady=px(8))
        self.btn_start = HudButton(bottom, "▶ НА БОРТ И СТАРТ С НАЧАЛА", self._start_new,
                                   color=AMBER, height=40, font_size=11)
        self.btn_start.pack(side=tk.RIGHT)
        self.btn_resume = HudButton(bottom, "▶ ПРОДОЛЖИТЬ С МЕСТА", self.app.resume_cargo,
                                    color=GREEN, height=40, font_size=11, width=250)
        self.btn_resume.pack(side=tk.RIGHT, padx=px(8))
        HudButton(bottom, "СОХРАНИТЬ НА БОРТ", lambda: self._start_new(switch=False), color=CYAN,
                  height=40, font_size=11).pack(side=tk.RIGHT)
        self.status = _label(bottom, "", fg=MUTED, size=9, bg=BG, justify="left", anchor="w")
        self.status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        middle = tk.Frame(self, bg=BG)
        middle.pack(fill=tk.BOTH, expand=True, padx=px(12))
        side = HudPanel(middle, "ОБРАБОТКА ТЕКСТА", accent=AMBER)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(px(8), 0))
        side.configure(width=px(360))
        sb_body = side.body
        self.opt_btns: dict[str, HudButton] = {}
        for key, title, desc in self.OPTIONS:
            row = tk.Frame(sb_body, bg=PANEL)
            row.pack(fill=tk.X, pady=(0, px(8)))
            b = HudButton(row, "● ВКЛ", lambda k=key: self._toggle_opt(k), width=86, height=30, font_size=9)
            b.pack(side=tk.LEFT, anchor="n")
            txt = tk.Frame(row, bg=PANEL)
            txt.pack(side=tk.LEFT, fill=tk.X, padx=(px(8), 0))
            _label(txt, title, size=10, bold=True, anchor="w").pack(anchor="w")
            _label(txt, desc, fg=MUTED, size=8, wraplength=px(240), justify="left").pack(anchor="w")
            self.opt_btns[key] = b
        HudButton(sb_body, "✦ ПРИМЕНИТЬ К ТЕКСТУ В ПОЛЕ", self._apply_to_field, color=AMBER,
                  height=32, font_size=9).pack(fill=tk.X, pady=(0, px(10)))
        tk.Frame(sb_body, bg=LINE, height=1).pack(fill=tk.X)
        _label(sb_body, "ПРЕДПРОСМОТР ДЛЯ ТРЕНАЖЁРА", fg=blend(CYAN, TEXT, 0.3), size=9,
               bold=True).pack(anchor="w", pady=(px(8), px(2)))
        self.preview_info = _label(sb_body, "", fg=AMBER, size=9, bold=True, justify="left", anchor="w")
        self.preview_info.pack(anchor="w")
        self.preview = _label(sb_body, "", fg=TEXT, size=10, mono=True, wraplength=px(330),
                              justify="left", anchor="nw", bg=BG2, padx=px(8), pady=px(6))
        self.preview.pack(fill=tk.BOTH, expand=True, pady=(px(4), 0))

        panel = HudPanel(middle, "ТЕКСТ")
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
            b.set_text("● ВКЛ" if on else "○ ВЫКЛ")
            b.set_color(GREEN if on else MUTED)
            b.set_active(on)

    def _process(self, text: str) -> str:
        o = self._opts()
        return process_text(text, lower=o["lower"], punct=o["punct"], spaces=o["spaces"])

    def _toggle_readonly(self) -> None:
        self._readonly = not self._readonly
        self.text.configure(state=tk.DISABLED if self._readonly else tk.NORMAL)
        self.btn_ro.set_text("ЗАЩИТА ОТ ПРАВКИ: ВКЛ" if self._readonly else "ЗАЩИТА ОТ ПРАВКИ: ВЫКЛ")
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
        self.btn_resume.set_text(f"▶ ПРОДОЛЖИТЬ С {saved.index / len(saved.text) * 100:.0f}%"
                                 if same else "▶ ПРОДОЛЖИТЬ С МЕСТА")
        if saved and not same:
            self.status.configure(text="На борту другой незаконченный текст.")
        elif same:
            self.status.configure(text=f"Этот текст уже на борту: пройдено {fmt_int(saved.index)} из "
                                       f"{fmt_int(len(saved.text))}.")
        else:
            self.status.configure(text="")
        if not adapted:
            self.preview_info.configure(text="Текст пуст")
            self.preview.configure(text="Откройте файл или вставьте текст.")
            return
        runs = [r for r in self.app.store.stats["runs"][-20:] if r.get("cpm")]
        avg = sum(r["cpm"] for r in runs) / len(runs) if runs else 150
        eta = fmt_time(len(adapted) / max(avg, 30) * 60)
        lang = "русский" if missions.detect_lang(adapted) == "ru" else "английский"
        self.preview_info.configure(text=f"{fmt_int(len(adapted))} знаков · {lang} · ≈ {eta}")
        self.preview.configure(text=adapted[:260] + ("…" if len(adapted) > 260 else ""))

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Открыть текст",
                                          filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if not path:
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
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{exc}", parent=self)
                return
        if content is None:
            messagebox.showerror("Ошибка", "Не удалось определить кодировку файла.", parent=self)
            return
        self._original = content
        self._set(content)

    def _paste(self) -> None:
        try:
            content = self.clipboard_get()
        except tk.TclError:
            return
        self._original = content
        self._set(content)

    def _clear(self) -> None:
        if self._get().strip() and not messagebox.askyesno("Очистить", "Очистить поле текста?", parent=self):
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
                                            title="Сохранить подготовленный текст",
                                            filetypes=[("Текстовые файлы", "*.txt")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(adapted)
            except OSError as exc:
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{exc}", parent=self)

    def _start_new(self, switch: bool = True) -> None:
        current = self._get()
        adapted = self._process(current)
        if not adapted.strip():
            messagebox.showwarning("Пустой текст", "Введите текст или откройте файл.", parent=self)
            return
        saved = load_session()
        if saved and saved.index > 0:
            pct = saved.index / len(saved.text) * 100
            msg = (f"Этот текст уже пройден на {pct:.0f}%.\nНачать его с самого начала? "
                   "(Чтобы продолжить — кнопка «Продолжить с места».)") if saved.text == adapted else (
                   f"На борту незаконченный текст (пройдено {pct:.0f}%).\n"
                   "Заменить его новым? Прогресс старого текста будет потерян.")
            if not messagebox.askyesno("Заменить текст?", msg, parent=self):
                return
        original = current
        if self._original and self._process(self._original) == adapted:
            original = self._original
        self.app.start_cargo(adapted, original, switch=switch)
        if not switch:
            self._update_preview()
            self.status.configure(text="Текст сохранён на борт. Таймер стартует с первой клавиши на "
                                       "Мостике (Ctrl+1).", fg=GREEN)
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
        _label(top, "БОРТЖУРНАЛ — СТАТИСТИКА ПОЛЁТОВ", size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        HudButton(top, "★ ДОСКА ПОЧЁТА", lambda: app.show("honor"), color=AMBER, height=34).pack(side=tk.RIGHT)
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

        mid = HudPanel(self, "ДИНАМИКА — ПОСЛЕДНИЕ 30 ПОЛЁТОВ")
        mid.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(4))
        self.chart = LineChart(mid.body)
        self.chart.pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=(px(4), px(10)))
        heat = HudPanel(bottom, "ТЕПЛОВАЯ КАРТА ОШИБОК (ЗА ВСЁ ВРЕМЯ)", accent=AMBER)
        heat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=px(4))
        self.kb = HudKeyboard(heat.body)
        self.kb.pack(fill=tk.BOTH, expand=True)
        row = tk.Frame(heat.body, bg=PANEL)
        row.pack(fill=tk.X)
        self.b_en = HudButton(row, "EN", lambda: self._heat_lang("en"), height=26, font_size=9)
        self.b_en.pack(side=tk.LEFT)
        self.b_ru = HudButton(row, "RU", lambda: self._heat_lang("ru"), height=26, font_size=9)
        self.b_ru.pack(side=tk.LEFT, padx=px(6))
        _label(row, "цифра на клавише — % ошибок; зелёный — хорошо, красный — нужен ремонт",
               fg=MUTED, size=8).pack(side=tk.LEFT, padx=px(8))

        side = HudPanel(bottom, "СЛАБЫЕ КЛАВИШИ")
        side.pack(side=tk.LEFT, fill=tk.BOTH, padx=px(4))
        self.weak_label = _label(side.body, "", fg=TEXT, size=11, mono=True, justify="left", anchor="nw")
        self.weak_label.pack(fill=tk.BOTH, expand=True)
        HudButton(side.body, "⚙ РЕМОНТ СЛАБЫХ КЛАВИШ", lambda: self.app.start_repair(self.heat_lang),
                  color=AMBER).pack(fill=tk.X, pady=(px(6), 0))
        HudButton(side.body, "СБРОСИТЬ СТАТИСТИКУ", self._reset, color=RED, height=28,
                  font_size=8).pack(fill=tk.X, pady=(px(6), 0))

    def _heat_lang(self, lang: str) -> None:
        self.heat_lang = lang
        self.refresh()

    def _reset(self) -> None:
        if messagebox.askyesno("Сброс статистики",
                               "Удалить всю статистику: историю полётов, звёзды миссий, "
                               "звание и тепловую карту?\nЭто нельзя отменить.", parent=self):
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
        done = sum(1 for v in st["missions"].values() if v.get("stars"))
        stars = sum(v.get("stars", 0) for v in st["missions"].values())
        data = [
            ("ВРЕМЯ В ПОЛЁТЕ", fmt_time(st["total_time"]), f"{len(runs)} полётов", CYAN),
            ("НАБРАНО ЗНАКОВ", fmt_int(st["total_chars"]), "правильно набранных", CYAN),
            ("ЛУЧШАЯ СКОРОСТЬ", f"{best:.0f}", f"средняя (10 последних): {avg_cpm:.0f}", GREEN),
            ("ТОЧНОСТЬ", f"{avg_acc:.1f}%", "средняя за 10 полётов", AMBER),
            ("ЗВАНИЕ", rank.upper(), f"{st['xp']} XP" + (f" · до след. {hi - st['xp']}" if hi else "")
             + f" · миссий {done}/20 · ★{stars}", AMBER),
        ]
        for (cap, val, sub), (c, v, s, col) in zip(self.cells, data):
            cap.configure(text=c)
            val.configure(text=v, fg=col, font=theme.font(18 if len(v) < 12 else 12, True, mono=True))
            sub.configure(text=s)
        self.chart.set_runs(runs)
        self.b_en.set_active(self.heat_lang == "en")
        self.b_ru.set_active(self.heat_lang == "ru")
        self.kb.set_lang(self.heat_lang)
        self.kb.set_heat(self.app.store.key_error_rates(min_total=5))
        weak = self.app.store.weakest_keys(self.heat_lang, count=8)
        if weak:
            lines = []
            for ch, r in weak:
                hits, misses = st["keys"].get(ch, [0, 0])
                lines.append(f"«{ch}»  {r * 100:4.1f}%  ({misses} из {hits + misses})")
            self.weak_label.configure(text="\n".join(lines))
        else:
            self.weak_label.configure(text="Данных пока мало.\nПечатайте —\nкомпьютер считает\nошибки по каждой\nклавише.")


# ===========================================================================
# Настройки
# ===========================================================================

class SettingsScreen(tk.Frame):
    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=px(14), pady=(px(10), px(4)))
        _label(top, "НАСТРОЙКИ БОРТОВЫХ СИСТЕМ", size=16, bold=True, bg=BG).pack(side=tk.LEFT)
        panel = HudPanel(self, "СИСТЕМЫ")
        panel.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=px(8))
        self.body = panel.body
        self.toggles: dict[str, HudButton] = {}
        self._row_i = 0
        self._toggle_row("sound", "Звук клавиш", "Щелчок печатной машинки на верную клавишу, «бззт» — на ошибку, "
                         "колокольчик — в конце миссии. Горячая клавиша F9.")
        vol = self._row("Громкость", "Звуки синтезированы программой, лежат в stamina/sounds.")
        self.vol_btns = {}
        for lvl in (1, 2, 3, 4):
            b = HudButton(vol, "▮" * lvl, lambda l=lvl: self._set_volume(l), width=64, height=30)
            b.pack(side=tk.LEFT, padx=px(3))
            self.vol_btns[lvl] = b
        HudButton(vol, "ПРОВЕРИТЬ", self._test_sound, color=AMBER, height=30,
                  font_size=9).pack(side=tk.LEFT, padx=px(10))
        self._toggle_row("translator", "Переводчик UPLINK",
                         "Перевод текущего предложения своего текста через интернет "
                         "(Google / MyMemory). Кэш: папка cache рядом с программой.")
        self._toggle_row("stars", "Звёздное поле", "Звёзды в иллюминаторе летят быстрее, когда вы печатаете "
                         "быстрее. Выключите, если ноутбук греется.")
        ls = self._row("Живой космос (прототип)", "Мостик: за стеклянными панелями летят звёзды, кометы, "
                       "планеты и астероиды. «Лёгкий» — меньше объектов и кадров. Нужен Pillow. "
                       "При «уменьшении движения» Windows картинка неподвижна.")
        self.ls_btns = {}
        for key, name in (("off", "ВЫКЛ"), ("light", "ЛЁГКИЙ"), ("full", "ПОЛНЫЙ")):
            b = HudButton(ls, name, lambda k=key: self._set_living(k), width=96, height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(3))
            self.ls_btns[key] = b
        self._toggle_row("keyboard", "Экранная клавиатура", "Подсветка следующей клавиши и пальца.")
        self._toggle_row("zones", "Цветные зоны пальцев", "Клавиши окрашены по пальцам, как в прежнем Stamina.")
        fs = self._row("Размер шрифта строки", "Размер букв в иллюминаторе.")
        self.font_btns = {}
        for key, name in (("S", "МЕЛКИЙ"), ("M", "СРЕДНИЙ"), ("L", "КРУПНЫЙ")):
            b = HudButton(fs, name, lambda k=key: self._set_font(k), width=100, height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(3))
            self.font_btns[key] = b
        data = self._row("Данные", f"Статистика и прогресс: {DATA_DIR}")
        HudButton(data, "ОТКРЫТЬ ПАПКУ", self._open_data, height=30, font_size=9).pack(side=tk.LEFT)
        _label(self.body, "Горячие клавиши:  F1 — справка  ·  F5 — заново  ·  Esc — пауза  ·  F9 — звук  ·  "
                          "Ctrl+1…5 — разделы  ·  в отчёте: Enter — повторить, → — следующая, R — ремонт",
               fg=MUTED, size=9).pack(anchor="w", pady=(px(14), 0))
        self.refresh()

    def _row(self, title: str, desc: str) -> tk.Frame:
        row = tk.Frame(self.body, bg=PANEL)
        row.pack(fill=tk.X, pady=px(5))
        left = tk.Frame(row, bg=PANEL)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        _label(left, title, size=11, bold=True).pack(anchor="w")
        _label(left, desc, fg=MUTED, size=8, wraplength=px(650), justify="left").pack(anchor="w")
        right = tk.Frame(row, bg=PANEL)
        right.pack(side=tk.RIGHT)
        tk.Frame(self.body, bg=LINE, height=1).pack(fill=tk.X)
        return right

    def _toggle_row(self, key: str, title: str, desc: str) -> None:
        right = self._row(title, desc)
        b = HudButton(right, "ВКЛ", lambda: self._toggle(key), width=110, height=30)
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

    def _set_font(self, key: str) -> None:
        self.app.store.settings["font"] = key
        self.app.apply_settings()
        self.refresh()

    def _test_sound(self) -> None:
        snd = self.app.sound
        if not snd.available:
            messagebox.showinfo("Звук", "Звук доступен только в Windows.", parent=self)
            return
        snd.enabled = True
        snd.click()
        self.after(160, snd.click)
        self.after(320, snd.error)
        self.after(650, lambda: setattr(snd, "enabled", self.app.store.settings["sound"]))

    def _open_data(self) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(DATA_DIR))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            messagebox.showinfo("Данные", str(DATA_DIR), parent=self)

    def refresh(self) -> None:
        st = self.app.store.settings
        for key, b in self.toggles.items():
            on = bool(st.get(key))
            b.set_text("● ВКЛ" if on else "○ ВЫКЛ")
            b.set_color(GREEN if on else MUTED)
            b.set_active(on)
        for lvl, b in self.vol_btns.items():
            b.set_active(st.get("volume") == lvl)
        for k, b in getattr(self, "ls_btns", {}).items():
            b.set_active(k == st.get("living_space", "full"))
        for k, b in self.font_btns.items():
            b.set_active(st.get("font") == k)


# ===========================================================================
# Справка (F1)
# ===========================================================================

class HelpScreen(tk.Frame):
    """Показывает ИНСТРУКЦИЯ.md с простой разметкой."""

    def __init__(self, master, app: "Cockpit") -> None:
        super().__init__(master, bg=BG)
        self.app = app
        panel = HudPanel(self, "СПРАВКА — ИНСТРУКЦИЯ ПО УПРАВЛЕНИЮ КОСМОЛЁТОМ STAR TYPING  (F1)")
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
            lines = (PROJECT_DIR / "ИНСТРУКЦИЯ.md").read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = ["# Инструкция не найдена", "Файл ИНСТРУКЦИЯ.md должен лежать рядом с main.py."]
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
