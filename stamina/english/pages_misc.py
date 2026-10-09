"""Отсеки (мои списки), бортжурнал (прогресс, достижения, ошибки) и настройки модуля «Английский»."""
from __future__ import annotations

import csv
import datetime as dt
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from stamina import theme
from stamina.hud import HudButton, HudPanel, Readouts, RingGauge, SegmentBar
from stamina.theme import (AMBER, BG, CYAN, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL, PANEL_HI, PURPLE, RED, TEXT,
                           blend, heat_color, px)

from . import paths
from .progress import ACHIEVEMENTS
from .ui import L, ScrollFrame, entry, hline
from .vocab import SETS

try:
    from stamina.missions import rank_for
except Exception:  # noqa: BLE001
    rank_for = None


def _clear(frame) -> None:
    for c in frame.winfo_children():
        c.destroy()


# =============================================================================
# ОТСЕКИ — мои списки
# =============================================================================

class ListsPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.sel = "favorites"
        self.grid_columnconfigure(0, minsize=px(280))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = HudPanel(self, "ГРУЗОВЫЕ ОТСЕКИ")
        left.grid(row=0, column=0, sticky="nsew", padx=(px(12), px(6)), pady=px(8))
        self.lbox = tk.Frame(left.body, bg=PANEL)
        self.lbox.pack(fill=tk.BOTH, expand=True)
        HudButton(left.body, "+ НОВЫЙ ОТСЕК", self.new_list, color=GREEN, height=32).pack(fill=tk.X, pady=(px(6), 0))
        HudButton(left.body, "⇩ ИМПОРТ СЛОВ (.txt)", self.import_txt, height=30, font_size=9).pack(fill=tk.X, pady=px(3))
        right = HudPanel(self, "СОДЕРЖИМОЕ")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, px(12)), pady=px(8))
        self.head = tk.Frame(right.body, bg=PANEL)
        self.head.pack(fill=tk.X)
        self.sf = ScrollFrame(right.body, bg=PANEL)
        self.sf.pack(fill=tk.BOTH, expand=True, pady=(px(6), 0))

    def refresh(self) -> None:
        p = self.ctx.progress
        if not p.list_by_id(self.sel):
            self.sel = "favorites"
        _clear(self.lbox)
        for l in p.lists:
            on = l["id"] == self.sel
            row = tk.Frame(self.lbox, bg=PANEL_HI if on else PANEL, cursor="hand2",
                           highlightthickness=1, highlightbackground=CYAN if on else LINE)
            row.pack(fill=tk.X, pady=px(2))
            a = L(row, ("★ " if l["id"] == "favorites" else "▣ ") + l["name"], fg=CYAN if on else TEXT, size=11,
                  bold=True, bg=row.cget("bg"))
            a.pack(side=tk.LEFT, padx=px(8), pady=px(6))
            b = L(row, str(len(l["slugs"])), fg=AMBER, size=10, bold=True, mono=True, bg=row.cget("bg"))
            b.pack(side=tk.RIGHT, padx=px(8))
            for x in (row, a, b):
                x.bind("<Button-1>", lambda _e, lid=l["id"]: self.select(lid))
        self._render_right()

    def select(self, lid: str) -> None:
        self.sel = lid
        self.refresh()

    def _render_right(self) -> None:
        p, v = self.ctx.progress, self.ctx.vocab
        l = p.list_by_id(self.sel)
        _clear(self.head)
        _clear(self.sf.inner)
        words = [v.get(s) for s in l["slugs"] if v.get(s)]
        known = p.known_or_learned(l["slugs"])
        L(self.head, l["name"], fg=TEXT, size=16, bold=True).pack(side=tk.LEFT)
        L(self.head, f"  {len(words)} слов · знаю/выучено {known}", fg=MUTED, size=9).pack(side=tk.LEFT)
        bar = tk.Frame(self.sf.inner, bg=PANEL)
        bar.pack(fill=tk.X, pady=(0, px(6)))
        en = bool(words)
        b1 = HudButton(bar, "⚙ ПРОВЕРКА СИСТЕМ", lambda: self.ctx.start_review([w["slug"] for w in words]),
                       color=AMBER, height=30, font_size=9)
        b1.pack(side=tk.LEFT, padx=(0, px(4)))
        b2 = HudButton(bar, "▶ МИССИЯ ПО ОТСЕКУ", lambda: self.ctx.start_session(
            "random", source="filtered", ids=[w["slug"] for w in words]), color=GREEN, height=30, font_size=9)
        b2.pack(side=tk.LEFT, padx=px(4))
        b3 = HudButton(bar, "⇧ ЭКСПОРТ CSV", lambda: self.export_csv(l, words), height=30, font_size=9)
        b3.pack(side=tk.LEFT, padx=px(4))
        for b in (b1, b2, b3):
            b.set_enabled(en)
        if l["id"] != "favorites":
            HudButton(bar, "✕ УДАЛИТЬ", lambda: self.delete(l), color=RED, height=30, font_size=9).pack(side=tk.RIGHT)
            HudButton(bar, "✎ ПЕРЕИМЕНОВАТЬ", lambda: self.rename(l), height=30, font_size=9).pack(
                side=tk.RIGHT, padx=px(4))
        if not words:
            L(self.sf.inner, "Отсек пуст. Добавляй слова кнопкой ⊞ на плитках звёздной карты или «В ОТСЕК» в сканере.",
              fg=MUTED, size=10, wraplength=px(600), justify="left").pack(anchor="w", pady=px(20))
            return
        for w in words:
            row = tk.Frame(self.sf.inner, bg=PANEL)
            row.pack(fill=tk.X, pady=px(1))
            ok = p.is_known(w["slug"]) or p.is_learned(w["slug"])
            L(row, "✓" if ok else "·", fg=GREEN if ok else MUTED, size=11, bold=True, width=2).pack(side=tk.LEFT)
            a = L(row, w["word"], fg=TEXT, size=12, bold=True, mono=True, cursor="hand2", width=16, anchor="w")
            a.pack(side=tk.LEFT)
            a.bind("<Button-1>", lambda _e, s=w["slug"]: self.ctx.open_word(s))
            tr = p.tr(w["slug"])
            L(row, f"#{w['rank']}", fg=MUTED, size=8, mono=True, width=7).pack(side=tk.LEFT)
            L(row, (tr + " · " if tr else "") + (w.get("definition") or "")[:90], fg=MUTED, size=9,
              anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
            HudButton(row, "✕", lambda s=w["slug"]: self.remove(s), color=RED, width=32, height=24,
                      font_size=8).pack(side=tk.RIGHT, padx=px(2))
            self.ctx.audio_button(row, "🔊 ГОЛОС", lambda t=w["word"]: t, height=24, font_size=8).pack(
                side=tk.RIGHT)

    def remove(self, slug: str) -> None:
        self.ctx.progress.toggle_in_list(self.sel, slug)
        self.refresh()

    def new_list(self) -> None:
        name = simpledialog.askstring("Новый отсек", "Название отсека:", parent=self)
        if name:
            self.sel = self.ctx.progress.create_list(name)["id"]
            self.refresh()

    def rename(self, l) -> None:
        name = simpledialog.askstring("Переименовать", "Новое название:", initialvalue=l["name"], parent=self)
        if name:
            self.ctx.progress.rename_list(l["id"], name)
            self.refresh()

    def delete(self, l) -> None:
        if messagebox.askyesno("Удалить отсек", f"Удалить отсек «{l['name']}»? Слова и прогресс останутся.",
                               parent=self):
            self.ctx.progress.delete_list(l["id"])
            self.sel = "favorites"
            self.refresh()

    def export_csv(self, l, words) -> None:
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile=f"{l['name']}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        p = self.ctx.progress
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f, delimiter=";")
            wr.writerow(["word", "rank", "pos", "my_translation", "ru", "definition", "example"])
            for w in words:
                s = self.ctx.vocab.sentences(w)
                wr.writerow([w["word"], w["rank"], w["pos"], p.my_tr(w["slug"]), w.get("ru") or "", w.get("definition", ""),
                             s[0]["en"] if s else ""])
        self.ctx.status(f"Отсек сохранён: {path}", GREEN)

    def import_txt(self) -> None:
        path = filedialog.askopenfilename(parent=self, filetypes=[("Текст", "*.txt *.csv"), ("Все", "*.*")])
        if not path:
            return
        try:
            text = open(path, encoding="utf-8-sig").read()
        except (OSError, UnicodeDecodeError) as exc:
            self.ctx.status(f"Не прочитать файл: {exc}", RED)
            return
        import re
        cands = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'\-]*", text)]
        found, miss = [], 0
        for c in dict.fromkeys(cands):
            if self.ctx.vocab.get(c):
                found.append(c)
            else:
                miss += 1
        if not found:
            self.ctx.status("В файле не нашлось слов из словаря", AMBER)
            return
        name = os.path.splitext(os.path.basename(path))[0]
        l = self.ctx.progress.create_list(name)
        l["slugs"].extend(found)
        self.ctx.progress.save()
        self.sel = l["id"]
        self.ctx.status(f"Импорт: {len(found)} слов в отсек «{name}», не найдено в словаре: {miss}", GREEN)
        self.refresh()


