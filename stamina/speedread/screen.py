"""Вкладка «СКОРОЧТЕНИЕ»: обзор, гипердрайв, тренажёры, библиотека, журнал, настройки."""
from __future__ import annotations

from stamina.i18n import t as _t

import threading
import time
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox

from stamina import theme
from stamina.hud import Readouts, RingGauge
from stamina.theme import (AMBER, BG, BG2, CYAN, FAINT, GREEN, LINE, LINE_HI, MUTED, PANEL, RED,
                           TEXT, blend, px)

from stamina import library as libmod

from .exercises import CATALOG, FlashEx, PyramidEx, SchulteEx, best_text
from .reader import ReaderPage
from .store import SpeedStore
from .ui import HudButton, HudPanel, L, ScrollFrame, Toggle, WpmChart, entry

TABS = [("overview", _t("ОБЗОР")), ("reader", _t("ГИПЕРДРАЙВ")), ("exercises", _t("ТРЕНАЖЁРЫ")),
        ("library", _t("БИБЛИОТЕКА")), ("journal", _t("ЖУРНАЛ")), ("settings", _t("НАСТРОЙКИ"))]

STATUS_RU = {"full": (_t("ОРИГИНАЛ"), GREEN), "recovered": (_t("ОРИГИНАЛ ВОССТАНОВЛЕН"), CYAN),
             "missing": (_t("НЕТ ОРИГИНАЛА"), AMBER)}