# =============================================================================
# ЖУРНАЛ — прогресс
# =============================================================================

MODE_RU = {"reading": "ЧТЕНИЕ", "questions": "ВОПРОСЫ", "speaking": "ГОВОРЕНИЕ", "review": "КАРТОЧКИ"}


class LogPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.sf = ScrollFrame(self, bg=BG)
        self.sf.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(6))

    def refresh(self) -> None:
        _clear(self.sf.inner)
        p, v = self.ctx.progress, self.ctx.vocab
        root = self.sf.inner
        top = tk.Frame(root, bg=BG)
        top.pack(fill=tk.X)
        for i in range(3):
            top.grid_columnconfigure(i, weight=1, uniform="t")
        # -- телеметрия
        tel = HudPanel(top, "ТЕЛЕМЕТРИЯ ПИЛОТА")
        tel.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        lvl, a, b = p.level()
        ro = Readouts(tel.body, rows=5)
        ro.pack(fill=tk.X)
        rank = "—"
        try:
            if rank_for:
                r = rank_for(self.ctx.app.store.stats["xp"])
                rank = r[0] if isinstance(r, tuple) else str(r)
        except Exception:  # noqa: BLE001
            pass
        ro.set([("УРОВЕНЬ", str(lvl), CYAN), ("XP АНГЛИЙСКИЙ", str(p.xp_total), AMBER),
                ("ЗВАНИЕ STAR TYPING", rank, PURPLE), ("СЕРИЯ / ЛУЧШАЯ", f"{p.streak()} / {p.data['xp'].get('best_streak', 0)}", GREEN),
                ("СЕГОДНЯ", f"{p.xp_today()} / {p.settings['daily_goal']} XP", TEXT)])
        sb = SegmentBar(tel.body, f"ДО УРОВНЯ {lvl + 1}", color=CYAN)
        sb.pack(fill=tk.X, pady=(px(6), 0))
        sb.set((p.xp_total - a) / max(1, b - a), f"{p.xp_total - a} / {b - a}")
        # -- наборы
        sets = HudPanel(top, "ОСВОЕНИЕ НАБОРОВ")
        sets.grid(row=0, column=1, sticky="nsew", padx=px(6))
        for sid, lim, name, sub, code in SETS:
            slugs = [w["slug"] for w in v.in_set(sid)]
            if not slugs:
                continue
            k = p.known_or_learned(slugs)
            bar = SegmentBar(sets.body, f"{code} · {name}", color=GREEN if k == len(slugs) else AMBER, height=40)
            bar.pack(fill=tk.X, pady=px(1))
            bar.set(k / len(slugs), f"{k} / {len(slugs)}")
            if sid == "top-1000" and k >= len(slugs) and len(slugs) >= 1000 and not p.data.get("set_1000_done"):
                p.data["set_1000_done"] = True
                p.check_achievements()
        # -- точность
        accp = HudPanel(top, "ТОЧНОСТЬ ПО РЕЖИМАМ (90 ДН)")
        accp.grid(row=0, column=2, sticky="nsew", padx=(px(6), 0))
        acc = p.accuracy_by_mode()
        tot_ok = sum(x[0] for x in acc.values())
        tot = sum(x[1] for x in acc.values())
        ring = RingGauge(accp.body, title="ОБЩАЯ")
        ring.pack(fill=tk.X)
        ring.set(100 * tot_ok / tot if tot else None, f"{tot} ответов")
        ro2 = Readouts(accp.body, rows=4)
        ro2.pack(fill=tk.X)
        ro2.set([(MODE_RU[m], f"{acc[m][0] * 100 // acc[m][1]}% · {acc[m][1]}" if m in acc else "—",
                  CYAN) for m in ("reading", "questions", "speaking", "review")])
        # -- тепловая карта 12 недель
        hp = HudPanel(root, "АКТИВНОСТЬ · 12 НЕДЕЛЬ (XP ЗА ДЕНЬ)")
        hp.pack(fill=tk.X, pady=px(8))
        cv = tk.Canvas(hp.body, bg=PANEL, highlightthickness=0, height=px(7 * 16 + 10))
        cv.pack(fill=tk.X)
        by = p.data["xp"]["by_day"]
        goal = max(1, p.settings["daily_goal"])
        today = dt.date.today()
        start = today - dt.timedelta(days=today.weekday() + 7 * 11)
        cell = px(14)
        gap = px(2)
        for wk in range(12):
            for d in range(7):
                day = start + dt.timedelta(days=wk * 7 + d)
                if day > today:
                    continue
                xp = by.get(day.isoformat(), 0)
                col = blend(PANEL, LINE, 0.6) if xp == 0 else (GREEN if xp >= goal else heat_color(0.25 + 0.25 * xp / goal))
                x = px(40) + wk * (cell + gap)
                y = px(4) + d * (cell + gap)
                cv.create_rectangle(x, y, x + cell, y + cell, fill=col, outline=CYAN if day == today else "")
        for d, n in ((0, "ПН"), (2, "СР"), (4, "ПТ"), (6, "ВС")):
            cv.create_text(px(6), px(4) + d * (cell + gap) + cell // 2, text=n, anchor="w", fill=MUTED,
                           font=theme.font(7))
        cv.create_text(px(40) + 12 * (cell + gap) + px(16), px(10), anchor="nw", fill=MUTED, font=theme.font(8),
                       text=f"зелёный — дневная цель {goal} XP выполнена\nжёлтый — была активность")
        # -- достижения
        ach = HudPanel(root, "ЗНАКИ ОТЛИЧИЯ")
        ach.pack(fill=tk.X)
        g = tk.Frame(ach.body, bg=PANEL)
        g.pack(fill=tk.X)
        got = p.data["achievements"]
        for i, (aid, name, desc, bonus) in enumerate(ACHIEVEMENTS):
            on = aid in got
            f = tk.Frame(g, bg=PANEL_HI if on else PANEL, highlightthickness=1,
                         highlightbackground=AMBER if on else LINE)
            f.grid(row=i // 4, column=i % 4, sticky="nsew", padx=px(3), pady=px(3))
            g.grid_columnconfigure(i % 4, weight=1, uniform="a")
            L(f, ("★ " if on else "☆ ") + name, fg=AMBER if on else MUTED, size=10, bold=True,
              bg=f.cget("bg")).pack(anchor="w", padx=px(8), pady=(px(4), 0))
            L(f, f"{desc} · +{bonus} XP" + (f" · {got[aid]}" if on else ""), fg=MUTED, size=8,
              bg=f.cget("bg"), wraplength=px(260), justify="left").pack(anchor="w", padx=px(8), pady=(0, px(4)))
        # -- ошибки
        mis = p.mistakes(7)
        mp = HudPanel(root, f"ОШИБКИ ЗА 7 ДНЕЙ · {len(mis)}", accent=RED)
        mp.pack(fill=tk.X, pady=px(8))
        if not mis:
            L(mp.body, "Ошибок нет — так держать.", fg=MUTED, size=10).pack(anchor="w")
        else:
            row = tk.Frame(mp.body, bg=PANEL)
            row.pack(fill=tk.X)
            for i, s in enumerate(mis[:30]):
                w = v.get(s)
                if not w:
                    continue
                lb = L(row, w["word"], fg=RED, size=10, bold=True, mono=True, cursor="hand2")
                lb.grid(row=i // 6, column=i % 6, sticky="w", padx=px(8), pady=px(1))
                lb.bind("<Button-1>", lambda _e, sl=s: self.ctx.open_word(sl))
            b = tk.Frame(mp.body, bg=PANEL)
            b.pack(anchor="w", pady=(px(6), 0))
            HudButton(b, "⚙ ПОВТОРИТЬ ОШИБКИ", lambda: self.ctx.start_session("random", source="mistakes"),
                      color=AMBER, height=30, font_size=9).pack(side=tk.LEFT)
            HudButton(b, "КАРТОЧКАМИ", lambda: self.ctx.start_review(mis), height=30, font_size=9).pack(
                side=tk.LEFT, padx=px(6))


# =============================================================================
# НАСТРОЙКИ
# =============================================================================

class SettingsPage(tk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.sf = ScrollFrame(self, bg=BG)
        self.sf.pack(fill=tk.BOTH, expand=True, padx=px(12), pady=px(6))

    def _set(self, key, val) -> None:
        self.ctx.progress.settings[key] = val
        self.ctx.progress.save()
        if key == "asr" and val:
            self.ctx.asr.load_async()
        self.refresh()

    def _row(self, parent, title, hint="") -> tk.Frame:
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill=tk.X, pady=px(3))
        t = tk.Frame(r, bg=PANEL)
        t.pack(side=tk.LEFT, fill=tk.X, expand=True)
        L(t, title, fg=TEXT, size=10, bold=True).pack(anchor="w")
        if hint:
            L(t, hint, fg=MUTED, size=8, wraplength=px(420), justify="left").pack(anchor="w")
        c = tk.Frame(r, bg=PANEL)
        c.pack(side=tk.RIGHT)
        return c

    def _toggle(self, parent, key, title, hint="") -> None:
        c = self._row(parent, title, hint)
        on = bool(self.ctx.progress.settings.get(key))
        HudButton(c, "ВКЛ" if on else "ВЫКЛ", lambda: self._set(key, not on), color=GREEN if on else MUTED,
                  active=on, width=80, height=28, font_size=9).pack()

    def _choice(self, parent, key, title, options, hint="") -> None:
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill=tk.X, pady=px(3))
        L(r, title, fg=TEXT, size=10, bold=True).pack(anchor="w")
        if hint:
            L(r, hint, fg=MUTED, size=8, wraplength=px(520), justify="left").pack(anchor="w")
        c = tk.Frame(r, bg=PANEL)
        c.pack(anchor="w", pady=(px(2), 0))
        cur = self.ctx.progress.settings.get(key)
        for val, text in options:
            HudButton(c, text, lambda v=val: self._set(key, v), active=cur == val, height=28, font_size=9).pack(
                side=tk.LEFT, padx=px(2))

    def refresh(self) -> None:
        _clear(self.sf.inner)
        root = self.sf.inner
        p = self.ctx.progress
        cols = tk.Frame(root, bg=BG)
        cols.pack(fill=tk.BOTH, expand=True)
        cols.grid_columnconfigure(0, weight=1, uniform="c")
        cols.grid_columnconfigure(1, weight=1, uniform="c")
        # -- голос и микрофон
        snd = HudPanel(cols, "СВЯЗЬ: ГОЛОС И МИКРОФОН")
        snd.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)), pady=(0, px(8)))
        s = snd.body
        self._choice(s, "rate", "Скорость озвучки", [(-4, "−4"), (-2, "−2"), (0, "0"), (2, "+2")],
                     "Голос Windows (английский, Microsoft Zira). 🐢 всегда медленнее на 4.")
        c = self._row(s, "Проверить голос")
        self.ctx.audio_button(c, "🔊 ТЕСТ", lambda: "Hello, pilot. All systems are ready.", height=28,
                  font_size=9).pack()
        self._toggle(s, "autoplay", "Автоозвучка слова", "Слово звучит при открытии в сканере и на карточке")
        hline(s).pack(fill=tk.X, pady=px(6))
        asr = self.ctx.asr
        if asr.available():
            st = f"готов к работе · статус модели: {asr.status}"
            col = GREEN
        else:
            st = asr.why_unavailable()
            col = AMBER
        self._toggle(s, "asr", "Распознавание речи (Vosk, без интернета)",
                     "Предложение читается в микрофон, слова сверяются с текстом, балл 0–100")
        L(s, f"Состояние: {st}", fg=col, size=8, wraplength=px(480), justify="left").pack(anchor="w")
        L(s, f"Модель: {paths.vosk_model_dir() or paths.MODELS_DIR}", fg=MUTED, size=8, wraplength=px(480),
          justify="left").pack(anchor="w")
        c = self._row(s, "Проверить микрофон", "Скажи «hello world» — ниже появится распознанный текст")
        HudButton(c, "🎤 ТЕСТ", self.mic_test, color=RED, height=28, font_size=9).pack()
        self.mic_out = L(s, "", fg=MUTED, size=9)
        self.mic_out.pack(anchor="w")
        self._toggle(s, "self_assess", "Самооценка, если микрофон недоступен",
                     "Кнопки «сказал хорошо / так себе / не получилось»")
        # -- обучение
        lp = HudPanel(cols, "ПОЛЁТНЫЙ РЕЖИМ: ОБУЧЕНИЕ")
        lp.grid(row=0, column=1, sticky="nsew", padx=(px(6), 0), pady=(0, px(8)))
        b = lp.body
        self._choice(b, "current_set", "Текущий набор", [(sid, code) for sid, lim, name, sub, code in SETS],
                     "Откуда берутся новые слова для карточек и миссий")
        self._choice(b, "daily_goal", "Дневная цель, XP", [(10, "10"), (30, "30"), (50, "50"), (100, "100")],
                     "Серия дней засчитывается при выполненной цели")
        self._choice(b, "new_per_day", "Новых карточек в день", [(5, "5"), (10, "10"), (20, "20"), (40, "40")])
        self._choice(b, "session_len", "Заданий в миссии", [(5, "5"), (10, "10"), (20, "20")])
        self._toggle(b, "reverse", "Обратные карточки", "Сначала перевод/определение, вспомнить английское слово")
        self._toggle(b, "show_tr", "Сразу показывать перевод примеров", "В сканере перевод предложения виден без нажатия «ПЕРЕВОД»")
        self._toggle(b, "xp_to_rank", "XP идёт в звание Star Typing",
                     "Опыт из «Английского» добавляется к общему опыту и званиям")
        # -- данные
        dp = HudPanel(root, "ДАННЫЕ")
        dp.pack(fill=tk.X)
        d = dp.body
        L(d, f"Прогресс: {p.path}", fg=MUTED, size=8).pack(anchor="w")
        L(d, f"Словарь: {self.ctx.vocab.source} · слов {len(self.ctx.vocab.words)} · "
             f"с подробностями {sum(1 for w in self.ctx.vocab.words if w.get('definition'))}", fg=MUTED,
          size=8).pack(anchor="w")
        r = tk.Frame(d, bg=PANEL)
        r.pack(anchor="w", pady=px(6))
        HudButton(r, "⇧ ЭКСПОРТ", self.export, height=30, font_size=9).pack(side=tk.LEFT, padx=(0, px(4)))
        HudButton(r, "⇩ ИМПОРТ", self.import_, height=30, font_size=9).pack(side=tk.LEFT, padx=px(4))
        HudButton(r, "📂 ОТКРЫТЬ ПАПКУ", self.open_folder, height=30, font_size=9).pack(side=tk.LEFT, padx=px(4))
        HudButton(r, "✕ СБРОС ПРОГРЕССА", self.reset, color=RED, height=30, font_size=9).pack(side=tk.LEFT, padx=px(4))

    def mic_test(self) -> None:
        asr = self.ctx.asr
        if not asr.available():
            self.mic_out.configure(text=asr.why_unavailable(), fg=AMBER)
            return
        asr.load_async()
        asr.poll()
        if asr.listen(max_sec=6):
            self.mic_out.configure(text="Слушаю…", fg=RED)
            self.after(100, self._mic_poll)

    def _mic_poll(self) -> None:
        if not self.mic_out.winfo_exists():
            return
        for kind, val in self.ctx.asr.poll():
            if kind == "level":
                bars = min(20, int(val * 400))
                if not self.mic_out.cget("text").startswith("«"):
                    self.mic_out.configure(text="● СЛУШАЮ  " + "▮" * bars + "▯" * (20 - bars), fg=RED)
            elif kind == "partial":
                self.mic_out.configure(text=f"«{val}»", fg=TEXT)
            elif kind == "processing":
                self.mic_out.configure(text="◌ Распознаю…", fg=AMBER)
            elif kind == "silent":
                self._mic_silent = val
            elif kind == "final":
                silent = getattr(self, "_mic_silent", "")
                self._mic_silent = ""
                self.mic_out.configure(text=f"Распознано: «{val[0]}»" if val else (silent or "Звук есть, но слова не распознаны"),
                                       fg=GREEN if val else (RED if silent else AMBER))
                return
            elif kind == "error":
                self.mic_out.configure(text=f"Ошибка: {val}", fg=RED)
                return
        self.after(100, self._mic_poll)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=f"english-progress-{dt.date.today()}.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            self.ctx.progress.export_to(path)
            self.ctx.status(f"Прогресс сохранён: {path}", GREEN)

    def import_(self) -> None:
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("Импорт", "Заменить текущий прогресс «Английского» данными из файла?", parent=self):
            return
        try:
            info = self.ctx.progress.import_from(path)
            self.ctx.status(f"Импорт выполнен: {info}", GREEN)
        except Exception as exc:  # noqa: BLE001
            self.ctx.status(f"Импорт не удался: {exc}", RED)
        self.ctx.changed()
        self.refresh()

    def open_folder(self) -> None:
        folder = str(self.ctx.progress.path.parent)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:  # noqa: BLE001
            self.ctx.status(f"Не открыть папку: {exc}", RED)

    def reset(self) -> None:
        word = simpledialog.askstring("Сброс прогресса",
                                      "Будут удалены слова «знаю», карточки, отсеки, XP и знаки отличия "
                                      "«Английского» (данные Star Typing не трогаются).\n"
                                      "Для подтверждения введи СБРОС:", parent=self)
        if word and word.strip().upper() == "СБРОС":
            self.ctx.progress.reset()
            self.ctx.status("Прогресс «Английского» сброшен", AMBER)
            self.ctx.changed()
            self.refresh()