def _log(text: str) -> None:
    try:
        from stamina.storage import DATA_DIR
        with open(DATA_DIR / "speedread_error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except Exception:  # noqa: BLE001
        pass


def pct(a: int, b: int) -> str:
    return f"{a / b * 100:.0f}%" if b else "0%"


class SpeedReadScreen(tk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master, bg=BG)
        self.app = app
        self.sstore = SpeedStore(app=app)
        self.lib = libmod.Library()
        self.current = None
        self.migration_report: dict | None = None
        self.bar = tk.Frame(self, bg=BG)
        self.bar.pack(fill=tk.X, padx=px(14), pady=(px(8), px(6)))
        L(self.bar, _t("СКОРОЧТЕНИЕ"), fg=AMBER, size=11, bold=True, bg=BG).pack(side=tk.LEFT, padx=(0, px(14)))
        self.tab_btns: dict[str, HudButton] = {}
        for key, title in TABS:
            b = HudButton(self.bar, title, lambda k=key: self.show(k), height=30, font_size=9)
            b.pack(side=tk.LEFT, padx=px(2))
            self.tab_btns[key] = b
        self.lbl_info = L(self.bar, "", fg=MUTED, size=8, bold=True, bg=BG)
        self.lbl_info.pack(side=tk.RIGHT)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self.pages = {
            "overview": OverviewPage(self.body, self),
            "reader": ReaderPage(self.body, self),
            "exercises": ExercisesPage(self.body, self),
            "library": LibraryPage(self.body, self),
            "journal": JournalPage(self.body, self),
            "settings": SettingsPage(self.body, self),
        }
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")
        self._start_migration()
        self.show("overview")

    # -- миграция в фоне ---------------------------------------------------------------
    def _start_migration(self) -> None:
        if self.lib.index.get("migrated"):
            return
        self.lbl_info.configure(text=_t("БИБЛИОТЕКА: перенос текста…"), fg=AMBER)
        box: dict = {}

        def work():
            try:
                box["r"] = libmod.migrate(self.lib, self.app.store)
            except Exception:  # noqa: BLE001
                box["err"] = traceback.format_exc()
        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                self.after(200, poll)
                return
            if "err" in box:
                _log(box["err"])
                self.lbl_info.configure(text=_t("БИБЛИОТЕКА: ошибка переноса (см. speedread_error.log)"), fg=RED)
                return
            self.migration_report = box.get("r")
            r = self.migration_report or {}
            msg = {"full": _t("текст перенесён с оригиналом"), "recovered": _t("оригинал найден и привязан"),
                   "missing": _t("текст перенесён, оригинал не найден")}.get(r.get("original", ""), _t("готово"))
            self.lbl_info.configure(text=_t("БИБЛИОТЕКА: {0}").format(msg), fg=GREEN)
            self.changed()
        self.after(200, poll)

    # -- интерфейс для страниц -------------------------------------------------------------
    def show(self, name: str) -> None:
        if self.current == "reader" and name != "reader":
            rd: ReaderPage = self.pages["reader"]
            if rd.state == "run":
                rd.pause()
        if name == "reader":
            rd = self.pages["reader"]
            if rd.tid is None:
                tid = self.lib.index.get("active_reading") or (self.lib.ids() or [None])[0]
                if tid is None:
                    self.app.set_status(_t("БИБЛИОТЕКА ПУСТА — добавьте текст"), AMBER)
                    name = "library"
                else:
                    rd.open(tid)
        if name == "exercises":
            self.pages["exercises"].show_catalog()
        self.current = name
        page = self.pages[name]
        if hasattr(page, "refresh"):
            page.refresh()
        page.tkraise()
        for k, b in self.tab_btns.items():
            b.set_active(k == name)
        self.app.focus_set()

    def read(self, tid: str, word: int | None = None) -> None:
        self.pages["reader"].open(tid, word=word)
        self.show("reader")

    def set_focus_mode(self, on: bool) -> None:
        if on:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(fill=tk.X, padx=px(14), pady=(px(8), px(6)), before=self.body)

    def changed(self) -> None:
        for name in ("overview", "library", "journal"):
            if self.current == name:
                self.pages[name].refresh()

    def refresh(self) -> None:
        if self.current in self.pages and hasattr(self.pages[self.current], "refresh"):
            self.pages[self.current].refresh()

    def on_key(self, e) -> None:
        w = e.widget
        if isinstance(w, tk.Entry) and e.keysym != "Escape":
            return
        if isinstance(w, tk.Text) and str(w.cget("state")) == "normal" and e.keysym != "Escape":
            return
        page = self.pages.get(self.current)
        if page is not None and hasattr(page, "on_key"):
            page.on_key(e)

    def on_leave(self) -> None:
        rd: ReaderPage = self.pages["reader"]
        if rd.state == "run":
            rd.pause()

    def close(self) -> None:
        try:
            self.pages["reader"].stop_session(save=True)
            self.pages["exercises"].stop()
        finally:
            self.sstore.save()


# ======================================================================================
class OverviewPage(tk.Frame):
    def __init__(self, master, ctx: SpeedReadScreen) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        sf = ScrollFrame(self)
        sf.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        root = sf.inner
        top = tk.Frame(root, bg=BG)
        top.pack(fill=tk.X)
        top.grid_columnconfigure(1, weight=1)
        launch = HudPanel(top, _t("СТАРТ ГИПЕРДРАЙВА"), accent=AMBER)
        launch.grid(row=0, column=0, sticky="nsew")
        launch.configure(width=px(360), height=px(250))
        launch.grid_propagate(False)
        launch.pack_propagate(False)
        b = launch.body
        self.lbl_title = L(b, "", fg=TEXT, size=13, bold=True, wraplength=px(320), justify="left", anchor="w")
        self.lbl_title.pack(anchor="w")
        self.lbl_status = L(b, "", fg=MUTED, size=8, bold=True)
        self.lbl_status.pack(anchor="w", pady=(px(2), px(6)))
        self.lbl_pos = L(b, "", fg=TEXT, size=9, mono=True, justify="left", anchor="w")
        self.lbl_pos.pack(anchor="w")
        row = tk.Frame(b, bg=PANEL)
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(px(6), 0))
        self.btn_go = HudButton(row, _t("▶ ГИПЕРДРАЙВ"), lambda: self.ctx.show("reader"), color=GREEN, height=40)
        self.btn_go.pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(row, _t("БИБЛИОТЕКА"), lambda: self.ctx.show("library"), height=40, width=120).pack(
            side=tk.LEFT, padx=(px(6), 0))
        chart = HudPanel(top, _t("СКОРОСТЬ ПО СЕССИЯМ · СЛОВ/МИН (ЦИАН) · С ПОНИМАНИЕМ (ЗЕЛЁНЫЙ)"))
        chart.grid(row=0, column=1, sticky="nsew", padx=px(10))
        chart.configure(height=px(250))
        chart.pack_propagate(False)
        self.chart = WpmChart(chart.body, height=190)
        self.chart.pack(fill=tk.BOTH, expand=True)
        rg = HudPanel(top, _t("ПОНИМАНИЕ"))
        rg.grid(row=0, column=2, sticky="nsew")
        rg.configure(width=px(190), height=px(250))
        rg.pack_propagate(False)
        self.ring = RingGauge(rg.body, title=_t("ТЕСТЫ"))
        self.ring.pack(fill=tk.BOTH, expand=True)
        rp = HudPanel(top, _t("ТЕЛЕМЕТРИЯ"), accent=LINE_HI)
        rp.grid(row=0, column=3, sticky="nsew", padx=(px(10), 0))
        rp.configure(width=px(240), height=px(250))
        rp.pack_propagate(False)
        self.readouts = Readouts(rp.body, rows=4)
        self.readouts.pack(fill=tk.BOTH, expand=True)
        L(root, _t("ТРЕНАЖЁРЫ ОБЗОРА"), fg=AMBER, size=10, bold=True, bg=BG).pack(anchor="w", pady=(px(12), px(4)))
        self.cards = tk.Frame(root, bg=BG)
        self.cards.pack(fill=tk.X)

    def refresh(self) -> None:
        lib, st = self.ctx.lib, self.ctx.sstore
        tid = lib.index.get("active_reading") or (lib.ids() or [None])[0]
        m = lib.meta(tid) if tid else None
        if m:
            self.lbl_title.configure(text=m["title"] + (f"\n{m['author']}" if m.get("author") else ""))
            s, col = STATUS_RU.get(m["original"]["status"], ("", MUTED))
            self.lbl_status.configure(text=f"● {s} · {m['lang'].upper()}", fg=col)
            words = m["original"]["words"] or len(lib.prepared(tid).split())
            rw = m["positions"]["reading"].get("word", 0)
            tw = lib.typing_word(tid)
            last = st.data.get("last_wpm", {}).get(tid) or st.settings["wpm_start"]
            self.lbl_pos.configure(text=_t("ЧТЕНИЕ  слово {0:,} / {1:,} · {2}\nПЕЧАТЬ  ").format(rw, words, pct(rw, words)) + (_t("слово {0:,} · {1}").format(tw, pct(tw, words)) if tw else "—") +
                                        _t("\nСКОРОСТЬ СТАРТА  {0} сл/мин").format(last).replace(",", " "))
            self.btn_go.set_enabled(True)
        else:
            self.lbl_title.configure(text=_t("Библиотека пуста"))
            self.lbl_status.configure(text=_t("Добавьте текст в «Библиотеке» или «Своём тексте»"), fg=AMBER)
            self.lbl_pos.configure(text="")
            self.btn_go.set_enabled(False)
        self.chart.set(st.last_sessions(30), int(st.settings["wpm_target"]))
        comp = st.avg_comp()
        self.ring.set(comp * 100 if comp is not None else None, _t("средн. 20 сессий") if comp is not None else _t("нет тестов"))
        sess = st.data["sessions"]
        eff = [s["eff_wpm"] for s in sess if s.get("eff_wpm")]
        self.readouts.set([
            (_t("РЕКОРД, СЛ/МИН"), f"{st.best_wpm() or '—'}", CYAN),
            (_t("ЭФФЕКТ., СЛ/МИН"), f"{eff[-1]}" if eff else "—", GREEN),
            (_t("СЕРИЯ, ДНЕЙ"), f"{st.streak()}", AMBER),
            (_t("XP В ЗВАНИЕ"), f"{st.data['xp'].get('total', 0)}", AMBER),
        ])
        for w in self.cards.winfo_children():
            w.destroy()
        for i, (code, title, desc, ready) in enumerate(CATALOG[1:]):
            card = ExerciseCard(self.cards, code, title, desc, ready,
                                best_text(code, st.exercise_best(code)) if ready else _t("скоро"),
                                lambda c=code: self.ctx.pages["exercises"].launch(c))
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=px(3), pady=px(3))
        for c in range(4):
            self.cards.grid_columnconfigure(c, weight=1)


class ExerciseCard(tk.Frame):
    def __init__(self, master, code, title, desc, ready, best, command) -> None:
        col = CYAN if ready else FAINT
        super().__init__(master, bg=blend(col, BG, 0.5), padx=1, pady=1, cursor="hand2" if ready else "")
        inner = tk.Frame(self, bg=PANEL, padx=px(10), pady=px(8))
        inner.pack(fill=tk.BOTH, expand=True)
        a = L(inner, code, fg=AMBER if ready else FAINT, size=8, bold=True, mono=True)
        a.pack(anchor="w")
        b = L(inner, title.upper(), fg=TEXT if ready else MUTED, size=11, bold=True)
        b.pack(anchor="w")
        c = L(inner, desc, fg=MUTED, size=8, wraplength=px(230), justify="left")
        c.pack(anchor="w")
        d = L(inner, (_t("ЛУЧШЕЕ: ") + best) if ready else _t("В РАЗРАБОТКЕ"), fg=GREEN if ready else FAINT, size=8, bold=True)
        d.pack(anchor="w", pady=(px(4), 0))
        if ready:
            for w in (self, inner, a, b, c, d):
                w.bind("<Button-1>", lambda _e: command())


# ======================================================================================
class ExercisesPage(tk.Frame):
    def __init__(self, master, ctx: SpeedReadScreen) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.catalog = tk.Frame(self, bg=BG)
        self.catalog.grid(row=0, column=0, sticky="nsew")
        self.active = None

    def refresh(self) -> None:
        if self.active is not None:
            return
        for w in self.catalog.winfo_children():
            w.destroy()
        L(self.catalog, _t("ТРЕНАЖЁРЫ ОБЗОРА — расширяют поле зрения и убирают проговаривание. 5–10 минут перед чтением."), fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(14))
        grid = tk.Frame(self.catalog, bg=BG)
        grid.pack(fill=tk.X, padx=px(14), pady=px(8))
        st = self.ctx.sstore
        for i, (code, title, desc, ready) in enumerate(CATALOG[1:]):
            ExerciseCard(grid, code, title, desc, ready,
                         best_text(code, st.exercise_best(code)) if ready else _t("скоро"),
                         lambda c=code: self.launch(c)).grid(row=i // 3, column=i % 3, sticky="nsew",
                                                              padx=px(4), pady=px(4))
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)

    def launch(self, code: str) -> None:
        self.stop()
        cls = {"E-SHL": lambda m, c, x: SchulteEx(m, c, x, gorbov=False),
               "E-GRB": lambda m, c, x: SchulteEx(m, c, x, gorbov=True),
               "E-PYR": PyramidEx, "E-TAC": FlashEx}.get(code)
        if cls is None:
            return
        if self.ctx.current != "exercises":
            self.ctx.current = None
            self.ctx.show("exercises")
        self.active = cls(self, self.ctx, self.show_catalog)
        self.active.grid(row=0, column=0, sticky="nsew")
        self.active.tkraise()

    def stop(self) -> None:
        if self.active is not None:
            self.active.stop()
            self.active.destroy()
            self.active = None

    def show_catalog(self) -> None:
        self.stop()
        self.refresh()
        self.catalog.tkraise()
        self.ctx.changed()

    def on_key(self, e) -> None:
        if self.active is not None:
            self.active.on_key(e)


# ======================================================================================
class LibraryPage(tk.Frame):
    def __init__(self, master, ctx: SpeedReadScreen) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        self.sel: str | None = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = HudPanel(self, _t("ТЕКСТЫ НА БОРТУ"))
        left.grid(row=0, column=0, sticky="nsew", padx=(px(14), px(6)), pady=(0, px(10)))
        left.configure(width=px(380))
        left.grid_propagate(False)
        left.pack_propagate(False)
        acts = tk.Frame(left.body, bg=PANEL)
        acts.pack(fill=tk.X, side=tk.BOTTOM, pady=(px(6), 0))
        HudButton(acts, _t("＋ ОТКРЫТЬ .TXT"), self.open_file, height=32, font_size=8).pack(side=tk.LEFT, fill=tk.X, expand=True)
        HudButton(acts, _t("＋ ОТКРЫТЬ PDF"), self.open_pdf, height=32, font_size=8).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(px(4), 0))
        HudButton(acts, _t("＋ ВСТАВИТЬ"), self.paste_dialog, height=32, font_size=8).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(px(4), 0))
        self.list = ScrollFrame(left.body, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True)
        self.detail = HudPanel(self, _t("ПАСПОРТ ТЕКСТА"), accent=AMBER)
        self.detail.grid(row=0, column=1, sticky="nsew", padx=(px(6), px(14)), pady=(0, px(10)))

    def refresh(self) -> None:
        self.list.clear()
        lib = self.ctx.lib
        metas = lib.all()
        if self.sel not in [m["id"] for m in metas]:
            self.sel = lib.index.get("active_reading") or (metas[0]["id"] if metas else None)
        for m in metas:
            on = m["id"] == self.sel
            row = tk.Frame(self.list.inner, bg=blend(CYAN, BG, 0.8) if on else PANEL, cursor="hand2")
            row.pack(fill=tk.X, pady=1)
            s, col = STATUS_RU.get(m["original"]["status"], ("", MUTED))
            t = L(row, m["title"], fg=TEXT, size=10, bold=True, bg=row["bg"], anchor="w")
            t.pack(fill=tk.X, padx=px(8), pady=(px(4), 0))
            sub = _t("{0} · {1} · {2} сл.").format(m.get('author') or '—', m['lang'].upper(), m['original']['words'] or '?')
            a = L(row, sub, fg=MUTED, size=8, bg=row["bg"], anchor="w")
            a.pack(fill=tk.X, padx=px(8))
            c = L(row, "● " + s, fg=col, size=7, bold=True, bg=row["bg"], anchor="w")
            c.pack(fill=tk.X, padx=px(8), pady=(0, px(4)))
            for w in (row, t, a, c):
                w.bind("<Button-1>", lambda _e, i=m["id"]: self.select(i))
        if not metas:
            L(self.list.inner, _t("Пусто. Добавьте текст: «Открыть .txt» или «Вставить».\nТексты из «Своего текста» попадают сюда сами."), fg=MUTED, size=9,
              justify="left").pack(anchor="w", padx=px(8), pady=px(8))
        self._detail()

    def select(self, tid: str) -> None:
        self.sel = tid
        self.refresh()

    def _detail(self) -> None:
        b = self.detail.body
        for w in b.winfo_children():
            w.destroy()
        lib = self.ctx.lib
        m = lib.meta(self.sel) if self.sel else None
        if not m:
            L(b, _t("Выберите текст слева."), fg=MUTED, size=10).pack(anchor="w")
            return
        tid = m["id"]
        L(b, m["title"], fg=TEXT, size=16, bold=True, anchor="w").pack(fill=tk.X)
        L(b, m.get("author") or _t("автор не указан"), fg=MUTED, size=10, anchor="w").pack(fill=tk.X)
        chips = tk.Frame(b, bg=PANEL)
        chips.pack(anchor="w", pady=px(8))
        s, col = STATUS_RU.get(m["original"]["status"], ("", MUTED))
        for text, c in ((s, col), (m["lang"].upper(), CYAN),
                        (_t("ПЕЧАТЬ: ") + (_t("без заглавных") if m["prepared"]["opts"].get("lower") else _t("с заглавными")), MUTED)):
            L(chips, f" {text} ", fg=c, size=8, bold=True, bg=blend(c, BG, 0.82)).pack(side=tk.LEFT, padx=(0, px(6)))
        words = m["original"]["words"] or len(lib.prepared(tid).split())
        rw = m["positions"]["reading"].get("word", 0)
        tw = lib.typing_word(tid)
        tp = lib.typing_position(tid)
        info = (_t("ВЕРСИЯ ДЛЯ ЧТЕНИЯ   {0:,} зн. · {1:,} слов\nВЕРСИЯ ДЛЯ ПЕЧАТИ   {2:,} зн.\nЧТЕНИЕ              слово {3:,} ({4})\nПЕЧАТЬ              знак {5:,} ({6})").format(m['original']['chars'], words, m['prepared']['chars'], rw, pct(rw, words), tp, pct(tp, m['prepared']['chars']))
                + (_t(" ≈ слово {0:,}").format(tw) if tw else "")).replace(",", " ")
        L(b, info, fg=TEXT, size=10, mono=True, justify="left", anchor="w").pack(fill=tk.X)
        if m["original"].get("note"):
            L(b, m["original"]["note"], fg=MUTED, size=8, anchor="w", wraplength=px(560),
              justify="left").pack(fill=tk.X, pady=(px(4), 0))
        if m["original"]["status"] == "missing":
            L(b, _t("Оригинал не найден: гипердрайв покажет подготовленный текст (без заглавных и знаков). Привяжите файл с оригиналом — позиции сохранятся."), fg=AMBER, size=9,
              wraplength=px(560), justify="left", anchor="w").pack(fill=tk.X, pady=(px(6), 0))
        offer = m.get("full_source_offer")
        if offer and not offer.get("asked"):
            box = tk.Frame(b, bg=blend(GREEN, BG, 0.85), padx=px(10), pady=px(8))
            box.pack(fill=tk.X, pady=(px(10), 0))
            L(box, _t("Найден полный файл книги. Печатаете вы фрагмент — а читать можно всю книгу целиком (отдельной записью; печать не изменится)."), fg=TEXT, size=9, bg=box["bg"],
              wraplength=px(540), justify="left").pack(anchor="w")
            r = tk.Frame(box, bg=box["bg"])
            r.pack(anchor="w", pady=(px(6), 0))
            HudButton(r, _t("ДОБАВИТЬ ВСЮ КНИГУ"), lambda: self.add_full(tid), color=GREEN, height=30,
                      font_size=8).pack(side=tk.LEFT)
            HudButton(r, _t("НЕ НАДО"), lambda: self.dismiss_offer(tid), height=30, font_size=8).pack(
                side=tk.LEFT, padx=px(6))
        acts = tk.Frame(b, bg=PANEL)
        acts.pack(side=tk.BOTTOM, fill=tk.X)
        HudButton(acts, _t("▶ ЧИТАТЬ"), lambda: self.ctx.read(tid), color=GREEN, height=40).pack(
            side=tk.LEFT, padx=(0, px(6)))
        if tw:
            HudButton(acts, _t("ЧИТАТЬ С МЕСТА ПЕЧАТИ"), lambda: self.ctx.read(tid, tw), height=40).pack(
                side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("⌨ ПЕЧАТАТЬ"), lambda: self.type_text(tid), color=CYAN, height=40).pack(
            side=tk.LEFT, padx=(0, px(6)))
        if m["original"]["status"] == "missing":
            HudButton(acts, _t("ПРИВЯЗАТЬ ОРИГИНАЛ"), lambda: self.attach(tid), color=AMBER, height=40).pack(
                side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("ПЕРЕИМЕНОВАТЬ"), lambda: self.rename(tid), height=40).pack(side=tk.LEFT, padx=(0, px(6)))
        HudButton(acts, _t("✕ УДАЛИТЬ"), lambda: self.delete(tid), color=RED, height=40).pack(side=tk.RIGHT)

    # -- действия -----------------------------------------------------------------------
    def _opts(self) -> dict:
        return dict(self.ctx.app.store.settings.get("cargo_opts") or {})

    def open_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title=_t("Текст для библиотеки"),
                                          filetypes=[(_t("Текст или PDF"), "*.txt *.pdf"), (_t("Текст"), "*.txt"),
                                                     ("PDF", "*.pdf"), (_t("Все файлы"), "*.*")])
        if not path:
            return
        if path.lower().endswith(".pdf"):
            self.open_pdf(path)
            return
        try:
            text, _enc = libmod.read_text_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(_t("Библиотека"), _t("Не удалось прочитать файл:\n{0}").format(exc), parent=self)
            return
        from pathlib import Path
        title, author = libmod.guess_title(text, Path(path).stem)
        m = self.ctx.lib.add(text, title=title, author=author, opts=self._opts(),
                             source={"kind": "file", "path": path, "filename": Path(path).name})
        self.sel = m["id"]
        self.refresh()

    def open_pdf(self, path: str | None = None) -> None:
        """PDF → предпросмотр очищенного текста → обычная книга библиотеки (оригинал + подготовленный)."""
        from pathlib import Path
        from stamina.pdf_dialog import import_pdf
        res = import_pdf(self, path)
        if not res:
            return
        text, path, (first, last) = res
        title, author = libmod.guess_title(text, Path(path).stem)
        m = self.ctx.lib.add(text, title=title, author=author, opts=self._opts(),
                             source={"kind": "pdf", "path": path, "filename": Path(path).name,
                                     "pages": [first, last]})
        self.sel = m["id"]
        self.refresh()

    def paste_dialog(self) -> None:
        dlg = tk.Toplevel(self, bg=BG)
        dlg.title(_t("Вставить текст"))
        dlg.transient(self.winfo_toplevel())
        L(dlg, _t("Название:"), fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(10), pady=(px(10), 0))
        e = entry(dlg, width=50)
        e.pack(fill=tk.X, padx=px(10))
        t = tk.Text(dlg, width=80, height=18, bg=BG2, fg=TEXT, insertbackground=CYAN, relief="flat",
                    font=theme.font(10), wrap="word")
        t.pack(fill=tk.BOTH, expand=True, padx=px(10), pady=px(8))
        try:
            t.insert("1.0", self.clipboard_get())
        except tk.TclError:
            pass

        def ok():
            text = t.get("1.0", tk.END).strip()
            if text:
                m = self.ctx.lib.add(text, title=e.get().strip(), opts=self._opts(), source={"kind": "paste"})
                self.sel = m["id"]
            dlg.destroy()
            self.refresh()
        HudButton(dlg, _t("СОХРАНИТЬ В БИБЛИОТЕКУ"), ok, color=GREEN, height=36).pack(pady=(0, px(10)))
        e.focus_set()

    def attach(self, tid: str) -> None:
        path = filedialog.askopenfilename(parent=self, title=_t("Файл с оригиналом"),
                                          filetypes=[(_t("Текст"), "*.txt"), (_t("Все файлы"), "*.*")])
        if not path:
            return
        try:
            text, _enc = libmod.read_text_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(_t("Библиотека"), str(exc), parent=self)
            return
        st = self.ctx.lib.attach_original(tid, text, {"path": path})
        if st:
            self.ctx.app.set_status(_t("ОРИГИНАЛ ПРИВЯЗАН — позиции чтения и печати сохранены"), GREEN)
        else:
            messagebox.showwarning(_t("Библиотека"), _t("Этот файл не совпадает с текстом для печати."), parent=self)
        self.refresh()

    def add_full(self, tid: str) -> None:
        lib = self.ctx.lib
        m = lib.meta(tid)
        path = m["full_source_offer"]["path"]
        try:
            text, _enc = libmod.read_text_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(_t("Библиотека"), _t("Файл недоступен:\n{0}").format(exc), parent=self)
            return
        nm = lib.add(text, title=m["title"] + _t(" (вся книга)"), author=m.get("author", ""),
                     opts=m["prepared"]["opts"], source={"kind": "file", "path": path})
        lib.set_position(nm["id"], "reading", m["positions"]["reading"].get("word", 0))
        self.dismiss_offer(tid)
        self.sel = nm["id"]
        self.refresh()

    def dismiss_offer(self, tid: str) -> None:
        lib = self.ctx.lib
        m = lib.meta(tid)
        if m and m.get("full_source_offer"):
            m["full_source_offer"]["asked"] = True
            lib.save_meta(m)
        self.refresh()

    def rename(self, tid: str) -> None:
        m = self.ctx.lib.meta(tid)
        dlg = tk.Toplevel(self, bg=BG)
        dlg.title(_t("Переименовать"))
        dlg.transient(self.winfo_toplevel())
        L(dlg, _t("Название:"), fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(10), pady=(px(10), 0))
        e1 = entry(dlg, width=44)
        e1.insert(0, m["title"])
        e1.pack(padx=px(10))
        L(dlg, _t("Автор:"), fg=MUTED, size=9, bg=BG).pack(anchor="w", padx=px(10), pady=(px(6), 0))
        e2 = entry(dlg, width=44)
        e2.insert(0, m.get("author", ""))
        e2.pack(padx=px(10))

        def ok():
            self.ctx.lib.rename(tid, e1.get(), e2.get())
            dlg.destroy()
            self.refresh()
        HudButton(dlg, _t("СОХРАНИТЬ"), ok, color=GREEN, height=34).pack(pady=px(10))

    def delete(self, tid: str) -> None:
        m = self.ctx.lib.meta(tid)
        if not messagebox.askyesno(_t("Удалить текст"),
                                   _t("Убрать «{0}» из библиотеки?\nФайлы будут перенесены в backups\\deleted-texts (не стираются).").format(m['title']),
                                   parent=self):
            return
        rd = self.ctx.pages["reader"]
        if rd.tid == tid:
            rd.stop_session(save=False)
            rd.tid = None
        self.ctx.lib.delete(tid)
        self.sel = None
        self.refresh()

    def type_text(self, tid: str) -> None:
        """Отправить текст в «Свой текст» с сохранённой позицией печати."""
        from stamina.session_storage import SessionState, load_session, save_session
        app, lib = self.ctx.app, self.ctx.lib
        m = lib.meta(tid)
        prep, orig = lib.prepared(tid), lib.original(tid)
        saved = load_session()
        if saved is not None and libmod.sha(saved.text) == m["prepared"]["sha256"]:
            app.resume_cargo()
            return
        if saved is not None:
            if not messagebox.askyesno(_t("Печать"), _t("Переключить печать на «{0}»?\nПозиция текущего текста сохранится в библиотеке.").format(m['title']), parent=self):
                return
            try:
                app.screens["bridge"].leave_current()
            except Exception:  # noqa: BLE001
                pass
            saved = load_session()
            cur = lib.find_by_prepared(saved.text) if saved else None
            if cur is None and saved is not None:
                cur = lib.upsert_from_cargo(saved.text, "", app.store.settings.get("cargo_opts"))
            if cur and saved is not None:
                lib.set_position(cur, "typing", saved.index)
        lib.set_active("typing", tid)
        pos = int(m["positions"]["typing"].get("char", 0))
        good_orig = orig if orig and libmod.processor(m["prepared"]["opts"])(orig) == prep else ""
        app.store.save_cargo(prep, good_orig)
        app.screens["cargo"].load_initial(prep, good_orig)
        if 0 < pos < len(prep):
            save_session(SessionState(text=prep, index=pos,
                                      case_sensitive=not m["prepared"]["opts"].get("lower", True)))
            app.resume_cargo()
        else:
            app.start_cargo(prep, good_orig)


# ======================================================================================
class JournalPage(tk.Frame):
    def __init__(self, master, ctx: SpeedReadScreen) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        p = HudPanel(self, _t("ЖУРНАЛ ПОЛЁТОВ · ЧТЕНИЕ И ТРЕНАЖЁРЫ"))
        p.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        self.chart = WpmChart(p.body, height=150)
        self.chart.pack(fill=tk.X)
        self.list = ScrollFrame(p.body, bg=PANEL)
        self.list.pack(fill=tk.BOTH, expand=True, pady=(px(8), 0))

    def refresh(self) -> None:
        st = self.ctx.sstore
        self.chart.set(st.last_sessions(60), int(st.settings["wpm_target"]))
        self.list.clear()
        rows = []
        for s in st.data["sessions"]:
            comp = f"{s['comp'] * 100:.0f}%" if s.get("comp") is not None else "—"
            rows.append((s["ts"], _t("ЧТЕНИЕ   {0:<34} {1:>6} сл  {2:>4} сл/мин  max {3:>4}  понимание {4:>4}  {5:<3} +{6} XP").format(s.get('title', '')[:34], s['words'], s['avg_wpm'], s.get('max_wpm', 0), comp, '★' * s.get('stars', 0), s.get('xp', 0)), CYAN))
        names = {c: t for c, t, _d, _r in CATALOG}
        for code, ex in st.data["exercises"].items():
            for variant, rec in ex.items():
                for r in rec["runs"]:
                    rows.append((r["ts"], _t("ТРЕНАЖЁР {0:<20} {1:<10} результат {2}  {3}").format(names.get(code, code)[:20], variant, r['result'], '★' * r.get('stars', 0)), AMBER))
        rows.sort(key=lambda x: -x[0])
        for ts, text, col in rows[:300]:
            r = tk.Frame(self.list.inner, bg=PANEL)
            r.pack(fill=tk.X)
            L(r, time.strftime("%d.%m %H:%M", time.localtime(ts)), fg=MUTED, size=9, mono=True).pack(side=tk.LEFT)
            L(r, "  " + text, fg=col if col == AMBER else TEXT, size=9, mono=True, anchor="w").pack(side=tk.LEFT)
        if not rows:
            L(self.list.inner, _t("Пока пусто — первый полёт впереди."), fg=MUTED, size=10).pack(anchor="w")


# ======================================================================================
class SettingsPage(tk.Frame):
    def __init__(self, master, ctx: SpeedReadScreen) -> None:
        super().__init__(master, bg=BG)
        self.ctx = ctx
        sf = ScrollFrame(self)
        sf.pack(fill=tk.BOTH, expand=True, padx=px(14), pady=(0, px(10)))
        self.root = sf.inner
        self.built = False

    def refresh(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        st = self.ctx.sstore.settings
        cols = tk.Frame(self.root, bg=BG)
        cols.pack(fill=tk.X)
        cols.grid_columnconfigure(0, weight=1)
        cols.grid_columnconfigure(1, weight=1)
        a = HudPanel(cols, _t("СКОРОСТЬ И РАЗГОН"))
        a.grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        b = HudPanel(cols, _t("ПОКАЗ И ПРОВЕРКА"), accent=AMBER)
        b.grid(row=0, column=1, sticky="nsew", padx=(px(6), 0))

        def stepper(parent, label, key, step, lo, hi, unit=""):
            r = tk.Frame(parent, bg=PANEL)
            r.pack(fill=tk.X, pady=px(3))
            L(r, label, fg=MUTED, size=9, bold=True, width=26, anchor="w").pack(side=tk.LEFT)
            val = L(r, f"{st[key]} {unit}", fg=CYAN, size=11, bold=True, mono=True, width=10)

            def ch(d):
                st[key] = max(lo, min(hi, st[key] + d))
                val.configure(text=f"{st[key]} {unit}")
                self.ctx.sstore.save()
            HudButton(r, "▼", lambda: ch(-step), height=26, width=34, font_size=9).pack(side=tk.LEFT)
            val.pack(side=tk.LEFT)
            HudButton(r, "▲", lambda: ch(step), height=26, width=34, font_size=9).pack(side=tk.LEFT)

        def choice(parent, label, key, options):
            r = tk.Frame(parent, bg=PANEL)
            r.pack(fill=tk.X, pady=px(3))
            L(r, label, fg=MUTED, size=9, bold=True, width=26, anchor="w").pack(side=tk.LEFT)
            btns = {}

            def pick(v):
                st[key] = v
                self.ctx.sstore.save()
                for k, bb in btns.items():
                    bb.set_active(k == v)
            for v, t in options:
                bb = HudButton(r, t, lambda v=v: pick(v), height=26, font_size=8)
                bb.pack(side=tk.LEFT, padx=1)
                bb.set_active(st[key] == v)
                btns[v] = bb

        def toggle(parent, label, key):
            r = tk.Frame(parent, bg=PANEL)
            r.pack(fill=tk.X, pady=px(3))
            L(r, label, fg=MUTED, size=9, bold=True, width=26, anchor="w").pack(side=tk.LEFT)

            def cb(v):
                st[key] = v
                self.ctx.sstore.save()
            Toggle(r, st[key], cb).pack(side=tk.LEFT)

        stepper(a.body, _t("СТАРТОВАЯ СКОРОСТЬ"), "wpm_start", 25, 100, 1500, _t("сл/мин"))
        stepper(a.body, _t("ЦЕЛЕВАЯ СКОРОСТЬ"), "wpm_target", 25, 150, 2000, _t("сл/мин"))
        choice(a.body, _t("РАЗГОН"), "ramp", [("smooth", _t("ПЛАВНЫЙ")), ("steps", _t("СТУПЕНИ")), ("off", _t("ВЫКЛ"))])
        stepper(a.body, _t("ШАГ ПЛАВНОГО РАЗГОНА"), "ramp_step", 5, 5, 100, _t("сл/мин"))
        stepper(a.body, _t("КАЖДЫЕ"), "ramp_every_s", 10, 10, 300, _t("с"))
        toggle(a.body, _t("ПАУЗЫ НА ЗНАКАХ"), "punct_pauses")
        stepper(b.body, _t("СЛОВ В КАДРЕ"), "chunk", 1, 1, 5)
        stepper(b.body, _t("МАКС. ДЛИНА КАДРА"), "chunk_max_chars", 2, 12, 40, _t("зн."))
        stepper(b.body, _t("РАЗМЕР ШРИФТА"), "font_pt", 4, 24, 120, "pt")
        toggle(b.body, _t("КРАСНАЯ БУКВА (ORP)"), "orp")
        toggle(b.body, _t("НАПРАВЛЯЮЩИЕ"), "guides")
        choice(b.body, _t("ТЕСТ ПОНИМАНИЯ"), "quiz", [("always", _t("ВСЕГДА")), ("ask", _t("СПРОСИТЬ")), ("never", _t("НЕТ"))])
        stepper(b.body, _t("ТЕСТ КАЖДЫЕ"), "quiz_words", 250, 250, 5000, _t("слов"))
        choice(b.body, _t("СИНХРОНИЗАЦИЯ С ПЕЧАТЬЮ"), "sync", [("ask", _t("ПОДСКАЗКА")), ("off", _t("НЕТ"))])
        L(self.root, _t("Изменения применяются к следующему запуску гипердрайва. Данные: %APPDATA%\\Stamina\\speedread.json и library\\."), fg=MUTED, size=8, bg=BG).pack(
            anchor="w", pady=px(8))
